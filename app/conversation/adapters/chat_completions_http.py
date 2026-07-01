"""Compatible chat completions adapter for CV conversations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Protocol

from app.conversation.application.answer_conversation_turn import PublicResearchAnswerResult
from app.conversation.application.append_turn import (
    AppendUserTurnCommand,
    AppendUserTurnHandler,
)
from app.conversation.application.present_conversation_answer import (
    PresentConversationAnswerCommand,
    PresentConversationAnswerHandler,
)
from app.conversation.domain.conversation import (
    Conversation,
    ConversationStatus,
    ConversationTurn,
)


_CHAT_COMPLETIONS_FIELDS = frozenset(
    {"conversation_id", "idempotency_key", "messages", "model", "occurred_at"}
)
_MESSAGE_FIELDS = frozenset({"content", "role"})
_FORBIDDEN_BODY_FIELDS = frozenset(
    {
        "default_mode_fallback",
        "direct_llm_url",
        "eg_registry_table",
        "llm_backend",
        "max_tokens",
        "prompt_override",
        "qdrant_collection",
        "ra_storage",
        "response_format",
        "stream",
        "support_status_override",
        "system_prompt",
        "temperature",
        "tool_choice",
        "tools",
        "top_p",
        "vllm_endpoint",
    }
)
_FORBIDDEN_PUBLIC_TOKENS = (
    "direct_llm_url",
    "eg_registry",
    "llm_backend",
    "prompt_override",
    "qdrant",
    "ra_storage",
    "system_prompt",
    "vllm",
)


class ConversationRepositoryPort(Protocol):
    """Port used by the chat compatibility adapter."""

    def conversation_for_id(self, conversation_id: str) -> Conversation:
        """Return an existing conversation."""


class TurnRepositoryPort(Protocol):
    """Port used to append user turns before answering."""

    def next_sequence_for_conversation(self, conversation_id: str) -> int:
        """Return next turn sequence."""

    def save(self, turn: ConversationTurn) -> ConversationTurn:
        """Persist one turn."""


class IdFactory(Protocol):
    """Explicit identifier factory."""

    def next_id(self) -> str:
        """Return one identifier."""


class ChatCompletionAnswerProvider(Protocol):
    """Application port called after the compatible request is mapped to CV."""

    def answer(self, request: "ChatCompletionAnswerRequest") -> PublicResearchAnswerResult:
        """Return one public RA answer result."""


@dataclass(frozen=True)
class HttpRequest:
    """Minimal framework-free HTTP request."""

    method: str
    path: str
    body: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "method", _ensure_http_method(self.method))
        object.__setattr__(self, "path", _ensure_path(self.path))
        object.__setattr__(self, "body", _ensure_mapping(self.body, "body"))


@dataclass(frozen=True)
class HttpResponse:
    """Minimal framework-free HTTP response."""

    status_code: int
    body: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "status_code", _ensure_status_code(self.status_code))
        object.__setattr__(self, "body", _ensure_mapping(self.body, "body"))


@dataclass(frozen=True)
class ChatCompletionAnswerRequest:
    """CV request handed to the answer provider after strict HTTP mapping."""

    conversation_id: str
    turn_id: str
    user_message: str
    research_mandate: Mapping[str, Any]
    model: str
    requested_by_context: str
    occurred_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "conversation_id", _ensure_conversation_id(self.conversation_id))
        object.__setattr__(self, "turn_id", _ensure_turn_id(self.turn_id))
        object.__setattr__(self, "user_message", _ensure_public_text(self.user_message, "user_message"))
        object.__setattr__(
            self,
            "research_mandate",
            _freeze_mapping(self.research_mandate, "research_mandate"),
        )
        object.__setattr__(self, "model", _ensure_public_text(self.model, "model"))
        if self.requested_by_context != "CV":
            raise ValueError("requested_by_context CV requis")
        object.__setattr__(self, "occurred_at", _ensure_utc_text(self.occurred_at, "occurred_at"))


@dataclass(frozen=True)
class ChatCompletionRequestDto:
    """Strict DTO for `POST /v1/chat/completions`."""

    model: str
    conversation_id: str
    user_message: str
    idempotency_key: str
    occurred_at: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ChatCompletionRequestDto":
        parsed = _ensure_mapping(payload, "body")
        invalid = _invalid_body_field(parsed)
        if invalid is not None:
            raise ChatCompletionRequestValidationError("body champ interdit", field="body")
        missing = _missing_field(parsed, _CHAT_COMPLETIONS_FIELDS)
        if missing is not None:
            raise ChatCompletionRequestValidationError(f"{missing} absent", field=missing)
        return cls(
            model=parsed["model"],
            conversation_id=parsed["conversation_id"],
            user_message=_user_message_from_messages(parsed["messages"]),
            idempotency_key=parsed["idempotency_key"],
            occurred_at=parsed["occurred_at"],
        )

    def __post_init__(self) -> None:
        object.__setattr__(self, "model", _ensure_public_text(self.model, "model"))
        object.__setattr__(self, "conversation_id", _ensure_conversation_id(self.conversation_id))
        object.__setattr__(self, "user_message", _ensure_public_text(self.user_message, "user_message"))
        object.__setattr__(
            self,
            "idempotency_key",
            _ensure_public_text(self.idempotency_key, "idempotency_key"),
        )
        object.__setattr__(self, "occurred_at", _ensure_utc_text(self.occurred_at, "occurred_at"))


class ChatCompletionRequestValidationError(ValueError):
    """Transport validation error with a stable public field."""

    def __init__(self, message: str, *, field: str) -> None:
        self.field = _ensure_error_field(field)
        super().__init__(message)


class ChatCompletionsHttpAdapter:
    """Routes the compatible chat completions endpoint without owning CV domain."""

    def __init__(
        self,
        *,
        conversation_repository: ConversationRepositoryPort,
        turn_repository: TurnRepositoryPort,
        turn_id_factory: IdFactory,
        answer_provider: ChatCompletionAnswerProvider,
        presenter: PresentConversationAnswerHandler | None = None,
    ) -> None:
        if not callable(getattr(conversation_repository, "conversation_for_id", None)):
            raise ValueError("conversation_repository sans conversation_for_id")
        if not callable(getattr(turn_repository, "next_sequence_for_conversation", None)):
            raise ValueError("turn_repository sans next_sequence_for_conversation")
        if not callable(getattr(turn_repository, "save", None)):
            raise ValueError("turn_repository sans save")
        if not callable(getattr(turn_id_factory, "next_id", None)):
            raise ValueError("turn_id_factory sans next_id")
        if not callable(getattr(answer_provider, "answer", None)):
            raise ValueError("answer_provider sans answer")
        self._conversation_repository = conversation_repository
        self._append_handler = AppendUserTurnHandler(
            conversation_repository=conversation_repository,
            turn_repository=turn_repository,
        )
        self._turn_id_factory = turn_id_factory
        self._answer_provider = answer_provider
        self._presenter = presenter if presenter is not None else PresentConversationAnswerHandler()

    def handle(self, request: HttpRequest) -> HttpResponse:
        parsed_request = _ensure_http_request(request)
        if parsed_request.method == "POST" and parsed_request.path == "/v1/chat/completions":
            return self._handle_chat_completion(parsed_request)
        return HttpResponse(
            status_code=404,
            body={"error_code": "ENDPOINT_NOT_FOUND", "path": parsed_request.path},
        )

    def _handle_chat_completion(self, request: HttpRequest) -> HttpResponse:
        try:
            request_dto = ChatCompletionRequestDto.from_payload(request.body)
        except ChatCompletionRequestValidationError as exc:
            return _bad_request_response(exc.field)
        except ValueError:
            return _bad_request_response("body")

        try:
            conversation = self._conversation_repository.conversation_for_id(
                request_dto.conversation_id
            )
        except ValueError:
            return _not_found_response()

        if conversation.status is ConversationStatus.ARCHIVED:
            return _archived_response()

        try:
            turn_id = self._turn_id_factory.next_id()
            turn = self._append_handler.append_user_turn(
                AppendUserTurnCommand(
                    conversation_id=request_dto.conversation_id,
                    turn_id=turn_id,
                    message=request_dto.user_message,
                    idempotency_key=request_dto.idempotency_key,
                    occurred_at=request_dto.occurred_at,
                )
            )
            answer_request = ChatCompletionAnswerRequest(
                conversation_id=request_dto.conversation_id,
                turn_id=turn.turn_id,
                user_message=request_dto.user_message,
                research_mandate=conversation.default_mandate,
                model=request_dto.model,
                requested_by_context="CV",
                occurred_at=request_dto.occurred_at,
            )
            answer_result = self._answer_provider.answer(answer_request)
            if not isinstance(answer_result, PublicResearchAnswerResult):
                return _answer_invalid_response()
            presented = self._presenter.present(
                PresentConversationAnswerCommand(
                    conversation_id=request_dto.conversation_id,
                    turn_id=turn.turn_id,
                    answer_result=answer_result,
                    occurred_at=request_dto.occurred_at,
                )
            )
        except ValueError as exc:
            if str(exc) == "conversation archivee":
                return _archived_response()
            return _bad_request_response("body")

        body = _chat_completion_payload(
            model=request_dto.model,
            occurred_at=request_dto.occurred_at,
            turn_id=turn.turn_id,
            product_payload=presented.presentation.to_payload(),
        )
        _ensure_no_forbidden_public_tokens(body)
        return HttpResponse(status_code=200, body=body)


def _chat_completion_payload(
    *,
    model: str,
    occurred_at: str,
    turn_id: str,
    product_payload: Mapping[str, Any],
) -> Mapping[str, Any]:
    return MappingProxyType(
        {
            "choices": (
                {
                    "finish_reason": "stop",
                    "index": 0,
                    "message": {
                        "content": product_payload["answer_text"],
                        "role": "assistant",
                    },
                },
            ),
            "created_at": occurred_at,
            "id": f"chatcmpl-{turn_id}",
            "model": model,
            "object": "chat.completion",
            "ost_product": product_payload,
        }
    )


def _invalid_body_field(body: Mapping[str, Any]) -> str | None:
    actual = frozenset(body.keys())
    forbidden = actual & _FORBIDDEN_BODY_FIELDS
    if len(forbidden) > 0:
        return sorted(forbidden)[0]
    unexpected = actual - _CHAT_COMPLETIONS_FIELDS
    if len(unexpected) > 0:
        return sorted(unexpected)[0]
    return None


def _missing_field(body: Mapping[str, Any], expected_fields: frozenset[str]) -> str | None:
    missing = expected_fields - frozenset(body.keys())
    if len(missing) == 0:
        return None
    return sorted(missing)[0]


def _user_message_from_messages(value: object) -> str:
    if value is None or isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ChatCompletionRequestValidationError("messages invalides", field="messages")
    messages = tuple(value)
    if len(messages) != 1:
        raise ChatCompletionRequestValidationError("messages doit contenir un seul user", field="messages")
    message = messages[0]
    if not isinstance(message, Mapping):
        raise ChatCompletionRequestValidationError("message non objet", field="messages")
    actual = frozenset(message.keys())
    if actual - _MESSAGE_FIELDS:
        raise ChatCompletionRequestValidationError("message champ interdit", field="messages")
    if "role" not in message or "content" not in message:
        raise ChatCompletionRequestValidationError("message incomplet", field="messages")
    role = _ensure_public_text(message["role"], "role")
    if role != "user":
        raise ChatCompletionRequestValidationError("role user requis", field="messages")
    return _ensure_public_text(message["content"], "content")


def _bad_request_response(field_name: str) -> HttpResponse:
    return HttpResponse(
        status_code=400,
        body={"error_code": "HTTP_REQUEST_INVALID", "field": field_name},
    )


def _not_found_response() -> HttpResponse:
    return HttpResponse(status_code=404, body={"error_code": "CONVERSATION_NOT_FOUND"})


def _archived_response() -> HttpResponse:
    return HttpResponse(status_code=409, body={"error_code": "CONVERSATION_ARCHIVED"})


def _answer_invalid_response() -> HttpResponse:
    return HttpResponse(status_code=502, body={"error_code": "CHAT_COMPLETION_ANSWER_INVALID"})


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


def _ensure_mapping(value: object, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")
    return dict(value)


def _ensure_status_code(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("status_code invalide")
    if value < 100 or value > 599:
        raise ValueError("status_code invalide")
    return value


def _ensure_conversation_id(value: object) -> str:
    text = _ensure_public_text(value, "conversation_id")
    if not text.startswith("CONV-"):
        raise ValueError("conversation_id invalide")
    return text


def _ensure_turn_id(value: object) -> str:
    text = _ensure_public_text(value, "turn_id")
    if not text.startswith("TURN-"):
        raise ValueError("turn_id invalide")
    return text


def _ensure_error_field(value: object) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise ValueError("field invalide")
    return value


def _ensure_public_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    lowered = value.lower()
    for forbidden in _FORBIDDEN_PUBLIC_TOKENS:
        if forbidden in lowered:
            raise ValueError(f"payload sensible interdit: {forbidden}")
    return value


def _ensure_utc_text(value: object, field_name: str) -> str:
    text = _ensure_public_text(value, field_name)
    if len(text) != 20 or text[4] != "-" or text[7] != "-" or text[10] != "T" or text[19] != "Z":
        raise ValueError(f"{field_name} invalide")
    return text


def _freeze_mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")
    if len(value) == 0:
        raise ValueError(f"{field_name} vide")
    return MappingProxyType(
        {
            _ensure_public_text(key, "cle"): _freeze_value(child, field_name)
            for key, child in value.items()
        }
    )


def _freeze_value(value: object, field_name: str) -> Any:
    if isinstance(value, str):
        return _ensure_public_text(value, field_name)
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, Mapping):
        return _freeze_mapping(value, field_name)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(_freeze_value(child, field_name) for child in value)
    raise ValueError(f"{field_name} invalide")


def _ensure_no_forbidden_public_tokens(value: object) -> None:
    serialized = repr(value).lower()
    for forbidden in _FORBIDDEN_PUBLIC_TOKENS:
        if forbidden in serialized:
            raise ValueError(f"payload sensible interdit: {forbidden}")


__all__ = [
    "ChatCompletionAnswerProvider",
    "ChatCompletionAnswerRequest",
    "ChatCompletionRequestDto",
    "ChatCompletionRequestValidationError",
    "ChatCompletionsHttpAdapter",
    "ConversationRepositoryPort",
    "HttpRequest",
    "HttpResponse",
    "IdFactory",
    "TurnRepositoryPort",
]
