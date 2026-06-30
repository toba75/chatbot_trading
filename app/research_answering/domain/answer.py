"""Agrégat RA de réponse documentaire avant publication."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any


_HASH_HEX_LENGTH = 24
_UTC_INSTANT_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
_ANSWER_ID_PATTERN = re.compile(r"^ANS-[A-Z0-9][A-Z0-9-]*$")
_ASSERTION_ID_PATTERN = re.compile(r"^AAS-[A-Z0-9][A-Z0-9-]*$")
_RESEARCH_CASE_ID_PATTERN = re.compile(r"^RSC-[A-Z0-9][A-Z0-9-]*$")
_EVIDENCE_SET_ID_PATTERN = re.compile(r"^EVS-[A-Z0-9][A-Z0-9-]*$")
_COMPOSITE_MARKERS = (
    re.compile(r"\s+et\s+", re.IGNORECASE),
    re.compile(r"\s+tandis\s+que\s+", re.IGNORECASE),
    re.compile(r"\s+alors\s+que\s+", re.IGNORECASE),
    re.compile(r";"),
)


class AnswerStatus(str, Enum):
    """État métier de l'agrégat Answer."""

    DRAFT = "DRAFT"
    ASSERTIONS_EXTRACTED = "ASSERTIONS_EXTRACTED"
    SUPPORT_EVALUATED = "SUPPORT_EVALUATED"
    VERIFIED = "VERIFIED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    REJECTED = "REJECTED"


class AssertionOriginType(str, Enum):
    """Origine métier d'une assertion extraite."""

    SOURCE = "SOURCE"
    DEDUCTION = "DEDUCTION"
    DESIGN_CHOICE = "DESIGN_CHOICE"


class AssertionEvaluationStatus(str, Enum):
    """Statut local avant la politique de support T-007."""

    PENDING_EVALUATION = "PENDING_EVALUATION"


@dataclass(frozen=True)
class AssertionOrigin:
    """Origine obligatoire d'une assertion de réponse."""

    origin_type: AssertionOriginType
    basis_refs: Sequence[str]
    rationale: str

    def __post_init__(self) -> None:
        if not isinstance(self.origin_type, AssertionOriginType):
            raise ValueError("assertion_origin_type invalide")
        basis_refs = _ensure_text_tuple(
            self.basis_refs,
            "premisses" if self.origin_type is AssertionOriginType.DEDUCTION else "basis_refs",
            allow_empty=False,
        )
        object.__setattr__(self, "basis_refs", basis_refs)
        object.__setattr__(self, "rationale", _ensure_text(self.rationale, "rationale"))

    def to_payload(self) -> dict[str, Any]:
        return {
            "origin_type": self.origin_type.value,
            "basis_refs": self.basis_refs,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class AnswerDraft:
    """Brouillon RA non public produit avant extraction."""

    draft_version: int
    content: str
    model_provenance: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "draft_version",
            _ensure_positive_integer(self.draft_version, "draft_version"),
        )
        object.__setattr__(self, "content", _ensure_text(self.content, "answer_draft"))
        object.__setattr__(
            self,
            "model_provenance",
            _ensure_text(self.model_provenance, "model_provenance"),
        )

    @property
    def draft_hash(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()

    def to_payload(self) -> dict[str, Any]:
        return {
            "draft_version": self.draft_version,
            "draft_hash": self.draft_hash,
            "model_provenance": self.model_provenance,
        }


@dataclass(frozen=True)
class AnswerAssertionCandidate:
    """Assertion proposée par l'extracteur avant rattachement à Answer."""

    text: str
    origin: AssertionOrigin
    important: bool
    support_status: AssertionEvaluationStatus

    @classmethod
    def important_pending(cls, *, text: str, origin: AssertionOrigin) -> "AnswerAssertionCandidate":
        return cls(
            text=text,
            origin=origin,
            important=True,
            support_status=AssertionEvaluationStatus.PENDING_EVALUATION,
        )

    def __post_init__(self) -> None:
        object.__setattr__(self, "text", _ensure_atomic_text(self.text))
        if not isinstance(self.origin, AssertionOrigin):
            raise ValueError("assertion_origin absent")
        if not isinstance(self.important, bool):
            raise ValueError("assertion important non booleen")
        if not self.important:
            raise ValueError("assertion importante absente")
        if self.support_status is not AssertionEvaluationStatus.PENDING_EVALUATION:
            raise ValueError("support_status predecide interdit")


@dataclass(frozen=True)
class AnswerAssertion:
    """Assertion atomique rattachée à une version de brouillon."""

    assertion_id: str
    answer_id: str
    draft_version: int
    sequence: int
    text: str
    origin: AssertionOrigin
    important: bool
    support_status: AssertionEvaluationStatus

    @classmethod
    def from_extracted(
        cls,
        *,
        answer_id: str,
        draft_version: int,
        sequence: int,
        text: str,
        origin: AssertionOrigin,
    ) -> "AnswerAssertion":
        return cls(
            assertion_id=_assertion_id_for(
                answer_id=answer_id,
                draft_version=draft_version,
                sequence=sequence,
                text=text,
                origin=origin,
            ),
            answer_id=answer_id,
            draft_version=draft_version,
            sequence=sequence,
            text=text,
            origin=origin,
            important=True,
            support_status=AssertionEvaluationStatus.PENDING_EVALUATION,
        )

    @classmethod
    def from_candidate(
        cls,
        *,
        answer_id: str,
        draft_version: int,
        sequence: int,
        candidate: AnswerAssertionCandidate,
    ) -> "AnswerAssertion":
        parsed_candidate = _ensure_candidate(candidate)
        return cls.from_extracted(
            answer_id=answer_id,
            draft_version=draft_version,
            sequence=sequence,
            text=parsed_candidate.text,
            origin=parsed_candidate.origin,
        )

    def __post_init__(self) -> None:
        object.__setattr__(self, "assertion_id", _ensure_assertion_id(self.assertion_id))
        object.__setattr__(self, "answer_id", _ensure_answer_id(self.answer_id))
        object.__setattr__(
            self,
            "draft_version",
            _ensure_positive_integer(self.draft_version, "draft_version"),
        )
        object.__setattr__(self, "sequence", _ensure_positive_integer(self.sequence, "sequence"))
        object.__setattr__(self, "text", _ensure_atomic_text(self.text))
        if not isinstance(self.origin, AssertionOrigin):
            raise ValueError("assertion_origin absent")
        if not isinstance(self.important, bool):
            raise ValueError("assertion important non booleen")
        if not self.important:
            raise ValueError("assertion importante absente")
        if self.support_status is not AssertionEvaluationStatus.PENDING_EVALUATION:
            raise ValueError("support_status predecide interdit")

    @property
    def atomic(self) -> bool:
        return True

    def to_payload(self) -> dict[str, Any]:
        return {
            "assertion_id": self.assertion_id,
            "answer_id": self.answer_id,
            "draft_version": self.draft_version,
            "sequence": self.sequence,
            "text": self.text,
            "origin": self.origin.to_payload(),
            "important": self.important,
            "support_status": self.support_status.value,
        }


@dataclass(frozen=True)
class AnswerDrafted:
    """Événement RA de création du brouillon."""

    answer_id: str
    research_case_id: str
    draft_hash: str
    model_provenance: str
    occurred_at: str

    @property
    def event_type(self) -> str:
        return "AnswerDrafted"

    def __post_init__(self) -> None:
        object.__setattr__(self, "answer_id", _ensure_answer_id(self.answer_id))
        object.__setattr__(self, "research_case_id", _ensure_research_case_id(self.research_case_id))
        object.__setattr__(self, "draft_hash", _ensure_sha256(self.draft_hash, "draft_hash"))
        object.__setattr__(
            self,
            "model_provenance",
            _ensure_text(self.model_provenance, "model_provenance"),
        )
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at, "occurred_at"))

    def to_payload(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "occurred_at": self.occurred_at,
            "payload": {
                "answer_id": self.answer_id,
                "research_case_id": self.research_case_id,
                "draft_hash": self.draft_hash,
                "model_provenance": self.model_provenance,
            },
        }


@dataclass(frozen=True)
class AnswerAssertionsExtracted:
    """Événement RA d'extraction des assertions vérifiables."""

    answer_id: str
    assertion_count: int
    extractor_version: str
    occurred_at: str

    @property
    def event_type(self) -> str:
        return "AnswerAssertionsExtracted"

    def __post_init__(self) -> None:
        object.__setattr__(self, "answer_id", _ensure_answer_id(self.answer_id))
        object.__setattr__(
            self,
            "assertion_count",
            _ensure_positive_integer(self.assertion_count, "assertion_count"),
        )
        object.__setattr__(
            self,
            "extractor_version",
            _ensure_text(self.extractor_version, "extractor_version"),
        )
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at, "occurred_at"))

    def to_payload(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "occurred_at": self.occurred_at,
            "payload": {
                "answer_id": self.answer_id,
                "assertion_count": self.assertion_count,
                "extractor_version": self.extractor_version,
            },
        }


@dataclass(frozen=True)
class Answer:
    """Agrégat RA qui sépare brouillon, assertions et publication future."""

    answer_id: str
    research_case_id: str
    evidence_set_id: str
    evidence_set_version: int
    status: AnswerStatus
    answer_draft: AnswerDraft
    assertions: Sequence[AnswerAssertion]
    drafted_at: str
    events: Sequence[AnswerDrafted | AnswerAssertionsExtracted]

    @classmethod
    def create_draft(
        cls,
        *,
        answer_id: str,
        research_case_id: str,
        evidence_set_id: str,
        evidence_set_version: int,
        draft: AnswerDraft,
        occurred_at: str,
    ) -> "Answer":
        parsed_draft = _ensure_draft(draft)
        event = AnswerDrafted(
            answer_id=answer_id,
            research_case_id=research_case_id,
            draft_hash=parsed_draft.draft_hash,
            model_provenance=parsed_draft.model_provenance,
            occurred_at=occurred_at,
        )
        return cls(
            answer_id=answer_id,
            research_case_id=research_case_id,
            evidence_set_id=evidence_set_id,
            evidence_set_version=evidence_set_version,
            status=AnswerStatus.DRAFT,
            answer_draft=parsed_draft,
            assertions=(),
            drafted_at=occurred_at,
            events=(event,),
        )

    def __post_init__(self) -> None:
        object.__setattr__(self, "answer_id", _ensure_answer_id(self.answer_id))
        object.__setattr__(self, "research_case_id", _ensure_research_case_id(self.research_case_id))
        object.__setattr__(self, "evidence_set_id", _ensure_evidence_set_id(self.evidence_set_id))
        object.__setattr__(
            self,
            "evidence_set_version",
            _ensure_positive_integer(self.evidence_set_version, "evidence_set_version"),
        )
        if not isinstance(self.status, AnswerStatus):
            raise ValueError("answer_status invalide")
        object.__setattr__(self, "answer_draft", _ensure_draft(self.answer_draft))
        object.__setattr__(self, "assertions", _ensure_assertions(self.assertions))
        object.__setattr__(self, "drafted_at", _ensure_utc_instant(self.drafted_at, "drafted_at"))
        object.__setattr__(self, "events", _ensure_events(self.events))
        if self.status is AnswerStatus.DRAFT and len(self.assertions) > 0:
            raise ValueError("assertions interdites pour DRAFT")
        if self.status is AnswerStatus.ASSERTIONS_EXTRACTED and len(self.assertions) == 0:
            raise ValueError("assertions absentes pour ASSERTIONS_EXTRACTED")

    @property
    def is_published(self) -> bool:
        return self.status in {AnswerStatus.VERIFIED, AnswerStatus.PARTIALLY_SUPPORTED}

    @property
    def draft(self) -> AnswerDraft:
        return self.answer_draft

    def extract_assertions(
        self,
        *,
        assertions: Sequence[AnswerAssertion | AnswerAssertionCandidate],
        extractor_version: str,
        occurred_at: str,
    ) -> tuple["Answer", AnswerAssertionsExtracted]:
        if self.status is not AnswerStatus.DRAFT:
            raise ValueError("answer non extractible")
        parsed_assertions = _ensure_extracted_assertions(
            assertions,
            answer_id=self.answer_id,
            draft_version=self.answer_draft.draft_version,
        )
        if len(parsed_assertions) == 0:
            raise ValueError("answer_assertions absentes")
        event = AnswerAssertionsExtracted(
            answer_id=self.answer_id,
            assertion_count=len(parsed_assertions),
            extractor_version=extractor_version,
            occurred_at=occurred_at,
        )
        return (
            replace(
                self,
                status=AnswerStatus.ASSERTIONS_EXTRACTED,
                assertions=parsed_assertions,
                events=self.events + (event,),
            ),
            event,
        )

    def replace_draft(self, draft: AnswerDraft) -> "Answer":
        if self.status is not AnswerStatus.DRAFT:
            raise ValueError("draft version publiee non modifiable")
        parsed_draft = _ensure_draft(draft)
        if parsed_draft.draft_version <= self.answer_draft.draft_version:
            raise ValueError("draft_version non croissante")
        return replace(self, answer_draft=parsed_draft)

    def to_payload(self) -> dict[str, Any]:
        return {
            "answer_id": self.answer_id,
            "research_case_id": self.research_case_id,
            "evidence_set_id": self.evidence_set_id,
            "evidence_set_version": self.evidence_set_version,
            "status": self.status.value,
            "is_published": self.is_published,
            "draft": self.answer_draft.to_payload(),
            "assertions": [assertion.to_payload() for assertion in self.assertions],
            "drafted_at": self.drafted_at,
            "events": [event.to_payload() for event in self.events],
        }


def answer_id_for(*, research_case_id: str, evidence_set_id: str, draft_hash: str) -> str:
    payload = {
        "research_case_id": _ensure_research_case_id(research_case_id),
        "evidence_set_id": _ensure_evidence_set_id(evidence_set_id),
        "draft_hash": _ensure_sha256(draft_hash, "draft_hash"),
    }
    return f"ANS-{_hash_payload(payload)[:_HASH_HEX_LENGTH].upper()}"


def _ensure_draft(value: object) -> AnswerDraft:
    if not isinstance(value, AnswerDraft):
        raise ValueError("answer_draft absent")
    return value


def _ensure_candidate(value: object) -> AnswerAssertionCandidate:
    if not isinstance(value, AnswerAssertionCandidate):
        raise ValueError("answer_assertion_candidate invalide")
    return value


def _ensure_assertions(value: object) -> tuple[AnswerAssertion, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("answer_assertions invalides")
    assertions = tuple(value)
    ids: list[str] = []
    for assertion in assertions:
        if not isinstance(assertion, AnswerAssertion):
            raise ValueError("answer_assertion invalide")
        if assertion.assertion_id in ids:
            raise ValueError("answer_assertion dupliquee")
        ids.append(assertion.assertion_id)
    return assertions


def _ensure_extracted_assertions(
    value: object,
    *,
    answer_id: str,
    draft_version: int,
) -> tuple[AnswerAssertion, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("answer_assertions invalides")
    parsed_answer_id = _ensure_answer_id(answer_id)
    parsed_draft_version = _ensure_positive_integer(draft_version, "draft_version")
    parsed: list[AnswerAssertion] = []
    for index, item in enumerate(tuple(value), start=1):
        if isinstance(item, AnswerAssertionCandidate):
            parsed.append(
                AnswerAssertion.from_candidate(
                    answer_id=parsed_answer_id,
                    draft_version=parsed_draft_version,
                    sequence=index,
                    candidate=item,
                )
            )
            continue
        if isinstance(item, AnswerAssertion):
            if item.answer_id != parsed_answer_id:
                raise ValueError("answer_assertion hors answer")
            if item.draft_version != parsed_draft_version:
                raise ValueError("answer_assertion hors draft")
            parsed.append(item)
            continue
        raise ValueError("answer_assertion invalide")
    return _ensure_assertions(parsed)


def _ensure_events(value: object) -> tuple[AnswerDrafted | AnswerAssertionsExtracted, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("events invalides")
    events = tuple(value)
    if len(events) == 0:
        raise ValueError("events absents")
    for event in events:
        if not isinstance(event, (AnswerDrafted, AnswerAssertionsExtracted)):
            raise ValueError("event answer invalide")
    return events


def _ensure_atomic_text(value: object) -> str:
    text = _ensure_text(value, "answer_assertion")
    for marker in _COMPOSITE_MARKERS:
        if marker.search(text) is not None:
            raise ValueError("assertion composite non testable")
    return text


def _ensure_text_tuple(value: object, field_name: str, *, allow_empty: bool) -> tuple[str, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} invalides")
    parsed = tuple(_ensure_text(item, field_name) for item in value)
    if not allow_empty and len(parsed) == 0:
        raise ValueError(f"{field_name} absentes")
    if len(parsed) != len(set(parsed)):
        raise ValueError(f"{field_name} dupliquees")
    return parsed


def _ensure_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


def _ensure_positive_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_utc_instant(value: object, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if _UTC_INSTANT_PATTERN.fullmatch(text) is None:
        raise ValueError(f"{field_name} invalide")
    return text


def _ensure_answer_id(value: object) -> str:
    text = _ensure_text(value, "answer_id")
    if _ANSWER_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("answer_id invalide")
    return text


def _ensure_assertion_id(value: object) -> str:
    text = _ensure_text(value, "assertion_id")
    if _ASSERTION_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("assertion_id invalide")
    return text


def _ensure_research_case_id(value: object) -> str:
    text = _ensure_text(value, "research_case_id")
    if _RESEARCH_CASE_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("research_case_id invalide")
    return text


def _ensure_evidence_set_id(value: object) -> str:
    text = _ensure_text(value, "evidence_set_id")
    if _EVIDENCE_SET_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("evidence_set_id invalide")
    return text


def _ensure_sha256(value: object, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if re.fullmatch(r"[0-9a-f]{64}", text) is None:
        raise ValueError(f"{field_name} invalide")
    return text


def _assertion_id_for(
    *,
    answer_id: str,
    draft_version: int,
    sequence: int,
    text: str,
    origin: AssertionOrigin,
) -> str:
    payload = {
        "answer_id": _ensure_answer_id(answer_id),
        "draft_version": _ensure_positive_integer(draft_version, "draft_version"),
        "sequence": _ensure_positive_integer(sequence, "sequence"),
        "text": _ensure_text(text, "answer_assertion"),
        "origin": origin.to_payload() if isinstance(origin, AssertionOrigin) else None,
    }
    return f"AAS-{_hash_payload(payload)[:_HASH_HEX_LENGTH].upper()}"


def _hash_payload(payload: Mapping[str, Any]) -> str:
    serialized_payload = json.dumps(
        _json_ready(payload),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(serialized_payload.encode("utf-8")).hexdigest()


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(child) for child in value]
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "to_payload") and callable(value.to_payload):
        return _json_ready(value.to_payload())
    return value


__all__ = [
    "Answer",
    "AnswerAssertion",
    "AnswerAssertionCandidate",
    "AnswerAssertionsExtracted",
    "AnswerDraft",
    "AnswerDrafted",
    "AnswerStatus",
    "AssertionEvaluationStatus",
    "AssertionOrigin",
    "AssertionOriginType",
    "answer_id_for",
]
