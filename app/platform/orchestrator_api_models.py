"""Modèles OpenAPI publics stricts de l'API orchestratrice."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue as PydanticJsonValue,
    RootModel,
    model_validator,
)

from app.contracts.document_public_statuses import (
    PublicActionPhase,
    PublicConversionStatus,
    PublicDiagnosticStatus,
    PublicProjectionStatus,
    PublicSourceStatus,
)
from app.contracts.identity import DomainIdentifier


class PublicApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PublicErrorResponse(PublicApiModel):
    error_code: str
    field: str | None = None
    document_id: str | None = None
    reason: str | None = None
    max_body_bytes: int | None = None
    message: str | None = None
    path: str | None = None
    endpoint: str | None = None
    status_code: int | None = None
    task_name: str | None = None
    gateway_status_code: int | None = None
    gateway_response: dict[str, PydanticJsonValue] | None = None


class ChatMessageRequest(PublicApiModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1)


class ChatCompletionRequest(PublicApiModel):
    model: str = Field(min_length=1)
    conversation_id: str = Field(min_length=1)
    messages: list[ChatMessageRequest] = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    sampling_parameters: dict[str, PydanticJsonValue] = Field(min_length=1)


class ProductConversationCreateRequest(PublicApiModel):
    title: str = Field(min_length=1, max_length=160)
    default_mandate: dict[str, PydanticJsonValue] = Field(min_length=1)
    presentation_preferences: dict[str, PydanticJsonValue] = Field(min_length=1)
    occurred_at: str = Field(min_length=1)


class ProductConversationMessageRequest(PublicApiModel):
    message: str = Field(min_length=1, max_length=8000)
    idempotency_key: str = Field(min_length=1)
    occurred_at: str = Field(min_length=1)
    requested_mode: Literal["CHAT_DOCUMENTAIRE"]
    selected_documents: list[str] = Field(min_length=1)
    research_mandate: dict[str, PydanticJsonValue] | None = None


class ProductConversationResponse(PublicApiModel):
    conversation_id: str
    title: str
    status: Literal["ACTIVE", "ARCHIVED"]
    created_at: str
    updated_at: str


class ProductConversationCitationResponse(PublicApiModel):
    citation_id: str
    evidence_id: str
    quoted_span_hash: str = Field(min_length=64, max_length=64)
    source_locator: "SourceLocatorResponse"


class ProductConversationMessageResponse(PublicApiModel):
    conversation_id: str
    turn_id: str
    resolved_question: str
    mode: Literal["CHAT_DOCUMENTAIRE"]
    mode_justification: str
    support_status: Literal[
        "SUPPORTED",
        "PARTIALLY_SUPPORTED",
        "INSUFFICIENT_EVIDENCE",
        "CONFLICTING_EVIDENCE",
        "REQUIRES_CURRENT_DATA",
    ]
    answer_id: str
    verified_answer_ref: str
    answer_text: str
    citations: list[ProductConversationCitationResponse] = Field(min_length=1)
    knowledge_gaps: list[dict[str, PydanticJsonValue]]
    unresolved_conflicts: list[dict[str, PydanticJsonValue]]
    abstention_reason: str | None


class ProductConversationTurnResponse(PublicApiModel):
    conversation_id: str
    turn_id: str
    sequence: int = Field(ge=1)
    role: Literal["USER"]
    message: str = Field(min_length=1)
    occurred_at: str = Field(min_length=1)
    presentation: ProductConversationMessageResponse | None = None


class ProductConversationTurnsResponse(PublicApiModel):
    conversation_id: str
    next_page_token: str | None
    turns: list[ProductConversationTurnResponse]


class BenchmarkRequest(PublicApiModel):
    model: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    sampling_parameters: dict[str, PydanticJsonValue] = Field(min_length=1)


class SearchRequest(PublicApiModel):
    query_text: str = Field(min_length=1, max_length=4096)


class IndexRequest(PublicApiModel):
    """Corps vide historique tant que le service KA n'est pas composé."""


class ProjectionCommandRequest(PublicApiModel):
    """Profil strict de la commande réelle de projection KA."""

    projection_profile_id: str = Field(min_length=1)
    chunking_profile: str = Field(min_length=1)
    embedding_model: str = Field(min_length=1)
    sparse_profile: str = Field(min_length=1)
    index_schema: str = Field(min_length=1)


class ChatChoiceMessageResponse(PublicApiModel):
    role: Literal["assistant"]
    content: str = Field(min_length=1)


class ChatChoiceResponse(PublicApiModel):
    index: int = Field(ge=0)
    message: ChatChoiceMessageResponse
    finish_reason: Literal["stop"]


class ChatProductProvenanceResponse(PublicApiModel):
    provider: str | None = None
    model_id: str | None = None
    model_revision: str | None = None
    runtime_version: str | None = None
    prompt_id: str | None = None
    prompt_version: str | None = None
    schema_version: str | None = None
    input_hash: str | None = None
    output_hash: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    configuration_hash: str


class ChatProductResponse(PublicApiModel):
    execution_mode: Literal["live_spark"]
    path_segments: tuple[
        Literal["docker-local"],
        Literal["orchestrator-api"],
        Literal["llm-gateway"],
        Literal["vllm-spark"],
    ]
    gateway_endpoint: str
    raw_response_id: str
    provenance: ChatProductProvenanceResponse


class ChatCompletionResponse(PublicApiModel):
    id: str
    object: Literal["chat.completion"]
    created: int = Field(ge=0)
    model: str
    choices: list[ChatChoiceResponse] = Field(min_length=1)
    ost_product: ChatProductResponse


class BenchmarkTaskResultResponse(PublicApiModel):
    task_name: str
    passed: bool
    raw_response_id: str
    response_json_sha256: str = Field(min_length=64, max_length=64)
    answer_sha256: str = Field(min_length=64, max_length=64)
    gateway_latency_ms: str
    provenance: ChatProductProvenanceResponse


class BenchmarkMetricResponse(PublicApiModel):
    name: str
    value: str | None
    numerator: int | None
    denominator: int | None
    measured: bool
    unavailable_reason: str | None = None

    @model_validator(mode="after")
    def validate_measurement(self) -> "BenchmarkMetricResponse":
        if self.measured:
            if self.value is None or self.numerator is None or self.denominator is None:
                raise ValueError("métrique mesurée partielle")
            if self.unavailable_reason is not None:
                raise ValueError("raison indisponible interdite pour métrique mesurée")
        elif (
            self.value is not None
            or self.numerator is not None
            or self.denominator is not None
            or self.unavailable_reason is None
        ):
            raise ValueError("métrique indisponible partielle")
        return self


class BenchmarkResponse(PublicApiModel):
    object: Literal["llm_real_path_benchmark.run"]
    run_id: str
    execution_mode: Literal["live_spark"]
    model: str
    configuration_hash: str = Field(min_length=64, max_length=64)
    path_segments: tuple[
        Literal["docker-local"],
        Literal["orchestrator-api"],
        Literal["llm-gateway"],
        Literal["vllm-spark"],
    ]
    task_names: list[str] = Field(min_length=1)
    task_results: list[BenchmarkTaskResultResponse] = Field(min_length=1)
    technical_metric_names: list[str] = Field(min_length=1)
    technical_metrics: list[BenchmarkMetricResponse] = Field(min_length=1)


class SearchUnavailableResponse(PublicApiModel):
    error_code: Literal["SERVICE_NOT_CONFIGURED"]
    endpoint: Literal["POST /v1/search"]


class IndexUnavailableResponse(PublicApiModel):
    document_id: str
    error_code: Literal["SERVICE_NOT_CONFIGURED"]
    endpoint: Literal["POST /v1/documents/{document_id}/index"]


class IndexAcceptedResponse(PublicApiModel):
    document_id: str
    projection_id: str
    projection_status: PublicProjectionStatus
    canonical_version_id: str


class DocumentRegisteredResponse(PublicApiModel):
    document_id: str
    document_status: PublicSourceStatus


class DocumentDuplicateResponse(DocumentRegisteredResponse):
    duplicate: Literal[True]


class DiagnosticAcceptedResponse(PublicApiModel):
    document_id: str
    diagnostic_status: PublicDiagnosticStatus


class ConversionAcceptedResponse(PublicApiModel):
    document_id: str
    conversion_status: PublicConversionStatus
    canonical_version_id: str | None = None

    @model_validator(mode="after")
    def validate_conversion_acceptance(self) -> "ConversionAcceptedResponse":
        if self.conversion_status not in {
            PublicConversionStatus.CONVERSION_REQUESTED,
            PublicConversionStatus.CANONICAL_ACCEPTED,
        }:
            raise ValueError("statut de commande conversion invalide")
        accepted = self.conversion_status is PublicConversionStatus.CANONICAL_ACCEPTED
        if accepted != (self.canonical_version_id is not None):
            raise ValueError("version canonique incohérente avec l'acceptation")
        return self


class DocumentActionProgressResponse(PublicApiModel):
    action_name: Literal["DIAGNOSE", "CONVERT_DOCUMENT", "PROJECT_DOCUMENT"]
    phase: PublicActionPhase
    completed_units: int = Field(ge=0)
    total_units: int | None = Field(default=None, ge=1)
    failure_error_code: str | None

    @model_validator(mode="after")
    def validate_progress(self) -> "DocumentActionProgressResponse":
        if self.phase is PublicActionPhase.NOT_REQUESTED:
            if (
                self.completed_units != 0
                or self.total_units is not None
                or self.failure_error_code is not None
            ):
                raise ValueError("progression non demandée incohérente")
            return self
        if self.total_units is None:
            raise ValueError("total d'unités requis")
        if self.completed_units > self.total_units:
            raise ValueError("progression supérieure au total")
        if self.phase is PublicActionPhase.SUCCEEDED:
            if self.completed_units != self.total_units or self.failure_error_code is not None:
                raise ValueError("progression réussie incohérente")
        elif self.phase is PublicActionPhase.FAILED:
            if self.failure_error_code is None:
                raise ValueError("code d'échec progression requis")
        elif self.failure_error_code is not None:
            raise ValueError("code d'échec interdit hors échec")
        return self


class DocumentCorpusItemResponse(PublicApiModel):
    document_id: str
    title: str
    document_status: PublicSourceStatus
    diagnostic_status: PublicDiagnosticStatus
    conversion_status: PublicConversionStatus
    canonical_version_id: str | None
    projection_status: PublicProjectionStatus
    manual_review_reason: str | None = None
    failure_error_code: str | None = None
    conversion_action_available: bool
    projection_action_available: bool = False

    @model_validator(mode="after")
    def validate_canonical_version(self) -> "DocumentCorpusItemResponse":
        accepted = self.conversion_status is PublicConversionStatus.CANONICAL_ACCEPTED
        if accepted != (self.canonical_version_id is not None):
            raise ValueError("version canonique incohérente avec le statut de conversion")
        return self


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
    diagnostic_status: PublicDiagnosticStatus
    source_page_count: int = Field(ge=1)
    diagnosed_page_count: int = Field(ge=0)
    manual_review_reason: str | None
    failure_error_code: str | None = None
    manifest: list[PageManifestEntryResponse]
    pages: list[DiagnosticPageResponse]


class DocumentConversionResponse(PublicApiModel):
    document_id: str
    conversion_status: PublicConversionStatus
    qa_rejection_error_code: str | None
    canonical_version_id: str | None

    @model_validator(mode="after")
    def validate_conversion_outputs(self) -> "DocumentConversionResponse":
        if self.conversion_status is PublicConversionStatus.CANONICAL_ACCEPTED:
            if self.canonical_version_id is None or self.qa_rejection_error_code is not None:
                raise ValueError("conversion canonique partielle")
        elif self.conversion_status is PublicConversionStatus.QA_REJECTED:
            if self.qa_rejection_error_code is None or self.canonical_version_id is not None:
                raise ValueError("rejet QA partiel")
        elif self.qa_rejection_error_code is not None or self.canonical_version_id is not None:
            raise ValueError("sortie de conversion prématurée")
        return self


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

    @model_validator(mode="after")
    def validate_searchable_projection(self) -> "KnowledgeProjectionResponse":
        if self.projection_status == "SEARCHABLE" and (
            self.chunk_count < 1 or len(self.chunk_samples) == 0
        ):
            raise ValueError("projection SEARCHABLE incomplète")
        if len(self.chunk_samples) > self.chunk_count:
            raise ValueError("échantillons de projection incohérents")
        return self


ProjectionResponseUnion = Annotated[
    ProjectionNotRequestedResponse | KnowledgeProjectionResponse,
    Field(discriminator="projection_status"),
]


class ProjectionResponse(RootModel[ProjectionResponseUnion]):
    """Union publique: absence explicite ou projection KA complète."""


PUBLIC_ERROR_RESPONSES = {
    401: {"model": PublicErrorResponse, "description": "Autorisation locale requise."},
    403: {"model": PublicErrorResponse, "description": "Autorisation locale refusée."},
    400: {"model": PublicErrorResponse, "description": "Requête publique invalide."},
    404: {"model": PublicErrorResponse, "description": "Ressource publique absente."},
    409: {"model": PublicErrorResponse, "description": "Conflit d'état métier."},
    413: {"model": PublicErrorResponse, "description": "Corps HTTP trop volumineux."},
    422: {"model": PublicErrorResponse, "description": "Source ou payload refusé."},
    500: {"model": PublicErrorResponse, "description": "Erreur interne traçable."},
    503: {"model": PublicErrorResponse, "description": "Dépendance obligatoire indisponible."},
    507: {"model": PublicErrorResponse, "description": "Quota durable du corpus atteint."},
}


def parse_public_document_id(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("document_id public invalide")
    return str(DomainIdentifier.parse_with_prefix(value, "DOC"))


def public_error(error_code: str, **fields: object) -> dict[str, object]:
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
    "BenchmarkMetricResponse",
    "BenchmarkRequest",
    "BenchmarkResponse",
    "BenchmarkTaskResultResponse",
    "ChatChoiceMessageResponse",
    "ChatChoiceResponse",
    "ChatCompletionRequest",
    "ChatCompletionResponse",
    "ConversionAcceptedResponse",
    "ChatMessageRequest",
    "ChatProductProvenanceResponse",
    "ChatProductResponse",
    "DiagnosticAcceptedResponse",
    "DiagnosticPageResponse",
    "DocumentConversionResponse",
    "DocumentCorpusItemResponse",
    "DocumentActionProgressResponse",
    "DocumentCorpusResponse",
    "DocumentDiagnosticResponse",
    "DocumentDuplicateResponse",
    "DocumentRegisteredResponse",
    "DOCUMENT_MULTIPART_OPENAPI",
    "KnowledgeProjectionResponse",
    "IndexRequest",
    "IndexUnavailableResponse",
    "PageDiagnosticSignalsResponse",
    "PageManifestEntryResponse",
    "PageRouteResponse",
    "ProjectionChunkSampleResponse",
    "ProjectionCommandRequest",
    "ProjectionFreshnessResponse",
    "ProjectionNotRequestedResponse",
    "ProjectionProfileResponse",
    "ProjectionResponse",
    "PUBLIC_ERROR_RESPONSES",
    "PublicErrorResponse",
    "SearchRequest",
    "SearchUnavailableResponse",
    "SourceLocatorResponse",
    "parse_public_document_id",
    "public_error",
]
