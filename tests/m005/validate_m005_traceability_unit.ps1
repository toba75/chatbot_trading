$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import math
import sys

sys.path.insert(0, sys.argv[1])

from app.knowledge_access.application.traceability_metrics import (
    EvaluationQuestion,
    EvaluationResult,
    InitialSearchMetricsPublisher,
    KnowledgeSearchAuditSignal,
    SearchEvaluationCorpus,
    assert_no_full_passage_in_audit_payload,
)


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def assert_false(condition, message):
    if condition:
        raise AssertionError(message)


def assert_close(actual, expected, message):
    if not math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-9):
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_raises(expected_fragment, action):
    try:
        action()
    except ValueError as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


questions = (
    EvaluationQuestion(
        question_id="M005-Q001",
        query_text="Quelle preuve décrit le risque convexe ?",
        relevant_chunk_ids=("KCHK-M005-T010-A", "KCHK-M005-T010-C"),
    ),
    EvaluationQuestion(
        question_id="M005-Q002",
        query_text="Quel passage décrit la liquidité ?",
        relevant_chunk_ids=("KCHK-M005-T010-D",),
    ),
)
corpus = SearchEvaluationCorpus(
    corpus_id="m005_initial_search_eval_fixture_v1",
    fixture_path="tests/m005/fixtures/m005_initial_search_eval_fixture.json",
    questions=questions,
)
results = (
    EvaluationResult(
        question_id="M005-Q001",
        ranked_chunk_ids=("KCHK-M005-T010-A", "KCHK-M005-T010-B", "KCHK-M005-T010-C"),
    ),
    EvaluationResult(
        question_id="M005-Q002",
        ranked_chunk_ids=("KCHK-M005-T010-E", "KCHK-M005-T010-F", "KCHK-M005-T010-D"),
    ),
)

# Given un corpus de questions identifié.
# When les mesures initiales M-005 sont publiées.
# Then Recall@k, MRR et nDCG sont calculées sans devenir des seuils V1.
snapshot = InitialSearchMetricsPublisher().publish(
    corpus=corpus,
    results=results,
    k=3,
    measured_at="2026-06-28T15:00:00Z",
)
payload = snapshot.to_payload()
assert_equal(payload["corpus_id"], "m005_initial_search_eval_fixture_v1", "Le corpus doit être identifié.")
assert_equal(payload["fixture_path"], "tests/m005/fixtures/m005_initial_search_eval_fixture.json", "La fixture doit être identifiée.")
assert_equal(payload["question_count"], 2, "Le nombre de questions doit être publié.")
assert_equal(payload["k"], 3, "Le k de Recall@k doit être publié.")
assert_close(payload["metrics"]["recall_at_k"], 1.0, "Recall@k initial incorrect.")
assert_close(payload["metrics"]["mrr"], 2.0 / 3.0, "MRR initial incorrect.")
assert_close(payload["metrics"]["ndcg"], 0.7098603945740938, "nDCG initial incorrect.")
assert_false(payload["is_v1_acceptance_threshold"], "Les métriques M-005 ne sont pas des seuils V1.")
assert_equal(payload["calibration_milestone"], "M-012", "La calibration seuil doit rester rattachée à M-012.")
assert_false("threshold_value" in repr(payload).lower(), "Aucune valeur de seuil ne doit être publiée avant M-012.")
assert_false("minimum" in repr(payload).lower(), "Aucun minimum d'acceptation ne doit être publié avant M-012.")

# Une métrique sans jeu de questions serait décorative et doit être refusée.
assert_raises(
    "jeu de questions absent",
    lambda: InitialSearchMetricsPublisher().publish(
        corpus=SearchEvaluationCorpus(
            corpus_id="m005_empty",
            fixture_path="tests/m005/fixtures/empty.json",
            questions=(),
        ),
        results=(),
        k=3,
        measured_at="2026-06-28T15:00:00Z",
    ),
)

# Le signal d'audit KA doit exposer les références et les métriques sans texte documentaire complet.
full_passage = "Passage complet documentaire M-005 qui ne doit jamais être journalisé."
signal = KnowledgeSearchAuditSignal.from_metric_snapshot(
    search_trace_id="STRC-M005-T010-000000000000000000000001",
    projection_id="PROJ-M005-T010",
    query_hash="a" * 64,
    result_count=1,
    candidate_refs=(
        {
            "chunk_id": "KCHK-M005-T010-A",
            "document_id": "DOC-M005-T010",
            "canonical_version_id": "CVER-M005-T010-0001",
            "content_hash": "b" * 64,
        },
    ),
    metric_snapshot=snapshot,
    forbidden_full_passages=(full_passage,),
)
signal_payload = signal.to_payload()
assert_equal(signal_payload["signal_name"], "knowledge_search_initial_metrics_published", "Le signal doit être nommé.")
assert_equal(signal_payload["metric_scope"], "INITIAL_M005_NON_DEFINITIVE", "La portée métrique doit être explicite.")
assert_equal(signal_payload["metrics"]["recall_at_k"], payload["metrics"]["recall_at_k"], "Les métriques doivent être reprises.")
assert_equal(signal_payload["candidate_refs"][0]["content_hash"], "b" * 64, "La référence candidate doit porter le hash.")
assert_false(full_passage in repr(signal_payload), "Le signal ne doit pas contenir le passage complet.")
assert_false("verified_claim" in repr(signal_payload).lower(), "Le signal KA ne doit pas publier de claim vérifié.")

assert_raises(
    "result_count incoherent",
    lambda: KnowledgeSearchAuditSignal.from_metric_snapshot(
        search_trace_id="STRC-M005-T010-000000000000000000000002",
        projection_id="PROJ-M005-T010",
        query_hash="a" * 64,
        result_count=2,
        candidate_refs=signal_payload["candidate_refs"],
        metric_snapshot=snapshot,
        forbidden_full_passages=(full_passage,),
    ),
)
assert_raises(
    "contenu documentaire interdit dans candidate_refs",
    lambda: KnowledgeSearchAuditSignal.from_metric_snapshot(
        search_trace_id="STRC-M005-T010-000000000000000000000003",
        projection_id="PROJ-M005-T010",
        query_hash="a" * 64,
        result_count=1,
        candidate_refs=(
            {
                "chunk_id": "KCHK-M005-T010-A",
                "document_id": "DOC-M005-T010",
                "canonical_version_id": "CVER-M005-T010-0001",
                "content_hash": "b" * 64,
                "source_locator": {"item_id": "DOC-M005-T010-P001-I001"},
            },
        ),
        metric_snapshot=snapshot,
        forbidden_full_passages=(full_passage,),
    ),
)

# Un payload de log qui contient un passage complet doit être refusé.
assert_raises(
    "passage complet interdit dans signal d'audit",
    lambda: assert_no_full_passage_in_audit_payload(
        {"message": full_passage},
        forbidden_full_passages=(full_passage,),
    ),
)

print("Tests unitaires T-010 traçabilité et métriques M-005: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m005_traceability_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-010 traçabilité et métriques M-005: OK"
