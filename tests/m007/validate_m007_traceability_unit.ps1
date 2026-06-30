$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import math
import sys

sys.path.insert(0, sys.argv[1])

from app.research_answering.application.traceability_metrics import (
    ResearchAnsweringAuditSignal,
    ResearchAnsweringMetricsPublisher,
    ResponseMetricObservation,
    assert_no_sensitive_payload_in_audit_payload,
)


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_close(actual, expected, message):
    if not math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-9):
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_false(condition, message):
    if condition:
        raise AssertionError(message)


def assert_raises(expected_fragment, action):
    try:
        action()
    except (TypeError, ValueError) as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


forbidden_answer_text = "Réponse documentaire complète supportée qui ne doit pas être journalisée."
forbidden_prompt = "Prompt interne demandant au modèle de rédiger une réponse."
forbidden_document_text = "Passage documentaire complet utilisé comme preuve source."

observations = (
    ResponseMetricObservation(
        trace_id="TRACE-M007-T010-SUPPORTED",
        research_case_id="RSC-M007-T010-SUPPORTED",
        answer_id="ANS-M007-T010-SUPPORTED",
        support_status="SUPPORTED",
        citation_count=2,
        citation_resolution_failed_count=0,
        unsupported_assertion_count=0,
        coverage_obligation_count=2,
        coverage_obligation_met_count=2,
        knowledge_gap_types=(),
        contradiction_classifications=(),
        abstention_reason=None,
        evidence_set_sealed=True,
        model_draft_hash="1" * 64,
        started_at="2026-06-30T19:00:00Z",
        completed_at="2026-06-30T19:00:05Z",
    ),
    ResponseMetricObservation(
        trace_id="TRACE-M007-T010-PARTIAL",
        research_case_id="RSC-M007-T010-PARTIAL",
        answer_id="ANS-M007-T010-PARTIAL",
        support_status="PARTIALLY_SUPPORTED",
        citation_count=1,
        citation_resolution_failed_count=0,
        unsupported_assertion_count=1,
        coverage_obligation_count=2,
        coverage_obligation_met_count=1,
        knowledge_gap_types=("COVERAGE_OBLIGATION_MISSING",),
        contradiction_classifications=("RESOLVED_BY_QUALIFICATION",),
        abstention_reason=None,
        evidence_set_sealed=True,
        model_draft_hash="2" * 64,
        started_at="2026-06-30T19:01:00Z",
        completed_at="2026-06-30T19:01:09Z",
    ),
    ResponseMetricObservation(
        trace_id="TRACE-M007-T010-CONFLICTING",
        research_case_id="RSC-M007-T010-CONFLICTING",
        answer_id="ANS-M007-T010-CONFLICTING",
        support_status="CONFLICTING_EVIDENCE",
        citation_count=1,
        citation_resolution_failed_count=0,
        unsupported_assertion_count=0,
        coverage_obligation_count=2,
        coverage_obligation_met_count=2,
        knowledge_gap_types=(),
        contradiction_classifications=("DIRECT_CONFLICT",),
        abstention_reason=None,
        evidence_set_sealed=True,
        model_draft_hash="3" * 64,
        started_at="2026-06-30T19:02:00Z",
        completed_at="2026-06-30T19:02:07Z",
    ),
    ResponseMetricObservation(
        trace_id="TRACE-M007-T010-INSUFFICIENT",
        research_case_id="RSC-M007-T010-INSUFFICIENT",
        answer_id="ANS-M007-T010-INSUFFICIENT",
        support_status="INSUFFICIENT_EVIDENCE",
        citation_count=0,
        citation_resolution_failed_count=1,
        unsupported_assertion_count=0,
        coverage_obligation_count=2,
        coverage_obligation_met_count=1,
        knowledge_gap_types=("COVERAGE_OBLIGATION_MISSING",),
        contradiction_classifications=(),
        abstention_reason=None,
        evidence_set_sealed=True,
        model_draft_hash="4" * 64,
        started_at="2026-06-30T19:03:00Z",
        completed_at="2026-06-30T19:03:04Z",
    ),
    ResponseMetricObservation(
        trace_id="TRACE-M007-T010-ABSTAINED",
        research_case_id="RSC-M007-T010-ABSTAINED",
        answer_id="ANS-M007-T010-ABSTAINED",
        support_status="REQUIRES_CURRENT_DATA",
        citation_count=0,
        citation_resolution_failed_count=0,
        unsupported_assertion_count=1,
        coverage_obligation_count=1,
        coverage_obligation_met_count=0,
        knowledge_gap_types=("CURRENT_DATA_REQUIRED",),
        contradiction_classifications=(),
        abstention_reason="CURRENT_DATA_REQUIRED",
        evidence_set_sealed=True,
        model_draft_hash="5" * 64,
        started_at="2026-06-30T19:04:00Z",
        completed_at="2026-06-30T19:04:05Z",
    ),
)

# Given des observations RA agrégées par trace et statuts documentaires.
# When les métriques de clôture M-007 sont calculées.
# Then les statuts, citations, lacunes, contradictions, abstentions et latences sont publiés sans contenu sensible.
snapshot = ResearchAnsweringMetricsPublisher().publish(
    fixture_id="m007_response_metrics_fixture_v1",
    fixture_path="tests/m007/fixtures/m007_response_metrics_fixture.json",
    observations=observations,
    measured_at="2026-06-30T19:30:00Z",
)
payload = snapshot.to_payload()
assert_equal(payload["metric_scope"], "M007_VERIFIED_DOCUMENTARY_ANSWER", "La portée métrique doit nommer M-007.")
assert_equal(payload["response_count"], 5, "Le nombre de réponses doit être publié.")
assert_equal(
    payload["support_status_counts"],
    {
        "SUPPORTED": 1,
        "PARTIALLY_SUPPORTED": 1,
        "INSUFFICIENT_EVIDENCE": 1,
        "CONFLICTING_EVIDENCE": 1,
        "REQUIRES_CURRENT_DATA": 1,
    },
    "Chaque SupportStatus M-007 doit être compté.",
)
assert_equal(
    payload["normative_signals"],
    {
        "answer_support_status_total": 5,
        "answer_unsupported_assertions_removed_total": 2,
        "answer_citation_resolution_failed_total": 1,
        "answer_abstention_total": 1,
        "research_coverage_obligation_met_total": 6,
        "answer_conflict_detected_total": 2,
        "answer_knowledge_gap_total": 3,
        "answer_evidence_set_sealed_total": 5,
        "answer_model_draft_total": 5,
    },
    "Les signaux normatifs M-007 doivent être publiés explicitement.",
)
assert_equal(payload["knowledge_gap_type_counts"], {"COVERAGE_OBLIGATION_MISSING": 2, "CURRENT_DATA_REQUIRED": 1}, "Les lacunes doivent être comptées par type.")
assert_equal(payload["contradiction_classification_counts"], {"DIRECT_CONFLICT": 1, "RESOLVED_BY_QUALIFICATION": 1}, "Les contradictions doivent être comptées par classification.")
assert_equal(payload["abstention_reason_counts"], {"CURRENT_DATA_REQUIRED": 1}, "Les abstentions doivent être comptées par raison.")
assert_equal(payload["citation_count_distribution"], {"0": 2, "1": 2, "2": 1}, "La distribution de citations est incorrecte.")
assert_close(payload["average_publication_latency_seconds"], 6.0, "La latence moyenne est incorrecte.")
assert_close(payload["rates"]["supported_rate"], 0.2, "Le taux SUPPORTED est incorrect.")
assert_close(payload["rates"]["partially_supported_rate"], 0.2, "Le taux PARTIALLY_SUPPORTED est incorrect.")
assert_close(payload["rates"]["insufficient_evidence_rate"], 0.2, "Le taux INSUFFICIENT_EVIDENCE est incorrect.")
assert_close(payload["rates"]["conflicting_evidence_rate"], 0.2, "Le taux CONFLICTING_EVIDENCE est incorrect.")
assert_close(payload["rates"]["abstention_rate"], 0.2, "Le taux d'abstention est incorrect.")
assert_false(forbidden_answer_text in repr(payload), "La réponse complète ne doit pas sortir dans les métriques.")
assert_false(forbidden_prompt in repr(payload), "Le prompt ne doit pas sortir dans les métriques.")
assert_false(forbidden_document_text in repr(payload), "Le texte documentaire complet ne doit pas sortir dans les métriques.")
assert_false("consensus" in repr(payload).lower(), "Le nombre de citations ne doit pas devenir preuve de consensus.")

# Les métriques refusent les états incohérents au lieu de dégrader silencieusement le signal.
assert_raises(
    "abstention_reason requis",
    lambda: ResponseMetricObservation(
        trace_id="TRACE-M007-T010-BAD-ABSTENTION",
        research_case_id="RSC-M007-T010-BAD-ABSTENTION",
        answer_id="ANS-M007-T010-BAD-ABSTENTION",
        support_status="REQUIRES_CURRENT_DATA",
        citation_count=0,
        citation_resolution_failed_count=0,
        unsupported_assertion_count=1,
        coverage_obligation_count=1,
        coverage_obligation_met_count=0,
        knowledge_gap_types=("CURRENT_DATA_REQUIRED",),
        contradiction_classifications=(),
        abstention_reason=None,
        evidence_set_sealed=True,
        model_draft_hash="6" * 64,
        started_at="2026-06-30T19:05:00Z",
        completed_at="2026-06-30T19:05:01Z",
    ),
)
assert_raises(
    "SUPPORTED avec assertion non supportee",
    lambda: ResponseMetricObservation(
        trace_id="TRACE-M007-T010-BAD-SUPPORTED",
        research_case_id="RSC-M007-T010-BAD-SUPPORTED",
        answer_id="ANS-M007-T010-BAD-SUPPORTED",
        support_status="SUPPORTED",
        citation_count=1,
        citation_resolution_failed_count=0,
        unsupported_assertion_count=1,
        coverage_obligation_count=1,
        coverage_obligation_met_count=1,
        knowledge_gap_types=(),
        contradiction_classifications=(),
        abstention_reason=None,
        evidence_set_sealed=True,
        model_draft_hash="7" * 64,
        started_at="2026-06-30T19:05:00Z",
        completed_at="2026-06-30T19:05:01Z",
    ),
)
assert_raises(
    "delai publication negatif",
    lambda: ResponseMetricObservation(
        trace_id="TRACE-M007-T010-BAD-LATENCY",
        research_case_id="RSC-M007-T010-BAD-LATENCY",
        answer_id="ANS-M007-T010-BAD-LATENCY",
        support_status="PARTIALLY_SUPPORTED",
        citation_count=1,
        citation_resolution_failed_count=0,
        unsupported_assertion_count=1,
        coverage_obligation_count=1,
        coverage_obligation_met_count=1,
        knowledge_gap_types=(),
        contradiction_classifications=(),
        abstention_reason=None,
        evidence_set_sealed=True,
        model_draft_hash="8" * 64,
        started_at="2026-06-30T19:06:00Z",
        completed_at="2026-06-30T19:05:00Z",
    ).publication_latency_seconds(),
)

# Le signal d'audit publie uniquement des références et hashes, jamais un prompt, brouillon ou texte complet.
signal = ResearchAnsweringAuditSignal.from_metric_snapshot(
    audit_signal_id="RA-AUDIT-M007-T010-0001",
    trace_id="TRACE-M007-T010-0001",
    metric_snapshot=snapshot,
    answer_refs=(
        {
            "answer_id": "ANS-M007-T010-SUPPORTED",
            "answer_version": 1,
            "support_status": "SUPPORTED",
            "answer_text_hash": "a" * 64,
            "citation_ids": ("CIT-M007-T010-SUPPORTED",),
            "knowledge_gap_ids": (),
            "contradiction_ids": (),
        },
    ),
    forbidden_sensitive_payloads=(forbidden_answer_text, forbidden_prompt, forbidden_document_text),
)
signal_payload = signal.to_payload()
assert_equal(signal_payload["signal_name"], "research_answering_response_metrics_published", "Le signal RA doit être nommé.")
assert_equal(signal_payload["metrics"]["response_count"], 5, "Le signal doit reprendre les métriques RA.")
assert_false(forbidden_answer_text in repr(signal_payload), "Le signal ne doit pas contenir la réponse complète.")
assert_false(forbidden_prompt in repr(signal_payload), "Le signal ne doit pas contenir le prompt.")
assert_false(forbidden_document_text in repr(signal_payload), "Le signal ne doit pas contenir la preuve complète.")
assert_false("'answer_text':" in repr(signal_payload), "Le signal ne doit pas exposer le texte de réponse.")

assert_raises(
    "payload sensible interdit dans answer_refs",
    lambda: ResearchAnsweringAuditSignal.from_metric_snapshot(
        audit_signal_id="RA-AUDIT-M007-T010-0002",
        trace_id="TRACE-M007-T010-0002",
        metric_snapshot=snapshot,
        answer_refs=(
            {
                "answer_id": "ANS-M007-T010-SUPPORTED",
                "answer_version": 1,
                "support_status": "SUPPORTED",
                "answer_text_hash": "a" * 64,
                "citation_ids": ("CIT-M007-T010-SUPPORTED",),
                "knowledge_gap_ids": (),
                "contradiction_ids": (),
                "prompt": forbidden_prompt,
            },
        ),
        forbidden_sensitive_payloads=(forbidden_answer_text, forbidden_prompt, forbidden_document_text),
    ),
)
assert_raises(
    "payload sensible interdit dans signal d'audit",
    lambda: assert_no_sensitive_payload_in_audit_payload(
        {"response": forbidden_answer_text},
        forbidden_sensitive_payloads=(forbidden_answer_text, forbidden_prompt, forbidden_document_text),
    ),
)

print("Tests unitaires T-010 traçabilité et métriques M-007: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m007_traceability_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
try {
    $env:PYTHONIOENCODING = "utf-8"
    $output = & $pythonExecutable -B $pythonScriptPath $repoRoot 2>&1
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
    Remove-Item -LiteralPath $pythonScriptPath -Force
}

if ($LASTEXITCODE -ne 0) {
    throw ($output -join "`n")
}

Write-Host "Tests unitaires T-010 traçabilité et métriques M-007: OK"
