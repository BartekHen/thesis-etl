import json
import argparse
from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from app.db import get_engine
from app.auth import get_access_token
from app.http import allegro_get

PAGE = 100


def fetch_entries(token, since_iso):
    offset = 0
    while True:
        data = allegro_get(
            "/billing/billing-entries", token,
            {"limit": PAGE, "offset": offset, "occurredAt.gte": since_iso},
        )
        entries = data.get("billingEntries", [])
        yield from entries
        if len(entries) < PAGE:
            break
        offset += PAGE


def upsert_fee(conn, channel_id, e):
    order_ext = (e.get("order") or {}).get("id")
    amount = (e.get("value") or {}).get("amount")
    conn.execute(text("""
        INSERT INTO fee
            (channel_id, order_id, external_id, fee_type, amount,
             booked_at, raw_payload)
        VALUES (
            :ch,
            (SELECT order_id FROM customer_order
              WHERE channel_id = :ch AND external_id = :oext),
            :ext, :typ, :amt, :at, CAST(:raw AS jsonb))
        ON CONFLICT (channel_id, external_id) DO UPDATE SET
            order_id = EXCLUDED.order_id,
            fee_type = EXCLUDED.fee_type,
            amount = EXCLUDED.amount,
            raw_payload = EXCLUDED.raw_payload
    """), {
        "ch": channel_id, "oext": order_ext, "ext": e["id"],
        "typ": (e.get("type") or {}).get("id"),
        "amt": amount, "at": e.get("occurredAt"),
        "raw": json.dumps(e),
    })


def run(channel_id, days=365):
    engine = get_engine()
    token = get_access_token(channel_id)

    with engine.begin() as c:
        last = c.execute(text("""
            SELECT max(started_at) FROM etl_run
            WHERE channel_id = :ch AND entity = 'fees' AND status = 'ok'
        """), {"ch": channel_id}).scalar()
        since = (last - timedelta(days=2)) if last else \
            datetime.now(timezone.utc) - timedelta(days=days)
        run_id = c.execute(text("""
            INSERT INTO etl_run (channel_id, entity, status)
            VALUES (:ch, 'fees', 'running') RETURNING run_id
        """), {"ch": channel_id}).scalar()

    since_iso = since.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    count = 0
    try:
        with engine.begin() as c:
            for e in fetch_entries(token, since_iso):
                upsert_fee(c, channel_id, e)
                count += 1
        status, error = "ok", None
    except Exception as ex:
        status, error = "error", str(ex)[:500]

    with engine.begin() as c:
        c.execute(text("""
            UPDATE etl_run SET finished_at = now(), rows_loaded = :n,
                   status = :s, error = :e WHERE run_id = :r
        """), {"n": count, "s": status, "e": error, "r": run_id})
    print(f"Kanal {channel_id}: {status}, wpisow: {count}", error or "")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--channel", type=int, required=True)
    p.add_argument("--days", type=int, default=365)
    a = p.parse_args()
    run(a.channel, a.days)