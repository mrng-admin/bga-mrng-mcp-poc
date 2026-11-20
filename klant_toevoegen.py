"""Onboarding van een klant voor de gateway.

  python klant_toevoegen.py toevoegen <klant> <inrichting|controle> [--verloopt JJJJ-MM-DD]
  python klant_toevoegen.py status
  python klant_toevoegen.py herbevestig <klant> <mode>
  python klant_toevoegen.py intrekken <klant> <mode>

'toevoegen' vraagt de sleutel verborgen, controleert de rechten van de bot-gebruiker ZONDER records aan te maken
(dus veilig op een echte klantdatabase), en slaat pas daarna de sleutel in de kluis op en de URL en verloopdatum vast.
"""
import argparse
import getpass
import sys
from datetime import date, timedelta

import audit
import pin
import register
import secrets_store
from odoo_client import OdooClient, OdooError

OPS = ("create", "write", "unlink")

# Nooit schrijfrechten, in geen enkele mode: hiermee kun je rechten, code of automatiseringen aanpassen.
SENSITIEF = {
    "res.users": ("create", "unlink"),
    "res.groups": OPS,
    "ir.rule": OPS,
    "ir.model.access": OPS,
    "ir.cron": OPS,
    "ir.actions.server": OPS,
    "base.automation": OPS,
}
# Extra voor mode 'controle': die gebruiker mag nergens iets aanmaken, wijzigen of verwijderen.
CONTROLE_GEEN_SCHRIJVEN = ["account.move", "account.move.line", "account.account", "account.journal", "account.tax",
                           "account.payment", "res.partner", "res.partner.bank", "product.template",
                           "project.project", "project.task"]


def heeft_recht(client: OdooClient, model: str, op: str):
    """True/False, of None als het model niet bestaat in die database. Fout bij onduidelijkheid (fail closed)."""
    fouten = []
    for methode, kw in (("has_access", {"operation": op}),
                        ("check_access_rights", {"operation": op, "raise_exception": False})):
        try:
            return bool(client.call(model, methode, **kw))
        except OdooError as e:
            fouten.append(str(e))
    if any("404" in f for f in fouten):
        return None
    raise OdooError("; ".join(f[:100] for f in fouten))


# Standaardrechten van elke interne Odoo-gebruiker (relaties wijzigen, eigen To-Do-taken). Daar kan de Odoo-rol
# niets aan veranderen; in mode 'controle' wordt dit alleen gemeld, en de gateway-policy houdt het tegen.
TOLEREERD_BIJ_CONTROLE = {"res.partner": ("write",), "project.task": OPS}


def voorcontrole(client: OdooClient, mode: str) -> tuple[list[str], list[str], list[str]]:
    """Geeft (overtredingen, waarschuwingen, regels voor weergave). Schrijft nooit iets."""
    checks = dict(SENSITIEF)
    if mode == "controle":
        for m in CONTROLE_GEEN_SCHRIJVEN:
            checks[m] = OPS
    overtredingen, waarschuwingen, regels = [], [], []
    for model, ops in checks.items():
        rechten = []
        for op in ops:
            try:
                r = heeft_recht(client, model, op)
            except OdooError as e:
                overtredingen.append(f"{model}: kon '{op}' niet controleren ({str(e)[:80]})")
                rechten.append(f"{op}=?")
                continue
            if r is True:
                if mode == "controle" and op in TOLEREERD_BIJ_CONTROLE.get(model, ()):
                    waarschuwingen.append(f"{model}: '{op}' (standaardrecht van een interne gebruiker)")
                else:
                    overtredingen.append(f"{model}: heeft het recht '{op}'")
            rechten.append(f"{op}={'ja' if r else ('n.v.t.' if r is None else 'nee')}")
        regels.append(f"  {model:<20} {', '.join(rechten)}")
    return overtredingen, waarschuwingen, regels


def cmd_toevoegen(a):
    try:
        cfg = register.resolve(a.klant)
    except LookupError as e:
        sys.exit(f"Afgebroken: {e}")
    verloopt = date.fromisoformat(a.verloopt) if a.verloopt else date.today() + timedelta(days=28)
    if verloopt > date.today() + timedelta(days=31):
        print("Let op: een verloopdatum van meer dan een maand vooruit klopt waarschijnlijk niet met de sleutel.")
    print(f"Klant : {a.klant} ({cfg['bron']})\nURL   : {cfg['url']}\nMode  : {a.mode}\nVerloopt: {verloopt}\n")
    if a.uit_kluis:
        key = secrets_store.get_key(a.klant, a.mode)   # bestaande sleutel vastzetten, zonder opnieuw te typen
        print("Sleutel uit de kluis gebruikt.")
    else:
        key = getpass.getpass("API-sleutel van de bot-gebruiker (tekens zijn onzichtbaar): ").strip()
    if not key:
        sys.exit("Geen sleutel ingevoerd, niets gedaan.")
    client = OdooClient(a.klant, a.mode, cfg=cfg, key=key)
    try:
        ctx = client.call("res.users", "context_get")
    except OdooError as e:
        audit.log_best_effort(tool="onboarding", klant=a.klant, mode=a.mode, uitkomst="fout", reden=str(e)[:200])
        sys.exit(f"De sleutel werkt niet: {e}")
    uid = ctx.get("uid")
    try:
        login = client.call("res.users", "read", ids=[uid], fields=["login"])[0]["login"]
    except Exception:
        login = None
    print(f"Verbinding OK. Bot-gebruiker: uid {uid}" + (f", login {login}" if login else "") + "\n\nRechtencontrole (alleen lezen, geen records aangemaakt):")
    overtredingen, waarschuwingen, regels = voorcontrole(client, a.mode)
    print("\n".join(regels))
    if waarschuwingen:
        print("\nLet op, in Odoo zelf kan deze gebruiker nog schrijven op (alleen de gateway houdt dit tegen):")
        print("\n".join("  - " + w for w in waarschuwingen))
    if overtredingen:
        audit.log_best_effort(tool="onboarding", klant=a.klant, mode=a.mode, uitkomst="geweigerd",
                              reden=f"{len(overtredingen)} te ruime rechten")
        print("\nAFGEKEURD, er is niets opgeslagen. Te ruime rechten voor mode '%s':" % a.mode)
        print("\n".join("  - " + o for o in overtredingen))
        sys.exit(1)
    print("\nGoedgekeurd.")
    if input(f"Sleutel opslaan in de kluis en URL en verloopdatum vastzetten voor {a.klant} ({a.mode})? (ja/nee): ").strip().lower() != "ja":
        sys.exit("Niet opgeslagen.")
    secrets_store.set_key(a.klant, a.mode, key)
    pin.zet(a.klant, a.mode, url=cfg["url"].rstrip("/"), database=cfg["database"], bot_login=login, uid=uid,
            verloopt=verloopt.isoformat(), aangesloten_op=date.today().isoformat(), aangesloten_door=audit.GEBRUIKER)
    audit.log_best_effort(tool="onboarding", klant=a.klant, mode=a.mode, uitkomst="ok", odoo_uid=uid)
    print(f"Klaar. '{a.klant}' is aangesloten voor '{a.mode}'. Sleutel verloopt op {verloopt}.")


def cmd_status(_):
    l = register.lijst(True)
    print(f"Register: {l['register']}; {l['aantal']} klant(en)\n")
    print(f"{'klant':<32} {'mode':<11} {'verloopt':<11} {'dagen':>5}  bot-login")
    onboard = 0
    for k in l["klanten"]:
        for mode in secrets_store.MODES:
            p = pin.haal(k["code"], mode)
            if p:
                onboard += 1
                d = pin.dagen_resterend(p)
                vlag = "  VERLOPEN" if d is not None and d < 0 else ("  verloopt bijna" if d is not None and d <= pin.WAARSCHUWING_DAGEN else "")
                print(f"{k['code']:<32} {mode:<11} {p['verloopt']:<11} {d:>5}  {p.get('bot_login') or '-'}{vlag}")
    print(f"\n{onboard} aansluiting(en) vastgezet; {sum(1 for k in l['klanten'] if not k['aangesloten_modes'])} klant(en) zonder sleutel.")


def cmd_herbevestig(a):
    p = pin.haal(a.klant, a.mode)
    if not p:
        sys.exit("Geen onboarding gevonden voor deze klant en mode.")
    try:
        cfg = register.resolve(a.klant)
    except LookupError as e:
        sys.exit(f"Afgebroken: {e}")
    print(f"Vastgezet : {p['url']}  ({p['database']})\nRegister  : {cfg['url']}  ({cfg['database']})")
    if p["url"].rstrip("/") == cfg["url"].rstrip("/") and p["database"] == cfg["database"]:
        sys.exit("Geen verschil, niets te bevestigen.")
    print("\nControleer dat dit echt dezelfde klant is (bijvoorbeeld een verhuizing van Odoo.sh naar Odoo Online). "
          "Bij twijfel: intrekken en opnieuw onboarden met een nieuwe sleutel.")
    if input("Nieuwe URL bevestigen? (ja/nee): ").strip().lower() != "ja":
        sys.exit("Niet gewijzigd.")
    pin.zet(a.klant, a.mode, **{**p, "url": cfg["url"].rstrip("/"), "database": cfg["database"]})
    audit.log_best_effort(tool="onboarding_herbevestig", klant=a.klant, mode=a.mode, uitkomst="ok")
    print("Bevestigd.")


def cmd_intrekken(a):
    if not pin.haal(a.klant, a.mode) and not secrets_store.has_key(a.klant, a.mode):
        sys.exit("Niets gevonden om in te trekken.")
    if input(f"Sleutel en vastlegging voor {a.klant} ({a.mode}) verwijderen? (ja/nee): ").strip().lower() != "ja":
        sys.exit("Niet verwijderd.")
    try:
        secrets_store.delete_key(a.klant, a.mode)
    except Exception:
        pass
    pin.verwijder(a.klant, a.mode)
    audit.log_best_effort(tool="onboarding_intrekken", klant=a.klant, mode=a.mode, uitkomst="ok")
    print("Verwijderd uit de kluis en uit de vastlegging.\nVergeet niet ook de bot-gebruiker en sleutel in de klantdatabase zelf te verwijderen of te archiveren.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("toevoegen"); t.add_argument("klant"); t.add_argument("mode", choices=secrets_store.MODES)
    t.add_argument("--verloopt")
    t.add_argument("--uit-kluis", action="store_true", help="gebruik de sleutel die al in de kluis staat")
    t.set_defaults(f=cmd_toevoegen)
    sub.add_parser("status").set_defaults(f=cmd_status)
    h = sub.add_parser("herbevestig"); h.add_argument("klant"); h.add_argument("mode", choices=secrets_store.MODES); h.set_defaults(f=cmd_herbevestig)
    i = sub.add_parser("intrekken"); i.add_argument("klant"); i.add_argument("mode", choices=secrets_store.MODES); i.set_defaults(f=cmd_intrekken)
    args = ap.parse_args()
    args.f(args)
