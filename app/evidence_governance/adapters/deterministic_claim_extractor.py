"""Double déterministe du port ClaimExtractor."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.evidence_governance.domain.claim_extraction import ClaimExtractionProposal


class DeterministicClaimExtractor:
    """Extracteur strict basé sur des propositions préconfigurées par chunk."""

    def __init__(
        self,
        *,
        extractor_version: str,
        proposals_by_chunk_id: Mapping[str, Sequence[Mapping[str, object]]],
    ) -> None:
        self.extractor_version = _ensure_text(extractor_version, "extractor_version")
        self._proposals_by_chunk_id = _ensure_proposals_mapping(proposals_by_chunk_id)

    def extract_claims(
        self,
        *,
        evidence_candidates: Sequence[object],
        extraction_schema_version: str,
        requested_by_context: str,
    ) -> tuple[ClaimExtractionProposal, ...]:
        _ensure_text(extraction_schema_version, "extraction_schema_version")
        if _ensure_text(requested_by_context, "requested_by_context") != "EG":
            raise ValueError("requested_by_context inconnu")
        candidates = _ensure_candidates(evidence_candidates)
        proposals: list[ClaimExtractionProposal] = []
        for candidate in candidates:
            chunk_id = _ensure_chunk_id(getattr(candidate, "chunk_id", None))
            payloads = self._proposals_by_chunk_id.get(chunk_id)
            if payloads is None:
                raise ValueError(f"propositions absentes: {chunk_id}")
            for payload in payloads:
                proposals.append(
                    ClaimExtractionProposal.from_payload(
                        payload,
                        evidence_candidate=candidate,
                        extractor_version=self.extractor_version,
                    )
                )
        return tuple(proposals)


def _ensure_proposals_mapping(
    value: Mapping[str, Sequence[Mapping[str, object]]],
) -> dict[str, tuple[Mapping[str, object], ...]]:
    if not isinstance(value, Mapping):
        raise ValueError("proposals_by_chunk_id non objet")
    parsed: dict[str, tuple[Mapping[str, object], ...]] = {}
    for chunk_id, payloads in value.items():
        parsed_chunk_id = _ensure_chunk_id(chunk_id)
        if isinstance(payloads, str) or not isinstance(payloads, Sequence):
            raise ValueError("propositions invalides")
        parsed_payloads = tuple(payloads)
        if len(parsed_payloads) == 0:
            raise ValueError("propositions absentes")
        for payload in parsed_payloads:
            if not isinstance(payload, Mapping):
                raise ValueError("proposition non objet")
        parsed[parsed_chunk_id] = parsed_payloads
    if len(parsed) == 0:
        raise ValueError("proposals_by_chunk_id vide")
    return parsed


def _ensure_candidates(value: Sequence[object]) -> tuple[object, ...]:
    if value is None:
        raise ValueError("evidence_candidates absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("evidence_candidates invalides")
    candidates = tuple(value)
    if len(candidates) == 0:
        raise ValueError("evidence_candidates absents")
    for candidate in candidates:
        _ensure_chunk_id(getattr(candidate, "chunk_id", None))
    return candidates


def _ensure_chunk_id(value: object) -> str:
    text = _ensure_text(value, "chunk_id")
    if not text.startswith("KCHK-"):
        raise ValueError("chunk_id invalide")
    return text


def _ensure_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


__all__ = ["DeterministicClaimExtractor"]
