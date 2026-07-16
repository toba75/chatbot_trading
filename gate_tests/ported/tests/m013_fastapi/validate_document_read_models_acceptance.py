"""Acceptation HTTP du read-model documentaire SP après ADR-038."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.source_processing.adapters.query_http import build_document_query_router
from app.source_processing.application.document_queries import DocumentQueryService


class SnapshotRepository:
    def find_document_snapshot(self, document_id):
        return None


class CorpusRepository:
    def list_document_status_rows(self, *, limit: int, after_document_id: str | None):
        assert limit == 101
        assert after_document_id is None
        common = {
            "document_status": "REGISTERED",
            "diagnostic_status": "DIAGNOSTIC_NOT_REQUESTED",
            "conversion_status": "CONVERSION_NOT_REQUESTED",
            "canonical_version_id": None,
            "manual_review_reason": None,
            "failure_error_code": None,
            "conversion_action_available": False,
        }
        return (
            SimpleNamespace(
                document_id="DOC-0000000000000001",
                title=None,
                authors=None,
                publication_year=None,
                edition=None,
                metadata_status="PENDING",
                **common,
            ),
            SimpleNamespace(
                document_id="DOC-0000000000000002",
                title="Document historique",
                authors=("Auteur explicite",),
                publication_year=2026,
                edition="1",
                metadata_status="LEGACY_DECLARED",
                **common,
            ),
        )


def test_validate_document_read_models_acceptance() -> None:
    service = DocumentQueryService(
        document_snapshot_repository=SnapshotRepository(),
        document_corpus_status_repository=CorpusRepository(),
    )
    application = FastAPI()
    application.include_router(build_document_query_router(document_queries=service))

    response = TestClient(application).get("/v1/documents?limit=100")

    assert response.status_code == 200
    payload = response.json()
    assert payload["next_cursor"] is None
    assert len(payload["documents"]) == 2
    pending, legacy = payload["documents"]
    assert pending["metadata_status"] == "PENDING"
    assert pending["title"] is None
    assert pending["authors"] is None
    assert legacy["metadata_status"] == "LEGACY_DECLARED"
    assert legacy["authors"] == ["Auteur explicite"]
    forbidden = {
        "original_storage_ref",
        "processing_run_id",
        "job_id",
        "artifact_ref",
    }
    assert not forbidden.intersection(str(payload))
