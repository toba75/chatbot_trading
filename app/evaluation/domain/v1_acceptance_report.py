"""Rapport d'acceptation V1 M-013."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.evaluation.domain.v1_gap_decisions import (
    EXPECTED_CONTEXT_BY_V1_CRITERION,
    V1_GAP_DECISION_ACCEPTED,
    V1_GAP_DECISION_BLOCKING,
    V1_GAP_DECISION_CORRECTED,
    V1_GAP_DECISION_DEFERRED,
    V1_GAP_DECISION_POLICY_VERSION,
    V1GapDecisionPolicy,
    V1GapDecisionRegister,
)


V1_ACCEPTANCE_STATUS_ACCEPTED = "accepté"
V1_ACCEPTANCE_STATUS_DEFERRED = "différé"
V1_ACCEPTANCE_STATUS_BLOCKING = "bloquant"
V1_ACCEPTANCE_STATUS_REJECTED = "non acceptée"
V1_ACCEPTANCE_REPORT_POLICY_VERSION = "V1AcceptanceReportPolicy-M013-1.0"

_EXPECTED_CRITERIA = (
    "V1-SP-QUALITE-DOCUMENTAIRE",
    "V1-KA-RECHERCHE-PAGES",
    "V1-EG-GOUVERNANCE-PREUVES",
    "V1-RA-REPONSES-VERIFIEES",
    "V1-CV-CONVERSATION-PRODUIT",
    "V1-SD-PARAMETRES-CALIBRABLES",
    "V1-LLM-CHECKPOINT-PRINCIPAL",
    "V1-EX-BACKTESTS-REPRODUCTIBLES",
)
_EXPECTED_CONTEXTS = ("SP", "KA", "EG", "RA", "CV", "SD", "LLM", "EX")
_EXPECTED_CONTEXT_BY_CRITERION = EXPECTED_CONTEXT_BY_V1_CRITERION
_ALLOWED_VERDICTS = frozenset(
    {V1_ACCEPTANCE_STATUS_ACCEPTED, V1_ACCEPTANCE_STATUS_DEFERRED, V1_ACCEPTANCE_STATUS_BLOCKING}
)
_ALLOWED_GATE_STATUSES = frozenset({"GREEN", "NON_ACCEPTATION", "DIFFÉRÉ", "BLOQUANT"})
_COMMAND_PREFIX = "uv run gate"


@dataclass(frozen=True)
class V1AcceptanceCriterionVerdict:
    criterion_id: str
    context: str
    verdict: str
    evidence_artifact: str
    evidence_command: str
    adr_refs: tuple[str, ...]
    gap_status: str
    decision: str
    final_impact: str

    def __post_init__(self) -> None:
        criterion_id = _required_text(self.criterion_id, "critère V1", empty_message="critère V1 absent")
        context = _required_text(self.context, "contexte V1")
        verdict = _required_status(self.verdict, _ALLOWED_VERDICTS, "verdict V1")

        if criterion_id not in _EXPECTED_CRITERIA:
            raise ValueError("critère V1 inconnu")
        if context not in _EXPECTED_CONTEXTS:
            raise ValueError("contexte V1 inconnu")
        if _EXPECTED_CONTEXT_BY_CRITERION[criterion_id] != context:
            raise ValueError("contexte V1 incohérent")

        object.__setattr__(self, "criterion_id", criterion_id)
        object.__setattr__(self, "context", context)
        object.__setattr__(self, "verdict", verdict)
        object.__setattr__(
            self,
            "evidence_artifact",
            _required_text(self.evidence_artifact, "preuve par verdict", empty_message="preuve par verdict absente"),
        )
        object.__setattr__(self, "evidence_command", _required_command(self.evidence_command, "commande finale"))
        object.__setattr__(self, "adr_refs", _required_adr_refs(self.adr_refs))
        object.__setattr__(self, "gap_status", _required_text(self.gap_status, "statut d'écart"))
        object.__setattr__(self, "decision", _required_text(self.decision, "décision d'écart"))
        object.__setattr__(self, "final_impact", _required_text(self.final_impact, "impact final"))

        if self.gap_status == "bloquant" and verdict == V1_ACCEPTANCE_STATUS_ACCEPTED:
            raise ValueError("écart bloquant accepté")
        if self.gap_status == "différé" and verdict == V1_ACCEPTANCE_STATUS_ACCEPTED and self.decision != "accepté":
            raise ValueError("écart différé accepté sans décision")


@dataclass(frozen=True)
class V1AcceptanceFinalGate:
    gate_id: str
    command: str
    status: str
    evidence_artifact: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "gate_id", _required_text(self.gate_id, "gate finale"))
        object.__setattr__(self, "command", _required_command(self.command, "commande finale"))
        object.__setattr__(self, "status", _required_status(self.status, _ALLOWED_GATE_STATUSES, "statut de gate finale"))
        object.__setattr__(self, "evidence_artifact", _required_text(self.evidence_artifact, "preuve de gate finale"))


@dataclass(frozen=True)
class V1AcceptanceReport:
    report_id: str
    policy_version: str
    specification_version: str
    criteria: tuple[V1AcceptanceCriterionVerdict, ...]
    final_gates: tuple[V1AcceptanceFinalGate, ...]
    non_accepted_gaps: tuple[V1AcceptanceCriterionVerdict, ...]
    blocking_gaps: tuple[V1AcceptanceCriterionVerdict, ...]
    traceability_requirement_id: str
    definition_of_done_ref: str
    acceptance_allowed: bool
    final_verdict: str


@dataclass(frozen=True)
class V1AcceptanceReportPolicy:
    policy_version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_version", _required_policy_version(self.policy_version))

    def publish_report(
        self,
        *,
        report_id: str,
        specification_version: str,
        criteria: Sequence[V1AcceptanceCriterionVerdict],
        final_gates: Sequence[V1AcceptanceFinalGate],
        gap_decision_register: V1GapDecisionRegister,
        traceability_requirement_id: str,
        definition_of_done_ref: str,
    ) -> V1AcceptanceReport:
        parsed_criteria = _required_criteria_tuple(criteria)
        parsed_final_gates = _required_gate_tuple(final_gates)
        parsed_gap_decision_register = _required_gap_decision_register(gap_decision_register)
        _assert_complete_criteria(parsed_criteria)
        _assert_criteria_match_gap_register(parsed_criteria, parsed_gap_decision_register)

        non_accepted = tuple(
            criterion
            for criterion in parsed_criteria
            if criterion.verdict in {V1_ACCEPTANCE_STATUS_DEFERRED, V1_ACCEPTANCE_STATUS_BLOCKING}
        )
        blocking = tuple(criterion for criterion in parsed_criteria if criterion.verdict == V1_ACCEPTANCE_STATUS_BLOCKING)

        acceptance_allowed = len(non_accepted) == 0 and all(gate.status == "GREEN" for gate in parsed_final_gates)
        final_verdict = V1_ACCEPTANCE_STATUS_ACCEPTED if acceptance_allowed else V1_ACCEPTANCE_STATUS_REJECTED

        return V1AcceptanceReport(
            report_id=_required_text(report_id, "rapport d'acceptation"),
            policy_version=self.policy_version,
            specification_version=_required_text(specification_version, "version de spécification"),
            criteria=parsed_criteria,
            final_gates=parsed_final_gates,
            non_accepted_gaps=non_accepted,
            blocking_gaps=blocking,
            traceability_requirement_id=_required_text(traceability_requirement_id, "exigence de traçabilité"),
            definition_of_done_ref=_required_text(definition_of_done_ref, "définition de terminé"),
            acceptance_allowed=acceptance_allowed,
            final_verdict=final_verdict,
        )

    def validate_report(self, report: V1AcceptanceReport) -> None:
        if not isinstance(report, V1AcceptanceReport):
            raise ValueError("V1AcceptanceReport requis")
        if report.policy_version != self.policy_version:
            raise ValueError("version de politique incohérente")
        _required_text(report.report_id, "rapport d'acceptation")
        _required_text(report.specification_version, "version de spécification")
        parsed_criteria = _required_criteria_tuple(report.criteria)
        parsed_final_gates = _required_gate_tuple(report.final_gates)
        _assert_complete_criteria(parsed_criteria)

        expected_non_accepted = tuple(
            criterion
            for criterion in parsed_criteria
            if criterion.verdict in {V1_ACCEPTANCE_STATUS_DEFERRED, V1_ACCEPTANCE_STATUS_BLOCKING}
        )
        expected_blocking = tuple(
            criterion for criterion in parsed_criteria if criterion.verdict == V1_ACCEPTANCE_STATUS_BLOCKING
        )
        if report.non_accepted_gaps != expected_non_accepted:
            raise ValueError("écarts non acceptés incohérents")
        if report.blocking_gaps != expected_blocking:
            raise ValueError("écarts bloquants incohérents")

        expected_acceptance_allowed = len(expected_non_accepted) == 0 and all(
            gate.status == "GREEN" for gate in parsed_final_gates
        )
        if report.acceptance_allowed != expected_acceptance_allowed:
            raise ValueError("autorisation d'acceptation incohérente")

        expected_final_verdict = (
            V1_ACCEPTANCE_STATUS_ACCEPTED
            if expected_acceptance_allowed
            else V1_ACCEPTANCE_STATUS_REJECTED
        )
        if report.final_verdict != expected_final_verdict:
            raise ValueError("verdict final incohérent")
        _required_text(report.traceability_requirement_id, "exigence de traçabilité")
        _required_text(report.definition_of_done_ref, "définition de terminé")
        if report.acceptance_allowed and report.blocking_gaps:
            raise ValueError("verdict acceptée avec écart bloquant")


def build_m013_v1_acceptance_report() -> V1AcceptanceReport:
    from app.evaluation.domain.v1_gap_decisions import build_m013_v1_gap_decision_register

    policy = V1AcceptanceReportPolicy(policy_version=V1_ACCEPTANCE_REPORT_POLICY_VERSION)
    return policy.publish_report(
        report_id="M013-V1AcceptanceReport-1.0",
        specification_version="docs/specs/m013_durcissement_acceptation_v1.md",
        criteria=(
            _criterion(
                criterion_id="V1-SP-QUALITE-DOCUMENTAIRE",
                context="SP",
                verdict=V1_ACCEPTANCE_STATUS_DEFERRED,
                gap_status="différé",
                decision="différé",
                evidence_artifact="docs/governance/m013_v1_gap_decisions.md",
                evidence_command="uv run gate --scope m012",
                final_impact="Écart non accepté: qualité documentaire pilote différée.",
            ),
            _criterion(
                criterion_id="V1-KA-RECHERCHE-PAGES",
                context="KA",
                verdict=V1_ACCEPTANCE_STATUS_DEFERRED,
                gap_status="différé",
                decision="différé",
                evidence_artifact="docs/governance/m013_v1_gap_decisions.md",
                evidence_command="uv run gate --scope m012",
                final_impact="Écart non accepté: rappel pilote KA sous seuil.",
            ),
            _criterion(
                criterion_id="V1-EG-GOUVERNANCE-PREUVES",
                context="EG",
                verdict=V1_ACCEPTANCE_STATUS_ACCEPTED,
                gap_status="satisfait",
                decision="accepté",
                evidence_artifact="docs/governance/m013_v1_gap_decisions.md",
                evidence_command="uv run gate --scope m012",
                final_impact="Accepté: gouvernance des preuves séparée de RA.",
            ),
            _criterion(
                criterion_id="V1-RA-REPONSES-VERIFIEES",
                context="RA",
                verdict=V1_ACCEPTANCE_STATUS_DEFERRED,
                gap_status="différé",
                decision="différé",
                evidence_artifact="docs/governance/m013_v1_gap_decisions.md",
                evidence_command="uv run gate --scope m012",
                final_impact="Écart non accepté: abstention correcte à renforcer.",
            ),
            _criterion(
                criterion_id="V1-CV-CONVERSATION-PRODUIT",
                context="CV",
                verdict=V1_ACCEPTANCE_STATUS_ACCEPTED,
                gap_status="satisfait",
                decision="accepté",
                evidence_artifact="docs/governance/m013_v1_gap_decisions.md",
                evidence_command="uv run gate --scope m012",
                final_impact="Accepté: critères conversationnels V1 satisfaits.",
            ),
            _criterion(
                criterion_id="V1-SD-PARAMETRES-CALIBRABLES",
                context="SD",
                verdict=V1_ACCEPTANCE_STATUS_BLOCKING,
                gap_status="bloquant",
                decision="bloquant",
                evidence_artifact="docs/governance/m013_v1_gap_decisions.md",
                evidence_command="uv run gate --scope m012",
                final_impact="Écart bloquant: paramètres sans plan de calibration.",
            ),
            _criterion(
                criterion_id="V1-LLM-CHECKPOINT-PRINCIPAL",
                context="LLM",
                verdict=V1_ACCEPTANCE_STATUS_BLOCKING,
                gap_status="bloquant",
                decision="bloquant",
                evidence_artifact="docs/governance/m013_v1_gap_decisions.md",
                evidence_command="uv run gate --scope m012",
                final_impact="Écart bloquant: checkpoint principal non promu sur toutes les tâches obligatoires.",
            ),
            _criterion(
                criterion_id="V1-EX-BACKTESTS-REPRODUCTIBLES",
                context="EX",
                verdict=V1_ACCEPTANCE_STATUS_ACCEPTED,
                gap_status="satisfait",
                decision="accepté",
                evidence_artifact="docs/governance/m013_v1_gap_decisions.md",
                evidence_command="uv run gate --scope m012",
                final_impact="Accepté: expériences reproductibles et résultats négatifs conservés.",
            ),
        ),
        final_gates=(
            _gate("GATE-M013-ACCEPTANCE-001", "uv run gate --scope m013", "GREEN"),
            _gate("GATE-M013-ACCEPTANCE-002", "uv run gate --scope m013", "GREEN"),
            _gate("GATE-M013-ACCEPTANCE-003", "uv run gate --scope m013", "NON_ACCEPTATION"),
            _gate("GATE-M013-ACCEPTANCE-004", "uv run gate --scope m013", "GREEN"),
            _gate("GATE-M013-ACCEPTANCE-005", "uv run gate --scope m013", "GREEN"),
            _gate("GATE-M013-ACCEPTANCE-006", "uv run gate --scope m012", "GREEN"),
            _gate("GATE-M013-ACCEPTANCE-007", "uv run gate --scope m012", "GREEN"),
        ),
        gap_decision_register=build_m013_v1_gap_decision_register(),
        traceability_requirement_id="REQ-M013-012",
        definition_of_done_ref="docs/governance/definition_of_done.md",
    )


def _criterion(
    *,
    criterion_id: str,
    context: str,
    verdict: str,
    gap_status: str,
    decision: str,
    evidence_artifact: str,
    evidence_command: str,
    final_impact: str,
) -> V1AcceptanceCriterionVerdict:
    return V1AcceptanceCriterionVerdict(
        criterion_id=criterion_id,
        context=context,
        verdict=verdict,
        evidence_artifact=evidence_artifact,
        evidence_command=evidence_command,
        adr_refs=("ADR-010", "DDD-ADR-010", "DDD-ADR-011"),
        gap_status=gap_status,
        decision=decision,
        final_impact=final_impact,
    )


def _gate(gate_id: str, command: str, status: str) -> V1AcceptanceFinalGate:
    return V1AcceptanceFinalGate(
        gate_id=gate_id,
        command=command,
        status=status,
        evidence_artifact="docs/governance/m013_v1_acceptance_report.md",
    )


def _required_policy_version(value: Any) -> str:
    text = _required_text(value, "version de politique")
    if text != V1_ACCEPTANCE_REPORT_POLICY_VERSION:
        raise ValueError("version de politique incohérente")
    return text


def _required_status(value: Any, expected_values: frozenset[str], label: str) -> str:
    text = _required_text(value, label)
    if text not in expected_values:
        raise ValueError(f"{label} inconnu")
    return text


def _required_command(value: Any, field_name: str) -> str:
    text = _required_text(value, field_name, empty_message=f"{field_name} absente")
    if not text.startswith(_COMMAND_PREFIX):
        raise ValueError(f"{field_name} absente")
    return text


def _required_text(value: Any, field_name: str, *, empty_message: str | None = None) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(empty_message or f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalisé")
    return value


def _required_adr_refs(values: Sequence[str]) -> tuple[str, ...]:
    if isinstance(values, str) or not isinstance(values, Sequence):
        raise ValueError("ADR reliée absente")
    parsed = tuple(_required_text(value, "ADR reliée") for value in values)
    if len(parsed) == 0:
        raise ValueError("ADR reliée absente")
    return parsed


def _required_criteria_tuple(values: Sequence[V1AcceptanceCriterionVerdict]) -> tuple[V1AcceptanceCriterionVerdict, ...]:
    if isinstance(values, str) or not isinstance(values, Sequence):
        raise ValueError("critères V1 requis")
    parsed = tuple(values)
    if len(parsed) == 0:
        raise ValueError("critères V1 requis")
    for criterion in parsed:
        if not isinstance(criterion, V1AcceptanceCriterionVerdict):
            raise ValueError("V1AcceptanceCriterionVerdict requis")
    return parsed


def _required_gate_tuple(values: Sequence[V1AcceptanceFinalGate]) -> tuple[V1AcceptanceFinalGate, ...]:
    if isinstance(values, str) or not isinstance(values, Sequence):
        raise ValueError("gates finales requises")
    parsed = tuple(values)
    if len(parsed) == 0:
        raise ValueError("gates finales requises")
    for gate in parsed:
        if not isinstance(gate, V1AcceptanceFinalGate):
            raise ValueError("V1AcceptanceFinalGate requis")
    return parsed


def _required_gap_decision_register(value: Any) -> V1GapDecisionRegister:
    if not isinstance(value, V1GapDecisionRegister):
        raise ValueError("registre d'écarts V1 requis")
    V1GapDecisionPolicy(policy_version=V1_GAP_DECISION_POLICY_VERSION).validate_register(value)
    decisions_by_context = value.decisions_by_context
    for context in _EXPECTED_CONTEXTS:
        if context not in decisions_by_context:
            raise ValueError(f"écart M-012 absent: {context}")
    return value


def _assert_complete_criteria(criteria: Sequence[V1AcceptanceCriterionVerdict]) -> None:
    criteria_by_id: dict[str, V1AcceptanceCriterionVerdict] = {}
    contexts: set[str] = set()

    for criterion in criteria:
        if criterion.criterion_id in criteria_by_id:
            raise ValueError("critère V1 dupliqué")
        if criterion.context in contexts:
            raise ValueError("contexte V1 dupliqué")
        criteria_by_id[criterion.criterion_id] = criterion
        contexts.add(criterion.context)

    for criterion_id in _EXPECTED_CRITERIA:
        if criterion_id not in criteria_by_id:
            raise ValueError(f"critère V1 absent: {criterion_id}")

    for context in _EXPECTED_CONTEXTS:
        if context not in contexts:
            raise ValueError(f"contexte V1 absent: {context}")


def _assert_criteria_match_gap_register(
    criteria: Sequence[V1AcceptanceCriterionVerdict],
    gap_decision_register: V1GapDecisionRegister,
) -> None:
    decisions_by_context = gap_decision_register.decisions_by_context
    for criterion in criteria:
        decision = decisions_by_context[criterion.context]
        decision_status = decision.decision_status
        if decision_status in {V1_GAP_DECISION_DEFERRED, V1_GAP_DECISION_BLOCKING}:
            if criterion.verdict == V1_ACCEPTANCE_STATUS_ACCEPTED:
                raise ValueError(f"écart non accepté toujours actif: {criterion.context}")
            if criterion.gap_status != decision_status or criterion.decision != decision_status:
                raise ValueError(f"rapport contredit registre d'écarts: {criterion.context}")
        elif decision_status not in {V1_GAP_DECISION_ACCEPTED, V1_GAP_DECISION_CORRECTED}:
            raise ValueError(f"décision V1 inconnue: {criterion.context}")


__all__ = [
    "V1_ACCEPTANCE_REPORT_POLICY_VERSION",
    "V1_ACCEPTANCE_STATUS_ACCEPTED",
    "V1_ACCEPTANCE_STATUS_BLOCKING",
    "V1_ACCEPTANCE_STATUS_DEFERRED",
    "V1_ACCEPTANCE_STATUS_REJECTED",
    "V1AcceptanceCriterionVerdict",
    "V1AcceptanceFinalGate",
    "V1AcceptanceReport",
    "V1AcceptanceReportPolicy",
    "build_m013_v1_acceptance_report",
]
