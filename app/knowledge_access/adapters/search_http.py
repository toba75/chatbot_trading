"""Adaptateur HTTP public pour la commande KA de recherche."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from app.contracts.identity import DomainIdentifier
from app.knowledge_access.adapters.projection_http import HttpRequest, HttpResponse
from app.knowledge_access.application.search_knowledge import (
    SearchIndexUnavailableError,
    SearchProfileUnsupportedError,
    SearchProjectionNotFoundError,
    SearchProjectionStaleError,
    SearchProjectionUnavailableError,
    SearchTracePersistenceError,
)
from app.knowledge_access.domain.projection_metadata import (
    SearchFilter,
    SearchFilterNotSupportedError,
)
from app.knowledge_access.domain.search import (
    HybridRetrievalPolicy,
    RetrievalCandidate,
    SearchRequest,
    SearchResponse,
)
from app.knowledge_access.domain.time import ensure_utc_instant


_SEARCH_BODY_FIELDS = frozenset(
    {
        "projection_id",
        "query_text",
        "filters",
        "search_profile_id",
        "occurred_at",
    }
)
_AMBIGUOUS_QUERY_FIELDS = frozenset({"query", "question", "prompt", "text"})
_ALLOWED_REQUESTING_CONTEXTS = frozenset({"RA", "EG"})
_MAX_QUERY_TEXT_CHARACTERS = 4096
_MAX_FILTER_VALUES_PER_DIMENSION = 50


class KnowledgeSearchCommandPort(Protocol):
    """Port applicatif appelé par l'adaptateur HTTP de recherche."""

    def search(self, request: SearchRequest) -> SearchResponse:
        """Retourne des preuves candidates KA."""


class SearchProfileCatalog(Protocol):
    """Catalogue de profils publics vers politiques hybrides internes."""

    def profile_for_id(self, search_profile_id: str) -> HybridRetrievalPolicy:
        """Retourne la politique hybride attachée au profil public."""


class SearchHttpRequestValidationError(ValueError):
    """Erreur de validation transport avec champ public stable."""

    def __init__(self, message: str, *, field: str) -> None:
        self.field = _ensure_text(field, "field")
        super().__init__(message)


@dataclass(frozen=True)
class SearchRequestDto:
    """DTO public de requête `POST /v1/search`."""

    projection_id: str
    query_text: str
    filters: Mapping[str, Any]
    search_profile_id: str
    occurred_at: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "SearchRequestDto":
        parsed_payload = _ensure_mapping(payload, "body")
        actual_fields = frozenset(parsed_payload.keys())
        ambiguous_fields = actual_fields & _AMBIGUOUS_QUERY_FIELDS
        if len(ambiguous_fields) > 0:
            raise SearchHttpRequestValidationError(
                f"body ambigu: {sorted(ambiguous_fields)[0]}",
                field="body",
            )
        unexpected_fields = actual_fields - _SEARCH_BODY_FIELDS
        if len(unexpected_fields) > 0:
            raise SearchHttpRequestValidationError(
                f"body champ interdit: {sorted(unexpected_fields)[0]}",
                field="body",
            )
        missing_fields = _SEARCH_BODY_FIELDS - actual_fields
        if len(missing_fields) > 0:
            missing_field = sorted(missing_fields)[0]
            raise SearchHttpRequestValidationError(
                f"{missing_field} absent",
                field=missing_field,
            )
        return cls(
            projection_id=parsed_payload["projection_id"],
            query_text=parsed_payload["query_text"],
            filters=parsed_payload["filters"],
            search_profile_id=parsed_payload["search_profile_id"],
            occurred_at=parsed_payload["occurred_at"],
        )

    def __post_init__(self) -> None:
        object.__setattr__(self, "projection_id", _ensure_projection_id(self.projection_id))
        object.__setattr__(self, "query_text", _ensure_query_text(self.query_text))
        object.__setattr__(self, "filters", _ensure_filter_mapping(self.filters))
        object.__setattr__(
            self,
            "search_profile_id",
            _ensure_text(self.search_profile_id, "search_profile_id"),
        )
        try:
            occurred_at = ensure_utc_instant(self.occurred_at, "occurred_at")
        except ValueError as exc:
            raise SearchHttpRequestValidationError("occurred_at invalide", field="occurred_at") from exc
        object.__setattr__(self, "occurred_at", occurred_at)

    def to_domain_request(self, hybrid_policy: HybridRetrievalPolicy, *, authenticated_context: str) -> SearchRequest:
        if not isinstance(hybrid_policy, HybridRetrievalPolicy):
            raise SearchProfileUnsupportedError(self.search_profile_id)
        requesting_context = _ensure_authenticated_search_context(authenticated_context)
        return SearchRequest(
            projection_id=self.projection_id,
            query_text=self.query_text,
            filters=SearchFilter.from_payload(self.filters),
            hybrid_policy=hybrid_policy,
            occurred_at=self.occurred_at,
            requested_by_context=requesting_context,
        )


@dataclass(frozen=True)
class SearchResultDto:
    """DTO public d'une preuve candidate KA."""

    candidate: RetrievalCandidate

    @classmethod
    def from_candidate(cls, candidate: RetrievalCandidate) -> "SearchResultDto":
        return cls(candidate=candidate)

    def __post_init__(self) -> None:
        if not isinstance(self.candidate, RetrievalCandidate):
            raise ValueError("candidate invalide")

    def to_payload(self) -> dict[str, Any]:
        return {
            "chunk_id": self.candidate.chunk_id,
            "document_id": self.candidate.document_id,
            "canonical_version_id": self.candidate.canonical_version_id,
            "content_hash": self.candidate.content_hash,
            "source_locator": self.candidate.source_locator.to_payload(),
            "scores": self.candidate.score_bundle.to_payload(),
            "excerpt": self.candidate.text,
        }


@dataclass(frozen=True)
class SearchResponseDto:
    """DTO public de réponse `POST /v1/search`."""

    response: SearchResponse

    @classmethod
    def from_domain(cls, response: SearchResponse) -> "SearchResponseDto":
        return cls(response=response)

    def __post_init__(self) -> None:
        if not isinstance(self.response, SearchResponse):
            raise ValueError("search_response invalide")

    def to_payload(self) -> dict[str, Any]:
        return {
            "search_trace_id": self.response.search_trace_id,
            "projection_id": self.response.projection_id,
            "results": tuple(
                SearchResultDto.from_candidate(candidate).to_payload()
                for candidate in self.response.candidates
            ),
            "warnings": self.response.warnings,
            "applied_filters": self.response.applied_filters,
        }


class KnowledgeSearchHttpAdapter:
    """Route explicitement POST /v1/search côté KA."""

    def __init__(
        self,
        *,
        search_commands: KnowledgeSearchCommandPort,
        search_profile_catalog: SearchProfileCatalog,
    ) -> None:
        if not callable(getattr(search_commands, "search", None)):
            raise ValueError("search_commands sans SearchKnowledge")
        if not callable(getattr(search_profile_catalog, "profile_for_id", None)):
            raise ValueError("search_profile_catalog sans profile_for_id")
        self._search_commands = search_commands
        self._search_profile_catalog = search_profile_catalog

    def handle(self, request: HttpRequest) -> HttpResponse:
        parsed_request = _ensure_http_request(request)
        if parsed_request.method == "POST" and parsed_request.path == "/v1/search":
            return self._handle_search(parsed_request)
        return HttpResponse(
            status_code=404,
            body={"error_code": "ENDPOINT_NOT_FOUND", "path": parsed_request.path},
        )

    def _handle_search(self, request: HttpRequest) -> HttpResponse:
        try:
            request_dto = SearchRequestDto.from_payload(request.body)
            hybrid_policy = self._profile_for_id(request_dto.search_profile_id)
            domain_request = request_dto.to_domain_request(
                hybrid_policy,
                authenticated_context=request.authenticated_context,
            )
        except SearchFilterNotSupportedError as exc:
            return HttpResponse(
                status_code=422,
                body={"error_code": "FILTER_NOT_SUPPORTED", "dimension": exc.dimension},
            )
        except SearchProfileUnsupportedError as exc:
            return _search_profile_unsupported_response(exc.reason)
        except SearchHttpRequestValidationError as exc:
            return _bad_request_response(exc.field)
        except ValueError:
            return _bad_request_response("body")

        try:
            response = self._search_commands.search(domain_request)
        except SearchProjectionNotFoundError as exc:
            return HttpResponse(
                status_code=404,
                body={"error_code": "PROJECTION_NOT_FOUND", "projection_id": exc.projection_id},
            )
        except SearchProjectionStaleError as exc:
            return HttpResponse(
                status_code=409,
                body={"error_code": "PROJECTION_STALE", "projection_id": exc.projection_id},
            )
        except SearchProfileUnsupportedError as exc:
            return _search_profile_unsupported_response(exc.reason)
        except SearchProjectionUnavailableError as exc:
            return HttpResponse(
                status_code=503,
                body={
                    "error_code": "SEARCH_INDEX_UNAVAILABLE",
                    "reason": f"projection non searchable: {exc.status.value}",
                },
            )
        except SearchIndexUnavailableError as exc:
            return HttpResponse(
                status_code=503,
                body={"error_code": "SEARCH_INDEX_UNAVAILABLE", "reason": exc.reason},
            )
        except SearchTracePersistenceError:
            return HttpResponse(
                status_code=503,
                body={"error_code": "SEARCH_INDEX_UNAVAILABLE", "reason": "trace non persistee"},
            )

        return HttpResponse(
            status_code=200,
            body=SearchResponseDto.from_domain(response).to_payload(),
        )

    def _profile_for_id(self, search_profile_id: str) -> HybridRetrievalPolicy:
        try:
            hybrid_policy = self._search_profile_catalog.profile_for_id(search_profile_id)
        except ValueError:
            raise SearchProfileUnsupportedError(search_profile_id)
        if not isinstance(hybrid_policy, HybridRetrievalPolicy):
            raise SearchProfileUnsupportedError(search_profile_id)
        return hybrid_policy


def _ensure_http_request(value: HttpRequest) -> HttpRequest:
    if not isinstance(value, HttpRequest):
        raise ValueError("requête HTTP invalide")
    return value


def _ensure_projection_id(value: Any) -> str:
    try:
        return str(DomainIdentifier.parse_with_prefix(_ensure_text(value, "projection_id"), "PROJ"))
    except ValueError as exc:
        raise SearchHttpRequestValidationError("projection_id invalide", field="projection_id") from exc


def _ensure_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise SearchHttpRequestValidationError(f"{field_name} non textuel", field=field_name)
    if value.strip() == "":
        raise SearchHttpRequestValidationError(f"{field_name} vide", field=field_name)
    if value != value.strip():
        raise SearchHttpRequestValidationError(f"{field_name} non normalisé", field=field_name)
    return value


def _ensure_authenticated_search_context(value: Any) -> str:
    context = _ensure_text(value, "authenticated_context")
    if context not in _ALLOWED_REQUESTING_CONTEXTS:
        raise SearchHttpRequestValidationError(
            "authenticated_context inconnu",
            field="authenticated_context",
        )
    return context


def _ensure_mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise SearchHttpRequestValidationError(f"{field_name} non objet", field=field_name)
    return dict(value)


def _ensure_query_text(value: Any) -> str:
    text = _ensure_text(value, "query_text")
    if len(text) > _MAX_QUERY_TEXT_CHARACTERS:
        raise SearchHttpRequestValidationError("query_text trop long", field="query_text")
    return text


def _ensure_filter_mapping(value: Any) -> dict[str, Any]:
    filters = _ensure_mapping(value, "filters")
    for dimension, raw_filter_value in filters.items():
        _ensure_text(dimension, "filters")
        if isinstance(raw_filter_value, str):
            value_count = 1
        elif isinstance(raw_filter_value, Mapping):
            value_count = len(raw_filter_value)
        elif isinstance(raw_filter_value, tuple) or isinstance(raw_filter_value, list):
            value_count = len(raw_filter_value)
        else:
            value_count = 1
        if value_count > _MAX_FILTER_VALUES_PER_DIMENSION:
            raise SearchHttpRequestValidationError("filters trop volumineux", field="filters")
    return filters


def _bad_request_response(field_name: str) -> HttpResponse:
    return HttpResponse(
        status_code=400,
        body={"error_code": "HTTP_REQUEST_INVALID", "field": field_name},
    )


def _search_profile_unsupported_response(reason: str) -> HttpResponse:
    return HttpResponse(
        status_code=422,
        body={"error_code": "SEARCH_PROFILE_UNSUPPORTED", "reason": reason},
    )


__all__ = [
    "HttpRequest",
    "HttpResponse",
    "KnowledgeSearchCommandPort",
    "KnowledgeSearchHttpAdapter",
    "SearchProfileCatalog",
    "SearchRequestDto",
    "SearchResponseDto",
]
