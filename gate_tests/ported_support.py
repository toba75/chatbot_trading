"""Contrats de parité des preuves PowerShell portées."""

from __future__ import annotations

import json
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_PARITY_PATH = _REPOSITORY_ROOT / "docs" / "governance" / "powershell_python_parity.json"


def assert_native_parity(legacy_path: str, python_path: str, classification: str) -> None:
    """Empêche une preuve native de disparaître pendant le port progressif."""

    records = json.loads(_PARITY_PATH.read_text(encoding="utf-8"))["records"]
    matches = [record for record in records if record["legacy_path"] == legacy_path]
    if len(matches) != 1:
        raise AssertionError(f"PARITY_RECORD_REQUIRED:{legacy_path}")
    record = matches[0]
    if record["python_path"] != python_path:
        raise AssertionError(f"PARITY_TARGET_MISMATCH:{legacy_path}")
    if record["classification"] != classification:
        raise AssertionError(f"PARITY_CLASSIFICATION_MISMATCH:{legacy_path}")
    if not record["behavior"]:
        raise AssertionError(f"PARITY_BEHAVIOR_REQUIRED:{legacy_path}")
    if not (_REPOSITORY_ROOT / python_path).is_file():
        raise AssertionError(f"PARITY_TARGET_REQUIRED:{python_path}")
