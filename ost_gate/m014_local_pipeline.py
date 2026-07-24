"""Validation exécutable de la spécification M14-local-pipeline."""

from __future__ import annotations

from collections.abc import Sequence


class LocalPipelineSpecificationError(ValueError):
    """Signale une règle absente ou ambiguë du pipeline local distribué."""


def validate_local_pipeline_specification(specification_text: str) -> None:
    """Valide les responsabilités et l'ordre causal du pipeline documentaire."""

    if not isinstance(specification_text, str) or not specification_text.strip():
        raise LocalPipelineSpecificationError(
            "M014_LOCAL_PIPELINE_SPECIFICATION_INVALID"
        )

    specification = _normalized_markdown(specification_text)
    _require_markers(
        specification,
        (
            "# M14-local-pipeline - Pipeline documentaire local distribué",
            "## Mission",
            "## Contexte DDD",
            "## Langage ubiquitaire",
            "## Invariants non négociables",
            "## Machines d’états",
            "## Ports propriétaires",
            "## Enveloppes intercontextes",
            "## Erreurs stables",
        ),
        "M014_LOCAL_PIPELINE_STRUCTURE_REQUIRED",
    )
    _require_markers(
        specification,
        (
            "Source Processing **DOIT** rester propriétaire du manifeste, des "
            "résultats de pages, de la progression et de la version canonique.",
            "`platform` **DOIT** rester propriétaire de la file, des claims, du "
            "quota Granite et des enveloppes de complétion.",
            "Knowledge Access **DOIT** rester propriétaire de "
            "`KnowledgeProjection` et de Qdrant comme projection régénérable.",
        ),
        "M014_LOCAL_PIPELINE_OWNER_REQUIRED",
    )
    _require_markers(
        specification,
        (
            "Le manifeste et son `total` **DOIVENT** être figés avant le fan-out "
            "et ne changent plus pendant le traitement.",
            "Une page `SKIP_EMPTY` **DOIT** être terminale et compter exactement "
            "une unité sans créer de job `CONVERT_PAGE`.",
        ),
        "M014_LOCAL_PIPELINE_MANIFEST_TOTAL_IMMUTABLE",
    )
    _require_markers(
        specification,
        (
            "Aucune transaction forte **NE DOIT** lire ou écrire simultanément "
            "une donnée SP et une table `platform`.",
            "transaction SP productrice",
            "transaction `platform` consommatrice",
            "transaction SP d’acquittement",
            "transaction `platform` d’acquittement",
        ),
        "M014_LOCAL_PIPELINE_LOCAL_TRANSACTIONS_REQUIRED",
    )
    _require_markers(
        specification,
        (
            "La progression publique **DOIT** provenir exclusivement des "
            "résultats SP persistés ; aucun log, état local ou compteur "
            "synthétique ne peut la produire.",
            "phase, unités réalisées, total et erreur terminale éventuelle",
        ),
        "M014_LOCAL_PIPELINE_PERSISTED_PROGRESS_REQUIRED",
    )
    _require_markers(
        specification,
        (
            "L’assemblage **NE DOIT PAS** commencer avant la complétude du "
            "manifeste et l’absence d’erreur terminale.",
            "L’assembleur **NE DOIT** réexécuter aucun modèle.",
            "une seule version canonique immuable",
        ),
        "M014_LOCAL_PIPELINE_ASSEMBLY_COMPLETENESS_REQUIRED",
    )
    _require_markers(
        specification,
        (
            "KA **NE DOIT PAS** projeter avant `CanonicalSourcePublished` et ne "
            "lit que la version canonique publiée complète.",
            "`PROJECT_DOCUMENT` reste au niveau document",
            "Qdrant du même environnement",
        ),
        "M014_LOCAL_PIPELINE_PUBLICATION_BEFORE_PROJECTION_REQUIRED",
    )
    _require_markers(
        specification,
        (
            "Un worker **NE DOIT PAS** modifier la route M-003, choisir une "
            "route alternative ou basculer Granite sur CPU.",
            "aucune activation implicite",
        ),
        "M014_LOCAL_PIPELINE_ROUTE_FALLBACK_FORBIDDEN",
    )
    _require_markers(
        specification,
        (
            "Chaque échange **DOIT** porter `environment`, `deployment_id` et "
            "`configuration_hash` explicites et concordants avec le traitement.",
            "`CONTRACT_ENVIRONMENT_MISMATCH`",
            "`WORKER_ENVIRONMENT_MISMATCH`",
            "`PROJECTION_ENVIRONMENT_MISMATCH`",
        ),
        "M014_LOCAL_PIPELINE_ENVIRONMENT_IDENTITY_REQUIRED",
    )
    _require_markers(
        specification,
        (
            "`CONVERT_DOCUMENT`",
            "`CONVERT_PAGE`",
            "Résultat de page",
            "`SKIP_EMPTY`",
            "Enveloppe de complétion",
            "Assemblage canonique",
            "`CanonicalSourcePublished`",
            "`PROJECT_DOCUMENT`",
            "Rejeu idempotent",
        ),
        "M014_LOCAL_PIPELINE_LANGUAGE_REQUIRED",
    )
    _require_markers(
        specification,
        (
            "`PageResultStatus`",
            "`SUCCEEDED`",
            "`FAILED`",
            "`SKIP_EMPTY`",
            "`PUBLISHED`",
            "`REQUESTED`",
            "`SEARCHABLE`",
        ),
        "M014_LOCAL_PIPELINE_STATE_MACHINES_REQUIRED",
    )
    _require_markers(
        specification,
        (
            "`ClaimCompatibleTechnicalJob`",
            "`CompletePageExecution`",
            "`CanonicalSourceReader`",
            "`KnowledgeProjectionRepository`",
            "`VectorIndex`",
        ),
        "M014_LOCAL_PIPELINE_PORTS_REQUIRED",
    )
    _require_markers(
        specification,
        (
            "`claim_generation`",
            "`claim_token`",
            "`slot_generation`",
            "`slot_token`",
            "redélivrance identique",
            "divergence",
        ),
        "M014_LOCAL_PIPELINE_COMPLETION_ENVELOPE_REQUIRED",
    )
    _require_markers(
        specification,
        (
            "`JOB_LEASE_LOST`",
            "`PAGE_RESULT_REPLAY_DIVERGENCE`",
            "`PAGE_MANIFEST_INCOMPLETE`",
            "`PAGE_RESULT_TERMINAL_FAILURE`",
            "`CANONICAL_ASSEMBLY_REPLAY_DIVERGENCE`",
            "`CANONICAL_SOURCE_NOT_PUBLISHED`",
        ),
        "M014_LOCAL_PIPELINE_ERRORS_REQUIRED",
    )
    _require_markers(
        specification,
        (
            "## DIST-003 - Reprise après perte d’un worker",
            "## DIST-004 - Étanchéité des environnements",
            "## DIST-005 - Publication canonique atomique",
            "Given",
            "When",
            "Then",
        ),
        "M014_LOCAL_PIPELINE_SCENARIOS_REQUIRED",
    )
    _require_markers(
        specification,
        (
            "ADR-024",
            "ADR-025",
            "ADR-052",
            "DDD-ADR-008",
            "## Ordre des transactions ADR-024",
            "## Migration, activation et rollback explicites",
            "arrête explicitement la création de nouveaux jobs de pages",
            "ne supprime ni table ni colonne",
        ),
        "M014_LOCAL_PIPELINE_ADR_ROLLBACK_REQUIRED",
    )
    _require_markers(
        specification,
        (
            "T-009",
            "T-010",
            "T-011",
            "M14-local-qualification",
            "campagne de cent PDF",
        ),
        "M014_LOCAL_PIPELINE_EXCLUSIONS_REQUIRED",
    )
    _require_markers(
        specification,
        (
            "0003_eclater_conversion_en_jobs_pages.md",
            "0004_executer_persister_page_fenced.md",
            "0005_assembler_publier_document_canonique.md",
            "0006_projeter_document_publie_localement.md",
        ),
        "M014_LOCAL_PIPELINE_TASK_TRACEABILITY_REQUIRED",
    )


def _normalized_markdown(value: str) -> str:
    return " ".join(value.split())


def _require_markers(value: str, markers: Sequence[str], code: str) -> None:
    if any(_normalized_markdown(marker) not in value for marker in markers):
        raise LocalPipelineSpecificationError(code)


__all__ = [
    "LocalPipelineSpecificationError",
    "validate_local_pipeline_specification",
]
