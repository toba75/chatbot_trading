"""Sorties pagewise M-004 et fusion locale vers document structuré."""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.contracts.identity import DomainIdentifier
from app.source_processing.domain.document_processing_run import (
    PageDecision,
    PageManifest,
    PageNumber,
    RoutePlan,
    PageRouteName,
)
from app.source_processing.domain.source_document import (
    DocumentId,
    OriginalStorageRef,
    SourceDocument,
    SourceDocumentStatus,
    SourceFingerprint,
)


_SOURCE_LOCATOR_SCHEMA_VERSION = "1.0"
_PAGE_AUTHORITY_MISSING = "PAGE_AUTHORITY_MISSING"
_PAGE_AUTHORITY_AMBIGUOUS = "PAGE_AUTHORITY_AMBIGUOUS"
_ARTIFACT_REF_PATTERN = re.compile(
    r"^artifact:source_processing\.[a-z0-9_]+/[A-Za-z0-9_.@/-]+$"
)


class ConversionToolName(str, Enum):
    """Outil documentaire réellement exécuté pour une page."""

    DOCLING_STANDARD = "DOCLING_STANDARD"
    GRANITE_DOCLING = "GRANITE_DOCLING"
    OCRMYPDF = "OCRMYPDF"

    @classmethod
    def from_value(cls, value: "ConversionToolName | str") -> "ConversionToolName":
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise ValueError("outil de conversion inconnu")
        for tool_name in cls:
            if tool_name.value == value:
                return tool_name
        raise ValueError("outil de conversion inconnu")


class PageConversionItemLabel(str, Enum):
    """Label minimal conservé dans le document structuré local."""

    TEXT = "TEXT"
    TABLE = "TABLE"
    FIGURE = "FIGURE"

    @classmethod
    def from_value(
        cls,
        value: "PageConversionItemLabel | str",
    ) -> "PageConversionItemLabel":
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise ValueError("label d'item inconnu")
        for label in cls:
            if label.value == value:
                return label
        raise ValueError("label d'item inconnu")


class QualityDecisionStatus(str, Enum):
    """Statut métier publié par les contrôles qualité M-004."""

    PASS = "PASS"
    PASS_WITH_WARNINGS = "PASS_WITH_WARNINGS"
    RETRY_WITH_ALTERNATIVE_ROUTE = "RETRY_WITH_ALTERNATIVE_ROUTE"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    QUARANTINE = "QUARANTINE"

    @classmethod
    def from_value(
        cls,
        value: "QualityDecisionStatus | str",
    ) -> "QualityDecisionStatus":
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise ValueError("statut QA inconnu")
        for status in cls:
            if status.value == value:
                return status
        raise ValueError("statut QA inconnu")


class QualityFindingCode(str, Enum):
    """Anomalie documentaire conservée sans contenu complet."""

    PAGE_OMITTED = "PAGE_OMITTED"
    PAGE_UNEXPECTED = "PAGE_UNEXPECTED"
    SOURCE_LOCATOR_INCONSISTENT = "SOURCE_LOCATOR_INCONSISTENT"
    NUMERIC_INCONSISTENCY = "NUMERIC_INCONSISTENCY"
    NEGATIVE_SIGN_ALTERED = "NEGATIVE_SIGN_ALTERED"
    PERCENTAGE_ALTERED = "PERCENTAGE_ALTERED"
    DECIMAL_SEPARATOR_ALTERED = "DECIMAL_SEPARATOR_ALTERED"
    INCOMPLETE_TABLE = "INCOMPLETE_TABLE"
    FIGURE_PROVENANCE_MISSING = "FIGURE_PROVENANCE_MISSING"
    SOURCE_QUARANTINED = "SOURCE_QUARANTINED"
    WARNING_REVIEW_NOTE = "WARNING_REVIEW_NOTE"

    @classmethod
    def from_value(cls, value: "QualityFindingCode | str") -> "QualityFindingCode":
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise ValueError("code d'anomalie QA inconnu")
        for code in cls:
            if code.value == value:
                return code
        raise ValueError("code d'anomalie QA inconnu")


@dataclass(frozen=True)
class PageItemGeometry:
    """Coordonnées d'item dans le repère de page retourné par l'outil."""

    left: float
    top: float
    right: float
    bottom: float
    page_width: float
    page_height: float

    def __post_init__(self) -> None:
        left = _ensure_finite_number(self.left, "coordonnées de page invalides")
        top = _ensure_finite_number(self.top, "coordonnées de page invalides")
        right = _ensure_finite_number(self.right, "coordonnées de page invalides")
        bottom = _ensure_finite_number(self.bottom, "coordonnées de page invalides")
        page_width = _ensure_positive_finite_number(
            self.page_width,
            "coordonnées de page invalides",
        )
        page_height = _ensure_positive_finite_number(
            self.page_height,
            "coordonnées de page invalides",
        )
        if left < 0 or top < 0 or right > page_width or bottom > page_height:
            raise ValueError("coordonnées de page invalides")
        if left >= right or top >= bottom:
            raise ValueError("coordonnées de page invalides")
        object.__setattr__(self, "left", left)
        object.__setattr__(self, "top", top)
        object.__setattr__(self, "right", right)
        object.__setattr__(self, "bottom", bottom)
        object.__setattr__(self, "page_width", page_width)
        object.__setattr__(self, "page_height", page_height)

    def normalized_bbox(self) -> tuple[float, float, float, float]:
        """Retourne les coordonnées normalisées attendues par SourceLocator."""

        return (
            self.left / self.page_width,
            self.top / self.page_height,
            self.right / self.page_width,
            self.bottom / self.page_height,
        )


@dataclass(frozen=True)
class PageConversionItem:
    """Item documentaire produit par une conversion de page."""

    label: PageConversionItemLabel
    text: str
    geometry: PageItemGeometry
    content_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "label", PageConversionItemLabel.from_value(self.label))
        text = _ensure_text(self.text, "texte d'item invalide")
        object.__setattr__(self, "text", text)
        _ensure_page_item_geometry(self.geometry)
        content_hash = _ensure_content_hash(self.content_hash)
        if content_hash != _content_hash_for_text(text):
            raise ValueError("content_hash incohérent avec le texte")
        object.__setattr__(self, "content_hash", content_hash)


@dataclass(frozen=True)
class PageConversionArtifact:
    """Sortie auditable d'une page convertie par sa route explicite."""

    page_number: PageNumber
    route_name: PageRouteName
    tool_name: ConversionToolName
    tool_version: str
    artifact_hash: str
    audit_artifact_ref: str
    items: tuple[PageConversionItem, ...]

    def __post_init__(self) -> None:
        _ensure_page_number(self.page_number)
        object.__setattr__(self, "route_name", PageRouteName.from_value(self.route_name))
        object.__setattr__(self, "tool_name", ConversionToolName.from_value(self.tool_name))
        object.__setattr__(
            self,
            "tool_version",
            _ensure_text(self.tool_version, "version d'outil invalide"),
        )
        object.__setattr__(
            self,
            "artifact_hash",
            _ensure_artifact_hash(self.artifact_hash),
        )
        object.__setattr__(
            self,
            "audit_artifact_ref",
            _ensure_artifact_ref(self.audit_artifact_ref),
        )
        object.__setattr__(self, "items", _ensure_conversion_items(self.items))


class TextAuthoritySelectionError(ValueError):
    """Erreur métier stable pour l'adjudication d'autorité textuelle."""

    def __init__(self, code: str, message: str) -> None:
        self.code = _ensure_text_authority_error_code(code)
        super().__init__(f"{self.code}: {message}")


@dataclass(frozen=True)
class PageConversionCandidate:
    """Sortie de conversion candidate pour l'autorité textuelle d'une page."""

    candidate_id: str
    page_output: PageConversionArtifact

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "candidate_id",
            _ensure_authority_text(self.candidate_id, "candidate_id d'autorité invalide"),
        )
        if not isinstance(self.page_output, PageConversionArtifact):
            raise TextAuthoritySelectionError(
                _PAGE_AUTHORITY_MISSING,
                "sortie candidate d'autorité invalide",
            )

    @property
    def page_number(self) -> PageNumber:
        return self.page_output.page_number

    def to_payload(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "page_pdf": self.page_number.value,
            "route_name": self.page_output.route_name.value,
            "tool_name": self.page_output.tool_name.value,
            "tool_version": self.page_output.tool_version,
            "artifact_hash": self.page_output.artifact_hash,
            "audit_artifact_ref": self.page_output.audit_artifact_ref,
            "content_hashes": tuple(item.content_hash for item in self.page_output.items),
        }


@dataclass(frozen=True)
class TextAuthority:
    """Autorité textuelle retenue pour une page canonique."""

    page_number: PageNumber
    candidate_id: str
    tool_name: ConversionToolName
    tool_version: str
    artifact_hash: str
    audit_artifact_ref: str
    policy_version: str
    justification: str

    def __post_init__(self) -> None:
        _ensure_page_number(self.page_number)
        object.__setattr__(
            self,
            "candidate_id",
            _ensure_authority_text(self.candidate_id, "autorité textuelle vide"),
        )
        object.__setattr__(self, "tool_name", ConversionToolName.from_value(self.tool_name))
        object.__setattr__(
            self,
            "tool_version",
            _ensure_authority_text(self.tool_version, "outil source d'autorité absent"),
        )
        object.__setattr__(self, "artifact_hash", _ensure_artifact_hash(self.artifact_hash))
        object.__setattr__(self, "audit_artifact_ref", _ensure_artifact_ref(self.audit_artifact_ref))
        object.__setattr__(
            self,
            "policy_version",
            _ensure_authority_text(
                self.policy_version,
                "version de politique d'autorité obligatoire",
            ),
        )
        object.__setattr__(
            self,
            "justification",
            _ensure_authority_text(
                self.justification,
                "justification d'autorité obligatoire",
            ),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "page_pdf": self.page_number.value,
            "candidate_id": self.candidate_id,
            "tool_name": self.tool_name.value,
            "tool_version": self.tool_version,
            "artifact_hash": self.artifact_hash,
            "audit_artifact_ref": self.audit_artifact_ref,
            "policy_version": self.policy_version,
            "justification": self.justification,
        }


@dataclass(frozen=True)
class TextAuthorityPageDecision:
    """Décision d'autorité textuelle et candidats conservés pour audit."""

    page_number: PageNumber
    authority: TextAuthority
    candidates: tuple[PageConversionCandidate, ...]

    def __post_init__(self) -> None:
        parsed_page_number = _ensure_page_number(self.page_number)
        if not isinstance(self.authority, TextAuthority):
            raise TextAuthoritySelectionError(
                _PAGE_AUTHORITY_MISSING,
                "autorité textuelle absente",
            )
        if self.authority.page_number != parsed_page_number:
            raise TextAuthoritySelectionError(
                _PAGE_AUTHORITY_MISSING,
                "autorité textuelle hors page",
            )
        candidates = _ensure_authority_candidates(
            self.candidates,
            page_number=parsed_page_number,
        )
        selected_candidates = tuple(
            candidate
            for candidate in candidates
            if candidate.candidate_id == self.authority.candidate_id
        )
        if len(selected_candidates) == 0:
            raise TextAuthoritySelectionError(
                _PAGE_AUTHORITY_MISSING,
                "autorité textuelle absente des candidats",
            )
        if len(selected_candidates) > 1:
            raise TextAuthoritySelectionError(
                _PAGE_AUTHORITY_AMBIGUOUS,
                "autorité textuelle dupliquée",
            )
        selected_output = selected_candidates[0].page_output
        if selected_output.tool_name is not self.authority.tool_name:
            raise TextAuthoritySelectionError(
                _PAGE_AUTHORITY_MISSING,
                "outil source d'autorité incohérent",
            )
        if selected_output.tool_version != self.authority.tool_version:
            raise TextAuthoritySelectionError(
                _PAGE_AUTHORITY_MISSING,
                "version d'outil d'autorité incohérente",
            )
        if selected_output.artifact_hash != self.authority.artifact_hash:
            raise TextAuthoritySelectionError(
                _PAGE_AUTHORITY_MISSING,
                "hash d'artefact d'autorité incohérent",
            )
        if selected_output.audit_artifact_ref != self.authority.audit_artifact_ref:
            raise TextAuthoritySelectionError(
                _PAGE_AUTHORITY_MISSING,
                "artefact d'audit d'autorité incohérent",
            )
        object.__setattr__(self, "candidates", candidates)

    def selected_page_output(self) -> PageConversionArtifact:
        for candidate in self.candidates:
            if candidate.candidate_id == self.authority.candidate_id:
                return candidate.page_output
        raise TextAuthoritySelectionError(
            _PAGE_AUTHORITY_MISSING,
            "autorité textuelle absente des candidats",
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "page_pdf": self.page_number.value,
            "authority": self.authority.to_payload(),
            "candidates": tuple(candidate.to_payload() for candidate in self.candidates),
        }


@dataclass(frozen=True)
class TextAuthorityManifest:
    """Manifeste d'autorité textuelle couvrant exactement les pages publiables."""

    page_manifest: PageManifest
    page_decisions: tuple[TextAuthorityPageDecision, ...]

    def __post_init__(self) -> None:
        parsed_page_manifest = _ensure_page_manifest(self.page_manifest)
        decisions = _ensure_text_authority_page_decisions(self.page_decisions)
        _ensure_text_authority_manifest_covers_page_manifest(
            page_manifest=parsed_page_manifest,
            page_decisions=decisions,
        )
        object.__setattr__(self, "page_decisions", decisions)

    @classmethod
    def from_page_decisions(
        cls,
        *,
        page_manifest: PageManifest,
        page_decisions: Sequence[TextAuthorityPageDecision],
    ) -> "TextAuthorityManifest":
        return cls(
            page_manifest=page_manifest,
            page_decisions=tuple(page_decisions),
        )

    @property
    def entries(self) -> tuple[TextAuthorityPageDecision, ...]:
        return self.page_decisions

    def decision_for(self, page_number: PageNumber) -> TextAuthorityPageDecision:
        parsed_page_number = _ensure_page_number(page_number)
        for decision in self.page_decisions:
            if decision.page_number == parsed_page_number:
                return decision
        raise TextAuthoritySelectionError(
            _PAGE_AUTHORITY_MISSING,
            "autorité textuelle absente pour la page",
        )

    def selected_page_outputs(self) -> tuple[PageConversionArtifact, ...]:
        return tuple(decision.selected_page_output() for decision in self.page_decisions)

    def to_payload(self) -> dict[str, Any]:
        return {
            "entries": tuple(decision.to_payload() for decision in self.page_decisions),
        }


@dataclass(frozen=True)
class TextAuthoritySelectionPolicy:
    """Politique normative d'adjudication explicite d'une autorité par page."""

    policy_version: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "policy_version",
            _ensure_authority_text(
                self.policy_version,
                "version de politique d'autorité obligatoire",
            ),
        )

    def select(
        self,
        *,
        page_number: PageNumber,
        candidates: Sequence[PageConversionCandidate],
        selected_candidate_ids: Sequence[str],
        justification: str,
    ) -> TextAuthorityPageDecision:
        parsed_page_number = _ensure_page_number(page_number)
        parsed_candidates = _ensure_authority_candidates(
            candidates,
            page_number=parsed_page_number,
        )
        selected_ids = _ensure_selected_candidate_ids(selected_candidate_ids)
        if len(selected_ids) == 0:
            raise TextAuthoritySelectionError(
                _PAGE_AUTHORITY_MISSING,
                "aucune autorité textuelle sélectionnée",
            )
        if len(selected_ids) > 1:
            raise TextAuthoritySelectionError(
                _PAGE_AUTHORITY_AMBIGUOUS,
                "plusieurs autorités textuelles sélectionnées",
            )
        selected_candidate_id = selected_ids[0]
        candidates_by_id = {candidate.candidate_id: candidate for candidate in parsed_candidates}
        if selected_candidate_id not in candidates_by_id:
            raise TextAuthoritySelectionError(
                _PAGE_AUTHORITY_MISSING,
                "autorité textuelle absente des candidats",
            )
        selected_candidate = candidates_by_id[selected_candidate_id]
        selected_output = selected_candidate.page_output
        authority = TextAuthority(
            page_number=parsed_page_number,
            candidate_id=selected_candidate.candidate_id,
            tool_name=selected_output.tool_name,
            tool_version=selected_output.tool_version,
            artifact_hash=selected_output.artifact_hash,
            audit_artifact_ref=selected_output.audit_artifact_ref,
            policy_version=self.policy_version,
            justification=justification,
        )
        return TextAuthorityPageDecision(
            page_number=parsed_page_number,
            authority=authority,
            candidates=parsed_candidates,
        )


@dataclass(frozen=True)
class CriticalPageReason:
    """Raison explicite d'inclusion d'une page dans l'échantillon critique."""

    page_number: PageNumber
    reason: str

    def __post_init__(self) -> None:
        _ensure_page_number(self.page_number)
        object.__setattr__(
            self,
            "reason",
            _ensure_quality_text(self.reason, "raison de page critique obligatoire"),
        )


@dataclass(frozen=True)
class CriticalPageSelection:
    """Sélection versionnée des pages contrôlées avant conversion."""

    policy_version: str
    reasons: tuple[CriticalPageReason, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "policy_version",
            _ensure_quality_policy_version(self.policy_version),
        )
        reasons = _ensure_critical_page_reasons(self.reasons)
        object.__setattr__(self, "reasons", reasons)

    @property
    def page_numbers(self) -> tuple[PageNumber, ...]:
        pages_by_value = {reason.page_number.value: reason.page_number for reason in self.reasons}
        return tuple(pages_by_value[page_value] for page_value in sorted(pages_by_value))

    def reasons_for(self, page_number: PageNumber) -> tuple[str, ...]:
        parsed_page_number = _ensure_page_number(page_number)
        reasons = tuple(
            reason.reason
            for reason in self.reasons
            if reason.page_number == parsed_page_number
        )
        if len(reasons) == 0:
            raise ValueError("page critique absente")
        return reasons

    def to_audit_payload(self) -> dict[str, Any]:
        return {
            "policy_version": self.policy_version,
            "pages": tuple(
                {
                    "page_pdf": page_number.value,
                    "reasons": self.reasons_for(page_number),
                }
                for page_number in self.page_numbers
            ),
        }


@dataclass(frozen=True)
class CriticalPageSamplingPolicy:
    """Politique pré-conversion de sélection explicite des pages critiques."""

    policy_version: str
    low_confidence_threshold: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "policy_version",
            _ensure_quality_policy_version(self.policy_version),
        )
        object.__setattr__(
            self,
            "low_confidence_threshold",
            _ensure_quality_confidence_threshold(self.low_confidence_threshold),
        )

    def select(
        self,
        *,
        page_manifest: PageManifest,
        page_diagnostics: Sequence[PageDecision],
        route_plan: RoutePlan,
    ) -> CriticalPageSelection:
        parsed_page_manifest = _ensure_page_manifest(page_manifest)
        diagnostics = _ensure_page_diagnostics(page_diagnostics)
        parsed_route_plan = _ensure_route_plan(route_plan)
        _ensure_diagnostics_cover_manifest(
            page_manifest=parsed_page_manifest,
            page_diagnostics=diagnostics,
        )
        _ensure_route_plan_covers_manifest(
            page_manifest=parsed_page_manifest,
            route_plan=parsed_route_plan,
        )

        reasons: list[CriticalPageReason] = []
        manifest_page_numbers = tuple(entry.page_number for entry in parsed_page_manifest.entries)
        for page_number, reason in _sampling_position_reasons(manifest_page_numbers):
            reasons.append(CriticalPageReason(page_number=page_number, reason=reason))

        for diagnostic in diagnostics:
            if diagnostic.signals.has_table:
                reasons.append(CriticalPageReason(page_number=diagnostic.page_number, reason="TABLE"))
            if diagnostic.signals.has_formula:
                reasons.append(CriticalPageReason(page_number=diagnostic.page_number, reason="FORMULA"))
            if diagnostic.signals.native_text_state.value == "SUSPECT":
                reasons.append(
                    CriticalPageReason(page_number=diagnostic.page_number, reason="LOW_CONFIDENCE")
                )

        for page_route in parsed_route_plan.page_routes:
            if page_route.confidence_score < self.low_confidence_threshold:
                reasons.append(
                    CriticalPageReason(page_number=page_route.page_number, reason="LOW_CONFIDENCE")
                )
            if page_route.route_name is not parsed_route_plan.dominant_route_name:
                reasons.append(
                    CriticalPageReason(page_number=page_route.page_number, reason="MINORITY_ROUTE")
                )

        return CriticalPageSelection(
            policy_version=self.policy_version,
            reasons=_deduplicate_critical_page_reasons(reasons),
        )


@dataclass(frozen=True)
class PreConversionRouteComparison:
    """Comparaison explicite de route avant conversion."""

    page_number: PageNumber
    current_route_name: PageRouteName
    alternative_route_name: PageRouteName | None
    status: QualityDecisionStatus
    justification: str

    def __post_init__(self) -> None:
        _ensure_page_number(self.page_number)
        object.__setattr__(self, "current_route_name", PageRouteName.from_value(self.current_route_name))
        if self.alternative_route_name is not None:
            object.__setattr__(
                self,
                "alternative_route_name",
                PageRouteName.from_value(self.alternative_route_name),
            )
            if self.alternative_route_name is self.current_route_name:
                raise ValueError("route alternative incohérente")
        object.__setattr__(self, "status", QualityDecisionStatus.from_value(self.status))
        if (
            self.status is QualityDecisionStatus.RETRY_WITH_ALTERNATIVE_ROUTE
            and self.alternative_route_name is None
        ):
            raise ValueError("route alternative obligatoire")
        object.__setattr__(
            self,
            "justification",
            _ensure_quality_text(self.justification, "justification QA obligatoire"),
        )

    def to_audit_payload(self) -> dict[str, Any]:
        return {
            "page_pdf": self.page_number.value,
            "current_route_name": self.current_route_name.value,
            "alternative_route_name": (
                None if self.alternative_route_name is None else self.alternative_route_name.value
            ),
            "status": self.status.value,
            "justification": self.justification,
        }


@dataclass(frozen=True)
class PreConversionQualityReport:
    """Rapport QA obligatoire avant conversion."""

    policy_version: str
    critical_page_selection: CriticalPageSelection
    route_comparisons: tuple[PreConversionRouteComparison, ...]
    status: QualityDecisionStatus

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "policy_version",
            _ensure_quality_policy_version(self.policy_version),
        )
        if not isinstance(self.critical_page_selection, CriticalPageSelection):
            raise ValueError("sélection de pages critiques obligatoire")
        object.__setattr__(
            self,
            "route_comparisons",
            _ensure_route_comparisons(self.route_comparisons),
        )
        object.__setattr__(self, "status", QualityDecisionStatus.from_value(self.status))
        if self.status is QualityDecisionStatus.RETRY_WITH_ALTERNATIVE_ROUTE:
            if not any(
                comparison.status is QualityDecisionStatus.RETRY_WITH_ALTERNATIVE_ROUTE
                for comparison in self.route_comparisons
            ):
                raise ValueError("comparaison de route obligatoire")

    def to_audit_payload(self) -> dict[str, Any]:
        return {
            "policy_version": self.policy_version,
            "critical_page_selection": self.critical_page_selection.to_audit_payload(),
            "route_comparisons": tuple(
                comparison.to_audit_payload() for comparison in self.route_comparisons
            ),
            "status": self.status.value,
        }


@dataclass(frozen=True)
class PostConversionQualityFinding:
    """Anomalie QA post-conversion conservée pour refus ou audit."""

    code: QualityFindingCode
    page_number: PageNumber
    item_id: str
    expected: str
    actual: str
    detail: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", QualityFindingCode.from_value(self.code))
        _ensure_page_number(self.page_number)
        object.__setattr__(self, "item_id", _ensure_quality_text(self.item_id, "item_id QA obligatoire"))
        object.__setattr__(self, "expected", _ensure_quality_text(self.expected, "valeur attendue QA obligatoire"))
        object.__setattr__(self, "actual", _ensure_quality_text(self.actual, "valeur actuelle QA obligatoire"))
        object.__setattr__(self, "detail", _ensure_quality_text(self.detail, "détail QA obligatoire"))

    @property
    def blocking(self) -> bool:
        return self.code is not QualityFindingCode.WARNING_REVIEW_NOTE

    def to_audit_payload(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "page_pdf": self.page_number.value,
            "item_id": self.item_id,
        }


@dataclass(frozen=True)
class PostConversionQualityReport:
    """Rapport QA obligatoire après conversion."""

    policy_version: str
    findings: tuple[PostConversionQualityFinding, ...]
    status: QualityDecisionStatus

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "policy_version",
            _ensure_quality_policy_version(self.policy_version),
        )
        findings = _ensure_post_conversion_findings(self.findings)
        object.__setattr__(self, "findings", findings)
        object.__setattr__(self, "status", QualityDecisionStatus.from_value(self.status))
        if self.status is QualityDecisionStatus.PASS and len(findings) > 0:
            raise ValueError("rapport QA post-conversion incohérent")
        if self.status is QualityDecisionStatus.PASS_WITH_WARNINGS:
            if len(findings) == 0 or any(finding.blocking for finding in findings):
                raise ValueError("rapport QA post-conversion incohérent")
        if self.status is QualityDecisionStatus.MANUAL_REVIEW:
            if not any(finding.blocking for finding in findings):
                raise ValueError("rapport QA post-conversion incohérent")

    def to_audit_payload(self) -> dict[str, Any]:
        return {
            "policy_version": self.policy_version,
            "status": self.status.value,
            "findings": tuple(finding.to_audit_payload() for finding in self.findings),
        }


@dataclass(frozen=True)
class CanonicalQualityDecision:
    """Décision d'acceptation canonique issue des deux rapports QA."""

    policy_version: str
    status: QualityDecisionStatus
    publication_allowed: bool
    findings: tuple[PostConversionQualityFinding, ...]
    publication_events: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "policy_version",
            _ensure_quality_policy_version(self.policy_version),
        )
        object.__setattr__(self, "status", QualityDecisionStatus.from_value(self.status))
        _ensure_bool(self.publication_allowed, "publication_allowed")
        object.__setattr__(self, "findings", _ensure_post_conversion_findings(self.findings))
        object.__setattr__(self, "publication_events", _ensure_publication_events(self.publication_events))
        if self.publication_allowed and self.status not in {
            QualityDecisionStatus.PASS,
            QualityDecisionStatus.PASS_WITH_WARNINGS,
        }:
            raise ValueError("décision QA incohérente")
        if not self.publication_allowed and self.status in {
            QualityDecisionStatus.PASS,
            QualityDecisionStatus.PASS_WITH_WARNINGS,
        }:
            raise ValueError("décision QA incohérente")

    def to_audit_payload(self) -> dict[str, Any]:
        return {
            "policy_version": self.policy_version,
            "status": self.status.value,
            "publication_allowed": self.publication_allowed,
            "findings": tuple(finding.to_audit_payload() for finding in self.findings),
            "publication_event_count": len(self.publication_events),
        }


@dataclass(frozen=True)
class CanonicalAcceptancePolicy:
    """Politique qui décide si une candidate peut devenir canonique."""

    policy_version: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "policy_version",
            _ensure_quality_policy_version(self.policy_version),
        )

    def evaluate_post_conversion(
        self,
        *,
        page_manifest: PageManifest,
        text_authority_manifest: TextAuthorityManifest,
        docling_document: PagewiseDoclingDocument,
        findings: Sequence[PostConversionQualityFinding],
    ) -> PostConversionQualityReport:
        parsed_page_manifest = _ensure_page_manifest(page_manifest)
        parsed_text_authority_manifest = _ensure_text_authority_manifest(text_authority_manifest)
        if not isinstance(docling_document, PagewiseDoclingDocument):
            raise ValueError("DoclingDocument QA invalide")
        _ensure_text_authority_manifest_covers_page_manifest(
            page_manifest=parsed_page_manifest,
            page_decisions=parsed_text_authority_manifest.page_decisions,
        )
        parsed_findings = _ensure_post_conversion_findings(findings)
        generated_findings = _post_conversion_integrity_findings(
            page_manifest=parsed_page_manifest,
            text_authority_manifest=parsed_text_authority_manifest,
            docling_document=docling_document,
        )
        all_findings = generated_findings + parsed_findings
        return PostConversionQualityReport(
            policy_version=self.policy_version,
            findings=all_findings,
            status=_post_conversion_status_for(all_findings),
        )

    def decide(
        self,
        *,
        source_document: SourceDocument,
        page_manifest: PageManifest,
        text_authority_manifest: TextAuthorityManifest,
        pre_conversion_report: PreConversionQualityReport | None,
        post_conversion_report: PostConversionQualityReport | None,
    ) -> CanonicalQualityDecision:
        parsed_source_document = _ensure_source_document(source_document)
        parsed_page_manifest = _ensure_page_manifest(page_manifest)
        parsed_text_authority_manifest = _ensure_text_authority_manifest(text_authority_manifest)
        parsed_pre_report = _ensure_pre_conversion_report(pre_conversion_report)
        parsed_post_report = _ensure_post_conversion_report(post_conversion_report)
        _ensure_report_policy_matches(
            policy_version=self.policy_version,
            report_policy_version=parsed_pre_report.policy_version,
            message="rapport QA pré-conversion incohérent",
        )
        _ensure_report_policy_matches(
            policy_version=self.policy_version,
            report_policy_version=parsed_post_report.policy_version,
            message="rapport QA post-conversion incohérent",
        )
        _ensure_text_authority_manifest_covers_page_manifest(
            page_manifest=parsed_page_manifest,
            page_decisions=parsed_text_authority_manifest.page_decisions,
        )

        findings = parsed_post_report.findings
        if parsed_source_document.status is SourceDocumentStatus.QUARANTINED:
            findings = findings + (
                PostConversionQualityFinding(
                    code=QualityFindingCode.SOURCE_QUARANTINED,
                    page_number=parsed_page_manifest.entries[0].page_number,
                    item_id="SOURCE",
                    expected="REGISTERED",
                    actual="QUARANTINED",
                    detail="Source documentaire en quarantaine.",
                ),
            )
            return CanonicalQualityDecision(
                policy_version=self.policy_version,
                status=QualityDecisionStatus.QUARANTINE,
                publication_allowed=False,
                findings=findings,
                publication_events=(),
            )

        status = _canonical_decision_status(
            pre_conversion_status=parsed_pre_report.status,
            post_conversion_status=parsed_post_report.status,
        )
        publication_allowed = status in {
            QualityDecisionStatus.PASS,
            QualityDecisionStatus.PASS_WITH_WARNINGS,
        }
        return CanonicalQualityDecision(
            policy_version=self.policy_version,
            status=status,
            publication_allowed=publication_allowed,
            findings=findings,
            publication_events=(),
        )


@dataclass(frozen=True)
class PreprocessedPageArtifact:
    """Artefact OCRmyPDF conditionnel produit avant Granite-Docling."""

    page_number: PageNumber
    route_name: PageRouteName
    tool_name: ConversionToolName
    tool_version: str
    artifact_hash: str
    artifact_ref: str

    def __post_init__(self) -> None:
        _ensure_page_number(self.page_number)
        object.__setattr__(self, "route_name", PageRouteName.from_value(self.route_name))
        object.__setattr__(self, "tool_name", ConversionToolName.from_value(self.tool_name))
        object.__setattr__(
            self,
            "tool_version",
            _ensure_text(self.tool_version, "version d'outil invalide"),
        )
        object.__setattr__(
            self,
            "artifact_hash",
            _ensure_artifact_hash(self.artifact_hash),
        )
        object.__setattr__(self, "artifact_ref", _ensure_artifact_ref(self.artifact_ref))


@dataclass(frozen=True)
class CanonicalItemProvenance:
    """Provenance compatible SourceLocator pour un item canonique candidat."""

    schema_version: str
    canonical_version_id: str
    document_id: str
    page_pdf: int
    item_id: str
    bbox: tuple[float, float, float, float]
    content_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "schema_version",
            _ensure_source_locator_schema_version(self.schema_version),
        )
        object.__setattr__(
            self,
            "canonical_version_id",
            _ensure_domain_identifier(self.canonical_version_id, "canonical_version_id", "CVER"),
        )
        object.__setattr__(
            self,
            "document_id",
            _ensure_domain_identifier(self.document_id, "document_id", "DOC"),
        )
        object.__setattr__(self, "page_pdf", _ensure_positive_integer(self.page_pdf, "page_pdf invalide"))
        object.__setattr__(self, "item_id", _ensure_text(self.item_id, "item_id invalide"))
        object.__setattr__(self, "bbox", _ensure_normalized_bbox(self.bbox))
        object.__setattr__(self, "content_hash", _ensure_content_hash(self.content_hash))

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "canonical_version_id": self.canonical_version_id,
            "document_id": self.document_id,
            "page_pdf": self.page_pdf,
            "item_id": self.item_id,
            "bbox": list(self.bbox),
            "content_hash": self.content_hash,
        }


@dataclass(frozen=True)
class CanonicalDocumentItem:
    """Item intégré dans la représentation locale du DoclingDocument unique."""

    item_id: str
    label: str
    text: str
    bbox: tuple[float, float, float, float]
    content_hash: str
    provenance: CanonicalItemProvenance

    def __post_init__(self) -> None:
        object.__setattr__(self, "item_id", _ensure_text(self.item_id, "item_id invalide"))
        object.__setattr__(self, "label", _ensure_text(self.label, "label d'item invalide"))
        object.__setattr__(self, "text", _ensure_text(self.text, "texte d'item invalide"))
        object.__setattr__(self, "bbox", _ensure_normalized_bbox(self.bbox))
        object.__setattr__(self, "content_hash", _ensure_content_hash(self.content_hash))
        if not isinstance(self.provenance, CanonicalItemProvenance):
            raise ValueError("provenance d'item invalide")
        if self.provenance.item_id != self.item_id:
            raise ValueError("provenance d'item incohérente")
        if self.provenance.bbox != self.bbox:
            raise ValueError("bbox de provenance incohérente")
        if self.provenance.content_hash != self.content_hash:
            raise ValueError("hash de provenance incohérent")
        if self.content_hash != _content_hash_for_text(self.text):
            raise ValueError("content_hash incohérent avec le texte")

    def to_payload(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "label": self.label,
            "text": self.text,
            "bbox": list(self.bbox),
            "content_hash": self.content_hash,
            "provenance": self.provenance.to_payload(),
        }


@dataclass(frozen=True)
class CanonicalDocumentPage:
    """Page intégrée dans le document fusionné."""

    page_number: PageNumber
    route_name: PageRouteName
    conversion_artifact_hash: str
    items: tuple[CanonicalDocumentItem, ...]

    def __post_init__(self) -> None:
        _ensure_page_number(self.page_number)
        object.__setattr__(self, "route_name", PageRouteName.from_value(self.route_name))
        object.__setattr__(
            self,
            "conversion_artifact_hash",
            _ensure_artifact_hash(self.conversion_artifact_hash),
        )
        items = _ensure_canonical_items(self.items)
        for item in items:
            if item.provenance.page_pdf != self.page_number.value:
                raise ValueError("page_pdf de provenance incohérent")
        object.__setattr__(self, "items", items)

    def to_payload(self) -> dict[str, Any]:
        return {
            "page_pdf": self.page_number.value,
            "route_name": self.route_name.value,
            "conversion_artifact_hash": self.conversion_artifact_hash,
            "items": tuple(item.to_payload() for item in self.items),
        }


@dataclass(frozen=True)
class PagewiseDoclingDocument:
    """Représentation locale stricte du DoclingDocument unique M-004."""

    document_id: DocumentId
    canonical_version_id: str
    source_sha256: SourceFingerprint
    original_storage_ref: OriginalStorageRef
    pages: tuple[CanonicalDocumentPage, ...]

    def __post_init__(self) -> None:
        _ensure_document_id(self.document_id)
        object.__setattr__(
            self,
            "canonical_version_id",
            _ensure_domain_identifier(self.canonical_version_id, "canonical_version_id", "CVER"),
        )
        _ensure_source_fingerprint(self.source_sha256)
        _ensure_original_storage_ref(self.original_storage_ref)
        pages = _ensure_document_pages(self.pages)
        _ensure_document_page_order(pages)
        _ensure_unique_item_ids(pages)
        _ensure_document_provenance(
            document_id=self.document_id,
            canonical_version_id=self.canonical_version_id,
            pages=pages,
        )
        object.__setattr__(self, "pages", pages)

    def to_payload(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id.value,
            "canonical_version_id": self.canonical_version_id,
            "source_sha256": self.source_sha256.value,
            "original_storage_ref": self.original_storage_ref.value,
            "pages": tuple(page.to_payload() for page in self.pages),
        }


class PagewiseDoclingFusionService:
    """Fusionne les sorties routées dans l'ordre strict du PDF original."""

    def merge_authorized(
        self,
        *,
        document_id: DocumentId,
        canonical_version_id: str,
        source_sha256: SourceFingerprint,
        original_storage_ref: OriginalStorageRef,
        page_manifest: PageManifest,
        text_authority_manifest: TextAuthorityManifest,
    ) -> PagewiseDoclingDocument:
        parsed_page_manifest = _ensure_page_manifest(page_manifest)
        parsed_text_authority_manifest = _ensure_text_authority_manifest(
            text_authority_manifest
        )
        _ensure_text_authority_manifest_covers_page_manifest(
            page_manifest=parsed_page_manifest,
            page_decisions=parsed_text_authority_manifest.page_decisions,
        )
        return self.merge(
            document_id=document_id,
            canonical_version_id=canonical_version_id,
            source_sha256=source_sha256,
            original_storage_ref=original_storage_ref,
            page_manifest=parsed_page_manifest,
            page_outputs=parsed_text_authority_manifest.selected_page_outputs(),
        )

    def merge(
        self,
        *,
        document_id: DocumentId,
        canonical_version_id: str,
        source_sha256: SourceFingerprint,
        original_storage_ref: OriginalStorageRef,
        page_manifest: PageManifest,
        page_outputs: Sequence[PageConversionArtifact],
    ) -> PagewiseDoclingDocument:
        parsed_document_id = _ensure_document_id(document_id)
        parsed_canonical_version_id = _ensure_domain_identifier(
            canonical_version_id,
            "canonical_version_id",
            "CVER",
        )
        parsed_source_sha256 = _ensure_source_fingerprint(source_sha256)
        parsed_original_storage_ref = _ensure_original_storage_ref(original_storage_ref)
        parsed_manifest = _ensure_page_manifest(page_manifest)
        parsed_outputs = _ensure_page_outputs(page_outputs)
        _ensure_page_outputs_cover_manifest(
            page_manifest=parsed_manifest,
            page_outputs=parsed_outputs,
        )

        pages = tuple(
            _canonical_page_from_output(
                document_id=parsed_document_id,
                canonical_version_id=parsed_canonical_version_id,
                page_output=page_output,
            )
            for page_output in parsed_outputs
        )
        return PagewiseDoclingDocument(
            document_id=parsed_document_id,
            canonical_version_id=parsed_canonical_version_id,
            source_sha256=parsed_source_sha256,
            original_storage_ref=parsed_original_storage_ref,
            pages=pages,
        )


def _canonical_page_from_output(
    *,
    document_id: DocumentId,
    canonical_version_id: str,
    page_output: PageConversionArtifact,
) -> CanonicalDocumentPage:
    items = tuple(
        _canonical_item_from_conversion_item(
            document_id=document_id,
            canonical_version_id=canonical_version_id,
            page_number=page_output.page_number,
            item_index=item_index,
            conversion_item=conversion_item,
        )
        for item_index, conversion_item in enumerate(page_output.items, start=1)
    )
    return CanonicalDocumentPage(
        page_number=page_output.page_number,
        route_name=page_output.route_name,
        conversion_artifact_hash=page_output.artifact_hash,
        items=items,
    )


def _canonical_item_from_conversion_item(
    *,
    document_id: DocumentId,
    canonical_version_id: str,
    page_number: PageNumber,
    item_index: int,
    conversion_item: PageConversionItem,
) -> CanonicalDocumentItem:
    parsed_item_index = _ensure_positive_integer(item_index, "index d'item invalide")
    item_id = f"{document_id.value}-P{page_number.value:03d}-I{parsed_item_index:03d}"
    bbox = conversion_item.geometry.normalized_bbox()
    provenance = CanonicalItemProvenance(
        schema_version=_SOURCE_LOCATOR_SCHEMA_VERSION,
        canonical_version_id=canonical_version_id,
        document_id=document_id.value,
        page_pdf=page_number.value,
        item_id=item_id,
        bbox=bbox,
        content_hash=conversion_item.content_hash,
    )
    return CanonicalDocumentItem(
        item_id=item_id,
        label=conversion_item.label.value,
        text=conversion_item.text,
        bbox=bbox,
        content_hash=conversion_item.content_hash,
        provenance=provenance,
    )


def _ensure_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_quality_text(value: Any, message: str) -> str:
    return _ensure_text(value, message)


def _ensure_quality_policy_version(value: Any) -> str:
    return _ensure_text(value, "version de politique QA obligatoire")


def _ensure_quality_confidence_threshold(value: Any) -> float:
    number = _ensure_finite_number(value, "seuil de confiance critique invalide")
    if number <= 0 or number > 1:
        raise ValueError("seuil de confiance critique invalide")
    return number


def _ensure_critical_page_reasons(
    value: Sequence[CriticalPageReason],
) -> tuple[CriticalPageReason, ...]:
    if value is None:
        raise ValueError("raisons de pages critiques absentes")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("raisons de pages critiques invalides")
    reasons = tuple(value)
    if len(reasons) == 0:
        raise ValueError("raisons de pages critiques vides")
    for reason in reasons:
        if not isinstance(reason, CriticalPageReason):
            raise ValueError("raison de page critique invalide")
    reason_keys = tuple((reason.page_number.value, reason.reason) for reason in reasons)
    if len(reason_keys) != len(set(reason_keys)):
        raise ValueError("raison de page critique dupliquée")
    return reasons


def _deduplicate_critical_page_reasons(
    reasons: Sequence[CriticalPageReason],
) -> tuple[CriticalPageReason, ...]:
    reason_by_key: dict[tuple[int, str], CriticalPageReason] = {}
    for reason in reasons:
        reason_by_key[(reason.page_number.value, reason.reason)] = reason
    return tuple(reason_by_key[key] for key in sorted(reason_by_key))


def _sampling_position_reasons(
    page_numbers: tuple[PageNumber, ...],
) -> tuple[tuple[PageNumber, str], ...]:
    page_count = len(page_numbers)
    first_quarter_index = math.ceil(page_count * 0.25) - 1
    center_index = math.ceil(page_count * 0.50) - 1
    last_quarter_index = math.ceil(page_count * 0.75) - 1
    return (
        (page_numbers[0], "FIRST_CONTENT"),
        (page_numbers[first_quarter_index], "FIRST_QUARTER"),
        (page_numbers[center_index], "CENTER"),
        (page_numbers[last_quarter_index], "LAST_QUARTER"),
        (page_numbers[-1], "FINAL_PAGE"),
    )


def _ensure_page_diagnostics(
    value: Sequence[PageDecision],
) -> tuple[PageDecision, ...]:
    if value is None:
        raise ValueError("diagnostics de pages absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("diagnostics de pages invalides")
    diagnostics = tuple(value)
    if len(diagnostics) == 0:
        raise ValueError("diagnostics de pages vides")
    for diagnostic in diagnostics:
        if not isinstance(diagnostic, PageDecision):
            raise ValueError("diagnostic de page invalide")
    page_values = tuple(diagnostic.page_number.value for diagnostic in diagnostics)
    if len(page_values) != len(set(page_values)):
        raise ValueError("diagnostic de page dupliqué")
    return diagnostics


def _ensure_route_plan(value: Any) -> RoutePlan:
    if not isinstance(value, RoutePlan):
        raise ValueError("plan de routage invalide")
    return value


def _ensure_diagnostics_cover_manifest(
    *,
    page_manifest: PageManifest,
    page_diagnostics: tuple[PageDecision, ...],
) -> None:
    expected_pages = tuple(entry.page_number.value for entry in page_manifest.entries)
    actual_pages = tuple(diagnostic.page_number.value for diagnostic in page_diagnostics)
    if set(actual_pages) != set(expected_pages):
        raise ValueError("diagnostics de pages incomplets")


def _ensure_route_plan_covers_manifest(
    *,
    page_manifest: PageManifest,
    route_plan: RoutePlan,
) -> None:
    expected_pages = tuple(entry.page_number.value for entry in page_manifest.entries)
    actual_pages = tuple(page_route.page_number.value for page_route in route_plan.page_routes)
    if set(actual_pages) != set(expected_pages):
        raise ValueError("plan de routage incomplet")


def _ensure_route_comparisons(
    value: Sequence[PreConversionRouteComparison],
) -> tuple[PreConversionRouteComparison, ...]:
    if value is None:
        raise ValueError("comparaisons de routes absentes")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("comparaisons de routes invalides")
    comparisons = tuple(value)
    for comparison in comparisons:
        if not isinstance(comparison, PreConversionRouteComparison):
            raise ValueError("comparaison de route invalide")
    comparison_pages = tuple(comparison.page_number.value for comparison in comparisons)
    if len(comparison_pages) != len(set(comparison_pages)):
        raise ValueError("comparaison de route dupliquée")
    return comparisons


def _ensure_post_conversion_findings(
    value: Sequence[PostConversionQualityFinding],
) -> tuple[PostConversionQualityFinding, ...]:
    if value is None:
        raise ValueError("anomalies QA absentes")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("anomalies QA invalides")
    findings = tuple(value)
    for finding in findings:
        if not isinstance(finding, PostConversionQualityFinding):
            raise ValueError("anomalie QA invalide")
    return findings


def _ensure_publication_events(value: Sequence[str]) -> tuple[str, ...]:
    if value is None:
        raise ValueError("événements de publication absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("événements de publication invalides")
    events = tuple(_ensure_quality_text(event, "événement de publication invalide") for event in value)
    return events


def _ensure_source_document(value: Any) -> SourceDocument:
    if not isinstance(value, SourceDocument):
        raise ValueError("source_document QA invalide")
    return value


def _ensure_pre_conversion_report(value: Any) -> PreConversionQualityReport:
    if value is None:
        raise ValueError("rapport QA pré-conversion obligatoire")
    if not isinstance(value, PreConversionQualityReport):
        raise ValueError("rapport QA pré-conversion invalide")
    return value


def _ensure_post_conversion_report(value: Any) -> PostConversionQualityReport:
    if value is None:
        raise ValueError("rapport QA post-conversion obligatoire")
    if not isinstance(value, PostConversionQualityReport):
        raise ValueError("rapport QA post-conversion invalide")
    return value


def _ensure_report_policy_matches(
    *,
    policy_version: str,
    report_policy_version: str,
    message: str,
) -> None:
    if report_policy_version != policy_version:
        raise ValueError(message)


def _post_conversion_integrity_findings(
    *,
    page_manifest: PageManifest,
    text_authority_manifest: TextAuthorityManifest,
    docling_document: PagewiseDoclingDocument,
) -> tuple[PostConversionQualityFinding, ...]:
    expected_pages = tuple(entry.page_number.value for entry in page_manifest.entries)
    actual_pages = tuple(page.page_number.value for page in docling_document.pages)
    missing_pages = tuple(page for page in expected_pages if page not in set(actual_pages))
    unexpected_pages = tuple(page for page in actual_pages if page not in set(expected_pages))
    missing_findings = tuple(
        PostConversionQualityFinding(
            code=QualityFindingCode.PAGE_OMITTED,
            page_number=PageNumber.from_value(page_value),
            item_id=f"PAGE-{page_value:03d}",
            expected="PRESENT",
            actual="ABSENT",
            detail="Page absente du DoclingDocument.",
        )
        for page_value in missing_pages
    )
    unexpected_findings = tuple(
        PostConversionQualityFinding(
            code=QualityFindingCode.PAGE_UNEXPECTED,
            page_number=PageNumber.from_value(page_value),
            item_id=f"PAGE-{page_value:03d}",
            expected="ABSENT",
            actual="PRESENT",
            detail="Page hors manifeste dans le DoclingDocument.",
        )
        for page_value in unexpected_pages
    )
    authority_findings = _text_authority_document_findings(
        page_manifest=page_manifest,
        text_authority_manifest=text_authority_manifest,
        docling_document=docling_document,
    )
    return missing_findings + unexpected_findings + authority_findings


def _text_authority_document_findings(
    *,
    page_manifest: PageManifest,
    text_authority_manifest: TextAuthorityManifest,
    docling_document: PagewiseDoclingDocument,
) -> tuple[PostConversionQualityFinding, ...]:
    authorized_document = PagewiseDoclingFusionService().merge_authorized(
        document_id=docling_document.document_id,
        canonical_version_id=docling_document.canonical_version_id,
        source_sha256=docling_document.source_sha256,
        original_storage_ref=docling_document.original_storage_ref,
        page_manifest=page_manifest,
        text_authority_manifest=text_authority_manifest,
    )
    if authorized_document.to_payload() == docling_document.to_payload():
        return ()
    authorized_pages = {
        page.page_number.value: page.to_payload()
        for page in authorized_document.pages
    }
    actual_pages = {
        page.page_number.value: page.to_payload()
        for page in docling_document.pages
    }
    return tuple(
        PostConversionQualityFinding(
            code=QualityFindingCode.SOURCE_LOCATOR_INCONSISTENT,
            page_number=PageNumber.from_value(page_value),
            item_id=f"PAGE-{page_value:03d}",
            expected="AUTHORIZED_TEXT",
            actual="CANDIDATE_TEXT",
            detail="DoclingDocument incohérent avec l'autorité textuelle.",
        )
        for page_value in sorted(authorized_pages.keys() & actual_pages.keys())
        if authorized_pages[page_value] != actual_pages[page_value]
    )


def _post_conversion_status_for(
    findings: tuple[PostConversionQualityFinding, ...],
) -> QualityDecisionStatus:
    if len(findings) == 0:
        return QualityDecisionStatus.PASS
    if all(not finding.blocking for finding in findings):
        return QualityDecisionStatus.PASS_WITH_WARNINGS
    return QualityDecisionStatus.MANUAL_REVIEW


def _canonical_decision_status(
    *,
    pre_conversion_status: QualityDecisionStatus,
    post_conversion_status: QualityDecisionStatus,
) -> QualityDecisionStatus:
    if (
        pre_conversion_status is QualityDecisionStatus.QUARANTINE
        or post_conversion_status is QualityDecisionStatus.QUARANTINE
    ):
        return QualityDecisionStatus.QUARANTINE
    if pre_conversion_status is QualityDecisionStatus.RETRY_WITH_ALTERNATIVE_ROUTE:
        return QualityDecisionStatus.RETRY_WITH_ALTERNATIVE_ROUTE
    if (
        pre_conversion_status is QualityDecisionStatus.MANUAL_REVIEW
        or post_conversion_status is QualityDecisionStatus.MANUAL_REVIEW
    ):
        return QualityDecisionStatus.MANUAL_REVIEW
    if (
        pre_conversion_status is QualityDecisionStatus.PASS_WITH_WARNINGS
        or post_conversion_status is QualityDecisionStatus.PASS_WITH_WARNINGS
    ):
        return QualityDecisionStatus.PASS_WITH_WARNINGS
    return QualityDecisionStatus.PASS


def _ensure_text(value: Any, message: str) -> str:
    if not isinstance(value, str):
        raise ValueError(message)
    if value.strip() == "":
        raise ValueError(message)
    if value != value.strip():
        raise ValueError(message)
    return value


def _ensure_text_authority_error_code(value: Any) -> str:
    if value in {_PAGE_AUTHORITY_MISSING, _PAGE_AUTHORITY_AMBIGUOUS}:
        return value
    raise ValueError("code d'erreur d'autorité textuelle inconnu")


def _ensure_authority_text(value: Any, message: str) -> str:
    if not isinstance(value, str):
        raise TextAuthoritySelectionError(_PAGE_AUTHORITY_MISSING, message)
    if value.strip() == "":
        raise TextAuthoritySelectionError(_PAGE_AUTHORITY_MISSING, message)
    if value != value.strip():
        raise TextAuthoritySelectionError(_PAGE_AUTHORITY_MISSING, message)
    return value


def _ensure_authority_candidates(
    value: Sequence[PageConversionCandidate],
    *,
    page_number: PageNumber,
) -> tuple[PageConversionCandidate, ...]:
    if value is None:
        raise TextAuthoritySelectionError(
            _PAGE_AUTHORITY_MISSING,
            "candidats d'autorité absents",
        )
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise TextAuthoritySelectionError(
            _PAGE_AUTHORITY_MISSING,
            "candidats d'autorité invalides",
        )
    candidates = tuple(value)
    if len(candidates) == 0:
        raise TextAuthoritySelectionError(
            _PAGE_AUTHORITY_MISSING,
            "candidats d'autorité vides",
        )
    candidate_ids: list[str] = []
    for candidate in candidates:
        if not isinstance(candidate, PageConversionCandidate):
            raise TextAuthoritySelectionError(
                _PAGE_AUTHORITY_MISSING,
                "candidat d'autorité invalide",
            )
        if candidate.page_number != page_number:
            raise TextAuthoritySelectionError(
                _PAGE_AUTHORITY_MISSING,
                "candidat d'autorité hors page",
            )
        candidate_ids.append(candidate.candidate_id)
    if len(candidate_ids) != len(set(candidate_ids)):
        raise TextAuthoritySelectionError(
            _PAGE_AUTHORITY_AMBIGUOUS,
            "candidats d'autorité dupliqués",
        )
    return candidates


def _ensure_selected_candidate_ids(value: Sequence[str]) -> tuple[str, ...]:
    if value is None:
        raise TextAuthoritySelectionError(
            _PAGE_AUTHORITY_MISSING,
            "sélection d'autorité absente",
        )
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise TextAuthoritySelectionError(
            _PAGE_AUTHORITY_MISSING,
            "sélection d'autorité invalide",
        )
    selected_ids = tuple(
        _ensure_authority_text(candidate_id, "identifiant d'autorité vide")
        for candidate_id in value
    )
    if len(selected_ids) != len(set(selected_ids)):
        raise TextAuthoritySelectionError(
            _PAGE_AUTHORITY_AMBIGUOUS,
            "sélection d'autorité dupliquée",
        )
    return selected_ids


def _ensure_text_authority_page_decisions(
    value: Sequence[TextAuthorityPageDecision],
) -> tuple[TextAuthorityPageDecision, ...]:
    if value is None:
        raise TextAuthoritySelectionError(
            _PAGE_AUTHORITY_MISSING,
            "décisions d'autorité absentes",
        )
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise TextAuthoritySelectionError(
            _PAGE_AUTHORITY_MISSING,
            "décisions d'autorité invalides",
        )
    decisions = tuple(value)
    if len(decisions) == 0:
        raise TextAuthoritySelectionError(
            _PAGE_AUTHORITY_MISSING,
            "décisions d'autorité vides",
        )
    page_numbers: list[int] = []
    for decision in decisions:
        if not isinstance(decision, TextAuthorityPageDecision):
            raise TextAuthoritySelectionError(
                _PAGE_AUTHORITY_MISSING,
                "décision d'autorité invalide",
            )
        page_numbers.append(decision.page_number.value)
    if len(page_numbers) != len(set(page_numbers)):
        raise TextAuthoritySelectionError(
            _PAGE_AUTHORITY_AMBIGUOUS,
            "décision d'autorité dupliquée pour une page",
        )
    return decisions


def _ensure_text_authority_manifest(
    value: Any,
) -> TextAuthorityManifest:
    if not isinstance(value, TextAuthorityManifest):
        raise TextAuthoritySelectionError(
            _PAGE_AUTHORITY_MISSING,
            "manifeste d'autorité textuelle absent",
        )
    return value


def _ensure_text_authority_manifest_covers_page_manifest(
    *,
    page_manifest: PageManifest,
    page_decisions: tuple[TextAuthorityPageDecision, ...],
) -> None:
    expected_pages = tuple(entry.page_number.value for entry in page_manifest.entries)
    actual_pages = tuple(decision.page_number.value for decision in page_decisions)
    if len(actual_pages) != len(set(actual_pages)):
        raise TextAuthoritySelectionError(
            _PAGE_AUTHORITY_AMBIGUOUS,
            "plusieurs autorités textuelles pour une page",
        )
    if set(actual_pages) != set(expected_pages):
        raise TextAuthoritySelectionError(
            _PAGE_AUTHORITY_MISSING,
            "autorité textuelle absente pour une page publiée",
        )
    if actual_pages != expected_pages:
        raise TextAuthoritySelectionError(
            _PAGE_AUTHORITY_AMBIGUOUS,
            "ordre des autorités textuelles ambigu",
        )


def _content_hash_for_text(value: str) -> str:
    text = _ensure_text(value, "texte d'item invalide")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _ensure_document_provenance(
    *,
    document_id: DocumentId,
    canonical_version_id: str,
    pages: tuple[CanonicalDocumentPage, ...],
) -> None:
    parsed_document_id = _ensure_document_id(document_id)
    parsed_canonical_version_id = _ensure_domain_identifier(
        canonical_version_id,
        "canonical_version_id",
        "CVER",
    )
    for page in pages:
        for item in page.items:
            if item.provenance.document_id != parsed_document_id.value:
                raise ValueError("document_id de provenance incohérent")
            if item.provenance.canonical_version_id != parsed_canonical_version_id:
                raise ValueError("version de provenance incohérente")


def _ensure_content_hash(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("content_hash non textuel")
    if value.strip() == "":
        raise ValueError("content_hash vide")
    if value != value.strip():
        raise ValueError("content_hash non normalisé")
    if len(value) != 64:
        raise ValueError("content_hash invalide")
    for character in value:
        if character not in "0123456789abcdef":
            raise ValueError("content_hash invalide")
    return value


def _ensure_artifact_hash(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("hash d'artefact invalide")
    if value.strip() == "":
        raise ValueError("hash d'artefact invalide")
    if value != value.strip():
        raise ValueError("hash d'artefact invalide")
    if len(value) != 64:
        raise ValueError("hash d'artefact invalide")
    for character in value:
        if character not in "0123456789abcdef":
            raise ValueError("hash d'artefact invalide")
    return value


def _ensure_artifact_ref(value: Any) -> str:
    text = _ensure_text(value, "référence d'artefact invalide")
    if _ARTIFACT_REF_PATTERN.fullmatch(text) is None:
        raise ValueError("référence d'artefact invalide")
    if "/../" in text or text.endswith("/..") or "/./" in text or text.endswith("/."):
        raise ValueError("référence d'artefact invalide")
    return text


def _ensure_finite_number(value: Any, message: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(message)
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(message)
    return number


def _ensure_positive_finite_number(value: Any, message: str) -> float:
    number = _ensure_finite_number(value, message)
    if number <= 0:
        raise ValueError(message)
    return number


def _ensure_positive_integer(value: Any, message: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(message)
    return value


def _ensure_normalized_bbox(value: Any) -> tuple[float, float, float, float]:
    if isinstance(value, str) or not hasattr(value, "__iter__"):
        raise ValueError("bbox invalide")
    coordinates = tuple(value)
    if len(coordinates) != 4:
        raise ValueError("bbox invalide")
    left, top, right, bottom = (
        _ensure_finite_number(coordinate, "bbox invalide")
        for coordinate in coordinates
    )
    if left < 0 or top < 0 or right > 1 or bottom > 1:
        raise ValueError("bbox invalide")
    if left >= right or top >= bottom:
        raise ValueError("bbox invalide")
    return (left, top, right, bottom)


def _ensure_source_locator_schema_version(value: Any) -> str:
    text = _ensure_text(value, "schema_version invalide")
    if text != _SOURCE_LOCATOR_SCHEMA_VERSION:
        raise ValueError("schema_version invalide")
    return text


def _ensure_domain_identifier(value: Any, field_name: str, expected_prefix: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} invalide")
    try:
        return str(DomainIdentifier.parse_with_prefix(value, expected_prefix))
    except ValueError as exc:
        raise ValueError(f"{field_name} invalide: {exc}") from exc


def _ensure_page_number(value: Any) -> PageNumber:
    if not isinstance(value, PageNumber):
        raise ValueError("page_number invalide")
    return value


def _ensure_page_item_geometry(value: Any) -> PageItemGeometry:
    if not isinstance(value, PageItemGeometry):
        raise ValueError("géométrie d'item invalide")
    return value


def _ensure_conversion_items(
    value: Sequence[PageConversionItem],
) -> tuple[PageConversionItem, ...]:
    if value is None:
        raise ValueError("items de conversion absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("items de conversion invalides")
    items = tuple(value)
    if len(items) == 0:
        raise ValueError("items de conversion vides")
    for item in items:
        if not isinstance(item, PageConversionItem):
            raise ValueError("item de conversion invalide")
    return items


def _ensure_canonical_items(
    value: Sequence[CanonicalDocumentItem],
) -> tuple[CanonicalDocumentItem, ...]:
    if value is None:
        raise ValueError("items canoniques absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("items canoniques invalides")
    items = tuple(value)
    if len(items) == 0:
        raise ValueError("items canoniques vides")
    for item in items:
        if not isinstance(item, CanonicalDocumentItem):
            raise ValueError("item canonique invalide")
    return items


def _ensure_document_pages(
    value: Sequence[CanonicalDocumentPage],
) -> tuple[CanonicalDocumentPage, ...]:
    if value is None:
        raise ValueError("pages fusionnées absentes")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("pages fusionnées invalides")
    pages = tuple(value)
    if len(pages) == 0:
        raise ValueError("pages fusionnées vides")
    for page in pages:
        if not isinstance(page, CanonicalDocumentPage):
            raise ValueError("page fusionnée invalide")
    return pages


def _ensure_document_page_order(pages: tuple[CanonicalDocumentPage, ...]) -> None:
    for expected_page_number, page in enumerate(pages, start=1):
        if page.page_number.value != expected_page_number:
            raise ValueError("ordre strict des pages invalide")


def _ensure_unique_item_ids(pages: tuple[CanonicalDocumentPage, ...]) -> None:
    item_ids = tuple(item.item_id for page in pages for item in page.items)
    if len(item_ids) != len(set(item_ids)):
        raise ValueError("item_id canonique dupliqué")


def _ensure_page_manifest(value: Any) -> PageManifest:
    if not isinstance(value, PageManifest):
        raise ValueError("manifeste de pages invalide")
    return value


def _ensure_page_outputs(
    value: Sequence[PageConversionArtifact],
) -> tuple[PageConversionArtifact, ...]:
    if value is None:
        raise ValueError("sorties de conversion absentes")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("sorties de conversion invalides")
    outputs = tuple(value)
    if len(outputs) == 0:
        raise ValueError("sorties de conversion vides")
    for output in outputs:
        if not isinstance(output, PageConversionArtifact):
            raise ValueError("sortie de conversion invalide")
    return outputs


def _ensure_page_outputs_cover_manifest(
    *,
    page_manifest: PageManifest,
    page_outputs: tuple[PageConversionArtifact, ...],
) -> None:
    expected_pages = tuple(entry.page_number.value for entry in page_manifest.entries)
    actual_pages = tuple(output.page_number.value for output in page_outputs)
    if set(actual_pages) != set(expected_pages):
        raise ValueError("page de conversion manquante")
    if actual_pages != expected_pages:
        raise ValueError("ordre strict des pages invalide")


def _ensure_document_id(value: Any) -> DocumentId:
    if not isinstance(value, DocumentId):
        raise ValueError("document_id invalide")
    return value


def _ensure_source_fingerprint(value: Any) -> SourceFingerprint:
    if not isinstance(value, SourceFingerprint):
        raise ValueError("source_sha256 invalide")
    return value


def _ensure_original_storage_ref(value: Any) -> OriginalStorageRef:
    if not isinstance(value, OriginalStorageRef):
        raise ValueError("original_storage_ref invalide")
    return value


__all__ = [
    "CanonicalAcceptancePolicy",
    "CanonicalDocumentItem",
    "CanonicalDocumentPage",
    "CanonicalItemProvenance",
    "CanonicalQualityDecision",
    "ConversionToolName",
    "CriticalPageReason",
    "CriticalPageSamplingPolicy",
    "CriticalPageSelection",
    "PageConversionArtifact",
    "PageConversionCandidate",
    "PageConversionItem",
    "PageConversionItemLabel",
    "PageItemGeometry",
    "PagewiseDoclingDocument",
    "PagewiseDoclingFusionService",
    "PostConversionQualityFinding",
    "PostConversionQualityReport",
    "PreConversionQualityReport",
    "PreConversionRouteComparison",
    "PreprocessedPageArtifact",
    "QualityDecisionStatus",
    "QualityFindingCode",
    "TextAuthority",
    "TextAuthorityManifest",
    "TextAuthorityPageDecision",
    "TextAuthoritySelectionError",
    "TextAuthoritySelectionPolicy",
]
