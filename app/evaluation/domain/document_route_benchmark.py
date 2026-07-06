"""Benchmark des routes documentaires M-012."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
import re
from typing import Any

from app.evaluation.domain.page_annotation import AnnotationSet, PageAnnotation, PageReference
from app.evaluation.domain.pilot_corpus import PilotCorpus, PilotDocument


DOCLING_STANDARD = "Docling standard"
GRANITE_DOCLING_DIRECT = "Granite-Docling direct"
PREPROCESSING_GRANITE_DOCLING = "prétraitement + Granite-Docling"
DOUBLE_CONVERSION_ADJUDICATION = "double conversion et adjudication"

REQUIRED_DOCUMENT_ROUTES = frozenset(
    {
        DOCLING_STANDARD,
        GRANITE_DOCLING_DIRECT,
        PREPROCESSING_GRANITE_DOCLING,
        DOUBLE_CONVERSION_ADJUDICATION,
    }
)

DOCUMENT_CER = "document_cer"
DOCUMENT_WER = "document_wer"
DOCUMENT_NUMERIC_TOKEN_ACCURACY = "document_numeric_token_accuracy"
DOCUMENT_SIGN_ACCURACY = "document_sign_accuracy"
DOCUMENT_FORMULA_FIDELITY = "document_formula_fidelity"
DOCUMENT_CELL_ACCURACY = "document_cell_accuracy"
DOCUMENT_READING_ORDER_ACCURACY = "document_reading_order_accuracy"
DOCUMENT_PAGE_TIME_SECONDS = "document_page_time_seconds"
DOCUMENT_MEMORY_BYTES = "document_memory_bytes"
DOCUMENT_ROUTE_STABILITY_RATE = "document_route_stability_rate"
DOCUMENT_FAILURE_RATE = "document_failure_rate"

REQUIRED_ROUTE_METRICS = frozenset(
    {
        DOCUMENT_CER,
        DOCUMENT_WER,
        DOCUMENT_NUMERIC_TOKEN_ACCURACY,
        DOCUMENT_SIGN_ACCURACY,
        DOCUMENT_FORMULA_FIDELITY,
        DOCUMENT_CELL_ACCURACY,
        DOCUMENT_READING_ORDER_ACCURACY,
        DOCUMENT_PAGE_TIME_SECONDS,
        DOCUMENT_MEMORY_BYTES,
        DOCUMENT_ROUTE_STABILITY_RATE,
        DOCUMENT_FAILURE_RATE,
    }
)

SUCCESS = "SUCCESS"
FAILED = "FAILED"
_EXPECTED_OUTPUT_STATUSES = frozenset({SUCCESS, FAILED})
_DECIMAL_SCALE = Decimal("0.000000000001")
_FORMULA_PATTERN = re.compile(r"\b[A-Z][A-Z0-9_]*\s*=\s*[A-Z0-9_]+(?:\s*[+\-*/]\s*[A-Z0-9_]+)+\b")


@dataclass(frozen=True)
class RouteMetric:
    name: str
    value: str
    numerator: int
    denominator: int


@dataclass(frozen=True)
class DocumentRouteOutput:
    output_id: str
    route_name: str
    page_ref: PageReference
    route_policy_version: str
    measured_text: str | None
    numeric_values: tuple[str, ...]
    formulas: tuple[str, ...]
    table_cells: tuple[str, ...]
    reading_order_roles: tuple[str, ...]
    processing_time_seconds: str
    memory_bytes: int
    status: str
    failure_reason: str | None

    def __init__(
        self,
        *,
        output_id: str,
        route_name: str,
        page_ref: PageReference,
        route_policy_version: str,
        measured_text: str | None,
        numeric_values: Sequence[str],
        formulas: Sequence[str],
        table_cells: Sequence[str],
        reading_order_roles: Sequence[str],
        processing_time_seconds: str | Decimal | None,
        memory_bytes: int | None,
        status: str,
        failure_reason: str | None,
    ) -> None:
        object.__setattr__(self, "output_id", _required_text_value(output_id, "output_id"))
        object.__setattr__(self, "route_name", _required_route_name(route_name))
        if not isinstance(page_ref, PageReference):
            raise ValueError("PageReference requise")
        object.__setattr__(self, "page_ref", page_ref)
        object.__setattr__(self, "route_policy_version", _required_text_value(route_policy_version, "route_policy_version"))
        object.__setattr__(self, "processing_time_seconds", _required_decimal_text(processing_time_seconds))
        object.__setattr__(self, "memory_bytes", _required_memory_bytes(memory_bytes))
        object.__setattr__(self, "status", _required_status(status))
        object.__setattr__(self, "numeric_values", _required_text_tuple(numeric_values, "numeric_values"))
        object.__setattr__(self, "formulas", _required_text_tuple(formulas, "formulas"))
        object.__setattr__(self, "table_cells", _required_text_tuple(table_cells, "table_cells"))
        object.__setattr__(self, "reading_order_roles", _required_text_tuple(reading_order_roles, "reading_order_roles"))

        if status == SUCCESS:
            object.__setattr__(self, "measured_text", _required_text_value(measured_text, "measured_text"))
            if failure_reason is not None:
                raise ValueError("failure_reason interdit sur succes")
            object.__setattr__(self, "failure_reason", None)
            return

        object.__setattr__(self, "measured_text", _optional_text_value(measured_text, "measured_text"))
        object.__setattr__(self, "failure_reason", _required_text_value(failure_reason, "failure_reason"))


@dataclass(frozen=True)
class RoutePageMeasurement:
    corpus_id: str
    annotation_set_id: str
    annotation_id: str
    route_name: str
    policy_version: str
    output_id: str
    page_ref: PageReference
    strata: frozenset[str]
    status: str
    metrics: Mapping[str, RouteMetric]


@dataclass(frozen=True)
class RouteStrataResult:
    stratum: str
    page_count: int
    failed_page_count: int
    metrics: Mapping[str, RouteMetric]


@dataclass(frozen=True)
class RouteBenchmarkResult:
    result_id: str
    corpus_id: str
    annotation_set_id: str
    route_name: str
    policy_version: str
    page_count: int
    failed_page_count: int
    metrics: Mapping[str, RouteMetric]
    strata_details: Mapping[str, RouteStrataResult]
    page_measurements: tuple[RoutePageMeasurement, ...]


@dataclass(frozen=True)
class RouteBenchmarkRun:
    run_id: str
    corpus_id: str
    annotation_set_id: str
    policy_version: str
    results: tuple[RouteBenchmarkResult, ...]

    def result_for_route(self, route_name: str) -> RouteBenchmarkResult:
        for result in self.results:
            if result.route_name == route_name:
                return result
        raise ValueError(f"resultat de route absent: {route_name}")


@dataclass(frozen=True)
class DocumentRouteBenchmark:
    policy_version: str

    def measure(
        self,
        *,
        run_id: str,
        corpus: PilotCorpus,
        annotation_set: AnnotationSet,
        route_outputs_by_route: Mapping[str, Sequence[DocumentRouteOutput]],
    ) -> RouteBenchmarkRun:
        _required_text_value(run_id, "run_id")
        if not isinstance(corpus, PilotCorpus):
            raise ValueError("PilotCorpus requis")
        if not isinstance(annotation_set, AnnotationSet):
            raise ValueError("AnnotationSet requis")
        if annotation_set.corpus_id != corpus.corpus_id:
            raise ValueError("corpus_id incoherent avec AnnotationSet")
        if not isinstance(route_outputs_by_route, Mapping):
            raise ValueError("sorties de routes non objet")

        missing_routes = sorted(REQUIRED_DOCUMENT_ROUTES.difference(route_outputs_by_route.keys()))
        if missing_routes:
            raise ValueError(f"route obligatoire absente: {', '.join(missing_routes)}")

        annotations_by_page = _annotations_by_page(annotation_set)
        documents_by_pilot_id = _documents_by_pilot_id(corpus)
        benchmark_page_keys = {page_ref.key for page_ref in annotation_set.benchmark_pages}
        results = tuple(
            self._measure_route(
                run_id=run_id,
                corpus=corpus,
                annotation_set=annotation_set,
                route_name=route_name,
                outputs=route_outputs_by_route[route_name],
                annotations_by_page=annotations_by_page,
                documents_by_pilot_id=documents_by_pilot_id,
                benchmark_page_keys=benchmark_page_keys,
            )
            for route_name in sorted(REQUIRED_DOCUMENT_ROUTES)
        )
        return RouteBenchmarkRun(
            run_id=run_id,
            corpus_id=corpus.corpus_id,
            annotation_set_id=annotation_set.annotation_set_id,
            policy_version=self.policy_version,
            results=results,
        )

    def _measure_route(
        self,
        *,
        run_id: str,
        corpus: PilotCorpus,
        annotation_set: AnnotationSet,
        route_name: str,
        outputs: Sequence[DocumentRouteOutput],
        annotations_by_page: Mapping[tuple[str, str, str, int], PageAnnotation],
        documents_by_pilot_id: Mapping[str, PilotDocument],
        benchmark_page_keys: set[tuple[str, str, str, int]],
    ) -> RouteBenchmarkResult:
        outputs_by_page = _outputs_by_page(route_name, outputs)
        missing_pages = sorted(benchmark_page_keys.difference(outputs_by_page.keys()))
        if missing_pages:
            raise ValueError(f"sortie manquante pour route {route_name}: {missing_pages[0]}")

        page_measurements: list[RoutePageMeasurement] = []
        for page_ref in annotation_set.benchmark_pages:
            annotation = annotations_by_page[page_ref.key]
            output = outputs_by_page[page_ref.key]
            _ensure_policy_version(output, self.policy_version)
            document = documents_by_pilot_id.get(page_ref.pilot_document_id)
            if document is None:
                raise ValueError(f"document pilote absent: {page_ref.pilot_document_id}")
            if len(document.strata) == 0:
                raise ValueError("strate vide")
            page_measurements.append(
                _measure_page(
                    corpus_id=corpus.corpus_id,
                    annotation_set_id=annotation_set.annotation_set_id,
                    annotation=annotation,
                    output=output,
                    policy_version=self.policy_version,
                    strata=document.strata,
                )
            )

        metrics = _aggregate_metrics(page_measurements)
        strata_details = _aggregate_strata(page_measurements)
        _ensure_required_metrics(metrics, "route")
        if not strata_details:
            raise ValueError("detail par strate absent")

        for strata_result in strata_details.values():
            _ensure_required_metrics(strata_result.metrics, f"strate {strata_result.stratum}")

        failed_page_count = sum(1 for measurement in page_measurements if measurement.status == FAILED)
        return RouteBenchmarkResult(
            result_id=f"{run_id}:{route_name}",
            corpus_id=corpus.corpus_id,
            annotation_set_id=annotation_set.annotation_set_id,
            route_name=route_name,
            policy_version=self.policy_version,
            page_count=len(page_measurements),
            failed_page_count=failed_page_count,
            metrics=metrics,
            strata_details=strata_details,
            page_measurements=tuple(page_measurements),
        )


@dataclass
class RouteBenchmarkLedger:
    _runs_by_id: dict[str, RouteBenchmarkRun]
    _results_by_id: set[str]

    def __init__(self) -> None:
        self._runs_by_id = {}
        self._results_by_id = set()

    def append(self, run: RouteBenchmarkRun) -> None:
        if not isinstance(run, RouteBenchmarkRun):
            raise ValueError("RouteBenchmarkRun requis")
        if run.run_id in self._runs_by_id:
            raise ValueError("resultat de benchmark duplique")
        result_ids = {result.result_id for result in run.results}
        if len(result_ids) != len(run.results) or self._results_by_id.intersection(result_ids):
            raise ValueError("resultat de benchmark duplique")
        self._runs_by_id[run.run_id] = run
        self._results_by_id.update(result_ids)

    @property
    def runs(self) -> tuple[RouteBenchmarkRun, ...]:
        return tuple(self._runs_by_id.values())


def calculate_character_error_rate(reference_text: str, measured_text: str) -> RouteMetric:
    reference = _required_text_value(reference_text, "reference_text")
    measured = _required_text_value(measured_text, "measured_text")
    denominator = max(len(reference), 1)
    return RouteMetric(DOCUMENT_CER, _metric_value(_levenshtein(reference, measured), denominator), 1, 1)


def calculate_word_error_rate(reference_text: str, measured_text: str) -> RouteMetric:
    reference_words = _required_text_value(reference_text, "reference_text").split()
    measured_words = _required_text_value(measured_text, "measured_text").split()
    denominator = max(len(reference_words), 1)
    return RouteMetric(DOCUMENT_WER, _metric_value(_levenshtein(reference_words, measured_words), denominator), 1, 1)


def _measure_page(
    *,
    corpus_id: str,
    annotation_set_id: str,
    annotation: PageAnnotation,
    output: DocumentRouteOutput,
    policy_version: str,
    strata: frozenset[str],
) -> RoutePageMeasurement:
    if output.status == FAILED:
        metrics = _failed_page_metrics(output)
    else:
        metrics = _success_page_metrics(annotation, output)
    _ensure_required_metrics(metrics, "page")
    return RoutePageMeasurement(
        corpus_id=corpus_id,
        annotation_set_id=annotation_set_id,
        annotation_id=annotation.annotation_id,
        route_name=output.route_name,
        policy_version=policy_version,
        output_id=output.output_id,
        page_ref=output.page_ref,
        strata=strata,
        status=output.status,
        metrics=metrics,
    )


def _success_page_metrics(annotation: PageAnnotation, output: DocumentRouteOutput) -> Mapping[str, RouteMetric]:
    reference_text = _required_text_value(annotation.reference_transcription, "reference_transcription")
    measured_text = _required_text_value(output.measured_text, "measured_text")
    cer = calculate_character_error_rate(reference_text, measured_text)
    wer = calculate_word_error_rate(reference_text, measured_text)
    return {
        DOCUMENT_CER: cer,
        DOCUMENT_WER: wer,
        DOCUMENT_NUMERIC_TOKEN_ACCURACY: _accuracy_metric(
            DOCUMENT_NUMERIC_TOKEN_ACCURACY,
            _expected_numeric_magnitudes(annotation),
            _numeric_magnitudes(output.numeric_values),
        ),
        DOCUMENT_SIGN_ACCURACY: _accuracy_metric(
            DOCUMENT_SIGN_ACCURACY,
            _expected_numeric_signs(annotation),
            _numeric_signs(output.numeric_values),
            normalizer=_normal_sign_text,
        ),
        DOCUMENT_FORMULA_FIDELITY: _accuracy_metric(
            DOCUMENT_FORMULA_FIDELITY,
            _formulas_from_reference(reference_text),
            output.formulas,
        ),
        DOCUMENT_CELL_ACCURACY: _accuracy_metric(
            DOCUMENT_CELL_ACCURACY,
            tuple(cell.text for cell in annotation.table_cells),
            output.table_cells,
        ),
        DOCUMENT_READING_ORDER_ACCURACY: _accuracy_metric(
            DOCUMENT_READING_ORDER_ACCURACY,
            tuple(item.role for item in sorted(annotation.reading_order, key=lambda item: item.order_index)),
            output.reading_order_roles,
        ),
        DOCUMENT_PAGE_TIME_SECONDS: RouteMetric(
            DOCUMENT_PAGE_TIME_SECONDS,
            output.processing_time_seconds,
            1,
            1,
        ),
        DOCUMENT_MEMORY_BYTES: RouteMetric(
            DOCUMENT_MEMORY_BYTES,
            _format_decimal(Decimal(output.memory_bytes)),
            1,
            1,
        ),
        DOCUMENT_ROUTE_STABILITY_RATE: RouteMetric(DOCUMENT_ROUTE_STABILITY_RATE, _format_decimal(Decimal(1)), 1, 1),
        DOCUMENT_FAILURE_RATE: RouteMetric(DOCUMENT_FAILURE_RATE, _format_decimal(Decimal(0)), 0, 1),
    }


def _failed_page_metrics(output: DocumentRouteOutput) -> Mapping[str, RouteMetric]:
    zero = _format_decimal(Decimal(0))
    return {
        DOCUMENT_CER: RouteMetric(DOCUMENT_CER, _format_decimal(Decimal(1)), 1, 1),
        DOCUMENT_WER: RouteMetric(DOCUMENT_WER, _format_decimal(Decimal(1)), 1, 1),
        DOCUMENT_NUMERIC_TOKEN_ACCURACY: RouteMetric(DOCUMENT_NUMERIC_TOKEN_ACCURACY, zero, 0, 1),
        DOCUMENT_SIGN_ACCURACY: RouteMetric(DOCUMENT_SIGN_ACCURACY, zero, 0, 1),
        DOCUMENT_FORMULA_FIDELITY: RouteMetric(DOCUMENT_FORMULA_FIDELITY, zero, 0, 1),
        DOCUMENT_CELL_ACCURACY: RouteMetric(DOCUMENT_CELL_ACCURACY, zero, 0, 1),
        DOCUMENT_READING_ORDER_ACCURACY: RouteMetric(DOCUMENT_READING_ORDER_ACCURACY, zero, 0, 1),
        DOCUMENT_PAGE_TIME_SECONDS: RouteMetric(DOCUMENT_PAGE_TIME_SECONDS, output.processing_time_seconds, 1, 1),
        DOCUMENT_MEMORY_BYTES: RouteMetric(DOCUMENT_MEMORY_BYTES, _format_decimal(Decimal(output.memory_bytes)), 1, 1),
        DOCUMENT_ROUTE_STABILITY_RATE: RouteMetric(DOCUMENT_ROUTE_STABILITY_RATE, zero, 0, 1),
        DOCUMENT_FAILURE_RATE: RouteMetric(DOCUMENT_FAILURE_RATE, _format_decimal(Decimal(1)), 1, 1),
    }


def _aggregate_metrics(measurements: Sequence[RoutePageMeasurement]) -> Mapping[str, RouteMetric]:
    if len(measurements) == 0:
        raise ValueError("run incomplet")
    metrics: dict[str, RouteMetric] = {}
    for metric_name in sorted(REQUIRED_ROUTE_METRICS):
        page_metrics = [measurement.metrics[metric_name] for measurement in measurements]
        total = sum(Decimal(metric.value) for metric in page_metrics)
        value = total / Decimal(len(page_metrics))
        numerator = sum(metric.numerator for metric in page_metrics)
        metrics[metric_name] = RouteMetric(metric_name, _format_decimal(value), numerator, len(page_metrics))
    return metrics


def _aggregate_strata(measurements: Sequence[RoutePageMeasurement]) -> Mapping[str, RouteStrataResult]:
    by_strata: dict[str, list[RoutePageMeasurement]] = {}
    for measurement in measurements:
        for stratum in measurement.strata:
            by_strata.setdefault(stratum, []).append(measurement)
    if not by_strata:
        raise ValueError("detail par strate absent")
    return {
        stratum: RouteStrataResult(
            stratum=stratum,
            page_count=len(strata_measurements),
            failed_page_count=sum(1 for measurement in strata_measurements if measurement.status == FAILED),
            metrics=_aggregate_metrics(strata_measurements),
        )
        for stratum, strata_measurements in sorted(by_strata.items())
    }


def _accuracy_metric(
    metric_name: str,
    expected_values: Sequence[str],
    measured_values: Sequence[str],
    *,
    normalizer: Any | None = None,
) -> RouteMetric:
    metric_normalizer = _normal_metric_text if normalizer is None else normalizer
    expected = tuple(metric_normalizer(value) for value in expected_values)
    measured = tuple(metric_normalizer(value) for value in measured_values)
    if len(expected) == 0:
        score = 1 if len(measured) == 0 else 0
        return RouteMetric(metric_name, _format_decimal(Decimal(score)), score, 1)
    correct = sum(1 for index, expected_value in enumerate(expected) if index < len(measured) and measured[index] == expected_value)
    return RouteMetric(metric_name, _metric_value(correct, len(expected)), correct, 1)


def _expected_numeric_magnitudes(annotation: PageAnnotation) -> tuple[str, ...]:
    return tuple(_numeric_magnitude(value.signed_value) for value in annotation.critical_numeric_values)


def _numeric_magnitudes(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(_numeric_magnitude(value) for value in values)


def _expected_numeric_signs(annotation: PageAnnotation) -> tuple[str, ...]:
    return tuple(value.signed_value[0] for value in annotation.critical_numeric_values)


def _numeric_signs(values: Sequence[str]) -> tuple[str, ...]:
    signs = []
    for value in values:
        text_value = _required_text_value(value, "numeric_value")
        if not (text_value.startswith("+") or text_value.startswith("-")):
            raise ValueError("signe numerique mesure absent")
        signs.append(text_value[0])
    return tuple(signs)


def _numeric_magnitude(value: str) -> str:
    text_value = _required_text_value(value, "numeric_value")
    normalized = text_value.replace(",", ".")
    if normalized.startswith("+") or normalized.startswith("-"):
        normalized = normalized[1:]
    try:
        return str(Decimal(normalized).normalize())
    except InvalidOperation as exc:
        raise ValueError(f"numeric_value invalide: {value}") from exc


def _formulas_from_reference(reference_text: str) -> tuple[str, ...]:
    return tuple(_normal_metric_text(match.group(0)) for match in _FORMULA_PATTERN.finditer(reference_text))


def _normal_metric_text(value: str) -> str:
    return _required_text_value(value, "metric_value").replace(" ", "")


def _normal_sign_text(value: str) -> str:
    return _required_text_value(value, "numeric_sign")


def _levenshtein(reference: Sequence[Any], measured: Sequence[Any]) -> int:
    previous = list(range(len(measured) + 1))
    for reference_index, reference_item in enumerate(reference, start=1):
        current = [reference_index]
        for measured_index, measured_item in enumerate(measured, start=1):
            insertion = current[measured_index - 1] + 1
            deletion = previous[measured_index] + 1
            substitution = previous[measured_index - 1] + (0 if reference_item == measured_item else 1)
            current.append(min(insertion, deletion, substitution))
        previous = current
    return previous[-1]


def _outputs_by_page(
    route_name: str,
    outputs: Sequence[DocumentRouteOutput],
) -> Mapping[tuple[str, str, str, int], DocumentRouteOutput]:
    if isinstance(outputs, str) or not isinstance(outputs, Sequence):
        raise ValueError("sorties de route invalides")
    outputs_by_page: dict[tuple[str, str, str, int], DocumentRouteOutput] = {}
    output_ids: set[str] = set()
    for output in outputs:
        if not isinstance(output, DocumentRouteOutput):
            raise ValueError("DocumentRouteOutput requis")
        if output.route_name != route_name:
            raise ValueError("sortie rattachee a une route incoherente")
        if output.output_id in output_ids:
            raise ValueError("sortie dupliquee")
        if output.page_ref.key in outputs_by_page:
            raise ValueError("sortie dupliquee")
        output_ids.add(output.output_id)
        outputs_by_page[output.page_ref.key] = output
    return outputs_by_page


def _annotations_by_page(annotation_set: AnnotationSet) -> Mapping[tuple[str, str, str, int], PageAnnotation]:
    annotations_by_page: dict[tuple[str, str, str, int], PageAnnotation] = {}
    for annotation in annotation_set.annotations:
        annotations_by_page[annotation.page_ref.key] = annotation
    return annotations_by_page


def _documents_by_pilot_id(corpus: PilotCorpus) -> Mapping[str, PilotDocument]:
    documents_by_pilot_id: dict[str, PilotDocument] = {}
    for document in corpus.documents:
        documents_by_pilot_id[document.pilot_document_id] = document
    return documents_by_pilot_id


def _ensure_policy_version(output: DocumentRouteOutput, policy_version: str) -> None:
    if output.route_policy_version != policy_version:
        raise ValueError("version de politique incoherente")


def _ensure_required_metrics(metrics: Mapping[str, RouteMetric], label: str) -> None:
    missing_metrics = sorted(REQUIRED_ROUTE_METRICS.difference(metrics.keys()))
    if missing_metrics:
        raise ValueError(f"metrique normative absente pour {label}: {', '.join(missing_metrics)}")


def _required_route_name(route_name: str) -> str:
    value = _required_text_value(route_name, "route_name")
    if value not in REQUIRED_DOCUMENT_ROUTES:
        raise ValueError(f"route documentaire inconnue: {value}")
    return value


def _required_status(status: str) -> str:
    value = _required_text_value(status, "status")
    if value not in _EXPECTED_OUTPUT_STATUSES:
        raise ValueError(f"status sortie inconnu: {value}")
    return value


def _required_text_value(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


def _optional_text_value(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return _required_text_value(value, field_name)


def _required_text_tuple(values: Sequence[str], field_name: str) -> tuple[str, ...]:
    if isinstance(values, str) or not isinstance(values, Sequence):
        raise ValueError(f"{field_name} invalide")
    return tuple(_required_text_value(value, field_name) for value in values)


def _required_decimal_text(value: str | Decimal | None) -> str:
    if value is None:
        raise ValueError("temps par page absent")
    try:
        decimal_value = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("temps par page invalide") from exc
    if decimal_value < 0:
        raise ValueError("temps par page invalide")
    return _format_decimal(decimal_value)


def _required_memory_bytes(value: int | None) -> int:
    if value is None:
        raise ValueError("memoire absente")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("memoire invalide")
    return value


def _metric_value(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        raise ValueError("denominateur metrique invalide")
    return _format_decimal(Decimal(numerator) / Decimal(denominator))


def _format_decimal(value: Decimal) -> str:
    return f"{value.quantize(_DECIMAL_SCALE, rounding=ROUND_HALF_EVEN):.12f}"


__all__ = [
    "DOCLING_STANDARD",
    "DOUBLE_CONVERSION_ADJUDICATION",
    "DOCUMENT_CELL_ACCURACY",
    "DOCUMENT_CER",
    "DOCUMENT_FAILURE_RATE",
    "DOCUMENT_FORMULA_FIDELITY",
    "DOCUMENT_MEMORY_BYTES",
    "DOCUMENT_NUMERIC_TOKEN_ACCURACY",
    "DOCUMENT_PAGE_TIME_SECONDS",
    "DOCUMENT_READING_ORDER_ACCURACY",
    "DOCUMENT_ROUTE_STABILITY_RATE",
    "DOCUMENT_SIGN_ACCURACY",
    "DOCUMENT_WER",
    "DocumentRouteBenchmark",
    "DocumentRouteOutput",
    "GRANITE_DOCLING_DIRECT",
    "PREPROCESSING_GRANITE_DOCLING",
    "REQUIRED_DOCUMENT_ROUTES",
    "REQUIRED_ROUTE_METRICS",
    "RouteBenchmarkLedger",
    "RouteBenchmarkResult",
    "RouteBenchmarkRun",
    "RouteMetric",
    "RoutePageMeasurement",
    "RouteStrataResult",
    "calculate_character_error_rate",
    "calculate_word_error_rate",
]
