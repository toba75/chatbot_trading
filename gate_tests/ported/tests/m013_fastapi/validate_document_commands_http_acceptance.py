"""Acceptation HTTP des commandes documentaires après ADR-038."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.source_processing.adapters.document_http import SourceProcessingHttpAdapter
from app.source_processing.adapters.http import build_document_command_router
from app.source_processing.application.document_commands import (
    DiagnosisAlreadyRequestedError,
    DocumentDiagnosisAcceptance,
    RegisterDocumentAcceptance,
    SourceNotFoundError,
    SourceUnreadableError,
)
from app.source_processing.domain.source_document import DocumentId, SourceFingerprint


class ContractCommands:
    def __init__(self) -> None:
        self.registered: dict[str, tuple[DocumentId, object]] = {}
        self.diagnosed: set[str] = set()

    def register_source_document_path(self, *, original_path: Path, bibliographic_metadata):
        return self.register_source_document(
            original_content=original_path.read_bytes(),
            bibliographic_metadata=bibliographic_metadata,
        )

    def register_source_document(self, *, original_content: bytes, bibliographic_metadata):
        if original_content == b"%PDF-corrompu\n%%EOF\n":
            raise SourceUnreadableError("PDF_CORRUPTED")
        fingerprint = SourceFingerprint.from_content(original_content)
        document_id = DocumentId.from_fingerprint(fingerprint)
        if fingerprint.value in self.registered:
            return RegisterDocumentAcceptance(document_id, "DUPLICATE_SOURCE", True)
        self.registered[fingerprint.value] = (document_id, bibliographic_metadata)
        return RegisterDocumentAcceptance(document_id, "REGISTERED", False)

    def start_document_processing(self, *, document_id: str):
        known_ids = {entry[0].value for entry in self.registered.values()}
        if document_id not in known_ids:
            raise SourceNotFoundError(document_id)
        if document_id in self.diagnosed:
            raise DiagnosisAlreadyRequestedError(document_id)
        self.diagnosed.add(document_id)
        return DocumentDiagnosisAcceptance(
            DocumentId.from_value(document_id),
            "DIAGNOSTIC_REQUESTED",
        )


class ForbiddenConversionAdapter:
    def handle(self, request):
        raise AssertionError("La conversion ne doit pas être appelée.")


def test_validate_document_commands_http_acceptance() -> None:
    commands = ContractCommands()
    application = FastAPI()
    application.include_router(
        build_document_command_router(
            document_http_adapter=SourceProcessingHttpAdapter(commands),
            document_conversion_http_adapter=ForbiddenConversionAdapter(),
            max_pdf_bytes=1024 * 1024,
        )
    )
    client = TestClient(application)
    pdf = b"%PDF-1.7\n1 0 obj<<>>endobj\n%%EOF\n"

    created = client.post(
        "/v1/documents",
        files={"original_content": ("document.pdf", pdf, "application/pdf")},
    )
    assert created.status_code == 201
    document_id = created.json()["document_id"]
    assert set(created.json()) == {"document_id", "document_status"}
    assert next(iter(commands.registered.values()))[1] is None

    duplicate = client.post(
        "/v1/documents",
        files={"original_content": ("document.pdf", pdf, "application/pdf")},
    )
    assert duplicate.status_code == 200
    assert duplicate.json() == {
        "document_id": document_id,
        "document_status": "DUPLICATE_SOURCE",
        "duplicate": True,
    }

    forbidden_metadata = client.post(
        "/v1/documents",
        files={"original_content": ("document.pdf", pdf, "application/pdf")},
        data={"title": "Titre manuel"},
    )
    assert forbidden_metadata.status_code == 400
    assert forbidden_metadata.json()["field"] == "body"

    corrupt = client.post(
        "/v1/documents",
        files={
            "original_content": (
                "document.pdf",
                b"%PDF-corrompu\n%%EOF\n",
                "application/pdf",
            )
        },
    )
    assert corrupt.status_code == 422
    assert corrupt.json()["error_code"] == "SOURCE_UNREADABLE"

    diagnosed = client.post(f"/v1/documents/{document_id}/diagnose")
    assert diagnosed.status_code == 202
    repeated = client.post(f"/v1/documents/{document_id}/diagnose")
    assert repeated.status_code == 409
    absent = client.post("/v1/documents/DOC-FFFFFFFFFFFFFFFF/diagnose")
    assert absent.status_code == 404
