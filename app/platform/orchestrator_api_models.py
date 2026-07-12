"""Modèles OpenAPI publics stricts de l'API orchestratrice."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel

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
    projection_status: str


class DocumentCorpusResponse(PublicApiModel):
    documents: list[DocumentCorpusItemResponse]
    next_cursor: str | None


class PageManifestEntryResponse(PublicApiModel):
    page_number: int = Field(ge=1)
    manifest_status: str


class PageDiagnosticSignalsResponse(PublicApiModel):
    page_state: str
    native_text_state: str
    image_state: str
    existing_ocr_state: str
    layout_complexity: str
    corruption_state: str
    mixed_content_detected: bool
    has_table: bool
    has_formula: bool
    diagnostic_version: str
    justification: str


class PageRouteResponse(PublicApiModel):
    route_name: str
    decision_mode: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    preprocessing_action: str
    routing_policy_version: str
    justification: str


class DiagnosticPageResponse(PublicApiModel):
    page_number: int = Field(ge=1)
    manifest_status: str
    diagnostic: PageDiagnosticSignalsResponse | None
    route: PageRouteResponse | None


class DocumentDiagnosticResponse(PublicApiModel):
    document_id: str
    diagnostic_status: str
    source_page_count: int = Field(ge=1)
    diagnosed_page_count: int = Field(ge=0)
    manual_review_reason: str | None
    manifest: list[PageManifestEntryResponse]
    pages: list[DiagnosticPageResponse]


class DocumentConversionResponse(PublicApiModel):
    document_id: str
    conversion_status: str
    qa_rejection_error_code: str | None
    canonical_version_id: str | None


class ProjectionProfileResponse(PublicApiModel):
    projection_profile_id: str
    chunking_profile: str
    embedding_model: str
    sparse_profile: str
    index_schema: str


class ProjectionFreshnessResponse(PublicApiModel):
    status: Literal["PENDING", "CURRENT", "STALE", "UNAVAILABLE"]
    observed_at: str


class SourceLocatorResponse(PublicApiModel):
    schema_version: str
    canonical_version_id: str
    document_id: str
    page_pdf: int = Field(ge=1)
    item_id: str
    bbox: tuple[float, float, float, float]
    content_hash: str


class ProjectionChunkSampleResponse(PublicApiModel):
    chunk_level: str
    text_preview: str
    text_preview_truncated: bool
    content_hash: str
    source_locators: list[SourceLocatorResponse]


class ProjectionNotRequestedResponse(PublicApiModel):
    document_id: str
    projection_status: Literal["PROJECTION_NOT_REQUESTED"]


class KnowledgeProjectionResponse(PublicApiModel):
    document_id: str
    projection_id: str
    canonical_version_id: str
    projection_status: Literal[
        "REQUESTED",
        "BUILDING",
        "BUILT",
        "INDEXING",
        "SEARCHABLE",
        "STALE",
        "FAILED",
        "RETIRED",
    ]
    profile: ProjectionProfileResponse
    freshness: ProjectionFreshnessResponse
    chunk_count: int = Field(ge=0)
    chunk_samples: list[ProjectionChunkSampleResponse]


class ProjectionResponse(
    RootModel[ProjectionNotRequestedResponse | KnowledgeProjectionResponse]
):
    """Union publique: absence explicite ou projection KA complète."""


PUBLIC_ERROR_RESPONSES = {
    400: {"model": PublicErrorResponse, "description": "Requête publique invalide."},
    404: {"model": PublicErrorResponse, "description": "Ressource publique absente."},
    409: {"model": PublicErrorResponse, "description": "Conflit d'état métier."},
    413: {"model": PublicErrorResponse, "description": "Corps HTTP trop volumineux."},
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
    "DiagnosticPageResponse",
    "DocumentConversionResponse",
    "DocumentCorpusItemResponse",
    "DocumentCorpusResponse",
    "DocumentDiagnosticResponse",
    "DocumentDuplicateResponse",
    "DocumentRegisteredResponse",
    "DOCUMENT_MULTIPART_OPENAPI",
    "KnowledgeProjectionResponse",
    "PageDiagnosticSignalsResponse",
    "PageManifestEntryResponse",
    "PageRouteResponse",
    "ProjectionChunkSampleResponse",
    "ProjectionFreshnessResponse",
    "ProjectionNotRequestedResponse",
    "ProjectionProfileResponse",
    "ProjectionResponse",
    "PUBLIC_ERROR_RESPONSES",
    "PublicErrorResponse",
    "SourceLocatorResponse",
    "parse_public_document_id",
    "public_error",
]
