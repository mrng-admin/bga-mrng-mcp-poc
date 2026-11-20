"""Losse test, nog zonder MCP. Gebruik: python test_connection.py <klant> <mode>"""
import sys

from odoo_client import OdooClient, OdooError

if len(sys.argv) != 3:
    sys.exit("Gebruik: python test_connection.py <klant> <inrichting|controle>")

c = OdooClient(sys.argv[1], sys.argv[2])
try:
    print("Gebruikerscontext:", c.call("res.users", "context_get"))
    print("Bedrijven:", c.call("res.company", "search_read", domain=[], fields=["name"], limit=5))
    print("Leesbare boekingen (account.move):", c.call("account.move", "search_count", domain=[]))
except OdooError as e:
    sys.exit(f"Mislukt: {e}")
print("OK: verbinding en rechten werken.")
