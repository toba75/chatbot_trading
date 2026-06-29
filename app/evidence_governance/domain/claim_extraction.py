"""Extraction de brouillons de claims EG."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any

from app.contracts.source_references import SourceLocator


_HASH_HEX_ALPHABET = frozenset("0123456789abcdef")
_CLAIM_ID_PATTERN = re.compile(r"^CLM-[A-Z0-9][A-Z0-9-]*$")
_ALLOWED_PROPOSAL_FIELDS = frozenset(
    {
        "claim_type",
        "canonical_text",
        "source_text",
        "scope",
        "conditions",
        "limitations",
        "evidence_span",
    }
)
_ALLOWED_SCOPE_FIELDS = frozenset({"universe", "horizon", "metric", "frequency"})
_ALLOWED_EVIDENCE_SPAN_FIELDS = frozenset({"quoted_text", "start_char", "end_char"})
_MODALITY_MARKERS = ("peut", "peuvent", "pourrait", "pourraient", "doit", "doivent")
_NEGATION_MARKERS = (" ne ", " n'", " pas", " jamais", " aucun", " aucune")
_COMPOSITE_MARKERS = (" et elle ", " et il ", " et elles ", " et ils ", " mais elle ", " mais il ", ";")


class DraftClaimStatus(str, Enum):
    """Statut initial d'un claim proposé par extraction."""

    DRAFT = "DRAFT"


@dataclass(frozen=True)
class CanonicalProposition:
    """Proposition canonique atomique conservant la sémantique du span."""

    text: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "text", _ensure_text(self.text, "canonical_text"))


@dataclass(frozen=True)
class ClaimScope:
    """Portée métier explicite du brouillon de claim."""

    universe: str
    horizon: str
    metric: str
    frequency: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ClaimScope":
        parsed_payload = _ensure_mapping(payload, "scope")
        _ensure_allowed_fields(parsed_payload, _ALLOWED_SCOPE_FIELDS, "scope")
        return cls(
            universe=_required_text(parsed_payload, "universe"),
            horizon=_required_text(parsed_payload, "horizon"),
            metric=_required_text(parsed_payload, "metric"),
            frequency=_required_text(parsed_payload, "frequency"),
        )

    def to_payload(self) -> dict[str, str]:
        return {
            "universe": self.universe,
            "horizon": self.horizon,
            "metric": self.metric,
            "frequency": self.frequency,
        }


@dataclass(frozen=True)
class ClaimCondition:
    """Condition nécessaire à la validité d'une proposition."""

    text: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "text", _ensure_text(self.text, "condition"))


@dataclass(frozen=True)
class Limitation:
    """Limite explicite issue de la preuve ou du contexte immédiat."""

    text: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "text", _ensure_text(self.text, "limitation"))


@dataclass(frozen=True)
class EvidenceSpan:
    """Span documentaire cité par un brouillon de claim."""

    quoted_text: str
    start_char: int
    end_char: int
    source_locator: SourceLocator
    quoted_span_hash: str

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
        *,
        evidence_candidate: Any,
    ) -> "EvidenceSpan":
        parsed_payload = _ensure_mapping(payload, "evidence_span")
        _ensure_allowed_fields(parsed_payload, _ALLOWED_EVIDENCE_SPAN_FIELDS, "evidence_span")
        candidate = _ensure_evidence_candidate(evidence_candidate)
        quoted_text = _required_text(parsed_payload, "quoted_text")
        if quoted_text not in candidate["text"]:
            raise ValueError("quoted_text absent du texte source")

        start_char = _required_non_negative_integer(parsed_payload, "start_char")
        end_char = _required_positive_integer(parsed_payload, "end_char")
        if start_char >= end_char or end_char > len(candidate["text"]):
            raise ValueError("evidence_span invalide")

        return cls(
            quoted_text=quoted_text,
            start_char=start_char,
            end_char=end_char,
            source_locator=candidate["source_locator"],
            quoted_span_hash=_sha256_text(quoted_text),
        )

    def __post_init__(self) -> None:
        object.__setattr__(self, "quoted_text", _ensure_text(self.quoted_text, "quoted_text"))
        object.__setattr__(
            self,
            "start_char",
            _ensure_non_negative_integer(self.start_char, "start_char"),
        )
        object.__setattr__(self, "end_char", _ensure_positive_integer(self.end_char, "end_char"))
        if self.start_char >= self.end_char:
            raise ValueError("evidence_span invalide")
        if not isinstance(self.source_locator, SourceLocator):
            raise ValueError("source_locator invalide")
        object.__setattr__(
            self,
            "quoted_span_hash",
            _ensure_sha256(self.quoted_span_hash, "quoted_span_hash"),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "quoted_span_hash": self.quoted_span_hash,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "source_locator": self.source_locator.to_payload(),
        }


@dataclass(frozen=True)
class ClaimExtractionProposal:
    """Sortie structurée d'un extracteur avant décision de domaine."""

    claim_type: str
    canonical_proposition: CanonicalProposition
    source_text: str
    scope: ClaimScope
    conditions: tuple[ClaimCondition, ...]
    limitations: tuple[Limitation, ...]
    evidence_span: EvidenceSpan
    evidence_chunk_id: str
    extractor_version: str

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
        *,
        evidence_candidate: Any,
        extractor_version: str,
    ) -> "ClaimExtractionProposal":
        parsed_payload = _ensure_mapping(payload, "claim_proposal")
        _ensure_allowed_fields(parsed_payload, _ALLOWED_PROPOSAL_FIELDS, "claim_proposal")
        candidate = _ensure_evidence_candidate(evidence_candidate)
        source_text = _required_text(parsed_payload, "source_text")
        if source_text not in candidate["text"]:
            raise ValueError("source_text absent du texte source")

        return cls(
            claim_type=_required_text(parsed_payload, "claim_type"),
            canonical_proposition=CanonicalProposition(_required_text(parsed_payload, "canonical_text")),
            source_text=source_text,
            scope=ClaimScope.from_payload(_required_value(parsed_payload, "scope")),
            conditions=_conditions_from_payload(_required_value(parsed_payload, "conditions")),
            limitations=_limitations_from_payload(_required_value(parsed_payload, "limitations")),
            evidence_span=EvidenceSpan.from_payload(
                _required_value(parsed_payload, "evidence_span"),
                evidence_candidate=evidence_candidate,
            ),
            evidence_chunk_id=candidate["chunk_id"],
            extractor_version=_ensure_text(extractor_version, "extractor_version"),
        )

    def __post_init__(self) -> None:
        object.__setattr__(self, "claim_type", _ensure_text(self.claim_type, "claim_type"))
        if not isinstance(self.canonical_proposition, CanonicalProposition):
            raise ValueError("canonical_proposition invalide")
        object.__setattr__(self, "source_text", _ensure_text(self.source_text, "source_text"))
        if not isinstance(self.scope, ClaimScope):
            raise ValueError("scope invalide")
        object.__setattr__(
            self,
            "conditions",
            _ensure_condition_tuple(self.conditions),
        )
        object.__setattr__(
            self,
            "limitations",
            _ensure_limitation_tuple(self.limitations),
        )
        if not isinstance(self.evidence_span, EvidenceSpan):
            raise ValueError("evidence_span invalide")
        object.__setattr__(self, "evidence_chunk_id", _ensure_chunk_id(self.evidence_chunk_id))
        object.__setattr__(
            self,
            "extractor_version",
            _ensure_text(self.extractor_version, "extractor_version"),
        )


class ClaimAtomicityPolicy:
    """Politique refusant les propositions composites."""

    def ensure_atomic(self, proposal: ClaimExtractionProposal) -> ClaimExtractionProposal:
        parsed_proposal = _ensure_proposal(proposal)
        normalized_text = _normalized_text(parsed_proposal.canonical_proposition.text)
        if any(marker in normalized_text for marker in _COMPOSITE_MARKERS):
            raise ValueError("claim non atomique")
        return parsed_proposal


class ClaimCanonicalizationPolicy:
    """Politique de conservation de négation, modalité et conditions."""

    def ensure_preserves_source_semantics(
        self,
        proposal: ClaimExtractionProposal,
    ) -> ClaimExtractionProposal:
        parsed_proposal = _ensure_proposal(proposal)
        source_text = _normalized_text(parsed_proposal.source_text)
        canonical_text = _normalized_text(parsed_proposal.canonical_proposition.text)

        if _contains_any(source_text, _MODALITY_MARKERS) and not _contains_any(
            canonical_text,
            _MODALITY_MARKERS,
        ):
            raise ValueError("modalite perdue")

        if _contains_any(source_text, _NEGATION_MARKERS) and not _contains_any(
            canonical_text,
            _NEGATION_MARKERS,
        ):
            raise ValueError("negation perdue")

        for condition in parsed_proposal.conditions:
            if not _contains_condition_terms(canonical_text, condition.text):
                raise ValueError("condition perdue")

        return parsed_proposal


@dataclass(frozen=True)
class DraftClaim:
    """Brouillon de claim créé par EG sans vérification automatique."""

    claim_id: str
    claim_version: int
    status: DraftClaimStatus
    claim_type: str
    canonical_proposition: CanonicalProposition
    scope: ClaimScope
    conditions: tuple[ClaimCondition, ...]
    limitations: tuple[Limitation, ...]
    evidence_span: EvidenceSpan
    evidence_chunk_id: str
    extractor_version: str

    @classmethod
    def from_proposal(
        cls,
        *,
        claim_id: str,
        proposal: ClaimExtractionProposal,
    ) -> "DraftClaim":
        parsed_proposal = _ensure_proposal(proposal)
        return cls(
            claim_id=claim_id,
            claim_version=1,
            status=DraftClaimStatus.DRAFT,
            claim_type=parsed_proposal.claim_type,
            canonical_proposition=parsed_proposal.canonical_proposition,
            scope=parsed_proposal.scope,
            conditions=parsed_proposal.conditions,
            limitations=parsed_proposal.limitations,
            evidence_span=parsed_proposal.evidence_span,
            evidence_chunk_id=parsed_proposal.evidence_chunk_id,
            extractor_version=parsed_proposal.extractor_version,
        )

    def __post_init__(self) -> None:
        object.__setattr__(self, "claim_id", _ensure_claim_id(self.claim_id))
        object.__setattr__(
            self,
            "claim_version",
            _ensure_positive_integer(self.claim_version, "claim_version"),
        )
        if not isinstance(self.status, DraftClaimStatus):
            raise ValueError("status claim invalide")
        object.__setattr__(self, "claim_type", _ensure_text(self.claim_type, "claim_type"))
        if not isinstance(self.canonical_proposition, CanonicalProposition):
            raise ValueError("canonical_proposition invalide")
        if not isinstance(self.scope, ClaimScope):
            raise ValueError("scope invalide")
        object.__setattr__(self, "conditions", _ensure_condition_tuple(self.conditions))
        object.__setattr__(self, "limitations", _ensure_limitation_tuple(self.limitations))
        if not isinstance(self.evidence_span, EvidenceSpan):
            raise ValueError("evidence_span invalide")
        object.__setattr__(self, "evidence_chunk_id", _ensure_chunk_id(self.evidence_chunk_id))
        object.__setattr__(
            self,
            "extractor_version",
            _ensure_text(self.extractor_version, "extractor_version"),
        )

    @property
    def proposition_hash(self) -> str:
        return _sha256_text(self.canonical_proposition.text)

    def to_event(self, *, occurred_at: str) -> "ClaimDrafted":
        return ClaimDrafted.from_draft(draft_claim=self, occurred_at=occurred_at)

    def to_payload(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "claim_version": self.claim_version,
            "status": self.status.value,
            "claim_type": self.claim_type,
            "canonical_proposition": {
                "text": self.canonical_proposition.text,
                "hash": self.proposition_hash,
            },
            "scope": self.scope.to_payload(),
            "conditions": tuple(condition.text for condition in self.conditions),
            "limitations": tuple(limitation.text for limitation in self.limitations),
            "evidence_span": self.evidence_span.to_payload(),
            "evidence_chunk_id": self.evidence_chunk_id,
            "extractor_version": self.extractor_version,
        }


@dataclass(frozen=True)
class ClaimDrafted:
    """Événement de domaine EG publié quand un brouillon est créé."""

    claim_id: str
    claim_version: int
    proposition_hash: str
    source_locator: SourceLocator
    extractor_version: str
    occurred_at: str

    @classmethod
    def from_draft(cls, *, draft_claim: DraftClaim, occurred_at: str) -> "ClaimDrafted":
        parsed_draft = _ensure_draft_claim(draft_claim)
        return cls(
            claim_id=parsed_draft.claim_id,
            claim_version=parsed_draft.claim_version,
            proposition_hash=parsed_draft.proposition_hash,
            source_locator=parsed_draft.evidence_span.source_locator,
            extractor_version=parsed_draft.extractor_version,
            occurred_at=_ensure_utc_instant(occurred_at, "occurred_at"),
        )

    @property
    def event_type(self) -> str:
        return "ClaimDrafted"

    def __post_init__(self) -> None:
        object.__setattr__(self, "claim_id", _ensure_claim_id(self.claim_id))
        object.__setattr__(
            self,
            "claim_version",
            _ensure_positive_integer(self.claim_version, "claim_version"),
        )
        object.__setattr__(
            self,
            "proposition_hash",
            _ensure_sha256(self.proposition_hash, "proposition_hash"),
        )
        if not isinstance(self.source_locator, SourceLocator):
            raise ValueError("source_locator invalide")
        object.__setattr__(
            self,
            "extractor_version",
            _ensure_text(self.extractor_version, "extractor_version"),
        )
        object.__setattr__(
            self,
            "occurred_at",
            _ensure_utc_instant(self.occurred_at, "occurred_at"),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "occurred_at": self.occurred_at,
            "payload": {
                "claim_id": self.claim_id,
                "claim_version": self.claim_version,
                "proposition_hash": self.proposition_hash,
                "source_locator": self.source_locator.to_payload(),
                "extractor_version": self.extractor_version,
            },
        }


def claim_id_for(*, idempotency_key: str, proposal: ClaimExtractionProposal) -> str:
    parsed_proposal = _ensure_proposal(proposal)
    seed = "|".join(
        (
            _ensure_text(idempotency_key, "idempotency_key"),
            parsed_proposal.evidence_chunk_id,
            parsed_proposal.canonical_proposition.text,
            parsed_proposal.evidence_span.quoted_span_hash,
        )
    )
    return f"CLM-{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:24].upper()}"


def _ensure_proposal(value: ClaimExtractionProposal) -> ClaimExtractionProposal:
    if not isinstance(value, ClaimExtractionProposal):
        raise ValueError("claim_proposal invalide")
    return value


def _ensure_draft_claim(value: DraftClaim) -> DraftClaim:
    if not isinstance(value, DraftClaim):
        raise ValueError("draft_claim invalide")
    return value


def _ensure_evidence_candidate(value: Any) -> Mapping[str, Any]:
    if value is None:
        raise ValueError("evidence_candidate absent")

    chunk_id = _ensure_chunk_id(getattr(value, "chunk_id", None))
    text = _ensure_text(getattr(value, "text", None), "text")
    source_locator = getattr(value, "source_locator", None)
    if not isinstance(source_locator, SourceLocator):
        raise ValueError("source_locator invalide")
    content_hash = _ensure_sha256(getattr(value, "content_hash", None), "content_hash")
    if source_locator.content_hash != content_hash:
        raise ValueError("content_hash incoherent avec SourceLocator")

    return MappingProxyType(
        {
            "chunk_id": chunk_id,
            "text": text,
            "source_locator": source_locator,
            "content_hash": content_hash,
        }
    )


def _conditions_from_payload(value: Any) -> tuple[ClaimCondition, ...]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("conditions invalides")
    return tuple(ClaimCondition(item) for item in value)


def _limitations_from_payload(value: Any) -> tuple[Limitation, ...]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("limitations invalides")
    return tuple(Limitation(item) for item in value)


def _ensure_condition_tuple(value: Sequence[ClaimCondition]) -> tuple[ClaimCondition, ...]:
    if value is None:
        raise ValueError("conditions absentes")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("conditions invalides")
    parsed = tuple(value)
    for condition in parsed:
        if not isinstance(condition, ClaimCondition):
            raise ValueError("condition invalide")
    return parsed


def _ensure_limitation_tuple(value: Sequence[Limitation]) -> tuple[Limitation, ...]:
    if value is None:
        raise ValueError("limitations absentes")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("limitations invalides")
    parsed = tuple(value)
    for limitation in parsed:
        if not isinstance(limitation, Limitation):
            raise ValueError("limitation invalide")
    return parsed


def _required_value(payload: Mapping[str, Any], field_name: str) -> Any:
    if field_name not in payload:
        raise ValueError(f"{field_name} absent")
    return payload[field_name]


def _required_text(payload: Mapping[str, Any], field_name: str) -> str:
    return _ensure_text(_required_value(payload, field_name), field_name)


def _required_positive_integer(payload: Mapping[str, Any], field_name: str) -> int:
    return _ensure_positive_integer(_required_value(payload, field_name), field_name)


def _required_non_negative_integer(payload: Mapping[str, Any], field_name: str) -> int:
    return _ensure_non_negative_integer(_required_value(payload, field_name), field_name)


def _ensure_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")
    return value


def _ensure_allowed_fields(payload: Mapping[str, Any], allowed_fields: frozenset[str], label: str) -> None:
    for field_name in payload:
        if field_name not in allowed_fields:
            raise ValueError(f"{label} champ interdit: {field_name}")


def _ensure_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


def _ensure_claim_id(value: Any) -> str:
    text = _ensure_text(value, "claim_id")
    if _CLAIM_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("claim_id invalide")
    return text


def _ensure_chunk_id(value: Any) -> str:
    text = _ensure_text(value, "chunk_id")
    if not text.startswith("KCHK-"):
        raise ValueError("chunk_id invalide")
    return text


def _ensure_sha256(value: Any, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if len(text) != 64:
        raise ValueError(f"{field_name} invalide")
    for character in text:
        if character not in _HASH_HEX_ALPHABET:
            raise ValueError(f"{field_name} invalide")
    return text


def _ensure_positive_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_non_negative_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_utc_instant(value: Any, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", text) is None:
        raise ValueError(f"{field_name} invalide")
    return text


def _sha256_text(value: str) -> str:
    return hashlib.sha256(_ensure_text(value, "text").encode("utf-8")).hexdigest()


def _normalized_text(value: str) -> str:
    return f" {_ensure_text(value, 'text').lower()} "


def _contains_any(value: str, markers: tuple[str, ...]) -> bool:
    return any(marker in value for marker in markers)


def _contains_condition_terms(canonical_text: str, condition_text: str) -> bool:
    terms = tuple(
        term
        for term in re.split(r"[^a-z0-9àâçéèêëîïôûùüÿñæœ]+", condition_text.lower())
        if len(term) > 2
    )
    if len(terms) == 0:
        raise ValueError("condition vide")
    return all(term in canonical_text for term in terms)


__all__ = [
    "CanonicalProposition",
    "ClaimAtomicityPolicy",
    "ClaimCanonicalizationPolicy",
    "ClaimCondition",
    "ClaimDrafted",
    "ClaimExtractionProposal",
    "ClaimScope",
    "DraftClaim",
    "DraftClaimStatus",
    "EvidenceSpan",
    "Limitation",
    "claim_id_for",
]
