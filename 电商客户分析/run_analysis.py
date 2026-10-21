"""下载/导入 UCI Online Retail，执行 SQL 并生成可离线查看的分析报告。"""
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
import argparse, hashlib, html, json, math, sqlite3, urllib.request, zipfile
import pandas as pd

ROOT = Path(__file__).resolve().parent
SOURCE = 'https://archive.ics.uci.edu/static/public/352/online+retail.zip'
def sql(name):
    return (ROOT / 'sql' / name).read_text(encoding='utf-8')
def money_pence(price, qty):
    return int((Decimal(str(price))*int(qty)*100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))

def load_data():
    data = ROOT / 'data'
    data.mkdir(exist_ok=True)
    archive = data / 'online_retail.zip'
    xlsx = data / 'Online Retail.xlsx'
    if not xlsx.exists():
        if not archive.exists():
            with urllib.request.urlopen(SOURCE, timeout=180) as response:
                archive.write_bytes(response.read())
        with zipfile.ZipFile(archive) as z:
            xlsx.write_bytes(z.read('Online Retail.xlsx'))
    raw = pd.read_excel(xlsx, engine='openpyxl')
    n = len(raw)
    duplicate_count = int(raw.duplicated().sum())
    # 完全相同八字段视为重复候选；原始 XLSX 保留用于审计。
    d = raw.drop_duplicates().copy()
    d.columns = ['invoice_no','stock_code','description','quantity','invoice_date','unit_price','customer_id','country']
    for col in ['invoice_no','stock_code','country']:
        d[col] = d[col].astype(str).str.strip()
    d['description'] = d.description.fillna('').astype(str)
    d['customer_id'] = d.customer_id.map(lambda x: None if pd.isna(x) else str(int(x)))
    d['invoice_date'] = pd.to_datetime(d.invoice_date).dt.strftime('%Y-%m-%d %H:%M:%S')
    d['amount_pence'] = [money_pence(p,q) for p,q in zip(d.unit_price,d.quantity)]
    d['record_type'] = 'invalid'
    c = d.invoice_no.str.upper().str.startswith('C')
    d.loc[(d.quantity>0)&(d.unit_price>0)&~c, 'record_type'] = 'sale'
    d.loc[(d.quantity<0)&(d.unit_price>0)&~c, 'record_type'] = 'other_negative'
    d.loc[(d.quantity<0)&(d.unit_price>0)&c, 'record_type'] = 'cancellation'
    audit = {'raw_rows':n,'duplicate_candidates_removed':duplicate_count,
      'deduplicated_rows':len(d),'raw_missing_customer_rows':int(raw.CustomerID.isna().sum()),
      'record_types':{str(k):int(v) for k,v in d.record_type.value_counts().items()},
      'missing_customer_sale_rows':int(((d.record_type=='sale')&d.customer_id.isna()).sum()),
      'date_min':d.invoice_date.min(),'date_max':d.invoice_date.max(),
      'xlsx_sha256':hashlib.sha256(xlsx.read_bytes()).hexdigest(),
      'raw_positive_gbp':int(sum(money_pence(p,q) for p,q in zip(raw.loc[(raw.Quantity>0)&(raw.UnitPrice>0)&~raw.InvoiceNo.astype(str).str.upper().str.startswith('C'),'UnitPrice'],raw.loc[(raw.Quantity>0)&(raw.UnitPrice>0)&~raw.InvoiceNo.astype(str).str.upper().str.startswith('C'),'Quantity'])))/100}
    return d,audit

def checks(con, d, tables):
    checks = []
    def check(name, condition):
        if not condition: raise AssertionError(name)
        checks.append({'check':name,'status':'PASS'})
    sales = d[d.record_type=='sale']
    orders = sales.groupby('invoice_no').amount_pence.sum()
    check('行数分类可对账', con.execute('SELECT COUNT(*) FROM lines').fetchone()[0]==len(d))
    check('订单内客户编号唯一', con.execute('SELECT COUNT(*) FROM (SELECT invoice_no FROM sales GROUP BY invoice_no HAVING COUNT(DISTINCT customer_id)>1)').fetchone()[0]==0)
    check('SQL订单数与独立Pandas去重一致', con.execute('SELECT COUNT(*) FROM orders').fetchone()[0]==len(orders))
    check('SQL订单金额与Pandas逐订单一致', dict(con.execute('SELECT invoice_no,gross_pence FROM orders'))==orders.astype(int).to_dict())
    check('金额汇总守恒', int(sales.amount_pence.sum())==con.execute('SELECT SUM(gross_pence) FROM orders').fetchone()[0])
    cohort = tables['cohort']
    check('同期群第0月为100%', bool((cohort.loc[cohort.month_offset==0,'retention']==1).all()))
    check('复购率范围正确', bool(cohort.retention.dropna().between(0,1).all()))
    check('尚未观测月份保留NULL', bool(cohort[(cohort.cohort_month=='2011-11')&(cohort.month_offset==1)].retention.isna().all()))
    check('12月环比不错误比较部分月份', bool(tables['monthly'].loc[tables['monthly'].month=='2011-12','mom_growth'].isna().all()))
    # 对完整月份，逐客户集合独立核对所有SQL同期群人数。
    co = pd.read_sql_query('SELECT * FROM customer_orders',con)
    co['month'] = co.order_date.str[:7]
    first = co.groupby('customer_id').month.min()
    for row in cohort.itertuples():
        target = (pd.Period(row.cohort_month,freq='M')+row.month_offset).strftime('%Y-%m')
        if target<='2011-11':
            ids = set(first[first==row.cohort_month].index)
            actual = len(ids & set(co.loc[co.month==target,'customer_id']))
            check(f'同期群独立核对 {row.cohort_month} M{row.month_offset}',actual==row.active_customers)
    check('RFM人数等于可识别购买客户数',len(tables['rfm'])==sales.customer_id.nunique())
    check('客户分层互斥且完整',int(tables['segments'].customers.sum())==len(tables['rfm']))
    # 至少两次订单的客户以订单去重口径独立核验。
    frequency = sales.dropna(subset=['customer_id']).groupby('customer_id').invoice_no.nunique()
    check('RFM频次逐客户独立核验',tables['rfm'].set_index('customer_id').frequency.astype(int).to_dict()==frequency.astype(int).to_dict())
    return checks

def dashboard(tables, summary):
    m=tables['monthly']; seg=tables['segments']; cohort=tables['cohort']
    maxval=m.gross_gbp.max(); bars=[]
    for i,r in enumerate(m.itertuples()):
        x=66+i*64; height=r.gross_gbp/maxval*200
        bars.append(f'<rect x="{x}" y="{230-height:.1f}" width="38" height="{height:.1f}" fill="{"#aaa" if r.coverage=="partial_month" else "#28627b"}"><title>{r.month}: £{r.gross_gbp:,.2f}</title></rect><text x="{x+19}" y="251" text-anchor="middle" font-size="11">{r.month[2:]}</text>')
    matrix=cohort.pivot(index='cohort_month',columns='month_offset',values='retention')
    matrixhtml='<table><thead><tr><th>首购月</th>'+''.join(f'<th>M{i}</th>' for i in matrix.columns)+'</tr></thead><tbody>'
    for month,row in matrix.iterrows():
        matrixhtml+=f'<tr><th>{month}</th>'+''.join('<td style="background:#eee">未观测</td>' if pd.isna(v) else f'<td style="background:rgba(40,98,123,{v*.60:.2f})">{v:.1%}</td>' for v in row)+'</tr>'
    matrixhtml+='</tbody></table>'
    labels={'champions':'核心价值客户','high_value_inactive':'高价值低活跃客户','recent_one_time':'近期单次购买客户','frequent_other':'其他高频客户','other':'其他客户'}
    rows=''.join(f'<tr><td>{labels[r.segment]}</td><td>{r.customers:,}</td><td>{r.customer_share:.1%}</td><td>£{r.gross_gbp:,.2f}</td><td>{r.revenue_share:.1%}</td></tr>' for r in seg.itertuples())
    payload=tables['rfm'][['customer_id','segment','recency_days','frequency','monetary_gbp']].to_json(orient='records')
    doc=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>电商经营与客户分析</title>
<style>body{{font:15px/1.7 -apple-system,BlinkMacSystemFont,"Microsoft YaHei",sans-serif;background:#f5f7f8;color:#172f3e;max-width:1120px;margin:auto;padding:32px}}h1{{font-size:30px}}h2{{margin-top:35px}}.stats{{display:flex;gap:18px;flex-wrap:wrap}}.stat{{background:white;padding:18px 24px;flex:1;min-width:180px}}.stat b{{font-size:26px;display:block}}table{{border-collapse:collapse;width:100%;background:white;font-size:13px}}td,th{{border:1px solid #d8dfe3;padding:7px;text-align:right}}th:first-child,td:first-child{{text-align:left}}thead{{background:#e5edf0}}.scroll{{overflow:auto}}select{{padding:8px}}svg{{width:100%;background:white}}a{{color:#28627b}}small,.note{{color:#526775}}.note{{font-size:13px}}</style>
<h1>电商经营与客户分析</h1><p>UCI Online Retail 公开数据实践 · SQL + Python · 分析制作于 2026-10-07</p>
<div class="stats"><div class="stat">正向交易金额<b>£{summary['gross_gbp']:,.0f}</b></div><div class="stat">正向订单<b>{summary['orders']:,}</b></div><div class="stat">可识别客户<b>{summary['customers']:,}</b></div><div class="stat">重复购买客户占比<b>{summary['repeat_customer_share']:.1%}</b></div></div>
<p class="note">交易窗口 2010-12-01 至 2011-12-09。正向金额含未识别客户及运费等交易项，不是会计净收入。客户指标仅覆盖可识别客户；分层未扣回取消金额。</p>
<h2>月度正向交易金额</h2><svg viewBox="0 0 940 285" role="img" aria-label="月度正向交易金额柱状图"><text x="16" y="20" font-size="13">GBP · 峰值 £{maxval:,.0f}</text>{''.join(bars)}</svg><p class="note">灰色的 2011-12 仅覆盖 1 至 9 日，已禁用环比比较。悬停柱体可看具体金额。</p>
<h2>RFM 客户分层</h2><table><thead><tr><th>分层</th><th>客户数</th><th>人数占比</th><th>历史正向金额</th><th>金额占比</th></tr></thead><tbody>{rows}</tbody></table><p class="note">R 为截至 2011-12-10 距最近订单天数；F 为订单数；M 为正向金额。五分位及分层规则见 sql/03_rfm.sql。分层用于提出运营假设，未经过活动效果验证。</p>
<h2>首购同期群月度复购</h2><div class="scroll">{matrixhtml}</div><p class="note">M1 指首购后的下一个自然月再次购买比例，不是次日/30天留存。首购是观测窗口内首次购买；未观测不等于零。</p>
<h2>客户分层筛选</h2><select id="filter" aria-label="选择客户分层"><option value="all">全部客户</option>{''.join(f'<option value="{k}">{v}</option>' for k,v in labels.items())}</select><span id="count"></span><p class="note">展示所选分层金额最高的前 20 位匿名客户。原始编号只用于公开数据实践。</p><table><thead><tr><th>客户编号</th><th>距上次购买天数</th><th>订单数</th><th>正向金额 GBP</th></tr></thead><tbody id="customers"></tbody></table>
<h2>取消金额核查</h2><p>{summary['nonpositive_signed_customers']} 位购买客户的窗口带符号金额不大于零，应排除于金额导向的优先触达；另有 {summary['targeting_manual_review_customers']} 位客户的取消金额达到正向金额的 50%，需进一步复核。这是客户粒度的敏感性检查，不是原订单逐笔退款匹配。</p><p><a href="value_sensitivity.csv">客户金额与取消核查明细</a> · <a href="largest_orders.csv">大额订单核查</a></p>
<h2>可复查的分析结果</h2><p><a href="monthly.csv">月度指标</a> · <a href="segments.csv">分层汇总</a> · <a href="rfm.csv">客户明细</a> · <a href="cohort.csv">复购同期群</a> · <a href="cancellations.csv">取消交易</a> · <a href="analysis_report.md">分析报告</a></p><p class="note">来源：<a href="https://archive.ics.uci.edu/dataset/352/online+retail">Chen, D. (2015). Online Retail. UCI</a>，CC BY 4.0。数据质量与验证见 audit.json、validation.json。</p>
<script>const data={payload}; const labels={json.dumps(labels,ensure_ascii=False)}; const filter=document.getElementById('filter');function render(){{const selected=data.filter(r=>filter.value==='all'||r.segment===filter.value);document.getElementById('count').textContent=' 共 '+selected.length+' 位客户';document.getElementById('customers').innerHTML=selected.slice(0,20).map(r=>'<tr><td>'+r.customer_id+'</td><td>'+r.recency_days+'</td><td>'+r.frequency+'</td><td>'+r.monetary_gbp.toLocaleString('en-GB',{{minimumFractionDigits:2,maximumFractionDigits:2}})+'</td></tr>').join('');}}filter.addEventListener('change',render);render();</script></html>'''
    (ROOT/'outputs'/'dashboard.html').write_text(doc,encoding='utf-8')

def main():
    d,audit=load_data()
    out=ROOT/'outputs';out.mkdir(exist_ok=True)
    with sqlite3.connect(ROOT/'data'/'retail.sqlite') as con:
        con.executescript('DROP TABLE IF EXISTS rfm;'+sql('01_schema.sql'))
        d.to_sql('lines',con,if_exists='append',index=False,chunksize=10000)
        tables={}
        for file,name in [('02_monthly_kpis.sql','monthly'),('03_rfm.sql','rfm'),('04_cohort.sql','cohort'),('05_customer_concentration.sql','concentration'),('06_cancellations.sql','cancellations'),('07_segment_summary.sql','segments'),('08_customer_value_sensitivity.sql','value_sensitivity')]:
            frame=pd.read_sql_query(sql(file),con);tables[name]=frame
            if name=='rfm':frame.to_sql('rfm',con,if_exists='replace',index=False)
            frame.to_csv(out/f'{name}.csv',index=False)
        validation=checks(con,d,tables)
        rfm=tables['rfm'];cohort=tables['cohort'];concentration=tables['concentration']
        m1=cohort[(cohort.month_offset==1)&cohort.retention.notna()]
        top=concentration.iloc[math.ceil(len(concentration)*.2)-1]
        summary={'orders':int(con.execute('SELECT COUNT(*) FROM orders').fetchone()[0]),'customers':len(rfm),
          'gross_gbp':int(d.loc[d.record_type=='sale','amount_pence'].sum())/100,
          'known_customer_gross_gbp':int(rfm.monetary_pence.sum())/100,
          'repeat_customer_share':float((rfm.frequency>=2).mean()),
          'top20_customer_revenue_share':float(top.cumulative_revenue_share),
          'top20_customers':int(top.customer_rank),
          'weighted_m1_retention':float(m1.active_customers.sum()/m1.cohort_customers.sum()),
          'm1_numerator':int(m1.active_customers.sum()),'m1_denominator':int(m1.cohort_customers.sum()),
          'sale_rows':audit['record_types']['sale'],
          'removed_positive_gbp':round(audit['raw_positive_gbp']-int(d.loc[d.record_type=='sale','amount_pence'].sum())/100,2),
          'nonpositive_signed_customers':int((tables['value_sensitivity'].signed_gbp<=0).sum()),
          'targeting_manual_review_customers':int((tables['value_sensitivity'].targeting_check=='manual_review_high_cancellation').sum())}
        # 额外保存最大订单以检查集中度是否受大额异常影响。
        pd.read_sql_query('SELECT * FROM orders ORDER BY gross_pence DESC LIMIT 10',con).to_csv(out/'largest_orders.csv',index=False)
    for name,value in [('audit',audit),('summary',summary),('validation',validation)]:
        (out/f'{name}.json').write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    dashboard(tables,summary)
    print(json.dumps({'summary':summary,'audit':audit,'validation_checks':len(validation)},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
