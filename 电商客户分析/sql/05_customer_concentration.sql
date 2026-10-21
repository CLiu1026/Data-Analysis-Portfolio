WITH customer_value AS (
 SELECT customer_id,SUM(gross_pence) AS gross_pence,COUNT(*) AS orders
 FROM customer_orders GROUP BY customer_id
), ranked AS (
 SELECT *, ROW_NUMBER() OVER(ORDER BY gross_pence DESC,customer_id) AS customer_rank,
 COUNT(*) OVER() AS customer_count,
 SUM(gross_pence) OVER() AS total_pence,
 SUM(gross_pence) OVER(ORDER BY gross_pence DESC,customer_id ROWS UNBOUNDED PRECEDING) AS running_pence
 FROM customer_value
)
SELECT customer_id,customer_rank,orders,gross_pence/100.0 AS gross_gbp,
customer_rank*1.0/customer_count AS customer_fraction,
running_pence*1.0/total_pence AS cumulative_revenue_share
FROM ranked ORDER BY customer_rank;
