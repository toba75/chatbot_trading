"""Tests unitaires du client UI du read-model documentaire."""

from __future__ import annotations

import json

import pytest

from app.platform.ui_document_api import (
    UiDocumentApiClient,
    UiDocumentApiResponse,
)


class CorpusTransport:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls: list[tuple[str, str]] = []

    def request(self, *, method: str, path: str, body, content_type):
        self.calls.append((method, path))
        return UiDocumentApiResponse(
            status_code=200,
            content_type="application/json",
            body=json.dumps(self.payload).encode("utf-8"),
        )


def _public_document(**overrides) -> dict[str, object]:
    document: dict[str, object] = {
        "document_id": "DOC-M013-API-0001",
        "title": "Trading on Momentum",
        "authors": ["Ken Wolff"],
        "publication_year": 2002,
        "edition": None,
        "metadata_status": "EXTRACTED",
        "document_status": "REGISTERED",
        "diagnostic_status": "ROUTE_PLANNED",
        "conversion_status": "CANONICAL_ACCEPTED",
        "canonical_version_id": "CANON-M013-API-0001",
        "projection_status": "SEARCHABLE",
        "manual_review_reason": None,
        "failure_error_code": None,
        "conversion_action_available": False,
        "projection_action_available": False,
    }
    document.update(overrides)
    return document


def _client_transporte_les_metadonnees_extraites() -> None:
    transport = CorpusTransport(
        {"documents": [_public_document()], "next_cursor": None}
    )
    state = UiDocumentApiClient(transport=transport).build_corpus_state(
        active_selected_document_ids=("DOC-M013-API-0001",)
    )

    assert transport.calls == [("GET", "/v1/documents?limit=100")]
    assert len(state.documents) == 1
    document = state.documents[0]
    assert document.title == "Trading on Momentum"
    assert document.authors == ("Ken Wolff",)
    assert document.publication_year == 2002
    assert document.metadata_status == "EXTRACTED"
    assert document.selectable_for_conversation is True


def _client_preserve_un_document_pending_non_selectionnable() -> None:
    pending = _public_document(
        title=None,
        authors=None,
        publication_year=None,
        edition=None,
        metadata_status="PENDING",
        conversion_status="CONVERSION_NOT_REQUESTED",
        canonical_version_id=None,
        projection_status="PROJECTION_NOT_REQUESTED",
    )
    transport = CorpusTransport({"documents": [pending], "next_cursor": None})
    document = UiDocumentApiClient(transport=transport).build_corpus_state(
        active_selected_document_ids=()
    ).documents[0]
    assert document.metadata_status == "PENDING"
    assert document.selectable_for_conversation is False


def _client_refuse_un_read_model_bibliographique_incoherent() -> None:
    transport = CorpusTransport(
        {
            "documents": [
                _public_document(metadata_status="PENDING")
            ],
            "next_cursor": None,
        }
    )
    with pytest.raises(ValueError, match="page de corpus publique incompatible"):
        UiDocumentApiClient(transport=transport).build_corpus_state(
            active_selected_document_ids=()
        )


def test_validate_ui_document_api_client_unit() -> None:
    _client_transporte_les_metadonnees_extraites()
    _client_preserve_un_document_pending_non_selectionnable()
    _client_refuse_un_read_model_bibliographique_incoherent()
