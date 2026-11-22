"""Reguly przypisania produktow do grup i kosztow zakupu - wczytywane z pliku CSV.

Plik (domyslnie data/produkty.csv, poza repozytorium) zastepuje reguly, ktore
wczesniej byly zapisane w kodzie. Dodanie produktu = dodanie wiersza w pliku.
Wzor formatu: app/costs/produkty.example.csv.

Kolumny (separator ;, kodowanie UTF-8):
  grupa          nazwa grupy produktow; "-" oznacza: nazwy pasujace do reguly
                 zostaja bez grupy i nie sa dalej sprawdzane
  wzorzec        warunki dopasowania do nazwy oferty (wielkosc liter bez znaczenia):
                 czesci rozdzielone znakiem & musza pasowac wszystkie (AND),
                 kazda czesc to wyrazenie regularne, w ktorym | oznacza LUB
                 np. "papier & fryer|frytkownic"
  wyklucz        (opcjonalnie) wyrazenie regularne; jesli pasuje, regula jest pomijana
  priorytet      liczba; reguly sa sprawdzane od najmniejszej, wygrywa pierwsza pasujaca
  zrodlo_kosztu  faktury_aliexpress | faktury_pl | szacunek_z_faktur | deklaracja | break_even
  koszt_netto    koszt zakupu 1 szt. netto, zl (dla break_even puste); wystarczy
                 wpisac w jednym wierszu grupy
Wiersze zaczynajace sie od # sa pomijane.
"""
import csv
import os
import re
from functools import lru_cache
from pathlib import Path

PRODUCTS_FILE = Path(os.getenv("PRODUCTS_FILE", "data/produkty.csv"))

SOURCES = {"faktury_aliexpress", "faktury_pl", "szacunek_z_faktur",
           "deklaracja", "break_even"}
NO_GROUP = "-"
AND = "&"


class _Rule:
    __slots__ = ("group", "parts", "exclude", "priority", "line")

    def __init__(self, group, parts, exclude, priority, line):
        self.group, self.parts = group, parts
        self.exclude, self.priority, self.line = exclude, priority, line

    def matches(self, key):
        if self.exclude is not None and self.exclude.search(key):
            return False
        return all(p.search(key) for p in self.parts)


def _regex(expr, line, what):
    try:
        return re.compile(expr, re.IGNORECASE)
    except re.error as e:
        raise ValueError(f"{PRODUCTS_FILE}, wiersz {line}: bledny {what} "
                         f"'{expr}' ({e})") from None


def _number(text, line, what):
    try:
        return float(text.replace(",", "."))
    except ValueError:
        raise ValueError(f"{PRODUCTS_FILE}, wiersz {line}: {what} "
                         f"'{text}' nie jest liczba") from None


@lru_cache(maxsize=None)
def _load(path):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Brak pliku regul produktow: {path}. Skopiuj "
            f"app/costs/produkty.example.csv do {path} i uzupelnij kolumne "
            f"koszt_netto (albo wygeneruj plik: python -m app.costs.migrate_rules).")
    rules, costs, sources = [], {}, {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        lines = (ln for ln in f if not ln.lstrip().startswith("#"))
        reader = csv.DictReader(lines, delimiter=";")
        missing = {"grupa", "wzorzec", "priorytet", "zrodlo_kosztu",
                   "koszt_netto"} - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path}: brak kolumn {sorted(missing)}")
        for n, r in enumerate(reader, start=2):
            group = (r["grupa"] or "").strip()
            pattern = (r["wzorzec"] or "").strip()
            if not group and not pattern:
                continue
            if not group or not pattern:
                raise ValueError(f"{path}, wiersz {n}: wymagane grupa i wzorzec")
            parts = [_regex(p.strip(), n, "wzorzec")
                     for p in pattern.split(AND) if p.strip()]
            excl = (r.get("wyklucz") or "").strip()
            prio = _number(r["priorytet"], n, "priorytet")
            rules.append(_Rule(group, parts,
                               _regex(excl, n, "wyklucz") if excl else None,
                               prio, n))
            if group == NO_GROUP:
                continue
            src = (r["zrodlo_kosztu"] or "").strip()
            cost = (r["koszt_netto"] or "").strip()
            if src:
                if src not in SOURCES:
                    raise ValueError(f"{path}, wiersz {n}: nieznane zrodlo kosztu "
                                     f"'{src}' (dozwolone: {sorted(SOURCES)})")
                if sources.setdefault(group, src) != src:
                    raise ValueError(f"{path}, wiersz {n}: grupa {group} ma rozne "
                                     f"zrodla kosztu w kilku wierszach")
            if cost:
                c = _number(cost, n, "koszt_netto")
                if costs.setdefault(group, c) != c:
                    raise ValueError(f"{path}, wiersz {n}: grupa {group} ma rozne "
                                     f"koszty w kilku wierszach")
    rules.sort(key=lambda x: x.priority)      # sort stabilny: remis = kolejnosc w pliku
    return rules, costs, sources


def classify(key):
    """Grupa produktu dla znormalizowanej nazwy (lower + trim) albo None."""
    for rule in _load(PRODUCTS_FILE)[0]:
        if rule.matches(key):
            return None if rule.group == NO_GROUP else rule.group
    return None


def cost_source(group):
    return _load(PRODUCTS_FILE)[2].get(group, "deklaracja")


def is_break_even(group):
    return cost_source(group) == "break_even"


def unit_cost(group):
    """Koszt zakupu 1 szt. netto dla grupy (blad, jesli nie podano w pliku)."""
    costs = _load(PRODUCTS_FILE)[1]
    if group not in costs:
        raise ValueError(f"Brak kosztu netto dla grupy '{group}' w {PRODUCTS_FILE}")
    return costs[group]
