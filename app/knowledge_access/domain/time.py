"""Validation temporelle interne au bounded context KA."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def ensure_utc_instant(value: Any, field_name: str) -> str:
    """Valide un instant UTC canonique sans dépendre des helpers privés de contrats."""

    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ValueError(f"{field_name} invalide") from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise ValueError(f"{field_name} invalide")
    return value


__all__ = ["ensure_utc_instant"]
