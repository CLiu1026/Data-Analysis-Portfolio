WITH line_month AS (
 SELECT substr(invoice_date,1,7) AS month, SUM(amount_pence) AS gross_pence,
 COUNT(*) AS sale_lines FROM sales GROUP BY month
), order_month AS (
 SELECT substr(order_date,1,7) AS month, COUNT(*) AS orders,
 COUNT(DISTINCT customer_id) AS known_customers FROM orders GROUP BY month
), previous AS (
 SELECT l.*, o.orders, o.known_customers,
 LAG(l.gross_pence) OVER(ORDER BY l.month) AS previous_pence
 FROM line_month l JOIN order_month o USING(month)
)
SELECT month, sale_lines, orders, known_customers, gross_pence/100.0 AS gross_gbp,
       gross_pence/100.0/orders AS average_order_gbp,
       CASE WHEN month<'2011-12' THEN (gross_pence*1.0/previous_pence)-1 END AS mom_growth,
       CASE WHEN month='2011-12' THEN 'partial_month' ELSE 'complete_month' END AS coverage
FROM previous ORDER BY month;
