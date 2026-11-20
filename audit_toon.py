"""Leesbaar overzicht van het auditlog + controle van de keten.

Gebruik: python audit_toon.py [aantal]      (standaard de laatste 30 regels)
"""
import sys

import audit

n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
regels = audit.lees_alles()
ok, melding = audit.verifieer()

print(f"{len(regels)} regels in totaal. Integriteit: {'OK' if ok else 'FOUT'} - {melding}\n")
for e in regels[-n:]:
    wat = e.get("model") or ""
    details = []
    for k in ("ids", "velden", "domeinvelden", "nieuwe_ids", "aantal", "odoo_uid"):
        if k in e:
            details.append(f"{k}={e[k]}")
    reden = f" | {e['reden']}" if e.get("reden") else ""
    print(f"{e['ts'][:19]}  {e.get('klant') or '-':<8} {e.get('mode') or '-':<10} {e['tool']:<20} "
          f"{e.get('actie') or '':<9} {wat:<18} {e['uitkomst']:<9} {' '.join(details)}{reden}")
sys.exit(0 if ok else 1)
