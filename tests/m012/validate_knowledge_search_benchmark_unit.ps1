$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

repo_root = sys.argv[1]
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from app.contracts.source_references import (
    ACCEPTED_CANONICAL_VERSION_STATUS,
    CanonicalSourceRef,
    SourceLocator,
    SourceLocatorValidationPolicy,
)
from app.evaluation.domain.knowledge_search_benchmark import (
    KNOWLEDGE_DOCUMENT_DIVERSITY,
    KNOWLEDGE_RECALL_AT_10,
    BenchmarkMetric,
    ExpectedPage,
    ExpectedPageSet,
    KnowledgeProjectionSnapshot,
    KnowledgeSearchBenchmark,
    KnowledgeSearchCandidate,
    SearchEvaluationQuestion,
    SearchEvaluationSet,
    calculate_expected_page_accuracy,
    calculate_mrr,
    calculate_ndcg,
    calculate_question_recall_at_k,
)
from app.evaluation.domain.page_annotation import PageReference


HASH = "d" * 64
POLICY_VERSION = "KnowledgeSearchBenchmarkPolicy-1.0"
PROJECTION_VERSION = "KPROJ-M012-KA-UNIT"


def source_policy():
    canonical_ref = CanonicalSourceRef.from_payload(
        {
            "schema_version": "1.0",
            "canonical_source_id": "CSRC-M012-KA-UNIT",
            "document_id": "DOC-M012-KA-UNIT",
            "canonical_version_id": "CVER-M012-KA-UNIT",
            "source_sha256": HASH,
            "canonical_artifact_sha256": HASH,
            "page_count": 10,
            "accepted_at": "2026-07-06T00:00:00Z",
            "quality_policy_version": "DocumentQualityCalibrationPolicy-1.0",
        }
    )
    return SourceLocatorValidationPolicy(
        canonical_sources_by_version_id={"CVER-M012-KA-UNIT": canonical_ref},
        version_statuses_by_version_id={
            "CVER-M012-KA-UNIT": ACCEPTED_CANONICAL_VERSION_STATUS,
        },
        resolvable_item_ids_by_version_id={
            "CVER-M012-KA-UNIT": {f"ITEM-M012-KA-UNIT-{index:04d}": HASH for index in range(1, 500)}
        },
    )


SOURCE_POLICY = source_policy()


def page_ref(page_pdf):
    return PageReference(
        pilot_document_id="PDOC-M012-KA-UNIT",
        source_document_id="DOC-M012-KA-UNIT",
        canonical_version_id="CVER-M012-KA-UNIT",
        page_pdf=page_pdf,
    )


def expected_page(page_pdf, *, source_language="en", relevance_grade=1):
    return ExpectedPage(
        page_ref=page_ref(page_pdf),
        source_language=source_language,
        relevance_grade=relevance_grade,
    )


def locator(page_pdf, item_index):
    return SourceLocator.from_payload(
        {
            "schema_version": "1.0",
            "canonical_version_id": "CVER-M012-KA-UNIT",
            "document_id": "DOC-M012-KA-UNIT",
            "page_pdf": page_pdf,
            "item_id": f"ITEM-M012-KA-UNIT-{item_index:04d}",
            "bbox": [0.1, 0.1, 0.2, 0.2],
            "content_hash": HASH,
        },
        validation_policy=SOURCE_POLICY,
    )


def candidate(rank, page_pdf, item_index):
    return KnowledgeSearchCandidate(
        candidate_id=f"CAND-M012-KA-UNIT-{item_index:04d}",
        search_trace_id="STRC-M012-KA-UNIT",
        projection_id="PROJ-M012-KA-UNIT",
        projection_version=PROJECTION_VERSION,
        rank=rank,
        score="0.500000000000",
        source_locator=locator(page_pdf, item_index),
        content_hash=HASH,
    )


def question(index, expected_pages=None):
    pages = ExpectedPageSet((expected_page((index % 10) + 1),)) if expected_pages is None else expected_pages
    return SearchEvaluationQuestion(
        question_id=f"Q-M012-KA-UNIT-{index:04d}",
        query_text=f"Question unitaire {index:04d}.",
        query_language="fr",
        subthemes=("risque",),
        expected_pages=pages,
    )


def evaluation_set():
    return SearchEvaluationSet(
        evaluation_set_id="SEVAL-M012-KA-UNIT",
        corpus_id="PCORP-M012-KA-UNIT",
        annotation_set_id="ASET-M012-KA-UNIT",
        policy_version=POLICY_VERSION,
        questions=tuple(question(index) for index in range(1, 101)),
    )


def projection(status="SEARCHABLE"):
    return KnowledgeProjectionSnapshot(
        projection_id="PROJ-M012-KA-UNIT",
        projection_version=PROJECTION_VERSION,
        build_fingerprint=HASH,
        index_generation="IDX-M012-KA-UNIT",
        status=status,
    )


def candidates_by_question(search_set):
    payload = {}
    for index, search_question in enumerate(search_set.questions, start=1):
        expected_page_pdf = search_question.expected_pages.pages[0].page_ref.page_pdf
        payload[search_question.question_id] = (candidate(1, expected_page_pdf, index),)
    return payload


def expect_raises(expected_fragment, action):
    try:
        action()
    except Exception as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(
                f"Erreur inattendue. Fragment attendu: {expected_fragment}. Erreur: {exc}"
            ) from exc
        return
    raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


expected = ExpectedPageSet((expected_page(2), expected_page(3)))
candidates = (candidate(1, 9, 301), candidate(2, 2, 302), candidate(3, 3, 303))

assert calculate_question_recall_at_k(expected, candidates, 1) == "0.000000000000"
assert calculate_question_recall_at_k(expected, candidates, 2) == "0.500000000000"
assert calculate_question_recall_at_k(expected, candidates, 20) == "1.000000000000"
assert calculate_mrr(expected, candidates) == "0.500000000000"
assert calculate_ndcg(expected, candidates, 20) == "0.693426403617"
assert calculate_expected_page_accuracy(expected, candidates) == "0.000000000000"
assert calculate_expected_page_accuracy(expected, candidates[1:]) == "1.000000000000"

search_set = evaluation_set()
benchmark = KnowledgeSearchBenchmark(policy_version=POLICY_VERSION)
run = benchmark.measure(
    run_id="KSRUN-M012-KA-UNIT",
    evaluation_set=search_set,
    projection_snapshot=projection(),
    candidates_by_question=candidates_by_question(search_set),
)
assert run.metrics[KNOWLEDGE_RECALL_AT_10].value == "1.000000000000"
assert run.metrics[KNOWLEDGE_DOCUMENT_DIVERSITY].denominator == 100

duplicated = candidates_by_question(search_set)
first_question_id = search_set.questions[0].question_id
first_candidate = duplicated[first_question_id][0]
duplicated[first_question_id] = (first_candidate, first_candidate)
expect_raises(
    "candidat recherche duplique",
    lambda: benchmark.measure(
        run_id="KSRUN-M012-KA-DUP",
        evaluation_set=search_set,
        projection_snapshot=projection(),
        candidates_by_question=duplicated,
    ),
)

missing_result = candidates_by_question(search_set)
del missing_result[first_question_id]
expect_raises(
    "resultat de recherche absent",
    lambda: benchmark.measure(
        run_id="KSRUN-M012-KA-MISSING",
        evaluation_set=search_set,
        projection_snapshot=projection(),
        candidates_by_question=missing_result,
    ),
)

extra_result = candidates_by_question(search_set)
extra_result["Q-M012-KA-UNIT-HORS-JEU"] = (first_candidate,)
expect_raises(
    "resultat de recherche hors jeu evaluation",
    lambda: benchmark.measure(
        run_id="KSRUN-M012-KA-EXTRA",
        evaluation_set=search_set,
        projection_snapshot=projection(),
        candidates_by_question=extra_result,
    ),
)

expect_raises(
    "projection obsolete",
    lambda: benchmark.measure(
        run_id="KSRUN-M012-KA-STALE",
        evaluation_set=search_set,
        projection_snapshot=projection(status="STALE"),
        candidates_by_question=candidates_by_question(search_set),
    ),
)
expect_raises("denominateur metrique invalide", lambda: BenchmarkMetric("bad_metric", "0.0", 0, 0))
expect_raises(
    "question FR vers source EN absente",
    lambda: SearchEvaluationSet(
        evaluation_set_id="SEVAL-M012-KA-NO-FR-EN",
        corpus_id="PCORP-M012-KA-UNIT",
        annotation_set_id="ASET-M012-KA-UNIT",
        policy_version=POLICY_VERSION,
        questions=tuple(
            question(
                index,
                expected_pages=ExpectedPageSet((expected_page((index % 10) + 1, source_language="fr"),)),
            )
            for index in range(1, 101)
        ),
    ),
)

print("Tests unitaires T-007 benchmark recherche de connaissances M-012: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m012_knowledge_search_benchmark_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
try {
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & $pythonExecutable -B $pythonScriptPath $repoRoot 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if ($exitCode -ne 0) {
        throw "Tests unitaires T-007 benchmark recherche de connaissances M-012 invalides. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
