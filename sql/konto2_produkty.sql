-- 1) Kanał 2 (Allegro konto_2): średnia cena sprzedaży vs koszt zakupu per produkt (netto, za sztukę)
SELECT left(lower(trim(oi.name)), 60)                               AS produkt,
       sum(oi.quantity)                                             AS szt,
       round(sum(oi.quantity * oi.unit_price) / sum(oi.quantity) / 1.23, 2) AS cena_netto_szt,
       pc.unit_cost_net                                             AS koszt_szt,
       round(sum(oi.quantity * oi.unit_price) / sum(oi.quantity) / 1.23
             - pc.unit_cost_net, 2)                                 AS marza_szt,
       round(100 * (sum(oi.quantity * oi.unit_price) / sum(oi.quantity) / 1.23
             - pc.unit_cost_net)
             / (sum(oi.quantity * oi.unit_price) / sum(oi.quantity) / 1.23), 1) AS marza_proc
FROM order_item oi
JOIN customer_order co ON co.order_id = oi.order_id
LEFT JOIN product_cost pc ON pc.product_key = lower(trim(oi.name))
WHERE co.channel_id = 2
  AND co.status NOT IN ('CANCELLED', 'CANCELED', 'REFUSED')
GROUP BY 1, pc.unit_cost_net
ORDER BY szt DESC;

-- 2) Kontrola: czy total_amount = suma pozycji + wysyłka (kanał 2)
SELECT count(*)                                                     AS zam,
       count(*) FILTER (WHERE abs(co.total_amount - s.pozycje - COALESCE(co.shipping_cost, 0)) > 0.01) AS niezgodne,
       sum(co.total_amount)                                         AS total_amount,
       sum(s.pozycje)                                               AS suma_pozycji,
       sum(COALESCE(co.shipping_cost, 0))                           AS wysylka,
       max(s.max_qty)                                               AS max_ilosc
FROM customer_order co
JOIN (SELECT order_id,
             sum(quantity * unit_price) AS pozycje,
             max(quantity)              AS max_qty
      FROM order_item GROUP BY order_id) s ON s.order_id = co.order_id
WHERE co.channel_id = 2
  AND co.status NOT IN ('CANCELLED', 'CANCELED', 'REFUSED');