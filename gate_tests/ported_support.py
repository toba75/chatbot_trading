"""Contrats de parité des preuves historiques portées."""

from __future__ import annotations

import json
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_PARITY_PATH = _REPOSITORY_ROOT / "docs" / "governance" / "historical_python_parity.json"


def assert_native_parity(python_path: str, classification: str) -> None:
    """Empêche une preuve native de disparaître pendant le port progressif."""

    records = json.loads(_PARITY_PATH.read_text(encoding="utf-8"))["records"]
    matches = [record for record in records if record["python_path"] == python_path]
    if len(matches) != 1:
        raise AssertionError(f"PARITY_RECORD_REQUIRED:{python_path}")
    record = matches[0]
    if record["classification"] != classification:
        raise AssertionError(f"PARITY_CLASSIFICATION_MISMATCH:{python_path}")
    if not record["behavior"]:
        raise AssertionError(f"PARITY_BEHAVIOR_REQUIRED:{python_path}")
    if not (_REPOSITORY_ROOT / python_path).is_file():
        raise AssertionError(f"PARITY_TARGET_REQUIRED:{python_path}")
