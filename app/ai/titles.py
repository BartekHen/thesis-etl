import argparse
import os
import re
import time

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types
from sqlalchemy import text

from app.db import get_engine

load_dotenv()

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
MAX_LEN = 75
MAX_ATTEMPTS = 3
PAUSE = 7  # sekundy miedzy zapytaniami (limit darmowej warstwy)

PROMPTS = {
    "title_v1": (
        "Jesteś copywriterem ofert na Allegro. Skracasz i poprawiasz tytuły "
        "ofert po polsku. Tytuł ma mieć NAJWYŻEJ 75 znaków, zawierać markę, "
        "model i najważniejsze cechy produktu. Nie wymyślaj parametrów, "
        "których nie ma w oryginale. Nie używaj emoji ani wielkich liter "
        "w całych słowach. Odpowiedz wyłącznie tytułem, bez cudzysłowów."
    ),
    "title_v2": (
        "Jesteś specjalistą SEO ofert na Allegro. Optymalizujesz tytuły "
        "pod wyszukiwarkę Allegro, po polsku. Tytuł ma mieć od 65 do 75 "
        "znaków (NIGDY więcej niż 75). Wykorzystaj dostępne miejsce: "
        "zachowaj markę, model, parametry techniczne i frazy, po których "
        "kupujący szukają produktu (np. rodzaj produktu, zastosowanie). "
        "Nie wymyślaj parametrów, których nie ma w oryginale. Nie używaj "
        "emoji ani wielkich liter w całych słowach. Odpowiedz wyłącznie "
        "tytułem, bez cudzysłowów."
    ),
    "title_v3": (
        "Jesteś specjalistą SEO ofert na Allegro. Optymalizujesz tytuły "
        "pod wyszukiwarkę Allegro, po polsku. Tytuł ma mieć od 65 do 75 "
        "znaków (NIGDY więcej niż 75). Zachowaj markę, model, parametry "
        "techniczne i frazy, po których kupujący szukają produktu. "
        "ZASADY: (1) Oznaczenia modeli i liczby przepisuj dokładnie z "
        "oryginału (np. L018, 2500mAh, 12V), niczego nie zmieniaj i nie "
        "dodawaj. (2) Nie dodawaj informacji, których nie ma w oryginale. "
        "(3) Pisz jak w zdaniu: pierwsza litera wielka, nazwy własne i "
        "oznaczenia modeli wielkimi literami, reszta małymi. "
        "(4) Bez emoji. Odpowiedz wyłącznie tytułem, bez cudzysłowów."
    ),
}


def get_client():
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise SystemExit("Brak GEMINI_API_KEY w .env")
    return genai.Client(
        api_key=key,
        http_options=types.HttpOptions(
            timeout=120_000,
            retry_options=types.HttpRetryOptions(attempts=1)))


def call_model(client, prompt, system):
    """Wywoluje model; przy 429/500/503/504 czeka i ponawia (10, 20, 40, 80 s)."""
    for wait in (10, 20, 40, 80, None):
        try:
            return client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system, temperature=0.4),
            )
        except (errors.ServerError, errors.ClientError) as e:
            code = getattr(e, "code", None)
            if code not in (429, 500, 503, 504) or wait is None:
                raise
            print(f"  blad {code}, ponawiam za {wait} s...", flush=True)
            time.sleep(wait)


def invented_tokens(original, generated):
    """Tokeny z cyframi (kody modeli, parametry) z wyniku, ktorych nie ma w oryginale."""
    norm = re.sub(r"\s+", "", original.lower())
    bad = []
    for tok in generated.lower().split():
        tok = tok.strip(".,;:()+-\"'")
        if len(tok) >= 3 and any(c.isdigit() for c in tok):
            if tok not in norm:
                bad.append(tok)
    return bad


def generate_title(client, original, system):
    """Zwraca (tytul, proby, tok_in, tok_out, wymyslone_tokeny)."""
    prompt = f"Oryginalny tytul: {original}\nNowy tytul (max {MAX_LEN} znakow):"
    tokens_in = tokens_out = 0
    title, bad = "", []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"  zapytanie do {MODEL} (proba {attempt})...", flush=True)
        resp = call_model(client, prompt, system)
        title = (resp.text or "").strip().strip('"')
        if title:
            title = title[0].upper() + title[1:]
        usage = resp.usage_metadata
        tokens_in += (usage.prompt_token_count or 0) if usage else 0
        tokens_out += (usage.candidates_token_count or 0) if usage else 0
        bad = invented_tokens(original, title)
        if 0 < len(title) <= MAX_LEN and not bad:
            return title, attempt, tokens_in, tokens_out, bad
        problems = []
        if len(title) > MAX_LEN:
            problems.append(f"ma {len(title)} znakow, max {MAX_LEN}")
        if bad:
            problems.append("zawiera oznaczenia, ktorych nie ma w oryginale: "
                            + ", ".join(bad))
        prompt = (
            f"Oryginalny tytul: {original}\n"
            f"Twoja poprzednia propozycja: {title}\n"
            f"Blad: {'; '.join(problems)}. Popraw. Sam tytul:"
        )
        time.sleep(PAUSE)
    return title, MAX_ATTEMPTS, tokens_in, tokens_out, bad


def pending_titles(conn, channel_id, limit, version):
    return conn.execute(text("""
        SELECT DISTINCT oi.name
        FROM order_item oi
        JOIN customer_order o ON o.order_id = oi.order_id
        WHERE o.channel_id = :ch AND oi.name IS NOT NULL
          AND oi.name NOT IN (
              SELECT original_text FROM ai_content
              WHERE channel_id = :ch AND content_type = 'title'
                AND prompt_version = :pv)
        ORDER BY oi.name
        LIMIT :lim
    """), {"ch": channel_id, "pv": version, "lim": limit}).scalars().all()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", type=int, default=1)
    ap.add_argument("--limit", type=int, default=3)
    ap.add_argument("--prompt", choices=list(PROMPTS), default="title_v3")
    args = ap.parse_args()

    client = get_client()
    engine = get_engine()
    with engine.begin() as conn:
        names = pending_titles(conn, args.channel, args.limit, args.prompt)
        print(f"Do przetworzenia: {len(names)}")
        for name in names:
            title, attempts, t_in, t_out, bad = generate_title(
                client, name, PROMPTS[args.prompt])
            status = ("too_long" if len(title) > MAX_LEN
                      else "suspect" if bad else "ok")
            conn.execute(text("""
                INSERT INTO ai_content
                    (channel_id, content_type, original_text, generated_text,
                     char_count, attempts, model, prompt_version, status,
                     tokens_in, tokens_out)
                VALUES (:ch, 'title', :orig, :gen, :cc, :att, :model, :pv,
                        :st, :ti, :to)
            """), {"ch": args.channel, "orig": name, "gen": title,
                   "cc": len(title), "att": attempts, "model": MODEL,
                   "pv": args.prompt,
                   "st": status,
                   "ti": t_in, "to": t_out})
            print(f"[{len(title)} zn, proby {attempts}, {status}] {name}\n   -> {title}")
            time.sleep(PAUSE)


if __name__ == "__main__":
    main()
