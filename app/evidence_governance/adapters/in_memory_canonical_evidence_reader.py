"""Lecteur memoire de spans canoniques pour EG."""

from __future__ import annotations

from collections.abc import Sequence

from app.contracts.source_references import SourceLocator
from app.evidence_governance.domain.claim_evidence import CanonicalEvidenceSpan


class InMemoryCanonicalEvidenceReader:
    """Double strict du port CanonicalEvidenceReader."""

    def __init__(self, *, spans: Sequence[CanonicalEvidenceSpan]) -> None:
        self._spans_by_locator_key: dict[tuple[object, ...], CanonicalEvidenceSpan] = {}
        for span in _ensure_spans(spans):
            locator_key = _locator_key(span.source_locator)
            if locator_key in self._spans_by_locator_key:
                raise ValueError("source_locator duplique")
            self._spans_by_locator_key[locator_key] = span

    def resolve(self, source_locator: SourceLocator) -> CanonicalEvidenceSpan:
        if not isinstance(source_locator, SourceLocator):
            raise ValueError("source_locator invalide")
        span = self._spans_by_locator_key.get(_locator_key(source_locator))
        if span is None:
            raise ValueError("source_locator non resolvable")
        return span


def _ensure_spans(value: Sequence[CanonicalEvidenceSpan]) -> tuple[CanonicalEvidenceSpan, ...]:
    if value is None:
        raise ValueError("spans absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("spans invalides")
    spans = tuple(value)
    for span in spans:
        if not isinstance(span, CanonicalEvidenceSpan):
            raise ValueError("span canonique invalide")
    return spans


def _locator_key(source_locator: SourceLocator) -> tuple[object, ...]:
    return (
        source_locator.canonical_version_id,
        source_locator.document_id,
        source_locator.page_pdf,
        source_locator.item_id,
        source_locator.bbox,
        source_locator.content_hash,
    )


__all__ = ["InMemoryCanonicalEvidenceReader"]
