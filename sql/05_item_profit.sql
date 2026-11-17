-- 05: grupa produktu i zrodlo kosztu w product_cost + widok rentownosci per pozycja (do Power BI)
-- Uruchomienie na istniejacej bazie (idempotentne):
--   Get-Content sql\05_item_profit.sql | docker exec -i thesis_db psql -U thesis -d ecommerce
-- Potem: python -m app.costs.assign_costs  (wypelnia product_group i cost_source)

ALTER TABLE product_cost ADD COLUMN IF NOT EXISTS product_group text;
ALTER TABLE product_cost ADD COLUMN IF NOT EXISTS cost_source   text;  -- faktury_aliexpress / deklaracja / break_even

-- Przychod i oplaty zamowienia dzielone na pozycje proporcjonalnie do ich wartosci
-- (ta sama logika co app/costs/profit_by_group.py). Anulowane pomijane przez v_order_profit.
CREATE OR REPLACE VIEW v_item_profit AS
WITH it AS (
    SELECT oi.item_id,
           oi.order_id,
           lower(trim(oi.name))                                        AS product_key,
           oi.name                                                     AS product_name,
           oi.quantity,
           oi.quantity * oi.unit_price                                 AS val,
           sum(oi.quantity * oi.unit_price) OVER (PARTITION BY oi.order_id) AS order_val
    FROM order_item oi
)
SELECT it.item_id,
       it.order_id,
       v.channel_id,
       v.ordered_at,
       it.product_key,
       it.product_name,
       COALESCE(pc.product_group, 'brak')                              AS product_group,
       pc.cost_source,
       it.quantity,
       round(v.revenue_net * it.val / NULLIF(it.order_val, 0), 2)      AS revenue_net,
       round(v.fees_net    * it.val / NULLIF(it.order_val, 0), 2)      AS fees_net,
       round(it.quantity * COALESCE(pc.unit_cost_net, 0), 2)           AS cogs_net,
       round((v.revenue_net - v.fees_net) * it.val / NULLIF(it.order_val, 0)
             - it.quantity * COALESCE(pc.unit_cost_net, 0), 2)         AS profit_net
FROM it
JOIN v_order_profit v      ON v.order_id = it.order_id
LEFT JOIN product_cost pc  ON pc.product_key = it.product_key;

-- Kontrola: suma zysku z pozycji = suma zysku z zamowien (roznica tylko z zaokraglen)
SELECT (SELECT round(sum(profit_net), 0) FROM v_item_profit)  AS zysk_pozycje,
       (SELECT round(sum(profit_net), 0) FROM v_order_profit) AS zysk_zamowienia;
