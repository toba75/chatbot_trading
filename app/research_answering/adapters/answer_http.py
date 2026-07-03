"""Adaptateur HTTP public pour la commande RA de réponse documentaire."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from app.research_answering.application.answer_question import (
    AnswerQuestion,
    AnswerQuestionResult,
)
from app.research_answering.application.deep_research import (
    DeepResearchRequest,
    DeepResearchResult,
)


_ANSWER_BODY_FIELDS = frozenset(
    {
        "resolved_question",
        "research_mandate",
        "requested_mode",
        "idempotency_key",
        "occurred_at",
    }
)
_EXPLICITLY_FORBIDDEN_BODY_FIELDS = frozenset(
    {
        "qdrant_collection",
        "qdrant_point_id",
        "eg_registry_table",
        "sp_table",
        "prompt_override",
        "support_status_override",
        "draft_text_as_final",
    }
)
_KNOWN_AUTHENTICATED_CONTEXTS = frozenset({"API", "CV", "RA", "KA", "EG", "SP", "SD", "EX"})
_ALLOWED_ANSWER_CONTEXTS = frozenset({"API", "CV", "RA"})
_ALLOWED_DEEP_RESEARCH_CONTEXTS = frozenset({"API", "CV", "RA"})
_PUBLIC_DOMAIN_ERRORS = {
    "RESEARCH_MANDATE_REQUIRED": (422, "RESEARCH_MANDATE_REQUIRED"),
    "EVIDENCE_SET_NOT_SEALED": (409, "EVIDENCE_SET_NOT_SEALED"),
    "ANSWER_ASSERTION_UNSUPPORTED": (422, "ANSWER_ASSERTION_UNSUPPORTED"),
    "ANSWER_CITATION_UNRESOLVABLE": (422, "ANSWER_CITATION_UNRESOLVABLE"),
    "ANSWER_CONFLICT_UNRESOLVED": (409, "ANSWER_CONFLICT_UNRESOLVED"),
    "INSUFFICIENT_EVIDENCE": (422, "INSUFFICIENT_EVIDENCE"),
    "CURRENT_DATA_REQUIRED": (422, "CURRENT_DATA_REQUIRED"),
    "ANSWER_PUBLICATION_FORBIDDEN": (409, "ANSWER_PUBLICATION_FORBIDDEN"),
    "RA_POLICY_MISSING": (422, "RA_POLICY_MISSING"),
}


class AnswerQuestionHandlerPort(Protocol):
    """Port applicatif RA appelé par l'adaptateur HTTP."""

    def answer(self, command: AnswerQuestion) -> AnswerQuestionResult:
        """Exécute la commande de réponse documentaire."""


class DeepResearchHandlerPort(Protocol):
    """Port applicatif RA appele par l'adaptateur HTTP approfondi."""

    def research(self, command: DeepResearchRequest) -> DeepResearchResult:
        """Execute la commande de recherche approfondie."""


class AnswerHttpRequestValidationError(ValueError):
    """Erreur de validation transport avec code public stable."""

    def __init__(self, message: str, *, field: str, error_code: str, status_code: int) -> None:
        self.field = _ensure_plain_text(field, "field")
        self.error_code = _ensure_plain_text(error_code, "error_code")
        self.status_code = _ensure_status_code(status_code)
        super().__init__(message)


@dataclass(frozen=True)
class HttpRequest:
    """Requête HTTP minimale et testable sans framework."""

    method: str
    path: str
    body: Mapping[str, Any]
    authenticated_context: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "method", _ensure_http_method(self.method))
        object.__setattr__(self, "path", _ensure_path(self.path))
        object.__setattr__(self, "body", _ensure_mapping(self.body, "body"))
        object.__setattr__(
            self,
            "authenticated_context",
            _ensure_authenticated_context(self.authenticated_context),
        )


@dataclass(frozen=True)
class HttpResponse:
    """Réponse HTTP minimale et stable pour le contrat RA."""

    status_code: int
    body: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "status_code", _ensure_status_code(self.status_code))
        object.__setattr__(self, "body", _ensure_mapping(self.body, "body"))


@dataclass(frozen=True)
class AnswerRequestDto:
    """DTO public de requête `POST /v1/answer`."""

    resolved_question: str
    research_mandate: Mapping[str, Any]
    requested_mode: str
    idempotency_key: str
    occurred_at: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "AnswerRequestDto":
        parsed_payload = _ensure_mapping(payload, "body")
        actual_fields = frozenset(parsed_payload.keys())
        if len(actual_fields & _EXPLICITLY_FORBIDDEN_BODY_FIELDS) > 0:
            raise AnswerHttpRequestValidationError(
                "body champ interdit",
                field="body",
                error_code="HTTP_REQUEST_INVALID",
                status_code=400,
            )
        unexpected_fields = actual_fields - _ANSWER_BODY_FIELDS
        if len(unexpected_fields) > 0:
            raise AnswerHttpRequestValidationError(
                f"body champ interdit: {sorted(unexpected_fields)[0]}",
                field="body",
                error_code="HTTP_REQUEST_INVALID",
                status_code=400,
            )
        missing_fields = _ANSWER_BODY_FIELDS - actual_fields
        if len(missing_fields) > 0:
            missing_field = sorted(missing_fields)[0]
            if missing_field == "research_mandate":
                raise AnswerHttpRequestValidationError(
                    "research_mandate absent",
                    field="research_mandate",
                    error_code="RESEARCH_MANDATE_REQUIRED",
                    status_code=422,
                )
            raise AnswerHttpRequestValidationError(
                f"{missing_field} absent",
                field=missing_field,
                error_code="HTTP_REQUEST_INVALID",
                status_code=400,
            )
        return cls(
            resolved_question=parsed_payload["resolved_question"],
            research_mandate=parsed_payload["research_mandate"],
            requested_mode=parsed_payload["requested_mode"],
            idempotency_key=parsed_payload["idempotency_key"],
            occurred_at=parsed_payload["occurred_at"],
        )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "resolved_question",
            _ensure_request_text(self.resolved_question, "resolved_question"),
        )
        object.__setattr__(
            self,
            "research_mandate",
            _ensure_research_mandate(self.research_mandate),
        )
        object.__setattr__(
            self,
            "requested_mode",
            _ensure_request_text(self.requested_mode, "requested_mode"),
        )
        object.__setattr__(
            self,
            "idempotency_key",
            _ensure_request_text(self.idempotency_key, "idempotency_key"),
        )
        object.__setattr__(
            self,
            "occurred_at",
            _ensure_request_text(self.occurred_at, "occurred_at"),
        )

    def to_command(self, *, authenticated_context: str) -> AnswerQuestion:
        return AnswerQuestion.from_payload(
            {
                "resolved_question": self.resolved_question,
                "research_mandate": self.research_mandate,
                "requested_mode": self.requested_mode,
                "idempotency_key": self.idempotency_key,
                "occurred_at": self.occurred_at,
            },
            requested_by_context=_ensure_answer_context(authenticated_context),
        )


class AnswerHttpAdapter:
    """Route explicitement POST /v1/answer côté RA."""

    def __init__(
        self,
        *,
        answer_question_handler: AnswerQuestionHandlerPort,
        deep_research_handler: DeepResearchHandlerPort | None = None,
    ) -> None:
        if not callable(getattr(answer_question_handler, "answer", None)):
            raise ValueError("answer_question_handler sans AnswerQuestion")
        if deep_research_handler is not None and not callable(
            getattr(deep_research_handler, "research", None)
        ):
            raise ValueError("deep_research_handler sans DeepResearchRequest")
        self._answer_question_handler = answer_question_handler
        self._deep_research_handler = deep_research_handler

    def handle(self, request: HttpRequest) -> HttpResponse:
        parsed_request = _ensure_http_request(request)
        if parsed_request.method == "POST" and parsed_request.path == "/v1/answer":
            return self._handle_answer(parsed_request)
        if parsed_request.method == "POST" and parsed_request.path == "/v1/research/deep":
            return self._handle_deep_research(parsed_request)
        return HttpResponse(
            status_code=404,
            body={"error_code": "ENDPOINT_NOT_FOUND", "path": parsed_request.path},
        )

    def _handle_answer(self, request: HttpRequest) -> HttpResponse:
        if request.authenticated_context not in _ALLOWED_ANSWER_CONTEXTS:
            return _public_error_response("ANSWER_CONTEXT_FORBIDDEN", 403)

        try:
            request_dto = AnswerRequestDto.from_payload(request.body)
            command = request_dto.to_command(authenticated_context=request.authenticated_context)
        except AnswerHttpRequestValidationError as exc:
            return _validation_error_response(exc)
        except ValueError as exc:
            if _is_missing_research_mandate_error(exc):
                return HttpResponse(
                    status_code=422,
                    body={"error_code": "RESEARCH_MANDATE_REQUIRED", "field": "research_mandate"},
                )
            return _bad_request_response("body")

        try:
            result = self._answer_question_handler.answer(command)
            if not isinstance(result, AnswerQuestionResult):
                raise ValueError("answer_question_result invalide")
            public_payload = result.to_public_payload()
        except ValueError as exc:
            return _domain_error_response(exc)

        return HttpResponse(status_code=200, body=public_payload)

    def _handle_deep_research(self, request: HttpRequest) -> HttpResponse:
        if self._deep_research_handler is None:
            return HttpResponse(
                status_code=404,
                body={"error_code": "ENDPOINT_NOT_FOUND", "path": request.path},
            )
        if request.authenticated_context not in _ALLOWED_DEEP_RESEARCH_CONTEXTS:
            return _public_error_response("DEEP_RESEARCH_CONTEXT_FORBIDDEN", 403)

        try:
            command = DeepResearchRequest.from_payload(
                request.body,
                requested_by_context=request.authenticated_context,
            )
        except ValueError as exc:
            return _deep_research_request_error_response(exc)

        try:
            result = self._deep_research_handler.research(command)
            if not isinstance(result, DeepResearchResult):
                raise ValueError("deep_research_result invalide")
            public_payload = result.to_public_payload()
        except ValueError as exc:
            return _deep_research_domain_error_response(exc)

        return HttpResponse(status_code=200, body=public_payload)


def _deep_research_request_error_response(exc: ValueError) -> HttpResponse:
    message = str(exc)
    if message.startswith("body champ stockage interdit:"):
        return HttpResponse(
            status_code=400,
            body={"error_code": "PUBLIC_STORAGE_FIELD_FORBIDDEN", "field": "body"},
        )
    if message in {"research_mandate absent", "research_mandate vide"}:
        return HttpResponse(
            status_code=422,
            body={"error_code": "DEEP_RESEARCH_MANDATE_REQUIRED", "field": "research_mandate"},
        )
    if message.startswith("research_mandate absent") or message.startswith("research_mandate vide"):
        return HttpResponse(
            status_code=422,
            body={"error_code": "DEEP_RESEARCH_MANDATE_REQUIRED", "field": "research_mandate"},
        )
    if message.startswith("research_mandate "):
        return _bad_request_response("body")
    if message.startswith("research_mode ") or message.startswith("requested_mode "):
        return HttpResponse(
            status_code=422,
            body={"error_code": "DEEP_RESEARCH_MODE_REQUIRED", "field": "research_mode"},
        )
    return _bad_request_response("body")


def _deep_research_domain_error_response(exc: ValueError) -> HttpResponse:
    message = str(exc).strip()
    public_errors = {
        "DEEP_RESEARCH_PLAN_REQUIRED": (409, "DEEP_RESEARCH_PLAN_REQUIRED"),
        "deep_research_plan": (409, "DEEP_RESEARCH_PLAN_REQUIRED"),
        "COVERAGE_OBLIGATION_MISSING": (422, "COVERAGE_OBLIGATION_MISSING"),
        "COVERAGE_INSUFFICIENT": (422, "COVERAGE_INSUFFICIENT"),
        "SOURCE_DIVERSIFICATION_INSUFFICIENT": (422, "SOURCE_DIVERSIFICATION_INSUFFICIENT"),
        "CLAIM_DEPENDENCY_UNRESOLVED": (409, "CLAIM_DEPENDENCY_UNRESOLVED"),
        "dependency_group": (409, "CLAIM_DEPENDENCY_UNRESOLVED"),
        "CONTRADICTION_UNCLASSIFIED": (409, "CONTRADICTION_UNCLASSIFIED"),
        "DEEP_RESEARCH_SYNTHESIS_UNSUPPORTED": (422, "DEEP_RESEARCH_SYNTHESIS_UNSUPPORTED"),
        "CURRENT_DATA_REQUIRED": (422, "CURRENT_DATA_REQUIRED"),
        "DEEP_RESEARCH_POLICY_MISSING": (422, "DEEP_RESEARCH_POLICY_MISSING"),
    }
    error_code = message.split(":", 1)[0].split(" ", 1)[0]
    if error_code in public_errors:
        status_code, public_error_code = public_errors[error_code]
        return _public_error_response(public_error_code, status_code)
    return _bad_request_response("body")


def _validation_error_response(exc: AnswerHttpRequestValidationError) -> HttpResponse:
    body = {"error_code": exc.error_code}
    if exc.field != "":
        body["field"] = exc.field
    return HttpResponse(status_code=exc.status_code, body=body)


def _domain_error_response(exc: ValueError) -> HttpResponse:
    error_code = _public_domain_error_code(str(exc))
    if error_code is not None:
        status_code, public_error_code = _PUBLIC_DOMAIN_ERRORS[error_code]
        return _public_error_response(public_error_code, status_code)
    return _bad_request_response("body")


def _public_domain_error_code(message: str) -> str | None:
    normalized = message.strip()
    if normalized in _PUBLIC_DOMAIN_ERRORS:
        return normalized
    for separator in (":", " "):
        candidate = normalized.split(separator, 1)[0]
        if candidate in _PUBLIC_DOMAIN_ERRORS:
            return candidate
    return None


def _is_missing_research_mandate_error(exc: ValueError) -> bool:
    return str(exc).strip() == "research_mandate absent"


def _public_error_response(error_code: str, status_code: int) -> HttpResponse:
    return HttpResponse(status_code=status_code, body={"error_code": error_code})


def _bad_request_response(field_name: str) -> HttpResponse:
    return HttpResponse(
        status_code=400,
        body={"error_code": "HTTP_REQUEST_INVALID", "field": field_name},
    )


def _ensure_http_request(value: object) -> HttpRequest:
    if not isinstance(value, HttpRequest):
        raise ValueError("requête HTTP invalide")
    return value


def _ensure_http_method(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("méthode HTTP invalide")
    if value.strip() == "":
        raise ValueError("méthode HTTP vide")
    if value != value.strip():
        raise ValueError("méthode HTTP non normalisée")
    if value != value.upper():
        raise ValueError("méthode HTTP non normalisée")
    return value


def _ensure_path(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("chemin HTTP invalide")
    if value.strip() == "":
        raise ValueError("chemin HTTP vide")
    if value != value.strip():
        raise ValueError("chemin HTTP non normalisé")
    if not value.startswith("/"):
        raise ValueError("chemin HTTP invalide")
    return value


def _ensure_mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")
    return dict(value)


def _ensure_research_mandate(value: Any) -> Mapping[str, Any]:
    mandate = _ensure_mapping(value, "research_mandate")
    if len(mandate) == 0:
        raise AnswerHttpRequestValidationError(
            "research_mandate vide",
            field="research_mandate",
            error_code="RESEARCH_MANDATE_REQUIRED",
            status_code=422,
        )
    return mandate


def _ensure_status_code(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("status_code invalide")
    if value < 100 or value > 599:
        raise ValueError("status_code invalide")
    return value


def _ensure_authenticated_context(value: Any) -> str:
    context = _ensure_request_text(value, "authenticated_context")
    if context not in _KNOWN_AUTHENTICATED_CONTEXTS:
        raise ValueError("authenticated_context inconnu")
    return context


def _ensure_answer_context(value: Any) -> str:
    context = _ensure_request_text(value, "authenticated_context")
    if context not in _ALLOWED_ANSWER_CONTEXTS:
        raise ValueError("authenticated_context interdit")
    return context


def _ensure_request_text(value: Any, field_name: str) -> str:
    try:
        return _ensure_plain_text(value, field_name)
    except ValueError as exc:
        raise AnswerHttpRequestValidationError(
            str(exc),
            field=field_name,
            error_code="HTTP_REQUEST_INVALID",
            status_code=400,
        ) from exc


def _ensure_plain_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalisé")
    return value


__all__ = [
    "AnswerHttpAdapter",
    "AnswerHttpRequestValidationError",
    "AnswerQuestionHandlerPort",
    "AnswerRequestDto",
    "DeepResearchHandlerPort",
    "HttpRequest",
    "HttpResponse",
]
