"""Mapping von CAPsMAN-AP-Identitaeten auf Stockwerke fuer die Visualisierung.

Wird aus einer JSON-Datei geladen (Pfad: settings.floors_config_path), damit
jede Installation ihre eigene Stockwerk-/AP-Struktur konfigurieren kann, ohne
Code anzufassen. Format siehe config/floors.example.json.
"""

import json
from pathlib import Path

from app.config import settings


def _load_floor_config() -> tuple[list[dict], dict[str, dict]]:
    path = Path(settings.floors_config_path)
    if not path.is_file():
        raise FileNotFoundError(
            f"Floor-Config nicht gefunden: '{path}'. "
            f"FLOORS_CONFIG_PATH in .env setzen oder config/floors.example.json "
            f"nach '{path}' kopieren und anpassen."
        )
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    floors = sorted(data["floors"], key=lambda f: f["order"])
    access_points = data["access_points"]
    return floors, access_points


FLOORS, AP_TO_FLOOR = _load_floor_config()

# Sortiert nach Laenge absteigend, damit z.B. "ap-garage" vor einem eventuellen
# kuerzeren Praefix greift, falls Namen sich einmal ueberschneiden sollten.
_AP_IDENTITIES = sorted(AP_TO_FLOOR.keys(), key=len, reverse=True)


def resolve_ap_identity(interface_name: str) -> str | None:
    """Extrahiert die AP-Identitaet aus einem Interface-Namen wie 'ap-ground_2GHz2'."""
    for identity in _AP_IDENTITIES:
        if interface_name == identity or interface_name.startswith(identity + "_"):
            return identity
    return None
