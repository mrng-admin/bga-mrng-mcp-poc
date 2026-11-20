"""Enige plek waar sleutels worden opgehaald of opgeslagen.

PoC-backend: Windows Credential Manager via keyring.
Definitieve backend: Infisical. Alleen dit bestand hoeft dan te wijzigen.
"""
import keyring

SERVICE = "mrng-mcp-poc"
MODES = ("inrichting", "controle")


def _naam(klant: str, mode: str) -> str:
    if mode not in MODES:
        raise ValueError(f"Onbekende mode '{mode}', kies uit {MODES}")
    return f"{klant}:{mode}"


def get_key(klant: str, mode: str) -> str:
    key = keyring.get_password(SERVICE, _naam(klant, mode))
    if not key:
        raise LookupError(f"Geen sleutel in de kluis voor {klant} ({mode})")
    return key


def has_key(klant: str, mode: str) -> bool:
    return bool(keyring.get_password(SERVICE, _naam(klant, mode)))


def set_key(klant: str, mode: str, key: str) -> None:
    keyring.set_password(SERVICE, _naam(klant, mode), key)


def delete_key(klant: str, mode: str) -> None:
    keyring.delete_password(SERVICE, _naam(klant, mode))
