"""Modèles OpenAPI publics de l'API orchestratrice."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict
from app.contracts.identity import DomainIdentifier


class PublicApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PublicErrorResponse(PublicApiModel):
    error_code: str
    field: str | None = None
    document_id: str | None = None
    reason: str | None = None
    max_body_bytes: int | None = None


class DocumentRegisteredResponse(PublicApiModel):
    document_id: str
    document_status: str


class DocumentDuplicateResponse(DocumentRegisteredResponse):
    duplicate: Literal[True]


class DiagnosticAcceptedResponse(PublicApiModel):
    document_id: str
    diagnostic_status: str


class DocumentCorpusItemResponse(PublicApiModel):
    document_id: str
    title: str
    document_status: str
    diagnostic_status: str
    conversion_status: str
    canonical_version_id: str | None


class DocumentCorpusResponse(PublicApiModel):
    documents: list[DocumentCorpusItemResponse]


class DocumentDiagnosticResponse(PublicApiModel):
    document_id: str
    diagnostic_status: str
    source_page_count: int
    diagnosed_page_count: int
    manual_review_reason: str | None
    manifest: list[dict[str, Any]]
    pages: list[dict[str, Any]]


class DocumentConversionResponse(PublicApiModel):
    document_id: str
    conversion_status: str
    qa_rejection_error_code: str | None
    canonical_version_id: str | None


class ProjectionResponse(PublicApiModel):
    document_id: str
    projection_status: str
    projection_id: str | None = None
    canonical_version_id: str | None = None
    profile: dict[str, Any] | None = None
    freshness: dict[str, Any] | None = None
    chunk_count: int | None = None
    chunk_samples: list[dict[str, Any]] | None = None


PUBLIC_ERROR_RESPONSES = {
    400: {"model": PublicErrorResponse, "description": "Requête publique invalide."},
    404: {"model": PublicErrorResponse, "description": "Ressource publique absente."},
    409: {"model": PublicErrorResponse, "description": "Conflit d'état métier."},
    422: {"model": PublicErrorResponse, "description": "Source ou payload refusé."},
    500: {"model": PublicErrorResponse, "description": "Erreur interne traçable."},
    503: {"model": PublicErrorResponse, "description": "Dépendance obligatoire indisponible."},
}


def parse_public_document_id(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("document_id public invalide")
    return str(DomainIdentifier.parse_with_prefix(value, "DOC"))


def public_error(error_code: str, **fields: Any) -> dict[str, Any]:
    if not isinstance(error_code, str) or error_code == "" or error_code != error_code.strip():
        raise ValueError("error_code public invalide")
    return {"error_code": error_code, **fields}


DOCUMENT_MULTIPART_OPENAPI = {
    "requestBody": {
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "required": [
                        "original_content",
                        "title",
                        "authors",
                        "publication_year",
                        "edition",
                    ],
                    "properties": {
                        "original_content": {"type": "string", "format": "binary"},
                        "title": {"type": "string", "maxLength": 512},
                        "authors": {
                            "type": "array",
                            "items": {"type": "string", "maxLength": 256},
                            "minItems": 1,
                            "maxItems": 16,
                        },
                        "publication_year": {"type": "integer", "minimum": 1, "maximum": 9999},
                        "edition": {"type": "string", "maxLength": 64},
                    },
                }
            }
        },
    }
}


__all__ = [
    "DiagnosticAcceptedResponse",
    "DocumentConversionResponse",
    "DocumentCorpusResponse",
    "DocumentDiagnosticResponse",
    "DocumentDuplicateResponse",
    "DocumentRegisteredResponse",
    "DOCUMENT_MULTIPART_OPENAPI",
    "ProjectionResponse",
    "PUBLIC_ERROR_RESPONSES",
    "PublicErrorResponse",
    "parse_public_document_id",
    "public_error",
]
