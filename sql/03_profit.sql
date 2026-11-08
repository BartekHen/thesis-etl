CREATE TABLE IF NOT EXISTS product_cost (
    product_key   text PRIMARY KEY,
    unit_cost_net numeric(12,2) NOT NULL,
    vat_rate      numeric(4,2) NOT NULL DEFAULT 0.23
);

CREATE OR REPLACE VIEW v_order_profit AS
WITH params AS (
    SELECT 1.23::numeric AS vat,
           1.23::numeric AS fee_div
),
items AS (
    SELECT oi.order_id,
           sum(oi.quantity * pc.unit_cost_net)              AS cogs,
           count(*) FILTER (WHERE pc.unit_cost_net IS NULL) AS missing_cost_items
    FROM order_item oi
    LEFT JOIN product_cost pc ON pc.product_key = lower(trim(oi.name))
    GROUP BY oi.order_id
),
fees AS (
    SELECT f.order_id, sum(f.amount) AS fees_signed
    FROM fee f
    JOIN fee_type t ON t.type_id = f.fee_type
    WHERE t.fee_group IN ('commission', 'shipping', 'refund')
      AND f.order_id IS NOT NULL
    GROUP BY f.order_id
)
SELECT co.order_id,
       co.channel_id,
       co.ordered_at,
       round(co.total_amount / p.vat, 2)                    AS revenue_net,
       round(COALESCE(i.cogs, 0), 2)                        AS cogs_net,
       round(-COALESCE(fe.fees_signed, 0) / p.fee_div, 2)   AS fees_net,
       round(co.total_amount / p.vat - COALESCE(i.cogs, 0)
             + COALESCE(fe.fees_signed, 0) / p.fee_div, 2)  AS profit_net,
       COALESCE(i.missing_cost_items, 0)                    AS missing_cost_items
FROM customer_order co
CROSS JOIN params p
LEFT JOIN items i  ON i.order_id  = co.order_id
LEFT JOIN fees  fe ON fe.order_id = co.order_id
WHERE co.status <> 'CANCELLED';