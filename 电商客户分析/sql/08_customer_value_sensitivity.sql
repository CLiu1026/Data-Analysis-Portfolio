-- 在客户粒度汇总取消金额，用于毛额分层的敏感性核对。
-- 无法逐笔匹配原订单，此处是窗口内带符号金额，不是会计确认的净收入。
WITH cancel AS (
 SELECT customer_id,SUM(amount_pence) AS cancellation_pence
 FROM lines WHERE record_type='cancellation' AND customer_id IS NOT NULL GROUP BY customer_id
)
SELECT r.customer_id,r.segment,r.frequency,r.recency_days,
       r.monetary_pence/100.0 AS gross_gbp,
       -COALESCE(c.cancellation_pence,0)/100.0 AS cancellation_gbp,
       (r.monetary_pence+COALESCE(c.cancellation_pence,0))/100.0 AS signed_gbp,
       CASE WHEN r.monetary_pence+COALESCE(c.cancellation_pence,0)<=0
         THEN 'exclude_from_value_targeting'
         WHEN -COALESCE(c.cancellation_pence,0)*1.0/r.monetary_pence>=0.5
         THEN 'manual_review_high_cancellation' ELSE 'normal' END AS targeting_check
FROM rfm r LEFT JOIN cancel c USING(customer_id) ORDER BY gross_gbp DESC;
