"""Decisions de calibration et promotion M-012."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from app.evaluation.domain.document_route_benchmark import REQUIRED_ROUTE_METRICS
from app.evaluation.domain.knowledge_search_benchmark import REQUIRED_KNOWLEDGE_SEARCH_METRICS
from app.evaluation.domain.llm_real_path_benchmark import REQUIRED_LLM_TASKS
from app.evaluation.domain.strategy_backtest_benchmark import REQUIRED_EX_METRICS, REQUIRED_SD_METRICS
from app.evaluation.domain.verified_answer_benchmark import (
    REQUIRED_EVIDENCE_GOVERNANCE_METRICS,
    REQUIRED_VERIFIED_ANSWER_METRICS,
)


ACCEPTED = "ACCEPTED"
REJECTED = "REJECTED"
DEFERRED = "DEFERRED"
SCIENTIFIC_GREEN = "GREEN"
SCIENTIFIC_RED = "SCIENTIFIC_RED"
THRESHOLD_MINIMUM = "MINIMUM"
THRESHOLD_MAXIMUM = "MAXIMUM"

CONTEXT_SP = "SP"
CONTEXT_KA = "KA"
CONTEXT_EG = "EG"
CONTEXT_RA = "RA"
CONTEXT_CV = "CV"
CONTEXT_SD = "SD"
CONTEXT_LLM = "LLM"
CONTEXT_EX = "EX"

POLICY_VERSION_M012 = "CalibrationDecisionPolicy-M012-1.0"

CONVERSATION_CREATION_CRITERION = "conversation_creation_criterion"
CONVERSATION_FOLLOW_UP_RESOLUTION_RATE = "conversation_follow_up_resolution_rate"
CONVERSATION_MODE_ROUTING_JUSTIFIED_RATE = "conversation_mode_routing_justified_rate"
CONVERSATION_RAW_HISTORY_FACT_USAGE_REJECTION_TOTAL = "conversation_raw_history_fact_usage_rejection_total"
REQUIRED_CONVERSATION_CRITERIA = frozenset(
    {
        CONVERSATION_CREATION_CRITERION,
        CONVERSATION_FOLLOW_UP_RESOLUTION_RATE,
        CONVERSATION_MODE_ROUTING_JUSTIFIED_RATE,
        CONVERSATION_RAW_HISTORY_FACT_USAGE_REJECTION_TOTAL,
    }
)

EG_VERDICT_DISTRIBUTION = "evidence_verdict_distribution"
EG_DEPENDENCY_GROUP_COUNT = "evidence_dependency_group_count"
REQUIRED_EG_DECISION_METRICS = frozenset(REQUIRED_EVIDENCE_GOVERNANCE_METRICS).union(
    {EG_VERDICT_DISTRIBUTION, EG_DEPENDENCY_GROUP_COUNT}
)

_EXPECTED_CONTEXTS = frozenset({CONTEXT_SP, CONTEXT_KA, CONTEXT_EG, CONTEXT_RA, CONTEXT_CV, CONTEXT_SD, CONTEXT_LLM, CONTEXT_EX})
_EXPECTED_DECISION_STATUSES = frozenset({ACCEPTED, REJECTED, DEFERRED})
_EXPECTED_VERDICT_STATUSES = frozenset({SCIENTIFIC_GREEN, SCIENTIFIC_RED})
_EXPECTED_THRESHOLD_OPERATORS = frozenset({THRESHOLD_MINIMUM, THRESHOLD_MAXIMUM})
_EXPECTED_SOFTWARE_GATE_STATUSES = frozenset({"GREEN", "RED"})
_OBSOLETE_REFERENCE_FRAGMENTS = ("/current", "/latest", ":latest", "current", "latest")


@dataclass(frozen=True)
class BenchmarkSourceLink:
    benchmark_id: str
    context: str
    artifact_path: str
    policy_version: str
    metric_names: tuple[str, ...]

    def __init__(
        self,
        *,
        benchmark_id: str,
        context: str,
        artifact_path: str,
        policy_version: str,
        metric_names: Sequence[str],
    ) -> None:
        object.__setattr__(self, "benchmark_id", _required_text(benchmark_id, "benchmark source requis"))
        object.__setattr__(self, "context", _required_context(context))
        parsed_path = _required_text(artifact_path, "artifact_path")
        _ensure_not_obsolete(parsed_path)
        object.__setattr__(self, "artifact_path", parsed_path)
        parsed_policy = _required_text(policy_version, "policy_version")
        _ensure_not_obsolete(parsed_policy)
        object.__setattr__(self, "policy_version", parsed_policy)
        object.__setattr__(self, "metric_names", _required_text_tuple(metric_names, "metrique critique absente"))


@dataclass(frozen=True)
class CalibrationThreshold:
    threshold_id: str
    metric_name: str
    operator: str
    value: str
    policy_version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "threshold_id", _required_text(self.threshold_id, "threshold_id"))
        object.__setattr__(self, "metric_name", _required_text(self.metric_name, "metric_name"))
        object.__setattr__(self, "operator", _required_status(self.operator, _EXPECTED_THRESHOLD_OPERATORS, "operateur de seuil"))
        object.__setattr__(self, "value", _required_decimal_text(self.value, "valeur de seuil invalide"))
        object.__setattr__(self, "policy_version", _required_policy_version(self.policy_version))


@dataclass(frozen=True)
class ContextDecisionCriteria:
    criterion_id: str
    policy_version: str
    status: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "criterion_id", _required_text(self.criterion_id, "criterion_id"))
        object.__setattr__(self, "policy_version", _required_policy_version(self.policy_version))
        object.__setattr__(self, "status", _required_status(self.status, _EXPECTED_DECISION_STATUSES, "statut critere"))


@dataclass(frozen=True)
class ScientificGateVerdict:
    verdict_id: str
    status: str
    metric_name: str
    benchmark_source_id: str
    software_gate_status: str
    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "verdict_id", _required_text(self.verdict_id, "verdict_id"))
        object.__setattr__(self, "status", _required_status(self.status, _EXPECTED_VERDICT_STATUSES, "statut verdict"))
        object.__setattr__(self, "metric_name", _required_text(self.metric_name, "metric_name"))
        object.__setattr__(self, "benchmark_source_id", _required_text(self.benchmark_source_id, "benchmark_source_id"))
        object.__setattr__(
            self,
            "software_gate_status",
            _required_status(self.software_gate_status, _EXPECTED_SOFTWARE_GATE_STATUSES, "statut gate logiciel"),
        )
        object.__setattr__(self, "reason", _required_text(self.reason, "reason"))


@dataclass(frozen=True)
class PromotionDecision:
    decision_id: str
    policy_version: str
    context: str
    status: str
    benchmark_sources: tuple[BenchmarkSourceLink, ...]
    thresholds: tuple[CalibrationThreshold, ...]
    criteria: tuple[ContextDecisionCriteria, ...]
    scientific_verdicts: tuple[ScientificGateVerdict, ...]
    adr_refs: tuple[str, ...]
    v1_gap_refs: tuple[str, ...]
    justification: str
    compared_llm_tasks: tuple[str, ...]

    def __init__(
        self,
        *,
        decision_id: str,
        policy_version: str,
        context: str,
        status: str,
        benchmark_sources: Sequence[BenchmarkSourceLink],
        thresholds: Sequence[CalibrationThreshold],
        criteria: Sequence[ContextDecisionCriteria],
        scientific_verdicts: Sequence[ScientificGateVerdict],
        adr_refs: Sequence[str],
        v1_gap_refs: Sequence[str],
        justification: str,
        compared_llm_tasks: Sequence[str] = (),
    ) -> None:
        parsed_policy_version = _required_policy_version(policy_version)
        parsed_context = _required_context(context)
        parsed_status = _required_status(status, _EXPECTED_DECISION_STATUSES, "statut decision")
        sources = _required_source_tuple(benchmark_sources)
        thresholds_tuple = _typed_tuple(thresholds, CalibrationThreshold, "CalibrationThreshold requis")
        criteria_tuple = _typed_tuple(criteria, ContextDecisionCriteria, "ContextDecisionCriteria requis")
        verdicts = _typed_tuple(scientific_verdicts, ScientificGateVerdict, "ScientificGateVerdict requis")
        adr_tuple = _required_text_tuple(adr_refs, "decision structurante sans ADR")
        v1_gaps = _text_tuple(v1_gap_refs, "v1_gap_refs")
        llm_tasks = _text_tuple(compared_llm_tasks, "compared_llm_tasks")

        for source in sources:
            if source.context != parsed_context:
                raise ValueError("benchmark source incoherent")
        for threshold in thresholds_tuple:
            if threshold.policy_version != parsed_policy_version:
                raise ValueError("version de politique incoherente")
            if threshold.metric_name not in _benchmark_metric_names(sources):
                raise ValueError("seuil sans benchmark source")
        for criterion in criteria_tuple:
            if criterion.policy_version != parsed_policy_version:
                raise ValueError("version de politique incoherente")
        for verdict in verdicts:
            if verdict.benchmark_source_id not in {source.benchmark_id for source in sources}:
                raise ValueError("verdict sans benchmark source")
            if verdict.metric_name not in _benchmark_metric_names(sources).union(_criteria_names(criteria_tuple)):
                raise ValueError("verdict sans metrique source")
        if parsed_status == ACCEPTED:
            if len(verdicts) == 0:
                raise ValueError("decision favorable avec metrique critique absente")
            if any(verdict.status == SCIENTIFIC_RED for verdict in verdicts):
                raise ValueError("decision favorable avec test scientifique RED")

        object.__setattr__(self, "decision_id", _required_text(decision_id, "decision_id"))
        object.__setattr__(self, "policy_version", parsed_policy_version)
        object.__setattr__(self, "context", parsed_context)
        object.__setattr__(self, "status", parsed_status)
        object.__setattr__(self, "benchmark_sources", sources)
        object.__setattr__(self, "thresholds", thresholds_tuple)
        object.__setattr__(self, "criteria", criteria_tuple)
        object.__setattr__(self, "scientific_verdicts", verdicts)
        object.__setattr__(self, "adr_refs", adr_tuple)
        object.__setattr__(self, "v1_gap_refs", v1_gaps)
        object.__setattr__(self, "justification", _required_text(justification, "justification"))
        object.__setattr__(self, "compared_llm_tasks", llm_tasks)


@dataclass(frozen=True)
class CalibrationDecisionRegister:
    register_id: str
    policy_version: str
    decisions: tuple[PromotionDecision, ...]
    decisions_by_context: Mapping[str, PromotionDecision]
    statuses_by_decision_id: Mapping[str, str]


@dataclass(frozen=True)
class CalibrationDecisionPolicy:
    policy_version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_version", _required_policy_version(self.policy_version))

    @property
    def required_llm_tasks(self) -> tuple[str, ...]:
        return REQUIRED_LLM_TASKS

    def publish_register(self, *, register_id: str, decisions: Sequence[PromotionDecision]) -> CalibrationDecisionRegister:
        parsed_register_id = _required_text(register_id, "register_id")
        parsed_decisions = _required_decision_tuple(decisions)
        decisions_by_context: dict[str, PromotionDecision] = {}
        statuses_by_decision_id: dict[str, str] = {}
        seen_decision_ids: set[str] = set()

        for decision in parsed_decisions:
            if decision.policy_version != self.policy_version:
                raise ValueError("version de politique incoherente")
            if decision.decision_id in seen_decision_ids:
                raise ValueError("conflit de decisions")
            seen_decision_ids.add(decision.decision_id)
            if decision.context in decisions_by_context:
                raise ValueError("conflit de decisions")
            decisions_by_context[decision.context] = decision
            statuses_by_decision_id[decision.decision_id] = decision.status
            if decision.status == ACCEPTED:
                self._validate_favorable_decision(decision)

        return CalibrationDecisionRegister(
            register_id=parsed_register_id,
            policy_version=self.policy_version,
            decisions=parsed_decisions,
            decisions_by_context=decisions_by_context,
            statuses_by_decision_id=statuses_by_decision_id,
        )

    def validate_register(self, register: CalibrationDecisionRegister) -> None:
        if not isinstance(register, CalibrationDecisionRegister):
            raise ValueError("CalibrationDecisionRegister requis")
        if register.policy_version != self.policy_version:
            raise ValueError("version de politique incoherente")
        missing_contexts = sorted(_EXPECTED_CONTEXTS.difference(register.decisions_by_context.keys()))
        if missing_contexts:
            raise ValueError("decision M-012 absente: " + ", ".join(missing_contexts))
        for decision in register.decisions:
            if decision.status == ACCEPTED:
                self._validate_favorable_decision(decision)
        if not any(decision.status == REJECTED for decision in register.decisions):
            raise ValueError("refus absent du registre")
        if not any(decision.status == DEFERRED for decision in register.decisions):
            raise ValueError("report absent du registre")
        if not any(verdict.status == SCIENTIFIC_RED for decision in register.decisions for verdict in decision.scientific_verdicts):
            raise ValueError("test scientifique RED absent")

    def render_markdown_report(self, register: CalibrationDecisionRegister) -> str:
        if not isinstance(register, CalibrationDecisionRegister):
            raise ValueError("CalibrationDecisionRegister requis")
        if register.policy_version != self.policy_version:
            raise ValueError("version de politique incoherente")
        if len(register.decisions) == 0:
            raise ValueError("decision absente")
        lines = [
            "# Rapport T-011 - Decisions de calibration et promotion M-012",
            "",
            "## Scenario BDD",
            "",
            "- Given les benchmarks M-012 sont termines et publies comme artefacts sources.",
            "- When les decisions de calibration et promotion sont publiees.",
            "- Then les acceptations, refus et reports restent versionnes avec benchmark, ADR et ecart V1.",
            "",
            "## Decisions publiees",
            "",
            "| Decision | Contexte | Statut | Benchmarks | ADR | Ecarts V1 |",
            "|---|---|---|---|---|---|",
        ]
        for decision in register.decisions:
            benchmarks = ", ".join(source.benchmark_id for source in decision.benchmark_sources)
            adr_refs = ", ".join(decision.adr_refs)
            gaps = ", ".join(decision.v1_gap_refs) if decision.v1_gap_refs else "Aucun"
            lines.append(f"| `{decision.decision_id}` | {decision.context} | {decision.status} | {benchmarks} | {adr_refs} | {gaps} |")

        red_verdicts = [
            verdict
            for decision in register.decisions
            for verdict in decision.scientific_verdicts
            if verdict.status == SCIENTIFIC_RED
        ]
        lines.extend(
            [
                "",
                "## Tests scientifiques",
                "",
                "Un Test scientifique RED reste publie meme quand le gate logiciel GREEN valide le code.",
            ]
        )
        for verdict in red_verdicts:
            lines.append(
                f"- Test scientifique RED `{verdict.metric_name}` depuis `{verdict.benchmark_source_id}`: "
                f"{verdict.reason}; gate logiciel {verdict.software_gate_status}."
            )

        lines.extend(
            [
                "",
                "## ADR",
                "",
                "ADR: non requise; T-011 applique ADR-010 et DDD-ADR-010 sans changer leur sens.",
                "",
            ]
        )
        return "\n".join(lines)

    def _validate_favorable_decision(self, decision: PromotionDecision) -> None:
        metric_names = _benchmark_metric_names(decision.benchmark_sources)
        criteria_names = _criteria_names(decision.criteria)
        if decision.context == CONTEXT_SP:
            _ensure_required_names(metric_names, REQUIRED_ROUTE_METRICS, "metrique SP obligatoire absente")
        elif decision.context == CONTEXT_KA:
            _ensure_required_names(metric_names, REQUIRED_KNOWLEDGE_SEARCH_METRICS, "metrique KA obligatoire absente")
        elif decision.context == CONTEXT_EG:
            _ensure_required_names(metric_names, REQUIRED_EG_DECISION_METRICS, "metrique EG obligatoire absente")
        elif decision.context == CONTEXT_RA:
            _ensure_required_names(metric_names, REQUIRED_VERIFIED_ANSWER_METRICS, "metrique RA obligatoire absente")
        elif decision.context == CONTEXT_CV:
            _ensure_required_names(criteria_names, REQUIRED_CONVERSATION_CRITERIA, "critere CV obligatoire absent")
        elif decision.context == CONTEXT_SD:
            _ensure_required_names(metric_names, REQUIRED_SD_METRICS, "metrique SD obligatoire absente")
        elif decision.context == CONTEXT_LLM:
            _ensure_required_names(set(decision.compared_llm_tasks), REQUIRED_LLM_TASKS, "tache LLM obligatoire absente")
        elif decision.context == CONTEXT_EX:
            _ensure_required_names(metric_names, REQUIRED_EX_METRICS, "metrique EX obligatoire absente")


def build_m012_calibration_decision_register() -> CalibrationDecisionRegister:
    policy = CalibrationDecisionPolicy(policy_version=POLICY_VERSION_M012)
    return policy.publish_register(
        register_id="REG-M012-CALIBRATION-PROMOTION-0001",
        decisions=(
            _decision(
                decision_id="DEC-M012-SP-DEFERRED",
                context=CONTEXT_SP,
                status=DEFERRED,
                benchmark_id="RBRUN-M012-DOCUMENT-ROUTES-0001",
                artifact_path="docs/evaluation/m012/document_quality_calibration_report.md",
                metric_names=tuple(sorted(REQUIRED_ROUTE_METRICS)),
                threshold_metric_names=("document_cell_accuracy", "document_formula_fidelity"),
                red_metric_name="document_cell_accuracy",
                v1_gap_refs=("V1-GAP-M012-SP-CELL-QUALITY",),
                justification="Qualite cellules sous seuil pilote sur une route; promotion differee.",
            ),
            _decision(
                decision_id="DEC-M012-KA-REJECTED",
                context=CONTEXT_KA,
                status=REJECTED,
                benchmark_id="KSRUN-M012-KNOWLEDGE-0001",
                artifact_path="docs/evaluation/m012/knowledge_search_benchmark_report.md",
                metric_names=tuple(sorted(REQUIRED_KNOWLEDGE_SEARCH_METRICS)),
                threshold_metric_names=("knowledge_recall_at_10", "knowledge_mrr"),
                red_metric_name="knowledge_recall_at_10",
                v1_gap_refs=("V1-GAP-M012-KA-RECALL",),
                justification="Recall@10 pilote insuffisant pour promotion V1.",
            ),
            _decision(
                decision_id="DEC-M012-EG-ACCEPTED",
                context=CONTEXT_EG,
                status=ACCEPTED,
                benchmark_id="EGRUN-M012-0001",
                artifact_path="docs/evaluation/m012/evidence_governance_benchmark_report.md",
                metric_names=tuple(sorted(REQUIRED_EG_DECISION_METRICS)),
                threshold_metric_names=("evidence_claim_verified_rate", "evidence_claim_rejected_rate"),
                red_metric_name=None,
                v1_gap_refs=(),
                justification="Gouvernance des preuves acceptee avec distributions conservees.",
            ),
            _decision(
                decision_id="DEC-M012-RA-DEFERRED",
                context=CONTEXT_RA,
                status=DEFERRED,
                benchmark_id="VARUN-M012-VERIFIED-ANSWERS-0001",
                artifact_path="docs/evaluation/m012/verified_answer_benchmark_report.md",
                metric_names=tuple(sorted(REQUIRED_VERIFIED_ANSWER_METRICS)),
                threshold_metric_names=("answer_citation_precision", "answer_correct_abstention_rate"),
                red_metric_name="answer_correct_abstention_rate",
                v1_gap_refs=("V1-GAP-M012-RA-ABSTENTION",),
                justification="Abstention correcte a renforcer avant promotion V1.",
            ),
            _decision(
                decision_id="DEC-M012-CV-ACCEPTED",
                context=CONTEXT_CV,
                status=ACCEPTED,
                benchmark_id="CVRUN-M012-CRITERIA-0001",
                artifact_path="docs/evaluation/m012/verified_answer_benchmark_report.md",
                metric_names=tuple(sorted(REQUIRED_CONVERSATION_CRITERIA)),
                threshold_metric_names=(),
                red_metric_name=None,
                v1_gap_refs=(),
                justification="Criteres conversationnels V1 retenus comme criteres de promotion.",
                criteria=tuple(
                    ContextDecisionCriteria(criterion_id, POLICY_VERSION_M012, ACCEPTED)
                    for criterion_id in sorted(REQUIRED_CONVERSATION_CRITERIA)
                ),
            ),
            _decision(
                decision_id="DEC-M012-SD-REJECTED",
                context=CONTEXT_SD,
                status=REJECTED,
                benchmark_id="SBRUN-M012-STRATEGY-BACKTEST-0001",
                artifact_path="docs/evaluation/m012/strategy_backtest_benchmark_report.md",
                metric_names=tuple(sorted(REQUIRED_SD_METRICS)),
                threshold_metric_names=("strategy_compilable_rate", "strategy_parameter_without_calibration_plan_total"),
                red_metric_name="strategy_parameter_without_calibration_plan_total",
                v1_gap_refs=("V1-GAP-M012-SD-CALIBRATION-PLAN",),
                justification="Parametres sans plan de calibration conserves comme refus pilote.",
            ),
            _decision(
                decision_id="DEC-M012-LLM-REJECTED",
                context=CONTEXT_LLM,
                status=REJECTED,
                benchmark_id="LLMRUN-M012-REAL-PATH-0001",
                artifact_path="docs/evaluation/m012/llm_real_path_benchmark_report.md",
                metric_names=REQUIRED_LLM_TASKS,
                threshold_metric_names=(),
                red_metric_name="exactitude_nombres",
                v1_gap_refs=("V1-GAP-M012-LLM-COMMUNITY-PROMOTION",),
                justification="Checkpoint communautaire refuse car une tache obligatoire reste inferieure aux references.",
                criteria=tuple(ContextDecisionCriteria(task_name, POLICY_VERSION_M012, REJECTED) for task_name in REQUIRED_LLM_TASKS),
                compared_llm_tasks=REQUIRED_LLM_TASKS,
            ),
            _decision(
                decision_id="DEC-M012-EX-ACCEPTED",
                context=CONTEXT_EX,
                status=ACCEPTED,
                benchmark_id="SBRUN-M012-EXPERIMENTS-0001",
                artifact_path="docs/evaluation/m012/strategy_backtest_benchmark_report.md",
                metric_names=tuple(sorted(REQUIRED_EX_METRICS)),
                threshold_metric_names=("experiment_reproducible_rate", "negative_experiment_retention_ratio"),
                red_metric_name=None,
                v1_gap_refs=(),
                justification="Mesures EX publiees avec resultats negatifs et couts visibles.",
            ),
        ),
    )


def _decision(
    *,
    decision_id: str,
    context: str,
    status: str,
    benchmark_id: str,
    artifact_path: str,
    metric_names: Sequence[str],
    threshold_metric_names: Sequence[str],
    red_metric_name: str | None,
    v1_gap_refs: Sequence[str],
    justification: str,
    criteria: Sequence[ContextDecisionCriteria] = (),
    compared_llm_tasks: Sequence[str] = (),
) -> PromotionDecision:
    source = BenchmarkSourceLink(
        benchmark_id=benchmark_id,
        context=context,
        artifact_path=artifact_path,
        policy_version=f"{context}BenchmarkPolicy-M012-1.0",
        metric_names=metric_names,
    )
    thresholds = tuple(
        CalibrationThreshold(
            threshold_id=f"THR-M012-{context}-{metric_name}",
            metric_name=metric_name,
            operator=THRESHOLD_MINIMUM,
            value="0.800000000000",
            policy_version=POLICY_VERSION_M012,
        )
        for metric_name in threshold_metric_names
    )
    if red_metric_name is None:
        verdicts = (
            ScientificGateVerdict(
                verdict_id=f"SCI-M012-{context}-GREEN",
                status=SCIENTIFIC_GREEN,
                metric_name=next(iter(metric_names)),
                benchmark_source_id=benchmark_id,
                software_gate_status="GREEN",
                reason="mesure pilote conforme a la decision publiee",
            ),
        )
    else:
        verdicts = (
            ScientificGateVerdict(
                verdict_id=f"SCI-M012-{context}-RED",
                status=SCIENTIFIC_RED,
                metric_name=red_metric_name,
                benchmark_source_id=benchmark_id,
                software_gate_status="GREEN",
                reason="test scientifique defavorable conserve dans le registre",
            ),
        )
    return PromotionDecision(
        decision_id=decision_id,
        policy_version=POLICY_VERSION_M012,
        context=context,
        status=status,
        benchmark_sources=(source,),
        thresholds=thresholds,
        criteria=criteria,
        scientific_verdicts=verdicts,
        adr_refs=("ADR-010", "DDD-ADR-010"),
        v1_gap_refs=v1_gap_refs,
        justification=justification,
        compared_llm_tasks=compared_llm_tasks,
    )


def _required_decision_tuple(values: Sequence[PromotionDecision]) -> tuple[PromotionDecision, ...]:
    decisions = _typed_tuple(values, PromotionDecision, "PromotionDecision requis")
    if len(decisions) == 0:
        raise ValueError("decision absente")
    return decisions


def _required_source_tuple(values: Sequence[BenchmarkSourceLink]) -> tuple[BenchmarkSourceLink, ...]:
    sources = _typed_tuple(values, BenchmarkSourceLink, "BenchmarkSourceLink requis")
    if len(sources) == 0:
        raise ValueError("benchmark source requis")
    source_ids: set[str] = set()
    for source in sources:
        if source.benchmark_id in source_ids:
            raise ValueError("benchmark source duplique")
        source_ids.add(source.benchmark_id)
    return sources


def _typed_tuple(values: Sequence[Any], expected_type: type[Any], error_message: str) -> tuple[Any, ...]:
    if isinstance(values, str) or not isinstance(values, Sequence):
        raise ValueError(error_message)
    parsed = tuple(values)
    for value in parsed:
        if not isinstance(value, expected_type):
            raise ValueError(error_message)
    return parsed


def _benchmark_metric_names(sources: Sequence[BenchmarkSourceLink]) -> set[str]:
    return {metric_name for source in sources for metric_name in source.metric_names}


def _criteria_names(criteria: Sequence[ContextDecisionCriteria]) -> set[str]:
    return {criterion.criterion_id for criterion in criteria}


def _ensure_required_names(actual: set[str], required: Sequence[str] | frozenset[str], message_prefix: str) -> None:
    missing = sorted(set(required).difference(actual))
    if missing:
        raise ValueError(f"{message_prefix}: {', '.join(missing)}")


def _required_policy_version(value: Any) -> str:
    text = _required_text(value, "version de politique requise")
    if not text.startswith("CalibrationDecisionPolicy-M012-"):
        raise ValueError("version de politique incoherente")
    return text


def _required_context(value: Any) -> str:
    text = _required_text(value, "context")
    if text not in _EXPECTED_CONTEXTS:
        raise ValueError("contexte M-012 inconnu")
    return text


def _required_status(value: Any, expected_values: frozenset[str], label: str) -> str:
    text = _required_text(value, label)
    if text not in expected_values:
        raise ValueError(f"{label} inconnu")
    return text


def _required_text_tuple(values: Sequence[str], field_name: str) -> tuple[str, ...]:
    parsed = _text_tuple(values, field_name)
    if len(parsed) == 0:
        raise ValueError(field_name)
    return parsed


def _text_tuple(values: Sequence[str], field_name: str) -> tuple[str, ...]:
    if isinstance(values, str) or not isinstance(values, Sequence):
        raise ValueError(field_name)
    parsed = tuple(_required_text(value, field_name) for value in values)
    if len(parsed) != len(set(parsed)):
        raise ValueError(f"{field_name} duplique")
    return parsed


def _ensure_not_obsolete(value: str) -> None:
    normalized = value.lower()
    if any(fragment in normalized for fragment in _OBSOLETE_REFERENCE_FRAGMENTS):
        raise ValueError("benchmark obsolete interdit")


def _required_decimal_text(value: Any, error_message: str) -> str:
    return f"{_decimal(value, error_message):.12f}"


def _decimal(value: Any, error_message: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(error_message)
    try:
        decimal_value = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(error_message) from exc
    if not decimal_value.is_finite():
        raise ValueError(error_message)
    return decimal_value


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


__all__ = [
    "ACCEPTED",
    "CONTEXT_CV",
    "CONTEXT_EG",
    "CONTEXT_EX",
    "CONTEXT_KA",
    "CONTEXT_LLM",
    "CONTEXT_RA",
    "CONTEXT_SD",
    "CONTEXT_SP",
    "DEFERRED",
    "POLICY_VERSION_M012",
    "REJECTED",
    "REQUIRED_CONVERSATION_CRITERIA",
    "REQUIRED_EG_DECISION_METRICS",
    "SCIENTIFIC_GREEN",
    "SCIENTIFIC_RED",
    "THRESHOLD_MAXIMUM",
    "THRESHOLD_MINIMUM",
    "BenchmarkSourceLink",
    "CalibrationDecisionPolicy",
    "CalibrationDecisionRegister",
    "CalibrationThreshold",
    "ContextDecisionCriteria",
    "PromotionDecision",
    "ScientificGateVerdict",
    "build_m012_calibration_decision_register",
]
