"""Benchmark RA/EG des réponses vérifiées M-012."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from typing import Any

from app.contracts.source_references import SourceLocator


SUPPORTED = "SUPPORTED"
PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
ANSWER_SUPPORT_STATUSES = (SUPPORTED, PARTIALLY_SUPPORTED, INSUFFICIENT_EVIDENCE, CONFLICTING_EVIDENCE)

EG_VERIFIED = "VERIFIED"
EG_REJECTED = "REJECTED"
EG_IN_REVIEW = "IN_REVIEW"
EG_CLAIM_STATUSES = (EG_IN_REVIEW, EG_REJECTED, EG_VERIFIED)

ANSWER_ACCURACY_SCORE = "answer_accuracy_score"
ANSWER_FIDELITY_SCORE = "answer_fidelity_score"
ANSWER_COMPLETENESS_SCORE = "answer_completeness_score"
ANSWER_CITATION_PRECISION = "answer_citation_precision"
ANSWER_CORRECT_ABSTENTION_RATE = "answer_correct_abstention_rate"
ANSWER_CONTRADICTION_MANAGEMENT_RATE = "answer_contradiction_management_rate"
ANSWER_SOURCE_DEDUCTION_DISTINCTION_RATE = "answer_source_deduction_distinction_rate"
ANSWER_INVENTED_PARAMETER_REJECTION_RATE = "answer_invented_parameter_rejection_rate"
ANSWER_UNSUPPORTED_ASSERTION_REMOVED_TOTAL = "answer_unsupported_assertion_removed_total"
ANSWER_RESEARCH_OBLIGATION_COVERAGE = "answer_research_obligation_coverage"
ANSWER_OBSOLETE_VERSION_REUSE_RATE = "answer_obsolete_version_reuse_rate"

EG_CLAIM_VERIFIED_RATE = "evidence_claim_verified_rate"
EG_CLAIM_REJECTED_RATE = "evidence_claim_rejected_rate"
EG_CLAIM_REVIEW_RATE = "evidence_claim_review_rate"
EG_UNSUPPORTED_ASSERTION_RATIO = "evidence_unsupported_assertion_ratio"
EG_SUPERSESSION_RATE = "evidence_supersession_rate"
EG_VERIFICATION_DELAY_SECONDS = "evidence_verification_delay_seconds"

REQUIRED_VERIFIED_ANSWER_METRICS = frozenset(
    {
        ANSWER_ACCURACY_SCORE,
        ANSWER_FIDELITY_SCORE,
        ANSWER_COMPLETENESS_SCORE,
        ANSWER_CITATION_PRECISION,
        ANSWER_CORRECT_ABSTENTION_RATE,
        ANSWER_CONTRADICTION_MANAGEMENT_RATE,
        ANSWER_SOURCE_DEDUCTION_DISTINCTION_RATE,
        ANSWER_INVENTED_PARAMETER_REJECTION_RATE,
        ANSWER_UNSUPPORTED_ASSERTION_REMOVED_TOTAL,
        ANSWER_RESEARCH_OBLIGATION_COVERAGE,
        ANSWER_OBSOLETE_VERSION_REUSE_RATE,
    }
)
REQUIRED_EVIDENCE_GOVERNANCE_METRICS = frozenset(
    {
        EG_CLAIM_VERIFIED_RATE,
        EG_CLAIM_REJECTED_RATE,
        EG_CLAIM_REVIEW_RATE,
        EG_UNSUPPORTED_ASSERTION_RATIO,
        EG_SUPERSESSION_RATE,
        EG_VERIFICATION_DELAY_SECONDS,
    }
)
_DECIMAL_SCALE = Decimal("0.000000000001")
_ALLOWED_VERDICTS = frozenset({"ENTAILED", "PARTIALLY_ENTAILED", "NOT_ENTAILED"})


@dataclass(frozen=True)
class BenchmarkMetric:
    name: str
    value: str
    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _required_text_value(self.name, "metric_name"))
        object.__setattr__(self, "value", _required_decimal_text(self.value, "valeur metrique invalide"))
        object.__setattr__(self, "numerator", _required_non_negative_integer(self.numerator, "metric_numerator"))
        object.__setattr__(self, "denominator", _required_metric_denominator(self.denominator))


@dataclass(frozen=True)
class CitationMeasurement:
    citation_id: str
    source_locator: SourceLocator | None
    resolved: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "citation_id", _required_text_value(self.citation_id, "citation_id"))
        object.__setattr__(self, "resolved", _required_bool(self.resolved, "resolved"))
        if self.resolved and not isinstance(self.source_locator, SourceLocator):
            raise ValueError("source_locator requis pour citation résolue")
        if not self.resolved and self.source_locator is not None and not isinstance(self.source_locator, SourceLocator):
            raise ValueError("source_locator invalide")


@dataclass(frozen=True)
class AnswerAssertionMeasurement:
    assertion_id: str
    expected_supported: bool
    observed_supported: bool
    faithful_to_evidence: bool
    source_deduction_distinguished: bool
    removed_because_unsupported: bool
    invented_parameter_detected: bool
    invented_parameter_rejected: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "assertion_id", _required_text_value(self.assertion_id, "assertion_id"))
        for field_name in (
            "expected_supported",
            "observed_supported",
            "faithful_to_evidence",
            "source_deduction_distinguished",
            "removed_because_unsupported",
            "invented_parameter_detected",
            "invented_parameter_rejected",
        ):
            object.__setattr__(self, field_name, _required_bool(getattr(self, field_name), field_name))
        if self.invented_parameter_rejected and not self.invented_parameter_detected:
            raise ValueError("paramètre inventé rejeté sans détection")

    @property
    def counts_as_correct(self) -> bool:
        return self.expected_supported and self.observed_supported

    @property
    def counts_as_faithful(self) -> bool:
        return self.counts_as_correct and self.faithful_to_evidence


@dataclass(frozen=True)
class ResearchObligationMeasurement:
    obligation_id: str
    topic: str
    covered: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "obligation_id", _required_text_value(self.obligation_id, "obligation_id"))
        object.__setattr__(self, "topic", _required_text_value(self.topic, "topic"))
        object.__setattr__(self, "covered", _required_bool(self.covered, "covered"))


@dataclass(frozen=True)
class AnswerEvaluationCase:
    case_id: str
    question: str
    expected_support_status: str
    support_status: str
    citations: tuple[CitationMeasurement, ...]
    assertions: tuple[AnswerAssertionMeasurement, ...]
    research_obligations: tuple[ResearchObligationMeasurement, ...]
    expected_abstention: bool
    abstained: bool
    contradiction_expected: bool
    contradiction_handled: bool
    reused_obsolete_version: bool
    raw_conversation_evidence_used: bool

    def __init__(
        self,
        *,
        case_id: str,
        question: str,
        expected_support_status: str,
        support_status: str,
        citations: Sequence[CitationMeasurement],
        assertions: Sequence[AnswerAssertionMeasurement],
        research_obligations: Sequence[ResearchObligationMeasurement],
        expected_abstention: bool,
        abstained: bool,
        contradiction_expected: bool,
        contradiction_handled: bool,
        reused_obsolete_version: bool,
        raw_conversation_evidence_used: bool,
    ) -> None:
        object.__setattr__(self, "case_id", _required_text_value(case_id, "case_id"))
        object.__setattr__(self, "question", _required_text_value(question, "question"))
        object.__setattr__(self, "expected_support_status", _required_answer_support_status(expected_support_status))
        object.__setattr__(self, "support_status", _required_answer_support_status(support_status))
        object.__setattr__(self, "citations", _required_citations(citations))
        object.__setattr__(self, "assertions", _required_assertions(assertions))
        object.__setattr__(self, "research_obligations", _required_obligations(research_obligations))
        object.__setattr__(self, "expected_abstention", _required_bool(expected_abstention, "expected_abstention"))
        object.__setattr__(self, "abstained", _required_bool(abstained, "abstained"))
        object.__setattr__(self, "contradiction_expected", _required_bool(contradiction_expected, "contradiction_expected"))
        object.__setattr__(self, "contradiction_handled", _required_bool(contradiction_handled, "contradiction_handled"))
        object.__setattr__(self, "reused_obsolete_version", _required_bool(reused_obsolete_version, "reused_obsolete_version"))
        object.__setattr__(
            self,
            "raw_conversation_evidence_used",
            _required_bool(raw_conversation_evidence_used, "raw_conversation_evidence_used"),
        )
        self._ensure_consistency()

    def _ensure_consistency(self) -> None:
        if self.raw_conversation_evidence_used:
            raise ValueError("historique conversationnel brut interdit")
        if self.support_status == SUPPORTED:
            for assertion in self.assertions:
                if assertion.expected_supported and not assertion.observed_supported:
                    raise ValueError("SUPPORTED avec assertion non supportée")
        if self.contradiction_handled and not self.contradiction_expected:
            raise ValueError("contradiction gérée sans contradiction attendue")


@dataclass(frozen=True)
class AnswerCaseBenchmarkResult:
    case_id: str
    support_status: str
    expected_support_status: str
    assertion_count: int
    correct_assertion_count: int
    citation_count: int
    citation_failure_count: int
    unsupported_assertion_removed_count: int
    research_obligation_count: int
    covered_research_obligation_count: int
    failure_reasons: tuple[str, ...]
    reused_obsolete_version: bool


@dataclass(frozen=True)
class AnswerSupportReport:
    support_status_rates: Mapping[str, BenchmarkMetric]
    case_results: tuple[AnswerCaseBenchmarkResult, ...]


@dataclass(frozen=True)
class AnswerAbstentionReport:
    expected_abstention_count: int
    correct_abstention_count: int
    missing_abstention_case_ids: tuple[str, ...]


@dataclass(frozen=True)
class VerifiedAnswerBenchmarkRun:
    run_id: str
    policy_version: str
    case_count: int
    metrics: Mapping[str, BenchmarkMetric]
    support_status_rates: Mapping[str, BenchmarkMetric]
    case_results: tuple[AnswerCaseBenchmarkResult, ...]
    support_report: AnswerSupportReport
    abstention_report: AnswerAbstentionReport


@dataclass(frozen=True)
class VerifiedAnswerBenchmark:
    policy_version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_version", _required_text_value(self.policy_version, "policy_version"))

    def measure(
        self,
        *,
        run_id: str,
        evaluation_cases: Sequence[AnswerEvaluationCase],
    ) -> VerifiedAnswerBenchmarkRun:
        parsed_run_id = _required_text_value(run_id, "run_id")
        cases = _required_answer_cases(evaluation_cases)
        case_results = tuple(_measure_answer_case(case) for case in cases)
        support_status_rates = _support_status_rates(cases)
        metrics = _answer_metrics(cases, case_results)
        _ensure_required_metrics(metrics, REQUIRED_VERIFIED_ANSWER_METRICS, "metrique RA absente")
        support_report = AnswerSupportReport(
            support_status_rates=support_status_rates,
            case_results=case_results,
        )
        missing_abstention_case_ids = tuple(
            result.case_id for case, result in zip(cases, case_results) if case.expected_abstention and not case.abstained
        )
        abstention_report = AnswerAbstentionReport(
            expected_abstention_count=sum(1 for case in cases if case.expected_abstention),
            correct_abstention_count=sum(1 for case in cases if case.expected_abstention and case.abstained),
            missing_abstention_case_ids=missing_abstention_case_ids,
        )
        return VerifiedAnswerBenchmarkRun(
            run_id=parsed_run_id,
            policy_version=self.policy_version,
            case_count=len(cases),
            metrics=metrics,
            support_status_rates=support_status_rates,
            case_results=case_results,
            support_report=support_report,
            abstention_report=abstention_report,
        )


@dataclass(frozen=True)
class EvidenceClaimMeasurement:
    claim_id: str
    claim_version: int
    subject: str
    status: str
    verdict: str
    has_direct_evidence: bool
    dependency_group_ids: tuple[str, ...]
    superseded: bool
    submitted_at: str
    decided_at: str | None

    def __init__(
        self,
        *,
        claim_id: str,
        claim_version: int,
        subject: str,
        status: str,
        verdict: str,
        has_direct_evidence: bool,
        dependency_group_ids: Sequence[str],
        superseded: bool,
        submitted_at: str,
        decided_at: str | None,
    ) -> None:
        object.__setattr__(self, "claim_id", _required_prefixed_text(claim_id, "CLM-", "claim_id"))
        object.__setattr__(self, "claim_version", _required_positive_integer(claim_version, "claim_version"))
        object.__setattr__(self, "subject", _required_text_value(subject, "subject"))
        object.__setattr__(self, "status", _required_claim_status(status))
        object.__setattr__(self, "verdict", _required_verdict(verdict))
        object.__setattr__(self, "has_direct_evidence", _required_bool(has_direct_evidence, "has_direct_evidence"))
        object.__setattr__(self, "dependency_group_ids", _required_dependency_group_ids(dependency_group_ids))
        object.__setattr__(self, "superseded", _required_bool(superseded, "superseded"))
        object.__setattr__(self, "submitted_at", _required_utc_instant(submitted_at, "submitted_at"))
        object.__setattr__(self, "decided_at", _optional_utc_instant(decided_at, "decided_at"))
        self._ensure_consistency()

    def _ensure_consistency(self) -> None:
        if self.status == EG_VERIFIED and not self.has_direct_evidence:
            raise ValueError("preuve directe requise pour claim VERIFIED")
        if self.status == EG_IN_REVIEW and self.decided_at is not None:
            raise ValueError("decided_at incompatible avec IN_REVIEW")
        if self.status != EG_IN_REVIEW and self.decided_at is None:
            raise ValueError("decided_at requis")
        self.verification_delay_seconds()

    def verification_delay_seconds(self) -> int | None:
        if self.decided_at is None:
            return None
        submitted_at = _parse_utc_instant(self.submitted_at)
        decided_at = _parse_utc_instant(self.decided_at)
        delay = int((decided_at - submitted_at).total_seconds())
        if delay < 0:
            raise ValueError("delai verification negatif")
        return delay


@dataclass(frozen=True)
class EvidenceGovernanceReport:
    status_distribution: Mapping[str, int]
    verdict_distribution: Mapping[str, int]
    dependency_group_count_by_subject: Mapping[str, int]
    claim_results: tuple[EvidenceClaimMeasurement, ...]


@dataclass(frozen=True)
class EvidenceGovernanceBenchmarkRun:
    run_id: str
    policy_version: str
    claim_count: int
    metrics: Mapping[str, BenchmarkMetric]
    status_distribution: Mapping[str, int]
    verdict_distribution: Mapping[str, int]
    dependency_group_count_by_subject: Mapping[str, int]
    governance_report: EvidenceGovernanceReport


@dataclass(frozen=True)
class EvidenceGovernanceBenchmark:
    policy_version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_version", _required_text_value(self.policy_version, "policy_version"))

    def measure(
        self,
        *,
        run_id: str,
        claim_measurements: Sequence[EvidenceClaimMeasurement],
    ) -> EvidenceGovernanceBenchmarkRun:
        parsed_run_id = _required_text_value(run_id, "run_id")
        claims = _required_claim_measurements(claim_measurements)
        status_distribution = _claim_status_distribution(claims)
        verdict_distribution = _verdict_distribution(claims)
        dependency_group_count_by_subject = _dependency_group_count_by_subject(claims)
        metrics = _evidence_governance_metrics(claims, status_distribution)
        _ensure_required_metrics(metrics, REQUIRED_EVIDENCE_GOVERNANCE_METRICS, "metrique EG absente")
        governance_report = EvidenceGovernanceReport(
            status_distribution=status_distribution,
            verdict_distribution=verdict_distribution,
            dependency_group_count_by_subject=dependency_group_count_by_subject,
            claim_results=claims,
        )
        return EvidenceGovernanceBenchmarkRun(
            run_id=parsed_run_id,
            policy_version=self.policy_version,
            claim_count=len(claims),
            metrics=metrics,
            status_distribution=status_distribution,
            verdict_distribution=verdict_distribution,
            dependency_group_count_by_subject=dependency_group_count_by_subject,
            governance_report=governance_report,
        )


def _measure_answer_case(case: AnswerEvaluationCase) -> AnswerCaseBenchmarkResult:
    citation_failures = sum(1 for citation in case.citations if not citation.resolved)
    unsupported_removed = sum(1 for assertion in case.assertions if assertion.removed_because_unsupported)
    correct_assertions = sum(1 for assertion in case.assertions if assertion.counts_as_correct)
    covered_obligations = sum(1 for obligation in case.research_obligations if obligation.covered)
    failure_reasons = _answer_failure_reasons(case, citation_failures)
    return AnswerCaseBenchmarkResult(
        case_id=case.case_id,
        support_status=case.support_status,
        expected_support_status=case.expected_support_status,
        assertion_count=len(case.assertions),
        correct_assertion_count=correct_assertions,
        citation_count=len(case.citations),
        citation_failure_count=citation_failures,
        unsupported_assertion_removed_count=unsupported_removed,
        research_obligation_count=len(case.research_obligations),
        covered_research_obligation_count=covered_obligations,
        failure_reasons=failure_reasons,
        reused_obsolete_version=case.reused_obsolete_version,
    )


def _answer_failure_reasons(case: AnswerEvaluationCase, citation_failures: int) -> tuple[str, ...]:
    reasons: list[str] = []
    if case.expected_support_status != case.support_status:
        reasons.append("statut documentaire inattendu")
    if citation_failures > 0:
        reasons.append("citation non résoluble")
    if case.expected_abstention and not case.abstained:
        reasons.append("abstention attendue absente")
    if case.contradiction_expected and not case.contradiction_handled:
        reasons.append("contradiction non gérée")
    for assertion in case.assertions:
        if assertion.invented_parameter_detected and not assertion.invented_parameter_rejected:
            reasons.append("paramètre inventé non rejeté")
    return tuple(reasons)


def _support_status_rates(cases: tuple[AnswerEvaluationCase, ...]) -> Mapping[str, BenchmarkMetric]:
    denominator = len(cases)
    return {
        status: BenchmarkMetric(f"answer_support_status_rate_{status}", _metric_value(_count_support(cases, status), denominator), _count_support(cases, status), denominator)
        for status in ANSWER_SUPPORT_STATUSES
    }


def _answer_metrics(
    cases: tuple[AnswerEvaluationCase, ...],
    case_results: tuple[AnswerCaseBenchmarkResult, ...],
) -> Mapping[str, BenchmarkMetric]:
    all_assertions = tuple(assertion for case in cases for assertion in case.assertions)
    all_citations = tuple(citation for case in cases for citation in case.citations)
    all_obligations = tuple(obligation for case in cases for obligation in case.research_obligations)
    expected_abstentions = tuple(case for case in cases if case.expected_abstention)
    expected_contradictions = tuple(case for case in cases if case.contradiction_expected)
    detected_invented_parameters = tuple(
        assertion for assertion in all_assertions if assertion.invented_parameter_detected
    )
    return {
        ANSWER_ACCURACY_SCORE: _ratio_metric(
            ANSWER_ACCURACY_SCORE,
            sum(1 for assertion in all_assertions if assertion.counts_as_correct),
            len(all_assertions),
        ),
        ANSWER_FIDELITY_SCORE: _ratio_metric(
            ANSWER_FIDELITY_SCORE,
            sum(1 for assertion in all_assertions if assertion.counts_as_faithful),
            len(all_assertions),
        ),
        ANSWER_COMPLETENESS_SCORE: _ratio_metric(
            ANSWER_COMPLETENESS_SCORE,
            sum(1 for obligation in all_obligations if obligation.covered),
            len(all_obligations),
        ),
        ANSWER_CITATION_PRECISION: _ratio_metric(
            ANSWER_CITATION_PRECISION,
            sum(1 for citation in all_citations if citation.resolved),
            len(all_citations),
        ),
        ANSWER_CORRECT_ABSTENTION_RATE: _ratio_metric(
            ANSWER_CORRECT_ABSTENTION_RATE,
            sum(1 for case in expected_abstentions if case.abstained),
            len(expected_abstentions),
        ),
        ANSWER_CONTRADICTION_MANAGEMENT_RATE: _ratio_metric(
            ANSWER_CONTRADICTION_MANAGEMENT_RATE,
            sum(1 for case in expected_contradictions if case.contradiction_handled),
            len(expected_contradictions),
        ),
        ANSWER_SOURCE_DEDUCTION_DISTINCTION_RATE: _ratio_metric(
            ANSWER_SOURCE_DEDUCTION_DISTINCTION_RATE,
            sum(1 for assertion in all_assertions if assertion.source_deduction_distinguished),
            len(all_assertions),
        ),
        ANSWER_INVENTED_PARAMETER_REJECTION_RATE: _ratio_metric(
            ANSWER_INVENTED_PARAMETER_REJECTION_RATE,
            sum(1 for assertion in detected_invented_parameters if assertion.invented_parameter_rejected),
            len(detected_invented_parameters),
        ),
        ANSWER_UNSUPPORTED_ASSERTION_REMOVED_TOTAL: BenchmarkMetric(
            ANSWER_UNSUPPORTED_ASSERTION_REMOVED_TOTAL,
            _format_decimal(Decimal(sum(result.unsupported_assertion_removed_count for result in case_results))),
            sum(result.unsupported_assertion_removed_count for result in case_results),
            1,
        ),
        ANSWER_RESEARCH_OBLIGATION_COVERAGE: _ratio_metric(
            ANSWER_RESEARCH_OBLIGATION_COVERAGE,
            sum(1 for obligation in all_obligations if obligation.covered),
            len(all_obligations),
        ),
        ANSWER_OBSOLETE_VERSION_REUSE_RATE: _ratio_metric(
            ANSWER_OBSOLETE_VERSION_REUSE_RATE,
            sum(1 for case in cases if case.reused_obsolete_version),
            len(cases),
        ),
    }


def _evidence_governance_metrics(
    claims: tuple[EvidenceClaimMeasurement, ...],
    status_distribution: Mapping[str, int],
) -> Mapping[str, BenchmarkMetric]:
    delays = tuple(delay for delay in (claim.verification_delay_seconds() for claim in claims) if delay is not None)
    if len(delays) == 0:
        raise ValueError("delai verification absent")
    delay_total = sum(delays)
    return {
        EG_CLAIM_VERIFIED_RATE: _ratio_metric(EG_CLAIM_VERIFIED_RATE, status_distribution[EG_VERIFIED], len(claims)),
        EG_CLAIM_REJECTED_RATE: _ratio_metric(EG_CLAIM_REJECTED_RATE, status_distribution[EG_REJECTED], len(claims)),
        EG_CLAIM_REVIEW_RATE: _ratio_metric(EG_CLAIM_REVIEW_RATE, status_distribution[EG_IN_REVIEW], len(claims)),
        EG_UNSUPPORTED_ASSERTION_RATIO: _ratio_metric(
            EG_UNSUPPORTED_ASSERTION_RATIO,
            sum(1 for claim in claims if not claim.has_direct_evidence),
            len(claims),
        ),
        EG_SUPERSESSION_RATE: _ratio_metric(
            EG_SUPERSESSION_RATE,
            sum(1 for claim in claims if claim.superseded),
            len(claims),
        ),
        EG_VERIFICATION_DELAY_SECONDS: BenchmarkMetric(
            EG_VERIFICATION_DELAY_SECONDS,
            _format_decimal(Decimal(delay_total) / Decimal(len(delays))),
            delay_total,
            len(delays),
        ),
    }


def _count_support(cases: tuple[AnswerEvaluationCase, ...], status: str) -> int:
    return sum(1 for case in cases if case.support_status == status)


def _claim_status_distribution(claims: tuple[EvidenceClaimMeasurement, ...]) -> Mapping[str, int]:
    return {status: sum(1 for claim in claims if claim.status == status) for status in EG_CLAIM_STATUSES}


def _verdict_distribution(claims: tuple[EvidenceClaimMeasurement, ...]) -> Mapping[str, int]:
    return {
        verdict: count
        for verdict, count in sorted(
            ((verdict, sum(1 for claim in claims if claim.verdict == verdict)) for verdict in _ALLOWED_VERDICTS),
            key=lambda item: item[0],
        )
        if count > 0
    }


def _dependency_group_count_by_subject(claims: tuple[EvidenceClaimMeasurement, ...]) -> Mapping[str, int]:
    by_subject: dict[str, set[str]] = {}
    for claim in claims:
        by_subject.setdefault(claim.subject, set()).update(claim.dependency_group_ids)
    return {subject: len(group_ids) for subject, group_ids in sorted(by_subject.items())}


def _required_answer_cases(values: Sequence[AnswerEvaluationCase]) -> tuple[AnswerEvaluationCase, ...]:
    if isinstance(values, str) or not isinstance(values, Sequence):
        raise ValueError("cas evaluation invalides")
    cases = tuple(values)
    if len(cases) == 0:
        raise ValueError("dénominateur métrique invalide")
    case_ids: set[str] = set()
    for case in cases:
        if not isinstance(case, AnswerEvaluationCase):
            raise ValueError("AnswerEvaluationCase requis")
        if case.case_id in case_ids:
            raise ValueError("cas evaluation duplique")
        case_ids.add(case.case_id)
    return cases


def _required_claim_measurements(values: Sequence[EvidenceClaimMeasurement]) -> tuple[EvidenceClaimMeasurement, ...]:
    if isinstance(values, str) or not isinstance(values, Sequence):
        raise ValueError("claim_measurements invalides")
    claims = tuple(values)
    if len(claims) == 0:
        raise ValueError("dénominateur métrique invalide")
    claim_refs: set[tuple[str, int]] = set()
    for claim in claims:
        if not isinstance(claim, EvidenceClaimMeasurement):
            raise ValueError("EvidenceClaimMeasurement requis")
        ref = (claim.claim_id, claim.claim_version)
        if ref in claim_refs:
            raise ValueError("claim measurement duplique")
        claim_refs.add(ref)
    return claims


def _required_citations(values: Sequence[CitationMeasurement]) -> tuple[CitationMeasurement, ...]:
    if isinstance(values, str) or not isinstance(values, Sequence):
        raise ValueError("citations invalides")
    citations = tuple(values)
    citation_ids: set[str] = set()
    for citation in citations:
        if not isinstance(citation, CitationMeasurement):
            raise ValueError("CitationMeasurement requise")
        if citation.citation_id in citation_ids:
            raise ValueError("citation dupliquee")
        citation_ids.add(citation.citation_id)
    return citations


def _required_assertions(values: Sequence[AnswerAssertionMeasurement]) -> tuple[AnswerAssertionMeasurement, ...]:
    if isinstance(values, str) or not isinstance(values, Sequence):
        raise ValueError("assertions invalides")
    assertions = tuple(values)
    assertion_ids: set[str] = set()
    for assertion in assertions:
        if not isinstance(assertion, AnswerAssertionMeasurement):
            raise ValueError("AnswerAssertionMeasurement requise")
        if assertion.assertion_id in assertion_ids:
            raise ValueError("assertion dupliquee")
        assertion_ids.add(assertion.assertion_id)
    return assertions


def _required_obligations(values: Sequence[ResearchObligationMeasurement]) -> tuple[ResearchObligationMeasurement, ...]:
    if isinstance(values, str) or not isinstance(values, Sequence):
        raise ValueError("obligations recherche invalides")
    obligations = tuple(values)
    if len(obligations) == 0:
        raise ValueError("obligation de recherche absente")
    obligation_ids: set[str] = set()
    for obligation in obligations:
        if not isinstance(obligation, ResearchObligationMeasurement):
            raise ValueError("ResearchObligationMeasurement requise")
        if obligation.obligation_id in obligation_ids:
            raise ValueError("obligation recherche dupliquee")
        obligation_ids.add(obligation.obligation_id)
    return obligations


def _required_dependency_group_ids(values: Sequence[str]) -> tuple[str, ...]:
    if isinstance(values, str) or not isinstance(values, Sequence):
        raise ValueError("dependency_group_ids invalides")
    group_ids = tuple(_required_prefixed_text(value, "DEP-", "dependency_group_id") for value in values)
    if len(group_ids) == 0:
        raise ValueError("dependency_group_ids absents")
    if len(group_ids) != len(set(group_ids)):
        raise ValueError("dependency_group_ids dupliques")
    return group_ids


def _ensure_required_metrics(
    metrics: Mapping[str, BenchmarkMetric],
    required_metrics: frozenset[str],
    message_prefix: str,
) -> None:
    missing_metrics = sorted(required_metrics.difference(metrics.keys()))
    if missing_metrics:
        raise ValueError(f"{message_prefix}: {', '.join(missing_metrics)}")
    for metric in metrics.values():
        if not isinstance(metric, BenchmarkMetric):
            raise ValueError("BenchmarkMetric requise")


def _required_answer_support_status(value: Any) -> str:
    text = _required_text_value(value, "support_status")
    if text not in ANSWER_SUPPORT_STATUSES:
        raise ValueError("statut documentaire invalide")
    return text


def _required_claim_status(value: Any) -> str:
    text = _required_text_value(value, "status")
    if text not in EG_CLAIM_STATUSES:
        raise ValueError("status claim invalide")
    return text


def _required_verdict(value: Any) -> str:
    text = _required_text_value(value, "verdict")
    if text not in _ALLOWED_VERDICTS:
        raise ValueError("verdict invalide")
    return text


def _required_prefixed_text(value: Any, prefix: str, field_name: str) -> str:
    text = _required_text_value(value, field_name)
    if not text.startswith(prefix):
        raise ValueError(f"{field_name} invalide")
    return text


def _required_utc_instant(value: Any, field_name: str) -> str:
    text = _required_text_value(value, field_name)
    _parse_utc_instant(text)
    return text


def _optional_utc_instant(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return _required_utc_instant(value, field_name)


def _parse_utc_instant(value: str) -> datetime:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ValueError("instant UTC invalide") from exc
    return parsed.replace(tzinfo=timezone.utc)


def _ratio_metric(metric_name: str, numerator: int, denominator: int) -> BenchmarkMetric:
    return BenchmarkMetric(metric_name, _metric_value(numerator, denominator), numerator, denominator)


def _metric_value(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        raise ValueError("dénominateur métrique invalide")
    return _format_decimal(Decimal(numerator) / Decimal(denominator))


def _required_decimal_text(value: Any, error_message: str) -> str:
    return _format_decimal(_decimal(value, error_message))


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


def _format_decimal(value: Decimal) -> str:
    return f"{value.quantize(_DECIMAL_SCALE, rounding=ROUND_HALF_EVEN):.12f}"


def _required_text_value(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


def _required_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} non booléen")
    return value


def _required_positive_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} invalide")
    return value


def _required_non_negative_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} invalide")
    return value


def _required_metric_denominator(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("dénominateur métrique invalide")
    return value


__all__ = [
    "ANSWER_ACCURACY_SCORE",
    "ANSWER_CITATION_PRECISION",
    "ANSWER_COMPLETENESS_SCORE",
    "ANSWER_CONTRADICTION_MANAGEMENT_RATE",
    "ANSWER_CORRECT_ABSTENTION_RATE",
    "ANSWER_FIDELITY_SCORE",
    "ANSWER_INVENTED_PARAMETER_REJECTION_RATE",
    "ANSWER_OBSOLETE_VERSION_REUSE_RATE",
    "ANSWER_RESEARCH_OBLIGATION_COVERAGE",
    "ANSWER_SOURCE_DEDUCTION_DISTINCTION_RATE",
    "ANSWER_SUPPORT_STATUSES",
    "ANSWER_UNSUPPORTED_ASSERTION_REMOVED_TOTAL",
    "CONFLICTING_EVIDENCE",
    "EG_CLAIM_REJECTED_RATE",
    "EG_CLAIM_REVIEW_RATE",
    "EG_CLAIM_STATUSES",
    "EG_CLAIM_VERIFIED_RATE",
    "EG_IN_REVIEW",
    "EG_REJECTED",
    "EG_SUPERSESSION_RATE",
    "EG_UNSUPPORTED_ASSERTION_RATIO",
    "EG_VERIFICATION_DELAY_SECONDS",
    "EG_VERIFIED",
    "INSUFFICIENT_EVIDENCE",
    "PARTIALLY_SUPPORTED",
    "REQUIRED_EVIDENCE_GOVERNANCE_METRICS",
    "REQUIRED_VERIFIED_ANSWER_METRICS",
    "SUPPORTED",
    "AnswerAbstentionReport",
    "AnswerAssertionMeasurement",
    "AnswerCaseBenchmarkResult",
    "AnswerEvaluationCase",
    "AnswerSupportReport",
    "BenchmarkMetric",
    "CitationMeasurement",
    "EvidenceClaimMeasurement",
    "EvidenceGovernanceBenchmark",
    "EvidenceGovernanceBenchmarkRun",
    "EvidenceGovernanceReport",
    "ResearchObligationMeasurement",
    "VerifiedAnswerBenchmark",
    "VerifiedAnswerBenchmarkRun",
]
