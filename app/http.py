import os
import requests
from dotenv import load_dotenv

load_dotenv()

API = "https://api.allegro.pl"
USER_AGENT = os.getenv("ALLEGRO_USER_AGENT", "")


def allegro_get(path, token, params=None):
    r = requests.get(
        f"{API}{path}",
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.allegro.public.v1+json",
            "Accept-Language": "pl-PL",
            "Authorization": f"Bearer {token}",
        },
        params=params,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()