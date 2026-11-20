"""Test of Odoo ZELF schrijven weigert voor een sleutel, buiten de gateway om.

Dit script omzeilt bewust policy.json: het meet de tweede verdedigingslinie (de Odoo-rechten
van de bot-gebruiker). Alleen op een test-/stagingomgeving draaien.
Gebruik: python test_odoo_rechten.py <klant> <mode>
"""
import sys

from odoo_client import OdooClient, OdooError

if len(sys.argv) != 3:
    sys.exit("Gebruik: python test_odoo_rechten.py <klant> <inrichting|controle>")

c = OdooClient(sys.argv[1], sys.argv[2])
print(f"Odoo-rechtentest voor {c.klant} ({c.mode}), buiten de gateway om.\n")

pogingen = [
    ("account.account", "create", {"vals_list": [{"name": "ZZ-RECHTENTEST", "code": "ZZRT01", "account_type": "asset_current"}]}),
    ("res.partner", "create", {"vals_list": [{"name": "ZZ-RECHTENTEST"}]}),
    ("project.project", "create", {"vals_list": [{"name": "ZZ-RECHTENTEST"}]}),
]
for model, methode, payload in pogingen:
    try:
        res = c.call(model, methode, **payload)
        print(f"GAT   {model}.{methode}: Odoo liet het toe (id {res}). Opruimen via Odoo: zoek 'ZZ-RECHTENTEST'.")
    except OdooError as e:
        melding = " ".join(str(e).split())
        print(f"GEBLOKKEERD  {model}.{methode}: {melding[:400]}")
