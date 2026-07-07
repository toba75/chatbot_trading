"""Décisions d'écarts V1 M-013."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


V1_GAP_STATUS_SATISFIED = "satisfait"
V1_GAP_STATUS_BLOCKING = "bloquant"
V1_GAP_STATUS_ACCEPTED = "accepté"
V1_GAP_STATUS_DEFERRED = "différé"

V1_GAP_DECISION_CORRECTED = "corrigé"
V1_GAP_DECISION_ACCEPTED = "accepté"
V1_GAP_DECISION_DEFERRED = "différé"
V1_GAP_DECISION_BLOCKING = "bloquant"

V1_GAP_DECISION_POLICY_VERSION = "V1GapDecisionPolicy-M013-1.0"

CONTEXT_SP = "SP"
CONTEXT_KA = "KA"
CONTEXT_EG = "EG"
CONTEXT_RA = "RA"
CONTEXT_CV = "CV"
CONTEXT_SD = "SD"
CONTEXT_LLM = "LLM"
CONTEXT_EX = "EX"

_EXPECTED_CONTEXTS = (CONTEXT_SP, CONTEXT_KA, CONTEXT_EG, CONTEXT_RA, CONTEXT_CV, CONTEXT_SD, CONTEXT_LLM, CONTEXT_EX)
_EXPECTED_M012_STATUSES = frozenset(
    {V1_GAP_STATUS_SATISFIED, V1_GAP_STATUS_BLOCKING, V1_GAP_STATUS_ACCEPTED, V1_GAP_STATUS_DEFERRED}
)
_EXPECTED_DECISION_STATUSES = frozenset(
    {V1_GAP_DECISION_CORRECTED, V1_GAP_DECISION_ACCEPTED, V1_GAP_DECISION_DEFERRED, V1_GAP_DECISION_BLOCKING}
)
_COMMAND_PREFIX = "powershell -NoProfile -ExecutionPolicy Bypass -File .\\"

_SOURCE_STATUSES_BY_CONTEXT = {
    CONTEXT_SP: V1_GAP_STATUS_DEFERRED,
    CONTEXT_KA: V1_GAP_STATUS_DEFERRED,
    CONTEXT_EG: V1_GAP_STATUS_SATISFIED,
    CONTEXT_RA: V1_GAP_STATUS_DEFERRED,
    CONTEXT_CV: V1_GAP_STATUS_SATISFIED,
    CONTEXT_SD: V1_GAP_STATUS_BLOCKING,
    CONTEXT_LLM: V1_GAP_STATUS_BLOCKING,
    CONTEXT_EX: V1_GAP_STATUS_SATISFIED,
}


@dataclass(frozen=True)
class V1GapDecision:
    gap_id: str
    context: str
    m012_status: str
    decision_status: str
    v1_criterion_id: str
    benchmark_source_id: str
    calibration_decision_id: str
    source_report_path: str
    evidence_command: str
    correction_command: str
    m013_green_proof: str
    non_acceptance_justification: str
    acceptance_impact: str

    def __post_init__(self) -> None:
        context = _required_context(self.context)
        m012_status = _required_status(self.m012_status, _EXPECTED_M012_STATUSES, "statut M-012")
        decision_status = _required_status(self.decision_status, _EXPECTED_DECISION_STATUSES, "décision V1")

        object.__setattr__(self, "gap_id", _required_text(self.gap_id, "écart V1"))
        object.__setattr__(self, "context", context)
        object.__setattr__(self, "m012_status", m012_status)
        object.__setattr__(self, "decision_status", decision_status)
        object.__setattr__(self, "v1_criterion_id", _required_text(self.v1_criterion_id, "critère V1 absent"))
        object.__setattr__(self, "benchmark_source_id", _required_text(self.benchmark_source_id, "benchmark source manque"))
        object.__setattr__(self, "calibration_decision_id", _required_text(self.calibration_decision_id, "décision calibration"))
        object.__setattr__(self, "source_report_path", _required_text(self.source_report_path, "rapport source"))
        object.__setattr__(self, "evidence_command", _required_command(self.evidence_command, "décision sans preuve"))
        object.__setattr__(self, "correction_command", _required_text(self.correction_command, "commande de correction"))
        object.__setattr__(self, "m013_green_proof", _required_text(self.m013_green_proof, "preuve GREEN M-013"))
        object.__setattr__(self, "acceptance_impact", _required_text(self.acceptance_impact, "impact acceptation V1"))

        if m012_status == V1_GAP_STATUS_BLOCKING and decision_status == V1_GAP_DECISION_ACCEPTED:
            raise ValueError("écart bloquant accepté")

        if decision_status == V1_GAP_DECISION_CORRECTED:
            object.__setattr__(self, "correction_command", _required_command(self.correction_command, "correction sans commande"))
            if "GREEN" not in self.m013_green_proof:
                raise ValueError("correction sans preuve GREEN")
        elif self.m013_green_proof.startswith("GREEN:") and not _is_command(self.correction_command):
            raise ValueError("preuve sans commande")

        if decision_status == V1_GAP_DECISION_DEFERRED:
            object.__setattr__(
                self,
                "non_acceptance_justification",
                _required_text(self.non_acceptance_justification, "écart différé sans justification"),
            )
        elif decision_status == V1_GAP_DECISION_BLOCKING:
            object.__setattr__(
                self,
                "non_acceptance_justification",
                _required_text(self.non_acceptance_justification, "écart bloquant sans justification"),
            )
        else:
            object.__setattr__(
                self,
                "non_acceptance_justification",
                _required_text(self.non_acceptance_justification, "justification décision V1"),
            )


@dataclass(frozen=True)
class V1GapDecisionRegister:
    register_id: str
    policy_version: str
    decisions: tuple[V1GapDecision, ...]
    decisions_by_context: Mapping[str, V1GapDecision]
    source_statuses_by_context: Mapping[str, str]
    non_accepted_decisions: tuple[V1GapDecision, ...]
    acceptance_allowed: bool


@dataclass(frozen=True)
class V1GapDecisionPolicy:
    policy_version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_version", _required_policy_version(self.policy_version))

    def publish_register(
        self,
        *,
        register_id: str,
        source_statuses_by_context: Mapping[str, str],
        decisions: Sequence[V1GapDecision],
    ) -> V1GapDecisionRegister:
        parsed_source_statuses = _required_source_statuses(source_statuses_by_context)
        parsed_decisions = _required_decision_tuple(decisions)
        decisions_by_context: dict[str, V1GapDecision] = {}
        seen_gap_ids: set[str] = set()

        for decision in parsed_decisions:
            if decision.gap_id in seen_gap_ids:
                raise ValueError("écart V1 dupliqué")
            seen_gap_ids.add(decision.gap_id)
            if decision.context in decisions_by_context:
                raise ValueError("écart V1 dupliqué")
            if decision.context in parsed_source_statuses and decision.m012_status != parsed_source_statuses[decision.context]:
                raise ValueError("décision contredit M-012")
            decisions_by_context[decision.context] = decision

        non_accepted = tuple(
            decision
            for decision in parsed_decisions
            if decision.decision_status in {V1_GAP_DECISION_DEFERRED, V1_GAP_DECISION_BLOCKING}
        )

        register = V1GapDecisionRegister(
            register_id=_required_text(register_id, "register_id"),
            policy_version=self.policy_version,
            decisions=parsed_decisions,
            decisions_by_context=decisions_by_context,
            source_statuses_by_context=parsed_source_statuses,
            non_accepted_decisions=non_accepted,
            acceptance_allowed=len(non_accepted) == 0,
        )
        return register

    def validate_register(self, register: V1GapDecisionRegister) -> None:
        if not isinstance(register, V1GapDecisionRegister):
            raise ValueError("V1GapDecisionRegister requis")
        if register.policy_version != self.policy_version:
            raise ValueError("version de politique incohérente")
        missing_contexts = [context for context in _EXPECTED_CONTEXTS if context not in register.decisions_by_context]
        if missing_contexts:
            raise ValueError("écart M-012 absent: " + ", ".join(missing_contexts))
        for context in _EXPECTED_CONTEXTS:
            decision = register.decisions_by_context[context]
            if register.source_statuses_by_context.get(context) != decision.m012_status:
                raise ValueError("décision contredit M-012")
        if any(decision.decision_status == V1_GAP_DECISION_BLOCKING for decision in register.decisions) and register.acceptance_allowed:
            raise ValueError("acceptation V1 avec écart bloquant")


def build_m013_v1_gap_decision_register() -> V1GapDecisionRegister:
    policy = V1GapDecisionPolicy(policy_version=V1_GAP_DECISION_POLICY_VERSION)
    return policy.publish_register(
        register_id="REG-M013-V1-GAP-DECISIONS-0001",
        source_statuses_by_context=_SOURCE_STATUSES_BY_CONTEXT,
        decisions=(
            _decision(
                gap_id="V1-GAP-M012-SP-CELL-QUALITY",
                context=CONTEXT_SP,
                m012_status=V1_GAP_STATUS_DEFERRED,
                decision_status=V1_GAP_DECISION_DEFERRED,
                v1_criterion_id="V1-SP-QUALITE-DOCUMENTAIRE",
                benchmark_source_id="RBRUN-M012-DOCUMENT-ROUTES-0001",
                calibration_decision_id="DEC-M012-SP-DEFERRED",
                evidence_command="powershell -NoProfile -ExecutionPolicy Bypass -File .\\tests\\m012\\validate_document_quality_calibration_acceptance.ps1",
                m013_green_proof="Non applicable: le test scientifique RED documentaire reste visible.",
                non_acceptance_justification="document_cell_accuracy reste un Test scientifique RED; report visible avant le rapport final V1.",
                acceptance_impact="Écart non accepté transmis au V1AcceptanceReport.",
            ),
            _decision(
                gap_id="V1-GAP-M012-KA-RECALL",
                context=CONTEXT_KA,
                m012_status=V1_GAP_STATUS_DEFERRED,
                decision_status=V1_GAP_DECISION_DEFERRED,
                v1_criterion_id="V1-KA-RECHERCHE-PAGES",
                benchmark_source_id="KSRUN-M012-KNOWLEDGE-0001",
                calibration_decision_id="DEC-M012-KA-REJECTED",
                evidence_command="powershell -NoProfile -ExecutionPolicy Bypass -File .\\tests\\m012\\validate_knowledge_search_benchmark_acceptance.ps1",
                m013_green_proof="Non applicable: le test scientifique RED KA reste visible.",
                non_acceptance_justification="Recall@10 pilote sous seuil; report visible avant le rapport final V1.",
                acceptance_impact="Écart non accepté transmis au V1AcceptanceReport.",
            ),
            _decision(
                gap_id="V1-GAP-M012-EG-ACCEPTED",
                context=CONTEXT_EG,
                m012_status=V1_GAP_STATUS_SATISFIED,
                decision_status=V1_GAP_DECISION_ACCEPTED,
                v1_criterion_id="V1-EG-GOUVERNANCE-PREUVES",
                benchmark_source_id="EGRUN-M012-0001",
                calibration_decision_id="DEC-M012-EG-ACCEPTED",
                evidence_command="powershell -NoProfile -ExecutionPolicy Bypass -File .\\tests\\m012\\validate_verified_answer_benchmark_acceptance.ps1",
                m013_green_proof="Preuve M-012 conservée: gouvernance des preuves séparée de RA.",
                non_acceptance_justification="Non applicable: écart satisfait et accepté explicitement.",
                acceptance_impact="Ne bloque pas l'acceptation V1.",
            ),
            _decision(
                gap_id="V1-GAP-M012-RA-ABSTENTION",
                context=CONTEXT_RA,
                m012_status=V1_GAP_STATUS_DEFERRED,
                decision_status=V1_GAP_DECISION_DEFERRED,
                v1_criterion_id="V1-RA-REPONSES-VERIFIEES",
                benchmark_source_id="VARUN-M012-VERIFIED-ANSWERS-0001",
                calibration_decision_id="DEC-M012-RA-DEFERRED",
                evidence_command="powershell -NoProfile -ExecutionPolicy Bypass -File .\\tests\\m012\\validate_verified_answer_benchmark_acceptance.ps1",
                m013_green_proof="Non applicable: le test scientifique RED RA reste visible.",
                non_acceptance_justification="answer_correct_abstention_rate reste à renforcer; report visible avant le rapport final V1.",
                acceptance_impact="Écart non accepté transmis au V1AcceptanceReport.",
            ),
            _decision(
                gap_id="V1-GAP-M012-CV-ACCEPTED",
                context=CONTEXT_CV,
                m012_status=V1_GAP_STATUS_SATISFIED,
                decision_status=V1_GAP_DECISION_ACCEPTED,
                v1_criterion_id="V1-CV-CONVERSATION-PRODUIT",
                benchmark_source_id="CVRUN-M012-CRITERIA-0001",
                calibration_decision_id="DEC-M012-CV-ACCEPTED",
                evidence_command="powershell -NoProfile -ExecutionPolicy Bypass -File .\\tests\\m012\\validate_calibration_decisions_acceptance.ps1",
                m013_green_proof="Preuve M-012 conservée: critères conversationnels V1 satisfaits.",
                non_acceptance_justification="Non applicable: écart satisfait et accepté explicitement.",
                acceptance_impact="Ne bloque pas l'acceptation V1.",
            ),
            _decision(
                gap_id="V1-GAP-M012-SD-CALIBRATION-PLAN",
                context=CONTEXT_SD,
                m012_status=V1_GAP_STATUS_BLOCKING,
                decision_status=V1_GAP_DECISION_BLOCKING,
                v1_criterion_id="V1-SD-PARAMETRES-CALIBRABLES",
                benchmark_source_id="SBRUN-M012-STRATEGY-BACKTEST-0001",
                calibration_decision_id="DEC-M012-SD-REJECTED",
                evidence_command="powershell -NoProfile -ExecutionPolicy Bypass -File .\\tests\\m012\\validate_strategy_backtest_benchmark_acceptance.ps1",
                m013_green_proof="Non applicable: aucune correction M-013 ne prouve SD GREEN.",
                non_acceptance_justification="Paramètres sans plan de calibration; l'écart bloque toute acceptation V1.",
                acceptance_impact="Acceptation V1 refusée tant que l'écart reste bloquant.",
            ),
            _decision(
                gap_id="V1-GAP-M012-LLM-COMMUNITY-PROMOTION",
                context=CONTEXT_LLM,
                m012_status=V1_GAP_STATUS_BLOCKING,
                decision_status=V1_GAP_DECISION_BLOCKING,
                v1_criterion_id="V1-LLM-CHECKPOINT-PRINCIPAL",
                benchmark_source_id="LLMRUN-M012-REAL-PATH-0001",
                calibration_decision_id="DEC-M012-LLM-REJECTED",
                evidence_command="powershell -NoProfile -ExecutionPolicy Bypass -File .\\tests\\m012\\validate_llm_benchmark_real_path_acceptance.ps1",
                m013_green_proof="Non applicable: aucune correction M-013 ne prouve LLM GREEN.",
                non_acceptance_justification="Checkpoint principal non promu sur toutes les tâches obligatoires; l'écart bloque l'acceptation V1.",
                acceptance_impact="Acceptation V1 refusée tant que l'écart reste bloquant.",
            ),
            _decision(
                gap_id="V1-GAP-M012-EX-ACCEPTED",
                context=CONTEXT_EX,
                m012_status=V1_GAP_STATUS_SATISFIED,
                decision_status=V1_GAP_DECISION_ACCEPTED,
                v1_criterion_id="V1-EX-BACKTESTS-REPRODUCTIBLES",
                benchmark_source_id="SBRUN-M012-EXPERIMENTS-0001",
                calibration_decision_id="DEC-M012-EX-ACCEPTED",
                evidence_command="powershell -NoProfile -ExecutionPolicy Bypass -File .\\tests\\m012\\validate_strategy_backtest_benchmark_acceptance.ps1",
                m013_green_proof="Preuve M-012 conservée: backtests pilotes reproductibles et résultats négatifs conservés.",
                non_acceptance_justification="Non applicable: écart satisfait et accepté explicitement.",
                acceptance_impact="Ne bloque pas l'acceptation V1.",
            ),
        ),
    )


def _decision(
    *,
    gap_id: str,
    context: str,
    m012_status: str,
    decision_status: str,
    v1_criterion_id: str,
    benchmark_source_id: str,
    calibration_decision_id: str,
    evidence_command: str,
    m013_green_proof: str,
    non_acceptance_justification: str,
    acceptance_impact: str,
) -> V1GapDecision:
    return V1GapDecision(
        gap_id=gap_id,
        context=context,
        m012_status=m012_status,
        decision_status=decision_status,
        v1_criterion_id=v1_criterion_id,
        benchmark_source_id=benchmark_source_id,
        calibration_decision_id=calibration_decision_id,
        source_report_path="docs/governance/m012_v1_gap_report.md",
        evidence_command=evidence_command,
        correction_command="Non applicable: T-003 ne corrige pas cet écart.",
        m013_green_proof=m013_green_proof,
        non_acceptance_justification=non_acceptance_justification,
        acceptance_impact=acceptance_impact,
    )


def _required_policy_version(value: Any) -> str:
    text = _required_text(value, "version de politique")
    if text != V1_GAP_DECISION_POLICY_VERSION:
        raise ValueError("version de politique incohérente")
    return text


def _required_context(value: Any) -> str:
    text = _required_text(value, "contexte")
    if text not in _EXPECTED_CONTEXTS:
        raise ValueError("contexte V1 inconnu")
    return text


def _required_status(value: Any, expected_values: frozenset[str], label: str) -> str:
    text = _required_text(value, label)
    if text not in expected_values:
        if label == "décision V1":
            raise ValueError(f"{label} inconnue")
        raise ValueError(f"{label} inconnu")
    return text


def _required_decision_tuple(values: Sequence[V1GapDecision]) -> tuple[V1GapDecision, ...]:
    if isinstance(values, str) or not isinstance(values, Sequence):
        raise ValueError("décision V1 invalide")
    decisions = tuple(values)
    if len(decisions) == 0:
        raise ValueError("décision V1 absente")
    for decision in decisions:
        if not isinstance(decision, V1GapDecision):
            raise ValueError("V1GapDecision requis")
    return decisions


def _required_source_statuses(values: Mapping[str, str]) -> Mapping[str, str]:
    if not isinstance(values, Mapping):
        raise ValueError("statuts source M-012 requis")
    parsed: dict[str, str] = {}
    for context, status in values.items():
        parsed[_required_context(context)] = _required_status(status, _EXPECTED_M012_STATUSES, "statut M-012")
    if len(parsed) == 0:
        raise ValueError("statuts source M-012 requis")
    return parsed


def _is_command(value: str) -> bool:
    return isinstance(value, str) and value.startswith(_COMMAND_PREFIX)


def _required_command(value: Any, field_name: str) -> str:
    text = _required_text(value, field_name)
    if not _is_command(text):
        raise ValueError(field_name)
    return text


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalisé")
    return value


__all__ = [
    "CONTEXT_CV",
    "CONTEXT_EG",
    "CONTEXT_EX",
    "CONTEXT_KA",
    "CONTEXT_LLM",
    "CONTEXT_RA",
    "CONTEXT_SD",
    "CONTEXT_SP",
    "V1_GAP_DECISION_ACCEPTED",
    "V1_GAP_DECISION_BLOCKING",
    "V1_GAP_DECISION_CORRECTED",
    "V1_GAP_DECISION_DEFERRED",
    "V1_GAP_DECISION_POLICY_VERSION",
    "V1_GAP_STATUS_ACCEPTED",
    "V1_GAP_STATUS_BLOCKING",
    "V1_GAP_STATUS_DEFERRED",
    "V1_GAP_STATUS_SATISFIED",
    "V1GapDecision",
    "V1GapDecisionPolicy",
    "V1GapDecisionRegister",
    "build_m013_v1_gap_decision_register",
]
