"""ETL zamowien Empik Marketplace (platforma Mirakl, endpoint OR11 GET /api/orders).

Prowizje Empiku sa w samych zamowieniach (total_commission), wiec ten sam
skrypt zapisuje tez opłaty do tabeli fee - osobny endpoint billingu nie jest
potrzebny.

Uzycie: python -m app.etl.empik_orders --channel 2 --days 400
"""
import argparse
import json
import os
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv
from sqlalchemy import text

from app.db import get_engine

load_dotenv()

API = os.getenv("EMPIK_API_URL", "https://marketplace.empik.com")
PAGE = 100
FEE_TYPE = "EMPIK_COM"  # wlasny kod typu oplaty: prowizja Empiku


def empik_get(path, params=None):
    """GET do API Mirakl. Autoryzacja: staly klucz API w naglowku (bez OAuth)."""
    r = requests.get(
        f"{API}{path}",
        headers={"Authorization": os.environ["EMPIK_API_KEY"],
                 "Accept": "application/json"},
        params=params,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def sanitize(order):
    """Usuwa dane osobowe kupujacego przed zapisem do bazy."""
    o = dict(order)
    for k in ("customer", "customer_notification_email",
              "billing_address", "shipping_address"):
        o.pop(k, None)
    return o


def fetch_orders(since_iso):
    """Pobiera zamowienia strona po stronie (paginacja offsetowa)."""
    offset = 0
    while True:
        data = empik_get("/api/orders", {
            "start_update_date": since_iso, "max": PAGE, "offset": offset})
        orders = data.get("orders", [])
        yield from orders
        offset += len(orders)
        if not orders or offset >= data.get("total_count", 0):
            break


def ensure_fee_type(conn):
    """Typ oplaty Empiku w slowniku fee_type, w grupie 'commission'
    (dzieki temu widok v_order_profit liczy go tak jak prowizje Allegro)."""
    conn.execute(text("""
        INSERT INTO fee_type (type_id, name, fee_group)
        VALUES (:t, 'Prowizja Empik Marketplace', 'commission')
        ON CONFLICT (type_id) DO NOTHING
    """), {"t": FEE_TYPE})


def upsert_order(conn, channel_id, o):
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
        "ch": channel_id, "ext": o["order_id"], "at": o.get("created_date"),
        "st": o.get("order_state"), "tot": o.get("total_price"),
        "cur": o.get("currency_iso_code", "PLN"),
        "ship": o.get("shipping_price"),
        "raw": json.dumps(sanitize(o)),
    }).scalar()

    conn.execute(text("DELETE FROM order_item WHERE order_id = :o"),
                 {"o": order_id})
    for line in o.get("order_lines") or []:
        qty = line.get("quantity") or 1
        unit = line.get("price_unit")
        if unit is None:  # 'price' to wartosc calej linii
            unit = (line.get("price") or 0) / qty
        conn.execute(text("""
            INSERT INTO order_item
                (order_id, offer_external_id, name, quantity, unit_price)
            VALUES (:o, :oe, :n, :q, :p)
        """), {"o": order_id, "oe": line.get("offer_sku"),
               "n": line.get("product_title"), "q": qty, "p": unit})

    # prowizja jako koszt: kwota ujemna, tak jak oplaty z billingu Allegro
    commission = o.get("total_commission")
    if commission:
        conn.execute(text("""
            INSERT INTO fee (channel_id, order_id, external_id, fee_type,
                             amount, booked_at)
            VALUES (:ch, :o, :ext, :t, :amt, :at)
            ON CONFLICT (channel_id, external_id) DO UPDATE SET
                amount = EXCLUDED.amount, order_id = EXCLUDED.order_id
        """), {"ch": channel_id, "o": order_id,
               "ext": f"{o['order_id']}-COMMISSION", "t": FEE_TYPE,
               "amt": -abs(commission), "at": o.get("created_date")})


def run(channel_id, days=400):
    engine = get_engine()

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

    since_iso = since.strftime("%Y-%m-%dT%H:%M:%SZ")
    count = 0
    try:
        with engine.begin() as c:
            ensure_fee_type(c)
            for order in fetch_orders(since_iso):
                upsert_order(c, channel_id, order)
                count += 1
        status, error = "ok", None
    except Exception as e:
        status, error = "error", str(e)[:500]

    with engine.begin() as c:
        c.execute(text("""
            UPDATE etl_run SET finished_at = now(), rows_loaded = :n,
                   status = :s, error = :e WHERE run_id = :r
        """), {"n": count, "s": status, "e": error, "r": run_id})
    print(f"Kanal {channel_id} (Empik): {status}, zamowien: {count}", error or "")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--channel", type=int, required=True)
    p.add_argument("--days", type=int, default=400)
    a = p.parse_args()
    run(a.channel, a.days)
