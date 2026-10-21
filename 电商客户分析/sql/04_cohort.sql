-- 仅比较完整月份；首购指观测窗口内的首次正向订单。
-- NULL 表示尚未完整观测，不是流失；零表示可观测但无人复购。
WITH RECURSIVE months(month) AS (
 SELECT '2010-12' UNION ALL
 SELECT strftime('%Y-%m',date(month||'-01','+1 month')) FROM months WHERE month<'2011-11'
), first_purchase AS (
 SELECT customer_id, MIN(substr(order_date,1,7)) AS cohort_month
 FROM customer_orders GROUP BY customer_id
), cohort_size AS (
 SELECT cohort_month,COUNT(*) AS customers FROM first_purchase
 WHERE cohort_month<='2011-11' GROUP BY cohort_month
), active AS (
 SELECT f.cohort_month,substr(o.order_date,1,7) AS active_month,
 COUNT(DISTINCT o.customer_id) AS active_customers
 FROM customer_orders o JOIN first_purchase f USING(customer_id)
 WHERE substr(o.order_date,1,7)<='2011-11'
 GROUP BY f.cohort_month,active_month
), offsets(n) AS (SELECT 0 UNION ALL SELECT n+1 FROM offsets WHERE n<11), grid AS (
 SELECT s.*,n, strftime('%Y-%m',date(cohort_month||'-01','+'||n||' month')) AS target_month
 FROM cohort_size s CROSS JOIN offsets
)
SELECT g.cohort_month,n AS month_offset,customers AS cohort_customers,
CASE WHEN g.target_month<='2011-11' THEN COALESCE(a.active_customers,0) END AS active_customers,
CASE WHEN g.target_month<='2011-11' THEN COALESCE(a.active_customers,0)*1.0/customers END AS retention
FROM grid g LEFT JOIN active a ON g.cohort_month=a.cohort_month AND g.target_month=a.active_month
ORDER BY g.cohort_month,n;
