import re
from sqlalchemy import text
from app.db import get_engine

# koszt zakupu 1 szt., netto, zl
COSTS = {
    "projektor": 230, "booster": 180, "x11": 300, "m3": 500,
    "v7": 290, "v11": 599, "bat_x11": 137, "bat_v7": 130,
    "bat_v11": 137, "parkside": 150, "karcher": 330, "philips": 80,
    "obrotowy_hepa": 370, "reczny_hepa": 300,
}

# produkty bez kodu modelu w nazwie, przypisane recznie
SPECIAL = {
    "odkurzacz bezprzewodowy pionowy mocny obrotowy filtr hepa x3 akcesoria": "obrotowy_hepa",
    "mocny odkurzacz pionowy ręczny akumulatorowy bezprzewodowy hepa akcesoria": "reczny_hepa",
}


def classify(key):
    if key in SPECIAL:
        return SPECIAL[key]
    if key.startswith("bateria") or key.startswith("wydajna bateria"):
        for m in ("x11", "v7", "v11"):
            if re.search(rf"\b{m}\b", key):
                return f"bat_{m}"
        return None
    if "booster" in key:
        return "booster"
    if "projektor" in key:
        return "projektor"
    if "parkside" in key or "paghs" in key:
        return "parkside"
    if "karcher" in key:
        return "karcher"
    if "philips" in key:
        return "philips"
    for m in ("m3", "x11", "v11", "v7"):
        if re.search(rf"\b{m}\b", key):
            return m
    return None


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
            c.execute(text("""
                INSERT INTO product_cost (product_key, unit_cost_net)
                VALUES (:k, :u)
                ON CONFLICT (product_key) DO UPDATE
                SET unit_cost_net = EXCLUDED.unit_cost_net
            """), {"k": k, "u": COSTS[g]})
            ok += 1
    print("Przypisano kosztow:", ok)
    print("Bez kosztu:", len(skipped))
    for k in skipped:
        print("  -", k)


if __name__ == "__main__":
    run()