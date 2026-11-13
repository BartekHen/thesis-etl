import argparse
import csv
import time
from pathlib import Path

from sqlalchemy import text

from app.ai.titles import (MAX_ATTEMPTS, MODEL, PAUSE, call_model,
                           get_client, invented_tokens)
from app.costs.assign_costs import classify
from app.db import get_engine

# limity dlugosci per wersja promptu (min, max)
LIMITS = {"desc_v1": (600, 1200), "desc_v2": (400, 1200)}
SPECS_FILE = Path(__file__).with_name("product_specs.csv")

PROMPTS = {
    "desc_v1": (
        "Jesteś copywriterem sklepu na Allegro. Piszesz opis produktu po "
        "polsku na podstawie NAZWY i SPECYFIKACJI. Struktura: 1-2 zdania "
        "wstępu o korzyści dla kupującego, potem lista 4-6 najważniejszych "
        "cech (każda w osobnej linii zaczynającej się od '- '), na końcu "
        "1 zdanie o zawartości zestawu lub zastosowaniu. Długość: 600-1200 "
        "znaków. ZASADY: (1) Używaj WYŁĄCZNIE faktów z nazwy i specyfikacji, "
        "liczby i oznaczenia modeli przepisuj dokładnie. (2) Nie dodawaj "
        "parametrów, certyfikatów, gwarancji ani informacji o wysyłce. "
        "(3) Bez emoji i bez nagłówków markdown. Odpowiedz samym opisem."
    ),
    "desc_v2": (
        "Jesteś copywriterem sklepu na Allegro. Piszesz opis produktu po "
        "polsku na podstawie NAZWY i SPECYFIKACJI. Struktura: 1-2 zdania "
        "wstępu o zastosowaniu produktu (bez pytań retorycznych), potem lista "
        "cech (każda w osobnej linii zaczynającej się od '- ' i wielkiej "
        "litery, jedna cecha = jeden fakt ze specyfikacji), na końcu 1 zdanie "
        "o zawartości zestawu lub zastosowaniu. Długość: 400-1200 znaków; "
        "jeśli faktów jest mało, opis ma być krótszy, bez ogólników. "
        "ZASADY: (1) Używaj WYŁĄCZNIE faktów z nazwy i specyfikacji, liczby i "
        "oznaczenia modeli przepisuj dokładnie. (2) Nie dopisuj do parametrów "
        "określeń, których nie ma w specyfikacji (np. 'szczytowy', "
        "'znamionowe', 'moc ssania' przy baterii). (3) Nie obiecuj efektów "
        "ani jakości ('gwarantuje', 'niezawodny', 'bezproblemowy'), nie "
        "dodawaj certyfikatów, gwarancji ani informacji o wysyłce. "
        "(4) Bez emoji i bez nagłówków markdown. Odpowiedz samym opisem."
    ),
}


def load_specs():
    with open(SPECS_FILE, encoding="utf-8") as f:
        return {r["grupa"]: r for r in csv.DictReader(f, delimiter=";")}


def spec_text(spec):
    parts = [
        f"Produkt: {spec['produkt']}",
        f"Marka: {spec['marka']}" if spec["marka"] else "",
        f"Model: {spec['model']}" if spec["model"] else "",
        f"Cechy: {spec['cechy']}" if spec["cechy"] else "",
        f"W zestawie: {spec['zestaw']}" if spec["zestaw"] else "",
    ]
    return "\n".join(p for p in parts if p)


def check(source, desc, limits):
    min_len, max_len = limits
    problems = []
    if not min_len <= len(desc) <= max_len:
        problems.append(f"ma {len(desc)} znakow, wymagane {min_len}-{max_len}")
    bad = invented_tokens(source, desc)
    if bad:
        problems.append("zawiera oznaczenia spoza nazwy i specyfikacji: "
                        + ", ".join(bad))
    return problems, bad


def generate_description(client, name, spec, system, limits):
    source = f"Nazwa: {name}\n{spec_text(spec)}"
    prompt = f"{source}\n\nNapisz opis produktu:"
    t_in = t_out = 0
    desc, problems, bad = "", [], []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"  zapytanie do {MODEL} (proba {attempt})...", flush=True)
        resp = call_model(client, prompt, system)
        desc = (resp.text or "").strip()
        u = resp.usage_metadata
        t_in += (u.prompt_token_count or 0) if u else 0
        t_out += (u.candidates_token_count or 0) if u else 0
        problems, bad = check(source, desc, limits)
        if not problems:
            break
        print(f"    odrzucono: {'; '.join(problems)}", flush=True)
        prompt = (f"{source}\n\nTwoj poprzedni opis:\n{desc}\n\n"
                  f"Blad: {'; '.join(problems)}. Popraw i podaj sam opis:")
        time.sleep(PAUSE)
    status = ("ok" if not problems else "suspect" if bad else "bad_length")
    return desc, attempt, t_in, t_out, status


def pending(conn, channel_id, version):
    return conn.execute(text("""
        SELECT DISTINCT oi.name
        FROM order_item oi
        JOIN customer_order o ON o.order_id = oi.order_id
        WHERE o.channel_id = :ch AND oi.name IS NOT NULL
          AND oi.name NOT IN (
              SELECT original_text FROM ai_content
              WHERE channel_id = :ch AND content_type = 'description'
                AND prompt_version = :pv)
        ORDER BY oi.name
    """), {"ch": channel_id, "pv": version}).scalars().all()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", type=int, default=1)
    ap.add_argument("--limit", type=int, default=3)
    ap.add_argument("--prompt", choices=list(PROMPTS), default="desc_v1")
    args = ap.parse_args()

    specs = load_specs()
    client = get_client()
    with get_engine().begin() as conn:
        todo = []
        for name in pending(conn, args.channel, args.prompt):
            group = classify(name.lower().strip())
            if group in specs:
                todo.append((name, group))
            else:
                print(f"  pomijam (brak grupy w specyfikacji): {name}")
        todo = todo[:args.limit]
        print(f"Do przetworzenia: {len(todo)}")
        for name, group in todo:
            desc, att, t_in, t_out, status = generate_description(
                client, name, specs[group], PROMPTS[args.prompt],
                LIMITS[args.prompt])
            conn.execute(text("""
                INSERT INTO ai_content
                    (channel_id, content_type, original_text, generated_text,
                     char_count, attempts, model, prompt_version, status,
                     tokens_in, tokens_out)
                VALUES (:ch, 'description', :orig, :gen, :cc, :att, :model,
                        :pv, :st, :ti, :to)
            """), {"ch": args.channel, "orig": name, "gen": desc,
                   "cc": len(desc), "att": att, "model": MODEL,
                   "pv": args.prompt, "st": status, "ti": t_in, "to": t_out})
            print(f"[{group}, {len(desc)} zn, proby {att}, {status}] {name}\n"
                  f"{desc}\n")
            time.sleep(PAUSE)


if __name__ == "__main__":
    main()
