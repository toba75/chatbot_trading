from __future__ import annotations

from pathlib import Path


def test_validate_ui_action_execution_progress_unit() -> None:
    repository_root = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "pyproject.toml").is_file()
    )
    import sys

    sys.path.insert(0, str(repository_root))

    from app.contracts.document_public_statuses import PublicActionPhase
    from app.platform.ui_corpus import render_document_inspection
    import app.platform.ui_local_stack as ui_local_stack
    from app.source_processing.application.document_queries import DocumentActionProgressView
    from app.source_processing.domain.document_processing_run import (
        DocumentProcessingRun,
        DocumentProcessingRunStatus,
        PageManifest,
        PageManifestEntry,
        PageManifestEntryState,
        PageNumber,
        ProcessingRunId,
    )
    from app.source_processing.domain.source_document import (
        BibliographicMetadata,
        DocumentId,
        OriginalStorageRef,
        SourceDocument,
        SourceFingerprint,
    )

    content = b"%PDF-1.7\nprogression\n%%EOF\n"
    fingerprint = SourceFingerprint.from_content(content)
    document_id = DocumentId.from_fingerprint(fingerprint)
    source = SourceDocument.register_original(
        document_id=document_id,
        fingerprint=fingerprint,
        original_storage_ref=OriginalStorageRef.from_value(
            f"artifact:source_processing.original_sources/{document_id.value}/{fingerprint.value}.pdf"
        ),
        metadata=BibliographicMetadata(
            title="Progression réelle",
            authors=("Équipe OSTrading",),
            publication_year=2026,
            edition="1",
        ),
    )
    queued = DocumentProcessingRun.start(
        processing_run_id=ProcessingRunId.from_value("RUN-M013-UI-PROGRESS"),
        source_document=source,
        page_manifest=PageManifest.from_entries(
            source_page_count=2,
            entries=(
                PageManifestEntry(PageNumber.from_value(1), PageManifestEntryState.PRESENT),
                PageManifestEntry(PageNumber.from_value(2), PageManifestEntryState.PRESENT),
            ),
        ),
    )

    # Given un diagnostic persisté dans l'outbox mais non encore consommé.
    # When le worker réel prend son travail.
    # Then l'état métier et la progression publique passent explicitement de
    # QUEUED à RUNNING sans simuler des pages diagnostiquées.
    running = queued.begin_diagnosis()
    assert running.status is DocumentProcessingRunStatus.DIAGNOSING
    progress = DocumentActionProgressView.from_processing_run(running)
    assert progress.phase is PublicActionPhase.RUNNING
    assert (progress.completed_units, progress.total_units) == (0, 2)
    assert callable(ui_local_stack._start_local_document_worker)

    html = render_document_inspection(
        title="Diagnostic",
        response=type(
            "Response",
            (),
            {
                "status_code": 200,
                "payload": {
                    "document_id": document_id.value,
                    "diagnostic_status": "DIAGNOSING",
                    "source_page_count": 2,
                    "diagnosed_page_count": 0,
                    "manual_review_reason": None,
                    "failure_error_code": None,
                    "manifest": [
                        {"page_number": 1, "manifest_status": "PRESENT"},
                        {"page_number": 2, "manifest_status": "PRESENT"},
                    ],
                    "pages": [
                        {"page_number": 1, "manifest_status": "PRESENT", "diagnostic": None, "route": None},
                        {"page_number": 2, "manifest_status": "PRESENT", "diagnostic": None, "route": None},
                    ],
                },
            },
        )(),
        action_progress=progress,
    )
    assert "RUNNING" in html
    assert "0 / 2" in html
    assert 'http-equiv="refresh"' in html
