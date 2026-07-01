$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$matrixPath = Join-Path $repoRoot "docs/traceability/matrix.md"
$traceabilityValidatorPath = Join-Path $repoRoot "scripts/validate_traceability.ps1"
$testGatePath = Join-Path $repoRoot "scripts/test.ps1"
$lintGatePath = Join-Path $repoRoot "scripts/lint.ps1"
$metricsPath = Join-Path $repoRoot "docs/governance/m007_response_metrics.json"
$fixturePath = Join-Path $repoRoot "tests/m007/fixtures/m007_response_metrics_fixture.json"

function Assert-Contains {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content,

        [Parameter(Mandatory = $true)]
        [string] $Expected,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if (-not $Content.Contains($Expected)) {
        throw "$Message Élément attendu: $Expected"
    }
}

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

# Given les comportements M-007 sont implémentés et testés.
# When la matrice de traçabilité et les gates sont exécutés.
# Then chaque exigence M-007 est rattachée à un test GREEN, une commande de validation et une ADR ou justification explicite.
$matrixContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $matrixPath
$traceabilityValidatorContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $traceabilityValidatorPath
$testGateContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $testGatePath
$lintGateContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $lintGatePath

foreach ($requirementId in @(
    "REQ-M007-001",
    "REQ-M007-002",
    "REQ-M007-003",
    "REQ-M007-004",
    "REQ-M007-005",
    "REQ-M007-006",
    "REQ-M007-007",
    "REQ-M007-008",
    "REQ-M007-009",
    "REQ-M007-010"
)) {
    Assert-Contains -Content $matrixContent -Expected $requirementId -Message "Exigence M-007 absente de la matrice."
    Assert-Contains -Content $traceabilityValidatorContent -Expected $requirementId -Message "Exigence M-007 absente du validateur de traçabilité."
}

foreach ($testPath in @(
    "tests/m007/validate_m007_precondition_acceptance.ps1",
    "tests/m007/validate_m007_precondition_unit.ps1",
    "tests/m007/validate_m007_specification_acceptance.ps1",
    "tests/m007/validate_m007_specification_unit.ps1",
    "tests/m007/validate_research_case_mandate_acceptance.ps1",
    "tests/m007/validate_research_case_mandate_unit.ps1",
    "tests/m007/validate_evidence_set_sealing_acceptance.ps1",
    "tests/m007/validate_evidence_set_sealing_unit.ps1",
    "tests/m007/validate_contradiction_gap_acceptance.ps1",
    "tests/m007/validate_contradiction_gap_unit.ps1",
    "tests/m007/validate_answer_assertion_extraction_acceptance.ps1",
    "tests/m007/validate_answer_assertion_extraction_unit.ps1",
    "tests/m007/validate_answer_support_acceptance.ps1",
    "tests/m007/validate_answer_support_unit.ps1",
    "tests/m007/validate_current_data_abstention_acceptance.ps1",
    "tests/m007/validate_current_data_abstention_unit.ps1",
    "tests/m007/validate_answer_http_contract_acceptance.ps1",
    "tests/m007/validate_answer_http_contract_unit.ps1",
    "tests/m007/validate_m007_traceability_acceptance.ps1",
    "tests/m007/validate_m007_traceability_unit.ps1"
)) {
    Assert-Contains -Content $testGateContent -Expected $testPath -Message "Test M-007 non enrôlé dans scripts/test.ps1."
}

Assert-Contains -Content $matrixContent -Expected "tests/m007/validate_m007_traceability_acceptance.ps1" -Message "Test d'acceptation T-010 absent de la matrice."
Assert-Contains -Content $matrixContent -Expected "app/research_answering/application/traceability_metrics.py" -Message "Code applicatif T-010 absent de la matrice."
Assert-Contains -Content $matrixContent -Expected "ADR-006; ADR-010; DDD-ADR-005; DDD-ADR-008" -Message "ADR T-010 absentes de la matrice."
Assert-Contains -Content $lintGateContent -Expected "scripts/validate_traceability.ps1" -Message "Validation de traçabilité absente de scripts/lint.ps1."
Assert-Contains -Content $lintGateContent -Expected "scripts/validate_m007_specification.ps1" -Message "Validation M-007 absente de scripts/lint.ps1."

Assert-File -Path $metricsPath -Message "Publication des métriques RA M-007 absente."
Assert-File -Path $fixturePath -Message "Fixture des métriques RA M-007 absente."

$pythonCode = @'
import json
import math
from pathlib import Path
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


repo_root = Path(sys.argv[1])
metrics_path = repo_root / "docs" / "governance" / "m007_response_metrics.json"
fixture_path = repo_root / "tests" / "m007" / "fixtures" / "m007_response_metrics_fixture.json"

fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
metrics_payload = json.loads(metrics_path.read_text(encoding="utf-8"))
observations = tuple(
    ResponseMetricObservation(
        trace_id=item["trace_id"],
        research_case_id=item["research_case_id"],
        answer_id=item["answer_id"],
        support_status=item["support_status"],
        citation_count=item["citation_count"],
        citation_resolution_failed_count=item["citation_resolution_failed_count"],
        unsupported_assertion_count=item["unsupported_assertion_count"],
        coverage_obligation_count=item["coverage_obligation_count"],
        coverage_obligation_met_count=item["coverage_obligation_met_count"],
        knowledge_gap_types=tuple(item["knowledge_gap_types"]),
        contradiction_classifications=tuple(item["contradiction_classifications"]),
        abstention_reason=item["abstention_reason"],
        evidence_set_sealed=item["evidence_set_sealed"],
        model_draft_hash=item["model_draft_hash"],
        started_at=item["started_at"],
        completed_at=item["completed_at"],
    )
    for item in fixture["observations"]
)
expected = ResearchAnsweringMetricsPublisher().publish(
    fixture_id=fixture["fixture_id"],
    fixture_path="tests/m007/fixtures/m007_response_metrics_fixture.json",
    observations=observations,
    measured_at=fixture["measured_at"],
).to_payload()

assert_equal(metrics_payload["fixture_id"], expected["fixture_id"], "La fixture publiée doit correspondre à la preuve.")
assert_equal(metrics_payload["response_count"], expected["response_count"], "Le nombre de réponses publié est incohérent.")
assert_equal(metrics_payload["support_status_counts"], expected["support_status_counts"], "Les compteurs de SupportStatus sont incohérents.")
assert_equal(metrics_payload["normative_signals"], fixture["expected_normative_signals"], "Les signaux normatifs publiés ne correspondent pas à la preuve attendue.")
assert_equal(metrics_payload["knowledge_gap_type_counts"], expected["knowledge_gap_type_counts"], "Les compteurs de lacunes sont incohérents.")
assert_equal(metrics_payload["contradiction_classification_counts"], expected["contradiction_classification_counts"], "Les compteurs de contradictions sont incohérents.")
assert_equal(metrics_payload["abstention_reason_counts"], expected["abstention_reason_counts"], "Les compteurs d'abstention sont incohérents.")
assert_equal(metrics_payload["citation_count_distribution"], expected["citation_count_distribution"], "La distribution de citations est incohérente.")
for key, value in expected["rates"].items():
    assert_close(metrics_payload["rates"][key], value, f"Le taux publié est incohérent pour {key}.")
assert_close(
    metrics_payload["average_publication_latency_seconds"],
    expected["average_publication_latency_seconds"],
    "La latence moyenne publiée est incohérente.",
)

for forbidden_payload in (
    fixture["forbidden_answer_text"],
    fixture["forbidden_prompt"],
    fixture["forbidden_document_text"],
):
    assert_false(forbidden_payload in repr(metrics_payload), "Les métriques ne doivent pas exposer de payload sensible.")
assert_false("consensus" in repr(metrics_payload).lower(), "Un compteur de citations ne doit pas devenir preuve de consensus.")

signal = ResearchAnsweringAuditSignal.from_metric_snapshot(
    audit_signal_id="RA-AUDIT-M007-T010-ACCEPTANCE",
    trace_id="TRACE-M007-T010-ACCEPTANCE",
    metric_snapshot=ResearchAnsweringMetricsPublisher().publish(
        fixture_id=fixture["fixture_id"],
        fixture_path="tests/m007/fixtures/m007_response_metrics_fixture.json",
        observations=observations,
        measured_at=fixture["measured_at"],
    ),
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
    forbidden_sensitive_payloads=(
        fixture["forbidden_answer_text"],
        fixture["forbidden_prompt"],
        fixture["forbidden_document_text"],
    ),
)
signal_payload = signal.to_payload()
assert_equal(signal_payload["metric_scope"], "M007_VERIFIED_DOCUMENTARY_ANSWER", "La portée du signal doit nommer M-007.")
assert_false(fixture["forbidden_answer_text"] in repr(signal_payload), "Le signal d'audit ne doit pas exposer la réponse complète.")
assert_false(fixture["forbidden_prompt"] in repr(signal_payload), "Le signal d'audit ne doit pas exposer le prompt.")
assert_false(fixture["forbidden_document_text"] in repr(signal_payload), "Le signal d'audit ne doit pas exposer le texte documentaire complet.")

assert_raises(
    "payload sensible interdit dans answer_refs",
    lambda: ResearchAnsweringAuditSignal.from_metric_snapshot(
        audit_signal_id="RA-AUDIT-M007-T010-LEAK",
        trace_id="TRACE-M007-T010-LEAK",
        metric_snapshot=ResearchAnsweringMetricsPublisher().publish(
            fixture_id=fixture["fixture_id"],
            fixture_path="tests/m007/fixtures/m007_response_metrics_fixture.json",
            observations=observations,
            measured_at=fixture["measured_at"],
        ),
        answer_refs=(
            {
                "answer_id": "ANS-M007-T010-SUPPORTED",
                "answer_version": 1,
                "support_status": "SUPPORTED",
                "answer_text_hash": "a" * 64,
                "citation_ids": ("CIT-M007-T010-SUPPORTED",),
                "knowledge_gap_ids": (),
                "contradiction_ids": (),
                "answer_text": fixture["forbidden_answer_text"],
            },
        ),
        forbidden_sensitive_payloads=(
            fixture["forbidden_answer_text"],
            fixture["forbidden_prompt"],
            fixture["forbidden_document_text"],
        ),
    ),
)

assert_raises(
    "payload sensible interdit dans signal d'audit",
    lambda: assert_no_sensitive_payload_in_audit_payload(
        {"prompt": fixture["forbidden_prompt"]},
        forbidden_sensitive_payloads=(
            fixture["forbidden_answer_text"],
            fixture["forbidden_prompt"],
            fixture["forbidden_document_text"],
        ),
    ),
)

print("Validation applicative T-010 traçabilité et métriques M-007: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m007_traceability_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-010 traçabilité et métriques M-007: OK"
