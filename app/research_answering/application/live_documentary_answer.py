"""Réponse RA live fondée exclusivement sur des extraits KA résolubles."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from app.contracts.documentary_evidence import DocumentaryEvidence
from app.contracts.llm_inference import (
    LlmInferenceGateway,
    LlmInferenceMessage,
    LlmInferenceRequest,
    LlmInferenceResponse,
)


class DocumentaryEvidenceRetriever(Protocol):
    def retrieve(
        self,
        *,
        question: str,
        selected_document_ids: tuple[str, ...],
    ) -> tuple[DocumentaryEvidence, ...]: ...


_EVIDENCE_MARKER_PATTERN = re.compile(r"\[EXTRAIT (?P<ordinal>[1-9][0-9]*)\]")


@dataclass(frozen=True, slots=True)
class LiveDocumentaryAnswerRequest:
    conversation_id: str
    turn_id: str
    resolved_question: str
    selected_document_ids: tuple[str, ...]
    occurred_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "conversation_id", _ensure_identifier(self.conversation_id, "CONV", "conversation_id"))
        object.__setattr__(self, "turn_id", _ensure_identifier(self.turn_id, "TURN", "turn_id"))
        object.__setattr__(self, "resolved_question", _ensure_text(self.resolved_question, "resolved_question"))
        documents = tuple(
            _ensure_identifier(value, "DOC", "selected_document_ids")
            for value in self.selected_document_ids
        )
        if len(documents) == 0 or len(documents) != len(set(documents)):
            raise ValueError("selected_document_ids invalides")
        object.__setattr__(self, "selected_document_ids", documents)
        object.__setattr__(self, "occurred_at", _ensure_utc(self.occurred_at, "occurred_at"))


@dataclass(frozen=True, slots=True)
class LiveDocumentaryAnswer:
    answer_id: str
    answer_text: str
    citations: tuple[Mapping[str, Any], ...]
    support_status: str
    knowledge_gaps: tuple[Mapping[str, Any], ...]
    unresolved_conflicts: tuple[Mapping[str, Any], ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "answer_id", _ensure_identifier(self.answer_id, "ANS", "answer_id"))
        object.__setattr__(self, "answer_text", _ensure_text(self.answer_text, "answer_text"))
        citations = tuple(_citation(citation) for citation in self.citations)
        if len(citations) == 0:
            raise ValueError("citations absentes")
        object.__setattr__(self, "citations", citations)
        if self.support_status != "PARTIALLY_SUPPORTED":
            raise ValueError("support_status live invalide")
        object.__setattr__(self, "knowledge_gaps", _mapping_sequence(self.knowledge_gaps, "knowledge_gaps"))
        object.__setattr__(self, "unresolved_conflicts", _mapping_sequence(self.unresolved_conflicts, "unresolved_conflicts"))


class LiveDocumentaryAnswerError(ValueError):
    """Une erreur RA publique ne peut pas être remplacée par une réponse plausible."""

    def __init__(self, error_code: str) -> None:
        self.error_code = _ensure_error_code(error_code)
        super().__init__(self.error_code)


@dataclass(frozen=True, slots=True)
class _StructuredDocumentaryAnswer:
    answer_text: str
    used_evidence_ordinals: tuple[int, ...]


class LiveDocumentaryAnswerService:
    """Construit le contexte LLM depuis KA et conserve les citations source."""

    def __init__(
        self,
        *,
        evidence_retriever: DocumentaryEvidenceRetriever,
        inference_gateway: LlmInferenceGateway,
        configuration_hash: str,
    ) -> None:
        if not callable(getattr(evidence_retriever, "retrieve", None)):
            raise ValueError("evidence_retriever invalide")
        if not callable(getattr(inference_gateway, "infer", None)):
            raise ValueError("inference_gateway invalide")
        self._evidence_retriever = evidence_retriever
        self._inference_gateway = inference_gateway
        self._configuration_hash = _ensure_hash(configuration_hash, "configuration_hash")

    def answer(self, request: LiveDocumentaryAnswerRequest) -> LiveDocumentaryAnswer:
        if not isinstance(request, LiveDocumentaryAnswerRequest):
            raise ValueError("requête réponse documentaire invalide")
        try:
            evidence = self._evidence_retriever.retrieve(
                question=request.resolved_question,
                selected_document_ids=request.selected_document_ids,
            )
        except ValueError as exc:
            error_code = getattr(exc, "error_code", None)
            if isinstance(error_code, str):
                raise LiveDocumentaryAnswerError(error_code) from exc
            raise
        if not isinstance(evidence, tuple) or any(
            not isinstance(item, DocumentaryEvidence) for item in evidence
        ):
            raise ValueError("evidence_retriever réponse invalide")
        if len(evidence) == 0:
            raise LiveDocumentaryAnswerError("DOCUMENTARY_EVIDENCE_NOT_FOUND")
        inference = self._inference_gateway.infer(
            LlmInferenceRequest(
                messages=(
                    LlmInferenceMessage(
                        role="system",
                        content=(
                            "Réponds en français exclusivement à partir des extraits documentaires fournis. "
                            "N'ajoute aucun fait absent des extraits. "
                            "Ajoute des marqueurs [EXTRAIT n] dans la réponse pour chaque extrait réellement "
                            "utilisé. N'inclus jamais un sommaire ou une table des matières qui ne soutient pas "
                            "directement la réponse."
                        ),
                    ),
                    LlmInferenceMessage(
                        role="user",
                        content=_prompt(request.resolved_question, evidence),
                    ),
                ),
                output_schema={
                    "type": "object",
                    "properties": {"answer": {"type": "string"}},
                    "required": ["answer"],
                    "additionalProperties": False,
                },
                schema_name="documentary_conversation_answer",
                schema_version="1.0",
                trace_id=f"TRACE-CV-{_short_hash(request.turn_id)}",
                request_id=f"REQ-CV-{_short_hash(request.conversation_id + request.turn_id)}",
                idempotency_key=f"idem-cv-{_short_hash(request.turn_id)}",
                prompt_id="PROMPT-RA-DOCUMENTARY-CONVERSATION",
                prompt_version="1.0",
                sampling_parameters={"temperature": 0},
            )
        )
        structured_answer = _structured_answer(inference, evidence_count=len(evidence))
        answer_id = f"ANS-LIVE-{_short_hash(request.conversation_id + request.turn_id)}"
        return LiveDocumentaryAnswer(
            answer_id=answer_id,
            answer_text=structured_answer.answer_text,
            citations=tuple(
                citation
                for evidence_ordinal in structured_answer.used_evidence_ordinals
                for citation in _citations_for(
                    evidence_item=evidence[evidence_ordinal - 1],
                    evidence_ordinal=evidence_ordinal,
                    request=request,
                )
            ),
            support_status="PARTIALLY_SUPPORTED",
            knowledge_gaps=(),
            unresolved_conflicts=(),
        )


def _structured_answer(response: object, *, evidence_count: int) -> _StructuredDocumentaryAnswer:
    if not isinstance(response, LlmInferenceResponse):
        raise ValueError("réponse gateway invalide")
    if response.status_code != 200:
        payload = response.payload
        candidate = payload.get("error_code") if isinstance(payload, Mapping) else None
        raise LiveDocumentaryAnswerError(
            candidate if isinstance(candidate, str) and candidate.isupper() else "LLM_GATEWAY_INFERENCE_FAILED"
        )
    structured = response.payload.get("structured_output")
    if not isinstance(structured, Mapping):
        raise LiveDocumentaryAnswerError("LLM_GATEWAY_RESPONSE_INVALID")
    if set(structured) != {"answer"}:
        raise LiveDocumentaryAnswerError("LLM_GATEWAY_RESPONSE_INVALID")
    try:
        marked_answer_text = _ensure_text(structured.get("answer"), "answer")
        used_evidence_ordinals = _evidence_ordinals_from_marked_answer(
            marked_answer_text,
            evidence_count=evidence_count,
        )
        answer_text = _answer_without_evidence_markers(marked_answer_text)
    except ValueError as exc:
        raise LiveDocumentaryAnswerError("LLM_GATEWAY_RESPONSE_INVALID") from exc
    return _StructuredDocumentaryAnswer(
        answer_text=answer_text,
        used_evidence_ordinals=used_evidence_ordinals,
    )


def _prompt(question: str, evidence: tuple[DocumentaryEvidence, ...]) -> str:
    excerpts = "\n\n".join(
        (
            f"[EXTRAIT {ordinal}] pages "
            f"{', '.join(str(page) for page in sorted({locator['page_pdf'] for locator in item.source_locators}))}"
            f"\n{item.excerpt}"
        )
        for ordinal, item in enumerate(evidence, start=1)
    )
    return f"Question : {question}\n\nExtraits documentaires :\n{excerpts}"


def _citations_for(
    *,
    evidence_item: DocumentaryEvidence,
    evidence_ordinal: int,
    request: LiveDocumentaryAnswerRequest,
) -> tuple[Mapping[str, Any], ...]:
    locator = _primary_source_locator(evidence_item)
    suffix = _short_hash(
        f"{request.turn_id}:{evidence_ordinal}:{locator['content_hash']}"
    )
    return (
        {
            "citation_id": f"CIT-LIVE-{suffix}",
            "evidence_id": f"EVS-LIVE-{suffix}",
            "quoted_span": evidence_item.excerpt,
            "quoted_span_hash": hashlib.sha256(
                evidence_item.excerpt.encode("utf-8")
            ).hexdigest(),
            "source_locator": locator,
        },
    )


def _evidence_ordinals_from_marked_answer(value: str, *, evidence_count: int) -> tuple[int, ...]:
    if isinstance(evidence_count, bool) or not isinstance(evidence_count, int) or evidence_count < 1:
        raise ValueError("evidence_count invalide")
    _ensure_text(value, "answer")
    ordinals = tuple(int(match.group("ordinal")) for match in _EVIDENCE_MARKER_PATTERN.finditer(value))
    if len(ordinals) == 0:
        raise ValueError("evidence_markers absents")
    for ordinal in ordinals:
        if ordinal < 1 or ordinal > evidence_count:
            raise ValueError("evidence_marker hors plage")
    return tuple(dict.fromkeys(ordinals))


def _answer_without_evidence_markers(value: str) -> str:
    without_markers = _EVIDENCE_MARKER_PATTERN.sub("", _ensure_text(value, "answer"))
    answer_text = re.sub(r"\s+", " ", without_markers).strip()
    return _ensure_text(answer_text, "answer")


def _primary_source_locator(evidence_item: DocumentaryEvidence) -> Mapping[str, Any]:
    if not isinstance(evidence_item, DocumentaryEvidence):
        raise ValueError("evidence_item invalide")
    locators = tuple(evidence_item.source_locators)
    if len(locators) == 0:
        raise ValueError("source_locators absents")
    return locators[0]


def _citation(value: object) -> Mapping[str, Any]:
    citation = dict(_mapping(value, "citation"))
    if set(citation) != {
        "citation_id",
        "evidence_id",
        "quoted_span",
        "quoted_span_hash",
        "source_locator",
    }:
        raise ValueError("citation invalide")
    _ensure_identifier(citation["citation_id"], "CIT", "citation_id")
    _ensure_identifier(citation["evidence_id"], "EVS", "evidence_id")
    quoted_span = _ensure_text(citation["quoted_span"], "quoted_span")
    quoted_span_hash = _ensure_hash(citation["quoted_span_hash"], "quoted_span_hash")
    if quoted_span_hash != hashlib.sha256(quoted_span.encode("utf-8")).hexdigest():
        raise ValueError("quoted_span_hash incohérent")
    citation["source_locator"] = _source_locator(citation["source_locator"])
    return citation


def _source_locator(value: object) -> Mapping[str, Any]:
    locator = dict(_mapping(value, "source_locator"))
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
    if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in bbox):
        raise ValueError("bbox invalide")
    _ensure_hash(locator["content_hash"], "content_hash")
    locator["bbox"] = tuple(bbox)
    return locator


def _mapping_sequence(value: object, name: str) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"{name} invalide")
    return tuple(dict(_mapping(item, name)) for item in value)


def _mapping(value: object, name: str) -> Mapping[str, Any]:
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


def _ensure_utc(value: object, name: str) -> str:
    text = _ensure_text(value, name)
    if len(text) != 20 or not text.endswith("Z"):
        raise ValueError(f"{name} invalide")
    return text


def _ensure_error_code(value: object) -> str:
    text = _ensure_text(value, "error_code")
    if any(character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for character in text):
        raise ValueError("error_code invalide")
    return text


def _short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:20].upper()


__all__ = [
    "DocumentaryEvidence",
    "DocumentaryEvidenceRetriever",
    "LiveDocumentaryAnswer",
    "LiveDocumentaryAnswerError",
    "LiveDocumentaryAnswerRequest",
    "LiveDocumentaryAnswerService",
]
