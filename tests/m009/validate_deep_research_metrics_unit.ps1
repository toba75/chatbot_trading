$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import math
import sys

sys.path.insert(0, sys.argv[1])

from app.research_answering.application.deep_research_metrics import (
    DeepResearchAuditSignal,
    DeepResearchMetricObservation,
    DeepResearchMetricSnapshot,
    DeepResearchMetricsPublisher,
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


def observation(**overrides):
    payload = {
        "trace_id": "TRACE-M009-T010-UNIT",
        "research_case_id": "RSC-M009-T010-UNIT",
        "answer_id": "ANS-M009-T010-UNIT",
        "support_status": "PARTIALLY_SUPPORTED",
        "support_decision_basis": "COVERAGE_AND_CLAIM_POLICY",
        "coverage_obligation_statuses": ("COVERED", "INSUFFICIENT"),
        "document_ids": ("DOC-M009-T010-U1", "DOC-M009-T010-U2"),
        "query_count": 2,
        "independent_dependency_group_ids": ("DEP-M009-T010-U1", "DEP-M009-T010-U2"),
        "contradiction_classifications": ("DIFFERENT_HORIZON",),
        "documentary_gap_types": ("COVERAGE_OBLIGATION_MISSING",),
        "projection_version_refs": ("PROJ-M009-T010-U1",),
        "verified_claim_version_refs": ({"claim_id": "CLM-M009-T010-U1", "claim_version": 1},),
        "public_error_code": None,
        "synthesis_published": True,
        "completed_at": "2026-07-02T17:40:00Z",
    }
    payload.update(overrides)
    return DeepResearchMetricObservation(**payload)


obs = observation()
snapshot = DeepResearchMetricsPublisher().publish(
    fixture_id="m009_deep_research_metrics_unit_fixture",
    fixture_path="tests/m009/validate_deep_research_metrics_unit.ps1",
    observations=(obs,),
    measured_at="2026-07-02T17:45:00Z",
)
payload = snapshot.to_payload()

assert_equal(payload["schema_version"], "1.0", "Le schéma public doit être versionné.")
assert_equal(payload["metric_scope"], "M009_DEEP_RESEARCH", "La portée doit nommer M-009.")
assert_equal(payload["coverage_obligation_status_counts"], {"COVERED": 1, "INSUFFICIENT": 1, "OUT_OF_SCOPE": 0}, "Les obligations doivent être comptées par statut.")
assert_close(payload["coverage_rate"], 0.5, "Le taux de couverture doit être déterministe.")
assert_equal(payload["documentary_diversity"]["distinct_document_total"], 2, "La diversité documentaire doit compter les documents distincts.")
assert_equal(payload["independent_dependency_group_total"], 2, "Les groupes indépendants doivent être comptés.")
assert_equal(payload["contradiction_classification_counts"], {"DIFFERENT_HORIZON": 1}, "Les contradictions doivent être publiées par classification.")
assert_equal(payload["documentary_gap_type_counts"], {"COVERAGE_OBLIGATION_MISSING": 1}, "Les lacunes doivent être publiées par type.")
assert_equal(payload["support_status_counts"]["PARTIALLY_SUPPORTED"], 1, "Le statut de support doit être compté.")
assert_equal(payload["projection_version_refs"], ["PROJ-M009-T010-U1"], "Les versions KA doivent être référencées.")
assert_equal(payload["verified_claim_version_refs"], [{"claim_id": "CLM-M009-T010-U1", "claim_version": 1}], "Les versions EG doivent être référencées.")
assert_false("consensus" in repr(payload).lower(), "Le snapshot ne doit pas déduire de consensus depuis un compteur.")

assert_raises(
    "coverage_obligation_statuses absents",
    lambda: observation(coverage_obligation_statuses=()),
)
assert_raises(
    "document_ids absents",
    lambda: observation(document_ids=()),
)
assert_raises(
    "query_count invalide",
    lambda: observation(query_count=0),
)
assert_raises(
    "projection_version_refs absents",
    lambda: observation(projection_version_refs=()),
)
assert_raises(
    "verified_claim_version_refs absentes",
    lambda: observation(verified_claim_version_refs=()),
)
assert_raises(
    "support_decision_basis par consensus interdit",
    lambda: observation(support_decision_basis="MENTION_COUNT_CONSENSUS"),
)
assert_raises(
    "contradiction requise pour CONFLICTING_EVIDENCE",
    lambda: observation(
        support_status="CONFLICTING_EVIDENCE",
        contradiction_classifications=(),
        documentary_gap_types=(),
    ),
)
assert_raises(
    "lacune requise pour INSUFFICIENT_EVIDENCE",
    lambda: observation(
        support_status="INSUFFICIENT_EVIDENCE",
        contradiction_classifications=(),
        documentary_gap_types=(),
    ),
)
assert_raises(
    "synthesis_published incompatible",
    lambda: observation(
        support_status="SUPPORTED",
        coverage_obligation_statuses=("COVERED",),
        contradiction_classifications=(),
        documentary_gap_types=(),
        synthesis_published=False,
    ),
)
assert_raises(
    "coverage_rate invalide",
    lambda: DeepResearchMetricSnapshot(
        fixture_id="m009-invalid-rate",
        fixture_path="tests/m009/validate_deep_research_metrics_unit.ps1",
        measured_at="2026-07-02T17:50:00Z",
        research_case_count=1,
        coverage_obligation_status_counts={"COVERED": 1, "INSUFFICIENT": 0, "OUT_OF_SCOPE": 0},
        coverage_rate=float("inf"),
        documentary_diversity={
            "distinct_document_total": 1,
            "minimum_document_count_per_research": 1,
            "maximum_document_count_per_research": 1,
        },
        independent_dependency_group_total=1,
        contradiction_classification_counts={},
        documentary_gap_type_counts={},
        support_status_counts={
            "SUPPORTED": 1,
            "PARTIALLY_SUPPORTED": 0,
            "INSUFFICIENT_EVIDENCE": 0,
            "CONFLICTING_EVIDENCE": 0,
            "REQUIRES_CURRENT_DATA": 0,
        },
        public_error_code_counts={},
        projection_version_refs=("PROJ-M009-T010-U1",),
        verified_claim_version_refs=({"claim_id": "CLM-M009-T010-U1", "claim_version": 1},),
        normative_signals={
            "deep_research_requested_total": 1,
            "deep_research_plan_created_total": 1,
            "deep_research_coverage_obligation_met_total": 1,
            "deep_research_coverage_obligation_missing_total": 0,
            "deep_research_query_executed_total": 1,
            "deep_research_independent_source_group_total": 1,
            "deep_research_contradiction_classified_total": 0,
            "deep_research_documentary_gap_total": 0,
            "deep_research_support_status_total": 1,
            "deep_research_public_error_total": 0,
            "deep_research_synthesis_published_total": 1,
            "deep_research_claim_version_recorded_total": 1,
        },
    ),
)

signal = DeepResearchAuditSignal.from_metric_snapshot(
    audit_signal_id="RA-AUDIT-M009-T010-UNIT",
    trace_id="TRACE-M009-T010-UNIT-SIGNAL",
    metric_snapshot=snapshot,
    research_refs=(
        {
            "research_case_id": "RSC-M009-T010-UNIT",
            "answer_id": "ANS-M009-T010-UNIT",
            "support_status": "PARTIALLY_SUPPORTED",
            "answer_text_hash": "b" * 64,
            "projection_version_refs": ("PROJ-M009-T010-U1",),
            "verified_claim_version_refs": ({"claim_id": "CLM-M009-T010-U1", "claim_version": 1},),
        },
    ),
    forbidden_sensitive_payloads=(
        "texte source complet interdit",
        "prompt complet interdit",
        "réponse complète interdite",
        "personne@example.test",
    ),
)
signal_payload = signal.to_payload()
assert_equal(signal_payload["signal_name"], "deep_research_metrics_published", "Le signal doit nommer la publication.")
assert_false("'answer_text':" in repr(signal_payload), "Le signal d'audit ne doit pas exposer de réponse complète.")

assert_raises(
    "payload sensible interdit dans research_refs",
    lambda: DeepResearchAuditSignal.from_metric_snapshot(
        audit_signal_id="RA-AUDIT-M009-T010-LEAK",
        trace_id="TRACE-M009-T010-LEAK",
        metric_snapshot=snapshot,
        research_refs=(
            {
                "research_case_id": "RSC-M009-T010-UNIT",
                "answer_id": "ANS-M009-T010-UNIT",
                "support_status": "PARTIALLY_SUPPORTED",
                "answer_text_hash": "b" * 64,
                "projection_version_refs": ("PROJ-M009-T010-U1",),
                "verified_claim_version_refs": ({"claim_id": "CLM-M009-T010-U1", "claim_version": 1},),
                "answer_text": "réponse complète interdite",
            },
        ),
        forbidden_sensitive_payloads=(
            "texte source complet interdit",
            "prompt complet interdit",
            "réponse complète interdite",
            "personne@example.test",
        ),
    ),
)
assert_raises(
    "payload sensible interdit dans signal d'audit",
    lambda: assert_no_sensitive_payload_in_audit_payload(
        {"source_text": "texte source complet interdit"},
        forbidden_sensitive_payloads=(
            "texte source complet interdit",
            "prompt complet interdit",
            "réponse complète interdite",
            "personne@example.test",
        ),
    ),
)

print("Tests unitaires T-010 métriques recherche approfondie M-009: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m009_deep_research_metrics_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-010 métriques recherche approfondie M-009: OK"
