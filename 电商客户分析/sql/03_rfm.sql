-- R 截止日为 2011-12-10；F 为去重订单数，M 为正向交易金额。
-- NTILE 同值时按 customer_id 排序拆分，保证复现；分位不是自然客户类别。
WITH customer_metrics AS (
 SELECT customer_id,
 CAST(julianday('2011-12-10')-julianday(date(MAX(order_date))) AS INTEGER) AS recency_days,
 COUNT(*) AS frequency, SUM(gross_pence) AS monetary_pence
 FROM customer_orders GROUP BY customer_id
), scores AS (
 SELECT *, 6-NTILE(5) OVER(ORDER BY recency_days,customer_id) AS r_score,
 NTILE(5) OVER(ORDER BY frequency,customer_id) AS f_score,
 NTILE(5) OVER(ORDER BY monetary_pence,customer_id) AS m_score
 FROM customer_metrics
)
SELECT *, monetary_pence/100.0 AS monetary_gbp,
 CASE WHEN r_score>=4 AND f_score>=4 AND m_score>=4 THEN 'champions'
      WHEN r_score<=2 AND m_score>=4 THEN 'high_value_inactive'
      WHEN frequency=1 AND r_score>=4 THEN 'recent_one_time'
      WHEN f_score>=4 THEN 'frequent_other'
      ELSE 'other' END AS segment
FROM scores ORDER BY monetary_pence DESC,customer_id;
