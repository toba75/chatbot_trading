"""Tests unitaires des query services documentaires SP."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.contracts.technical_jobs import JobEnvironmentIdentity
from app.source_processing.application.document_queries import DocumentQueryService


_ENVIRONMENT_IDENTITY = JobEnvironmentIdentity(
    environment="development",
    deployment_id="ostrading-development-local",
    configuration_hash="a" * 64,
)


class StatusRows:
    def __init__(self, rows: tuple[object, ...]) -> None:
        self.rows = rows
        self.calls: list[tuple[int, str | None]] = []

    def list_document_status_rows(self, *, limit: int, after_document_id: str | None):
        self.calls.append((limit, after_document_id))
        return self.rows


class Snapshots:
    def find_document_snapshot(self, document_id):
        return None


def _row(**overrides):
    values = {
        "document_id": "DOC-0000000000000001",
        "title": "Titre historique",
        "authors": ("Auteur",),
        "publication_year": 2026,
        "edition": "1",
        "metadata_status": "LEGACY_DECLARED",
        "document_status": "REGISTERED",
        "diagnostic_status": "DIAGNOSTIC_NOT_REQUESTED",
        "conversion_status": "CONVERSION_NOT_REQUESTED",
        "canonical_version_id": None,
        "manual_review_reason": None,
        "failure_error_code": None,
        "conversion_action_available": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_validate_document_queries_unit() -> None:
    rows = StatusRows(
        (
            _row(document_id="DOC-0000000000000002"),
            _row(
                title=None,
                authors=None,
                publication_year=None,
                edition=None,
                metadata_status="PENDING",
            ),
        )
    )
    service = DocumentQueryService(
        document_snapshot_repository=Snapshots(),
        document_corpus_status_repository=rows,
        environment_identity=_ENVIRONMENT_IDENTITY,
    )
    page = service.list_documents(limit=2, cursor=None)
    assert rows.calls == [(3, None)]
    assert tuple(item.document_id for item in page.documents) == (
        "DOC-0000000000000001",
        "DOC-0000000000000002",
    )
    pending = page.documents[0]
    assert pending.metadata_status == "PENDING"
    assert pending.title is None
    legacy = page.documents[1]
    assert legacy.authors == ("Auteur",)

    invalid_rows = StatusRows((SimpleNamespace(document_id="DOC-0000000000000001"),))
    invalid_service = DocumentQueryService(
        document_snapshot_repository=Snapshots(),
        document_corpus_status_repository=invalid_rows,
        environment_identity=_ENVIRONMENT_IDENTITY,
    )
    with pytest.raises(TypeError, match="projection légère de corpus invalide"):
        invalid_service.list_documents(limit=1, cursor=None)
