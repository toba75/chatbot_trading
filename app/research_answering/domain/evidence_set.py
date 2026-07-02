"""Jeu de preuves RA scellable avant rédaction de réponse."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from app.contracts.evidence_claims import EvidenceRef, VerifiedClaimRef
from app.contracts.source_references import SourceLocator
from app.research_answering.domain.contradiction_assessment import SupportStatus


_HASH_HEX_LENGTH = 24
_UTC_INSTANT_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
_EVIDENCE_SET_ID_PATTERN = re.compile(r"^EVS-[A-Z0-9][A-Z0-9-]*$")
_CITATION_ID_PATTERN = re.compile(r"^CIT-[A-Z0-9][A-Z0-9-]*$")
_DEEP_COVERAGE_POLARITIES = frozenset({"ANY", "FAVORABLE", "UNFAVORABLE", "NEUTRAL"})
_DEEP_COVERAGE_SOURCE_KINDS = frozenset({"PRIMARY", "SECONDARY"})
_CURRENT_DATA_REQUIRED_REASON = "CURRENT_DATA_REQUIRED"


@dataclass(frozen=True)
class EvidenceSetVersion:
    """Version publiée du jeu de preuves RA."""

    value: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _ensure_positive_integer(self.value, "evidence_set_version"))

    def to_payload(self) -> int:
        return self.value


@dataclass(frozen=True)
class Citation:
    """Citation ouvrable vers le SourceLocator d'une preuve retenue."""

    citation_id: str
    evidence_id: str
    source_locator: SourceLocator
    quoted_span_hash: str

    @classmethod
    def from_evidence_ref(cls, evidence_ref: EvidenceRef) -> "Citation":
        parsed_ref = _ensure_evidence_ref(evidence_ref)
        return cls(
            citation_id=_citation_id_for(parsed_ref),
            evidence_id=parsed_ref.evidence_id,
            source_locator=parsed_ref.source_locator,
            quoted_span_hash=parsed_ref.quoted_span_hash,
        )

    def __post_init__(self) -> None:
        object.__setattr__(self, "citation_id", _ensure_citation_id(self.citation_id))
        object.__setattr__(self, "evidence_id", _ensure_evidence_ref_id(self.evidence_id))
        if not isinstance(self.source_locator, SourceLocator):
            raise ValueError("source_locator absent")
        object.__setattr__(
            self,
            "quoted_span_hash",
            _ensure_hash(self.quoted_span_hash, "quoted_span_hash"),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "citation_id": self.citation_id,
            "evidence_id": self.evidence_id,
            "source_locator": self.source_locator.to_payload(),
            "quoted_span_hash": self.quoted_span_hash,
        }


@dataclass(frozen=True)
class EvidenceCoveragePolicy:
    """Politique RA de couverture minimale des obligations du plan."""

    required_obligations: Sequence[str]
    policy_version: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "required_obligations",
            _ensure_text_tuple(self.required_obligations, "coverage_obligations"),
        )
        object.__setattr__(
            self,
            "policy_version",
            _ensure_text(self.policy_version, "coverage_policy_version"),
        )

    def validate(self, candidates: Sequence[object]) -> None:
        parsed_candidates = _ensure_candidates(candidates)
        covered: set[str] = set()
        for candidate in parsed_candidates:
            covered.update(_candidate_covered_obligations(candidate))
        missing = tuple(
            obligation for obligation in self.required_obligations if obligation not in covered
        )
        if len(missing) > 0:
            raise ValueError(f"coverage_obligation non couverte: {missing[0]}")


@dataclass(frozen=True)
class DeepCoverageRequirement:
    """Obligation RA approfondie évaluée avant synthèse multi-sources."""

    obligation_name: str
    critical: bool
    required_polarity: str
    requires_primary_source: bool
    reason_code: str
    public_reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "obligation_name", _ensure_text(self.obligation_name, "obligation_name"))
        if not isinstance(self.critical, bool):
            raise ValueError("critical non booleen")
        object.__setattr__(self, "required_polarity", _ensure_deep_polarity(self.required_polarity))
        if not isinstance(self.requires_primary_source, bool):
            raise ValueError("requires_primary_source non booleen")
        reason_code = _ensure_text(self.reason_code, "reason_code")
        if reason_code == _CURRENT_DATA_REQUIRED_REASON:
            raise ValueError("CURRENT_DATA_REQUIRED separe de couverture documentaire")
        object.__setattr__(self, "reason_code", reason_code)
        object.__setattr__(self, "public_reason", _ensure_text(self.public_reason, "public_reason"))


@dataclass(frozen=True)
class DeepEvidenceCoverageEvaluation:
    """Décision publique de couverture documentaire approfondie."""

    support_status: SupportStatus
    missing_obligations: Sequence[str]
    critical_missing_obligations: Sequence[str]
    qualified_obligations: Sequence[str]
    reason_codes: Sequence[str]
    public_reasons: Sequence[str]
    covered_obligations: Sequence[str]

    def __post_init__(self) -> None:
        if not isinstance(self.support_status, SupportStatus):
            raise ValueError("support_status invalide")
        object.__setattr__(
            self,
            "missing_obligations",
            _ensure_text_sequence_allow_empty(self.missing_obligations, "missing_obligations"),
        )
        object.__setattr__(
            self,
            "critical_missing_obligations",
            _ensure_text_sequence_allow_empty(
                self.critical_missing_obligations,
                "critical_missing_obligations",
            ),
        )
        object.__setattr__(
            self,
            "qualified_obligations",
            _ensure_text_sequence_allow_empty(self.qualified_obligations, "qualified_obligations"),
        )
        object.__setattr__(
            self,
            "reason_codes",
            _ensure_text_sequence_allow_empty(self.reason_codes, "reason_codes"),
        )
        object.__setattr__(
            self,
            "public_reasons",
            _ensure_text_sequence_allow_empty(self.public_reasons, "public_reasons"),
        )
        object.__setattr__(
            self,
            "covered_obligations",
            _ensure_text_sequence_allow_empty(self.covered_obligations, "covered_obligations"),
        )
        if len(self.missing_obligations) != len(self.reason_codes):
            raise ValueError("reason_codes incoherents")
        if len(self.missing_obligations) != len(self.public_reasons):
            raise ValueError("public_reasons incoherentes")
        if self.support_status is SupportStatus.INSUFFICIENT_EVIDENCE:
            if len(self.critical_missing_obligations) == 0:
                raise ValueError("obligation critique manquante absente")
            return
        if self.support_status is SupportStatus.PARTIALLY_SUPPORTED:
            if len(self.critical_missing_obligations) > 0:
                raise ValueError("PARTIALLY_SUPPORTED avec obligation critique manquante")
            if len(self.qualified_obligations) == 0:
                raise ValueError("qualified_obligations absentes")
            return
        if self.support_status is SupportStatus.SUPPORTED:
            if len(self.missing_obligations) > 0:
                raise ValueError("SUPPORTED avec couverture manquante")
            return
        raise ValueError("support_status couverture non supporte")


@dataclass(frozen=True)
class DeepEvidenceCoveragePolicy:
    """Politique RA M-009 qui rend les lacunes de couverture auditables."""

    coverage_requirements: Sequence[DeepCoverageRequirement]
    policy_version: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "coverage_requirements",
            _ensure_deep_coverage_requirements(self.coverage_requirements),
        )
        object.__setattr__(
            self,
            "policy_version",
            _ensure_text(self.policy_version, "coverage_policy_version"),
        )

    def evaluate(self, candidates: Sequence[object]) -> DeepEvidenceCoverageEvaluation:
        parsed_candidates = _ensure_deep_coverage_candidates(candidates)
        missing_obligations: list[str] = []
        critical_missing_obligations: list[str] = []
        qualified_obligations: list[str] = []
        reason_codes: list[str] = []
        public_reasons: list[str] = []
        covered_obligations: list[str] = []

        for requirement in self.coverage_requirements:
            matching_candidates = tuple(
                candidate
                for candidate in parsed_candidates
                if requirement.obligation_name in _candidate_covered_obligations(candidate)
            )
            if len(matching_candidates) > 0:
                covered_obligations.append(requirement.obligation_name)
            if self._is_requirement_satisfied(requirement, matching_candidates):
                continue

            missing_obligations.append(requirement.obligation_name)
            reason_codes.append(requirement.reason_code)
            public_reasons.append(requirement.public_reason)
            if requirement.critical:
                critical_missing_obligations.append(requirement.obligation_name)
            else:
                qualified_obligations.append(requirement.obligation_name)

        if len(critical_missing_obligations) > 0:
            support_status = SupportStatus.INSUFFICIENT_EVIDENCE
        elif len(qualified_obligations) > 0:
            support_status = SupportStatus.PARTIALLY_SUPPORTED
        else:
            support_status = SupportStatus.SUPPORTED

        return DeepEvidenceCoverageEvaluation(
            support_status=support_status,
            missing_obligations=tuple(missing_obligations),
            critical_missing_obligations=tuple(critical_missing_obligations),
            qualified_obligations=tuple(qualified_obligations),
            reason_codes=tuple(reason_codes),
            public_reasons=tuple(public_reasons),
            covered_obligations=tuple(covered_obligations),
        )

    def _is_requirement_satisfied(
        self,
        requirement: DeepCoverageRequirement,
        candidates: tuple[object, ...],
    ) -> bool:
        if len(candidates) == 0:
            return False
        if requirement.required_polarity != "ANY" and not any(
            _candidate_evidence_polarity(candidate) == requirement.required_polarity
            for candidate in candidates
        ):
            return False
        if requirement.requires_primary_source and not any(
            _candidate_source_kind(candidate) == "PRIMARY"
            for candidate in candidates
        ):
            return False
        return True


@dataclass(frozen=True)
class EvidenceDiversificationPolicy:
    """Politique RA empêchant les doublons de preuve dans un EvidenceSet."""

    policy_version: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "policy_version",
            _ensure_text(self.policy_version, "diversification_policy_version"),
        )

    def validate(self, candidates: Sequence[object]) -> None:
        parsed_candidates = _ensure_candidates(candidates)
        evidence_ids = tuple(_candidate_evidence_ref(candidate).evidence_id for candidate in parsed_candidates)
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("evidence_ref duplique")
        locator_keys = tuple(
            _source_locator_key(_candidate_evidence_ref(candidate).source_locator)
            for candidate in parsed_candidates
        )
        if len(locator_keys) != len(set(locator_keys)):
            raise ValueError("source_locator duplique")


@dataclass(frozen=True)
class EvidenceCollectionCompleted:
    """Événement RA d'assemblage de preuves avant scellement."""

    research_case_id: str
    evidence_set_id: str
    evidence_count: int
    verified_claim_count: int
    occurred_at: str

    @property
    def event_type(self) -> str:
        return "EvidenceCollectionCompleted"

    def __post_init__(self) -> None:
        object.__setattr__(self, "research_case_id", _ensure_research_case_id(self.research_case_id))
        object.__setattr__(self, "evidence_set_id", _ensure_evidence_set_id(self.evidence_set_id))
        object.__setattr__(self, "evidence_count", _ensure_positive_integer(self.evidence_count, "evidence_count"))
        object.__setattr__(
            self,
            "verified_claim_count",
            _ensure_positive_integer(self.verified_claim_count, "verified_claim_count"),
        )
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at, "occurred_at"))

    def to_payload(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "occurred_at": self.occurred_at,
            "payload": {
                "research_case_id": self.research_case_id,
                "evidence_set_id": self.evidence_set_id,
                "evidence_count": self.evidence_count,
                "verified_claim_count": self.verified_claim_count,
            },
        }


@dataclass(frozen=True)
class EvidenceSetSealed:
    """Événement RA de scellement du jeu de preuves."""

    research_case_id: str
    evidence_set_id: str
    evidence_set_version: int
    evidence_hash: str
    occurred_at: str

    @property
    def event_type(self) -> str:
        return "EvidenceSetSealed"

    def __post_init__(self) -> None:
        object.__setattr__(self, "research_case_id", _ensure_research_case_id(self.research_case_id))
        object.__setattr__(self, "evidence_set_id", _ensure_evidence_set_id(self.evidence_set_id))
        object.__setattr__(
            self,
            "evidence_set_version",
            _ensure_positive_integer(self.evidence_set_version, "evidence_set_version"),
        )
        object.__setattr__(self, "evidence_hash", _ensure_sha256(self.evidence_hash, "evidence_hash"))
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at, "occurred_at"))

    def to_payload(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "occurred_at": self.occurred_at,
            "payload": {
                "research_case_id": self.research_case_id,
                "evidence_set_id": self.evidence_set_id,
                "evidence_set_version": self.evidence_set_version,
                "evidence_hash": self.evidence_hash,
            },
        }


@dataclass(frozen=True)
class EvidenceSet:
    """Objet-valeur RA des preuves retenues pour une réponse."""

    evidence_set_id: str
    research_case_id: str
    version: EvidenceSetVersion
    coverage_obligations: Sequence[str]
    evidence_refs: Sequence[EvidenceRef]
    verified_claim_refs: Sequence[VerifiedClaimRef]
    citations: Sequence[Citation]
    coverage_policy_version: str
    diversification_policy_version: str
    sealed: bool

    @classmethod
    def assemble(
        cls,
        *,
        research_case_id: str,
        coverage_obligations: Sequence[str],
        candidates: Sequence[object],
        verified_claim_refs: Sequence[VerifiedClaimRef],
        coverage_policy_version: str,
        diversification_policy_version: str,
    ) -> "EvidenceSet":
        parsed_case_id = _ensure_research_case_id(research_case_id)
        parsed_obligations = _ensure_text_tuple(coverage_obligations, "coverage_obligations")
        parsed_candidates = _ensure_candidates(candidates)
        EvidenceCoveragePolicy(
            required_obligations=parsed_obligations,
            policy_version=coverage_policy_version,
        ).validate(parsed_candidates)
        EvidenceDiversificationPolicy(
            policy_version=diversification_policy_version,
        ).validate(parsed_candidates)
        evidence_refs = tuple(_candidate_evidence_ref(candidate) for candidate in parsed_candidates)
        claim_refs = _ensure_verified_claim_refs(verified_claim_refs, evidence_refs)
        citations = tuple(Citation.from_evidence_ref(evidence_ref) for evidence_ref in evidence_refs)
        return cls(
            evidence_set_id=_evidence_set_id_for(
                research_case_id=parsed_case_id,
                evidence_refs=evidence_refs,
                verified_claim_refs=claim_refs,
            ),
            research_case_id=parsed_case_id,
            version=EvidenceSetVersion(1),
            coverage_obligations=parsed_obligations,
            evidence_refs=evidence_refs,
            verified_claim_refs=claim_refs,
            citations=citations,
            coverage_policy_version=coverage_policy_version,
            diversification_policy_version=diversification_policy_version,
            sealed=False,
        )

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_set_id", _ensure_evidence_set_id(self.evidence_set_id))
        object.__setattr__(self, "research_case_id", _ensure_research_case_id(self.research_case_id))
        if not isinstance(self.version, EvidenceSetVersion):
            raise ValueError("evidence_set_version invalide")
        object.__setattr__(
            self,
            "coverage_obligations",
            _ensure_text_tuple(self.coverage_obligations, "coverage_obligations"),
        )
        object.__setattr__(self, "evidence_refs", _ensure_evidence_refs(self.evidence_refs))
        object.__setattr__(
            self,
            "verified_claim_refs",
            _ensure_verified_claim_refs(self.verified_claim_refs, self.evidence_refs),
        )
        object.__setattr__(self, "citations", _ensure_citations(self.citations, self.evidence_refs))
        object.__setattr__(
            self,
            "coverage_policy_version",
            _ensure_text(self.coverage_policy_version, "coverage_policy_version"),
        )
        object.__setattr__(
            self,
            "diversification_policy_version",
            _ensure_text(self.diversification_policy_version, "diversification_policy_version"),
        )
        if not isinstance(self.sealed, bool):
            raise ValueError("evidence_set sealed non booleen")

    @property
    def evidence_hash(self) -> str:
        return _hash_payload(self._content_payload())

    def add_evidence(self, candidate: object) -> "EvidenceSet":
        if self.sealed:
            raise ValueError("evidence_set scelle")
        parsed_candidate = _ensure_candidate(candidate)
        evidence_refs = self.evidence_refs + (_candidate_evidence_ref(parsed_candidate),)
        citations = self.citations + (Citation.from_evidence_ref(_candidate_evidence_ref(parsed_candidate)),)
        return replace(self, evidence_refs=evidence_refs, citations=citations)

    def seal(self, *, citation_resolver: object, occurred_at: str) -> tuple["EvidenceSet", EvidenceSetSealed]:
        _ensure_utc_instant(occurred_at, "occurred_at")
        if self.sealed:
            raise ValueError("evidence_set deja scelle")
        if not callable(getattr(citation_resolver, "resolve", None)):
            raise ValueError("citation_resolver sans resolve")
        for citation in self.citations:
            try:
                resolved = citation_resolver.resolve(citation)
            except ValueError as exc:
                raise ValueError("ANSWER_CITATION_UNRESOLVABLE") from exc
            if resolved is None:
                raise ValueError("ANSWER_CITATION_UNRESOLVABLE")
        sealed_set = replace(self, sealed=True)
        event = EvidenceSetSealed(
            research_case_id=sealed_set.research_case_id,
            evidence_set_id=sealed_set.evidence_set_id,
            evidence_set_version=sealed_set.version.value,
            evidence_hash=sealed_set.evidence_hash,
            occurred_at=occurred_at,
        )
        return sealed_set, event

    def to_payload(self) -> dict[str, Any]:
        return {
            **self._content_payload(),
            "evidence_hash": self.evidence_hash,
        }

    def _content_payload(self) -> dict[str, Any]:
        return {
            "evidence_set_id": self.evidence_set_id,
            "research_case_id": self.research_case_id,
            "version": self.version.to_payload(),
            "coverage_obligations": self.coverage_obligations,
            "evidence_refs": [evidence_ref.to_payload() for evidence_ref in self.evidence_refs],
            "verified_claim_refs": [
                verified_claim_ref.to_payload()
                for verified_claim_ref in self.verified_claim_refs
            ],
            "citations": [citation.to_payload() for citation in self.citations],
            "coverage_policy_version": self.coverage_policy_version,
            "diversification_policy_version": self.diversification_policy_version,
            "sealed": self.sealed,
        }


def _ensure_candidates(value: Sequence[object]) -> tuple[object, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("evidence_candidates invalides")
    candidates = tuple(_ensure_candidate(candidate) for candidate in value)
    if len(candidates) == 0:
        raise ValueError("evidence_refs absentes")
    return candidates


def _ensure_candidate(value: object) -> object:
    _candidate_evidence_ref(value)
    _candidate_covered_obligations(value)
    return value


def _candidate_evidence_ref(candidate: object) -> EvidenceRef:
    evidence_ref = getattr(candidate, "evidence_ref", None)
    if evidence_ref is None:
        raise ValueError("evidence_ref absent")
    if getattr(evidence_ref, "source_locator", None) is None:
        raise ValueError("source_locator absent")
    return _ensure_evidence_ref(evidence_ref)


def _candidate_covered_obligations(candidate: object) -> tuple[str, ...]:
    return _ensure_text_tuple(
        getattr(candidate, "covered_obligations", None),
        "covered_obligations",
    )


def _candidate_evidence_polarity(candidate: object) -> str:
    return _ensure_deep_polarity(getattr(candidate, "evidence_polarity", None))


def _candidate_source_kind(candidate: object) -> str:
    return _ensure_deep_source_kind(getattr(candidate, "source_kind", None))


def _ensure_deep_coverage_requirements(value: object) -> tuple[DeepCoverageRequirement, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("coverage_requirements invalides")
    requirements = tuple(value)
    if len(requirements) == 0:
        raise ValueError("coverage_requirements absentes")
    obligation_names: list[str] = []
    for requirement in requirements:
        if not isinstance(requirement, DeepCoverageRequirement):
            raise ValueError("coverage_requirement invalide")
        if requirement.obligation_name in obligation_names:
            raise ValueError("coverage_requirement dupliquee")
        obligation_names.append(requirement.obligation_name)
    return requirements


def _ensure_deep_coverage_candidates(value: object) -> tuple[object, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("evidence_candidates invalides")
    candidates = tuple(value)
    if len(candidates) == 0:
        raise ValueError("evidence_refs absentes")
    for candidate in candidates:
        _candidate_covered_obligations(candidate)
        _candidate_evidence_polarity(candidate)
        _candidate_source_kind(candidate)
    return candidates


def _ensure_evidence_refs(value: Sequence[EvidenceRef]) -> tuple[EvidenceRef, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("evidence_refs invalides")
    evidence_refs = tuple(_ensure_evidence_ref(item) for item in value)
    if len(evidence_refs) == 0:
        raise ValueError("evidence_refs absentes")
    ids = tuple(evidence_ref.evidence_id for evidence_ref in evidence_refs)
    if len(ids) != len(set(ids)):
        raise ValueError("evidence_ref duplique")
    return evidence_refs


def _ensure_verified_claim_refs(
    value: Sequence[VerifiedClaimRef],
    evidence_refs: Sequence[EvidenceRef],
) -> tuple[VerifiedClaimRef, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("verified_claim_refs invalides")
    verified_claim_refs = tuple(value)
    if len(verified_claim_refs) == 0:
        raise ValueError("verified_claim_refs absents")
    for verified_claim_ref in verified_claim_refs:
        if getattr(verified_claim_ref, "status", None) != "VERIFIED":
            raise ValueError("claim non verifie")
        if not isinstance(verified_claim_ref, VerifiedClaimRef):
            raise ValueError("verified_claim_ref invalide")
    claim_ids = tuple(claim_ref.claim_id for claim_ref in verified_claim_refs)
    if len(claim_ids) != len(set(claim_ids)):
        raise ValueError("verified_claim_ref duplique")
    expected_evidence_ids = {evidence_ref.evidence_id for evidence_ref in evidence_refs}
    claim_evidence_ids = {
        evidence_ref.evidence_id
        for claim_ref in verified_claim_refs
        for evidence_ref in claim_ref.evidence_refs
    }
    missing = expected_evidence_ids.difference(claim_evidence_ids)
    if len(missing) > 0:
        raise ValueError(f"claim verifie absent pour preuve: {sorted(missing)[0]}")
    return verified_claim_refs


def _ensure_citations(
    value: Sequence[Citation],
    evidence_refs: Sequence[EvidenceRef],
) -> tuple[Citation, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("citations invalides")
    citations = tuple(value)
    if len(citations) == 0:
        raise ValueError("citations absentes")
    for citation in citations:
        if not isinstance(citation, Citation):
            raise ValueError("citation invalide")
    citation_evidence_ids = tuple(citation.evidence_id for citation in citations)
    expected_evidence_ids = tuple(evidence_ref.evidence_id for evidence_ref in evidence_refs)
    if set(citation_evidence_ids) != set(expected_evidence_ids):
        raise ValueError("citations incoherentes")
    if len(citation_evidence_ids) != len(set(citation_evidence_ids)):
        raise ValueError("citation dupliquee")
    return citations


def _ensure_evidence_ref(value: object) -> EvidenceRef:
    if not isinstance(value, EvidenceRef):
        raise ValueError("evidence_ref invalide")
    return value


def _ensure_research_case_id(value: object) -> str:
    text = _ensure_text(value, "research_case_id")
    if not text.startswith("RSC-"):
        raise ValueError("research_case_id invalide")
    return text


def _ensure_evidence_set_id(value: object) -> str:
    text = _ensure_text(value, "evidence_set_id")
    if _EVIDENCE_SET_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("evidence_set_id invalide")
    return text


def _ensure_evidence_ref_id(value: object) -> str:
    text = _ensure_text(value, "evidence_id")
    if not text.startswith("EVS-"):
        raise ValueError("evidence_id invalide")
    return text


def _ensure_citation_id(value: object) -> str:
    text = _ensure_text(value, "citation_id")
    if _CITATION_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("citation_id invalide")
    return text


def _ensure_text_tuple(value: object, field_name: str) -> tuple[str, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} invalides")
    parsed = tuple(_ensure_text(item, field_name) for item in value)
    if len(parsed) == 0:
        raise ValueError(f"{field_name} absentes")
    if len(parsed) != len(set(parsed)):
        raise ValueError(f"{field_name} dupliquees")
    return parsed


def _ensure_text_sequence_allow_empty(value: object, field_name: str) -> tuple[str, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} invalides")
    parsed = tuple(_ensure_text(item, field_name) for item in value)
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


def _ensure_deep_polarity(value: object) -> str:
    text = _ensure_text(value, "evidence_polarity")
    if text not in _DEEP_COVERAGE_POLARITIES:
        raise ValueError(f"evidence_polarity invalide: {text}")
    return text


def _ensure_deep_source_kind(value: object) -> str:
    text = _ensure_text(value, "source_kind")
    if text not in _DEEP_COVERAGE_SOURCE_KINDS:
        raise ValueError(f"source_kind invalide: {text}")
    return text


def _ensure_utc_instant(value: object, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if _UTC_INSTANT_PATTERN.fullmatch(text) is None:
        raise ValueError(f"{field_name} invalide")
    return text


def _ensure_positive_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_hash(value: object, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if re.fullmatch(r"[0-9a-f]{32}|[0-9a-f]{64}", text, flags=re.IGNORECASE) is None:
        raise ValueError(f"{field_name} invalide")
    return text


def _ensure_sha256(value: object, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if re.fullmatch(r"[0-9a-f]{64}", text) is None:
        raise ValueError(f"{field_name} invalide")
    return text


def _source_locator_key(source_locator: SourceLocator) -> tuple[object, ...]:
    if not isinstance(source_locator, SourceLocator):
        raise ValueError("source_locator absent")
    return (
        source_locator.canonical_version_id,
        source_locator.document_id,
        source_locator.page_pdf,
        source_locator.item_id,
        source_locator.bbox,
        source_locator.content_hash,
    )


def _citation_id_for(evidence_ref: EvidenceRef) -> str:
    payload = {
        "evidence_id": evidence_ref.evidence_id,
        "source_locator": evidence_ref.source_locator.to_payload(),
        "quoted_span_hash": evidence_ref.quoted_span_hash,
    }
    return f"CIT-{_hash_payload(payload)[:_HASH_HEX_LENGTH].upper()}"


def _evidence_set_id_for(
    *,
    research_case_id: str,
    evidence_refs: Sequence[EvidenceRef],
    verified_claim_refs: Sequence[VerifiedClaimRef],
) -> str:
    payload = {
        "research_case_id": research_case_id,
        "evidence_ids": tuple(evidence_ref.evidence_id for evidence_ref in evidence_refs),
        "claim_ids": tuple(claim_ref.claim_id for claim_ref in verified_claim_refs),
    }
    return f"EVS-{_hash_payload(payload)[:_HASH_HEX_LENGTH].upper()}"


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
    if hasattr(value, "to_payload") and callable(value.to_payload):
        return _json_ready(value.to_payload())
    return value


__all__ = [
    "Citation",
    "DeepCoverageRequirement",
    "DeepEvidenceCoverageEvaluation",
    "DeepEvidenceCoveragePolicy",
    "EvidenceCollectionCompleted",
    "EvidenceCoveragePolicy",
    "EvidenceDiversificationPolicy",
    "EvidenceSet",
    "EvidenceSetSealed",
    "EvidenceSetVersion",
]
