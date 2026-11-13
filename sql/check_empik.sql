SELECT status, count(*) AS zam, min(ordered_at)::date AS od, max(ordered_at)::date AS do, sum(total_amount) AS suma
FROM customer_order WHERE channel_id = 3 GROUP BY status ORDER BY zam DESC;

SELECT count(*) AS oplaty, sum(amount) AS suma_prowizji FROM fee WHERE channel_id = 3;

SELECT count(*) AS pozycje, count(DISTINCT oi.name) AS produkty
FROM order_item oi JOIN customer_order o USING (order_id) WHERE o.channel_id = 3;

SELECT channel_id, count(*) AS zam, sum(revenue_net) AS przychod, sum(cogs_net) AS koszt,
       sum(fees_net) AS oplaty, sum(profit_net) AS zysk, sum(missing_cost_items) AS bez_kosztu
FROM v_order_profit GROUP BY channel_id ORDER BY channel_id;

SELECT oi.name, count(*) AS ile
FROM order_item oi JOIN customer_order o USING (order_id)
LEFT JOIN product_cost pc ON pc.product_key = lower(trim(oi.name))
WHERE o.channel_id = 3 AND pc.product_key IS NULL
GROUP BY oi.name ORDER BY ile DESC LIMIT 15;