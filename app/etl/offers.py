import argparse
import json
from sqlalchemy import text
from app.db import get_engine
from app.auth import get_access_token
from app.http import allegro_get

PAGE = 100


def fetch_offers(token):
    offset = 0
    while True:
        data = allegro_get("/sale/offers", token,
                           {"limit": PAGE, "offset": offset})
        offers = data.get("offers", [])
        yield from offers
        if len(offers) < PAGE:
            break
        offset += PAGE


def upsert_offer(conn, channel_id, o):
    price = (o.get("sellingMode") or {}).get("price") or {}
    conn.execute(text("""
        INSERT INTO offer
            (channel_id, external_id, title, price, currency, status,
             updated_at, raw_payload)
        VALUES (:ch, :ext, :t, :p, :cur, :st, :upd, CAST(:raw AS jsonb))
        ON CONFLICT (channel_id, external_id) DO UPDATE SET
            title = EXCLUDED.title,
            price = EXCLUDED.price,
            currency = EXCLUDED.currency,
            status = EXCLUDED.status,
            updated_at = EXCLUDED.updated_at,
            raw_payload = EXCLUDED.raw_payload
    """), {
        "ch": channel_id,
        "ext": o["id"],
        "t": o.get("name"),
        "p": price.get("amount"),
        "cur": price.get("currency", "PLN"),
        "st": (o.get("publication") or {}).get("status"),
        "upd": o.get("updatedAt"),
        "raw": json.dumps(o),
    })


def run(channel_id):
    engine = get_engine()
    token = get_access_token(channel_id)

    with engine.begin() as c:
        run_id = c.execute(text("""
            INSERT INTO etl_run (channel_id, entity, status)
            VALUES (:ch, 'offers', 'running') RETURNING run_id
        """), {"ch": channel_id}).scalar()

    count = 0
    try:
        with engine.begin() as c:
            for o in fetch_offers(token):
                upsert_offer(c, channel_id, o)
                count += 1
            # powiazanie pozycji zamowien z ofertami
            c.execute(text("""
                UPDATE order_item oi
                SET offer_id = ofr.offer_id
                FROM customer_order co, offer ofr
                WHERE oi.order_id = co.order_id
                  AND co.channel_id = ofr.channel_id
                  AND oi.offer_external_id = ofr.external_id
                  AND oi.offer_id IS NULL
            """))
        status, error = "ok", None
    except Exception as e:
        status, error = "error", str(e)[:500]

    with engine.begin() as c:
        c.execute(text("""
            UPDATE etl_run SET finished_at = now(), rows_loaded = :n,
                   status = :s, error = :e WHERE run_id = :r
        """), {"n": count, "s": status, "e": error, "r": run_id})
    print(f"Kanal {channel_id}: {status}, ofert: {count}", error or "")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--channel", type=int, required=True)
    run(p.parse_args().channel)