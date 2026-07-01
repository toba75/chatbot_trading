$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$matrixPath = Join-Path $repoRoot "docs/traceability/matrix.md"
$traceabilityValidatorPath = Join-Path $repoRoot "scripts/validate_traceability.ps1"
$testGatePath = Join-Path $repoRoot "scripts/test.ps1"
$lintGatePath = Join-Path $repoRoot "scripts/lint.ps1"
$metricsPath = Join-Path $repoRoot "docs/governance/m008_conversation_metrics.json"
$fixturePath = Join-Path $repoRoot "tests/m008/fixtures/m008_conversation_metrics_fixture.json"

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

# Given les comportements M-008 sont implémentés et testés.
# When la matrice de traçabilité et les gates sont exécutées.
# Then chaque exigence M-008 est rattachée à un test GREEN, une commande de validation et une ADR ou justification explicite.
$matrixContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $matrixPath
$traceabilityValidatorContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $traceabilityValidatorPath
$testGateContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $testGatePath
$lintGateContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $lintGatePath

foreach ($requirementId in @(
    "REQ-M008-001",
    "REQ-M008-002",
    "REQ-M008-003",
    "REQ-M008-004",
    "REQ-M008-005",
    "REQ-M008-006",
    "REQ-M008-007",
    "REQ-M008-008",
    "REQ-M008-009",
    "REQ-M008-010",
    "REQ-M008-011"
)) {
    Assert-Contains -Content $matrixContent -Expected $requirementId -Message "Exigence M-008 absente de la matrice."
    Assert-Contains -Content $traceabilityValidatorContent -Expected $requirementId -Message "Exigence M-008 absente du validateur de traçabilité."
}

foreach ($testPath in @(
    "tests/m008/validate_m008_precondition_acceptance.ps1",
    "tests/m008/validate_m008_precondition_unit.ps1",
    "tests/m008/validate_m008_specification_acceptance.ps1",
    "tests/m008/validate_m008_specification_unit.ps1",
    "tests/m008/validate_conversation_turn_append_only_acceptance.ps1",
    "tests/m008/validate_conversation_turn_append_only_unit.ps1",
    "tests/m008/validate_conversation_context_snapshot_acceptance.ps1",
    "tests/m008/validate_conversation_context_snapshot_unit.ps1",
    "tests/m008/validate_followup_question_resolution_acceptance.ps1",
    "tests/m008/validate_followup_question_resolution_unit.ps1",
    "tests/m008/validate_conversation_mode_routing_acceptance.ps1",
    "tests/m008/validate_conversation_mode_routing_unit.ps1",
    "tests/m008/validate_verified_result_reuse_acceptance.ps1",
    "tests/m008/validate_verified_answer_attachment_unit.ps1",
    "tests/m008/validate_chat_answer_presentation_acceptance.ps1",
    "tests/m008/validate_chat_answer_presentation_unit.ps1",
    "tests/m008/validate_conversation_http_contract_acceptance.ps1",
    "tests/m008/validate_conversation_http_contract_unit.ps1",
    "tests/m008/validate_chat_completions_contract_acceptance.ps1",
    "tests/m008/validate_chat_completions_contract_unit.ps1",
    "tests/m008/validate_m008_traceability_acceptance.ps1",
    "tests/m008/validate_m008_traceability_unit.ps1"
)) {
    Assert-Contains -Content $testGateContent -Expected $testPath -Message "Test M-008 non enrôlé dans scripts/test.ps1."
}

Assert-Contains -Content $matrixContent -Expected "tests/m008/validate_m008_traceability_acceptance.ps1" -Message "Test d'acceptation T-011 absent de la matrice."
Assert-Contains -Content $matrixContent -Expected "app/conversation/application/traceability_metrics.py" -Message "Code applicatif T-011 absent de la matrice."
Assert-Contains -Content $matrixContent -Expected "ADR-010; DDD-ADR-008" -Message "ADR T-011 absentes de la matrice."
Assert-Contains -Content $lintGateContent -Expected "scripts/validate_traceability.ps1" -Message "Validation de traçabilité absente de scripts/lint.ps1."
Assert-Contains -Content $lintGateContent -Expected "scripts/validate_m008_specification.ps1" -Message "Validation M-008 absente de scripts/lint.ps1."

Assert-File -Path $metricsPath -Message "Publication des métriques CV M-008 absente."
Assert-File -Path $fixturePath -Message "Fixture des métriques CV M-008 absente."

$pythonCode = @'
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, sys.argv[1])

from app.conversation.application.traceability_metrics import (
    ConversationAuditSignal,
    ConversationMetricObservation,
    ConversationMetricsPublisher,
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
metrics_path = repo_root / "docs" / "governance" / "m008_conversation_metrics.json"
fixture_path = repo_root / "tests" / "m008" / "fixtures" / "m008_conversation_metrics_fixture.json"

fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
metrics_payload = json.loads(metrics_path.read_text(encoding="utf-8"))
observations = tuple(
    ConversationMetricObservation(
        trace_id=item["trace_id"],
        conversation_id=item["conversation_id"],
        turn_id=item["turn_id"],
        event_type=item["event_type"],
        mode=item["mode"],
        support_status=item["support_status"],
        public_error_code=item["public_error_code"],
        payload_hash=item["payload_hash"],
        occurred_at=item["occurred_at"],
    )
    for item in fixture["observations"]
)
expected = ConversationMetricsPublisher().publish(
    fixture_id=fixture["fixture_id"],
    fixture_path="tests/m008/fixtures/m008_conversation_metrics_fixture.json",
    observations=observations,
    measured_at=fixture["measured_at"],
).to_payload()

assert_equal(metrics_payload["fixture_id"], expected["fixture_id"], "La fixture publiée doit correspondre à la preuve.")
assert_equal(metrics_payload["observation_count"], expected["observation_count"], "Le nombre d'observations publié est incohérent.")
assert_equal(metrics_payload["normative_signals"], fixture["expected_normative_signals"], "Les signaux normatifs publiés ne correspondent pas à la preuve attendue.")
assert_equal(metrics_payload["mode_counts"], expected["mode_counts"], "Les compteurs de modes sont incohérents.")
assert_equal(metrics_payload["support_status_counts"], expected["support_status_counts"], "Les compteurs de statuts documentaires sont incohérents.")
assert_equal(metrics_payload["public_error_code_counts"], expected["public_error_code_counts"], "Les compteurs d'erreurs publiques sont incohérents.")
assert_equal(metrics_payload["clarification_required_total"], expected["clarification_required_total"], "Le compteur d'ambiguïtés est incohérent.")
assert_close(metrics_payload["archive_rate"], expected["archive_rate"], "Le taux d'archive est incohérent.")

for forbidden_payload in (
    fixture["forbidden_user_message"],
    fixture["forbidden_prompt"],
    fixture["forbidden_document_text"],
):
    assert_false(forbidden_payload in repr(metrics_payload), "Les métriques ne doivent pas exposer de payload sensible.")
assert_false("answer_text" in repr(metrics_payload), "Les métriques ne doivent pas exposer une réponse complète.")
assert_false("raw_history" in repr(metrics_payload), "Les métriques ne doivent pas exposer l'historique brut.")

signal = ConversationAuditSignal.from_metric_snapshot(
    audit_signal_id="CV-AUDIT-M008-T011-ACCEPTANCE",
    trace_id="TRACE-M008-T011-ACCEPTANCE",
    metric_snapshot=ConversationMetricsPublisher().publish(
        fixture_id=fixture["fixture_id"],
        fixture_path="tests/m008/fixtures/m008_conversation_metrics_fixture.json",
        observations=observations,
        measured_at=fixture["measured_at"],
    ),
    conversation_refs=(
        {
            "conversation_id": "CONV-M008-T011-A",
            "conversation_status": "ARCHIVED",
            "turn_count": 2,
            "last_turn_id": "TURN-M008-T011-B",
            "last_question_hash": "f" * 64,
        },
    ),
    forbidden_sensitive_payloads=(
        fixture["forbidden_user_message"],
        fixture["forbidden_prompt"],
        fixture["forbidden_document_text"],
    ),
)
signal_payload = signal.to_payload()
assert_equal(signal_payload["metric_scope"], "M008_PRODUCT_CONVERSATION", "La portée du signal doit nommer M-008.")
assert_false(fixture["forbidden_user_message"] in repr(signal_payload), "Le signal d'audit ne doit pas exposer le message complet.")
assert_false(fixture["forbidden_prompt"] in repr(signal_payload), "Le signal d'audit ne doit pas exposer le prompt.")
assert_false(fixture["forbidden_document_text"] in repr(signal_payload), "Le signal d'audit ne doit pas exposer le texte documentaire complet.")
assert_false("'message':" in repr(signal_payload), "Le signal d'audit ne doit pas exposer de message brut.")

assert_raises(
    "payload sensible interdit dans signal d'audit",
    lambda: assert_no_sensitive_payload_in_audit_payload(
        {"prompt": fixture["forbidden_prompt"]},
        forbidden_sensitive_payloads=(
            fixture["forbidden_user_message"],
            fixture["forbidden_prompt"],
            fixture["forbidden_document_text"],
        ),
    ),
)

print("Validation applicative T-011 traçabilité et métriques M-008: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m008_traceability_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-011 traçabilité et métriques M-008: OK"
