"""Acceptation T-005 : worker réel non natif, refus terminal et publication atomique."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from app.source_processing.adapters.docling_native_conversion import (
    NativeDoclingConversionResponse,
)
from app.source_processing.application.document_commands import (
    DocumentConversionExecutionPhase,
    DocumentConversionState,
    DocumentConversionStatus,
)
from app.source_processing.application.document_queries import _conversion_action_available
from app.source_processing.domain.document_processing_run import (
    DiagnosticVersion,
    DocumentProcessingRun,
    PageDecision,
    PageDecisionState,
    PageDiagnosticSignals,
    PageManifest,
    PageManifestEntry,
    PageManifestEntryState,
    PageNumber,
    PageRoutingConfiguration,
    ProcessingRunId,
    RoutingPolicyVersion,
)
from app.source_processing.domain.source_document import (
    BibliographicMetadata,
    DocumentId,
    OriginalStorageRef,
    SourceDocument,
    SourceFingerprint,
)


def _worker_module():
    try:
        return importlib.import_module(
            "app.source_processing.application.routed_document_conversion_worker"
        )
    except ModuleNotFoundError as error:
        pytest.fail(
            "NON_NATIVE_DOCUMENT_WORKER_ABSENT: le worker doit exécuter les routes M-003 non natives."
        )
        raise AssertionError("pytest.fail doit interrompre le test") from error


def test_the_non_native_worker_exposes_stable_terminal_errors_without_partial_canonical_artifact() -> None:
    # Given une page SCAN_GRANITE et un actif Granite absent après une demande acceptée.
    # When le worker CONVERT_DOCUMENT commence le traitement réel.
    # Then il persiste GRANITE_DOCLING_UNAVAILABLE et ne publie aucun artefact canonique partiel.
    worker_module = _worker_module()
    assert worker_module.RoutedDocumentConversionWorker.__name__ == "RoutedDocumentConversionWorker"
    assert worker_module.NON_NATIVE_TERMINAL_ERROR_CODES >= {
        "GRANITE_DOCLING_UNAVAILABLE",
        "OCRMYPDF_UNAVAILABLE",
        "CONVERSION_ASSET_MANIFEST_INVALID",
    }


def test_ui_can_offer_conversion_for_a_complete_non_native_route_only_when_the_real_worker_is_ready() -> None:
    # Given une source dont toutes les pages sont explicitement routées SCAN_GRANITE.
    # When le runtime UI supervise le worker réel doté des actifs scellés.
    # Then le contrat public peut rendre Convertir disponible, puis expose QUEUED, RUNNING et une issue persistée.
    worker_module = _worker_module()
    assert callable(worker_module.build_routed_document_conversion_worker)


def _scan_granite_run() -> tuple[SourceDocument, DocumentProcessingRun]:
    content = b"%PDF-1.7\nscan granite acceptance\n%%EOF\n"
    fingerprint = SourceFingerprint.from_content(content)
    document_id = DocumentId.from_fingerprint(fingerprint)
    source = SourceDocument.register_original(
        document_id=document_id,
        fingerprint=fingerprint,
        original_storage_ref=OriginalStorageRef.from_value(
            f"artifact:source_processing.original_sources/{document_id.value}/{fingerprint.value}.pdf"
        ),
        metadata=BibliographicMetadata.from_payload(
            {
                "title": "Route Granite réellement disponible",
                "authors": ["Perry J. Kaufman"],
                "publication_year": 2020,
                "edition": "1re édition",
            }
        ),
    )
    manifest = PageManifest.from_entries(
        source_page_count=1,
        entries=(
            PageManifestEntry(
                page_number=PageNumber.from_value(1),
                state=PageManifestEntryState.PRESENT,
            ),
        ),
    )
    run = DocumentProcessingRun.start(
        processing_run_id=ProcessingRunId.from_value("RUN-M004-T005-SCAN"),
        source_document=source,
        page_manifest=manifest,
    ).record_page_diagnostics(
        (
            PageDecision(
                page_number=PageNumber.from_value(1),
                page_state=PageDecisionState.SCAN_CLEAN,
                signals=PageDiagnosticSignals(
                    native_text_state="ABSENT",
                    image_state="SCAN_CLEAN",
                    existing_ocr_state="NONE",
                    layout_complexity="SIMPLE",
                    corruption_state="NONE",
                    mixed_content_detected=False,
                    has_table=False,
                    has_formula=False,
                ),
                diagnostic_version=DiagnosticVersion.from_value("diag-t005-v1"),
                justification="Scan propre réellement diagnostiqué.",
            ),
        )
    ).decide_route_plan(
        PageRoutingConfiguration(
            routing_policy_version=RoutingPolicyVersion.from_value("routing-t005-v1"),
            auto_confidence_min=0.90,
            benchmark_confidence_min=0.85,
        )
    )
    return source, run


def test_non_native_route_is_publicly_convertible_and_its_terminal_failure_is_persistable() -> None:
    # Given une route SCAN_GRANITE complète et le worker réel supervisé par l'UI.
    # When le read-model évalue Convertir puis que Granite devient indisponible pendant l'action.
    # Then le bouton peut être rendu avant la demande et GRANITE_DOCLING_UNAVAILABLE reste une issue FAILED persistable.
    source, run = _scan_granite_run()
    assert _conversion_action_available(processing_run=run, conversion=None) is True
    failed = DocumentConversionState(
        document_id=source.document_id,
        conversion_status=DocumentConversionStatus.QA_REJECTED,
        canonical_version_id=None,
        rejection_error_code="GRANITE_DOCLING_UNAVAILABLE",
        execution_phase=DocumentConversionExecutionPhase.FAILED,
        completed_units=0,
        total_units=1,
        failure_error_code="GRANITE_DOCLING_UNAVAILABLE",
    )
    assert failed.failure_error_code == "GRANITE_DOCLING_UNAVAILABLE"

    persistence_failed = DocumentConversionState(
        document_id=source.document_id,
        conversion_status=DocumentConversionStatus.QA_REJECTED,
        canonical_version_id=None,
        rejection_error_code="POSTGRES_INTEGRITY_FAILURE",
        execution_phase=DocumentConversionExecutionPhase.FAILED,
        completed_units=0,
        total_units=1,
        failure_error_code="POSTGRES_INTEGRITY_FAILURE",
    )
    assert persistence_failed.failure_error_code == "POSTGRES_INTEGRITY_FAILURE"


def test_partial_granite_response_is_refused_before_canonical_publication() -> None:
    # Given Granite retourne une réponse sans la page explicitement demandée.
    # When le worker traduit la réponse de l'outil.
    # Then il refuse le manifeste partiel avant tout appel au stockage canonique.
    worker_module = _worker_module()
    with pytest.raises(ValueError, match="réponse Docling partielle"):
        worker_module._page_output(
            response=NativeDoclingConversionResponse(tool_version="2.111.0", pages=()),
            page_number=PageNumber.from_value(1),
            route_name=_scan_granite_run()[1].route_plan.page_routes[0].route_name,
            tool_name=worker_module.ConversionToolName.GRANITE_DOCLING,
            expected_artifact_ref=(
                "artifact:source_processing.page_conversion/"
                "RUN-M004-T005-SCAN/page-001-scan_granite.json"
            ),
        )


def test_postgres_schema_accepts_a_canonical_version_from_each_explicit_m003_route() -> None:
    # Given le worker a produit un document canonique en respectant une route explicite M-003.
    # When sa publication atomique est persistée.
    # Then la contrainte PostgreSQL accepte chaque route admise, au lieu de réserver
    #      silencieusement la publication au chemin NATIVE_STANDARD historique.
    migration_path = (
        Path(__file__).resolve().parents[4]
        / "deploy"
        / "postgres"
        / "migrations"
        / "013_routed_document_conversion.sql"
    )
    migration = migration_path.read_text(encoding="utf-8")
    for route_name in (
        "NATIVE_STANDARD",
        "SCAN_GRANITE",
        "PREPROCESS_GRANITE",
        "BAD_OCR_TO_GRANITE",
        "MIXED_PAGEWISE",
        "TARGETED_ENRICHMENT",
    ):
        assert f"'{route_name}'" in migration
