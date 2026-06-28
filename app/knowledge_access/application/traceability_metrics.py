"""Mesures initiales et signaux d'audit de clôture M-005."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


_HASH_HEX_ALPHABET = frozenset("0123456789abcdef")
_METRIC_SCOPE = "INITIAL_M005_NON_DEFINITIVE"
_CALIBRATION_MILESTONE = "M-012"


@dataclass(frozen=True)
class EvaluationQuestion:
    """Question d'évaluation initiale rattachée à des chunks pertinents."""

    question_id: str
    query_text: str
    relevant_chunk_ids: Sequence[str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "question_id", _ensure_text(self.question_id, "question_id"))
        object.__setattr__(self, "query_text", _ensure_text(self.query_text, "query_text"))
        object.__setattr__(
            self,
            "relevant_chunk_ids",
            _ensure_chunk_id_tuple(self.relevant_chunk_ids, "relevant_chunk_ids"),
        )


@dataclass(frozen=True)
class EvaluationResult:
    """Résultat ordonné retourné par la recherche pour une question."""

    question_id: str
    ranked_chunk_ids: Sequence[str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "question_id", _ensure_text(self.question_id, "question_id"))
        object.__setattr__(
            self,
            "ranked_chunk_ids",
            _ensure_chunk_id_tuple(self.ranked_chunk_ids, "ranked_chunk_ids"),
        )


@dataclass(frozen=True)
class SearchEvaluationCorpus:
    """Corpus reproductible utilisé pour publier les métriques initiales."""

    corpus_id: str
    fixture_path: str
    questions: Sequence[EvaluationQuestion]

    def __post_init__(self) -> None:
        object.__setattr__(self, "corpus_id", _ensure_text(self.corpus_id, "corpus_id"))
        object.__setattr__(self, "fixture_path", _ensure_relative_path(self.fixture_path, "fixture_path"))
        object.__setattr__(self, "questions", _ensure_questions(self.questions))


@dataclass(frozen=True)
class InitialSearchMetricSnapshot:
    """Snapshot non définitif des métriques de recherche M-005."""

    corpus_id: str
    fixture_path: str
    question_count: int
    k: int
    measured_at: str
    recall_at_k: float
    mrr: float
    ndcg: float
    is_v1_acceptance_threshold: bool
    calibration_milestone: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "corpus_id", _ensure_text(self.corpus_id, "corpus_id"))
        object.__setattr__(self, "fixture_path", _ensure_relative_path(self.fixture_path, "fixture_path"))
        object.__setattr__(self, "question_count", _ensure_positive_integer(self.question_count, "question_count"))
        object.__setattr__(self, "k", _ensure_positive_integer(self.k, "k"))
        object.__setattr__(self, "measured_at", _ensure_text(self.measured_at, "measured_at"))
        object.__setattr__(self, "recall_at_k", _ensure_ratio(self.recall_at_k, "recall_at_k"))
        object.__setattr__(self, "mrr", _ensure_ratio(self.mrr, "mrr"))
        object.__setattr__(self, "ndcg", _ensure_ratio(self.ndcg, "ndcg"))
        if self.is_v1_acceptance_threshold is not False:
            raise ValueError("seuil V1 interdit avant M-012")
        object.__setattr__(
            self,
            "calibration_milestone",
            _ensure_expected_text(self.calibration_milestone, _CALIBRATION_MILESTONE, "calibration_milestone"),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "metric_scope": _METRIC_SCOPE,
            "corpus_id": self.corpus_id,
            "fixture_path": self.fixture_path,
            "question_count": self.question_count,
            "k": self.k,
            "measured_at": self.measured_at,
            "metrics": {
                "recall_at_k": self.recall_at_k,
                "mrr": self.mrr,
                "ndcg": self.ndcg,
            },
            "is_v1_acceptance_threshold": self.is_v1_acceptance_threshold,
            "calibration_milestone": self.calibration_milestone,
        }


class InitialSearchMetricsPublisher:
    """Calcule les mesures initiales reproductibles sans seuil d'acceptation V1."""

    def publish(
        self,
        *,
        corpus: SearchEvaluationCorpus,
        results: Sequence[EvaluationResult],
        k: int,
        measured_at: str,
    ) -> InitialSearchMetricSnapshot:
        parsed_corpus = _ensure_corpus(corpus)
        parsed_results = _ensure_results(results)
        parsed_k = _ensure_positive_integer(k, "k")
        parsed_measured_at = _ensure_text(measured_at, "measured_at")
        results_by_question_id = {result.question_id: result for result in parsed_results}
        question_ids = tuple(question.question_id for question in parsed_corpus.questions)

        if set(results_by_question_id) != set(question_ids):
            raise ValueError("résultats incohérents avec le jeu de questions")

        recall_values: list[float] = []
        reciprocal_ranks: list[float] = []
        ndcg_values: list[float] = []
        for question in parsed_corpus.questions:
            result = results_by_question_id[question.question_id]
            top_ranked = tuple(result.ranked_chunk_ids[:parsed_k])
            relevant = set(question.relevant_chunk_ids)
            found = tuple(chunk_id for chunk_id in top_ranked if chunk_id in relevant)
            recall_values.append(len(found) / len(relevant))
            reciprocal_ranks.append(_reciprocal_rank(top_ranked=top_ranked, relevant=relevant))
            ndcg_values.append(_ndcg_at_k(top_ranked=top_ranked, relevant=relevant, k=parsed_k))

        return InitialSearchMetricSnapshot(
            corpus_id=parsed_corpus.corpus_id,
            fixture_path=parsed_corpus.fixture_path,
            question_count=len(parsed_corpus.questions),
            k=parsed_k,
            measured_at=parsed_measured_at,
            recall_at_k=sum(recall_values) / len(recall_values),
            mrr=sum(reciprocal_ranks) / len(reciprocal_ranks),
            ndcg=sum(ndcg_values) / len(ndcg_values),
            is_v1_acceptance_threshold=False,
            calibration_milestone=_CALIBRATION_MILESTONE,
        )


@dataclass(frozen=True)
class KnowledgeSearchAuditSignal:
    """Signal KA de publication des métriques sans contenu documentaire complet."""

    signal_name: str
    metric_scope: str
    search_trace_id: str
    projection_id: str
    query_hash: str
    result_count: int
    candidate_refs: Sequence[Mapping[str, Any]]
    metric_snapshot: InitialSearchMetricSnapshot

    @classmethod
    def from_metric_snapshot(
        cls,
        *,
        search_trace_id: str,
        projection_id: str,
        query_hash: str,
        result_count: int,
        candidate_refs: Sequence[Mapping[str, Any]],
        metric_snapshot: InitialSearchMetricSnapshot,
        forbidden_full_passages: Sequence[str],
    ) -> "KnowledgeSearchAuditSignal":
        signal = cls(
            signal_name="knowledge_search_initial_metrics_published",
            metric_scope=_METRIC_SCOPE,
            search_trace_id=search_trace_id,
            projection_id=projection_id,
            query_hash=query_hash,
            result_count=result_count,
            candidate_refs=candidate_refs,
            metric_snapshot=metric_snapshot,
        )
        assert_no_full_passage_in_audit_payload(
            signal.to_payload(),
            forbidden_full_passages=forbidden_full_passages,
        )
        return signal

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "signal_name",
            _ensure_expected_text(
                self.signal_name,
                "knowledge_search_initial_metrics_published",
                "signal_name",
            ),
        )
        object.__setattr__(self, "metric_scope", _ensure_expected_text(self.metric_scope, _METRIC_SCOPE, "metric_scope"))
        object.__setattr__(
            self,
            "search_trace_id",
            _ensure_prefixed_text(self.search_trace_id, "STRC-", "search_trace_id"),
        )
        object.__setattr__(self, "projection_id", _ensure_prefixed_text(self.projection_id, "PROJ-", "projection_id"))
        object.__setattr__(self, "query_hash", _ensure_sha256(self.query_hash, "query_hash"))
        object.__setattr__(self, "result_count", _ensure_non_negative_integer(self.result_count, "result_count"))
        object.__setattr__(self, "candidate_refs", _ensure_candidate_refs(self.candidate_refs))
        if not isinstance(self.metric_snapshot, InitialSearchMetricSnapshot):
            raise ValueError("metric_snapshot invalide")

    def to_payload(self) -> dict[str, Any]:
        metric_payload = self.metric_snapshot.to_payload()
        return {
            "schema_version": "1.0",
            "signal_name": self.signal_name,
            "metric_scope": self.metric_scope,
            "search_trace_id": self.search_trace_id,
            "projection_id": self.projection_id,
            "query_hash": self.query_hash,
            "result_count": self.result_count,
            "candidate_refs": tuple(dict(ref) for ref in self.candidate_refs),
            "corpus_id": metric_payload["corpus_id"],
            "fixture_path": metric_payload["fixture_path"],
            "question_count": metric_payload["question_count"],
            "k": metric_payload["k"],
            "measured_at": metric_payload["measured_at"],
            "metrics": dict(metric_payload["metrics"]),
            "is_v1_acceptance_threshold": metric_payload["is_v1_acceptance_threshold"],
            "calibration_milestone": metric_payload["calibration_milestone"],
        }


def assert_no_full_passage_in_audit_payload(
    payload: Mapping[str, Any],
    *,
    forbidden_full_passages: Sequence[str],
) -> None:
    parsed_payload = _ensure_mapping(payload, "payload")
    passages = _ensure_text_tuple(forbidden_full_passages, "forbidden_full_passages")
    serialized_payload = json.dumps(_json_ready(parsed_payload), ensure_ascii=False, sort_keys=True)
    for passage in passages:
        if passage in serialized_payload:
            raise ValueError("passage complet interdit dans signal d'audit")


def _reciprocal_rank(*, top_ranked: tuple[str, ...], relevant: set[str]) -> float:
    for index, chunk_id in enumerate(top_ranked, start=1):
        if chunk_id in relevant:
            return 1.0 / index
    return 0.0


def _ndcg_at_k(*, top_ranked: tuple[str, ...], relevant: set[str], k: int) -> float:
    dcg = 0.0
    for index, chunk_id in enumerate(top_ranked[:k], start=1):
        if chunk_id in relevant:
            dcg += 1.0 / math.log2(index + 1)
    ideal_count = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(index + 1) for index in range(1, ideal_count + 1))
    if idcg == 0.0:
        raise ValueError("pertinence idéale absente")
    return dcg / idcg


def _ensure_corpus(value: SearchEvaluationCorpus) -> SearchEvaluationCorpus:
    if not isinstance(value, SearchEvaluationCorpus):
        raise ValueError("corpus invalide")
    return value


def _ensure_questions(value: Sequence[EvaluationQuestion]) -> tuple[EvaluationQuestion, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("jeu de questions invalide")
    questions = tuple(value)
    if len(questions) == 0:
        raise ValueError("jeu de questions absent")
    for question in questions:
        if not isinstance(question, EvaluationQuestion):
            raise ValueError("question invalide")
    question_ids = tuple(question.question_id for question in questions)
    if len(question_ids) != len(set(question_ids)):
        raise ValueError("question_id dupliqué")
    return questions


def _ensure_results(value: Sequence[EvaluationResult]) -> tuple[EvaluationResult, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("résultats invalides")
    results = tuple(value)
    if len(results) == 0:
        raise ValueError("résultats absents")
    for result in results:
        if not isinstance(result, EvaluationResult):
            raise ValueError("résultat invalide")
    question_ids = tuple(result.question_id for result in results)
    if len(question_ids) != len(set(question_ids)):
        raise ValueError("résultat question_id dupliqué")
    return results


def _ensure_candidate_refs(value: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("candidate_refs invalides")
    candidate_refs = tuple(_ensure_mapping(item, "candidate_ref") for item in value)
    if len(candidate_refs) == 0:
        raise ValueError("candidate_refs absentes")
    forbidden_keys = {"text", "passage", "full_text", "excerpt", "claim_id", "verified_claim_id"}
    for candidate_ref in candidate_refs:
        if forbidden_keys & {str(key) for key in candidate_ref}:
            raise ValueError("contenu documentaire interdit dans candidate_refs")
        _ensure_prefixed_text(candidate_ref.get("chunk_id"), "KCHK-", "chunk_id")
        _ensure_prefixed_text(candidate_ref.get("document_id"), "DOC-", "document_id")
        _ensure_prefixed_text(candidate_ref.get("canonical_version_id"), "CVER-", "canonical_version_id")
        _ensure_sha256(candidate_ref.get("content_hash"), "content_hash")
    return candidate_refs


def _ensure_chunk_id_tuple(value: Sequence[str], field_name: str) -> tuple[str, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} invalides")
    parsed = tuple(_ensure_prefixed_text(item, "KCHK-", field_name) for item in value)
    if len(parsed) == 0:
        raise ValueError(f"{field_name} absents")
    if len(parsed) != len(set(parsed)):
        raise ValueError(f"{field_name} dupliqués")
    return parsed


def _ensure_mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")
    return dict(value)


def _ensure_text_tuple(value: Sequence[str], field_name: str) -> tuple[str, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} invalides")
    parsed = tuple(_ensure_text(item, field_name) for item in value)
    if len(parsed) == 0:
        raise ValueError(f"{field_name} absents")
    if len(parsed) != len(set(parsed)):
        raise ValueError(f"{field_name} dupliqués")
    return parsed


def _ensure_expected_text(value: Any, expected: str, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if text != expected:
        raise ValueError(f"{field_name} invalide")
    return text


def _ensure_prefixed_text(value: Any, expected_prefix: str, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if not text.startswith(expected_prefix):
        raise ValueError(f"{field_name} invalide")
    return text


def _ensure_relative_path(value: Any, field_name: str) -> str:
    text = _ensure_text(value, field_name).replace("\\", "/")
    if text.startswith("/") or text.startswith("../") or "/../" in text or ":" in text:
        raise ValueError(f"{field_name} hors dépôt")
    return text


def _ensure_sha256(value: Any, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if len(text) != 64:
        raise ValueError(f"{field_name} invalide")
    for character in text:
        if character not in _HASH_HEX_ALPHABET:
            raise ValueError(f"{field_name} invalide")
    return text


def _ensure_positive_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_non_negative_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_ratio(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} invalide")
    parsed = float(value)
    if not math.isfinite(parsed) or parsed < 0.0 or parsed > 1.0:
        raise ValueError(f"{field_name} invalide")
    return parsed


def _ensure_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalisé")
    return value


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple) or isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


__all__ = [
    "EvaluationQuestion",
    "EvaluationResult",
    "InitialSearchMetricSnapshot",
    "InitialSearchMetricsPublisher",
    "KnowledgeSearchAuditSignal",
    "SearchEvaluationCorpus",
    "assert_no_full_passage_in_audit_payload",
]
