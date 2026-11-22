"""Przypisanie kosztow zakupu do produktow z zamowien (tabela product_cost).

Grupy produktow, zrodla i koszty sa wczytywane z pliku data/produkty.csv
(app/costs/rules.py). Uruchomienie: python -m app.costs.assign_costs
"""
from sqlalchemy import text
from app.db import get_engine
from app.costs.rules import classify, cost_source, is_break_even, unit_cost  # noqa: F401


def break_even_cost(c, key):
    # srednia cena sprzedazy netto za sztuke (brutto / 1.23)
    return c.execute(text("""
        SELECT round(sum(quantity * unit_price) / sum(quantity) / 1.23, 2)
        FROM order_item WHERE lower(trim(name)) = :k
    """), {"k": key}).scalar()


def run():
    ok, skipped = 0, []
    with get_engine().begin() as c:
        keys = [r[0] for r in c.execute(text(
            "SELECT DISTINCT lower(trim(name)) FROM order_item "
            "WHERE name IS NOT NULL"))]
        for k in keys:
            g = classify(k)
            if g is None:
                skipped.append(k)
                continue
            cost = break_even_cost(c, k) if is_break_even(g) else unit_cost(g)
            c.execute(text("""
                INSERT INTO product_cost (product_key, unit_cost_net, product_group, cost_source)
                VALUES (:k, :u, :g, :s)
                ON CONFLICT (product_key) DO UPDATE
                SET unit_cost_net = EXCLUDED.unit_cost_net,
                    product_group = EXCLUDED.product_group,
                    cost_source   = EXCLUDED.cost_source
            """), {"k": k, "u": cost, "g": g, "s": cost_source(g)})
            ok += 1
    print("Przypisano kosztow:", ok)
    print("Bez kosztu:", len(skipped))
    for k in skipped:
        print("  -", k)


if __name__ == "__main__":
    run()