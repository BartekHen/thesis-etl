"""Zysk netto per grupa kosztowa i zrodlo kosztu (faktury AliExpress / inne).

Przychod i oplaty zamowienia (z v_order_profit) dzielone na pozycje
proporcjonalnie do wartosci pozycji; koszt = ilosc * unit_cost_net.
Uruchomienie: python -m app.costs.profit_by_group
"""
from collections import defaultdict
from sqlalchemy import text
from app.db import get_engine
from app.costs.assign_costs import classify

# grupy, ktorych koszt pochodzi ze sredniej z faktur AliExpress
ALI = {"projektor", "booster", "x11", "m3", "v7", "v11", "bat_x11", "bat_v7",
       "bat_v11", "s7_pro", "carplay", "mata"}

SQL = """
WITH it AS (
    SELECT oi.order_id, lower(trim(oi.name)) AS k, oi.quantity AS q,
           oi.quantity * oi.unit_price AS val,
           sum(oi.quantity * oi.unit_price) OVER (PARTITION BY oi.order_id) AS order_val
    FROM order_item oi
)
SELECT it.k, v.channel_id, it.q,
       (v.revenue_net - v.fees_net) * it.val / NULLIF(it.order_val, 0) AS rev_minus_fees,
       v.revenue_net * it.val / NULLIF(it.order_val, 0)                 AS rev,
       it.q * pc.unit_cost_net                                         AS cogs
FROM it
JOIN v_order_profit v ON v.order_id = it.order_id
LEFT JOIN product_cost pc ON pc.product_key = it.k
"""


def run():
    g = defaultdict(lambda: [0, 0.0, 0.0])          # szt, przychod, zysk
    with get_engine().connect() as c:
        for k, ch, q, rmf, rev, cogs in c.execute(text(SQL)):
            grp = classify(k) or "BRAK"
            row = g[grp]
            row[0] += q
            row[1] += float(rev or 0)
            row[2] += float(rmf or 0) - float(cogs or 0)
    tot = {"ali": [0, 0.0, 0.0], "inne": [0, 0.0, 0.0]}
    print(f"{'grupa':16}{'zrodlo':>7}{'szt':>6}{'przychod':>11}{'zysk':>10}{'marza':>8}")
    for grp, (q, rev, prof) in sorted(g.items(), key=lambda x: -x[1][2]):
        src = "ali" if grp in ALI else "inne"
        for i, v in enumerate((q, rev, prof)):
            tot[src][i] += v
        m = 100 * prof / rev if rev else 0
        print(f"{grp:16}{src:>7}{q:>6}{rev:>11.0f}{prof:>10.0f}{m:>7.1f}%")
    print("-" * 58)
    for src, (q, rev, prof) in tot.items():
        print(f"{'RAZEM ' + src:16}{'':>7}{q:>6}{rev:>11.0f}{prof:>10.0f}{100 * prof / rev:>7.1f}%")


if __name__ == "__main__":
    run()
