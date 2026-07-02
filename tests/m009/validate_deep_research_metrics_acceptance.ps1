$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$metricsPath = Join-Path $repoRoot "docs/governance/m009_deep_research_metrics.json"

function Assert-File {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Message Chemin attendu: $Path"
    }
}

# Given plusieurs recherches approfondies ont produit des statuts différents.
# When les métriques M-009 sont publiées.
# Then les signaux exposent couverture, diversité, contradictions, lacunes et statuts sans contenu complet sensible.
Assert-File -Path $metricsPath -Message "Publication des métriques RA approfondies M-009 absente."

$pythonCode = @'
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, sys.argv[1])

from app.research_answering.application.deep_research_metrics import (
    DeepResearchAuditSignal,
    DeepResearchMetricObservation,
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


fixture = {
    "fixture_id": "m009_deep_research_metrics_fixture_v1",
    "fixture_path": "tests/m009/validate_deep_research_metrics_acceptance.ps1",
    "measured_at": "2026-07-02T17:30:00Z",
    "forbidden_source_text": "Texte source complet d'une preuve approfondie qui ne doit pas etre journalise.",
    "forbidden_prompt": "Prompt complet demandant au modele de synthétiser toutes les sources.",
    "forbidden_answer_text": "Réponse approfondie complète qualifiée par les preuves et les limites.",
    "forbidden_personal_data": "investisseur.prive@example.test",
    "expected_normative_signals": {
        "deep_research_requested_total": 4,
        "deep_research_plan_created_total": 4,
        "deep_research_coverage_obligation_met_total": 6,
        "deep_research_coverage_obligation_missing_total": 3,
        "deep_research_query_executed_total": 10,
        "deep_research_independent_source_group_total": 6,
        "deep_research_contradiction_classified_total": 3,
        "deep_research_documentary_gap_total": 3,
        "deep_research_support_status_total": 4,
        "deep_research_public_error_total": 1,
        "deep_research_synthesis_published_total": 2,
        "deep_research_claim_version_recorded_total": 7,
    },
    "observations": [
        {
            "trace_id": "TRACE-M009-T010-SUPPORTED",
            "research_case_id": "RSC-M009-T010-SUPPORTED",
            "answer_id": "ANS-M009-T010-SUPPORTED",
            "support_status": "SUPPORTED",
            "support_decision_basis": "COVERAGE_AND_CLAIM_POLICY",
            "coverage_obligation_statuses": ("COVERED", "COVERED", "COVERED"),
            "document_ids": ("DOC-M009-T010-A", "DOC-M009-T010-B", "DOC-M009-T010-C"),
            "query_count": 3,
            "independent_dependency_group_ids": ("DEP-M009-T010-A", "DEP-M009-T010-B", "DEP-M009-T010-C"),
            "contradiction_classifications": (),
            "documentary_gap_types": (),
            "projection_version_refs": ("PROJ-M009-T010-A", "PROJ-M009-T010-B"),
            "verified_claim_version_refs": (
                {"claim_id": "CLM-M009-T010-A", "claim_version": 1},
                {"claim_id": "CLM-M009-T010-B", "claim_version": 1},
            ),
            "public_error_code": None,
            "synthesis_published": True,
            "completed_at": "2026-07-02T17:00:00Z",
        },
        {
            "trace_id": "TRACE-M009-T010-PARTIAL",
            "research_case_id": "RSC-M009-T010-PARTIAL",
            "answer_id": "ANS-M009-T010-PARTIAL",
            "support_status": "PARTIALLY_SUPPORTED",
            "support_decision_basis": "COVERAGE_AND_CLAIM_POLICY",
            "coverage_obligation_statuses": ("COVERED", "COVERED", "INSUFFICIENT"),
            "document_ids": ("DOC-M009-T010-D", "DOC-M009-T010-E"),
            "query_count": 3,
            "independent_dependency_group_ids": ("DEP-M009-T010-D", "DEP-M009-T010-E"),
            "contradiction_classifications": ("DIFFERENT_HORIZON", "RESOLVED_BY_QUALIFICATION"),
            "documentary_gap_types": ("COVERAGE_OBLIGATION_MISSING",),
            "projection_version_refs": ("PROJ-M009-T010-C",),
            "verified_claim_version_refs": (
                {"claim_id": "CLM-M009-T010-C", "claim_version": 2},
                {"claim_id": "CLM-M009-T010-D", "claim_version": 1},
            ),
            "public_error_code": None,
            "synthesis_published": True,
            "completed_at": "2026-07-02T17:03:00Z",
        },
        {
            "trace_id": "TRACE-M009-T010-INSUFFICIENT",
            "research_case_id": "RSC-M009-T010-INSUFFICIENT",
            "answer_id": "ANS-M009-T010-INSUFFICIENT",
            "support_status": "INSUFFICIENT_EVIDENCE",
            "support_decision_basis": "COVERAGE_AND_CLAIM_POLICY",
            "coverage_obligation_statuses": ("COVERED", "INSUFFICIENT", "INSUFFICIENT"),
            "document_ids": ("DOC-M009-T010-F",),
            "query_count": 2,
            "independent_dependency_group_ids": ("DEP-M009-T010-F",),
            "contradiction_classifications": (),
            "documentary_gap_types": ("COVERAGE_OBLIGATION_MISSING", "SOURCE_DIVERSIFICATION_INSUFFICIENT"),
            "projection_version_refs": ("PROJ-M009-T010-D",),
            "verified_claim_version_refs": ({"claim_id": "CLM-M009-T010-E", "claim_version": 1},),
            "public_error_code": "COVERAGE_INSUFFICIENT",
            "synthesis_published": False,
            "completed_at": "2026-07-02T17:06:00Z",
        },
        {
            "trace_id": "TRACE-M009-T010-CONFLICTING",
            "research_case_id": "RSC-M009-T010-CONFLICTING",
            "answer_id": "ANS-M009-T010-CONFLICTING",
            "support_status": "CONFLICTING_EVIDENCE",
            "support_decision_basis": "DEEP_RESEARCH_POLICY",
            "coverage_obligation_statuses": ("OUT_OF_SCOPE", "INSUFFICIENT"),
            "document_ids": ("DOC-M009-T010-G", "DOC-M009-T010-H"),
            "query_count": 2,
            "independent_dependency_group_ids": (),
            "contradiction_classifications": ("GENUINE_CONTRADICTION",),
            "documentary_gap_types": (),
            "projection_version_refs": ("PROJ-M009-T010-E",),
            "verified_claim_version_refs": (
                {"claim_id": "CLM-M009-T010-F", "claim_version": 1},
                {"claim_id": "CLM-M009-T010-G", "claim_version": 3},
            ),
            "public_error_code": None,
            "synthesis_published": False,
            "completed_at": "2026-07-02T17:08:00Z",
        },
    ],
}


repo_root = Path(sys.argv[1])
metrics_path = repo_root / "docs" / "governance" / "m009_deep_research_metrics.json"
metrics_payload = json.loads(metrics_path.read_text(encoding="utf-8"))
observations = tuple(
    DeepResearchMetricObservation(
        trace_id=item["trace_id"],
        research_case_id=item["research_case_id"],
        answer_id=item["answer_id"],
        support_status=item["support_status"],
        support_decision_basis=item["support_decision_basis"],
        coverage_obligation_statuses=item["coverage_obligation_statuses"],
        document_ids=item["document_ids"],
        query_count=item["query_count"],
        independent_dependency_group_ids=item["independent_dependency_group_ids"],
        contradiction_classifications=item["contradiction_classifications"],
        documentary_gap_types=item["documentary_gap_types"],
        projection_version_refs=item["projection_version_refs"],
        verified_claim_version_refs=item["verified_claim_version_refs"],
        public_error_code=item["public_error_code"],
        synthesis_published=item["synthesis_published"],
        completed_at=item["completed_at"],
    )
    for item in fixture["observations"]
)
expected = DeepResearchMetricsPublisher().publish(
    fixture_id=fixture["fixture_id"],
    fixture_path=fixture["fixture_path"],
    observations=observations,
    measured_at=fixture["measured_at"],
).to_payload()

assert_equal(metrics_payload["metric_scope"], "M009_DEEP_RESEARCH", "La portée des métriques doit nommer M-009.")
assert_equal(metrics_payload["fixture_id"], expected["fixture_id"], "La fixture publiée doit correspondre à la preuve.")
assert_equal(metrics_payload["research_case_count"], expected["research_case_count"], "Le nombre de recherches est incohérent.")
assert_equal(metrics_payload["coverage_obligation_status_counts"], expected["coverage_obligation_status_counts"], "Les statuts de couverture sont incohérents.")
assert_equal(metrics_payload["documentary_diversity"], expected["documentary_diversity"], "La diversité documentaire est incohérente.")
assert_equal(metrics_payload["independent_dependency_group_total"], expected["independent_dependency_group_total"], "Les groupes indépendants sont incohérents.")
assert_equal(metrics_payload["contradiction_classification_counts"], expected["contradiction_classification_counts"], "Les contradictions sont incohérentes.")
assert_equal(metrics_payload["documentary_gap_type_counts"], expected["documentary_gap_type_counts"], "Les lacunes sont incohérentes.")
assert_equal(metrics_payload["support_status_counts"], expected["support_status_counts"], "Les statuts de support sont incohérents.")
assert_equal(metrics_payload["projection_version_refs"], expected["projection_version_refs"], "Les versions KA sont incohérentes.")
assert_equal(metrics_payload["verified_claim_version_refs"], expected["verified_claim_version_refs"], "Les versions EG sont incohérentes.")
assert_equal(metrics_payload["public_error_code_counts"], expected["public_error_code_counts"], "Les erreurs publiques sont incohérentes.")
assert_equal(metrics_payload["normative_signals"], fixture["expected_normative_signals"], "Les signaux normatifs M-009 ne correspondent pas à la preuve.")
assert_close(metrics_payload["coverage_rate"], expected["coverage_rate"], "Le taux de couverture est incohérent.")

rendered_metrics = json.dumps(metrics_payload, ensure_ascii=False, sort_keys=True)
for forbidden_payload in (
    fixture["forbidden_source_text"],
    fixture["forbidden_prompt"],
    fixture["forbidden_answer_text"],
    fixture["forbidden_personal_data"],
):
    assert_false(forbidden_payload in rendered_metrics, "Les métriques ne doivent pas exposer de payload sensible.")
assert_false("consensus" in rendered_metrics.lower(), "Un compteur ne doit pas devenir preuve de consensus.")

signal = DeepResearchAuditSignal.from_metric_snapshot(
    audit_signal_id="RA-AUDIT-M009-T010-ACCEPTANCE",
    trace_id="TRACE-M009-T010-ACCEPTANCE",
    metric_snapshot=DeepResearchMetricsPublisher().publish(
        fixture_id=fixture["fixture_id"],
        fixture_path=fixture["fixture_path"],
        observations=observations,
        measured_at=fixture["measured_at"],
    ),
    research_refs=(
        {
            "research_case_id": "RSC-M009-T010-SUPPORTED",
            "answer_id": "ANS-M009-T010-SUPPORTED",
            "support_status": "SUPPORTED",
            "answer_text_hash": "a" * 64,
            "projection_version_refs": ("PROJ-M009-T010-A", "PROJ-M009-T010-B"),
            "verified_claim_version_refs": ({"claim_id": "CLM-M009-T010-A", "claim_version": 1},),
        },
    ),
    forbidden_sensitive_payloads=(
        fixture["forbidden_source_text"],
        fixture["forbidden_prompt"],
        fixture["forbidden_answer_text"],
        fixture["forbidden_personal_data"],
    ),
)
signal_payload = signal.to_payload()
assert_equal(signal_payload["metric_scope"], "M009_DEEP_RESEARCH", "Le signal doit nommer la portée M-009.")
assert_false(fixture["forbidden_source_text"] in repr(signal_payload), "Le signal ne doit pas exposer le texte source complet.")
assert_false(fixture["forbidden_prompt"] in repr(signal_payload), "Le signal ne doit pas exposer le prompt complet.")
assert_false(fixture["forbidden_answer_text"] in repr(signal_payload), "Le signal ne doit pas exposer la réponse complète.")
assert_false(fixture["forbidden_personal_data"] in repr(signal_payload), "Le signal ne doit pas exposer de donnée personnelle inutile.")

assert_raises(
    "payload sensible interdit dans signal d'audit",
    lambda: assert_no_sensitive_payload_in_audit_payload(
        {"prompt": fixture["forbidden_prompt"]},
        forbidden_sensitive_payloads=(
            fixture["forbidden_source_text"],
            fixture["forbidden_prompt"],
            fixture["forbidden_answer_text"],
            fixture["forbidden_personal_data"],
        ),
    ),
)

print("Test d'acceptation T-010 métriques recherche approfondie M-009: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m009_deep_research_metrics_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-010 métriques recherche approfondie M-009: OK"
