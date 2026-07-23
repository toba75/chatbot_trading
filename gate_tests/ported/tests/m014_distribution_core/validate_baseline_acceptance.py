"""Acceptation BDD de la baseline locale M14-distribution-core."""

from __future__ import annotations

import json
from pathlib import Path

from ost_gate.m014_distribution_core import validate_distribution_baseline


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
EVIDENCE_PATH = REPOSITORY_ROOT / "docs" / "evaluation" / "m014" / "distribution_core_baseline.json"
REPORT_PATH = REPOSITORY_ROOT / "docs" / "governance" / "m014_distribution_core_baseline.md"


def test_baseline_locale_reproductible_est_publiee() -> None:
    # Given M-013 est GREEN et la branche contient Granite CUDA ainsi que la limite de 2 Gio.
    assert EVIDENCE_PATH.is_file(), "M014_BASELINE_EVIDENCE_MISSING"

    # When la preuve live de la même page Granite à un puis deux workers est contrôlée.
    payload = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    validate_distribution_baseline(payload)

    # Then les identités, mesures, sorties, mécanismes locaux et exclusions sont publiés.
    report = REPORT_PATH.read_text(encoding="utf-8")
    assert payload["evidence_id"] in report
    assert payload["runtime_identity"]["image_digest"] in report
    assert payload["workload"]["fixture_sha256"] in report
    assert "Given" in report and "When" in report and "Then" in report
    assert "aucune mesure du plan n’est présentée comme une nouvelle mesure" in report
