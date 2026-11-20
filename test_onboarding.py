"""Test van pin-logica (nepdata) en van de voorcontrole tegen de staging (alleen lezen, niets opgeslagen).
Gebruik: python test_onboarding.py
"""
import pathlib
import tempfile
from datetime import date, timedelta

import klant_toevoegen as kt
import pin
from odoo_client import OdooClient

pin.PAD = pathlib.Path(tempfile.mkdtemp(prefix="pin-test-")) / "aangesloten.json"   # raakt het echte bestand niet
CFG = {"url": "https://bakker.odoo.com", "database": "bakker", "bron": "register"}
vandaag = date.today()

print("== 1. Pin-logica ==")
gevallen = [
    ("register-klant zonder onboarding", None, CFG, False),
    ("handmatige klant zonder onboarding", None, {**CFG, "bron": "handmatig"}, True),
]
for naam, p, cfg, verwacht in gevallen:
    ok, m = pin.controleer("bakker", "controle", cfg)
    print(f"  {'OK ' if ok == verwacht else 'FOUT'} {naam}: {ok} {m[:60]}")
    assert ok == verwacht

def zet(**kw):
    pin.zet("bakker", "controle", **{"url": "https://bakker.odoo.com", "database": "bakker",
                                      "verloopt": (vandaag + timedelta(days=20)).isoformat(), **kw})

zet(); ok, m = pin.controleer("bakker", "controle", CFG); assert ok and not m; print("  OK  geldige onboarding")
zet(url="https://andere.odoo.com"); ok, m = pin.controleer("bakker", "controle", CFG); assert not ok; print("  OK  gewijzigde URL geblokkeerd")
zet(database="andere"); ok, m = pin.controleer("bakker", "controle", CFG); assert not ok; print("  OK  gewijzigde databasenaam geblokkeerd")
zet(verloopt=(vandaag - timedelta(days=1)).isoformat()); ok, m = pin.controleer("bakker", "controle", CFG); assert not ok; print("  OK  verlopen sleutel geblokkeerd")
zet(verloopt=(vandaag + timedelta(days=3)).isoformat()); ok, m = pin.controleer("bakker", "controle", CFG); assert ok and "verloopt over 3" in m; print("  OK  waarschuwing bij bijna verlopen")
pin.verwijder("bakker", "controle"); assert pin.haal("bakker", "controle") is None; print("  OK  intrekken")

print("\n== 2. Voorcontrole tegen de staging (alleen lezen) ==")
for mode in ("controle", "inrichting"):
    print(f"\n  -- trial / {mode} --")
    c = OdooClient("trial", mode)
    overtredingen, waarschuwingen, regels = kt.voorcontrole(c, mode)
    print("\n".join(regels))
    print("  UITKOMST:", "GOEDGEKEURD" if not overtredingen else "AFGEKEURD")
    for o in overtredingen:
        print("    - AFKEURING:", o)
    for w in waarschuwingen:
        print("    - let op:", w)
print("\nKlaar.")
