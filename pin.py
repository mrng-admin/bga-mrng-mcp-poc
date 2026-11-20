"""Vastgezette onboarding-gegevens per klant en mode (geen geheimen).

Bij onboarding leggen we vast naar welke URL de sleutel hoort en tot wanneer hij geldig is. Verandert de URL
daarna in het register, dan blokkeert de gateway de klant tot een beheerder het bevestigt: zo kan een
aangepast register nooit een sleutel naar een andere server sturen.
Definitief: deze gegevens horen als metadata bij de sleutel in Infisical.
"""
import json
import os
from datetime import date
from pathlib import Path

PAD = Path(__file__).parent / "aangesloten.json"
WAARSCHUWING_DAGEN = 7


def laad() -> dict:
    if not PAD.exists():
        return {}
    return json.loads(PAD.read_text(encoding="utf-8"))


def _schrijf(data: dict) -> None:
    tmp = PAD.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, PAD)


def haal(klant: str, mode: str) -> dict | None:
    return laad().get(klant, {}).get(mode)


def zet(klant: str, mode: str, **velden) -> None:
    data = laad()
    data.setdefault(klant, {})[mode] = velden
    _schrijf(data)


def verwijder(klant: str, mode: str) -> None:
    data = laad()
    data.get(klant, {}).pop(mode, None)
    if klant in data and not data[klant]:
        del data[klant]
    _schrijf(data)


def dagen_resterend(pin: dict | None) -> int | None:
    if not pin or not pin.get("verloopt"):
        return None
    return (date.fromisoformat(pin["verloopt"]) - date.today()).days


def controleer(klant: str, mode: str, cfg: dict) -> tuple[bool, str]:
    """(mag_verbinden, melding). Fail closed voor register-klanten zonder onboarding."""
    p = haal(klant, mode)
    if p is None:
        if cfg.get("bron") == "handmatig":
            return True, "Let op: deze handmatige klant is niet via onboarding vastgezet."
        return False, (f"'{klant}' is niet aangesloten via onboarding voor mode '{mode}'. "
                       f"Een beheerder moet eerst klant_toevoegen.py draaien.")
    if p["url"].rstrip("/") != cfg["url"].rstrip("/") or p["database"] != cfg["database"]:
        return False, ("De URL of databasenaam in het register wijkt af van de onboarding; verbinden is geblokkeerd. "
                       "Een beheerder moet dit controleren en bevestigen (klant_toevoegen.py herbevestig).")
    rest = dagen_resterend(p)
    if rest is not None and rest < 0:
        return False, f"De sleutel voor '{klant}' ({mode}) is verlopen op {p['verloopt']}. Maak een nieuwe sleutel en onboard opnieuw."
    if rest is not None and rest <= WAARSCHUWING_DAGEN:
        return True, f"Let op: de sleutel verloopt over {rest} dag(en), op {p['verloopt']}."
    return True, ""
