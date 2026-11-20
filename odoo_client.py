"""Minimale Odoo JSON-2 client (Odoo 19+). Sleutel komt uit de kluis, nooit uit code."""
import json
import logging
from pathlib import Path

import httpx

import secrets_store

# httpx logt standaard elke URL; voor een kluis-gedreven gateway houden we de logs stil.
logging.getLogger("httpx").setLevel(logging.WARNING)

KLANTEN = json.loads((Path(__file__).parent / "klanten.json").read_text(encoding="utf-8"))


class OdooError(Exception):
    pass


class OdooClient:
    def __init__(self, klant: str, mode: str, cfg: dict | None = None, key: str | None = None):
        """cfg: {'url','database'} uit het register; zonder cfg valt hij terug op klanten.json (handmatig).
        key: alleen voor interne leesacties op het register; normaal komt de sleutel uit de kluis."""
        if cfg is None:
            if klant not in KLANTEN:
                raise LookupError(f"Onbekende klant '{klant}'")
            cfg = KLANTEN[klant]
        self.klant, self.mode = klant, mode
        self.base = cfg["url"].rstrip("/")
        self.db = cfg["database"]
        self._key = key or secrets_store.get_key(klant, mode)

    def call(self, model: str, method: str, **payload):
        headers = {
            "Authorization": f"bearer {self._key}",
            "X-Odoo-Database": self.db,
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "mrng-mcp-poc",
        }
        r = httpx.post(f"{self.base}/json/2/{model}/{method}", headers=headers,
                       json=payload, timeout=30)
        if r.status_code != 200:
            # Alleen status en Odoo-foutmelding, nooit headers (daar zit de sleutel in).
            try:
                msg = r.json().get("message") or r.text[:300]
            except Exception:
                msg = r.text[:300]
            raise OdooError(f"HTTP {r.status_code} bij {model}.{method}: {msg}")
        return r.json()
