import json
import argparse
from sqlalchemy import text
from app.db import get_engine
from app.auth import get_access_token
from app.http import allegro_get


def run(channel_id):
    token = get_access_token(channel_id)
    data = allegro_get("/billing/billing-types", token)
    types = data if isinstance(data, list) else data.get("billingTypes", [])
    print("Przykladowy wpis:", json.dumps(types[0], ensure_ascii=False) if types else "brak")
    with get_engine().begin() as c:
        for t in types:
            c.execute(text("""
                INSERT INTO fee_type (type_id, name, raw_payload)
                VALUES (:i, :n, CAST(:r AS jsonb))
                ON CONFLICT (type_id) DO UPDATE
                SET name = EXCLUDED.name, raw_payload = EXCLUDED.raw_payload
            """), {"i": t["id"],
                   "n": t.get("description") or t.get("name"),
                   "r": json.dumps(t)})
    print("Zapisano typow:", len(types))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--channel", type=int, required=True)
    run(p.parse_args().channel)