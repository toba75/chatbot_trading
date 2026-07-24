"""Acceptation de clôture de la revue M14-local-pipeline.

Given les tranches T-005 à T-008 sont implémentées et revues,
When la documentation, la traçabilité et le schéma de coexistence sont contrôlés,
Then une seule gate globale longue appartient à l'orchestrateur et les contrats
M14 restent explicites, migrables et reliés à leurs preuves ciblées.
"""

from __future__ import annotations

import inspect
from pathlib import Path
import re

from app.source_processing.application.document_commands import (
    DocumentConversionCommandService,
)


ROOT = Path(__file__).resolve().parents[4]
TASKS = ROOT / "docs/tasks/milestone_014-local-pipeline"


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _assert_les_taches_ne_demandent_plus_de_gate_globale_aux_sous_agents() -> None:
    for task_name in (
        "0003_eclater_conversion_en_jobs_pages.md",
        "0004_executer_persister_page_fenced.md",
        "0005_assembler_publier_document_canonique.md",
        "0006_projeter_document_publie_localement.md",
    ):
        task = (TASKS / task_name).read_text(encoding="utf-8")
        assert re.search(r"uv run --locked gate(?:`|\s*[.;])", task) is None, task_name
        assert "tests et scopes ciblés" in task
        assert "orchestrateur" in task

    specification = _read("docs/specs/m014_local_pipeline_documentaire_distribue.md")
    journal = _read("docs/tasks/milestone_014-local-pipeline/journal.md")
    for document in (specification, journal):
        assert "3 600 000 ms" in document
        assert "même cell ID" in document
        assert "exactement une gate globale de clôture" in document
        assert "HEAD" in document and "worktree" in document


def _assert_la_specification_et_la_matrice_decrivent_le_pipeline_livre() -> None:
    specification = _read("docs/specs/m014_local_pipeline_documentaire_distribue.md")
    for marker in (
        "Statut : implémenté et activable explicitement",
        "CANONICAL_ARTIFACT_HASH_MISMATCH",
        "migrations 023 à 028",
        "T-009 à T-011",
        "m014-page-fanout-v1",
    ):
        assert marker in specification

    matrix = _read("docs/traceability/matrix.md")
    for requirement in (
        "REQ-M014-LP-001",
        "REQ-M014-LP-002",
        "REQ-M014-LP-003",
        "REQ-M014-LP-004",
        "REQ-M014-LP-005",
    ):
        assert requirement in matrix
    for migration in (
        "023_document_page_fan_out.sql",
        "024_canonical_assembly_publication.sql",
        "025_local_canonical_projection.sql",
        "026_page_completion_configuration_identity.sql",
        "027_local_projection_review_hardening.sql",
        "028_m014_local_pipeline_compatibility.sql",
    ):
        assert migration in matrix


def _assert_les_runbooks_exposent_activation_rollback_gpu_et_gates_bornees() -> None:
    distribution = _read("docs/runbooks/distribution_locale.md")
    environments = _read("docs/runbooks/environnements_explicites.md")
    for marker in (
        "CONVERT_PAGE",
        "ASSEMBLE_CANONICAL_DOCUMENT",
        "PROJECT_DOCUMENT",
        "nvidia-smi",
        "migration 028",
        "3 600 000 ms",
        "aucune alternative silencieuse",
    ):
        assert marker in distribution
    assert "m014_local_pipeline --live" in environments
    assert "exactement une gate globale de clôture" in environments


def _assert_la_migration_classe_seulement_un_writer_m004_prouve() -> None:
    migration = _read("deploy/postgres/migrations/028_m014_local_pipeline_compatibility.sql")
    assert "classify_m004_inline_orchestration" in migration
    assert "payload ? 'orchestration_version'" in migration
    assert "M014_ORCHESTRATION_VERSION_REQUIRED" in migration
    assert "CREATE TRIGGER" in migration
    assert "DEFAULT 'm004-inline-v1'" not in migration


def _assert_aucun_defaut_python_ne_choisit_le_parcours_de_conversion() -> None:
    parameter = inspect.signature(DocumentConversionCommandService.__init__).parameters[
        "orchestration_version"
    ]
    assert parameter.default is inspect.Parameter.empty


def _assert_l_artefact_attendu_est_compare_a_l_artefact_canonique_publie() -> None:
    assembly = _read("app/source_processing/application/assemble_canonical_document.py")
    assert "CANONICAL_ARTIFACT_REF_MISMATCH" in assembly
    assert "contract.expected_canonical_artifact" in assembly
    assert "published.stored_artifact_ref" in assembly


def test_cloture_revue_m014_local_pipeline() -> None:
    _assert_les_taches_ne_demandent_plus_de_gate_globale_aux_sous_agents()
    _assert_la_specification_et_la_matrice_decrivent_le_pipeline_livre()
    _assert_les_runbooks_exposent_activation_rollback_gpu_et_gates_bornees()
    _assert_la_migration_classe_seulement_un_writer_m004_prouve()
    _assert_aucun_defaut_python_ne_choisit_le_parcours_de_conversion()
    _assert_l_artefact_attendu_est_compare_a_l_artefact_canonique_publie()
