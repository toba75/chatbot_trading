"""Acceptation du contrat HTTP documentaire après ADR-038."""

from __future__ import annotations

from app.source_processing.adapters.document_http import HttpRequest, SourceProcessingHttpAdapter
from app.source_processing.application.document_commands import (
    DiagnosisAlreadyRequestedError,
    DocumentDiagnosisAcceptance,
    RegisterDocumentAcceptance,
    SourceNotFoundError,
    SourceUnreadableError,
)
from app.source_processing.domain.source_document import DocumentId


class ScriptedDocumentCommands:
    def __init__(self) -> None:
        self.register_result = RegisterDocumentAcceptance(
            document_id=DocumentId.from_value("DOC-1111111111111111"),
            document_status="REGISTERED",
            duplicate=False,
        )
        self.diagnosis_result = DocumentDiagnosisAcceptance(
            document_id=DocumentId.from_value("DOC-1111111111111111"),
            diagnostic_status="DIAGNOSTIC_REQUESTED",
        )
        self.register_error: Exception | None = None
        self.diagnosis_error: Exception | None = None
        self.register_calls: list[dict[str, object]] = []

    def register_source_document(self, *, original_content: bytes, bibliographic_metadata):
        self.register_calls.append(
            {
                "original_content": original_content,
                "bibliographic_metadata": bibliographic_metadata,
            }
        )
        if self.register_error is not None:
            raise self.register_error
        return self.register_result

    def start_document_processing(self, *, document_id: str):
        if self.diagnosis_error is not None:
            raise self.diagnosis_error
        return self.diagnosis_result


def _post_document(adapter: SourceProcessingHttpAdapter, content: bytes):
    return adapter.handle(
        HttpRequest(
            method="POST",
            path="/v1/documents",
            body={"original_content": content},
        )
    )


def _post_document_admet_le_pdf_seul_sans_inventer_de_metadonnees() -> None:
    commands = ScriptedDocumentCommands()
    adapter = SourceProcessingHttpAdapter(commands)

    response = _post_document(adapter, b"%PDF-1.7\n%%EOF\n")

    assert response.status_code == 201
    assert response.body == {
        "document_id": "DOC-1111111111111111",
        "document_status": "REGISTERED",
    }
    assert commands.register_calls == [
        {
            "original_content": b"%PDF-1.7\n%%EOF\n",
            "bibliographic_metadata": None,
        }
    ]


def _post_document_preserve_doublon_et_source_illisible() -> None:
    commands = ScriptedDocumentCommands()
    adapter = SourceProcessingHttpAdapter(commands)
    commands.register_result = RegisterDocumentAcceptance(
        document_id=DocumentId.from_value("DOC-1111111111111111"),
        document_status="DUPLICATE_SOURCE",
        duplicate=True,
    )
    duplicate = _post_document(adapter, b"%PDF-1.7\n%%EOF\n")
    assert duplicate.status_code == 200
    assert duplicate.body["duplicate"] is True

    commands.register_error = SourceUnreadableError(reason="PDF_CORRUPTED")
    unreadable = _post_document(adapter, b"%PDF-corrupt\n")
    assert unreadable.status_code == 422
    assert unreadable.body == {
        "error_code": "SOURCE_UNREADABLE",
        "reason": "PDF_CORRUPTED",
    }


def _post_document_refuse_un_contenu_original_absent() -> None:
    adapter = SourceProcessingHttpAdapter(ScriptedDocumentCommands())
    response = adapter.handle(HttpRequest(method="POST", path="/v1/documents", body={}))
    assert response.status_code == 400
    assert response.body == {
        "error_code": "HTTP_REQUEST_INVALID",
        "field": "original_content",
    }


def _diagnose_preserve_les_erreurs_publiques() -> None:
    commands = ScriptedDocumentCommands()
    adapter = SourceProcessingHttpAdapter(commands)
    invalid = adapter.handle(
        HttpRequest(method="POST", path="/v1/documents/invalide/diagnose", body={})
    )
    assert invalid.status_code == 400

    commands.diagnosis_error = SourceNotFoundError("DOC-2222222222222222")
    missing = adapter.handle(
        HttpRequest(
            method="POST",
            path="/v1/documents/DOC-2222222222222222/diagnose",
            body={},
        )
    )
    assert missing.status_code == 404

    commands.diagnosis_error = DiagnosisAlreadyRequestedError("DOC-1111111111111111")
    repeated = adapter.handle(
        HttpRequest(
            method="POST",
            path="/v1/documents/DOC-1111111111111111/diagnose",
            body={},
        )
    )
    assert repeated.status_code == 409


def test_validate_document_http_contract_acceptance() -> None:
    _post_document_admet_le_pdf_seul_sans_inventer_de_metadonnees()
    _post_document_preserve_doublon_et_source_illisible()
    _post_document_refuse_un_contenu_original_absent()
    _diagnose_preserve_les_erreurs_publiques()
