"""Contrat HTTP CV natif pour le chat documentaire produit."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
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


_CREATE_FIELDS = frozenset(
    {"title", "default_mandate", "presentation_preferences", "occurred_at"}
)
_MESSAGE_REQUIRED_FIELDS = frozenset(
    {"message", "idempotency_key", "occurred_at", "requested_mode", "selected_documents"}
)
_MESSAGE_FIELDS = _MESSAGE_REQUIRED_FIELDS | frozenset({"research_mandate"})


class ConversationRepositoryPort(Protocol):
    def save(self, conversation: Conversation) -> Conversation: ...
    def update(self, conversation: Conversation) -> Conversation: ...
    def conversation_for_id(self, conversation_id: str) -> Conversation: ...


class TurnRepositoryPort(Protocol):
    def next_sequence_for_conversation(self, conversation_id: str) -> int: ...
    def save(self, turn: ConversationTurn) -> ConversationTurn: ...
    def turns_for_conversation(self, conversation_id: str) -> tuple[ConversationTurn, ...]: ...


class IdFactory(Protocol):
    def next_id(self) -> str: ...


@dataclass(frozen=True, slots=True)
class HttpRequest:
    method: str
    path: str
    body: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "method", _ensure_method(self.method))
        object.__setattr__(self, "path", _ensure_path(self.path))
        object.__setattr__(self, "body", dict(_ensure_mapping(self.body, "body")))


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status_code: int
    body: Mapping[str, Any]

    def __post_init__(self) -> None:
        if isinstance(self.status_code, bool) or not isinstance(self.status_code, int):
            raise ValueError("status_code invalide")
        if not 100 <= self.status_code <= 599:
            raise ValueError("status_code invalide")
        object.__setattr__(self, "body", dict(_ensure_mapping(self.body, "body")))


@dataclass(frozen=True, slots=True)
class ProductConversationRequest:
    conversation_id: str
    turn_id: str
    resolved_question: str
    research_mandate: Mapping[str, Any]
    requested_mode: str
    selected_document_ids: tuple[str, ...]
    occurred_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "conversation_id", _ensure_identifier(self.conversation_id, "CONV", "conversation_id"))
        object.__setattr__(self, "turn_id", _ensure_identifier(self.turn_id, "TURN", "turn_id"))
        object.__setattr__(self, "resolved_question", _ensure_text(self.resolved_question, "resolved_question"))
        object.__setattr__(self, "research_mandate", dict(_ensure_non_empty_mapping(self.research_mandate, "research_mandate")))
        if self.requested_mode != "CHAT_DOCUMENTAIRE":
            raise ValueError("requested_mode CHAT_DOCUMENTAIRE requis")
        selected = tuple(_ensure_identifier(item, "DOC", "selected_documents") for item in self.selected_document_ids)
        if len(selected) == 0 or len(selected) != len(set(selected)):
            raise ValueError("selected_documents invalides")
        object.__setattr__(self, "selected_document_ids", selected)
        object.__setattr__(self, "occurred_at", _ensure_utc(self.occurred_at, "occurred_at"))


@dataclass(frozen=True, slots=True)
class ProductConversationAnswer:
    answer_id: str
    answer_text: str
    citations: tuple[Mapping[str, Any], ...]
    support_status: str
    knowledge_gaps: tuple[Mapping[str, Any], ...]
    unresolved_conflicts: tuple[Mapping[str, Any], ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "answer_id", _ensure_identifier(self.answer_id, "ANS", "answer_id"))
        object.__setattr__(self, "answer_text", _ensure_text(self.answer_text, "answer_text"))
        if self.support_status not in {
            "SUPPORTED",
            "PARTIALLY_SUPPORTED",
            "INSUFFICIENT_EVIDENCE",
            "CONFLICTING_EVIDENCE",
            "REQUIRES_CURRENT_DATA",
        }:
            raise ValueError("support_status invalide")
        citations = tuple(_citation_payload(citation) for citation in self.citations)
        if len(citations) == 0:
            raise ValueError("citations absentes")
        if len({citation["citation_id"] for citation in citations}) != len(citations):
            raise ValueError("citations dupliquees")
        object.__setattr__(self, "citations", citations)
        object.__setattr__(self, "knowledge_gaps", _mapping_sequence(self.knowledge_gaps, "knowledge_gaps"))
        object.__setattr__(self, "unresolved_conflicts", _mapping_sequence(self.unresolved_conflicts, "unresolved_conflicts"))


class ProductConversationAnswerProvider(Protocol):
    def answer(self, request: ProductConversationRequest) -> ProductConversationAnswer: ...


class ProductConversationAnswerError(ValueError):
    """Échec public RA qui interdit la publication d'une réponse de remplacement."""

    def __init__(self, error_code: str) -> None:
        self.error_code = _ensure_error_code(error_code)
        super().__init__(self.error_code)


class ProductConversationHttpAdapter:
    """CV possède le contrat produit et délègue la réponse à RA explicitement."""

    def __init__(
        self,
        *,
        conversation_repository: ConversationRepositoryPort,
        turn_repository: TurnRepositoryPort,
        conversation_id_factory: IdFactory,
        turn_id_factory: IdFactory,
        answer_provider: ProductConversationAnswerProvider,
        retention_policy_version: str,
    ) -> None:
        for repository, methods, name in (
            (conversation_repository, ("save", "update", "conversation_for_id"), "conversation_repository"),
            (turn_repository, ("next_sequence_for_conversation", "save", "turns_for_conversation"), "turn_repository"),
        ):
            if any(not callable(getattr(repository, method, None)) for method in methods):
                raise ValueError(f"{name} incomplet")
        if not callable(getattr(conversation_id_factory, "next_id", None)):
            raise ValueError("conversation_id_factory invalide")
        if not callable(getattr(turn_id_factory, "next_id", None)):
            raise ValueError("turn_id_factory invalide")
        if not callable(getattr(answer_provider, "answer", None)):
            raise ValueError("answer_provider invalide")
        self._conversation_repository = conversation_repository
        self._turn_repository = turn_repository
        self._start_handler = StartConversationHandler(conversation_repository=conversation_repository)
        self._append_handler = AppendUserTurnHandler(
            conversation_repository=conversation_repository,
            turn_repository=turn_repository,
        )
        self._conversation_id_factory = conversation_id_factory
        self._turn_id_factory = turn_id_factory
        self._answer_provider = answer_provider
        self._retention_policy_version = _ensure_text(retention_policy_version, "retention_policy_version")
        self._responses_by_idempotency_key: dict[tuple[str, str], tuple[Mapping[str, Any], Mapping[str, Any]]] = {}
        self._presentations_by_turn_id: dict[str, Mapping[str, Any]] = {}

    def handle(self, request: HttpRequest) -> HttpResponse:
        parsed = _ensure_request(request)
        if parsed.method == "POST" and parsed.path == "/v1/conversations":
            return self._create(parsed.body)
        conversation_id = _conversation_id_from_path(parsed.path, suffix=None)
        if conversation_id is not None:
            if parsed.method == "GET":
                return self._read_conversation(conversation_id)
            if parsed.method == "DELETE":
                return self._archive(conversation_id, parsed.body)
        conversation_id = _conversation_id_from_path(parsed.path, suffix="/turns")
        if conversation_id is not None and parsed.method == "GET":
            return self._read_turns(conversation_id)
        conversation_id = _conversation_id_from_path(parsed.path, suffix="/messages")
        if conversation_id is not None and parsed.method == "POST":
            return self._message(conversation_id, parsed.body)
        return HttpResponse(404, {"error_code": "ENDPOINT_NOT_FOUND", "path": parsed.path})

    def _create(self, body: Mapping[str, Any]) -> HttpResponse:
        if set(body) != _CREATE_FIELDS:
            return _invalid("body")
        try:
            result = self._start_handler.start(
                StartConversationCommand(
                    conversation_id=self._conversation_id_factory.next_id(),
                    title=body["title"],
                    default_mandate=body["default_mandate"],
                    presentation_preferences=body["presentation_preferences"],
                    occurred_at=body["occurred_at"],
                )
            )
            conversation = self._conversation_repository.conversation_for_id(result.conversation_id)
        except ValueError:
            return _invalid("body")
        return HttpResponse(201, _conversation_payload(conversation))

    def _read_conversation(self, conversation_id: str) -> HttpResponse:
        try:
            conversation = self._conversation_repository.conversation_for_id(conversation_id)
        except ValueError:
            return _not_found()
        return HttpResponse(200, _conversation_payload(conversation))

    def _read_turns(self, conversation_id: str) -> HttpResponse:
        try:
            self._conversation_repository.conversation_for_id(conversation_id)
            turns = self._turn_repository.turns_for_conversation(conversation_id)
        except ValueError:
            return _not_found()
        payload_turns = []
        for turn in turns:
            payload = {
                "conversation_id": turn.conversation_id,
                "turn_id": turn.turn_id,
                "sequence": turn.sequence,
                "role": turn.role.value,
                "message": turn.message,
                "occurred_at": turn.occurred_at,
            }
            presentation = self._presentations_by_turn_id.get(turn.turn_id)
            if presentation is not None:
                payload["presentation"] = presentation
            payload_turns.append(payload)
        return HttpResponse(
            200,
            {"conversation_id": conversation_id, "next_page_token": None, "turns": payload_turns},
        )

    def _message(self, conversation_id: str, body: Mapping[str, Any]) -> HttpResponse:
        if not set(body).issubset(_MESSAGE_FIELDS) or not _MESSAGE_REQUIRED_FIELDS.issubset(body):
            return _invalid("body")
        try:
            idempotency_key = _ensure_text(body["idempotency_key"], "idempotency_key")
            cached = self._responses_by_idempotency_key.get((conversation_id, idempotency_key))
            fingerprint = _message_fingerprint(body)
            if cached is not None:
                if cached[0] != fingerprint:
                    return HttpResponse(409, {"error_code": "IDEMPOTENCY_KEY_REUSED"})
                return HttpResponse(200, cached[1])
            conversation = self._conversation_repository.conversation_for_id(conversation_id)
            if conversation.status is ConversationStatus.ARCHIVED:
                return HttpResponse(409, {"error_code": "CONVERSATION_ARCHIVED"})
            turn_result = self._append_handler.append_user_turn(
                AppendUserTurnCommand(
                    conversation_id=conversation_id,
                    turn_id=self._turn_id_factory.next_id(),
                    message=body["message"],
                    idempotency_key=idempotency_key,
                    occurred_at=body["occurred_at"],
                )
            )
            answer = self._answer_provider.answer(
                ProductConversationRequest(
                    conversation_id=conversation_id,
                    turn_id=turn_result.turn_id,
                    resolved_question=body["message"],
                    research_mandate=(
                        body["research_mandate"]
                        if "research_mandate" in body
                        else conversation.default_mandate
                    ),
                    requested_mode=body["requested_mode"],
                    selected_document_ids=tuple(body["selected_documents"]),
                    occurred_at=body["occurred_at"],
                )
            )
            if not isinstance(answer, ProductConversationAnswer):
                raise ValueError("answer_provider réponse invalide")
        except ProductConversationAnswerError as exc:
            return HttpResponse(422, {"error_code": exc.error_code})
        except ValueError as exc:
            if str(exc).startswith("conversation inconnue"):
                return _not_found()
            if str(exc) == "conversation archivee":
                return HttpResponse(409, {"error_code": "CONVERSATION_ARCHIVED"})
            return _invalid("body")
        response = _message_payload(
            request=ProductConversationRequest(
                conversation_id=conversation_id,
                turn_id=turn_result.turn_id,
                resolved_question=body["message"],
                research_mandate=(body["research_mandate"] if "research_mandate" in body else conversation.default_mandate),
                requested_mode=body["requested_mode"],
                selected_document_ids=tuple(body["selected_documents"]),
                occurred_at=body["occurred_at"],
            ),
            answer=answer,
        )
        self._responses_by_idempotency_key[(conversation_id, idempotency_key)] = (fingerprint, response)
        self._presentations_by_turn_id[turn_result.turn_id] = response
        return HttpResponse(200, response)

    def _archive(self, conversation_id: str, body: Mapping[str, Any]) -> HttpResponse:
        if set(body) != {"occurred_at"}:
            return _invalid("body")
        try:
            conversation = self._conversation_repository.conversation_for_id(conversation_id)
            archived = conversation.archive(
                archived_at=body["occurred_at"],
                retention_policy_version=self._retention_policy_version,
            )
            saved = self._conversation_repository.update(archived)
        except ValueError as exc:
            if str(exc).startswith("conversation inconnue"):
                return _not_found()
            if str(exc) == "conversation archivee":
                return HttpResponse(409, {"error_code": "CONVERSATION_ARCHIVED"})
            return _invalid("body")
        return HttpResponse(
            200,
            {
                "conversation_id": saved.conversation_id,
                "status": saved.status.value,
                "archived_at": saved.archived_at,
            },
        )


def _conversation_payload(conversation: Conversation) -> Mapping[str, Any]:
    return {
        "conversation_id": conversation.conversation_id,
        "title": conversation.title,
        "status": conversation.status.value,
        "created_at": conversation.created_at,
        "updated_at": conversation.archived_at or conversation.created_at,
    }


def _message_payload(
    *,
    request: ProductConversationRequest,
    answer: ProductConversationAnswer,
) -> Mapping[str, Any]:
    return {
        "conversation_id": request.conversation_id,
        "turn_id": request.turn_id,
        "resolved_question": request.resolved_question,
        "mode": request.requested_mode,
        "mode_justification": "Question documentaire explicitement demandée.",
        "support_status": answer.support_status,
        "answer_id": answer.answer_id,
        "verified_answer_ref": f"{answer.answer_id}@1",
        "answer_text": answer.answer_text,
        "citations": list(answer.citations),
        "knowledge_gaps": list(answer.knowledge_gaps),
        "unresolved_conflicts": list(answer.unresolved_conflicts),
        "abstention_reason": None,
    }


def _citation_payload(value: object) -> Mapping[str, Any]:
    citation = dict(_ensure_mapping(value, "citation"))
    if set(citation) != {"citation_id", "evidence_id", "quoted_span_hash", "source_locator"}:
        raise ValueError("citation invalide")
    _ensure_identifier(citation["citation_id"], "CIT", "citation_id")
    _ensure_identifier(citation["evidence_id"], "EVS", "evidence_id")
    _ensure_hash(citation["quoted_span_hash"], "quoted_span_hash")
    locator = dict(_ensure_mapping(citation["source_locator"], "source_locator"))
    if set(locator) != {
        "schema_version", "canonical_version_id", "document_id", "page_pdf", "item_id", "bbox", "content_hash"
    }:
        raise ValueError("source_locator invalide")
    _ensure_text(locator["schema_version"], "schema_version")
    _ensure_identifier(locator["canonical_version_id"], "CVER", "canonical_version_id")
    _ensure_identifier(locator["document_id"], "DOC", "document_id")
    if isinstance(locator["page_pdf"], bool) or not isinstance(locator["page_pdf"], int) or locator["page_pdf"] < 1:
        raise ValueError("page_pdf invalide")
    _ensure_text(locator["item_id"], "item_id")
    bbox = locator["bbox"]
    if isinstance(bbox, (str, bytes)) or not isinstance(bbox, Sequence) or len(bbox) != 4:
        raise ValueError("bbox invalide")
    if any(isinstance(coordinate, bool) or not isinstance(coordinate, (int, float)) for coordinate in bbox):
        raise ValueError("bbox invalide")
    _ensure_hash(locator["content_hash"], "content_hash")
    return {**citation, "source_locator": {**locator, "bbox": tuple(bbox)}}


def _mapping_sequence(value: object, field_name: str) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} invalide")
    return tuple(dict(_ensure_mapping(item, field_name)) for item in value)


def _message_fingerprint(body: Mapping[str, Any]) -> Mapping[str, Any]:
    return {key: body[key] for key in sorted(body)}


def _conversation_id_from_path(path: str, suffix: str | None) -> str | None:
    prefix = "/v1/conversations/"
    if not path.startswith(prefix):
        return None
    value = path[len(prefix):]
    if suffix is not None:
        if not value.endswith(suffix):
            return None
        value = value[:-len(suffix)]
    if value == "" or "/" in value:
        return None
    try:
        return _ensure_identifier(value, "CONV", "conversation_id")
    except ValueError:
        return None


def _ensure_request(value: object) -> HttpRequest:
    if not isinstance(value, HttpRequest):
        raise ValueError("requête HTTP invalide")
    return value


def _ensure_method(value: object) -> str:
    text = _ensure_text(value, "méthode")
    if text != text.upper():
        raise ValueError("méthode invalide")
    return text


def _ensure_path(value: object) -> str:
    text = _ensure_text(value, "path")
    if not text.startswith("/"):
        raise ValueError("path invalide")
    return text


def _ensure_mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")
    return value


def _ensure_non_empty_mapping(value: object, field_name: str) -> Mapping[str, Any]:
    mapping = _ensure_mapping(value, field_name)
    if len(mapping) == 0:
        raise ValueError(f"{field_name} vide")
    return mapping


def _ensure_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_identifier(value: object, prefix: str, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if not text.startswith(f"{prefix}-"):
        raise ValueError(f"{field_name} invalide")
    return text


def _ensure_hash(value: object, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise ValueError(f"{field_name} invalide")
    return text


def _ensure_utc(value: object, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if len(text) != 20 or not text.endswith("Z"):
        raise ValueError(f"{field_name} invalide")
    return text


def _ensure_error_code(value: object) -> str:
    text = _ensure_text(value, "error_code")
    if any(character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for character in text):
        raise ValueError("error_code invalide")
    return text


def _invalid(field: str) -> HttpResponse:
    return HttpResponse(400, {"error_code": "HTTP_REQUEST_INVALID", "field": field})


def _not_found() -> HttpResponse:
    return HttpResponse(404, {"error_code": "CONVERSATION_NOT_FOUND"})


__all__ = [
    "HttpRequest",
    "HttpResponse",
    "ProductConversationAnswer",
    "ProductConversationAnswerError",
    "ProductConversationHttpAdapter",
    "ProductConversationRequest",
]
