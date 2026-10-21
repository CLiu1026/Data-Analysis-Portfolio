-- C 前缀是取消记录，不等于商品实物退货；不能关联回原订单，故不称真实退货率。
WITH positive AS (
 SELECT substr(invoice_date,1,7) AS month,SUM(amount_pence) AS sale_pence FROM sales GROUP BY month
), negative AS (
 SELECT substr(invoice_date,1,7) AS month,COUNT(DISTINCT invoice_no) AS cancellation_invoices,
 SUM(-amount_pence) AS cancellation_pence FROM lines WHERE record_type='cancellation' GROUP BY month
)
SELECT p.month,p.sale_pence/100.0 AS gross_gbp,
COALESCE(n.cancellation_pence,0)/100.0 AS cancellation_gbp,
COALESCE(n.cancellation_pence,0)*1.0/p.sale_pence AS cancellation_to_sales_value,
COALESCE(n.cancellation_invoices,0) AS cancellation_invoices,
(p.sale_pence-COALESCE(n.cancellation_pence,0))/100.0 AS signed_transaction_gbp
FROM positive p LEFT JOIN negative n USING(month) ORDER BY month;
