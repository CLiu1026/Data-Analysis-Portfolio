-- SQLite 3.25+; 金额采用整数便士，避免浮点汇总误差。
DROP VIEW IF EXISTS customer_orders;
DROP VIEW IF EXISTS orders;
DROP VIEW IF EXISTS sales;
DROP TABLE IF EXISTS lines;
CREATE TABLE lines (
  line_id INTEGER PRIMARY KEY, invoice_no TEXT NOT NULL, stock_code TEXT NOT NULL,
  description TEXT, quantity INTEGER NOT NULL, invoice_date TEXT NOT NULL,
  unit_price REAL NOT NULL, customer_id TEXT, country TEXT NOT NULL,
  amount_pence INTEGER NOT NULL, record_type TEXT NOT NULL
    CHECK(record_type IN ('sale','cancellation','other_negative','invalid'))
);
CREATE INDEX idx_invoice ON lines(invoice_no);
CREATE INDEX idx_customer_date ON lines(customer_id,invoice_date);
CREATE VIEW sales AS SELECT * FROM lines WHERE record_type='sale';
-- 先汇总至订单粒度，不能把商品行数当作购买频次。
CREATE VIEW orders AS
SELECT invoice_no, MIN(invoice_date) AS order_date, MIN(customer_id) AS customer_id,
       SUM(amount_pence) AS gross_pence, COUNT(*) AS line_count
FROM sales GROUP BY invoice_no;
CREATE VIEW customer_orders AS SELECT * FROM orders WHERE customer_id IS NOT NULL;
