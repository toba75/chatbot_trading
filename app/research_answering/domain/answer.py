"""Agrégat RA de réponse documentaire avant publication."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any

from app.contracts.evidence_claims import VerifiedClaimRef
from app.contracts.research_outcomes import VerifiedResearchOutcome
from app.research_answering.domain.contradiction_assessment import (
    ContradictionAssessment,
    KnowledgeGap,
    SupportStatus,
    ensure_support_status,
)
from app.research_answering.domain.evidence_set import Citation, EvidenceSet


_HASH_HEX_LENGTH = 24
_UTC_INSTANT_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
_ANSWER_ID_PATTERN = re.compile(r"^ANS-[A-Z0-9][A-Z0-9-]*$")
_ANSWER_REF_PATTERN = re.compile(r"^ANS-[A-Z0-9][A-Z0-9-]*@[1-9][0-9]*$")
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


class AssertionPublicationStatus(str, Enum):
    """Décision de publication d'une assertion importante."""

    SUPPORTED = "SUPPORTED"
    QUALIFIED = "QUALIFIED"
    REMOVED = "REMOVED"


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
class AssertionSupportDecision:
    """Décision documentaire publiée pour une assertion extraite."""

    assertion_id: str
    basis_refs: Sequence[str]
    publication_status: AssertionPublicationStatus
    reason_code: str
    public_reason: str
    claim_refs: Sequence[VerifiedClaimRef]
    citation_ids: Sequence[str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "assertion_id", _ensure_assertion_id(self.assertion_id))
        object.__setattr__(
            self,
            "basis_refs",
            _ensure_text_tuple(self.basis_refs, "basis_refs", allow_empty=False),
        )
        if not isinstance(self.publication_status, AssertionPublicationStatus):
            raise ValueError("assertion_publication_status invalide")
        object.__setattr__(self, "reason_code", _ensure_text(self.reason_code, "reason_code"))
        object.__setattr__(self, "public_reason", _ensure_text(self.public_reason, "public_reason"))
        object.__setattr__(
            self,
            "claim_refs",
            _ensure_verified_claim_refs(self.claim_refs, allow_empty=True),
        )
        object.__setattr__(
            self,
            "citation_ids",
            _ensure_text_tuple(self.citation_ids, "citation_ids", allow_empty=True),
        )
        if self.publication_status is AssertionPublicationStatus.SUPPORTED:
            if len(self.claim_refs) == 0:
                raise ValueError("claim_ref absent pour assertion supportee")
            if len(self.citation_ids) == 0:
                raise ValueError("citation absente pour assertion supportee")
        if self.publication_status is not AssertionPublicationStatus.SUPPORTED and self.reason_code == "SUPPORTED":
            raise ValueError("reason_code support incoherent")

    @property
    def supported(self) -> bool:
        return self.publication_status is AssertionPublicationStatus.SUPPORTED

    def to_payload(self) -> dict[str, Any]:
        return {
            "assertion_id": self.assertion_id,
            "basis_refs": self.basis_refs,
            "publication_status": self.publication_status.value,
            "reason_code": self.reason_code,
            "public_reason": self.public_reason,
            "claim_refs": [
                f"{claim_ref.claim_id}@{claim_ref.claim_version}"
                for claim_ref in self.claim_refs
            ],
            "citation_ids": self.citation_ids,
        }


@dataclass(frozen=True)
class AnswerSupportEvaluated:
    """Événement RA de décision du support documentaire."""

    answer_id: str
    support_status: SupportStatus
    unsupported_assertion_count: int
    policy_version: str
    occurred_at: str

    @property
    def event_type(self) -> str:
        return "AnswerSupportEvaluated"

    def __post_init__(self) -> None:
        object.__setattr__(self, "answer_id", _ensure_answer_id(self.answer_id))
        object.__setattr__(self, "support_status", ensure_support_status(self.support_status))
        object.__setattr__(
            self,
            "unsupported_assertion_count",
            _ensure_non_negative_integer(
                self.unsupported_assertion_count,
                "unsupported_assertion_count",
            ),
        )
        object.__setattr__(self, "policy_version", _ensure_text(self.policy_version, "policy_version"))
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at, "occurred_at"))

    def to_payload(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "occurred_at": self.occurred_at,
            "payload": {
                "answer_id": self.answer_id,
                "support_status": self.support_status.value,
                "unsupported_assertion_count": self.unsupported_assertion_count,
                "policy_version": self.policy_version,
            },
        }


@dataclass(frozen=True)
class AnswerVerified:
    """Événement RA de publication d'une réponse supportée."""

    answer_id: str
    answer_version: int
    evidence_set_version: int
    citation_count: int
    occurred_at: str

    @property
    def event_type(self) -> str:
        return "AnswerVerified"

    def __post_init__(self) -> None:
        object.__setattr__(self, "answer_id", _ensure_answer_id(self.answer_id))
        object.__setattr__(
            self,
            "answer_version",
            _ensure_positive_integer(self.answer_version, "answer_version"),
        )
        object.__setattr__(
            self,
            "evidence_set_version",
            _ensure_positive_integer(self.evidence_set_version, "evidence_set_version"),
        )
        object.__setattr__(
            self,
            "citation_count",
            _ensure_positive_integer(self.citation_count, "citation_count"),
        )
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at, "occurred_at"))

    def to_payload(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "occurred_at": self.occurred_at,
            "payload": {
                "answer_id": self.answer_id,
                "answer_version": self.answer_version,
                "evidence_set_version": self.evidence_set_version,
                "citation_count": self.citation_count,
            },
        }


@dataclass(frozen=True)
class AnswerPartiallySupported:
    """Événement RA de publication d'une réponse qualifiée."""

    answer_id: str
    answer_version: int
    knowledge_gap_count: int
    citation_count: int
    occurred_at: str

    @property
    def event_type(self) -> str:
        return "AnswerPartiallySupported"

    def __post_init__(self) -> None:
        object.__setattr__(self, "answer_id", _ensure_answer_id(self.answer_id))
        object.__setattr__(
            self,
            "answer_version",
            _ensure_positive_integer(self.answer_version, "answer_version"),
        )
        object.__setattr__(
            self,
            "knowledge_gap_count",
            _ensure_non_negative_integer(self.knowledge_gap_count, "knowledge_gap_count"),
        )
        object.__setattr__(
            self,
            "citation_count",
            _ensure_positive_integer(self.citation_count, "citation_count"),
        )
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at, "occurred_at"))

    def to_payload(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "occurred_at": self.occurred_at,
            "payload": {
                "answer_id": self.answer_id,
                "answer_version": self.answer_version,
                "knowledge_gap_count": self.knowledge_gap_count,
                "citation_count": self.citation_count,
            },
        }


@dataclass(frozen=True)
class AnswerSuperseded:
    """Événement RA de supersession explicite d'une réponse publiée."""

    old_answer_ref: str
    new_answer_ref: str
    supersession_reason: str
    occurred_at: str

    @property
    def event_type(self) -> str:
        return "AnswerSuperseded"

    def __post_init__(self) -> None:
        object.__setattr__(self, "old_answer_ref", _ensure_answer_ref(self.old_answer_ref, "old_answer_ref"))
        object.__setattr__(self, "new_answer_ref", _ensure_answer_ref(self.new_answer_ref, "new_answer_ref"))
        if self.old_answer_ref == self.new_answer_ref:
            raise ValueError("answer_ref supersession reflexive")
        object.__setattr__(
            self,
            "supersession_reason",
            _ensure_text(self.supersession_reason, "supersession_reason"),
        )
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at, "occurred_at"))

    def to_payload(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "occurred_at": self.occurred_at,
            "payload": {
                "old_answer_ref": self.old_answer_ref,
                "new_answer_ref": self.new_answer_ref,
                "supersession_reason": self.supersession_reason,
            },
        }


@dataclass(frozen=True)
class VerifiedAnswerVersion:
    """Version publiée immuable d'une réponse documentaire."""

    answer_id: str
    answer_version: int
    research_case_id: str
    evidence_set_id: str
    evidence_set_version: int
    evidence_set_snapshot: EvidenceSet
    support_status: SupportStatus
    answer_text: str
    source_assertions: Sequence[AnswerAssertion]
    assertion_decisions: Sequence[AssertionSupportDecision]
    citations: Sequence[Citation]
    claim_refs: Sequence[VerifiedClaimRef]
    policy_version: str
    published_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "answer_id", _ensure_answer_id(self.answer_id))
        object.__setattr__(
            self,
            "answer_version",
            _ensure_positive_integer(self.answer_version, "answer_version"),
        )
        object.__setattr__(self, "research_case_id", _ensure_research_case_id(self.research_case_id))
        object.__setattr__(self, "evidence_set_id", _ensure_evidence_set_id(self.evidence_set_id))
        object.__setattr__(
            self,
            "evidence_set_version",
            _ensure_positive_integer(self.evidence_set_version, "evidence_set_version"),
        )
        if not isinstance(self.evidence_set_snapshot, EvidenceSet):
            raise ValueError("evidence_set_snapshot invalide")
        if not self.evidence_set_snapshot.sealed:
            raise ValueError("evidence_set_snapshot non scelle")
        if self.evidence_set_snapshot.evidence_set_id != self.evidence_set_id:
            raise ValueError("evidence_set_snapshot incoherent")
        if self.evidence_set_snapshot.version.value != self.evidence_set_version:
            raise ValueError("evidence_set_version incoherente")
        object.__setattr__(self, "support_status", ensure_support_status(self.support_status))
        object.__setattr__(self, "answer_text", _ensure_text(self.answer_text, "answer_text"))
        assertions = _ensure_assertions(self.source_assertions)
        object.__setattr__(self, "source_assertions", assertions)
        decisions = _ensure_assertion_support_decisions(self.assertion_decisions)
        object.__setattr__(self, "assertion_decisions", decisions)
        _ensure_assertion_decisions_cover(assertions=assertions, decisions=decisions)
        object.__setattr__(self, "citations", _ensure_citation_sequence(self.citations, allow_empty=False))
        object.__setattr__(
            self,
            "claim_refs",
            _ensure_verified_claim_refs(self.claim_refs, allow_empty=True),
        )
        object.__setattr__(self, "policy_version", _ensure_text(self.policy_version, "policy_version"))
        object.__setattr__(self, "published_at", _ensure_utc_instant(self.published_at, "published_at"))
        if self.support_status is SupportStatus.SUPPORTED and not all(decision.supported for decision in decisions):
            raise ValueError("SUPPORTED avec assertion non supportee")
        supported_citation_ids = {
            citation_id
            for decision in decisions
            if decision.supported
            for citation_id in decision.citation_ids
        }
        available_citation_ids = {citation.citation_id for citation in self.citations}
        missing_citation_ids = supported_citation_ids.difference(available_citation_ids)
        if len(missing_citation_ids) > 0:
            raise ValueError(f"citation absente pour assertion supportee: {sorted(missing_citation_ids)[0]}")

    @property
    def answer_ref(self) -> str:
        return f"{self.answer_id}@{self.answer_version}"

    def to_verified_research_outcome(
        self,
        *,
        question: str,
        mandate: Mapping[str, Any],
        unresolved_conflicts: Sequence[ContradictionAssessment],
        knowledge_gaps: Sequence[KnowledgeGap],
        completed_at: str,
    ) -> VerifiedResearchOutcome:
        if len(self.claim_refs) == 0:
            raise ValueError("VerifiedResearchOutcome invalide: claim_refs vide")
        return VerifiedResearchOutcome.from_payload(
            {
                "schema_version": "1.0",
                "research_case_id": self.research_case_id,
                "question": _ensure_text(question, "question"),
                "mandate": dict(mandate),
                "answer_id": self.answer_id,
                "support_status": self.support_status.value,
                "claim_refs": [
                    f"{claim_ref.claim_id}@{claim_ref.claim_version}"
                    for claim_ref in self.claim_refs
                ],
                "unresolved_conflicts": [
                    _research_conflict_payload(assessment)
                    for assessment in unresolved_conflicts
                ],
                "knowledge_gaps": [
                    _knowledge_gap_payload(gap)
                    for gap in knowledge_gaps
                ],
                "completed_at": _ensure_utc_instant(completed_at, "completed_at"),
            }
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "answer_id": self.answer_id,
            "answer_version": self.answer_version,
            "answer_ref": self.answer_ref,
            "research_case_id": self.research_case_id,
            "evidence_set_id": self.evidence_set_id,
            "evidence_set_version": self.evidence_set_version,
            "evidence_hash": self.evidence_set_snapshot.evidence_hash,
            "support_status": self.support_status.value,
            "answer_text": self.answer_text,
            "assertion_decisions": [
                decision.to_payload()
                for decision in self.assertion_decisions
            ],
            "citations": [citation.to_payload() for citation in self.citations],
            "claim_refs": [
                f"{claim_ref.claim_id}@{claim_ref.claim_version}"
                for claim_ref in self.claim_refs
            ],
            "policy_version": self.policy_version,
            "published_at": self.published_at,
        }


@dataclass(frozen=True)
class CitationIntegrityPolicy:
    """Politique RA d'ouverture stricte des citations publiées."""

    policy_version: str
    citation_resolver: object

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_version", _ensure_text(self.policy_version, "citation_policy_version"))
        if not callable(getattr(self.citation_resolver, "resolve", None)):
            raise ValueError("citation_resolver sans resolve")

    def ensure_openable(self, citations: Sequence[Citation]) -> None:
        for citation in _ensure_citation_sequence(citations, allow_empty=False):
            if self.citation_resolver.resolve(citation) is None:
                raise ValueError("ANSWER_CITATION_UNRESOLVABLE")


@dataclass(frozen=True)
class AnswerFreshnessPolicy:
    """Politique RA de revalidation des réponses réutilisées."""

    policy_version: str
    current_support_policy_version: str
    accepted_canonical_version_ids: Sequence[str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_version", _ensure_text(self.policy_version, "freshness_policy_version"))
        object.__setattr__(
            self,
            "current_support_policy_version",
            _ensure_text(self.current_support_policy_version, "current_support_policy_version"),
        )
        object.__setattr__(
            self,
            "accepted_canonical_version_ids",
            _ensure_text_tuple(
                self.accepted_canonical_version_ids,
                "accepted_canonical_version_ids",
                allow_empty=False,
            ),
        )

    def ensure_fresh(self, *, evidence_set: EvidenceSet, support_policy_version: str) -> None:
        if not isinstance(evidence_set, EvidenceSet):
            raise ValueError("evidence_set invalide")
        if support_policy_version != self.current_support_policy_version:
            raise ValueError("ANSWER_POLICY_OBSOLETE")
        accepted_ids = set(self.accepted_canonical_version_ids)
        for citation in evidence_set.citations:
            if citation.source_locator.canonical_version_id not in accepted_ids:
                raise ValueError("ANSWER_SOURCE_OBSOLETE")


@dataclass(frozen=True)
class AnswerSupportPolicy:
    """Politique RA qui décide le support global sans score implicite."""

    policy_version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_version", _ensure_text(self.policy_version, "support_policy_version"))

    def evaluate(
        self,
        *,
        answer: "Answer",
        research_case: object,
        citation_policy: CitationIntegrityPolicy,
        occurred_at: str,
    ) -> tuple[
        "Answer",
        VerifiedAnswerVersion,
        tuple[AnswerSupportEvaluated | AnswerVerified | AnswerPartiallySupported, ...],
    ]:
        parsed_answer = _ensure_answer(answer)
        if parsed_answer.status is not AnswerStatus.ASSERTIONS_EXTRACTED:
            raise ValueError("answer non evaluable")
        evidence_set = getattr(research_case, "evidence_set", None)
        if not isinstance(evidence_set, EvidenceSet) or not evidence_set.sealed:
            raise ValueError("evidence_set non scelle")
        if parsed_answer.research_case_id != getattr(research_case, "research_case_id", None):
            raise ValueError("answer hors research_case")
        if parsed_answer.evidence_set_id != evidence_set.evidence_set_id:
            raise ValueError("answer hors evidence_set")
        if parsed_answer.evidence_set_version != evidence_set.version.value:
            raise ValueError("answer evidence_set_version obsolete")
        if any(
            getattr(assessment, "blocks_publication", False)
            for assessment in getattr(research_case, "contradiction_assessments", ())
        ):
            raise ValueError("ANSWER_CONFLICT_UNRESOLVED")

        citation_policy.ensure_openable(evidence_set.citations)
        decisions = _support_decisions_for(
            assertions=parsed_answer.assertions,
            evidence_set=evidence_set,
        )
        unsupported_count = sum(1 for decision in decisions if not decision.supported)
        claim_refs = _claim_refs_for_decisions(decisions)
        if unsupported_count == 0:
            support_status = SupportStatus.SUPPORTED
            research_case.ensure_support_status_allowed(support_status)
        else:
            if len(claim_refs) == 0:
                raise ValueError("VerifiedResearchOutcome invalide: claim_refs vide")
            support_status = SupportStatus.PARTIALLY_SUPPORTED

        citations = _citations_for_decisions(evidence_set=evidence_set, decisions=decisions)
        version = VerifiedAnswerVersion(
            answer_id=parsed_answer.answer_id,
            answer_version=1,
            research_case_id=parsed_answer.research_case_id,
            evidence_set_id=parsed_answer.evidence_set_id,
            evidence_set_version=parsed_answer.evidence_set_version,
            evidence_set_snapshot=evidence_set,
            support_status=support_status,
            answer_text=_published_answer_text(
                assertions=parsed_answer.assertions,
                decisions=decisions,
            ),
            source_assertions=parsed_answer.assertions,
            assertion_decisions=decisions,
            citations=citations,
            claim_refs=claim_refs,
            policy_version=self.policy_version,
            published_at=occurred_at,
        )
        evaluated = AnswerSupportEvaluated(
            answer_id=parsed_answer.answer_id,
            support_status=support_status,
            unsupported_assertion_count=unsupported_count,
            policy_version=self.policy_version,
            occurred_at=occurred_at,
        )
        if support_status is SupportStatus.SUPPORTED:
            published = AnswerVerified(
                answer_id=parsed_answer.answer_id,
                answer_version=version.answer_version,
                evidence_set_version=version.evidence_set_version,
                citation_count=len(version.citations),
                occurred_at=occurred_at,
            )
        else:
            published = AnswerPartiallySupported(
                answer_id=parsed_answer.answer_id,
                answer_version=version.answer_version,
                knowledge_gap_count=len(getattr(research_case, "knowledge_gaps", ())),
                citation_count=len(version.citations),
                occurred_at=occurred_at,
            )
        updated_answer = parsed_answer.publish_verified_version(
            verified_answer_version=version,
            events=(evaluated, published),
        )
        return updated_answer, version, (evaluated, published)


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
    verified_answer_version: VerifiedAnswerVersion | None
    superseded_by: str | None
    drafted_at: str
    events: Sequence[
        AnswerDrafted
        | AnswerAssertionsExtracted
        | AnswerSupportEvaluated
        | AnswerVerified
        | AnswerPartiallySupported
        | AnswerSuperseded
    ]

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
            verified_answer_version=None,
            superseded_by=None,
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
        if self.verified_answer_version is not None and not isinstance(
            self.verified_answer_version,
            VerifiedAnswerVersion,
        ):
            raise ValueError("verified_answer_version invalide")
        if self.superseded_by is not None:
            object.__setattr__(
                self,
                "superseded_by",
                _ensure_answer_ref(self.superseded_by, "superseded_by"),
            )
        object.__setattr__(self, "drafted_at", _ensure_utc_instant(self.drafted_at, "drafted_at"))
        object.__setattr__(self, "events", _ensure_events(self.events))
        if self.status is AnswerStatus.DRAFT and len(self.assertions) > 0:
            raise ValueError("assertions interdites pour DRAFT")
        if self.status is AnswerStatus.ASSERTIONS_EXTRACTED and len(self.assertions) == 0:
            raise ValueError("assertions absentes pour ASSERTIONS_EXTRACTED")
        if self.status in {AnswerStatus.DRAFT, AnswerStatus.ASSERTIONS_EXTRACTED}:
            if self.verified_answer_version is not None:
                raise ValueError("verified_answer_version interdite avant publication")
        if self.status in {AnswerStatus.VERIFIED, AnswerStatus.PARTIALLY_SUPPORTED}:
            if self.verified_answer_version is None:
                raise ValueError("verified_answer_version absente")
            if self.verified_answer_version.answer_id != self.answer_id:
                raise ValueError("verified_answer_version hors answer")
            expected_status = (
                SupportStatus.SUPPORTED
                if self.status is AnswerStatus.VERIFIED
                else SupportStatus.PARTIALLY_SUPPORTED
            )
            if self.verified_answer_version.support_status is not expected_status:
                raise ValueError("answer_status incoherent avec support_status")
        if self.status is AnswerStatus.REJECTED and self.verified_answer_version is not None:
            raise ValueError("verified_answer_version interdite pour REJECTED")

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

    def publish_verified_version(
        self,
        *,
        verified_answer_version: VerifiedAnswerVersion,
        events: Sequence[AnswerSupportEvaluated | AnswerVerified | AnswerPartiallySupported],
    ) -> "Answer":
        if self.status is not AnswerStatus.ASSERTIONS_EXTRACTED:
            raise ValueError("answer non publiable")
        parsed_version = _ensure_verified_answer_version(verified_answer_version)
        if parsed_version.answer_id != self.answer_id:
            raise ValueError("verified_answer_version hors answer")
        if tuple(parsed_version.source_assertions) != self.assertions:
            raise ValueError("verified_answer_version assertions incoherentes")
        parsed_events = _ensure_publication_events(events)
        if parsed_version.support_status is SupportStatus.SUPPORTED:
            next_status = AnswerStatus.VERIFIED
        elif parsed_version.support_status is SupportStatus.PARTIALLY_SUPPORTED:
            next_status = AnswerStatus.PARTIALLY_SUPPORTED
        else:
            raise ValueError("support_status non publiable pour Answer")
        return replace(
            self,
            status=next_status,
            verified_answer_version=parsed_version,
            events=self.events + parsed_events,
        )

    def supersede(
        self,
        *,
        new_answer_ref: str,
        supersession_reason: str,
        occurred_at: str,
    ) -> tuple["Answer", AnswerSuperseded]:
        if not self.is_published or self.verified_answer_version is None:
            raise ValueError("answer non publiee")
        if self.superseded_by is not None:
            raise ValueError("answer deja supersedee")
        event = AnswerSuperseded(
            old_answer_ref=self.verified_answer_version.answer_ref,
            new_answer_ref=new_answer_ref,
            supersession_reason=supersession_reason,
            occurred_at=occurred_at,
        )
        return replace(
            self,
            superseded_by=event.new_answer_ref,
            events=self.events + (event,),
        ), event

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
            "verified_answer_version": (
                None
                if self.verified_answer_version is None
                else self.verified_answer_version.to_payload()
            ),
            "superseded_by": self.superseded_by,
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


def _ensure_answer(value: object) -> Answer:
    if not isinstance(value, Answer):
        raise ValueError("answer invalide")
    return value


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


def _ensure_verified_answer_version(value: object) -> VerifiedAnswerVersion:
    if not isinstance(value, VerifiedAnswerVersion):
        raise ValueError("verified_answer_version invalide")
    return value


def _ensure_assertion_support_decisions(value: object) -> tuple[AssertionSupportDecision, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("assertion_decisions invalides")
    decisions = tuple(value)
    ids: list[str] = []
    for decision in decisions:
        if not isinstance(decision, AssertionSupportDecision):
            raise ValueError("assertion_decision invalide")
        if decision.assertion_id in ids:
            raise ValueError("assertion_decision dupliquee")
        ids.append(decision.assertion_id)
    return decisions


def _ensure_assertion_decisions_cover(
    *,
    assertions: Sequence[AnswerAssertion],
    decisions: Sequence[AssertionSupportDecision],
) -> None:
    decision_ids = {decision.assertion_id for decision in decisions}
    assertion_ids = {assertion.assertion_id for assertion in assertions}
    missing = assertion_ids.difference(decision_ids)
    if len(missing) > 0:
        raise ValueError(f"answer_assertion sans decision: {sorted(missing)[0]}")
    extra = decision_ids.difference(assertion_ids)
    if len(extra) > 0:
        raise ValueError(f"assertion_decision hors answer: {sorted(extra)[0]}")


def _ensure_verified_claim_refs(
    value: object,
    *,
    allow_empty: bool,
) -> tuple[VerifiedClaimRef, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("verified_claim_refs invalides")
    refs = tuple(value)
    if not allow_empty and len(refs) == 0:
        raise ValueError("verified_claim_refs absents")
    ids: list[tuple[str, int]] = []
    for ref in refs:
        if not isinstance(ref, VerifiedClaimRef):
            raise ValueError("verified_claim_ref invalide")
        key = (ref.claim_id, ref.claim_version)
        if key in ids:
            raise ValueError("verified_claim_ref duplique")
        ids.append(key)
    return refs


def _ensure_citation_sequence(
    value: object,
    *,
    allow_empty: bool,
) -> tuple[Citation, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("citations invalides")
    citations = tuple(value)
    if not allow_empty and len(citations) == 0:
        raise ValueError("citations absentes")
    ids: list[str] = []
    for citation in citations:
        if not isinstance(citation, Citation):
            raise ValueError("citation invalide")
        if citation.citation_id in ids:
            raise ValueError("citation dupliquee")
        ids.append(citation.citation_id)
    return citations


def _ensure_publication_events(
    value: object,
) -> tuple[AnswerSupportEvaluated | AnswerVerified | AnswerPartiallySupported, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("events publication invalides")
    events = tuple(value)
    if len(events) != 2:
        raise ValueError("events publication invalides")
    if not isinstance(events[0], AnswerSupportEvaluated):
        raise ValueError("event AnswerSupportEvaluated absent")
    if not isinstance(events[1], (AnswerVerified, AnswerPartiallySupported)):
        raise ValueError("event publication absent")
    return events


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


def _ensure_events(
    value: object,
) -> tuple[
    AnswerDrafted
    | AnswerAssertionsExtracted
    | AnswerSupportEvaluated
    | AnswerVerified
    | AnswerPartiallySupported
    | AnswerSuperseded,
    ...,
]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("events invalides")
    events = tuple(value)
    if len(events) == 0:
        raise ValueError("events absents")
    for event in events:
        if not isinstance(
            event,
            (
                AnswerDrafted,
                AnswerAssertionsExtracted,
                AnswerSupportEvaluated,
                AnswerVerified,
                AnswerPartiallySupported,
                AnswerSuperseded,
            ),
        ):
            raise ValueError("event answer invalide")
    return events


def _support_decisions_for(
    *,
    assertions: Sequence[AnswerAssertion],
    evidence_set: EvidenceSet,
) -> tuple[AssertionSupportDecision, ...]:
    claim_by_id = {claim_ref.claim_id: claim_ref for claim_ref in evidence_set.verified_claim_refs}
    citation_by_evidence_id = {citation.evidence_id: citation for citation in evidence_set.citations}
    decisions: list[AssertionSupportDecision] = []
    for assertion in assertions:
        if assertion.origin.origin_type is AssertionOriginType.SOURCE:
            claim_ref = claim_by_id.get(assertion.origin.basis_refs[0])
            if claim_ref is not None:
                citation_ids = tuple(
                    citation_by_evidence_id[evidence_ref.evidence_id].citation_id
                    for evidence_ref in claim_ref.evidence_refs
                    if evidence_ref.evidence_id in citation_by_evidence_id
                )
                if len(citation_ids) > 0:
                    decisions.append(
                        AssertionSupportDecision(
                            assertion_id=assertion.assertion_id,
                            basis_refs=assertion.origin.basis_refs,
                            publication_status=AssertionPublicationStatus.SUPPORTED,
                            reason_code="SUPPORTED",
                            public_reason="Assertion supportee par claim verifie et citation ouvrable.",
                            claim_refs=(claim_ref,),
                            citation_ids=citation_ids,
                        )
                    )
                    continue
            decisions.append(
                AssertionSupportDecision(
                    assertion_id=assertion.assertion_id,
                    basis_refs=assertion.origin.basis_refs,
                    publication_status=AssertionPublicationStatus.QUALIFIED,
                    reason_code="ANSWER_ASSERTION_UNSUPPORTED",
                    public_reason="Assertion importante sans claim verifie et citation admissible.",
                    claim_refs=(),
                    citation_ids=(),
                )
            )
            continue
        if assertion.origin.origin_type is AssertionOriginType.DEDUCTION:
            claim_refs, citation_ids = _support_refs_for_basis_refs(
                basis_refs=assertion.origin.basis_refs,
                evidence_set=evidence_set,
            )
            decisions.append(
                AssertionSupportDecision(
                    assertion_id=assertion.assertion_id,
                    basis_refs=assertion.origin.basis_refs,
                    publication_status=AssertionPublicationStatus.QUALIFIED,
                    reason_code="ANSWER_ASSERTION_INDIRECT_ONLY",
                    public_reason="Deduction qualifiee: une preuve indirecte seule ne suffit pas pour SUPPORTED.",
                    claim_refs=claim_refs,
                    citation_ids=citation_ids,
                )
            )
            continue
        decisions.append(
            AssertionSupportDecision(
                assertion_id=assertion.assertion_id,
                basis_refs=assertion.origin.basis_refs,
                publication_status=AssertionPublicationStatus.QUALIFIED,
                reason_code="ANSWER_ASSERTION_DESIGN_CHOICE",
                public_reason="Choix de conception publie comme qualification, pas comme fait documentaire.",
                claim_refs=(),
                citation_ids=(),
            )
        )
    return tuple(decisions)


def _support_refs_for_basis_refs(
    *,
    basis_refs: Sequence[str],
    evidence_set: EvidenceSet,
) -> tuple[tuple[VerifiedClaimRef, ...], tuple[str, ...]]:
    claim_by_id = {claim_ref.claim_id: claim_ref for claim_ref in evidence_set.verified_claim_refs}
    citation_by_evidence_id = {citation.evidence_id: citation for citation in evidence_set.citations}
    claim_refs: list[VerifiedClaimRef] = []
    citation_ids: list[str] = []
    for basis_ref in basis_refs:
        claim_ref = claim_by_id.get(basis_ref)
        if claim_ref is None:
            continue
        claim_refs.append(claim_ref)
        for evidence_ref in claim_ref.evidence_refs:
            citation = citation_by_evidence_id.get(evidence_ref.evidence_id)
            if citation is not None and citation.citation_id not in citation_ids:
                citation_ids.append(citation.citation_id)
    return tuple(claim_refs), tuple(citation_ids)


def _citations_for_decisions(
    *,
    evidence_set: EvidenceSet,
    decisions: Sequence[AssertionSupportDecision],
) -> tuple[Citation, ...]:
    requested_ids = []
    for decision in decisions:
        for citation_id in decision.citation_ids:
            if citation_id not in requested_ids:
                requested_ids.append(citation_id)
    citations_by_id = {citation.citation_id: citation for citation in evidence_set.citations}
    citations = tuple(citations_by_id[citation_id] for citation_id in requested_ids)
    return _ensure_citation_sequence(citations, allow_empty=False)


def _claim_refs_for_decisions(decisions: Sequence[AssertionSupportDecision]) -> tuple[VerifiedClaimRef, ...]:
    refs: list[VerifiedClaimRef] = []
    keys: set[tuple[str, int]] = set()
    for decision in decisions:
        for claim_ref in decision.claim_refs:
            key = (claim_ref.claim_id, claim_ref.claim_version)
            if key not in keys:
                refs.append(claim_ref)
                keys.add(key)
    return tuple(refs)


def _published_answer_text(
    *,
    assertions: Sequence[AnswerAssertion],
    decisions: Sequence[AssertionSupportDecision],
) -> str:
    decisions_by_assertion_id = {decision.assertion_id: decision for decision in decisions}
    lines: list[str] = []
    for assertion in assertions:
        decision = decisions_by_assertion_id[assertion.assertion_id]
        if decision.publication_status is AssertionPublicationStatus.SUPPORTED:
            lines.append(assertion.text)
        elif decision.publication_status is AssertionPublicationStatus.QUALIFIED:
            lines.append(f"Qualification documentaire: {assertion.text} ({decision.public_reason})")
    if len(lines) == 0:
        raise ValueError("answer_text publie vide")
    return "\n".join(lines)


def _research_conflict_payload(assessment: ContradictionAssessment) -> dict[str, Any]:
    if not isinstance(assessment, ContradictionAssessment):
        raise ValueError("contradiction_assessment invalide")
    return {
        "summary": assessment.public_reason,
        "claim_refs": [
            f"{assessment.source_claim_ref.claim_id}@{assessment.source_claim_ref.claim_version}",
            f"{assessment.target_claim_ref.claim_id}@{assessment.target_claim_ref.claim_version}",
        ],
        "blocking": assessment.blocks_publication,
    }


def _knowledge_gap_payload(gap: KnowledgeGap) -> dict[str, Any]:
    if not isinstance(gap, KnowledgeGap):
        raise ValueError("knowledge_gap invalide")
    return {
        "topic": gap.affected_obligation,
        "impact": gap.public_reason,
    }


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


def _ensure_non_negative_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
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


def _ensure_answer_ref(value: object, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if _ANSWER_REF_PATTERN.fullmatch(text) is None:
        raise ValueError(f"{field_name} invalide")
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
    "AnswerFreshnessPolicy",
    "AnswerPartiallySupported",
    "AnswerStatus",
    "AnswerSupportEvaluated",
    "AnswerSupportPolicy",
    "AnswerSuperseded",
    "AnswerVerified",
    "AssertionEvaluationStatus",
    "AssertionOrigin",
    "AssertionOriginType",
    "AssertionPublicationStatus",
    "AssertionSupportDecision",
    "CitationIntegrityPolicy",
    "VerifiedAnswerVersion",
    "answer_id_for",
]
