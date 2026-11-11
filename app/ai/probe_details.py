"""Test: jakie dane zwraca Allegro dla ofert z zamowien (bez zapisu do bazy)."""
import argparse
import json

import requests
from sqlalchemy import text

from app.auth import get_access_token
from app.db import get_engine
from app.http import API, USER_AGENT


def get_offer(token, offer_id):
    r = requests.get(
        f"{API}/sale/product-offers/{offer_id}",
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.allegro.public.v1+json",
            "Authorization": f"Bearer {token}",
        },
        timeout=30,
    )
    return r.status_code, (r.json() if r.content else {})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", type=int, default=1)
    ap.add_argument("--n", type=int, default=3)
    args = ap.parse_args()

    token = get_access_token(args.channel)
    with get_engine().connect() as conn:
        rows = conn.execute(text("""
            SELECT DISTINCT ON (oi.offer_external_id)
                   oi.offer_external_id, oi.name
            FROM order_item oi
            JOIN customer_order o ON o.order_id = oi.order_id
            WHERE o.channel_id = :ch AND oi.offer_external_id IS NOT NULL
            ORDER BY oi.offer_external_id
            LIMIT :n
        """), {"ch": args.channel, "n": args.n}).all()

    print(f"Ofert do sprawdzenia: {len(rows)}")
    for offer_id, name in rows:
        status, data = get_offer(token, offer_id)
        print(f"\n=== {offer_id} | HTTP {status} | {name}")
        if status != 200:
            print(json.dumps(data, ensure_ascii=False)[:300])
            continue
        print("klucze:", list(data.keys()))
        print("kategoria:", (data.get("category") or {}).get("id"))
        params = data.get("parameters") or []
        print(f"parametry ({len(params)}):")
        for p in params[:12]:
            vals = p.get("values") or p.get("valuesLabels") or []
            print(f"  - {p.get('name')}: {vals}")
        pp = (data.get("productSet") or [{}])[0].get("product") or {}
        print("parametry produktu:", len(pp.get("parameters") or []))
        desc = json.dumps(data.get("description") or {}, ensure_ascii=False)
        print("opis (poczatek):", desc[:200])


if __name__ == "__main__":
    main()
