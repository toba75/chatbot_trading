"""Acceptation BDD de la décision de distribution locale ADR-052."""

from __future__ import annotations

from pathlib import Path

from ost_gate.m014_distribution_core import validate_distribution_decision


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
ADR_052_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "adr"
    / "ADR-052-distribution-locale-pages-quota-granite-fenced.md"
)
ADR_051_PATH = (
    REPOSITORY_ROOT / "docs" / "adr" / "ADR-051-execution-granite-cuda-stricte.md"
)
ADR_INDEX_PATH = REPOSITORY_ROOT / "docs" / "adr" / "index.md"


def test_adr_052_decide_le_quota_granite_local_fenced() -> None:
    # Given deux workers généralistes détiennent les deux slots Granite locaux.
    assert ADR_052_PATH.is_file(), "M014_DISTRIBUTION_ADR_052_MISSING"

    # When la décision structurante, son index et ADR-051 immuable sont contrôlés.
    validate_distribution_decision(
        adr_text=ADR_052_PATH.read_text(encoding="utf-8"),
        index_text=ADR_INDEX_PATH.read_text(encoding="utf-8"),
        adr_051_bytes=ADR_051_PATH.read_bytes(),
    )

    # Then le troisième job attend et la reprise renouvelle les deux fences.
    decision = ADR_052_PATH.read_text(encoding="utf-8")
    assert "**Given**" in decision
    assert "**When**" in decision
    assert "**Then**" in decision
    assert "DIST-001" in decision and "DIST-002" in decision and "DIST-003" in decision
