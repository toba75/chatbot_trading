"""Tests unitaires du validateur de spécification M14-local-pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest

from ost_gate.m014_local_pipeline import (
    LocalPipelineSpecificationError,
    validate_local_pipeline_specification,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
SPECIFICATION_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "specs"
    / "m014_local_pipeline_documentaire_distribue.md"
)


def _specification() -> str:
    return SPECIFICATION_PATH.read_text(encoding="utf-8")


def _replace_required(source: str, old: str, new: str) -> str:
    assert old in source
    return source.replace(old, new, 1)


def _assert_error(code: str, specification: str) -> None:
    with pytest.raises(LocalPipelineSpecificationError, match=code):
        validate_local_pipeline_specification(specification)


def test_validate_local_pipeline_specification_unit() -> None:
    specification = _specification()
    validate_local_pipeline_specification(specification)

    _assert_error(
        "M014_LOCAL_PIPELINE_OWNER_REQUIRED",
        _replace_required(
            specification,
            "Source Processing **DOIT** rester propriétaire du manifeste, des "
            "résultats de pages, de la progression et de la version canonique.",
            "La plateforme possède toutes les écritures du pipeline.",
        ),
    )
    _assert_error(
        "M014_LOCAL_PIPELINE_MANIFEST_TOTAL_IMMUTABLE",
        _replace_required(
            specification,
            "Le manifeste et son `total` **DOIVENT** être figés avant le fan-out "
            "et ne changent plus pendant le traitement.",
            "Le manifeste et son `total` peuvent être recalculés pendant le traitement.",
        ),
    )
    _assert_error(
        "M014_LOCAL_PIPELINE_LOCAL_TRANSACTIONS_REQUIRED",
        _replace_required(
            specification,
            "Aucune transaction forte **NE DOIT** lire ou écrire simultanément "
            "une donnée SP et une table `platform`.",
            "Une transaction forte écrit simultanément SP et `platform`.",
        ),
    )
    _assert_error(
        "M014_LOCAL_PIPELINE_PERSISTED_PROGRESS_REQUIRED",
        _replace_required(
            specification,
            "La progression publique **DOIT** provenir exclusivement des "
            "résultats SP persistés ; aucun log, état local ou compteur "
            "synthétique ne peut la produire.",
            "La progression publique est déduite du compteur local du worker.",
        ),
    )
    _assert_error(
        "M014_LOCAL_PIPELINE_ASSEMBLY_COMPLETENESS_REQUIRED",
        _replace_required(
            specification,
            "L’assemblage **NE DOIT PAS** commencer avant la complétude du "
            "manifeste et l’absence d’erreur terminale.",
            "L’assemblage peut commencer dès le premier résultat de page.",
        ),
    )
    _assert_error(
        "M014_LOCAL_PIPELINE_PUBLICATION_BEFORE_PROJECTION_REQUIRED",
        _replace_required(
            specification,
            "KA **NE DOIT PAS** projeter avant `CanonicalSourcePublished` et ne "
            "lit que la version canonique publiée complète.",
            "KA peut projeter les pages avant la publication canonique.",
        ),
    )
    _assert_error(
        "M014_LOCAL_PIPELINE_ROUTE_FALLBACK_FORBIDDEN",
        _replace_required(
            specification,
            "Un worker **NE DOIT PAS** modifier la route M-003, choisir une "
            "route alternative ou basculer Granite sur CPU.",
            "Un worker peut choisir une route alternative et basculer sur CPU.",
        ),
    )
    _assert_error(
        "M014_LOCAL_PIPELINE_ENVIRONMENT_IDENTITY_REQUIRED",
        _replace_required(
            specification,
            "Chaque échange **DOIT** porter `environment`, `deployment_id` et "
            "`configuration_hash` explicites et concordants avec le traitement.",
            "Chaque échange peut déduire l’environnement depuis la file.",
        ),
    )
    _assert_error(
        "M014_LOCAL_PIPELINE_ORCHESTRATION_VERSION_REQUIRED",
        _replace_required(
            specification,
            "Le discriminateur fermé du job parent est `orchestration_version`.",
            "Le parcours est choisi depuis l’état local du worker.",
        ),
    )
