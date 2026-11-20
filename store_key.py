"""Zet een API-sleutel in de Windows-kluis. Gebruik: python store_key.py <klant> <mode>

De sleutel wordt verborgen gevraagd: hij komt niet in de terminalgeschiedenis,
niet in een bestand en niet in de chat.
"""
import getpass
import sys

import secrets_store

if len(sys.argv) != 3:
    sys.exit("Gebruik: python store_key.py <klant> <inrichting|controle>")

klant, mode = sys.argv[1], sys.argv[2]
key = getpass.getpass(f"API-sleutel voor {klant} ({mode}) - tekens zijn onzichtbaar: ").strip()
if not key:
    sys.exit("Geen sleutel ingevoerd, niets opgeslagen.")
secrets_store.set_key(klant, mode, key)
print(f"Opgeslagen in Windows-kluis als '{secrets_store.SERVICE}' / '{klant}:{mode}'.")
