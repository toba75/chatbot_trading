from __future__ import annotations

from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_validate_manual_review_ui_flow_acceptance() -> None:
    repository_root = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "pyproject.toml").is_file()
    )
    sys.path.insert(0, str(repository_root))

    from app.platform.ui_corpus import (
        CorpusPdfDocument,
        CorpusPdfScreenState,
        render_corpus_pdf_screen,
        render_document_inspection,
    )
    from app.platform.ui_document_api import UiDocumentJsonResponse
    from app.source_processing.adapters.http import build_document_command_router

    class UnusedAdapter:
        def handle(self, request):
            raise AssertionError("Commande documentaire inattendue")

        def handle_staged_registration(self, *, original_path, bibliographic_metadata):
            raise AssertionError("Enregistrement inattendu")

    class ManualReviewHandler:
        def __init__(self) -> None:
            self.commands = []

        def resolve_manual_review(self, **command):
            self.commands.append(command)
            return {
                "document_id": command["document_id"],
                "diagnostic_status": "ROUTE_PLANNED",
                "decision": command["decision"],
                "page_number": command["page_number"],
                "route_name": command["route_name"],
            }

    handler = ManualReviewHandler()
    application = FastAPI()
    application.include_router(
        build_document_command_router(
            document_http_adapter=UnusedAdapter(),
            document_conversion_http_adapter=UnusedAdapter(),
            manual_review_handler=handler,
            max_pdf_bytes=1024,
        )
    )
    response = TestClient(application).post(
        "/v1/documents/DOC-M013-MANUAL-REVIEW/manual-review",
        json={
            "decision": "ASSIGN_ROUTE",
            "page_number": 2,
            "route_name": "SCAN_GRANITE",
            "reviewer_id": "maxim",
            "reason": "La page contient une image exploitable.",
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "document_id": "DOC-M013-MANUAL-REVIEW",
        "diagnostic_status": "ROUTE_PLANNED",
        "decision": "ASSIGN_ROUTE",
        "page_number": 2,
        "route_name": "SCAN_GRANITE",
    }
    assert handler.commands[0]["reviewer_id"] == "maxim"

    corpus_html = render_corpus_pdf_screen(
        CorpusPdfScreenState(
            documents=(
                CorpusPdfDocument(
                    document_id="DOC-M013-MANUAL-REVIEW",
                    title=None,
                    authors=None,
                    publication_year=None,
                    edition=None,
                    metadata_status="PENDING",
                    source_status="REGISTERED",
                    diagnostic_status="MANUAL_REVIEW",
                    conversion_status="CONVERSION_NOT_REQUESTED",
                    canonical_version_id=None,
                    projection_status="PROJECTION_NOT_REQUESTED",
                    conversion_action_available=False,
                    selected=False,
                    manual_review_reason="page 2 sans route documentaire admissible",
                ),
            ),
            active_selected_document_ids=(),
            read_model_status="READ_MODEL_READY",
        )
    )
    assert "Examiner la revue" in corpus_html
    assert "/ui/documents/DOC-M013-MANUAL-REVIEW/diagnostic" in corpus_html

    diagnostic_html = render_document_inspection(
        title="Diagnostic",
        response=UiDocumentJsonResponse(
            status_code=200,
            payload={
                "document_id": "DOC-M013-MANUAL-REVIEW",
                "diagnostic_status": "MANUAL_REVIEW",
                "source_page_count": 2,
                "diagnosed_page_count": 2,
                "manual_review_reason": "page 2 sans route documentaire admissible",
                "failure_error_code": None,
                "pages": [
                    {
                        "page_number": 2,
                        "manifest_status": "PRESENT",
                        "diagnostic": {
                            "page_state": "UNSUPPORTED_OR_CORRUPT",
                            "manual_review_required": True,
                            "manual_review_resolution": None,
                        },
                        "route": None,
                    }
                ],
            },
        ),
        action_progress={
            "action_name": "DIAGNOSE",
            "phase": "SUCCEEDED",
            "completed_units": 2,
            "total_units": 2,
            "failure_error_code": None,
        },
    )
    for marker in (
        "CONFIRM_EMPTY",
        "ASSIGN_ROUTE",
        "REJECT_DOCUMENT",
        "reviewer_id",
        "reason",
        "/v1/documents/DOC-M013-MANUAL-REVIEW/manual-review",
    ):
        assert marker in diagnostic_html

    conversion_html = render_document_inspection(
        title="Conversion",
        response=UiDocumentJsonResponse(
            status_code=200,
            payload={
                "document_id": "DOC-M013-MANUAL-REVIEW",
                "conversion_status": "CANONICAL_ACCEPTED",
                "qa_rejection_error_code": None,
                "canonical_version_id": "CVER-M013-MANUAL-REVIEW",
                "converted_page_count": 1,
                "skipped_empty_page_count": 1,
            },
        ),
        action_progress={
            "action_name": "CONVERT_DOCUMENT",
            "phase": "SUCCEEDED",
            "completed_units": 2,
            "total_units": 2,
            "failure_error_code": None,
        },
    )
    assert "Pages converties : 1" in conversion_html
    assert "Pages vides ignorées : 1" in conversion_html
