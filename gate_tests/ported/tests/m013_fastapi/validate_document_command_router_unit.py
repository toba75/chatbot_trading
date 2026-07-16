"""Tests unitaires du routeur public d'admission documentaire."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.source_processing.adapters.document_http import HttpResponse
from app.source_processing.adapters.http import build_document_command_router


class RecordingDocumentAdapter:
    def __init__(self) -> None:
        self.calls: list[tuple[bytes, object]] = []

    def handle(self, request):
        raise AssertionError("Le chemin non streamé ne doit pas être utilisé.")

    def handle_staged_registration(
        self,
        *,
        original_path: Path,
        bibliographic_metadata,
    ) -> HttpResponse:
        self.calls.append((original_path.read_bytes(), bibliographic_metadata))
        return HttpResponse(
            status_code=201,
            body={
                "document_id": "DOC-1111111111111111",
                "document_status": "REGISTERED",
            },
        )


class ForbiddenConversionAdapter:
    def handle(self, request):
        raise AssertionError("La conversion ne doit pas être appelée.")


def _client(adapter: RecordingDocumentAdapter, *, max_pdf_bytes: int = 64) -> TestClient:
    application = FastAPI()
    application.include_router(
        build_document_command_router(
            document_http_adapter=adapter,
            document_conversion_http_adapter=ForbiddenConversionAdapter(),
            max_pdf_bytes=max_pdf_bytes,
        )
    )
    return TestClient(application)


def _routeur_admet_le_pdf_seul_et_delegue_none_comme_metadonnees() -> None:
    adapter = RecordingDocumentAdapter()
    pdf = b"%PDF-1.7\nbody\n%%EOF\n"
    response = _client(adapter).post(
        "/v1/documents",
        files={"original_content": ("document.pdf", pdf, "application/pdf")},
    )
    assert response.status_code == 201
    assert response.json() == {
        "document_id": "DOC-1111111111111111",
        "document_status": "REGISTERED",
    }
    assert adapter.calls == [(pdf, None)]


def _routeur_refuse_les_anciens_champs_bibliographiques() -> None:
    adapter = RecordingDocumentAdapter()
    response = _client(adapter).post(
        "/v1/documents",
        files={
            "original_content": (
                "document.pdf",
                b"%PDF-1.7\n%%EOF\n",
                "application/pdf",
            )
        },
        data={"title": "Titre manuel"},
    )
    assert response.status_code == 400
    assert response.json() == {
        "error_code": "HTTP_REQUEST_INVALID",
        "field": "body",
    }
    assert adapter.calls == []


def _routeur_refuse_type_mime_et_taille_invalides() -> None:
    adapter = RecordingDocumentAdapter()
    wrong_mime = _client(adapter).post(
        "/v1/documents",
        files={
            "original_content": (
                "document.pdf",
                b"%PDF-1.7\n%%EOF\n",
                "application/octet-stream",
            )
        },
    )
    assert wrong_mime.status_code == 400
    assert wrong_mime.json()["field"] == "original_content"

    oversized = _client(adapter, max_pdf_bytes=8).post(
        "/v1/documents",
        files={
            "original_content": (
                "document.pdf",
                b"%PDF-1.7\nbody\n%%EOF\n",
                "application/pdf",
            )
        },
    )
    assert oversized.status_code == 413
    assert oversized.json() == {
        "error_code": "HTTP_REQUEST_TOO_LARGE",
        "max_pdf_bytes": 8,
    }


def test_validate_document_command_router_unit() -> None:
    _routeur_admet_le_pdf_seul_et_delegue_none_comme_metadonnees()
    _routeur_refuse_les_anciens_champs_bibliographiques()
    _routeur_refuse_type_mime_et_taille_invalides()
