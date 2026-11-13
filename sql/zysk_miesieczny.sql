-- Zysk netto per miesiąc: Allegro konto_1 (1), Allegro konto_2 (2), Empik (3), 2025-2026
WITH miesiace AS (
    SELECT generate_series('2025-01-01'::date, '2026-12-01'::date, interval '1 month')::date AS m
),
dane AS (
    SELECT date_trunc('month', ordered_at AT TIME ZONE 'Europe/Warsaw')::date AS m,
           channel_id, revenue_net, profit_net
    FROM v_order_profit
    WHERE channel_id IN (1, 2, 3)
)
SELECT to_char(mi.m, 'YYYY-MM')                                                   AS miesiac,
       round(COALESCE(sum(d.profit_net) FILTER (WHERE d.channel_id = 1), 0), 0)   AS allegro_1,
       round(COALESCE(sum(d.profit_net) FILTER (WHERE d.channel_id = 2), 0), 0)   AS allegro_2,
       round(COALESCE(sum(d.profit_net) FILTER (WHERE d.channel_id = 3), 0), 0)   AS empik,
       round(COALESCE(sum(d.revenue_net), 0), 0)                                  AS przychod_razem,
       round(COALESCE(sum(d.profit_net), 0), 0)                                   AS zysk_razem,
       round(100 * sum(d.profit_net) / NULLIF(sum(d.revenue_net), 0), 1)          AS marza_proc
FROM miesiace mi
LEFT JOIN dane d ON d.m = mi.m
GROUP BY mi.m
ORDER BY mi.m;

-- Podsumowanie per kanał: okres i marża
SELECT channel_id,
       min(ordered_at)::date                               AS od,
       max(ordered_at)::date                               AS do,
       count(*)                                            AS zam,
       round(sum(profit_net), 0)                           AS zysk,
       round(100 * sum(profit_net) / sum(revenue_net), 1)  AS marza_proc
FROM v_order_profit
GROUP BY channel_id
ORDER BY channel_id;

-- Podsumowanie per rok
SELECT extract(year FROM ordered_at AT TIME ZONE 'Europe/Warsaw')::int  AS rok,
       round(sum(profit_net) FILTER (WHERE channel_id = 1), 0)          AS allegro_1,
       round(sum(profit_net) FILTER (WHERE channel_id = 2), 0)          AS allegro_2,
       round(sum(profit_net) FILTER (WHERE channel_id = 3), 0)          AS empik,
       round(sum(profit_net), 0)                                        AS zysk_razem,
       round(100 * sum(profit_net) / sum(revenue_net), 1)               AS marza_proc
FROM v_order_profit
GROUP BY 1
ORDER BY 1;
