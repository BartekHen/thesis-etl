import os
import time
import argparse
import requests
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from sqlalchemy import text
from app.db import get_engine

load_dotenv()

AUTH_URL = "https://allegro.pl/auth/oauth"
CLIENT_ID = os.getenv("ALLEGRO_CLIENT_ID")
CLIENT_SECRET = os.getenv("ALLEGRO_CLIENT_SECRET")
HEADERS = {"User-Agent": os.getenv("ALLEGRO_USER_AGENT", "")}
SCOPES = ("allegro:api:orders:read allegro:api:sale:offers:read "
          "allegro:api:billing:read allegro:api:payments:read")


def _save(engine, channel_id, tok):
    expires = datetime.now(timezone.utc) + timedelta(seconds=tok["expires_in"])
    with engine.begin() as c:
        c.execute(text("""
            INSERT INTO channel_credential
                (channel_id, access_token, refresh_token, expires_at)
            VALUES (:ch, :a, :r, :e)
            ON CONFLICT (channel_id) DO UPDATE
            SET access_token = :a, refresh_token = :r,
                expires_at = :e, updated_at = now()
        """), {"ch": channel_id, "a": tok["access_token"],
               "r": tok["refresh_token"], "e": expires})


def authorize(channel_id: int):
    r = requests.post(
        f"{AUTH_URL}/device",
        auth=(CLIENT_ID, CLIENT_SECRET),
        headers=HEADERS,
        params={"client_id": CLIENT_ID, "scope": SCOPES},
        timeout=30,
    )
    if r.status_code != 200:
        raise RuntimeError(f"{r.status_code}: {r.text}")
    d = r.json()
    print("\nOtworz w przegladarce i zaloguj sie NA WLASCIWE konto Allegro:")
    print(d["verification_uri_complete"], "\n")

    interval = d.get("interval", 5)
    deadline = time.time() + d["expires_in"]
    while time.time() < deadline:
        time.sleep(interval)
        t = requests.post(
            f"{AUTH_URL}/token",
            auth=(CLIENT_ID, CLIENT_SECRET),
            headers=HEADERS,
            params={"grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "device_code": d["device_code"]},
            timeout=30,
        )
        if t.status_code == 200:
            _save(get_engine(), channel_id, t.json())
            print("Zapisano token dla channel_id =", channel_id)
            return
        err = t.json().get("error")
        if err == "slow_down":
            interval += 5
        elif err != "authorization_pending":
            raise RuntimeError(t.text)
    raise TimeoutError("Minal czas na autoryzacje")


def get_access_token(channel_id: int) -> str:
    engine = get_engine()
    with engine.connect() as c:
        row = c.execute(text(
            "SELECT access_token, refresh_token, expires_at "
            "FROM channel_credential WHERE channel_id = :ch"),
            {"ch": channel_id}).fetchone()
    if row is None:
        raise RuntimeError(
            f"Brak tokenu. Uruchom: python -m app.auth --channel {channel_id}")
    access, refresh, expires = row
    if expires > datetime.now(timezone.utc) + timedelta(minutes=2):
        return access
    t = requests.post(
        f"{AUTH_URL}/token",
        auth=(CLIENT_ID, CLIENT_SECRET),
        headers=HEADERS,
        params={"grant_type": "refresh_token", "refresh_token": refresh},
        timeout=30,
    )
    t.raise_for_status()
    tok = t.json()
    _save(engine, channel_id, tok)
    return tok["access_token"]


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--channel", type=int, required=True)
    authorize(p.parse_args().channel)