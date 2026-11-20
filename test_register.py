"""Test van het klantenregister. Deel 1 en 2 gebruiken nepdata (geen netwerk); deel 3 leest echt uit de staging.
Gebruik: python test_register.py
"""
import pathlib
import tempfile
import time

import audit
import register
from odoo_client import OdooError

audit.DIR = pathlib.Path(tempfile.mkdtemp(prefix="audit-test-"))   # testregels komen niet in het echte log

RIJEN = [
    {"name": "Bakkerij Jansen", "database_url": "https://bakker-jansen.odoo.com", "database_name": "bakker-jansen",
     "database_version": "20.0", "database_hosting": "odoo_online", "database_last_synchro": "2026-11-20 08:00:00"},
    {"name": "Evil", "database_url": "https://evil.example.com", "database_name": "klant-evil"},
    {"name": "Onveilig", "database_url": "http://x.odoo.com", "database_name": "klant-http"},
    {"name": "Truc", "database_url": "https://x.odoo.com@evil.nl", "database_name": "klant-truc"},
    {"name": "Nepdomein", "database_url": "https://odoo.com.evil.nl", "database_name": "klant-nep"},
    {"name": "Zonder naam", "database_url": "https://leeg.odoo.com", "database_name": ""},
]


class NepClient:
    gedrag = "ok"

    def __init__(self, *a, **k):
        pass

    def call(self, model, methode, **p):
        if NepClient.gedrag == "fout":
            raise OdooError("HTTP 403 bij project.project.search_read: geen toegang")
        assert model == "project.project" and methode == "search_read"
        assert set(p["fields"]) == set(register.VELDEN), "alleen de vaste veldlijst mag gelezen worden"
        return RIJEN


echt_client, echte_sleutel = register.OdooClient, register.secrets_store.get_key
register.OdooClient = NepClient
register.secrets_store.get_key = lambda k, m: "nepsleutel"

print("== 1. Nepregister met goede en slechte items ==")
NepClient.gedrag = "ok"
register._cache["tijd"] = 0
codes = set(register._ververs() or register._cache["register"])
print("  in register:", sorted(codes))
assert codes == {"bakker-jansen"}, "alleen het item met een toegestaan https-domein mag erdoor"
assert register.resolve("bakker-jansen")["bron"] == "register"
for slecht in ("klant-evil", "klant-http", "klant-truc", "klant-nep"):
    try:
        register.resolve(slecht)
        raise SystemExit(f"FOUT: {slecht} had geweigerd moeten worden")
    except LookupError:
        pass
print("  OK: 1 goed item, 4 afgekeurde URL's, 1 zonder naam")
afgekeurd = [e for e in audit.lees_alles() if e["uitkomst"] == "geweigerd"]
print("  auditregels voor afgekeurde items:", len(afgekeurd))
assert len(afgekeurd) == 5

print("\n== 2. Register onbereikbaar (fail closed) ==")
NepClient.gedrag = "fout"
register._cache["tijd"] = 0
l = register.lijst()
print("  status:", l["register"])
assert "onbereikbaar" in l["register"]
assert all(k["bron"] == "handmatig" for k in l["klanten"]), "bij een fout geen oude register-klanten tonen"
try:
    register.resolve("bakker-jansen")
    raise SystemExit("FOUT: oud register-item mag niet meer bruikbaar zijn")
except LookupError:
    print("  OK: geen register-klanten meer, handmatige klanten blijven")

print("\n== 3. Echt register in de staging ==")
register.OdooClient, register.secrets_store.get_key = echt_client, echte_sleutel
register._cache["tijd"] = 0
l = register.lijst(True)
print("  register:", l["register"])
for k in l["klanten"]:
    print("  -", k["code"], "|", k["bron"], "| aangesloten:", k["aangesloten_modes"])
print("\nKlaar.")
