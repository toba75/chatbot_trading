"""Tests unitaires du validateur de la décision ADR-052."""

from __future__ import annotations

from pathlib import Path

import pytest

from ost_gate.m014_distribution_core import (
    DistributionDecisionError,
    validate_distribution_decision,
)


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


def _documents() -> tuple[str, str, bytes]:
    return (
        ADR_052_PATH.read_text(encoding="utf-8"),
        ADR_INDEX_PATH.read_text(encoding="utf-8"),
        ADR_051_PATH.read_bytes(),
    )


def _replace_required(source: str, old: str, new: str) -> str:
    assert old in source
    return source.replace(old, new, 1)


def _assert_error(
    code: str,
    *,
    adr_text: str | None = None,
    index_text: str | None = None,
    adr_051_bytes: bytes | None = None,
) -> None:
    valid_adr, valid_index, valid_adr_051 = _documents()
    with pytest.raises(DistributionDecisionError, match=code):
        validate_distribution_decision(
            adr_text=valid_adr if adr_text is None else adr_text,
            index_text=valid_index if index_text is None else index_text,
            adr_051_bytes=valid_adr_051 if adr_051_bytes is None else adr_051_bytes,
        )


def test_validate_distribution_decision_unit() -> None:
    adr_text, index_text, adr_051_bytes = _documents()
    validate_distribution_decision(
        adr_text=adr_text,
        index_text=index_text,
        adr_051_bytes=adr_051_bytes,
    )

    quota_non_borne = _replace_required(
        adr_text,
        "`slot_ordinal IN (1, 2)`",
        "`slot_ordinal > 0`",
    )
    _assert_error("M014_DISTRIBUTION_QUOTA_BOUNDS_REQUIRED", adr_text=quota_non_borne)

    autorite_memoire = _replace_required(
        adr_text,
        "PostgreSQL **DOIT** constituer l’unique autorité du quota.",
        "Un compteur en mémoire **DOIT** constituer l’autorité du quota.",
    )
    _assert_error(
        "M014_DISTRIBUTION_POSTGRES_AUTHORITY_REQUIRED",
        adr_text=autorite_memoire,
    )

    sans_generation = _replace_required(
        adr_text,
        "`slot_generation`, `slot_token`",
        "`slot_token`",
    )
    _assert_error("M014_DISTRIBUTION_FENCING_INCOMPLETE", adr_text=sans_generation)

    sans_token = _replace_required(
        adr_text,
        "`claim_generation`, `claim_token`",
        "`claim_generation`",
    )
    _assert_error("M014_DISTRIBUTION_FENCING_INCOMPLETE", adr_text=sans_token)

    liberation_non_fenced = _replace_required(
        adr_text,
        "Le port `ReleaseGraniteSlot` **DOIT** comparer le même tuple fenced complet",
        "Le port `ReleaseGraniteSlot` **DOIT** libérer par identifiant de slot",
    )
    _assert_error("M014_DISTRIBUTION_RELEASE_FENCING_REQUIRED", adr_text=liberation_non_fenced)

    route_specialisee = _replace_required(
        adr_text,
        "Aucun worker spécialisé Granite,\n  aucune route spécialisée",
        "Un worker spécialisé Granite et\n  une route spécialisée",
    )
    _assert_error("M014_DISTRIBUTION_GENERALIST_WORKERS_REQUIRED", adr_text=route_specialisee)

    file_supplementaire = _replace_required(
        adr_text,
        "aucune file supplémentaire **NE DOIVENT** être\n  créés.",
        "une file supplémentaire **DOIT** être créée.",
    )
    _assert_error("M014_DISTRIBUTION_SINGLE_QUEUE_REQUIRED", adr_text=file_supplementaire)

    hote_distant = _replace_required(
        adr_text,
        "un worker distant et un stockage d’objets réseau\n  **SONT INTERDITS**",
        "un worker distant et un stockage d’objets réseau\n  **SONT AUTORISÉS**",
    )
    _assert_error("M014_DISTRIBUTION_LOCAL_ONLY_REQUIRED", adr_text=hote_distant)

    _assert_error(
        "M014_DISTRIBUTION_ADR_051_CHANGED",
        adr_051_bytes=adr_051_bytes + b"\nmutation silencieuse\n",
    )

    sans_consequences_ni_rollback = adr_text.split("## Conséquences", maxsplit=1)[0]
    _assert_error(
        "M014_DISTRIBUTION_CONSEQUENCES_ROLLBACK_REQUIRED",
        adr_text=sans_consequences_ni_rollback,
    )

    _assert_error(
        "M014_DISTRIBUTION_INDEX_INVALID",
        index_text=index_text.replace("Prochaine ADR technique: ADR-053", "ADR-052"),
    )
