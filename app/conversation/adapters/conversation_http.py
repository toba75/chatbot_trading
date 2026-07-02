"""HTTP adapter for CV conversations and archival."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from app.conversation.application.append_turn import (
    AppendUserTurnCommand,
    AppendUserTurnHandler,
)
from app.conversation.application.start_conversation import (
    StartConversationCommand,
    StartConversationHandler,
)
from app.conversation.domain.conversation import Conversation, ConversationStatus, ConversationTurn


_CONVERSATION_CREATE_FIELDS = frozenset(
    {"title", "default_mandate", "presentation_preferences", "occurred_at"}
)
_MESSAGE_FIELDS = frozenset(
    {
        "idempotency_key",
        "message",
        "occurred_at",
        "requested_mode",
        "research_mandate",
        "selected_documents",
    }
)
_ARCHIVE_FIELDS = frozenset({"occurred_at"})
_FORBIDDEN_BODY_FIELDS = frozenset(
    {
        "default_mode_fallback",
        "eg_registry_table",
        "prompt_override",
        "qdrant_collection",
        "qdrant_point_id",
        "ra_storage",
        "storage_table",
        "support_status_override",
        "verified_research_outcome_text",
    }
)


class ConversationRepositoryPort(Protocol):
    """Port required by the CV HTTP adapter."""

    def save(self, conversation: Conversation) -> Conversation:
        """Persist a new conversation."""

    def update(self, conversation: Conversation) -> Conversation:
        """Update an existing conversation."""

    def conversation_for_id(self, conversation_id: str) -> Conversation:
        """Return an existing conversation."""


class TurnRepositoryPort(Protocol):
    """Port required for CV turn reads and writes."""

    def next_sequence_for_conversation(self, conversation_id: str) -> int:
        """Return next turn sequence."""

    def save(self, turn: ConversationTurn) -> ConversationTurn:
        """Persist a turn."""

    def turns_for_conversation(self, conversation_id: str) -> tuple[ConversationTurn, ...]:
        """Return ordered turns."""


class IdFactory(Protocol):
    """Identifier factory used by transport, not by domain policy."""

    def next_id(self) -> str:
        """Return one explicit identifier."""


@dataclass(frozen=True)
class HttpRequest:
    """Minimal HTTP request for framework-free contract tests."""

    method: str
    path: str
    body: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "method", _ensure_http_method(self.method))
        object.__setattr__(self, "path", _ensure_path(self.path))
        object.__setattr__(self, "body", _ensure_mapping(self.body, "body"))


@dataclass(frozen=True)
class HttpResponse:
    """Minimal HTTP response for CV public contract tests."""

    status_code: int
    body: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "status_code", _ensure_status_code(self.status_code))
        object.__setattr__(self, "body", _ensure_mapping(self.body, "body"))


class ConversationHttpAdapter:
    """Routes internal CV conversation endpoints explicitly."""

    def __init__(
        self,
        *,
        conversation_repository: ConversationRepositoryPort,
        turn_repository: TurnRepositoryPort,
        conversation_id_factory: IdFactory,
        turn_id_factory: IdFactory,
        retention_policy_version: str,
    ) -> None:
        if not callable(getattr(conversation_repository, "conversation_for_id", None)):
            raise ValueError("conversation_repository sans conversation_for_id")
        if not callable(getattr(conversation_repository, "save", None)):
            raise ValueError("conversation_repository sans save")
        if not callable(getattr(conversation_repository, "update", None)):
            raise ValueError("conversation_repository sans update")
        if not callable(getattr(turn_repository, "next_sequence_for_conversation", None)):
            raise ValueError("turn_repository sans next_sequence_for_conversation")
        if not callable(getattr(turn_repository, "save", None)):
            raise ValueError("turn_repository sans save")
        if not callable(getattr(turn_repository, "turns_for_conversation", None)):
            raise ValueError("turn_repository sans turns_for_conversation")
        if not callable(getattr(conversation_id_factory, "next_id", None)):
            raise ValueError("conversation_id_factory sans next_id")
        if not callable(getattr(turn_id_factory, "next_id", None)):
            raise ValueError("turn_id_factory sans next_id")
        self._conversation_repository = conversation_repository
        self._turn_repository = turn_repository
        self._start_handler = StartConversationHandler(
            conversation_repository=conversation_repository
        )
        self._append_handler = AppendUserTurnHandler(
            conversation_repository=conversation_repository,
            turn_repository=turn_repository,
        )
        self._conversation_id_factory = conversation_id_factory
        self._turn_id_factory = turn_id_factory
        self._retention_policy_version = _ensure_text(
            retention_policy_version,
            "retention_policy_version",
        )

    def handle(self, request: HttpRequest) -> HttpResponse:
        parsed_request = _ensure_http_request(request)
        if parsed_request.method == "POST" and parsed_request.path == "/v1/conversations":
            return self._handle_create(parsed_request)
        conversation_id = _conversation_id_from_path(parsed_request.path)
        if conversation_id is not None:
            if parsed_request.method == "GET":
                return self._handle_read(conversation_id)
            if parsed_request.method == "DELETE":
                return self._handle_archive(conversation_id, parsed_request)
        turns_conversation_id = _conversation_id_from_turns_path(parsed_request.path)
        if turns_conversation_id is not None and parsed_request.method == "GET":
            return self._handle_turns(turns_conversation_id)
        messages_conversation_id = _conversation_id_from_messages_path(parsed_request.path)
        if messages_conversation_id is not None and parsed_request.method == "POST":
            return self._handle_message(messages_conversation_id, parsed_request)
        return HttpResponse(
            status_code=404,
            body={"error_code": "ENDPOINT_NOT_FOUND", "path": parsed_request.path},
        )

    def _handle_create(self, request: HttpRequest) -> HttpResponse:
        body = request.body
        invalid = _invalid_body_field(body, _CONVERSATION_CREATE_FIELDS)
        if invalid is not None:
            return _bad_request_response("body")
        missing = _missing_field(body, _CONVERSATION_CREATE_FIELDS)
        if missing is not None:
            return _bad_request_response(missing)
        try:
            conversation_id = self._conversation_id_factory.next_id()
            result = self._start_handler.start(
                StartConversationCommand(
                    conversation_id=conversation_id,
                    title=body["title"],
                    default_mandate=body["default_mandate"],
                    presentation_preferences=body["presentation_preferences"],
                    occurred_at=body["occurred_at"],
                )
            )
            conversation = self._conversation_repository.conversation_for_id(
                result.conversation_id
            )
        except ValueError:
            return _bad_request_response("body")
        return HttpResponse(status_code=201, body=_conversation_payload(conversation))

    def _handle_read(self, conversation_id: str) -> HttpResponse:
        try:
            conversation = self._conversation_repository.conversation_for_id(conversation_id)
        except ValueError:
            return _not_found_response()
        return HttpResponse(status_code=200, body=_conversation_payload(conversation))

    def _handle_turns(self, conversation_id: str) -> HttpResponse:
        try:
            self._conversation_repository.conversation_for_id(conversation_id)
            turns = self._turn_repository.turns_for_conversation(conversation_id)
        except ValueError:
            return _not_found_response()
        return HttpResponse(
            status_code=200,
            body={
                "conversation_id": conversation_id,
                "next_page_token": None,
                "turns": tuple(_turn_payload(turn) for turn in turns),
            },
        )

    def _handle_message(self, conversation_id: str, request: HttpRequest) -> HttpResponse:
        body = request.body
        invalid = _invalid_body_field(body, _MESSAGE_FIELDS)
        if invalid is not None:
            return _bad_request_response("body")
        for required in ("idempotency_key", "message", "occurred_at"):
            if required not in body:
                return _bad_request_response(required)
        try:
            conversation = self._conversation_repository.conversation_for_id(conversation_id)
            if conversation.status is ConversationStatus.ARCHIVED:
                return _archived_response()
            turn_id = self._turn_id_factory.next_id()
            result = self._append_handler.append_user_turn(
                AppendUserTurnCommand(
                    conversation_id=conversation_id,
                    turn_id=turn_id,
                    message=body["message"],
                    idempotency_key=body["idempotency_key"],
                    occurred_at=body["occurred_at"],
                )
            )
        except ValueError as exc:
            if str(exc).startswith("conversation inconnue"):
                return _not_found_response()
            if str(exc) == "conversation archivee":
                return _archived_response()
            return _bad_request_response("body")
        return HttpResponse(
            status_code=200,
            body={
                "conversation_id": result.conversation_id,
                "sequence": result.sequence,
                "status": result.status,
                "turn_id": result.turn_id,
            },
        )

    def _handle_archive(self, conversation_id: str, request: HttpRequest) -> HttpResponse:
        body = request.body
        invalid = _invalid_body_field(body, _ARCHIVE_FIELDS)
        if invalid is not None:
            return _bad_request_response("body")
        if "occurred_at" not in body:
            return _bad_request_response("occurred_at")
        try:
            conversation = self._conversation_repository.conversation_for_id(conversation_id)
            if conversation.status is ConversationStatus.ARCHIVED:
                return _archived_response()
            archived = conversation.archive(
                archived_at=body["occurred_at"],
                retention_policy_version=self._retention_policy_version,
            )
            saved = self._conversation_repository.update(archived)
        except ValueError as exc:
            if str(exc).startswith("conversation inconnue"):
                return _not_found_response()
            if str(exc) == "conversation archivee":
                return _archived_response()
            return _bad_request_response("body")
        return HttpResponse(
            status_code=200,
            body={
                "archived_at": saved.archived_at,
                "conversation_id": saved.conversation_id,
                "status": saved.status.value,
            },
        )


def _conversation_payload(conversation: Conversation) -> Mapping[str, Any]:
    updated_at = conversation.archived_at if conversation.archived_at is not None else conversation.created_at
    return {
        "conversation_id": conversation.conversation_id,
        "created_at": conversation.created_at,
        "status": conversation.status.value,
        "title": conversation.title,
        "updated_at": updated_at,
    }


def _turn_payload(turn: ConversationTurn) -> Mapping[str, Any]:
    return {
        "conversation_id": turn.conversation_id,
        "message": turn.message,
        "occurred_at": turn.occurred_at,
        "role": turn.role.value,
        "sequence": turn.sequence,
        "turn_id": turn.turn_id,
    }


def _conversation_id_from_path(path: str) -> str | None:
    prefix = "/v1/conversations/"
    if not path.startswith(prefix):
        return None
    suffix = path[len(prefix) :]
    if "/" in suffix or suffix == "":
        return None
    return suffix


def _conversation_id_from_turns_path(path: str) -> str | None:
    prefix = "/v1/conversations/"
    suffix = "/turns"
    if not path.startswith(prefix) or not path.endswith(suffix):
        return None
    conversation_id = path[len(prefix) : -len(suffix)]
    if conversation_id == "" or "/" in conversation_id:
        return None
    return conversation_id


def _conversation_id_from_messages_path(path: str) -> str | None:
    prefix = "/v1/conversations/"
    suffix = "/messages"
    if not path.startswith(prefix) or not path.endswith(suffix):
        return None
    conversation_id = path[len(prefix) : -len(suffix)]
    if conversation_id == "" or "/" in conversation_id:
        return None
    return conversation_id


def _invalid_body_field(body: Mapping[str, Any], allowed_fields: frozenset[str]) -> str | None:
    actual_fields = frozenset(body.keys())
    forbidden = actual_fields & _FORBIDDEN_BODY_FIELDS
    if len(forbidden) > 0:
        return sorted(forbidden)[0]
    unexpected = actual_fields - allowed_fields
    if len(unexpected) > 0:
        return sorted(unexpected)[0]
    return None


def _missing_field(body: Mapping[str, Any], expected_fields: frozenset[str]) -> str | None:
    missing = expected_fields - frozenset(body.keys())
    if len(missing) == 0:
        return None
    return sorted(missing)[0]


def _bad_request_response(field_name: str) -> HttpResponse:
    return HttpResponse(
        status_code=400,
        body={"error_code": "HTTP_REQUEST_INVALID", "field": field_name},
    )


def _not_found_response() -> HttpResponse:
    return HttpResponse(status_code=404, body={"error_code": "CONVERSATION_NOT_FOUND"})


def _archived_response() -> HttpResponse:
    return HttpResponse(status_code=409, body={"error_code": "CONVERSATION_ARCHIVED"})


def _ensure_http_request(value: object) -> HttpRequest:
    if not isinstance(value, HttpRequest):
        raise ValueError("requete HTTP invalide")
    return value


def _ensure_http_method(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("methode HTTP invalide")
    if value.strip() == "":
        raise ValueError("methode HTTP vide")
    if value != value.strip() or value != value.upper():
        raise ValueError("methode HTTP non normalisee")
    return value


def _ensure_path(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("chemin HTTP invalide")
    if value.strip() == "":
        raise ValueError("chemin HTTP vide")
    if value != value.strip() or not value.startswith("/"):
        raise ValueError("chemin HTTP invalide")
    return value


def _ensure_mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")
    return dict(value)


def _ensure_status_code(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("status_code invalide")
    if value < 100 or value > 599:
        raise ValueError("status_code invalide")
    return value


def _ensure_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


__all__ = [
    "ConversationHttpAdapter",
    "ConversationRepositoryPort",
    "HttpRequest",
    "HttpResponse",
    "IdFactory",
    "TurnRepositoryPort",
]
