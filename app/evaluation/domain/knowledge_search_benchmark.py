"""Benchmark de recherche de connaissances KA M-012."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
import math
from typing import Any

from app.contracts.source_references import SourceLocator
from app.evaluation.domain.page_annotation import PageReference


KNOWLEDGE_RECALL_AT_5 = "knowledge_recall_at_5"
KNOWLEDGE_RECALL_AT_10 = "knowledge_recall_at_10"
KNOWLEDGE_RECALL_AT_20 = "knowledge_recall_at_20"
KNOWLEDGE_MRR = "knowledge_mrr"
KNOWLEDGE_NDCG = "knowledge_ndcg"
EXPECTED_PAGE_ACCURACY = "knowledge_expected_page_accuracy"
KNOWLEDGE_DOCUMENT_DIVERSITY = "knowledge_document_diversity"
KNOWLEDGE_SUBTHEME_COVERAGE = "knowledge_subtheme_coverage"
FR_TO_EN_RECALL_AT_10 = "knowledge_fr_to_en_recall_at_10"

REQUIRED_KNOWLEDGE_SEARCH_METRICS = frozenset(
    {
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
)

SEARCHABLE = "SEARCHABLE"
STALE = "STALE"
_EXPECTED_PROJECTION_STATUSES = frozenset({SEARCHABLE, STALE, "RETIRED", "FAILED"})
_DECIMAL_SCALE = Decimal("0.000000000001")


@dataclass(frozen=True)
class BenchmarkMetric:
    name: str
    value: str
    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _required_text_value(self.name, "metric_name"))
        object.__setattr__(self, "value", _required_decimal_text(self.value, "valeur metrique invalide"))
        object.__setattr__(self, "numerator", _required_non_negative_integer(self.numerator, "metric_numerator"))
        object.__setattr__(self, "denominator", _required_metric_denominator(self.denominator))


@dataclass(frozen=True)
class ExpectedPage:
    page_ref: PageReference
    source_language: str
    relevance_grade: int

    def __post_init__(self) -> None:
        if not isinstance(self.page_ref, PageReference):
            raise ValueError("PageReference requise")
        object.__setattr__(self, "source_language", _required_language(self.source_language, "source_language"))
        object.__setattr__(self, "relevance_grade", _required_positive_integer(self.relevance_grade, "relevance_grade"))

    @property
    def key(self) -> tuple[str, str, int]:
        return _page_key(self.page_ref)


@dataclass(frozen=True)
class ExpectedPageSet:
    pages: tuple[ExpectedPage, ...]

    def __init__(self, pages: Sequence[ExpectedPage]) -> None:
        if isinstance(pages, str) or not isinstance(pages, Sequence):
            raise ValueError("pages attendues invalides")
        page_tuple = tuple(pages)
        if len(page_tuple) == 0:
            raise ValueError("page attendue absente")
        keys: set[tuple[str, str, int]] = set()
        for page in page_tuple:
            if not isinstance(page, ExpectedPage):
                raise ValueError("ExpectedPage requise")
            if page.key in keys:
                raise ValueError("page attendue dupliquee")
            keys.add(page.key)
        object.__setattr__(self, "pages", page_tuple)

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def keys(self) -> frozenset[tuple[str, str, int]]:
        return frozenset(page.key for page in self.pages)


@dataclass(frozen=True)
class SearchEvaluationQuestion:
    question_id: str
    query_text: str
    query_language: str
    subthemes: tuple[str, ...]
    expected_pages: ExpectedPageSet

    def __init__(
        self,
        *,
        question_id: str,
        query_text: str,
        query_language: str,
        subthemes: Sequence[str],
        expected_pages: ExpectedPageSet,
    ) -> None:
        object.__setattr__(self, "question_id", _required_text_value(question_id, "question_id"))
        object.__setattr__(self, "query_text", _required_text_value(query_text, "query_text"))
        object.__setattr__(self, "query_language", _required_language(query_language, "query_language"))
        object.__setattr__(self, "subthemes", _required_text_tuple(subthemes, "subthemes"))
        if not isinstance(expected_pages, ExpectedPageSet):
            raise ValueError("ExpectedPageSet requis")
        object.__setattr__(self, "expected_pages", expected_pages)


@dataclass(frozen=True)
class SearchEvaluationSet:
    evaluation_set_id: str
    corpus_id: str
    annotation_set_id: str
    policy_version: str
    questions: tuple[SearchEvaluationQuestion, ...]

    def __init__(
        self,
        *,
        evaluation_set_id: str,
        corpus_id: str,
        annotation_set_id: str,
        policy_version: str,
        questions: Sequence[SearchEvaluationQuestion],
    ) -> None:
        object.__setattr__(self, "evaluation_set_id", _required_text_value(evaluation_set_id, "evaluation_set_id"))
        object.__setattr__(self, "corpus_id", _required_text_value(corpus_id, "corpus_id"))
        object.__setattr__(self, "annotation_set_id", _required_text_value(annotation_set_id, "annotation_set_id"))
        object.__setattr__(self, "policy_version", _required_text_value(policy_version, "policy_version"))
        question_tuple = _required_question_tuple(questions)
        if not 100 <= len(question_tuple) <= 300:
            raise ValueError("jeu d'evaluation entre 100 et 300 questions requis")
        question_ids: set[str] = set()
        for question in question_tuple:
            if question.question_id in question_ids:
                raise ValueError("question d'evaluation dupliquee")
            question_ids.add(question.question_id)
        if _fr_to_en_denominator(question_tuple) == 0:
            raise ValueError("question FR vers source EN absente")
        object.__setattr__(self, "questions", question_tuple)

    @property
    def question_count(self) -> int:
        return len(self.questions)


@dataclass(frozen=True)
class KnowledgeProjectionSnapshot:
    projection_id: str
    projection_version: str
    build_fingerprint: str
    index_generation: str
    status: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "projection_id", _required_text_value(self.projection_id, "projection_id"))
        object.__setattr__(
            self,
            "projection_version",
            _required_projection_version(self.projection_version),
        )
        object.__setattr__(self, "build_fingerprint", _required_hash(self.build_fingerprint, "build_fingerprint"))
        object.__setattr__(self, "index_generation", _required_text_value(self.index_generation, "index_generation"))
        if not self.index_generation.startswith("IDX-"):
            raise ValueError("index_generation invalide")
        object.__setattr__(self, "status", _required_projection_status(self.status))

    def ensure_promotable(self) -> None:
        if self.status == STALE:
            raise ValueError("projection obsolete")
        if self.status != SEARCHABLE:
            raise ValueError("projection non recherchable")


@dataclass(frozen=True)
class KnowledgeSearchCandidate:
    candidate_id: str
    search_trace_id: str
    projection_id: str
    projection_version: str
    rank: int
    score: str
    source_locator: SourceLocator
    content_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidate_id", _required_text_value(self.candidate_id, "candidate_id"))
        object.__setattr__(self, "search_trace_id", _required_text_value(self.search_trace_id, "search_trace_id"))
        object.__setattr__(self, "projection_id", _required_text_value(self.projection_id, "projection_id"))
        object.__setattr__(self, "projection_version", _required_projection_version(self.projection_version))
        object.__setattr__(self, "rank", _required_positive_integer(self.rank, "rank"))
        object.__setattr__(self, "score", _required_decimal_text(self.score, "score invalide"))
        if not isinstance(self.source_locator, SourceLocator):
            raise ValueError("source_locator requis")
        object.__setattr__(self, "content_hash", _required_hash(self.content_hash, "content_hash"))
        if self.source_locator.content_hash != self.content_hash:
            raise ValueError("content_hash incoherent avec SourceLocator")

    @property
    def page_key(self) -> tuple[str, str, int]:
        return (
            self.source_locator.document_id,
            self.source_locator.canonical_version_id,
            self.source_locator.page_pdf,
        )

    @property
    def locator_key(self) -> tuple[str, str, int, str]:
        return (
            self.source_locator.document_id,
            self.source_locator.canonical_version_id,
            self.source_locator.page_pdf,
            self.source_locator.item_id,
        )


@dataclass(frozen=True)
class KnowledgeQuestionBenchmarkResult:
    question_id: str
    expected_page_count: int
    candidate_count: int
    first_relevant_rank: int | None
    metrics: Mapping[str, BenchmarkMetric]
    candidates: tuple[KnowledgeSearchCandidate, ...]
    failure_reason: str | None


@dataclass(frozen=True)
class KnowledgeSearchBenchmarkRun:
    run_id: str
    evaluation_set_id: str
    corpus_id: str
    annotation_set_id: str
    projection_id: str
    projection_version: str
    policy_version: str
    question_count: int
    metrics: Mapping[str, BenchmarkMetric]
    question_results: tuple[KnowledgeQuestionBenchmarkResult, ...]


@dataclass(frozen=True)
class KnowledgeSearchBenchmark:
    policy_version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_version", _required_text_value(self.policy_version, "policy_version"))

    def measure(
        self,
        *,
        run_id: str,
        evaluation_set: SearchEvaluationSet,
        projection_snapshot: KnowledgeProjectionSnapshot,
        candidates_by_question: Mapping[str, Sequence[KnowledgeSearchCandidate]],
    ) -> KnowledgeSearchBenchmarkRun:
        _required_text_value(run_id, "run_id")
        if not isinstance(evaluation_set, SearchEvaluationSet):
            raise ValueError("SearchEvaluationSet requis")
        if evaluation_set.policy_version != self.policy_version:
            raise ValueError("policy_version benchmark incoherente")
        if not isinstance(projection_snapshot, KnowledgeProjectionSnapshot):
            raise ValueError("KnowledgeProjectionSnapshot requis")
        projection_snapshot.ensure_promotable()
        if not isinstance(candidates_by_question, Mapping):
            raise ValueError("resultats de recherche invalides")

        question_results = tuple(
            self._measure_question(
                question=question,
                projection_snapshot=projection_snapshot,
                candidates=_candidates_for_question(question.question_id, candidates_by_question),
            )
            for question in evaluation_set.questions
        )
        metrics = _aggregate_run_metrics(evaluation_set.questions, question_results)
        _ensure_required_metrics(metrics)
        return KnowledgeSearchBenchmarkRun(
            run_id=run_id,
            evaluation_set_id=evaluation_set.evaluation_set_id,
            corpus_id=evaluation_set.corpus_id,
            annotation_set_id=evaluation_set.annotation_set_id,
            projection_id=projection_snapshot.projection_id,
            projection_version=projection_snapshot.projection_version,
            policy_version=self.policy_version,
            question_count=evaluation_set.question_count,
            metrics=metrics,
            question_results=question_results,
        )

    def _measure_question(
        self,
        *,
        question: SearchEvaluationQuestion,
        projection_snapshot: KnowledgeProjectionSnapshot,
        candidates: Sequence[KnowledgeSearchCandidate],
    ) -> KnowledgeQuestionBenchmarkResult:
        candidate_tuple = _validated_candidates(candidates, projection_snapshot=projection_snapshot)
        metrics = {
            KNOWLEDGE_RECALL_AT_5: BenchmarkMetric(
                KNOWLEDGE_RECALL_AT_5,
                calculate_question_recall_at_k(question.expected_pages, candidate_tuple, 5),
                _metric_numerator(calculate_question_recall_at_k(question.expected_pages, candidate_tuple, 5)),
                1,
            ),
            KNOWLEDGE_RECALL_AT_10: BenchmarkMetric(
                KNOWLEDGE_RECALL_AT_10,
                calculate_question_recall_at_k(question.expected_pages, candidate_tuple, 10),
                _metric_numerator(calculate_question_recall_at_k(question.expected_pages, candidate_tuple, 10)),
                1,
            ),
            KNOWLEDGE_RECALL_AT_20: BenchmarkMetric(
                KNOWLEDGE_RECALL_AT_20,
                calculate_question_recall_at_k(question.expected_pages, candidate_tuple, 20),
                _metric_numerator(calculate_question_recall_at_k(question.expected_pages, candidate_tuple, 20)),
                1,
            ),
            KNOWLEDGE_MRR: BenchmarkMetric(
                KNOWLEDGE_MRR,
                calculate_mrr(question.expected_pages, candidate_tuple),
                _metric_numerator(calculate_mrr(question.expected_pages, candidate_tuple)),
                1,
            ),
            KNOWLEDGE_NDCG: BenchmarkMetric(
                KNOWLEDGE_NDCG,
                calculate_ndcg(question.expected_pages, candidate_tuple, 20),
                _metric_numerator(calculate_ndcg(question.expected_pages, candidate_tuple, 20)),
                1,
            ),
            EXPECTED_PAGE_ACCURACY: BenchmarkMetric(
                EXPECTED_PAGE_ACCURACY,
                calculate_expected_page_accuracy(question.expected_pages, candidate_tuple),
                _metric_numerator(calculate_expected_page_accuracy(question.expected_pages, candidate_tuple)),
                1,
            ),
            KNOWLEDGE_DOCUMENT_DIVERSITY: BenchmarkMetric(
                KNOWLEDGE_DOCUMENT_DIVERSITY,
                _document_diversity(candidate_tuple),
                _metric_numerator(_document_diversity(candidate_tuple)),
                1,
            ),
        }
        first_relevant_rank = _first_relevant_rank(question.expected_pages, candidate_tuple)
        return KnowledgeQuestionBenchmarkResult(
            question_id=question.question_id,
            expected_page_count=question.expected_pages.page_count,
            candidate_count=len(candidate_tuple),
            first_relevant_rank=first_relevant_rank,
            metrics=metrics,
            candidates=candidate_tuple,
            failure_reason=None if first_relevant_rank is not None and first_relevant_rank <= 20 else "page attendue absente des 20 premiers candidats",
        )


def calculate_question_recall_at_k(
    expected_pages: ExpectedPageSet,
    candidates: Sequence[KnowledgeSearchCandidate],
    k: int,
) -> str:
    _ensure_expected_pages(expected_pages)
    top_candidates = _top_k_candidates(candidates, k)
    found_pages = {candidate.page_key for candidate in top_candidates if candidate.page_key in expected_pages.keys}
    return _metric_value(len(found_pages), expected_pages.page_count)


def calculate_mrr(expected_pages: ExpectedPageSet, candidates: Sequence[KnowledgeSearchCandidate]) -> str:
    rank = _first_relevant_rank(expected_pages, candidates)
    if rank is None:
        return _format_decimal(Decimal(0))
    return _format_decimal(Decimal(1) / Decimal(rank))


def calculate_ndcg(
    expected_pages: ExpectedPageSet,
    candidates: Sequence[KnowledgeSearchCandidate],
    k: int,
) -> str:
    _ensure_expected_pages(expected_pages)
    _required_positive_integer(k, "k")
    relevance_by_page = {page.key: page.relevance_grade for page in expected_pages.pages}
    dcg = 0.0
    for candidate in _top_k_candidates(candidates, k):
        grade = relevance_by_page.get(candidate.page_key, 0)
        if grade > 0:
            dcg += grade / math.log2(candidate.rank + 1)
    ideal_grades = sorted((page.relevance_grade for page in expected_pages.pages), reverse=True)[:k]
    idcg = sum(grade / math.log2(index + 1) for index, grade in enumerate(ideal_grades, start=1))
    if idcg <= 0:
        raise ValueError("denominateur metrique invalide")
    return _format_decimal(Decimal(str(dcg / idcg)))


def calculate_expected_page_accuracy(
    expected_pages: ExpectedPageSet,
    candidates: Sequence[KnowledgeSearchCandidate],
) -> str:
    _ensure_expected_pages(expected_pages)
    parsed_candidates = _sorted_candidates(candidates)
    if len(parsed_candidates) == 0:
        return _format_decimal(Decimal(0))
    return _format_decimal(Decimal(1) if parsed_candidates[0].page_key in expected_pages.keys else Decimal(0))


def _aggregate_run_metrics(
    questions: Sequence[SearchEvaluationQuestion],
    question_results: Sequence[KnowledgeQuestionBenchmarkResult],
) -> Mapping[str, BenchmarkMetric]:
    if len(questions) == 0 or len(question_results) == 0:
        raise ValueError("denominateur metrique invalide")
    metrics: dict[str, BenchmarkMetric] = {}
    for metric_name in (
        KNOWLEDGE_RECALL_AT_5,
        KNOWLEDGE_RECALL_AT_10,
        KNOWLEDGE_RECALL_AT_20,
        KNOWLEDGE_MRR,
        KNOWLEDGE_NDCG,
        EXPECTED_PAGE_ACCURACY,
        KNOWLEDGE_DOCUMENT_DIVERSITY,
    ):
        values = [Decimal(result.metrics[metric_name].value) for result in question_results]
        metrics[metric_name] = _aggregate_metric(metric_name, values, len(question_results))

    metrics[KNOWLEDGE_SUBTHEME_COVERAGE] = _subtheme_coverage_metric(questions, question_results)
    metrics[FR_TO_EN_RECALL_AT_10] = _fr_to_en_recall_metric(questions, question_results)
    return metrics


def _aggregate_metric(metric_name: str, values: Sequence[Decimal], denominator: int) -> BenchmarkMetric:
    if denominator <= 0:
        raise ValueError("denominateur metrique invalide")
    total = sum(values, Decimal(0))
    value = total / Decimal(denominator)
    return BenchmarkMetric(metric_name, _format_decimal(value), _metric_numerator(_format_decimal(total)), denominator)


def _subtheme_coverage_metric(
    questions: Sequence[SearchEvaluationQuestion],
    question_results: Sequence[KnowledgeQuestionBenchmarkResult],
) -> BenchmarkMetric:
    all_subthemes = sorted({subtheme for question in questions for subtheme in question.subthemes})
    if len(all_subthemes) == 0:
        raise ValueError("denominateur metrique invalide")
    successful_question_ids = {
        result.question_id
        for result in question_results
        if Decimal(result.metrics[KNOWLEDGE_RECALL_AT_10].value) > Decimal(0)
    }
    covered_subthemes = {
        subtheme
        for question in questions
        if question.question_id in successful_question_ids
        for subtheme in question.subthemes
    }
    return BenchmarkMetric(
        KNOWLEDGE_SUBTHEME_COVERAGE,
        _metric_value(len(covered_subthemes), len(all_subthemes)),
        len(covered_subthemes),
        len(all_subthemes),
    )


def _fr_to_en_recall_metric(
    questions: Sequence[SearchEvaluationQuestion],
    question_results: Sequence[KnowledgeQuestionBenchmarkResult],
) -> BenchmarkMetric:
    results_by_question_id = {result.question_id: result for result in question_results}
    fr_to_en_values: list[Decimal] = []
    for question in questions:
        if question.query_language != "fr":
            continue
        if any(page.source_language == "en" for page in question.expected_pages.pages):
            fr_to_en_values.append(Decimal(results_by_question_id[question.question_id].metrics[KNOWLEDGE_RECALL_AT_10].value))
    if len(fr_to_en_values) == 0:
        raise ValueError("question FR vers source EN absente")
    value = sum(fr_to_en_values, Decimal(0)) / Decimal(len(fr_to_en_values))
    return BenchmarkMetric(
        FR_TO_EN_RECALL_AT_10,
        _format_decimal(value),
        _metric_numerator(_format_decimal(sum(fr_to_en_values, Decimal(0)))),
        len(fr_to_en_values),
    )


def _candidates_for_question(
    question_id: str,
    candidates_by_question: Mapping[str, Sequence[KnowledgeSearchCandidate]],
) -> Sequence[KnowledgeSearchCandidate]:
    if question_id not in candidates_by_question:
        raise ValueError(f"resultat de recherche absent: {question_id}")
    return candidates_by_question[question_id]


def _validated_candidates(
    candidates: Sequence[KnowledgeSearchCandidate],
    *,
    projection_snapshot: KnowledgeProjectionSnapshot,
) -> tuple[KnowledgeSearchCandidate, ...]:
    if isinstance(candidates, str) or not isinstance(candidates, Sequence):
        raise ValueError("candidats recherche invalides")
    parsed = _sorted_candidates(candidates)
    candidate_ids: set[str] = set()
    locator_keys: set[tuple[str, str, int, str]] = set()
    ranks: set[int] = set()
    for candidate in parsed:
        if candidate.candidate_id in candidate_ids or candidate.locator_key in locator_keys:
            raise ValueError("candidat recherche duplique")
        if candidate.rank in ranks:
            raise ValueError("rang candidat duplique")
        if candidate.projection_id != projection_snapshot.projection_id:
            raise ValueError("projection candidat incoherente")
        if candidate.projection_version != projection_snapshot.projection_version:
            raise ValueError("version de projection candidat incoherente")
        candidate_ids.add(candidate.candidate_id)
        locator_keys.add(candidate.locator_key)
        ranks.add(candidate.rank)
    return parsed


def _top_k_candidates(candidates: Sequence[KnowledgeSearchCandidate], k: int) -> tuple[KnowledgeSearchCandidate, ...]:
    _required_positive_integer(k, "k")
    return tuple(candidate for candidate in _sorted_candidates(candidates) if candidate.rank <= k)


def _sorted_candidates(candidates: Sequence[KnowledgeSearchCandidate]) -> tuple[KnowledgeSearchCandidate, ...]:
    if isinstance(candidates, str) or not isinstance(candidates, Sequence):
        raise ValueError("candidats recherche invalides")
    parsed = tuple(candidates)
    for candidate in parsed:
        if not isinstance(candidate, KnowledgeSearchCandidate):
            raise ValueError("KnowledgeSearchCandidate requis")
    return tuple(sorted(parsed, key=lambda candidate: candidate.rank))


def _first_relevant_rank(
    expected_pages: ExpectedPageSet,
    candidates: Sequence[KnowledgeSearchCandidate],
) -> int | None:
    _ensure_expected_pages(expected_pages)
    for candidate in _sorted_candidates(candidates):
        if candidate.page_key in expected_pages.keys:
            return candidate.rank
    return None


def _document_diversity(candidates: Sequence[KnowledgeSearchCandidate]) -> str:
    parsed_candidates = tuple(_top_k_candidates(candidates, 20))
    if len(parsed_candidates) == 0:
        return _format_decimal(Decimal(0))
    document_ids = {candidate.source_locator.document_id for candidate in parsed_candidates}
    return _metric_value(len(document_ids), len(parsed_candidates))


def _ensure_expected_pages(expected_pages: ExpectedPageSet) -> None:
    if not isinstance(expected_pages, ExpectedPageSet):
        raise ValueError("ExpectedPageSet requis")


def _ensure_required_metrics(metrics: Mapping[str, BenchmarkMetric]) -> None:
    missing_metrics = sorted(REQUIRED_KNOWLEDGE_SEARCH_METRICS.difference(metrics.keys()))
    if missing_metrics:
        raise ValueError(f"metrique recherche absente: {', '.join(missing_metrics)}")
    for metric in metrics.values():
        if not isinstance(metric, BenchmarkMetric):
            raise ValueError("BenchmarkMetric requise")


def _fr_to_en_denominator(questions: Sequence[SearchEvaluationQuestion]) -> int:
    return sum(
        1
        for question in questions
        if question.query_language == "fr" and any(page.source_language == "en" for page in question.expected_pages.pages)
    )


def _required_question_tuple(values: Sequence[SearchEvaluationQuestion]) -> tuple[SearchEvaluationQuestion, ...]:
    if isinstance(values, str) or not isinstance(values, Sequence):
        raise ValueError("questions evaluation invalides")
    questions = tuple(values)
    for question in questions:
        if not isinstance(question, SearchEvaluationQuestion):
            raise ValueError("SearchEvaluationQuestion requise")
    return questions


def _page_key(page_ref: PageReference) -> tuple[str, str, int]:
    return (
        page_ref.source_document_id,
        page_ref.canonical_version_id,
        page_ref.page_pdf,
    )


def _required_text_tuple(values: Sequence[str], field_name: str) -> tuple[str, ...]:
    if isinstance(values, str) or not isinstance(values, Sequence):
        raise ValueError(f"{field_name} invalide")
    parsed = tuple(_required_text_value(value, field_name) for value in values)
    if len(parsed) == 0:
        raise ValueError(f"{field_name} vide")
    if len(set(parsed)) != len(parsed):
        raise ValueError(f"{field_name} duplique")
    return parsed


def _required_language(value: Any, field_name: str) -> str:
    text_value = _required_text_value(value, field_name)
    normalized = text_value.lower()
    if text_value != normalized:
        raise ValueError(f"{field_name} non normalise")
    return normalized


def _required_projection_status(value: Any) -> str:
    text_value = _required_text_value(value, "projection_status")
    if text_value not in _EXPECTED_PROJECTION_STATUSES:
        raise ValueError("projection_status inconnu")
    return text_value


def _required_projection_version(value: Any) -> str:
    if not isinstance(value, str) or value.strip() == "":
        raise ValueError("version de projection absente")
    if value != value.strip():
        raise ValueError("version de projection non normalisee")
    return value


def _required_hash(value: Any, field_name: str) -> str:
    text_value = _required_text_value(value, field_name)
    if len(text_value) not in {32, 64} or any(character not in "0123456789abcdefABCDEF" for character in text_value):
        raise ValueError(f"{field_name} invalide")
    return text_value


def _required_decimal_text(value: Any, error_message: str) -> str:
    return _format_decimal(_decimal(value, error_message))


def _decimal(value: Any, error_message: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(error_message)
    try:
        decimal_value = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(error_message) from exc
    if not decimal_value.is_finite():
        raise ValueError(error_message)
    return decimal_value


def _required_text_value(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


def _required_positive_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} invalide")
    return value


def _required_non_negative_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} invalide")
    return value


def _required_metric_denominator(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("denominateur metrique invalide")
    return value


def _metric_value(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        raise ValueError("denominateur metrique invalide")
    return _format_decimal(Decimal(numerator) / Decimal(denominator))


def _metric_numerator(value: str) -> int:
    decimal_value = _decimal(value, "valeur metrique invalide")
    return int((decimal_value * Decimal(1_000_000)).to_integral_value(rounding=ROUND_HALF_EVEN))


def _format_decimal(value: Decimal) -> str:
    return f"{value.quantize(_DECIMAL_SCALE, rounding=ROUND_HALF_EVEN):.12f}"


__all__ = [
    "EXPECTED_PAGE_ACCURACY",
    "FR_TO_EN_RECALL_AT_10",
    "KNOWLEDGE_DOCUMENT_DIVERSITY",
    "KNOWLEDGE_MRR",
    "KNOWLEDGE_NDCG",
    "KNOWLEDGE_RECALL_AT_5",
    "KNOWLEDGE_RECALL_AT_10",
    "KNOWLEDGE_RECALL_AT_20",
    "KNOWLEDGE_SUBTHEME_COVERAGE",
    "REQUIRED_KNOWLEDGE_SEARCH_METRICS",
    "SEARCHABLE",
    "STALE",
    "BenchmarkMetric",
    "ExpectedPage",
    "ExpectedPageSet",
    "KnowledgeProjectionSnapshot",
    "KnowledgeQuestionBenchmarkResult",
    "KnowledgeSearchBenchmark",
    "KnowledgeSearchBenchmarkRun",
    "KnowledgeSearchCandidate",
    "SearchEvaluationQuestion",
    "SearchEvaluationSet",
    "calculate_expected_page_accuracy",
    "calculate_mrr",
    "calculate_ndcg",
    "calculate_question_recall_at_k",
]
