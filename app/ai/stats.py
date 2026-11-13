"""Statystyki tresci AI z tabeli ai_content per typ i wersja promptu.

Uzycie: python -m app.ai.stats --channel 1 [--type title|description]
"""
import argparse

import pandas as pd
from sqlalchemy import text

from app.ai.titles import invented_tokens
from app.db import get_engine

QUERY = """
    SELECT content_type                                   AS typ,
           prompt_version                                 AS prompt,
           COUNT(*)                                       AS n,
           ROUND(AVG(char_count), 1)                      AS sr_znakow,
           MIN(char_count)                                AS min_zn,
           MAX(char_count)                                AS max_zn,
           ROUND(100.0 * AVG((status = 'ok')::int), 1)    AS proc_ok,
           SUM((status = 'suspect')::int)                 AS suspect,
           SUM((status IN ('too_long', 'bad_length'))::int) AS zla_dlugosc,
           ROUND(AVG(attempts), 2)                        AS sr_prob,
           SUM(tokens_in)                                 AS tok_in,
           SUM(tokens_out)                                AS tok_out
    FROM ai_content
    WHERE channel_id = :ch
      AND (CAST(:typ AS text) IS NULL OR content_type = :typ)
    GROUP BY content_type, prompt_version
    ORDER BY content_type, prompt_version
"""


def recheck(conn, channel_id, content_type):
    """Ta sama kontrola wymyslonych oznaczen dla wszystkich wersji promptu,
    zeby porownanie bylo uczciwe (v1/v2 nie mialy jej w trakcie generowania)."""
    rows = conn.execute(text("""
        SELECT prompt_version, original_text, generated_text
        FROM ai_content
        WHERE channel_id = :ch AND content_type = :typ
    """), {"ch": channel_id, "typ": content_type}).all()
    df = pd.DataFrame(rows, columns=["prompt", "orig", "gen"])
    df["wymyslone"] = [invented_tokens(o or "", g or "")
                       for o, g in zip(df["orig"], df["gen"])]
    df["podejrzany"] = df["wymyslone"].str.len() > 0
    print(f"\nKontrola po fakcie ({content_type}):")
    print(df.groupby("prompt")["podejrzany"]
            .agg(n="size", podejrzane="sum").to_string())
    for _, r in df[df["podejrzany"]].iterrows():
        print(f"  [{r['prompt']}] {r['gen']}  ->  {', '.join(r['wymyslone'])}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", type=int, default=1)
    ap.add_argument("--type", choices=["title", "description"])
    ap.add_argument("--recheck", action="store_true",
                    help="kontrola wymyslonych oznaczen po fakcie")
    args = ap.parse_args()

    with get_engine().connect() as conn:
        df = pd.read_sql(text(QUERY), conn,
                         params={"ch": args.channel, "typ": args.type})
        pd.set_option("display.width", 200)
        print(df.to_string(index=False))
        if args.recheck:
            recheck(conn, args.channel, args.type or "title")


if __name__ == "__main__":
    main()
