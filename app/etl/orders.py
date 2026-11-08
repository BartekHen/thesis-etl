import json
import argparse
from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from app.db import get_engine
from app.auth import get_access_token
from app.http import allegro_get

PAGE = 100


def sanitize(form):
    """Usuwa dane osobowe kupującego przed zapisem do bazy."""
    f = dict(form)
    for k in ("buyer", "invoice"):
        f.pop(k, None)
    if isinstance(f.get("delivery"), dict):
        d = dict(f["delivery"])
        for k in ("address", "pickupPoint"):
            d.pop(k, None)
        f["delivery"] = d
    return f


def fetch_forms(token, since_iso):
    offset = 0
    while True:
        data = allegro_get(
            "/order/checkout-forms", token,
            {"limit": PAGE, "offset": offset,
             "updatedAt.gte": since_iso, "sort": "updatedAt"},
        )
        forms = data.get("checkoutForms", [])
        yield from forms
        if len(forms) < PAGE:
            break
        offset += PAGE


def upsert_order(conn, channel_id, f):
    items = f.get("lineItems") or []
    summary = (f.get("summary") or {}).get("totalToPay") or {}
    ship = ((f.get("delivery") or {}).get("cost") or {})
    bought = [li.get("boughtAt") for li in items if li.get("boughtAt")]
    ordered_at = min(bought) if bought else f.get("updatedAt")

    order_id = conn.execute(text("""
        INSERT INTO customer_order
            (channel_id, external_id, ordered_at, status, total_amount,
             currency, shipping_cost, raw_payload)
        VALUES (:ch, :ext, :at, :st, :tot, :cur, :ship, CAST(:raw AS jsonb))
        ON CONFLICT (channel_id, external_id) DO UPDATE SET
            status = EXCLUDED.status,
            total_amount = EXCLUDED.total_amount,
            shipping_cost = EXCLUDED.shipping_cost,
            raw_payload = EXCLUDED.raw_payload
        RETURNING order_id
    """), {
        "ch": channel_id, "ext": f["id"], "at": ordered_at,
        "st": f.get("status"), "tot": summary.get("amount"),
        "cur": summary.get("currency", "PLN"), "ship": ship.get("amount"),
        "raw": json.dumps(sanitize(f)),
    }).scalar()

    conn.execute(text("DELETE FROM order_item WHERE order_id = :o"),
                 {"o": order_id})
    for li in items:
        conn.execute(text("""
            INSERT INTO order_item
                (order_id, offer_external_id, name, quantity, unit_price)
            VALUES (:o, :oe, :n, :q, :p)
        """), {
            "o": order_id,
            "oe": (li.get("offer") or {}).get("id"),
            "n": (li.get("offer") or {}).get("name"),
            "q": li.get("quantity", 1),
            "p": (li.get("price") or {}).get("amount"),
        })


def run(channel_id, days=365):
    engine = get_engine()
    token = get_access_token(channel_id)

    with engine.begin() as c:
        last = c.execute(text("""
            SELECT max(started_at) FROM etl_run
            WHERE channel_id = :ch AND entity = 'orders' AND status = 'ok'
        """), {"ch": channel_id}).scalar()
        since = (last - timedelta(hours=1)) if last else \
            datetime.now(timezone.utc) - timedelta(days=days)
        run_id = c.execute(text("""
            INSERT INTO etl_run (channel_id, entity, status)
            VALUES (:ch, 'orders', 'running') RETURNING run_id
        """), {"ch": channel_id}).scalar()

    since_iso = since.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    count = 0
    try:
        with engine.begin() as c:
            for form in fetch_forms(token, since_iso):
                upsert_order(c, channel_id, form)
                count += 1
        status, error = "ok", None
    except Exception as e:
        status, error = "error", str(e)[:500]

    with engine.begin() as c:
        c.execute(text("""
            UPDATE etl_run SET finished_at = now(), rows_loaded = :n,
                   status = :s, error = :e WHERE run_id = :r
        """), {"n": count, "s": status, "e": error, "r": run_id})
    print(f"Kanal {channel_id}: {status}, zamowien: {count}", error or "")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--channel", type=int, required=True)
    p.add_argument("--days", type=int, default=365)
    a = p.parse_args()
    run(a.channel, a.days)