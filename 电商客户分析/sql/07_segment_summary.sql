-- rfm 是运行器将 03 查询结果写入的分析表。
SELECT segment,COUNT(*) AS customers,SUM(frequency) AS orders,
SUM(monetary_pence)/100.0 AS gross_gbp,AVG(recency_days) AS average_recency,
COUNT(*)*1.0/(SELECT COUNT(*) FROM rfm) AS customer_share,
SUM(monetary_pence)*1.0/(SELECT SUM(monetary_pence) FROM rfm) AS revenue_share
FROM rfm GROUP BY segment ORDER BY gross_gbp DESC;
