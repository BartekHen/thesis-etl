"""Jednorazowa migracja: tworzy data/produkty.csv z dotychczasowych regul
(zapisanych wczesniej w kodzie assign_costs.py) i kwot z data/koszty.csv.

Uruchomienie:  python -m app.costs.migrate_rules
Opcje:         --costs data/koszty.csv  --out data/produkty.csv  --example
(--example zapisuje wzorzec bez kwot, tak powstal app/costs/produkty.example.csv)
Po sprawdzeniu wynikow plik data/koszty.csv nie jest juz potrzebny.
"""
import argparse
import csv
import re
from pathlib import Path

BREAK_EVEN = {"papier_af", "kabel"}
INVOICE_GROUPS = {"projektor", "booster", "x11", "m3", "v7", "v11", "bat_x11",
                  "bat_v7", "bat_v11", "s7_pro", "carplay", "mata"}
PL_INVOICE_GROUPS = {"hy300", "philips", "frytkownica", "frytkownica_hd9270",
                     "basen_305", "basen_366", "tunel"}
ESTIMATE_GROUPS = {"parkside"}

# produkty bez kodu modelu w nazwie, przypisane recznie (cala nazwa oferty)
SPECIAL = {
    "odkurzacz bezprzewodowy pionowy mocny obrotowy filtr hepa x3 akcesoria": "obrotowy_hepa",
    "mocny odkurzacz pionowy ręczny akumulatorowy bezprzewodowy hepa akcesoria": "reczny_hepa",
    "odkurzacz bezprzewodowy pionowy mocny 500w filtr hepa mocne ssanie laresar": "v7",
    "odkurzacz bezprzewodowy pionowy mocny 550w filtr hepa mocne ssanie laresar": "x11",
}

# (grupa, wzorzec) w kolejnosci sprawdzania - jak dawny classify()
ORDERED = [
    ("bat_x11", r"^(wydajna )?bateria & \bx11\b"),
    ("bat_v7", r"^(wydajna )?bateria & \bv7\b"),
    ("bat_v11", r"^(wydajna )?bateria & \bv11\b"),
    ("-", r"^(wydajna )?bateria"),            # bateria bez znanego modelu: bez grupy
    ("szczypce", "szczypce"),
    ("papier_af", "papier & fryer|frytkownic"),
    ("silikon_af", "silikon & fryer|frytkownic"),
    ("finish_2x100", "finish & 2x100"),
    ("finish_100", "finish"),
    ("wozek", "wózek|wozek"),
    ("allpowers", "allpowers"),
    ("kabel", "kabel & usb-c"),
    ("praska", "praska"),
    ("mata", "mata masująca|mata masujaca"),
    ("booster", "booster"),
    ("hy300", "hy300"),
    ("projektor", "projektor"),
    ("parkside", "parkside|paghs"),
    ("karcher", "karcher"),
    ("frytkownica_hd9270", "hd9270"),
    ("frytkownica", "frytkownica|airfryer"),
    ("philips", "philips"),
    ("s7_pro", r"\bs7 pro\b"),
    ("carplay", "carplay"),
    ("lezak", "leżak|lezak"),
    ("tunel", "tunel foliowy|szklarnia"),
    ("basen_366", "basen & 366"),
    ("basen_305", "basen & 305"),
    ("fotel", "fotel & kokon|wisz"),
    ("m3", r"\bm3\b"),
    ("x11", r"\bx11\b"),
    ("v11", r"\bv11\b"),
    ("v7", r"\bv7\b"),
]


def source(group):
    if group in INVOICE_GROUPS:
        return "faktury_aliexpress"
    if group in PL_INVOICE_GROUPS:
        return "faktury_pl"
    if group in ESTIMATE_GROUPS:
        return "szacunek_z_faktur"
    if group in BREAK_EVEN:
        return "break_even"
    return "deklaracja"


def exact(key):
    assert "&" not in key
    return "^" + re.sub(r"([.^$*+?{}\[\]\\|()])", r"\\\1", key) + "$"


def build_rules():
    rules = [(g, exact(k)) for k, g in SPECIAL.items()] + ORDERED
    return [(g, w, i * 10) for i, (g, w) in enumerate(rules, start=1)]


def run(costs_path, out_path, example):
    costs = {}
    if not example:
        with open(costs_path, encoding="utf-8-sig", newline="") as f:
            costs = {r["grupa"]: r["koszt_netto"].strip()
                     for r in csv.DictReader(f, delimiter=";")}
    rules = build_rules()
    groups = {g for g, _, _ in rules if g != "-"}
    seen, rows = set(), []
    for g, w, p in sorted(rules, key=lambda r: (r[0] == "-", r[0], r[1].startswith("^") and r[1].endswith("$"), r[2])):
        first = g not in seen and g != "-"
        seen.add(g)
        src = source(g) if first else ""
        if first and g in BREAK_EVEN:
            cost = ""
        elif first:
            cost = "0.00" if example else costs.get(g, "")
        else:
            cost = ""
        rows.append([g, w, "", p, src, cost])
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        if example:
            f.write("# Wzorzec pliku regul produktow (kolumny i skladnia: app/costs/rules.py)\n")
            f.write("# Skopiuj do data/produkty.csv i wpisz kwoty w kolumnie koszt_netto.\n")
        w = csv.writer(f, delimiter=";", lineterminator="\n")
        w.writerow(["grupa", "wzorzec", "wyklucz", "priorytet",
                    "zrodlo_kosztu", "koszt_netto"])
        w.writerows(rows)
    if not example:
        no_cost = sorted(g for g in groups
                         if g not in BREAK_EVEN and not costs.get(g))
        unused = sorted(set(costs) - groups)
        print(f"Zapisano {len(rows)} regul do {out_path}")
        if no_cost:
            print("UWAGA - brak kosztu w koszty.csv dla grup:", ", ".join(no_cost))
        if unused:
            print("Grupy z koszty.csv bez reguly (pominiete):", ", ".join(unused))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--costs", default="data/koszty.csv")
    ap.add_argument("--out", default="data/produkty.csv")
    ap.add_argument("--example", action="store_true")
    a = ap.parse_args()
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    run(a.costs, a.out, a.example)
