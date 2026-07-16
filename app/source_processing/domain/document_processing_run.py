"""Tentative de traitement documentaire et manifeste de pages SP."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.source_processing.domain.source_document import DocumentId, SourceDocument


_PROCESSING_RUN_ID_PATTERN = re.compile(r"^RUN-[A-Z0-9][A-Z0-9-]*$")


class DocumentProcessingRunStatus(str, Enum):
    """État métier explicite d'une tentative de traitement documentaire."""

    MANIFEST_CREATED = "MANIFEST_CREATED"
    DIAGNOSING = "DIAGNOSING"
    DIAGNOSED = "DIAGNOSED"
    ROUTE_PLANNED = "ROUTE_PLANNED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    QUARANTINED = "QUARANTINED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class PageManifestEntryState(str, Enum):
    """État minimal d'une page dans le manifeste avant diagnostic."""

    PRESENT = "PRESENT"
    EMPTY = "EMPTY"
    UNREADABLE = "UNREADABLE"
    REJECTED = "REJECTED"

    @classmethod
    def from_value(cls, value: "PageManifestEntryState | str") -> "PageManifestEntryState":
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise ValueError("état de page manifeste inconnu")
        for state in cls:
            if state.value == value:
                return state
        raise ValueError("état de page manifeste inconnu")


class PageDecisionState(str, Enum):
    """État diagnostique métier publié pour une page source."""

    NATIVE_OK = "NATIVE_OK"
    NATIVE_SUSPECT = "NATIVE_SUSPECT"
    SCAN_CLEAN = "SCAN_CLEAN"
    SCAN_DEGRADED = "SCAN_DEGRADED"
    OCR_BAD = "OCR_BAD"
    MIXED_CONTENT = "MIXED_CONTENT"
    COMPLEX_VISUAL = "COMPLEX_VISUAL"
    EMPTY = "EMPTY"
    UNSUPPORTED_OR_CORRUPT = "UNSUPPORTED_OR_CORRUPT"

    @classmethod
    def from_value(cls, value: "PageDecisionState | str") -> "PageDecisionState":
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise ValueError("état de diagnostic inconnu")
        for state in cls:
            if state.value == value:
                return state
        raise ValueError("état de diagnostic inconnu")


class PageRouteName(str, Enum):
    """Route documentaire explicite issue du diagnostic de page."""

    NATIVE_STANDARD = "NATIVE_STANDARD"
    SCAN_GRANITE = "SCAN_GRANITE"
    PREPROCESS_GRANITE = "PREPROCESS_GRANITE"
    BAD_OCR_TO_GRANITE = "BAD_OCR_TO_GRANITE"
    MIXED_PAGEWISE = "MIXED_PAGEWISE"
    TARGETED_ENRICHMENT = "TARGETED_ENRICHMENT"
    SKIP_EMPTY = "SKIP_EMPTY"

    @classmethod
    def from_value(cls, value: "PageRouteName | str") -> "PageRouteName":
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise ValueError("route de page inconnue")
        for route_name in cls:
            if route_name.value == value:
                return route_name
        raise ValueError("route de page inconnue")


class RouteDecisionMode(str, Enum):
    """Mode de décision appliqué à une route de page."""

    AUTO = "AUTO"
    BENCHMARK = "BENCHMARK"
    MANUAL = "MANUAL"
    MANUAL_REVIEW = "MANUAL_REVIEW"

    @classmethod
    def from_value(cls, value: "RouteDecisionMode | str") -> "RouteDecisionMode":
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise ValueError("mode de décision de route inconnu")
        for decision_mode in cls:
            if decision_mode.value == value:
                return decision_mode
        raise ValueError("mode de décision de route inconnu")


class PagePreprocessingAction(str, Enum):
    """Prétraitement conditionnel décidé avant conversion documentaire."""

    NONE = "NONE"
    OCR_PHYSICAL_PREPROCESSING = "OCR_PHYSICAL_PREPROCESSING"

    @classmethod
    def from_value(
        cls,
        value: "PagePreprocessingAction | str",
    ) -> "PagePreprocessingAction":
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise ValueError("prétraitement de page inconnu")
        for preprocessing_action in cls:
            if preprocessing_action.value == value:
                return preprocessing_action
        raise ValueError("prétraitement de page inconnu")


class RoutePlanningOutcome(str, Enum):
    """Issue globale de la politique de routage."""

    ROUTE_PLANNED = "ROUTE_PLANNED"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class ManualReviewDecisionType(str, Enum):
    """Décision humaine publique qui résout ou termine une revue."""

    CONFIRM_EMPTY = "CONFIRM_EMPTY"
    ASSIGN_ROUTE = "ASSIGN_ROUTE"
    REJECT_DOCUMENT = "REJECT_DOCUMENT"

    @classmethod
    def from_value(
        cls,
        value: "ManualReviewDecisionType | str",
    ) -> "ManualReviewDecisionType":
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise ValueError("décision de revue manuelle inconnue")
        try:
            return cls(value)
        except ValueError as exc:
            raise ValueError("décision de revue manuelle inconnue") from exc


class NativeTextSignal(str, Enum):
    """Signal technique inspecté pour la couche texte native."""

    RELIABLE = "RELIABLE"
    SUSPECT = "SUSPECT"
    ABSENT = "ABSENT"

    @classmethod
    def from_value(cls, value: "NativeTextSignal | str") -> "NativeTextSignal":
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise ValueError("signal texte natif inconnu")
        for signal in cls:
            if signal.value == value:
                return signal
        raise ValueError("signal texte natif inconnu")


class PageImageSignal(str, Enum):
    """Signal technique inspecté pour la présence d'image scannée."""

    NONE = "NONE"
    SCAN_CLEAN = "SCAN_CLEAN"
    SCAN_DEGRADED = "SCAN_DEGRADED"

    @classmethod
    def from_value(cls, value: "PageImageSignal | str") -> "PageImageSignal":
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise ValueError("signal image inconnu")
        for signal in cls:
            if signal.value == value:
                return signal
        raise ValueError("signal image inconnu")


class ExistingOcrSignal(str, Enum):
    """Signal technique inspecté pour une couche OCR déjà présente."""

    NONE = "NONE"
    VALID = "VALID"
    BAD = "BAD"

    @classmethod
    def from_value(cls, value: "ExistingOcrSignal | str") -> "ExistingOcrSignal":
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise ValueError("signal OCR existant inconnu")
        for signal in cls:
            if signal.value == value:
                return signal
        raise ValueError("signal OCR existant inconnu")


class LayoutComplexitySignal(str, Enum):
    """Signal technique inspecté pour la complexité visuelle."""

    SIMPLE = "SIMPLE"
    COMPLEX = "COMPLEX"

    @classmethod
    def from_value(cls, value: "LayoutComplexitySignal | str") -> "LayoutComplexitySignal":
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise ValueError("signal complexité visuelle inconnu")
        for signal in cls:
            if signal.value == value:
                return signal
        raise ValueError("signal complexité visuelle inconnu")


class PageCorruptionSignal(str, Enum):
    """Signal technique inspecté pour une page corrompue."""

    NONE = "NONE"
    CORRUPT = "CORRUPT"

    @classmethod
    def from_value(cls, value: "PageCorruptionSignal | str") -> "PageCorruptionSignal":
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise ValueError("signal corruption inconnu")
        for signal in cls:
            if signal.value == value:
                return signal
        raise ValueError("signal corruption inconnu")


@dataclass(frozen=True)
class ProcessingRunId:
    """Identifiant interne d'une tentative de traitement SP."""

    value: str

    @classmethod
    def from_value(cls, value: str) -> "ProcessingRunId":
        return cls(value=_ensure_processing_run_id_value(value))

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _ensure_processing_run_id_value(self.value))


@dataclass(frozen=True)
class PageNumber:
    """Numéro de page PDF strictement positif."""

    value: int

    @classmethod
    def from_value(cls, value: int) -> "PageNumber":
        return cls(value=_ensure_page_number_value(value))

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _ensure_page_number_value(self.value))


@dataclass(frozen=True)
class PageManifestEntry:
    """Entrée explicite d'une page dans le manifeste."""

    page_number: PageNumber
    state: PageManifestEntryState

    def __post_init__(self) -> None:
        _ensure_page_number(self.page_number)
        object.__setattr__(self, "state", PageManifestEntryState.from_value(self.state))


@dataclass(frozen=True)
class PageManifest:
    """Inventaire complet et ordonné des pages attendues."""

    source_page_count: int
    entries: tuple[PageManifestEntry, ...]

    @classmethod
    def from_entries(
        cls,
        source_page_count: int,
        entries: Sequence[PageManifestEntry],
    ) -> "PageManifest":
        return cls(source_page_count=source_page_count, entries=tuple(entries))

    def __post_init__(self) -> None:
        source_page_count = _ensure_source_page_count(self.source_page_count)
        entries = _ensure_manifest_entries(self.entries)
        _ensure_manifest_completeness(
            source_page_count=source_page_count,
            entries=entries,
        )
        object.__setattr__(self, "source_page_count", source_page_count)
        object.__setattr__(self, "entries", entries)


@dataclass(frozen=True)
class DiagnosticVersion:
    """Version explicite de la politique de diagnostic appliquée."""

    value: str

    @classmethod
    def from_value(cls, value: str) -> "DiagnosticVersion":
        return cls(value=_ensure_diagnostic_version_value(value))

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "value",
            _ensure_diagnostic_version_value(self.value),
        )


@dataclass(frozen=True)
class RoutingPolicyVersion:
    """Version explicite de la configuration de routage appliquée."""

    value: str

    @classmethod
    def from_value(cls, value: str) -> "RoutingPolicyVersion":
        return cls(value=_ensure_routing_policy_version_value(value))

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "value",
            _ensure_routing_policy_version_value(self.value),
        )


@dataclass(frozen=True)
class PageRoutingConfiguration:
    """Seuils versionnés utilisés par la politique de routage de page."""

    routing_policy_version: RoutingPolicyVersion
    auto_confidence_min: float
    benchmark_confidence_min: float

    def __post_init__(self) -> None:
        _ensure_routing_policy_version(self.routing_policy_version)
        object.__setattr__(
            self,
            "auto_confidence_min",
            _ensure_route_confidence_score(self.auto_confidence_min),
        )
        object.__setattr__(
            self,
            "benchmark_confidence_min",
            _ensure_route_confidence_score(self.benchmark_confidence_min),
        )
        if self.auto_confidence_min < self.benchmark_confidence_min:
            raise ValueError("ordre des seuils de routage invalide")


@dataclass(frozen=True)
class PageDiagnosticSignals:
    """Signaux techniques conservés pour justifier une décision de page."""

    native_text_state: NativeTextSignal
    image_state: PageImageSignal
    existing_ocr_state: ExistingOcrSignal
    layout_complexity: LayoutComplexitySignal
    corruption_state: PageCorruptionSignal
    mixed_content_detected: bool
    has_table: bool
    has_formula: bool

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "native_text_state",
            NativeTextSignal.from_value(self.native_text_state),
        )
        object.__setattr__(
            self,
            "image_state",
            PageImageSignal.from_value(self.image_state),
        )
        object.__setattr__(
            self,
            "existing_ocr_state",
            ExistingOcrSignal.from_value(self.existing_ocr_state),
        )
        object.__setattr__(
            self,
            "layout_complexity",
            LayoutComplexitySignal.from_value(self.layout_complexity),
        )
        object.__setattr__(
            self,
            "corruption_state",
            PageCorruptionSignal.from_value(self.corruption_state),
        )
        _ensure_bool(self.mixed_content_detected, "mixed_content_detected")
        _ensure_bool(self.has_table, "has_table")
        _ensure_bool(self.has_formula, "has_formula")


@dataclass(frozen=True)
class ManualReviewResolution:
    """Résolution humaine persistée sur la page diagnostiquée."""

    decision: ManualReviewDecisionType
    route_name: PageRouteName | None
    reviewer_id: str
    reason: str

    def __post_init__(self) -> None:
        parsed_decision = ManualReviewDecisionType.from_value(self.decision)
        if parsed_decision is ManualReviewDecisionType.REJECT_DOCUMENT:
            raise ValueError("rejet document interdit comme résolution de page")
        parsed_route = None if self.route_name is None else PageRouteName.from_value(self.route_name)
        if parsed_decision is ManualReviewDecisionType.CONFIRM_EMPTY:
            if parsed_route is not None:
                raise ValueError("route interdite pour une page confirmée vide")
        elif parsed_route is None or parsed_route is PageRouteName.SKIP_EMPTY:
            raise ValueError("route manuelle de conversion invalide")
        object.__setattr__(self, "decision", parsed_decision)
        object.__setattr__(self, "route_name", parsed_route)
        object.__setattr__(
            self,
            "reviewer_id",
            _ensure_manual_review_actor(self.reviewer_id),
        )
        object.__setattr__(self, "reason", _ensure_manual_review_reason(self.reason))


@dataclass(frozen=True)
class PageDecision:
    """Décision diagnostique explicite pour une page source."""

    page_number: PageNumber
    page_state: PageDecisionState
    signals: PageDiagnosticSignals
    diagnostic_version: DiagnosticVersion
    justification: str
    manual_review_resolution: ManualReviewResolution | None = None

    def __post_init__(self) -> None:
        _ensure_page_number(self.page_number)
        object.__setattr__(
            self,
            "page_state",
            PageDecisionState.from_value(self.page_state),
        )
        _ensure_page_diagnostic_signals(self.signals)
        _ensure_diagnostic_version(self.diagnostic_version)
        object.__setattr__(
            self,
            "justification",
            _ensure_diagnostic_justification(self.justification),
        )
        if self.manual_review_resolution is not None and not isinstance(
            self.manual_review_resolution,
            ManualReviewResolution,
        ):
            raise ValueError("résolution de revue manuelle invalide")

    def resolve_manual_review(
        self,
        resolution: ManualReviewResolution,
    ) -> "PageDecision":
        if not isinstance(resolution, ManualReviewResolution):
            raise ValueError("résolution de revue manuelle invalide")
        if self.manual_review_resolution is not None:
            raise ValueError("page déjà résolue manuellement")
        return PageDecision(
            page_number=self.page_number,
            page_state=self.page_state,
            signals=self.signals,
            diagnostic_version=self.diagnostic_version,
            justification=self.justification,
            manual_review_resolution=resolution,
        )


@dataclass(frozen=True)
class PageRoute:
    """Route explicite et justifiée pour une page diagnostiquée."""

    page_number: PageNumber
    route_name: PageRouteName
    decision_mode: RouteDecisionMode
    confidence_score: float
    preprocessing_action: PagePreprocessingAction
    routing_policy_version: RoutingPolicyVersion
    justification: str

    def __post_init__(self) -> None:
        _ensure_page_number(self.page_number)
        object.__setattr__(self, "route_name", PageRouteName.from_value(self.route_name))
        object.__setattr__(
            self,
            "decision_mode",
            RouteDecisionMode.from_value(self.decision_mode),
        )
        if self.decision_mode is RouteDecisionMode.MANUAL_REVIEW:
            raise ValueError("route de page en revue manuelle invalide")
        object.__setattr__(
            self,
            "confidence_score",
            _ensure_route_confidence_score(self.confidence_score),
        )
        object.__setattr__(
            self,
            "preprocessing_action",
            PagePreprocessingAction.from_value(self.preprocessing_action),
        )
        _ensure_routing_policy_version(self.routing_policy_version)
        object.__setattr__(
            self,
            "justification",
            _ensure_route_justification(self.justification),
        )
        _ensure_page_route_preprocessing(
            route_name=self.route_name,
            preprocessing_action=self.preprocessing_action,
        )


@dataclass(frozen=True)
class RoutePlan:
    """Plan de routage approuvé pour toutes les pages diagnostiquées."""

    routing_policy_version: RoutingPolicyVersion
    page_routes: tuple[PageRoute, ...]
    dominant_route_name: PageRouteName
    page_exceptions: tuple[PageRoute, ...]
    confidence_score: float

    def __post_init__(self) -> None:
        _ensure_routing_policy_version(self.routing_policy_version)
        page_routes = _ensure_page_routes(self.page_routes)
        object.__setattr__(self, "page_routes", page_routes)
        object.__setattr__(
            self,
            "dominant_route_name",
            PageRouteName.from_value(self.dominant_route_name),
        )
        page_exceptions = _ensure_page_routes(
            self.page_exceptions,
            allow_empty=True,
        )
        _ensure_route_plan_exceptions(
            page_routes=page_routes,
            dominant_route_name=self.dominant_route_name,
            page_exceptions=page_exceptions,
        )
        object.__setattr__(self, "page_exceptions", page_exceptions)
        object.__setattr__(
            self,
            "confidence_score",
            _ensure_route_confidence_score(self.confidence_score),
        )
        for page_route in page_routes:
            if page_route.routing_policy_version != self.routing_policy_version:
                raise ValueError("version de routage incohérente")


@dataclass(frozen=True)
class RoutePlanningResult:
    """Résultat pur de la politique de routage avant transition d'agrégat."""

    outcome: RoutePlanningOutcome
    routing_policy_version: RoutingPolicyVersion
    route_plan: RoutePlan | None
    manual_review_reason: str | None

    @classmethod
    def route_planned(cls, route_plan: RoutePlan) -> "RoutePlanningResult":
        parsed_route_plan = _ensure_route_plan(route_plan)
        return cls(
            outcome=RoutePlanningOutcome.ROUTE_PLANNED,
            routing_policy_version=parsed_route_plan.routing_policy_version,
            route_plan=parsed_route_plan,
            manual_review_reason=None,
        )

    @classmethod
    def manual_review(
        cls,
        routing_policy_version: RoutingPolicyVersion,
        reason: str,
    ) -> "RoutePlanningResult":
        return cls(
            outcome=RoutePlanningOutcome.MANUAL_REVIEW,
            routing_policy_version=_ensure_routing_policy_version(
                routing_policy_version
            ),
            route_plan=None,
            manual_review_reason=_ensure_manual_review_reason(reason),
        )

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, RoutePlanningOutcome):
            raise ValueError("issue de routage invalide")
        _ensure_routing_policy_version(self.routing_policy_version)
        if self.outcome is RoutePlanningOutcome.ROUTE_PLANNED:
            route_plan = _ensure_route_plan(self.route_plan)
            if route_plan.routing_policy_version != self.routing_policy_version:
                raise ValueError("version de routage incohérente")
            if self.manual_review_reason is not None:
                raise ValueError("raison de revue manuelle interdite")
        if self.outcome is RoutePlanningOutcome.MANUAL_REVIEW:
            if self.route_plan is not None:
                raise ValueError("plan de route interdit en revue manuelle")
            _ensure_manual_review_reason(self.manual_review_reason)


class PageDiagnosticPolicy:
    """Politique de classification des signaux en états diagnostiques publiés."""

    def classify(
        self,
        page_number: PageNumber,
        signals: PageDiagnosticSignals,
        diagnostic_version: DiagnosticVersion,
        justification: str,
    ) -> PageDecision:
        parsed_page_number = _ensure_page_number(page_number)
        parsed_signals = _ensure_page_diagnostic_signals(signals)
        parsed_diagnostic_version = _ensure_diagnostic_version(diagnostic_version)
        parsed_justification = _ensure_diagnostic_justification(justification)

        if parsed_signals.corruption_state is PageCorruptionSignal.CORRUPT:
            page_state = PageDecisionState.UNSUPPORTED_OR_CORRUPT
        elif (
            parsed_signals.native_text_state
            in {NativeTextSignal.ABSENT, NativeTextSignal.SUSPECT}
            and parsed_signals.image_state is PageImageSignal.SCAN_CLEAN
            and parsed_signals.layout_complexity is LayoutComplexitySignal.COMPLEX
        ):
            page_state = PageDecisionState.SCAN_CLEAN
        elif parsed_signals.layout_complexity is LayoutComplexitySignal.COMPLEX:
            page_state = PageDecisionState.COMPLEX_VISUAL
        elif parsed_signals.image_state is PageImageSignal.SCAN_DEGRADED:
            page_state = PageDecisionState.SCAN_DEGRADED
        elif parsed_signals.existing_ocr_state is ExistingOcrSignal.BAD:
            page_state = PageDecisionState.OCR_BAD
        elif parsed_signals.mixed_content_detected:
            page_state = PageDecisionState.MIXED_CONTENT
        elif parsed_signals.image_state is PageImageSignal.SCAN_CLEAN:
            page_state = PageDecisionState.SCAN_CLEAN
        elif parsed_signals.native_text_state is NativeTextSignal.SUSPECT:
            page_state = PageDecisionState.NATIVE_SUSPECT
        elif parsed_signals.native_text_state is NativeTextSignal.RELIABLE:
            page_state = PageDecisionState.NATIVE_OK
        elif (
            parsed_signals.native_text_state is NativeTextSignal.ABSENT
            and parsed_signals.image_state is PageImageSignal.NONE
            and parsed_signals.existing_ocr_state is ExistingOcrSignal.NONE
        ):
            page_state = PageDecisionState.EMPTY
        else:
            raise ValueError("signaux diagnostiques insuffisants")

        return PageDecision(
            page_number=parsed_page_number,
            page_state=page_state,
            signals=parsed_signals,
            diagnostic_version=parsed_diagnostic_version,
            justification=parsed_justification,
        )


class PageRoutingPolicy:
    """Politique pure de choix d'une route documentaire à partir des diagnostics."""

    def manual_review_reason_for(
        self,
        page_decision: PageDecision,
        routing_configuration: PageRoutingConfiguration,
    ) -> str | None:
        return _manual_review_reason_for_page(
            page_decision=page_decision,
            routing_configuration=routing_configuration,
        )
    def decide_page_route(
        self,
        page_decision: PageDecision,
        routing_configuration: PageRoutingConfiguration,
    ) -> PageRoute:
        parsed_page_decision = _ensure_page_decision(page_decision)
        parsed_configuration = _ensure_routing_configuration(routing_configuration)
        manual_review_reason = _manual_review_reason_for_page(
            page_decision=parsed_page_decision,
            routing_configuration=parsed_configuration,
        )
        if manual_review_reason is not None:
            raise ValueError(manual_review_reason)

        resolution = parsed_page_decision.manual_review_resolution
        if resolution is not None:
            if resolution.decision is ManualReviewDecisionType.CONFIRM_EMPTY:
                route_name = PageRouteName.SKIP_EMPTY
            else:
                route_name = PageRouteName.from_value(resolution.route_name)
            confidence_score = 1.0
            preprocessing_action = _preprocessing_for_route(route_name)
            decision_mode = RouteDecisionMode.MANUAL
        else:
            route_name, confidence_score, preprocessing_action, requires_benchmark = (
                _routing_profile_for_state(parsed_page_decision.page_state)
            )
            decision_mode = _route_decision_mode(
                confidence_score=confidence_score,
                requires_benchmark=requires_benchmark,
                routing_configuration=parsed_configuration,
            )

        return PageRoute(
            page_number=parsed_page_decision.page_number,
            route_name=route_name,
            decision_mode=decision_mode,
            confidence_score=confidence_score,
            preprocessing_action=preprocessing_action,
            routing_policy_version=parsed_configuration.routing_policy_version,
            justification=_route_justification(
                page_decision=parsed_page_decision,
                route_name=route_name,
                decision_mode=decision_mode,
                confidence_score=confidence_score,
                preprocessing_action=preprocessing_action,
            ),
        )

    def plan_routes(
        self,
        page_decisions: Sequence[PageDecision],
        routing_configuration: PageRoutingConfiguration,
    ) -> RoutePlanningResult:
        parsed_page_decisions = _ensure_page_decisions(page_decisions)
        parsed_configuration = _ensure_routing_configuration(routing_configuration)
        manual_review_reasons = tuple(
            reason
            for reason in (
                _manual_review_reason_for_page(
                    page_decision=page_decision,
                    routing_configuration=parsed_configuration,
                )
                for page_decision in parsed_page_decisions
            )
            if reason is not None
        )
        if len(manual_review_reasons) != 0:
            return RoutePlanningResult.manual_review(
                routing_policy_version=parsed_configuration.routing_policy_version,
                reason="; ".join(manual_review_reasons),
            )

        page_routes = tuple(
            self.decide_page_route(
                page_decision=page_decision,
                routing_configuration=parsed_configuration,
            )
            for page_decision in parsed_page_decisions
        )
        dominant_route_name = _dominant_route_name(page_routes)
        if dominant_route_name is None:
            dominant_route_name = PageRouteName.MIXED_PAGEWISE
        page_exceptions = tuple(
            page_route
            for page_route in page_routes
            if page_route.route_name is not dominant_route_name
        )
        route_plan = RoutePlan(
            routing_policy_version=parsed_configuration.routing_policy_version,
            page_routes=page_routes,
            dominant_route_name=dominant_route_name,
            page_exceptions=page_exceptions,
            confidence_score=sum(
                page_route.confidence_score for page_route in page_routes
            )
            / len(page_routes),
        )
        return RoutePlanningResult.route_planned(route_plan)


@dataclass(frozen=True)
class DocumentProcessingStarted:
    """Événement produit lors du démarrage d'une tentative de traitement."""

    processing_run_id: ProcessingRunId
    document_id: DocumentId
    source_page_count: int

    def __post_init__(self) -> None:
        _ensure_processing_run_id(self.processing_run_id)
        _ensure_document_id(self.document_id)
        object.__setattr__(
            self,
            "source_page_count",
            _ensure_source_page_count(self.source_page_count),
        )


@dataclass(frozen=True)
class PageDiagnosticRecorded:
    """Événement produit pour chaque diagnostic de page enregistré."""

    processing_run_id: ProcessingRunId
    document_id: DocumentId
    page_number: PageNumber
    page_state: PageDecisionState
    diagnostic_version: DiagnosticVersion

    def __post_init__(self) -> None:
        _ensure_processing_run_id(self.processing_run_id)
        _ensure_document_id(self.document_id)
        _ensure_page_number(self.page_number)
        object.__setattr__(
            self,
            "page_state",
            PageDecisionState.from_value(self.page_state),
        )
        _ensure_diagnostic_version(self.diagnostic_version)


@dataclass(frozen=True)
class PageRouteDecided:
    """Événement produit pour chaque route de page décidée."""

    processing_run_id: ProcessingRunId
    document_id: DocumentId
    page_number: PageNumber
    route_name: PageRouteName
    decision_mode: RouteDecisionMode
    routing_policy_version: RoutingPolicyVersion

    def __post_init__(self) -> None:
        _ensure_processing_run_id(self.processing_run_id)
        _ensure_document_id(self.document_id)
        _ensure_page_number(self.page_number)
        object.__setattr__(self, "route_name", PageRouteName.from_value(self.route_name))
        object.__setattr__(
            self,
            "decision_mode",
            RouteDecisionMode.from_value(self.decision_mode),
        )
        if self.decision_mode is RouteDecisionMode.MANUAL_REVIEW:
            raise ValueError("route décidée en revue manuelle invalide")
        _ensure_routing_policy_version(self.routing_policy_version)


@dataclass(frozen=True)
class ManualReviewRequested:
    """Événement produit quand le routage automatique est explicitement refusé."""

    processing_run_id: ProcessingRunId
    document_id: DocumentId
    routing_policy_version: RoutingPolicyVersion
    reason: str

    def __post_init__(self) -> None:
        _ensure_processing_run_id(self.processing_run_id)
        _ensure_document_id(self.document_id)
        _ensure_routing_policy_version(self.routing_policy_version)
        object.__setattr__(self, "reason", _ensure_manual_review_reason(self.reason))


@dataclass(frozen=True)
class ManualReviewResolved:
    """Événement produit quand un réviseur résout explicitement une page."""

    processing_run_id: ProcessingRunId
    document_id: DocumentId
    page_number: PageNumber
    resolution: ManualReviewResolution

    def __post_init__(self) -> None:
        _ensure_processing_run_id(self.processing_run_id)
        _ensure_document_id(self.document_id)
        _ensure_page_number(self.page_number)
        if not isinstance(self.resolution, ManualReviewResolution):
            raise ValueError("résolution de revue manuelle invalide")


@dataclass(frozen=True)
class ProcessingRunQuarantined:
    """Événement produit quand une tentative est isolée avant publication aval."""

    processing_run_id: ProcessingRunId
    document_id: DocumentId
    routing_policy_version: RoutingPolicyVersion
    reason: str

    def __post_init__(self) -> None:
        _ensure_processing_run_id(self.processing_run_id)
        _ensure_document_id(self.document_id)
        _ensure_routing_policy_version(self.routing_policy_version)
        object.__setattr__(self, "reason", _ensure_manual_review_reason(self.reason))


@dataclass(frozen=True)
class ProcessingRunRejected:
    """Événement produit quand une tentative est rejetée explicitement."""

    processing_run_id: ProcessingRunId
    document_id: DocumentId
    routing_policy_version: RoutingPolicyVersion
    reason: str

    def __post_init__(self) -> None:
        _ensure_processing_run_id(self.processing_run_id)
        _ensure_document_id(self.document_id)
        _ensure_routing_policy_version(self.routing_policy_version)
        object.__setattr__(self, "reason", _ensure_manual_review_reason(self.reason))


@dataclass(frozen=True)
class ProcessingRunFailed:
    """Événement terminal quand le diagnostic technique échoue explicitement."""

    processing_run_id: ProcessingRunId
    document_id: DocumentId
    error_code: str

    def __post_init__(self) -> None:
        _ensure_processing_run_id(self.processing_run_id)
        _ensure_document_id(self.document_id)
        object.__setattr__(self, "error_code", _ensure_failure_error_code(self.error_code))


@dataclass(frozen=True)
class DocumentProcessingRun:
    """Agrégat SP qui porte une tentative de traitement d'un SourceDocument."""

    processing_run_id: ProcessingRunId
    document_id: DocumentId
    page_manifest: PageManifest
    page_decisions: tuple[PageDecision, ...]
    route_plan: RoutePlan | None
    manual_review_reason: str | None
    blocking_policy_version: RoutingPolicyVersion | None
    status: DocumentProcessingRunStatus
    aggregate_version: int
    events: tuple[
        DocumentProcessingStarted
        | PageDiagnosticRecorded
        | PageRouteDecided
        | ManualReviewRequested
        | ManualReviewResolved
        | ProcessingRunQuarantined
        | ProcessingRunRejected
        | ProcessingRunFailed,
        ...,
    ]
    failure_error_code: str | None = None

    @classmethod
    def start(
        cls,
        processing_run_id: ProcessingRunId,
        source_document: SourceDocument,
        page_manifest: PageManifest,
    ) -> "DocumentProcessingRun":
        parsed_processing_run_id = _ensure_processing_run_id(processing_run_id)
        parsed_source_document = _ensure_source_document(source_document)
        parsed_source_document.ensure_documentary_publication_allowed()
        parsed_manifest = _ensure_page_manifest(page_manifest)
        started_event = DocumentProcessingStarted(
            processing_run_id=parsed_processing_run_id,
            document_id=parsed_source_document.document_id,
            source_page_count=parsed_manifest.source_page_count,
        )
        return cls(
            processing_run_id=parsed_processing_run_id,
            document_id=parsed_source_document.document_id,
            page_manifest=parsed_manifest,
            page_decisions=(),
            route_plan=None,
            manual_review_reason=None,
            blocking_policy_version=None,
            status=DocumentProcessingRunStatus.MANIFEST_CREATED,
            aggregate_version=0,
            events=(started_event,),
        )

    @property
    def blocking_reason(self) -> str | None:
        """Justification bloquante conservée pour les états non publiables."""

        return self.failure_error_code or self.manual_review_reason

    def record_page_diagnostics(
        self,
        page_decisions: Sequence[PageDecision],
    ) -> "DocumentProcessingRun":
        if self.status not in (
            DocumentProcessingRunStatus.MANIFEST_CREATED,
            DocumentProcessingRunStatus.DIAGNOSING,
        ):
            raise ValueError("transition de diagnostic interdite")

        parsed_page_decisions = _ensure_page_decisions(page_decisions)
        _ensure_page_diagnostic_completeness(
            page_manifest=self.page_manifest,
            page_decisions=parsed_page_decisions,
        )
        diagnostic_events = tuple(
            PageDiagnosticRecorded(
                processing_run_id=self.processing_run_id,
                document_id=self.document_id,
                page_number=page_decision.page_number,
                page_state=page_decision.page_state,
                diagnostic_version=page_decision.diagnostic_version,
            )
            for page_decision in parsed_page_decisions
        )
        return DocumentProcessingRun(
            processing_run_id=self.processing_run_id,
            document_id=self.document_id,
            page_manifest=self.page_manifest,
            page_decisions=parsed_page_decisions,
            route_plan=None,
            manual_review_reason=None,
            blocking_policy_version=None,
            status=DocumentProcessingRunStatus.DIAGNOSED,
            aggregate_version=self.aggregate_version + 1,
            events=self.events + diagnostic_events,
        )

    def begin_diagnosis(self) -> "DocumentProcessingRun":
        """Publie l'exécution réelle avant toute inspection du PDF."""

        if self.status is not DocumentProcessingRunStatus.MANIFEST_CREATED:
            raise ValueError("transition d'exécution diagnostic interdite")
        return DocumentProcessingRun(
            processing_run_id=self.processing_run_id,
            document_id=self.document_id,
            page_manifest=self.page_manifest,
            page_decisions=(),
            route_plan=None,
            manual_review_reason=None,
            blocking_policy_version=None,
            status=DocumentProcessingRunStatus.DIAGNOSING,
            aggregate_version=self.aggregate_version + 1,
            events=self.events,
        )

    def decide_route_plan(
        self,
        routing_configuration: PageRoutingConfiguration,
    ) -> "DocumentProcessingRun":
        if self.status is not DocumentProcessingRunStatus.DIAGNOSED:
            raise ValueError("transition de routage interdite")

        parsed_configuration = _ensure_routing_configuration(routing_configuration)
        route_planning_result = PageRoutingPolicy().plan_routes(
            page_decisions=self.page_decisions,
            routing_configuration=parsed_configuration,
        )

        if route_planning_result.outcome is RoutePlanningOutcome.MANUAL_REVIEW:
            manual_review_event = ManualReviewRequested(
                processing_run_id=self.processing_run_id,
                document_id=self.document_id,
                routing_policy_version=route_planning_result.routing_policy_version,
                reason=_ensure_manual_review_reason(
                    route_planning_result.manual_review_reason
                ),
            )
            return DocumentProcessingRun(
                processing_run_id=self.processing_run_id,
                document_id=self.document_id,
                page_manifest=self.page_manifest,
                page_decisions=self.page_decisions,
                route_plan=None,
                manual_review_reason=manual_review_event.reason,
                blocking_policy_version=manual_review_event.routing_policy_version,
                status=DocumentProcessingRunStatus.MANUAL_REVIEW,
                aggregate_version=self.aggregate_version + 1,
                events=self.events + (manual_review_event,),
            )

        route_plan = _ensure_route_plan(route_planning_result.route_plan)
        route_events = tuple(
            PageRouteDecided(
                processing_run_id=self.processing_run_id,
                document_id=self.document_id,
                page_number=page_route.page_number,
                route_name=page_route.route_name,
                decision_mode=page_route.decision_mode,
                routing_policy_version=page_route.routing_policy_version,
            )
            for page_route in route_plan.page_routes
        )
        return DocumentProcessingRun(
            processing_run_id=self.processing_run_id,
            document_id=self.document_id,
            page_manifest=self.page_manifest,
            page_decisions=self.page_decisions,
            route_plan=route_plan,
            manual_review_reason=None,
            blocking_policy_version=None,
            status=DocumentProcessingRunStatus.ROUTE_PLANNED,
            aggregate_version=self.aggregate_version + 1,
            events=self.events + route_events,
        )

    def resolve_manual_review(
        self,
        *,
        page_number: PageNumber,
        resolution: ManualReviewResolution,
        routing_configuration: PageRoutingConfiguration,
    ) -> "DocumentProcessingRun":
        if self.status is not DocumentProcessingRunStatus.MANUAL_REVIEW:
            raise ValueError("transition de résolution manuelle interdite")
        parsed_page_number = _ensure_page_number(page_number)
        if not isinstance(resolution, ManualReviewResolution):
            raise ValueError("résolution de revue manuelle invalide")
        parsed_configuration = _ensure_routing_configuration(routing_configuration)
        if self.blocking_policy_version != parsed_configuration.routing_policy_version:
            raise ValueError("version de politique de revue incohérente")

        matching = tuple(
            decision
            for decision in self.page_decisions
            if decision.page_number == parsed_page_number
        )
        if len(matching) != 1:
            raise ValueError("page de revue manuelle absente")
        current = matching[0]
        if _manual_review_reason_for_page(current, parsed_configuration) is None:
            raise ValueError("page sans revue manuelle en attente")
        resolved_decision = current.resolve_manual_review(resolution)
        decisions = tuple(
            resolved_decision if decision.page_number == parsed_page_number else decision
            for decision in self.page_decisions
        )
        resolved_event = ManualReviewResolved(
            processing_run_id=self.processing_run_id,
            document_id=self.document_id,
            page_number=parsed_page_number,
            resolution=resolution,
        )
        planning = PageRoutingPolicy().plan_routes(
            page_decisions=decisions,
            routing_configuration=parsed_configuration,
        )
        if planning.outcome is RoutePlanningOutcome.MANUAL_REVIEW:
            requested_event = ManualReviewRequested(
                processing_run_id=self.processing_run_id,
                document_id=self.document_id,
                routing_policy_version=planning.routing_policy_version,
                reason=_ensure_manual_review_reason(planning.manual_review_reason),
            )
            return DocumentProcessingRun(
                processing_run_id=self.processing_run_id,
                document_id=self.document_id,
                page_manifest=self.page_manifest,
                page_decisions=decisions,
                route_plan=None,
                manual_review_reason=requested_event.reason,
                blocking_policy_version=requested_event.routing_policy_version,
                status=DocumentProcessingRunStatus.MANUAL_REVIEW,
                aggregate_version=self.aggregate_version + 1,
                events=self.events + (resolved_event, requested_event),
            )

        route_plan = _ensure_route_plan(planning.route_plan)
        route_events = tuple(
            PageRouteDecided(
                processing_run_id=self.processing_run_id,
                document_id=self.document_id,
                page_number=page_route.page_number,
                route_name=page_route.route_name,
                decision_mode=page_route.decision_mode,
                routing_policy_version=page_route.routing_policy_version,
            )
            for page_route in route_plan.page_routes
        )
        return DocumentProcessingRun(
            processing_run_id=self.processing_run_id,
            document_id=self.document_id,
            page_manifest=self.page_manifest,
            page_decisions=decisions,
            route_plan=route_plan,
            manual_review_reason=None,
            blocking_policy_version=None,
            status=DocumentProcessingRunStatus.ROUTE_PLANNED,
            aggregate_version=self.aggregate_version + 1,
            events=self.events + (resolved_event,) + route_events,
        )

    def quarantine(
        self,
        routing_policy_version: RoutingPolicyVersion,
        reason: str,
    ) -> "DocumentProcessingRun":
        if self.status not in (
            DocumentProcessingRunStatus.MANIFEST_CREATED,
            DocumentProcessingRunStatus.DIAGNOSED,
            DocumentProcessingRunStatus.MANUAL_REVIEW,
        ):
            raise ValueError("transition de quarantaine interdite")

        parsed_routing_policy_version = _ensure_routing_policy_version(
            routing_policy_version
        )
        parsed_reason = _ensure_manual_review_reason(reason)
        quarantined_event = ProcessingRunQuarantined(
            processing_run_id=self.processing_run_id,
            document_id=self.document_id,
            routing_policy_version=parsed_routing_policy_version,
            reason=parsed_reason,
        )
        return DocumentProcessingRun(
            processing_run_id=self.processing_run_id,
            document_id=self.document_id,
            page_manifest=self.page_manifest,
            page_decisions=self.page_decisions,
            route_plan=None,
            manual_review_reason=quarantined_event.reason,
            blocking_policy_version=quarantined_event.routing_policy_version,
            status=DocumentProcessingRunStatus.QUARANTINED,
            aggregate_version=self.aggregate_version + 1,
            events=self.events + (quarantined_event,),
        )

    def reject(
        self,
        routing_policy_version: RoutingPolicyVersion,
        reason: str,
    ) -> "DocumentProcessingRun":
        if self.status is not DocumentProcessingRunStatus.MANUAL_REVIEW:
            raise ValueError("transition de rejet interdite")

        parsed_routing_policy_version = _ensure_routing_policy_version(
            routing_policy_version
        )
        parsed_reason = _ensure_manual_review_reason(reason)
        rejected_event = ProcessingRunRejected(
            processing_run_id=self.processing_run_id,
            document_id=self.document_id,
            routing_policy_version=parsed_routing_policy_version,
            reason=parsed_reason,
        )
        return DocumentProcessingRun(
            processing_run_id=self.processing_run_id,
            document_id=self.document_id,
            page_manifest=self.page_manifest,
            page_decisions=self.page_decisions,
            route_plan=None,
            manual_review_reason=rejected_event.reason,
            blocking_policy_version=rejected_event.routing_policy_version,
            status=DocumentProcessingRunStatus.REJECTED,
            aggregate_version=self.aggregate_version + 1,
            events=self.events + (rejected_event,),
        )

    def fail(self, error_code: str) -> "DocumentProcessingRun":
        """Rend terminal et public un diagnostic impossible à terminer."""

        if self.status not in (
            DocumentProcessingRunStatus.MANIFEST_CREATED,
            DocumentProcessingRunStatus.DIAGNOSING,
            DocumentProcessingRunStatus.DIAGNOSED,
            DocumentProcessingRunStatus.MANUAL_REVIEW,
        ):
            raise ValueError("transition d'échec interdite")
        failed_event = ProcessingRunFailed(
            processing_run_id=self.processing_run_id,
            document_id=self.document_id,
            error_code=error_code,
        )
        return DocumentProcessingRun(
            processing_run_id=self.processing_run_id,
            document_id=self.document_id,
            page_manifest=self.page_manifest,
            page_decisions=self.page_decisions,
            route_plan=None,
            manual_review_reason=None,
            blocking_policy_version=None,
            status=DocumentProcessingRunStatus.FAILED,
            aggregate_version=self.aggregate_version + 1,
            events=self.events + (failed_event,),
            failure_error_code=failed_event.error_code,
        )

    def ensure_documentary_publication_allowed(self) -> None:
        if self.status is DocumentProcessingRunStatus.ROUTE_PLANNED:
            return

        if self.blocking_reason is None:
            raise ValueError(f"tentative M-003 non publiable: {self.status.value}")
        raise ValueError(
            f"tentative M-003 non publiable: {self.status.value}; "
            f"{self.blocking_reason}"
        )

    def __post_init__(self) -> None:
        _ensure_processing_run_id(self.processing_run_id)
        _ensure_document_id(self.document_id)
        _ensure_page_manifest(self.page_manifest)
        page_decisions = _ensure_page_decisions(self.page_decisions, allow_empty=True)
        route_plan = _ensure_route_plan_or_none(self.route_plan)
        manual_review_reason = _ensure_manual_review_reason_or_none(
            self.manual_review_reason
        )
        blocking_policy_version = _ensure_routing_policy_version_or_none(
            self.blocking_policy_version
        )
        failure_error_code = _ensure_failure_error_code_or_none(self.failure_error_code)
        if not isinstance(self.status, DocumentProcessingRunStatus):
            raise ValueError("document_processing_run_status invalide")
        if (
            isinstance(self.aggregate_version, bool)
            or not isinstance(self.aggregate_version, int)
            or self.aggregate_version < 0
        ):
            raise ValueError("aggregate_version invalide")
        if not isinstance(self.events, tuple):
            raise ValueError("events DocumentProcessingRun non tuple")
        if len(self.events) == 0:
            raise ValueError("events DocumentProcessingRun vide")
        for event in self.events:
            if not isinstance(
                event,
                (
                    DocumentProcessingStarted,
                    PageDiagnosticRecorded,
                    PageRouteDecided,
                    ManualReviewRequested,
                    ManualReviewResolved,
                    ProcessingRunQuarantined,
                    ProcessingRunRejected,
                    ProcessingRunFailed,
                ),
            ):
                raise ValueError("event DocumentProcessingRun invalide")
        if self.status in (
            DocumentProcessingRunStatus.MANIFEST_CREATED,
            DocumentProcessingRunStatus.DIAGNOSING,
        ) and len(page_decisions) != 0:
            raise ValueError("diagnostics interdits avant fin d'exécution")
        if self.status in (
            DocumentProcessingRunStatus.MANIFEST_CREATED,
            DocumentProcessingRunStatus.DIAGNOSING,
        ):
            if route_plan is not None or manual_review_reason is not None:
                raise ValueError("route interdite sur tentative créée")
            if blocking_policy_version is not None:
                raise ValueError("décision bloquante interdite sur tentative créée")
        if self.status is DocumentProcessingRunStatus.DIAGNOSED:
            _ensure_page_diagnostic_completeness(
                page_manifest=self.page_manifest,
                page_decisions=page_decisions,
            )
            if route_plan is not None or manual_review_reason is not None:
                raise ValueError("route interdite avant décision de routage")
            if blocking_policy_version is not None:
                raise ValueError("décision bloquante interdite avant routage")
        if self.status is DocumentProcessingRunStatus.ROUTE_PLANNED:
            _ensure_page_diagnostic_completeness(
                page_manifest=self.page_manifest,
                page_decisions=page_decisions,
            )
            _ensure_route_plan(route_plan)
            _ensure_route_plan_completeness(
                page_decisions=page_decisions,
                route_plan=route_plan,
            )
            if manual_review_reason is not None:
                raise ValueError("revue manuelle interdite sur plan approuvé")
            if blocking_policy_version is not None:
                raise ValueError("décision bloquante interdite sur plan approuvé")
        if self.status is DocumentProcessingRunStatus.MANUAL_REVIEW:
            _ensure_page_diagnostic_completeness(
                page_manifest=self.page_manifest,
                page_decisions=page_decisions,
            )
            if route_plan is not None:
                raise ValueError("plan de route interdit en revue manuelle")
            _ensure_manual_review_reason(manual_review_reason)
            _ensure_routing_policy_version(blocking_policy_version)
        if self.status in (
            DocumentProcessingRunStatus.QUARANTINED,
            DocumentProcessingRunStatus.REJECTED,
        ):
            if self.status is DocumentProcessingRunStatus.REJECTED or len(page_decisions) > 0:
                _ensure_page_diagnostic_completeness(
                    page_manifest=self.page_manifest,
                    page_decisions=page_decisions,
                )
            if route_plan is not None:
                raise ValueError("plan de route interdit sur tentative bloquée")
            _ensure_manual_review_reason(manual_review_reason)
            _ensure_routing_policy_version(blocking_policy_version)
        if self.status is DocumentProcessingRunStatus.FAILED:
            if route_plan is not None or manual_review_reason is not None:
                raise ValueError("route interdite sur tentative en échec")
            if blocking_policy_version is not None:
                raise ValueError("politique de routage interdite sur échec technique")
            _ensure_failure_error_code(failure_error_code)
            if not isinstance(self.events[-1], ProcessingRunFailed):
                raise ValueError("event d'échec absent")
        elif failure_error_code is not None:
            raise ValueError("failure_error_code interdit hors échec")
        object.__setattr__(self, "page_decisions", page_decisions)
        object.__setattr__(self, "route_plan", route_plan)
        object.__setattr__(self, "manual_review_reason", manual_review_reason)
        object.__setattr__(
            self,
            "blocking_policy_version",
            blocking_policy_version,
        )
        object.__setattr__(self, "failure_error_code", failure_error_code)


def _ensure_processing_run_id_value(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("processing_run_id invalide")
    if value.strip() == "":
        raise ValueError("processing_run_id invalide")
    if value != value.strip():
        raise ValueError("processing_run_id invalide")
    if _PROCESSING_RUN_ID_PATTERN.fullmatch(value) is None:
        raise ValueError("processing_run_id invalide")
    return value


def _ensure_page_number_value(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("page_number invalide")
    return value


def _ensure_source_page_count(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("nombre de pages source invalide")
    return value


def _ensure_diagnostic_version_value(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("version de diagnostic invalide")
    if value.strip() == "":
        raise ValueError("version de diagnostic invalide")
    if value != value.strip():
        raise ValueError("version de diagnostic invalide")
    return value


def _ensure_routing_policy_version_value(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("version de politique de routage invalide")
    if value.strip() == "":
        raise ValueError("version de politique de routage invalide")
    if value != value.strip():
        raise ValueError("version de politique de routage invalide")
    return value


def _ensure_diagnostic_justification(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("justification de diagnostic invalide")
    if value.strip() == "":
        raise ValueError("justification de diagnostic invalide")
    if value != value.strip():
        raise ValueError("justification de diagnostic invalide")
    return value


def _ensure_route_justification(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("justification de route invalide")
    if value.strip() == "":
        raise ValueError("justification de route invalide")
    if value != value.strip():
        raise ValueError("justification de route invalide")
    return value


def _ensure_manual_review_reason(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("raison de revue manuelle invalide")
    if value.strip() == "":
        raise ValueError("raison de revue manuelle invalide")
    if value != value.strip():
        raise ValueError("raison de revue manuelle invalide")
    return value


def _ensure_manual_review_actor(value: Any) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise ValueError("réviseur de revue manuelle invalide")
    if len(value) > 128:
        raise ValueError("réviseur de revue manuelle invalide")
    return value


def _ensure_manual_review_reason_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return _ensure_manual_review_reason(value)


def _ensure_failure_error_code(value: Any) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise ValueError("failure_error_code invalide")
    if value.upper() != value or not value.replace("_", "").isalnum():
        raise ValueError("failure_error_code invalide")
    return value


def _ensure_failure_error_code_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return _ensure_failure_error_code(value)


def _ensure_route_confidence_score(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("seuil de confiance de routage invalide")
    if value < 0.0 or value > 1.0:
        raise ValueError("seuil de confiance de routage invalide")
    return float(value)


def _ensure_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_manifest_entries(
    value: Sequence[PageManifestEntry],
) -> tuple[PageManifestEntry, ...]:
    if value is None:
        raise ValueError("entrées de manifeste absentes")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("entrées de manifeste invalides")
    entries = tuple(value)
    if len(entries) == 0:
        raise ValueError("entrées de manifeste vides")
    for entry in entries:
        if not isinstance(entry, PageManifestEntry):
            raise ValueError("entrée de manifeste invalide")
    return entries


def _ensure_manifest_completeness(
    source_page_count: int,
    entries: tuple[PageManifestEntry, ...],
) -> None:
    for entry in entries:
        if entry.page_number.value > source_page_count:
            raise ValueError("page_number hors plage")

    for index, entry in enumerate(entries, start=1):
        if entry.page_number.value != index:
            raise ValueError("ordre strict du manifeste invalide")

    if len(entries) != source_page_count:
        raise ValueError("nombre de pages du manifeste discordant")


def _ensure_page_decisions(
    value: Sequence[PageDecision],
    *,
    allow_empty: bool = False,
) -> tuple[PageDecision, ...]:
    if value is None:
        raise ValueError("diagnostics de pages absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("diagnostics de pages invalides")
    page_decisions = tuple(value)
    if len(page_decisions) == 0 and not allow_empty:
        raise ValueError("diagnostics de pages vides")
    for page_decision in page_decisions:
        if not isinstance(page_decision, PageDecision):
            raise ValueError("diagnostic de page invalide")
    return page_decisions


def _ensure_page_routes(
    value: Sequence[PageRoute],
    *,
    allow_empty: bool = False,
) -> tuple[PageRoute, ...]:
    if value is None:
        raise ValueError("routes de pages absentes")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("routes de pages invalides")
    page_routes = tuple(value)
    if len(page_routes) == 0 and not allow_empty:
        raise ValueError("routes de pages vides")
    for page_route in page_routes:
        if not isinstance(page_route, PageRoute):
            raise ValueError("route de page invalide")
    route_pages = tuple(page_route.page_number.value for page_route in page_routes)
    if len(route_pages) != len(set(route_pages)):
        raise ValueError("route de page dupliquée")
    return page_routes


def _ensure_page_diagnostic_completeness(
    page_manifest: PageManifest,
    page_decisions: tuple[PageDecision, ...],
) -> None:
    manifest_pages = tuple(entry.page_number.value for entry in page_manifest.entries)
    diagnostic_pages = tuple(
        page_decision.page_number.value for page_decision in page_decisions
    )
    diagnostic_page_set = set(diagnostic_pages)
    manifest_page_set = set(manifest_pages)

    if len(diagnostic_pages) != len(diagnostic_page_set):
        raise ValueError("diagnostic de page dupliqué")

    if not diagnostic_page_set.issubset(manifest_page_set):
        raise ValueError("diagnostic hors manifeste")

    if diagnostic_page_set != manifest_page_set:
        raise ValueError("diagnostic de page manquant")

    if diagnostic_pages != manifest_pages:
        raise ValueError("ordre strict des diagnostics invalide")


def _ensure_route_plan_completeness(
    page_decisions: tuple[PageDecision, ...],
    route_plan: RoutePlan,
) -> None:
    page_routes = _ensure_route_plan(route_plan).page_routes
    diagnostic_pages = tuple(
        page_decision.page_number.value for page_decision in page_decisions
    )
    route_pages = tuple(page_route.page_number.value for page_route in page_routes)

    if route_pages != diagnostic_pages:
        raise ValueError("ordre strict des routes invalide")


def _ensure_route_plan_exceptions(
    page_routes: tuple[PageRoute, ...],
    dominant_route_name: PageRouteName,
    page_exceptions: tuple[PageRoute, ...],
) -> None:
    expected_exceptions = tuple(
        page_route
        for page_route in page_routes
        if page_route.route_name is not dominant_route_name
    )
    if page_exceptions != expected_exceptions:
        raise ValueError("exceptions de route incohérentes")


def _ensure_page_route_preprocessing(
    route_name: PageRouteName,
    preprocessing_action: PagePreprocessingAction,
) -> None:
    if preprocessing_action is PagePreprocessingAction.OCR_PHYSICAL_PREPROCESSING:
        if route_name is not PageRouteName.PREPROCESS_GRANITE:
            raise ValueError("prétraitement OCRmyPDF inadmissible")
    if route_name is PageRouteName.PREPROCESS_GRANITE:
        if preprocessing_action is not PagePreprocessingAction.OCR_PHYSICAL_PREPROCESSING:
            raise ValueError("prétraitement OCRmyPDF requis")


def _preprocessing_for_route(route_name: PageRouteName) -> PagePreprocessingAction:
    parsed_route = PageRouteName.from_value(route_name)
    if parsed_route is PageRouteName.PREPROCESS_GRANITE:
        return PagePreprocessingAction.OCR_PHYSICAL_PREPROCESSING
    return PagePreprocessingAction.NONE


def _routing_profile_for_state(
    page_state: PageDecisionState,
) -> tuple[PageRouteName, float, PagePreprocessingAction, bool]:
    parsed_page_state = PageDecisionState.from_value(page_state)
    if parsed_page_state is PageDecisionState.NATIVE_OK:
        return (
            PageRouteName.NATIVE_STANDARD,
            0.98,
            PagePreprocessingAction.NONE,
            False,
        )
    if parsed_page_state is PageDecisionState.NATIVE_SUSPECT:
        return (
            PageRouteName.NATIVE_STANDARD,
            0.86,
            PagePreprocessingAction.NONE,
            True,
        )
    if parsed_page_state is PageDecisionState.SCAN_CLEAN:
        return (
            PageRouteName.SCAN_GRANITE,
            0.94,
            PagePreprocessingAction.NONE,
            False,
        )
    if parsed_page_state is PageDecisionState.SCAN_DEGRADED:
        return (
            PageRouteName.PREPROCESS_GRANITE,
            0.91,
            PagePreprocessingAction.OCR_PHYSICAL_PREPROCESSING,
            False,
        )
    if parsed_page_state is PageDecisionState.OCR_BAD:
        return (
            PageRouteName.BAD_OCR_TO_GRANITE,
            0.90,
            PagePreprocessingAction.NONE,
            False,
        )
    if parsed_page_state is PageDecisionState.MIXED_CONTENT:
        return (
            PageRouteName.MIXED_PAGEWISE,
            0.90,
            PagePreprocessingAction.NONE,
            False,
        )
    if parsed_page_state is PageDecisionState.COMPLEX_VISUAL:
        return (
            PageRouteName.TARGETED_ENRICHMENT,
            0.86,
            PagePreprocessingAction.NONE,
            True,
        )
    if parsed_page_state is PageDecisionState.EMPTY:
        return (
            PageRouteName.SKIP_EMPTY,
            1.0,
            PagePreprocessingAction.NONE,
            False,
        )
    raise ValueError("page sans route documentaire admissible")


def _manual_review_reason_for_page(
    page_decision: PageDecision,
    routing_configuration: PageRoutingConfiguration,
) -> str | None:
    parsed_page_decision = _ensure_page_decision(page_decision)
    parsed_configuration = _ensure_routing_configuration(routing_configuration)

    if parsed_page_decision.manual_review_resolution is not None:
        return None

    if parsed_page_decision.page_state is PageDecisionState.UNSUPPORTED_OR_CORRUPT:
        return (
            f"page {parsed_page_decision.page_number.value} "
            "sans route documentaire admissible"
        )

    route_name, confidence_score, _, _ = _routing_profile_for_state(
        parsed_page_decision.page_state
    )
    if confidence_score < parsed_configuration.benchmark_confidence_min:
        return (
            f"page {parsed_page_decision.page_number.value} "
            f"score de confiance {confidence_score:.2f} inférieur au seuil "
            f"de benchmark {parsed_configuration.benchmark_confidence_min:.2f} "
            f"pour {route_name.value}"
        )

    return None


def _route_decision_mode(
    confidence_score: float,
    requires_benchmark: bool,
    routing_configuration: PageRoutingConfiguration,
) -> RouteDecisionMode:
    _ensure_route_confidence_score(confidence_score)
    _ensure_bool(requires_benchmark, "requires_benchmark")
    parsed_configuration = _ensure_routing_configuration(routing_configuration)
    if requires_benchmark:
        return RouteDecisionMode.BENCHMARK
    if confidence_score < parsed_configuration.auto_confidence_min:
        return RouteDecisionMode.BENCHMARK
    return RouteDecisionMode.AUTO


def _route_justification(
    page_decision: PageDecision,
    route_name: PageRouteName,
    decision_mode: RouteDecisionMode,
    confidence_score: float,
    preprocessing_action: PagePreprocessingAction,
) -> str:
    parsed_page_decision = _ensure_page_decision(page_decision)
    parsed_route_name = PageRouteName.from_value(route_name)
    parsed_decision_mode = RouteDecisionMode.from_value(decision_mode)
    parsed_preprocessing_action = PagePreprocessingAction.from_value(
        preprocessing_action
    )
    _ensure_route_confidence_score(confidence_score)
    resolution = parsed_page_decision.manual_review_resolution
    if resolution is not None:
        return (
            f"{resolution.decision.value} -> {parsed_route_name.value} "
            f"par {resolution.reviewer_id}; motif: {resolution.reason}"
        )
    if parsed_preprocessing_action is PagePreprocessingAction.OCR_PHYSICAL_PREPROCESSING:
        preprocessing_label = "prétraitement OCRmyPDF conditionnel"
    else:
        preprocessing_label = "sans prétraitement"
    return (
        f"{parsed_page_decision.page_state.value} -> {parsed_route_name.value} "
        f"en {parsed_decision_mode.value}; score {confidence_score:.2f}; "
        f"{preprocessing_label}; diagnostic: {parsed_page_decision.justification}"
    )


def _dominant_route_name(page_routes: tuple[PageRoute, ...]) -> PageRouteName | None:
    parsed_page_routes = _ensure_page_routes(page_routes)
    route_counts: dict[PageRouteName, int] = {}
    for page_route in parsed_page_routes:
        if page_route.route_name is PageRouteName.SKIP_EMPTY:
            continue
        route_counts[page_route.route_name] = route_counts.get(page_route.route_name, 0) + 1

    if len(route_counts) == 0:
        return None

    highest_count = max(route_counts.values())
    dominant_candidates = tuple(
        route_name
        for route_name, route_count in route_counts.items()
        if route_count == highest_count
    )
    if len(dominant_candidates) != 1:
        return None
    return dominant_candidates[0]


def _ensure_processing_run_id(value: ProcessingRunId) -> ProcessingRunId:
    if not isinstance(value, ProcessingRunId):
        raise ValueError("processing_run_id invalide")
    return value


def _ensure_page_number(value: PageNumber) -> PageNumber:
    if not isinstance(value, PageNumber):
        raise ValueError("page_number invalide")
    return value


def _ensure_document_id(value: DocumentId) -> DocumentId:
    if not isinstance(value, DocumentId):
        raise ValueError("document_id invalide")
    return value


def _ensure_page_manifest(value: PageManifest) -> PageManifest:
    if not isinstance(value, PageManifest):
        raise ValueError("page_manifest invalide")
    return value


def _ensure_diagnostic_version(value: DiagnosticVersion) -> DiagnosticVersion:
    if not isinstance(value, DiagnosticVersion):
        raise ValueError("version de diagnostic invalide")
    return value


def _ensure_routing_policy_version(
    value: RoutingPolicyVersion,
) -> RoutingPolicyVersion:
    if not isinstance(value, RoutingPolicyVersion):
        raise ValueError("version de politique de routage invalide")
    return value


def _ensure_routing_policy_version_or_none(
    value: RoutingPolicyVersion | None,
) -> RoutingPolicyVersion | None:
    if value is None:
        return None
    return _ensure_routing_policy_version(value)


def _ensure_routing_configuration(
    value: PageRoutingConfiguration,
) -> PageRoutingConfiguration:
    if not isinstance(value, PageRoutingConfiguration):
        raise ValueError("configuration de routage invalide")
    return value


def _ensure_page_diagnostic_signals(
    value: PageDiagnosticSignals,
) -> PageDiagnosticSignals:
    if not isinstance(value, PageDiagnosticSignals):
        raise ValueError("signaux diagnostiques invalides")
    return value


def _ensure_page_decision(value: PageDecision) -> PageDecision:
    if not isinstance(value, PageDecision):
        raise ValueError("diagnostic de page invalide")
    return value


def _ensure_route_plan(value: RoutePlan | None) -> RoutePlan:
    if not isinstance(value, RoutePlan):
        raise ValueError("plan de routage invalide")
    return value


def _ensure_route_plan_or_none(value: RoutePlan | None) -> RoutePlan | None:
    if value is None:
        return None
    return _ensure_route_plan(value)


def _ensure_source_document(value: SourceDocument) -> SourceDocument:
    if not isinstance(value, SourceDocument):
        raise ValueError("source_document invalide")
    return value


__all__ = [
    "DiagnosticVersion",
    "DocumentProcessingRun",
    "DocumentProcessingRunStatus",
    "DocumentProcessingStarted",
    "ExistingOcrSignal",
    "LayoutComplexitySignal",
    "ManualReviewDecisionType",
    "ManualReviewRequested",
    "ManualReviewResolution",
    "ManualReviewResolved",
    "NativeTextSignal",
    "PagePreprocessingAction",
    "PageCorruptionSignal",
    "PageDecision",
    "PageDecisionState",
    "PageDiagnosticPolicy",
    "PageDiagnosticRecorded",
    "PageDiagnosticSignals",
    "PageImageSignal",
    "PageManifest",
    "PageManifestEntry",
    "PageManifestEntryState",
    "PageNumber",
    "PageRoute",
    "PageRouteDecided",
    "PageRouteName",
    "PageRoutingConfiguration",
    "PageRoutingPolicy",
    "ProcessingRunQuarantined",
    "ProcessingRunRejected",
    "ProcessingRunId",
    "RouteDecisionMode",
    "RoutePlan",
    "RoutePlanningOutcome",
    "RoutePlanningResult",
    "RoutingPolicyVersion",
]
