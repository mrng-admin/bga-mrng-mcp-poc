"""Klantenregister: de lijst van klantdatabases komt uit de Databases-app van het kantoor.

Een klantdatabase is daar een project.project-record met database_url, database_name enz.
De klantcode in de gateway is de database_name (uniek). We lezen alleen een vaste veldlijst.

Veiligheid: de gateway stuurt de sleutel van een klant naar de URL uit het register. Wie het register
kan wijzigen zou die URL kunnen verleggen. Daarom: alleen https en alleen toegestane domeinen.
"""
import json
import time
from pathlib import Path
from urllib.parse import urlparse

import audit
import pin
import secrets_store
from odoo_client import KLANTEN, OdooClient, OdooError

KANTOOR_PAD = Path(__file__).parent / "kantoor.json"
VELDEN = ["name", "database_url", "database_name", "database_version", "database_hosting",
          "database_can_access", "database_last_synchro"]
TTL = 300  # seconden; een nieuwe klant in de Databases-app is dus binnen 5 minuten zichtbaar
_cache: dict = {"tijd": 0.0, "register": {}, "status": "nog niet gelezen"}


def _kantoor() -> dict | None:
    if not KANTOOR_PAD.exists():
        return None
    return json.loads(KANTOOR_PAD.read_text(encoding="utf-8"))


def _url_ok(url: str, toegestaan: list[str]) -> tuple[bool, str]:
    p = urlparse(url or "")
    if p.scheme != "https" or not p.hostname:
        return False, "geen https-URL"
    host = p.hostname.lower()
    if not any(host.endswith(d.lower()) for d in toegestaan):
        return False, f"domein {host} niet toegestaan"
    return True, ""


def _lees_register(cfg: dict) -> dict[str, dict]:
    bron = cfg["sleutel"]
    c = OdooClient("_kantoor", bron["mode"], cfg={"url": cfg["url"], "database": cfg["database"]},
                   key=secrets_store.get_key(bron["klant"], bron["mode"]))
    rijen = c.call("project.project", "search_read",
                   domain=[["database_url", "!=", False], ["database_name", "!=", False]],
                   fields=VELDEN, limit=500)
    register, afgekeurd = {}, 0
    for r in rijen:
        ok, reden = _url_ok(r.get("database_url"), cfg.get("toegestane_domeinen", []))
        code = (r.get("database_name") or "").strip()
        if not ok or not code:
            afgekeurd += 1
            audit.log_best_effort(tool="register_lezen", klant=code or None, uitkomst="geweigerd",
                                  reden=f"register-item afgekeurd: {reden or 'geen databasenaam'}")
            continue
        register[code] = {"url": r["database_url"].rstrip("/"), "database": code, "naam": r.get("name"),
                          "versie": r.get("database_version"), "hosting": r.get("database_hosting"),
                          "laatste_sync": r.get("database_last_synchro")}
    return register


def _ververs(forceer: bool = False) -> None:
    if not forceer and time.time() - _cache["tijd"] < TTL:
        return
    cfg = _kantoor()
    if cfg is None:
        _cache.update(tijd=time.time(), register={}, status="geen kantoor.json: alleen handmatige klanten")
        return
    try:
        _cache.update(tijd=time.time(), register=_lees_register(cfg), status="ok")
    except (OdooError, LookupError) as e:
        # Fail closed: bij een fout geen register-klanten, ook geen oude. Handmatige klanten blijven wel (indien toegestaan).
        _cache.update(tijd=time.time(), register={}, status=f"register onbereikbaar: {str(e)[:150]}")
        audit.log_best_effort(tool="register_lezen", uitkomst="fout", reden=_cache["status"])


def _handmatig_toegestaan() -> bool:
    cfg = _kantoor()
    return True if cfg is None else bool(cfg.get("handmatig_toegestaan", False))


def resolve(klant: str) -> dict:
    """Geeft {'url','database','bron'} voor een klantcode, of LookupError."""
    _ververs()
    if klant in _cache["register"]:
        return {**_cache["register"][klant], "bron": "register"}
    if _handmatig_toegestaan() and klant in KLANTEN:
        return {**KLANTEN[klant], "bron": "handmatig"}
    raise LookupError(f"Klant '{klant}' staat niet in de Databases-app van het kantoor (register: {_cache['status']}).")


def lijst(forceer: bool = False) -> dict:
    _ververs(forceer)
    klanten = []
    items = {**_cache["register"]}
    bron = {code: "register" for code in items}
    if _handmatig_toegestaan():
        for code, cfg in KLANTEN.items():
            if code not in items:
                items[code] = {"naam": code, "versie": None, "hosting": None, "laatste_sync": None}
                bron[code] = "handmatig"
    for code in sorted(items):
        modes = [m for m in secrets_store.MODES if secrets_store.has_key(code, m)]
        verloopt = {m: (pin.haal(code, m) or {}).get("verloopt") for m in modes}
        i = items[code]
        klanten.append({"code": code, "naam": i.get("naam"), "versie": i.get("versie"), "hosting": i.get("hosting"),
                        "bron": bron[code], "aangesloten_modes": modes, "sleutel_verloopt": verloopt})
    return {"register": _cache["status"], "aantal": len(klanten), "klanten": klanten}
