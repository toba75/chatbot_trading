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
    EXPECTED_PAGE_ACCURACY,
    FR_TO_EN_RECALL_AT_10,
    KNOWLEDGE_DOCUMENT_DIVERSITY,
    KNOWLEDGE_MRR,
    KNOWLEDGE_NDCG,
    KNOWLEDGE_RECALL_AT_5,
    KNOWLEDGE_RECALL_AT_10,
    KNOWLEDGE_RECALL_AT_20,
    KNOWLEDGE_SUBTHEME_COVERAGE,
    ExpectedPage,
    ExpectedPageSet,
    KnowledgeProjectionSnapshot,
    KnowledgeSearchBenchmark,
    KnowledgeSearchCandidate,
    SearchEvaluationQuestion,
    SearchEvaluationSet,
)
from app.evaluation.domain.page_annotation import PageReference


HASH = "c" * 64
POLICY_VERSION = "KnowledgeSearchBenchmarkPolicy-1.0"
PROJECTION_VERSION = "KPROJ-M012-KA-0001"


def source_policy():
    canonical_ref = CanonicalSourceRef.from_payload(
        {
            "schema_version": "1.0",
            "canonical_source_id": "CSRC-M012-KA-0001",
            "document_id": "DOC-M012-KA-0001",
            "canonical_version_id": "CVER-M012-KA-0001",
            "source_sha256": HASH,
            "canonical_artifact_sha256": HASH,
            "page_count": 10,
            "accepted_at": "2026-07-06T00:00:00Z",
            "quality_policy_version": "DocumentQualityCalibrationPolicy-1.0",
        }
    )
    return SourceLocatorValidationPolicy(
        canonical_sources_by_version_id={"CVER-M012-KA-0001": canonical_ref},
        version_statuses_by_version_id={
            "CVER-M012-KA-0001": ACCEPTED_CANONICAL_VERSION_STATUS,
        },
        resolvable_item_ids_by_version_id={
            "CVER-M012-KA-0001": {f"ITEM-M012-KA-{index:04d}": HASH for index in range(1, 400)}
        },
    )


SOURCE_POLICY = source_policy()


def page_ref(page_pdf):
    return PageReference(
        pilot_document_id="PDOC-M012-KA-0001",
        source_document_id="DOC-M012-KA-0001",
        canonical_version_id="CVER-M012-KA-0001",
        page_pdf=page_pdf,
    )


def expected_page(page_pdf, *, source_language="en"):
    return ExpectedPage(
        page_ref=page_ref(page_pdf),
        source_language=source_language,
        relevance_grade=1,
    )


def question(index):
    subtheme = ("liquidite", "marge", "risque", "croissance")[index % 4]
    return SearchEvaluationQuestion(
        question_id=f"Q-M012-KA-{index:04d}",
        query_text=f"Quelle information financiere faut-il retrouver pour le cas {index:04d} ?",
        query_language="fr",
        subthemes=(subtheme,),
        expected_pages=ExpectedPageSet((expected_page((index % 10) + 1),)),
    )


def evaluation_set(count=100):
    return SearchEvaluationSet(
        evaluation_set_id="SEVAL-M012-KA-0001",
        corpus_id="PCORP-M012-KA-0001",
        annotation_set_id="ASET-M012-KA-0001",
        policy_version=POLICY_VERSION,
        questions=tuple(question(index) for index in range(1, count + 1)),
    )


def locator(page_pdf, item_index):
    return SourceLocator.from_payload(
        {
            "schema_version": "1.0",
            "canonical_version_id": "CVER-M012-KA-0001",
            "document_id": "DOC-M012-KA-0001",
            "page_pdf": page_pdf,
            "item_id": f"ITEM-M012-KA-{item_index:04d}",
            "bbox": [0.1, 0.1, 0.2, 0.2],
            "content_hash": HASH,
        },
        validation_policy=SOURCE_POLICY,
    )


def candidate(question_id, rank, page_pdf, *, suffix):
    return KnowledgeSearchCandidate(
        candidate_id=f"CAND-{question_id}-{suffix}",
        search_trace_id=f"STRC-{question_id}",
        projection_id="PROJ-M012-KA-0001",
        projection_version=PROJECTION_VERSION,
        rank=rank,
        score="0.900000000000",
        source_locator=locator(page_pdf, suffix),
        content_hash=HASH,
    )


def candidates_for_question(search_question, index):
    expected_page_pdf = search_question.expected_pages.pages[0].page_ref.page_pdf
    wrong_page_pdf = (expected_page_pdf % 10) + 1
    candidates = []
    if index <= 70:
        candidates.append(candidate(search_question.question_id, 1, expected_page_pdf, suffix=index))
    else:
        candidates.append(candidate(search_question.question_id, 1, wrong_page_pdf, suffix=index))

    if 71 <= index <= 90:
        candidates.append(candidate(search_question.question_id, 8, expected_page_pdf, suffix=index + 100))
    if 91 <= index <= 95:
        candidates.append(candidate(search_question.question_id, 15, expected_page_pdf, suffix=index + 200))
    return tuple(candidates)


def candidates_by_question(search_set):
    return {
        search_question.question_id: candidates_for_question(search_question, index)
        for index, search_question in enumerate(search_set.questions, start=1)
    }


def projection(status="SEARCHABLE", version=PROJECTION_VERSION):
    return KnowledgeProjectionSnapshot(
        projection_id="PROJ-M012-KA-0001",
        projection_version=version,
        build_fingerprint=HASH,
        index_generation="IDX-M012-KA-0001",
        status=status,
    )


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


# Given un jeu de 100 à 300 questions avec pages attendues.
search_set = evaluation_set()
benchmark = KnowledgeSearchBenchmark(policy_version=POLICY_VERSION)

# When la recherche de connaissances est exécutée sur la projection versionnée du corpus pilote.
run = benchmark.measure(
    run_id="KSRUN-M012-KA-0001",
    evaluation_set=search_set,
    projection_snapshot=projection(),
    candidates_by_question=candidates_by_question(search_set),
)

# Then les métriques de rappel, rang, diversité et couverture sont publiées avec les échecs visibles.
expected_metrics = {
    KNOWLEDGE_RECALL_AT_5,
    KNOWLEDGE_RECALL_AT_10,
    KNOWLEDGE_RECALL_AT_20,
    KNOWLEDGE_MRR,
    KNOWLEDGE_NDCG,
    EXPECTED_PAGE_ACCURACY,
    KNOWLEDGE_DOCUMENT_DIVERSITY,
    KNOWLEDGE_SUBTHEME_COVERAGE,
    FR_TO_EN_RECALL_AT_10,
}
assert expected_metrics.issubset(run.metrics.keys())
assert run.question_count == 100
assert run.metrics[KNOWLEDGE_RECALL_AT_5].value == "0.700000000000"
assert run.metrics[KNOWLEDGE_RECALL_AT_10].value == "0.900000000000"
assert run.metrics[KNOWLEDGE_RECALL_AT_20].value == "0.950000000000"
assert run.metrics[EXPECTED_PAGE_ACCURACY].value == "0.700000000000"
assert run.metrics[FR_TO_EN_RECALL_AT_10].value == "0.900000000000"
assert run.metrics[KNOWLEDGE_SUBTHEME_COVERAGE].value == "1.000000000000"
assert run.metrics[KNOWLEDGE_MRR].denominator == 100
assert run.metrics[KNOWLEDGE_NDCG].denominator == 100
assert run.question_results[-1].first_relevant_rank is None
assert run.question_results[-1].failure_reason == "page attendue absente des 20 premiers candidats"
assert run.question_results[0].candidates[0].source_locator.item_id == "ITEM-M012-KA-0001"

expect_raises("entre 100 et 300 questions", lambda: evaluation_set(99))
expect_raises("entre 100 et 300 questions", lambda: evaluation_set(301))
expect_raises(
    "page attendue absente",
    lambda: SearchEvaluationQuestion(
        question_id="Q-M012-KA-EMPTY",
        query_text="Question sans page attendue.",
        query_language="fr",
        subthemes=("risque",),
        expected_pages=ExpectedPageSet(()),
    ),
)
expect_raises(
    "source_locator requis",
    lambda: KnowledgeSearchCandidate(
        candidate_id="CAND-M012-KA-BAD",
        search_trace_id="STRC-M012-KA-BAD",
        projection_id="PROJ-M012-KA-0001",
        projection_version=PROJECTION_VERSION,
        rank=1,
        score="0.100000000000",
        source_locator=None,
        content_hash=HASH,
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
expect_raises(
    "version de projection absente",
    lambda: benchmark.measure(
        run_id="KSRUN-M012-KA-NOVERSION",
        evaluation_set=search_set,
        projection_snapshot=projection(version=""),
        candidates_by_question=candidates_by_question(search_set),
    ),
)

print("Test d'acceptation T-007 benchmark recherche de connaissances M-012: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m012_knowledge_search_benchmark_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Test d'acceptation T-007 benchmark recherche de connaissances M-012 invalide. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
