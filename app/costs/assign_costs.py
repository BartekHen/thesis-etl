import re
from sqlalchemy import text
from app.db import get_engine

# koszt zakupu 1 szt., netto, zl
# projektor, booster, x11, m3, v7, v11, baterie, s7_pro, carplay, mata: srednia wazona z faktur AliExpress
# (12.2025-01.2026, 06.2026; po kuponach, z wysylka) - faktury/srednie_koszty_aliexpress.csv
COSTS = {
    "projektor": 217, "booster": 181, "x11": 303, "m3": 444,
    "v7": 246, "v11": 351, "bat_x11": 124, "bat_v7": 142,
    "bat_v11": 125, "parkside": 210, "karcher": 330, "philips": 80,
    "obrotowy_hepa": 370, "reczny_hepa": 300,
    # produkty z Empiku (13.11)
    "s7_pro": 595, "carplay": 128, "fotel": 515,
    "lezak": 200, "tunel": 159, "basen_305": 400, "basen_366": 700,
    "hy300": 180, "frytkownica": 400,
    # produkty z konta 2 Allegro
    "silikon_af": 11, "szczypce": 8, "finish_100": 45, "finish_2x100": 90,
    "wozek": 104, "allpowers": 590, "praska": 9, "mata": 205,
}

# grupy bez znanego kosztu: koszt = srednia cena sprzedazy netto (zysk na towarze 0)
BREAK_EVEN = {"papier_af", "kabel"}

# produkty bez kodu modelu w nazwie, przypisane recznie
SPECIAL = {
    "odkurzacz bezprzewodowy pionowy mocny obrotowy filtr hepa x3 akcesoria": "obrotowy_hepa",
    "mocny odkurzacz pionowy ręczny akumulatorowy bezprzewodowy hepa akcesoria": "reczny_hepa",
    "odkurzacz bezprzewodowy pionowy mocny 500w filtr hepa mocne ssanie laresar": "v7",
    "odkurzacz bezprzewodowy pionowy mocny 550w filtr hepa mocne ssanie laresar": "x11",
}


def classify(key):
    if key in SPECIAL:
        return SPECIAL[key]
    if key.startswith("bateria") or key.startswith("wydajna bateria"):
        for m in ("x11", "v7", "v11"):
            if re.search(rf"\b{m}\b", key):
                return f"bat_{m}"
        return None
    # akcesoria do air fryera - PRZED "frytkownica" i "philips"
    if "szczypce" in key:
        return "szczypce"
    if "papier" in key and ("fryer" in key or "frytkownic" in key):
        return "papier_af"
    if "silikon" in key and ("fryer" in key or "frytkownic" in key):
        return "silikon_af"
    if "finish" in key:
        return "finish_2x100" if "2x100" in key else "finish_100"
    if "wózek" in key or "wozek" in key:
        return "wozek"
    if "allpowers" in key:
        return "allpowers"
    if "kabel" in key and "usb-c" in key:
        return "kabel"
    if "praska" in key:
        return "praska"
    if "mata masująca" in key or "mata masujaca" in key:
        return "mata"
    if "booster" in key:
        return "booster"
    if "hy300" in key:                        # przed "projektor" (inny koszt niz L018)
        return "hy300"
    if "projektor" in key:
        return "projektor"
    if "parkside" in key or "paghs" in key:   # B2 i C3; 210 = zestaw (pila ~145 + akumulator, ladowarka)
        return "parkside"
    if "karcher" in key:
        return "karcher"
    if "frytkownica" in key or "airfryer" in key:   # przed "philips" (golarka)
        return "frytkownica"
    if "philips" in key:
        return "philips"
    # po MODELU, nie po marce (laresar = marka wszystkich odkurzaczy)
    if re.search(r"\bs7 pro\b", key):
        return "s7_pro"
    if "carplay" in key:
        return "carplay"
    if "leżak" in key or "lezak" in key:
        return "lezak"
    if "tunel foliowy" in key or "szklarnia" in key:
        return "tunel"
    if "basen" in key and "366" in key:
        return "basen_366"
    if "basen" in key and "305" in key:
        return "basen_305"
    if "fotel" in key and ("kokon" in key or "wisz" in key):
        return "fotel"
    for m in ("m3", "x11", "v11", "v7"):
        if re.search(rf"\b{m}\b", key):
            return m
    return None


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
            cost = break_even_cost(c, k) if g in BREAK_EVEN else COSTS[g]
            c.execute(text("""
                INSERT INTO product_cost (product_key, unit_cost_net)
                VALUES (:k, :u)
                ON CONFLICT (product_key) DO UPDATE
                SET unit_cost_net = EXCLUDED.unit_cost_net
            """), {"k": k, "u": cost})
            ok += 1
    print("Przypisano kosztow:", ok)
    print("Bez kosztu:", len(skipped))
    for k in skipped:
        print("  -", k)


if __name__ == "__main__":
    run()