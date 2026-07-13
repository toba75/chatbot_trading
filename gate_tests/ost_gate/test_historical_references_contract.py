from __future__ import annotations

from pathlib import Path

from ost_gate.historical_references import validate_historical_references


def test_historical_references_are_closed_and_immutable() -> None:
    validate_historical_references(Path(__file__).resolve().parents[2])
