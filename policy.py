"""Toetst elke actie aan policy.json. Default deny; bij elke fout wordt alles geweigerd."""
import fnmatch
import json
from pathlib import Path

POLICY_PAD = Path(__file__).parent / "policy.json"
ACTIES = ("lezen", "aanmaken", "wijzigen")

# Hard in code, niet door het beleidsbestand te overrulen: hiermee kun je rechten of code
# (serveracties, automatiseringen) aanpassen en dus de rest van het beleid omzeilen.
NOOIT_SCHRIJVEN = ("ir.*", "res.users*", "res.groups*", "base.automation*")


def _laad() -> dict:
    return json.loads(POLICY_PAD.read_text(encoding="utf-8"))["modules"]


def _match(model: str, patronen: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(model, p) for p in patronen)


def toegestaan(model: str, actie: str, mode: str) -> tuple[bool, str]:
    """Geeft (mag, reden). De reden is bedoeld om aan de gebruiker te tonen."""
    if actie not in ACTIES:
        return False, f"Onbekende actie '{actie}'."
    if actie != "lezen" and _match(model, list(NOOIT_SCHRIJVEN)):
        return False, f"Schrijven op {model} is altijd verboden (vast in de code)."
    try:
        modules = _laad()
    except Exception as e:  # fail closed
        return False, f"Beleidsbestand onleesbaar ({type(e).__name__}); alles is geweigerd."
    gevonden = False
    for naam, m in modules.items():
        if _match(model, m.get("modellen", [])):
            gevonden = True
            if actie in m.get("rechten", {}).get(mode, []):
                return True, f"Toegestaan via module '{naam}'."
    if not gevonden:
        return False, f"{model} valt onder geen enkele module in policy.json."
    return False, f"Actie '{actie}' op {model} is in mode '{mode}' niet toegestaan volgens policy.json."


def overzicht(mode: str) -> dict[str, list[str]]:
    """Effectieve rechten per module voor een mode (voor klant_policy)."""
    try:
        return {n: m.get("rechten", {}).get(mode, []) for n, m in _laad().items()}
    except Exception as e:
        return {"FOUT": [f"Beleidsbestand onleesbaar: {type(e).__name__}"]}
