$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$matrixPath = Join-Path $repoRoot "docs/traceability/matrix.md"
$traceabilityValidatorPath = Join-Path $repoRoot "scripts/validate_traceability.ps1"
$testGatePath = Join-Path $repoRoot "scripts/test.ps1"
$metricsPath = Join-Path $repoRoot "docs/governance/m005_initial_search_metrics.json"
$fixturePath = Join-Path $repoRoot "tests/m005/fixtures/m005_initial_search_eval_fixture.json"

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

# Given les comportements M-005 sont implémentés et testés.
# When les gates de clôture M-005 s'exécutent.
# Then chaque exigence M-005 est reliée à une preuve et les métriques initiales sont publiées sans seuil V1.
$matrixContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $matrixPath
$traceabilityValidatorContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $traceabilityValidatorPath
$testGateContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $testGatePath

foreach ($requirementId in @(
    "REQ-M005-001",
    "REQ-M005-002",
    "REQ-M005-003",
    "REQ-M005-004",
    "REQ-M005-005",
    "REQ-M005-006",
    "REQ-M005-007",
    "REQ-M005-008",
    "REQ-M005-009",
    "REQ-M005-010"
)) {
    Assert-Contains -Content $matrixContent -Expected $requirementId -Message "Exigence M-005 absente de la matrice."
    Assert-Contains -Content $traceabilityValidatorContent -Expected $requirementId -Message "Exigence M-005 absente du validateur de traçabilité."
}

Assert-Contains -Content $matrixContent -Expected "tests/m005/validate_m005_traceability_acceptance.ps1" -Message "Test d'acceptation T-010 absent de la matrice."
Assert-Contains -Content $matrixContent -Expected "app/knowledge_access/application/traceability_metrics.py" -Message "Code applicatif T-010 absent de la matrice."
Assert-Contains -Content $matrixContent -Expected "ADR-005; ADR-006; ADR-010; DDD-ADR-004; DDD-ADR-008" -Message "ADR T-010 absentes de la matrice."
Assert-Contains -Content $testGateContent -Expected 'tests/m005/validate_m005_traceability_acceptance.ps1' -Message "Test d'acceptation T-010 non enrôlé dans scripts/test.ps1."
Assert-Contains -Content $testGateContent -Expected 'tests/m005/validate_m005_traceability_unit.ps1' -Message "Test unitaire T-010 non enrôlé dans scripts/test.ps1."

Assert-File -Path $metricsPath -Message "Publication des métriques initiales M-005 absente."
Assert-File -Path $fixturePath -Message "Fixture d'évaluation initiale M-005 absente."

$pythonCode = @'
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, sys.argv[1])

from app.knowledge_access.application.traceability_metrics import (
    EvaluationQuestion,
    EvaluationResult,
    InitialSearchMetricsPublisher,
    KnowledgeSearchAuditSignal,
    SearchEvaluationCorpus,
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
metrics_path = repo_root / "docs" / "governance" / "m005_initial_search_metrics.json"
fixture_path = repo_root / "tests" / "m005" / "fixtures" / "m005_initial_search_eval_fixture.json"

fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
metrics_payload = json.loads(metrics_path.read_text(encoding="utf-8"))

questions = tuple(
    EvaluationQuestion(
        question_id=item["question_id"],
        query_text=item["query_text"],
        relevant_chunk_ids=tuple(item["relevant_chunk_ids"]),
    )
    for item in fixture["questions"]
)
results = tuple(
    EvaluationResult(
        question_id=item["question_id"],
        ranked_chunk_ids=tuple(item["ranked_chunk_ids"]),
    )
    for item in fixture["results"]
)
corpus = SearchEvaluationCorpus(
    corpus_id=fixture["corpus_id"],
    fixture_path="tests/m005/fixtures/m005_initial_search_eval_fixture.json",
    questions=questions,
)
expected = InitialSearchMetricsPublisher().publish(
    corpus=corpus,
    results=results,
    k=fixture["k"],
    measured_at=metrics_payload["measured_at"],
).to_payload()

assert_equal(metrics_payload["corpus_id"], expected["corpus_id"], "Le corpus publié doit correspondre à la fixture.")
assert_equal(metrics_payload["fixture_path"], expected["fixture_path"], "Le chemin de fixture doit être publié.")
assert_equal(metrics_payload["question_count"], expected["question_count"], "Le nombre de questions doit être publié.")
assert_equal(metrics_payload["k"], expected["k"], "Le k doit être publié.")
assert_close(metrics_payload["metrics"]["recall_at_k"], expected["metrics"]["recall_at_k"], "Recall@k publié incohérent.")
assert_close(metrics_payload["metrics"]["mrr"], expected["metrics"]["mrr"], "MRR publié incohérent.")
assert_close(metrics_payload["metrics"]["ndcg"], expected["metrics"]["ndcg"], "nDCG publié incohérent.")
assert_false(metrics_payload["is_v1_acceptance_threshold"], "La mesure M-005 ne doit pas devenir un seuil V1.")
assert_equal(metrics_payload["calibration_milestone"], "M-012", "La calibration doit rester prévue en M-012.")
assert_false("threshold_value" in repr(metrics_payload).lower(), "Aucune valeur de seuil ne doit être publiée avant M-012.")
assert_false("minimum" in repr(metrics_payload).lower(), "Aucun minimum ne doit être publié avant M-012.")

full_passage = fixture["forbidden_full_passage"]
signal = KnowledgeSearchAuditSignal.from_metric_snapshot(
    search_trace_id="STRC-M005-T010-ACCEPTANCE-000000000001",
    projection_id="PROJ-M005-T010",
    query_hash="c" * 64,
    result_count=len(fixture["results"]),
    candidate_refs=tuple(fixture["candidate_refs"]),
    metric_snapshot=InitialSearchMetricsPublisher().publish(
        corpus=corpus,
        results=results,
        k=fixture["k"],
        measured_at=metrics_payload["measured_at"],
    ),
    forbidden_full_passages=(full_passage,),
)
signal_payload = signal.to_payload()
assert_false(full_passage in repr(signal_payload), "Le signal d'audit ne doit pas contenir de passage documentaire complet.")
assert_false("verified_claim" in repr(signal_payload).lower(), "Le signal d'audit KA ne doit pas contenir de claim vérifié.")
assert_equal(signal_payload["metric_scope"], "INITIAL_M005_NON_DEFINITIVE", "La portée non définitive doit être publiée.")

print("Validation applicative T-010 traçabilité et métriques M-005: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m005_traceability_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-010 traçabilité et métriques M-005: OK"
