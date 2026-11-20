"""Auditlog: append-only JSON Lines met een hash-keten, zodat achteraf wijzigen of weghalen opvalt.

Wat erin staat: wie, wanneer, welke klant en mode, welke tool, model, actie, ids, veldNAMEN, uitkomst.
Wat er NIET in staat: veldwaarden, domeinwaarden, resultaten en sleutels.
"""
import getpass
import hashlib
import json
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

DIR = Path(__file__).parent / "audit"
SESSIE = uuid.uuid4().hex[:12]
GEBRUIKER = getpass.getuser()  # hosted versie: de SSO-identiteit van de accountant
_NUL = "0" * 64
_lock = threading.Lock()
_prev: str | None = None


def _hash(event: dict) -> str:
    body = json.dumps({k: v for k, v in event.items() if k != "hash"}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _laatste_hash() -> str:
    for f in sorted(DIR.glob("audit-*.jsonl"), reverse=True):
        regels = f.read_text(encoding="utf-8").splitlines()
        if regels:
            return json.loads(regels[-1])["hash"]
    return _NUL


def log(**velden) -> None:
    """Schrijf één regel. Raised bij een fout, zodat de aanroeper kan besluiten de actie te weigeren."""
    global _prev
    with _lock:
        DIR.mkdir(exist_ok=True)
        if _prev is None:
            _prev = _laatste_hash()
        nu = datetime.now(timezone.utc)
        event = {"ts": nu.isoformat(timespec="milliseconds"), "sessie": SESSIE,
                 "gebruiker": GEBRUIKER, **velden, "prev": _prev}
        event["hash"] = _hash(event)
        with open(DIR / f"audit-{nu:%Y-%m}.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n")
        _prev = event["hash"]


def log_best_effort(**velden) -> None:
    try:
        log(**velden)
    except Exception as e:  # nooit stdout: dat is het MCP-protocol
        print(f"AUDITLOG FOUT: {type(e).__name__}", file=sys.stderr)


def lees_alles() -> list[dict]:
    regels = []
    for f in sorted(DIR.glob("audit-*.jsonl")):
        for r in f.read_text(encoding="utf-8").splitlines():
            if r.strip():
                regels.append(json.loads(r))
    return regels


def verifieer() -> tuple[bool, str]:
    """Controleer de keten: elke regel moet kloppen en naar de vorige verwijzen."""
    vorige = _NUL
    for i, e in enumerate(lees_alles(), 1):
        if e.get("prev") != vorige:
            return False, f"Keten verbroken bij regel {i}: er ontbreekt of is iets gewijzigd vóór deze regel."
        if _hash(e) != e.get("hash"):
            return False, f"Regel {i} is gewijzigd (hash klopt niet)."
        vorige = e["hash"]
    return True, "Keten intact."
