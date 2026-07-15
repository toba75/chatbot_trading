"""Client HTTP strict de l'UI vers le contrat public de conversation CV."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.platform.ui_document_api import (
    UiDocumentApiResponse,
    UiDocumentApiTransport,
)


ORCHESTRATOR_API_UNAVAILABLE = "ORCHESTRATOR_API_UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class UiConversationApiResponse:
    status_code: int
    content_type: str
    body: bytes

    def __post_init__(self) -> None:
        if isinstance(self.status_code, bool) or not isinstance(self.status_code, int):
            raise ValueError("status_code conversation invalide")
        if self.status_code < 100 or self.status_code > 599:
            raise ValueError("status_code conversation invalide")
        _ensure_text(self.content_type, "content_type")
        if not isinstance(self.body, bytes):
            raise ValueError("body conversation invalide")


@dataclass(frozen=True, slots=True)
class UiConversationView:
    conversation_id: str
    title: str
    status: str
    created_at: str
    updated_at: str

    def __post_init__(self) -> None:
        _ensure_identifier(self.conversation_id, "CONV", "conversation_id")
        _ensure_text(self.title, "title")
        if self.status not in {"ACTIVE", "ARCHIVED"}:
            raise ValueError("status conversation invalide")
        _ensure_utc(self.created_at, "created_at")
        _ensure_utc(self.updated_at, "updated_at")


@dataclass(frozen=True, slots=True)
class UiConversationCitation:
    citation_id: str
    evidence_id: str
    quoted_span_hash: str
    source_locator: Mapping[str, Any]

    def __post_init__(self) -> None:
        _ensure_identifier(self.citation_id, "CIT", "citation_id")
        _ensure_identifier(self.evidence_id, "EVS", "evidence_id")
        _ensure_hash(self.quoted_span_hash, "quoted_span_hash")
        locator = dict(_ensure_mapping(self.source_locator, "source_locator"))
        required = {
            "schema_version",
            "canonical_version_id",
            "document_id",
            "page_pdf",
            "item_id",
            "bbox",
            "content_hash",
        }
        if set(locator) != required:
            raise ValueError("source_locator public invalide")
        _ensure_text(locator["schema_version"], "schema_version")
        _ensure_identifier(locator["canonical_version_id"], "CVER", "canonical_version_id")
        _ensure_identifier(locator["document_id"], "DOC", "document_id")
        if isinstance(locator["page_pdf"], bool) or not isinstance(locator["page_pdf"], int) or locator["page_pdf"] < 1:
            raise ValueError("page_pdf invalide")
        _ensure_text(locator["item_id"], "item_id")
        bbox = locator["bbox"]
        if isinstance(bbox, (str, bytes)) or not isinstance(bbox, Sequence) or len(bbox) != 4:
            raise ValueError("bbox invalide")
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in bbox):
            raise ValueError("bbox invalide")
        _ensure_hash(locator["content_hash"], "content_hash")
        object.__setattr__(self, "source_locator", locator)


@dataclass(frozen=True, slots=True)
class UiConversationAnswer:
    conversation_id: str
    turn_id: str
    resolved_question: str
    mode: str
    mode_justification: str
    support_status: str
    answer_id: str
    verified_answer_ref: str
    answer_text: str
    citations: tuple[UiConversationCitation, ...]
    knowledge_gaps: tuple[Mapping[str, Any], ...]
    unresolved_conflicts: tuple[Mapping[str, Any], ...]
    abstention_reason: str | None

    def __post_init__(self) -> None:
        _ensure_identifier(self.conversation_id, "CONV", "conversation_id")
        _ensure_identifier(self.turn_id, "TURN", "turn_id")
        _ensure_text(self.resolved_question, "resolved_question")
        if self.mode != "CHAT_DOCUMENTAIRE":
            raise ValueError("mode conversation non pris en charge par l'UI")
        _ensure_text(self.mode_justification, "mode_justification")
        if self.support_status not in {
            "SUPPORTED",
            "PARTIALLY_SUPPORTED",
            "INSUFFICIENT_EVIDENCE",
            "CONFLICTING_EVIDENCE",
            "REQUIRES_CURRENT_DATA",
        }:
            raise ValueError("support_status invalide")
        _ensure_identifier(self.answer_id, "ANS", "answer_id")
        _ensure_verified_answer_ref(self.verified_answer_ref, self.answer_id)
        _ensure_text(self.answer_text, "answer_text")
        citations = tuple(self.citations)
        if len(citations) == 0:
            raise ValueError("citations absentes")
        if any(not isinstance(citation, UiConversationCitation) for citation in citations):
            raise ValueError("citation conversation invalide")
        if len({citation.citation_id for citation in citations}) != len(citations):
            raise ValueError("citation dupliquee")
        object.__setattr__(self, "citations", citations)
        object.__setattr__(self, "knowledge_gaps", _freeze_mapping_sequence(self.knowledge_gaps, "knowledge_gaps"))
        object.__setattr__(self, "unresolved_conflicts", _freeze_mapping_sequence(self.unresolved_conflicts, "unresolved_conflicts"))
        if self.abstention_reason is not None:
            _ensure_text(self.abstention_reason, "abstention_reason")


class UiConversationApiUnavailableError(ConnectionError):
    """L'unique API orchestratrice n'est pas joignable."""


class UiConversationApiPublicError(RuntimeError):
    def __init__(self, *, status_code: int, payload: Mapping[str, Any]) -> None:
        if not isinstance(status_code, int):
            raise TypeError("status_code erreur conversation invalide")
        public_payload = dict(_ensure_mapping(payload, "erreur conversation"))
        _ensure_text(public_payload.get("error_code"), "error_code")
        self.status_code = status_code
        self.payload = public_payload
        super().__init__(public_payload["error_code"])


class UiConversationApiClient:
    """N'appelle que les endpoints CV, jamais la compatibilité chat externe."""

    def __init__(self, *, transport: UiDocumentApiTransport) -> None:
        if not callable(getattr(transport, "request", None)):
            raise ValueError("transport API conversation UI invalide")
        self._transport = transport

    def create_conversation(
        self,
        *,
        title: str,
        default_mandate: Mapping[str, Any],
        presentation_preferences: Mapping[str, Any],
        occurred_at: str,
    ) -> UiConversationView:
        payload = {
            "title": _ensure_text(title, "title"),
            "default_mandate": dict(_ensure_mapping(default_mandate, "default_mandate")),
            "presentation_preferences": dict(
                _ensure_mapping(presentation_preferences, "presentation_preferences")
            ),
            "occurred_at": _ensure_utc(occurred_at, "occurred_at"),
        }
        response = self._json_request("POST", "/v1/conversations", payload)
        _require_status(response, {201})
        return _conversation_from_payload(response.payload)

    def read_conversation(self, conversation_id: str) -> UiConversationView:
        identifier = _ensure_identifier(conversation_id, "CONV", "conversation_id")
        response = self._json_request("GET", f"/v1/conversations/{identifier}", None)
        _require_status(response, {200})
        return _conversation_from_payload(response.payload)

    def send_message(
        self,
        *,
        conversation_id: str,
        message: str,
        idempotency_key: str,
        occurred_at: str,
        requested_mode: str,
        selected_documents: Sequence[str],
        research_mandate: Mapping[str, Any] | None = None,
    ) -> UiConversationAnswer:
        identifier = _ensure_identifier(conversation_id, "CONV", "conversation_id")
        selected = tuple(
            _ensure_identifier(document_id, "DOC", "selected_documents")
            for document_id in selected_documents
        )
        if len(selected) == 0 or len(selected) != len(set(selected)):
            raise ValueError("selected_documents invalides")
        if requested_mode != "CHAT_DOCUMENTAIRE":
            raise ValueError("requested_mode CHAT_DOCUMENTAIRE requis")
        payload: dict[str, Any] = {
            "message": _ensure_text(message, "message"),
            "idempotency_key": _ensure_text(idempotency_key, "idempotency_key"),
            "occurred_at": _ensure_utc(occurred_at, "occurred_at"),
            "requested_mode": requested_mode,
            "selected_documents": list(selected),
        }
        if research_mandate is not None:
            payload["research_mandate"] = dict(
                _ensure_mapping(research_mandate, "research_mandate")
            )
        response = self._json_request(
            "POST",
            f"/v1/conversations/{identifier}/messages",
            payload,
        )
        _require_status(response, {200})
        return _answer_from_payload(response.payload)

    def _json_request(
        self,
        method: str,
        path: str,
        payload: Mapping[str, Any] | None,
    ) -> "_UiConversationJsonResponse":
        body = None if payload is None else json.dumps(
            dict(payload), ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        try:
            response = self._transport.request(
                method=method,
                path=path,
                body=body,
                content_type="application/json; charset=utf-8",
            )
        except ConnectionError as exc:
            raise UiConversationApiUnavailableError(ORCHESTRATOR_API_UNAVAILABLE) from exc
        raw = UiConversationApiResponse(
            status_code=response.status_code,
            content_type=response.content_type,
            body=response.body,
        )
        if raw.content_type != "application/json":
            raise ValueError("content_type conversation public invalide")
        try:
            parsed = json.loads(raw.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("JSON conversation public invalide") from exc
        return _UiConversationJsonResponse(
            status_code=raw.status_code,
            payload=_ensure_mapping(parsed, "payload conversation"),
        )


@dataclass(frozen=True, slots=True)
class _UiConversationJsonResponse:
    status_code: int
    payload: Mapping[str, Any]


def _require_status(response: _UiConversationJsonResponse, expected: set[int]) -> None:
    if response.status_code in expected:
        return
    raise UiConversationApiPublicError(
        status_code=response.status_code,
        payload=response.payload,
    )


def _conversation_from_payload(payload: Mapping[str, Any]) -> UiConversationView:
    expected = {"conversation_id", "title", "status", "created_at", "updated_at"}
    if set(payload) != expected:
        raise ValueError("contrat conversation publique incompatible")
    return UiConversationView(
        conversation_id=payload["conversation_id"],
        title=payload["title"],
        status=payload["status"],
        created_at=payload["created_at"],
        updated_at=payload["updated_at"],
    )


def _answer_from_payload(payload: Mapping[str, Any]) -> UiConversationAnswer:
    expected = {
        "conversation_id",
        "turn_id",
        "resolved_question",
        "mode",
        "mode_justification",
        "support_status",
        "answer_id",
        "verified_answer_ref",
        "answer_text",
        "citations",
        "knowledge_gaps",
        "unresolved_conflicts",
        "abstention_reason",
    }
    if set(payload) != expected:
        raise ValueError("contrat de réponse conversationnelle incompatible")
    citations_payload = payload["citations"]
    if isinstance(citations_payload, (str, bytes)) or not isinstance(citations_payload, Sequence):
        raise ValueError("citations conversation invalides")
    citations = tuple(
        UiConversationCitation(
            citation_id=_required(item, "citation_id"),
            evidence_id=_required(item, "evidence_id"),
            quoted_span_hash=_required(item, "quoted_span_hash"),
            source_locator=_required(item, "source_locator"),
        )
        for item in citations_payload
        if isinstance(item, Mapping)
    )
    if len(citations) != len(citations_payload):
        raise ValueError("citation conversation invalide")
    return UiConversationAnswer(
        conversation_id=payload["conversation_id"],
        turn_id=payload["turn_id"],
        resolved_question=payload["resolved_question"],
        mode=payload["mode"],
        mode_justification=payload["mode_justification"],
        support_status=payload["support_status"],
        answer_id=payload["answer_id"],
        verified_answer_ref=payload["verified_answer_ref"],
        answer_text=payload["answer_text"],
        citations=citations,
        knowledge_gaps=_freeze_mapping_sequence(payload["knowledge_gaps"], "knowledge_gaps"),
        unresolved_conflicts=_freeze_mapping_sequence(
            payload["unresolved_conflicts"], "unresolved_conflicts"
        ),
        abstention_reason=payload["abstention_reason"],
    )


def _required(value: object, name: str) -> Any:
    mapping = _ensure_mapping(value, "citation")
    if name not in mapping:
        raise ValueError(f"citation {name} absent")
    return mapping[name]


def _freeze_mapping_sequence(value: object, name: str) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"{name} invalide")
    result = tuple(dict(_ensure_mapping(item, name)) for item in value)
    return result


def _ensure_mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} non objet")
    return value


def _ensure_text(value: object, name: str) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise ValueError(f"{name} invalide")
    return value


def _ensure_identifier(value: object, prefix: str, name: str) -> str:
    text = _ensure_text(value, name)
    if not text.startswith(f"{prefix}-"):
        raise ValueError(f"{name} invalide")
    return text


def _ensure_hash(value: object, name: str) -> str:
    text = _ensure_text(value, name)
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise ValueError(f"{name} invalide")
    return text


def _ensure_verified_answer_ref(value: object, answer_id: str) -> str:
    text = _ensure_text(value, "verified_answer_ref")
    if text != f"{answer_id}@1":
        raise ValueError("verified_answer_ref invalide")
    return text


def _ensure_utc(value: object, name: str) -> str:
    text = _ensure_text(value, name)
    if len(text) != 20 or not text.endswith("Z"):
        raise ValueError(f"{name} invalide")
    return text


__all__ = [
    "ORCHESTRATOR_API_UNAVAILABLE",
    "UiConversationAnswer",
    "UiConversationApiClient",
    "UiConversationApiPublicError",
    "UiConversationApiResponse",
    "UiConversationApiUnavailableError",
    "UiConversationCitation",
    "UiConversationView",
]
