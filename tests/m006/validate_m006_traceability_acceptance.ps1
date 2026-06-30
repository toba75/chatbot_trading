$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$matrixPath = Join-Path $repoRoot "docs/traceability/matrix.md"
$traceabilityValidatorPath = Join-Path $repoRoot "scripts/validate_traceability.ps1"
$testGatePath = Join-Path $repoRoot "scripts/test.ps1"
$lintGatePath = Join-Path $repoRoot "scripts/lint.ps1"
$metricsPath = Join-Path $repoRoot "docs/governance/m006_claim_metrics.json"
$fixturePath = Join-Path $repoRoot "tests/m006/fixtures/m006_claim_metrics_fixture.json"

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

# Given les comportements M-006 sont implémentés et testés.
# When la matrice de traçabilité et les gates sont exécutés.
# Then chaque exigence M-006 est rattachée à un test GREEN, une commande de validation et une ADR ou justification explicite.
$matrixContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $matrixPath
$traceabilityValidatorContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $traceabilityValidatorPath
$testGateContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $testGatePath
$lintGateContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $lintGatePath

foreach ($requirementId in @(
    "REQ-M006-001",
    "REQ-M006-002",
    "REQ-M006-003",
    "REQ-M006-004",
    "REQ-M006-005",
    "REQ-M006-006",
    "REQ-M006-007",
    "REQ-M006-008",
    "REQ-M006-009",
    "REQ-M006-010"
)) {
    Assert-Contains -Content $matrixContent -Expected $requirementId -Message "Exigence M-006 absente de la matrice."
    Assert-Contains -Content $traceabilityValidatorContent -Expected $requirementId -Message "Exigence M-006 absente du validateur de traçabilité."
}

Assert-Contains -Content $matrixContent -Expected "tests/m006/validate_m006_traceability_acceptance.ps1" -Message "Test d'acceptation T-010 absent de la matrice."
Assert-Contains -Content $matrixContent -Expected "app/evidence_governance/application/traceability_metrics.py" -Message "Code applicatif T-010 absent de la matrice."
Assert-Contains -Content $matrixContent -Expected "ADR-006; ADR-010; DDD-ADR-005; DDD-ADR-010" -Message "ADR T-010 absentes de la matrice."
Assert-Contains -Content $testGateContent -Expected 'tests/m006/validate_m006_traceability_acceptance.ps1' -Message "Test d'acceptation T-010 non enrôlé dans scripts/test.ps1."
Assert-Contains -Content $testGateContent -Expected 'tests/m006/validate_m006_traceability_unit.ps1' -Message "Test unitaire T-010 non enrôlé dans scripts/test.ps1."
Assert-Contains -Content $lintGateContent -Expected 'scripts/validate_traceability.ps1' -Message "Validation de traçabilité absente de scripts/lint.ps1."
Assert-Contains -Content $lintGateContent -Expected 'scripts/validate_m006_specification.ps1' -Message "Validation M-006 absente de scripts/lint.ps1."

Assert-File -Path $metricsPath -Message "Publication des métriques EG M-006 absente."
Assert-File -Path $fixturePath -Message "Fixture des métriques EG M-006 absente."

$pythonCode = @'
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, sys.argv[1])

from app.evidence_governance.application.traceability_metrics import (
    ClaimMetricObservation,
    EvidenceGovernanceAuditSignal,
    EvidenceGovernanceMetricsPublisher,
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


repo_root = Path(sys.argv[1])
metrics_path = repo_root / "docs" / "governance" / "m006_claim_metrics.json"
fixture_path = repo_root / "tests" / "m006" / "fixtures" / "m006_claim_metrics_fixture.json"

fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
metrics_payload = json.loads(metrics_path.read_text(encoding="utf-8"))
observations = tuple(
    ClaimMetricObservation(
        claim_id=item["claim_id"],
        claim_version=item["claim_version"],
        status=item["status"],
        direct_evidence_count=item["direct_evidence_count"],
        verification_verdict=item["verification_verdict"],
        reason_codes=tuple(item["reason_codes"]),
        dependency_group_ids=tuple(item["dependency_group_ids"]),
        submitted_at=item["submitted_at"],
        decided_at=item["decided_at"],
        superseded_by_claim_version=item["superseded_by_claim_version"],
    )
    for item in fixture["observations"]
)
expected = EvidenceGovernanceMetricsPublisher().publish(
    fixture_id=fixture["fixture_id"],
    fixture_path="tests/m006/fixtures/m006_claim_metrics_fixture.json",
    observations=observations,
    measured_at=fixture["measured_at"],
).to_payload()

assert_equal(metrics_payload["fixture_id"], expected["fixture_id"], "La fixture publiée doit correspondre à la preuve.")
assert_equal(metrics_payload["claim_count"], expected["claim_count"], "Le nombre de claims publié est incohérent.")
assert_equal(metrics_payload["status_counts"], expected["status_counts"], "Les compteurs de statuts sont incohérents.")
assert_equal(
    metrics_payload["normative_signals"],
    fixture["expected_normative_signals"],
    "Les signaux normatifs publiés ne correspondent pas à la preuve attendue.",
)
assert_equal(metrics_payload["verdict_distribution"], expected["verdict_distribution"], "La distribution des verdicts est incohérente.")
assert_equal(
    metrics_payload["dependency_group_count_distribution"],
    expected["dependency_group_count_distribution"],
    "La distribution des groupes de dépendance est incohérente.",
)
assert_close(
    metrics_payload["average_verification_latency_seconds"],
    expected["average_verification_latency_seconds"],
    "Le délai de vérification publié est incohérent.",
)
for key, value in expected["rates"].items():
    assert_close(metrics_payload["rates"][key], value, f"Le taux publié est incohérent pour {key}.")

assert_false(fixture["forbidden_claim_text"] in repr(metrics_payload), "Les métriques ne doivent pas exposer le claim complet.")
assert_false(fixture["forbidden_evidence_text"] in repr(metrics_payload), "Les métriques ne doivent pas exposer le payload documentaire.")
assert_false("documentary_mention_count" in repr(metrics_payload), "Les métriques ne doivent pas mélanger mention documentaire et confirmation indépendante.")

signal = EvidenceGovernanceAuditSignal.from_metric_snapshot(
    audit_signal_id="EG-AUDIT-M006-T010-ACCEPTANCE",
    trace_id="TRACE-M006-T010-ACCEPTANCE",
    metric_snapshot=EvidenceGovernanceMetricsPublisher().publish(
        fixture_id=fixture["fixture_id"],
        fixture_path="tests/m006/fixtures/m006_claim_metrics_fixture.json",
        observations=observations,
        measured_at=fixture["measured_at"],
    ),
    claim_refs=(
        {
            "claim_id": "CLM-M006-T010-VERIFIED",
            "claim_version": 1,
            "status": "VERIFIED",
            "proposition_hash": "b" * 64,
            "evidence_ref_ids": ("EVS-M006-T010-A",),
            "dependency_group_ids": ("DEP-M006-T010-PRIMARY",),
        },
    ),
    forbidden_documentary_payloads=(fixture["forbidden_claim_text"], fixture["forbidden_evidence_text"]),
)
signal_payload = signal.to_payload()
assert_false(fixture["forbidden_claim_text"] in repr(signal_payload), "Le signal d'audit ne doit pas exposer le claim complet.")
assert_false(fixture["forbidden_evidence_text"] in repr(signal_payload), "Le signal d'audit ne doit pas exposer la preuve complète.")
assert_false("canonical_proposition" in repr(signal_payload), "Le signal d'audit ne doit pas exposer la proposition.")
assert_equal(signal_payload["metric_scope"], "M006_CLAIMS_VERIFIABLES", "La portée du signal doit nommer M-006.")

print("Validation applicative T-010 traçabilité et métriques M-006: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m006_traceability_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-010 traçabilité et métriques M-006: OK"
