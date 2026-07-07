"""Politique de drill des pannes Spark M-013."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any


SPARK_FAILURE_DRILL_POLICY_VERSION = "M013-SparkFailureDrill-1.0"

FAILURE_SPARK_UNAVAILABLE = "spark_unavailable"
FAILURE_FIRST_TOKEN_TIMEOUT = "first_token_timeout"
FAILURE_TLS_REJECTED = "tls_rejected"
FAILURE_API_KEY_REJECTED = "api_key_rejected"
FAILURE_STREAM_CUT_BEFORE_FIRST_TOKEN = "stream_cut_before_first_token"
FAILURE_STREAM_CUT_AFTER_FIRST_TOKEN = "stream_cut_after_first_token"
FAILURE_CIRCUIT_BREAKER_OPEN = "circuit_breaker_open"
FAILURE_CIRCUIT_BREAKER_CLOSED = "circuit_breaker_closed_after_recovery"

LOCAL_CAPABILITY_INGESTION = "ingestion_locale"
LOCAL_CAPABILITY_RESTORE = "restauration_locale"
LOCAL_CAPABILITY_SEARCH = "consultation_locale"
LOCAL_CAPABILITY_AUDIT = "audit_local"

_REQUIRED_FAILURE_MODES = (
    FAILURE_SPARK_UNAVAILABLE,
    FAILURE_FIRST_TOKEN_TIMEOUT,
    FAILURE_TLS_REJECTED,
    FAILURE_API_KEY_REJECTED,
    FAILURE_STREAM_CUT_BEFORE_FIRST_TOKEN,
    FAILURE_STREAM_CUT_AFTER_FIRST_TOKEN,
    FAILURE_CIRCUIT_BREAKER_OPEN,
    FAILURE_CIRCUIT_BREAKER_CLOSED,
)
_REQUIRED_CONSUMER_CONTEXTS = ("RA", "CV", "SD", "EV")
_REQUIRED_LOCAL_CAPABILITIES = (
    LOCAL_CAPABILITY_INGESTION,
    LOCAL_CAPABILITY_RESTORE,
    LOCAL_CAPABILITY_SEARCH,
    LOCAL_CAPABILITY_AUDIT,
)
_ALLOWED_STATUS_BY_FAILURE_MODE = MappingProxyType(
    {
        FAILURE_SPARK_UNAVAILABLE: "LLM_UNAVAILABLE",
        FAILURE_FIRST_TOKEN_TIMEOUT: "LLM_FIRST_TOKEN_TIMEOUT",
        FAILURE_TLS_REJECTED: "LLM_TLS_CERTIFICATE_INVALID",
        FAILURE_API_KEY_REJECTED: "LLM_AUTHENTICATION_FAILED",
        FAILURE_STREAM_CUT_BEFORE_FIRST_TOKEN: "LLM_UNAVAILABLE",
        FAILURE_STREAM_CUT_AFTER_FIRST_TOKEN: "LLM_PARTIAL_OUTPUT",
        FAILURE_CIRCUIT_BREAKER_OPEN: "LLM_CIRCUIT_OPEN",
        FAILURE_CIRCUIT_BREAKER_CLOSED: "LLM_RECOVERED",
    }
)
_SENSITIVE_METRIC_FRAGMENTS = (
    "api key",
    "api_key",
    "authorization",
    "bearer",
    "mot de passe",
    "password",
    "prompt complet",
    "preuve complète",
    "preuve complete",
    "réponse complète",
    "reponse complete",
    "secret",
)


@dataclass(frozen=True)
class SparkFailureCase:
    case_id: str
    failure_mode: str
    consumer_context: str
    public_status: str
    diagnostic_code: str
    complete_generation: bool
    factual_response_published: bool
    strategy_snapshot_created: bool
    llm_benchmark_promoted: bool
    alternative_provider_calls: tuple[str, ...]
    retry_before_first_token_count: int
    retry_after_first_token_count: int
    retry_limit: int
    first_token_emitted: bool
    idempotency_key: str
    circuit_breaker_open_visible: bool
    circuit_breaker_close_visible: bool
    local_capabilities_available: tuple[str, ...]
    metric_public_labels: tuple[str, ...]
    outbox_event_ids: tuple[str, ...]

    def __init__(
        self,
        *,
        case_id: str,
        failure_mode: str,
        consumer_context: str,
        public_status: str,
        diagnostic_code: str,
        complete_generation: bool,
        factual_response_published: bool,
        strategy_snapshot_created: bool,
        llm_benchmark_promoted: bool,
        alternative_provider_calls: Sequence[str],
        retry_before_first_token_count: int,
        retry_after_first_token_count: int,
        retry_limit: int,
        first_token_emitted: bool,
        idempotency_key: str,
        circuit_breaker_open_visible: bool,
        circuit_breaker_close_visible: bool,
        local_capabilities_available: Sequence[str],
        metric_public_labels: Sequence[str],
        outbox_event_ids: Sequence[str],
    ) -> None:
        parsed_failure_mode = _required_failure_mode(failure_mode)
        parsed_status = _required_text(public_status, "public_status")
        expected_status = _ALLOWED_STATUS_BY_FAILURE_MODE[parsed_failure_mode]
        if parsed_status != expected_status:
            raise ValueError("statut public panne Spark invalide")

        if _required_bool(complete_generation, "complete_generation"):
            raise ValueError("génération complète interdite sur panne")
        if _required_bool(factual_response_published, "factual_response_published"):
            raise ValueError("réponse factuelle publiée interdite")
        if _required_bool(strategy_snapshot_created, "strategy_snapshot_created"):
            raise ValueError("snapshot stratégie interdit")
        if _required_bool(llm_benchmark_promoted, "llm_benchmark_promoted"):
            raise ValueError("benchmark LLM promu interdit")

        parsed_alternative_providers = _required_text_tuple(
            alternative_provider_calls,
            "alternative_provider_calls",
            allow_empty=True,
        )
        if parsed_alternative_providers:
            raise ValueError("provider alternatif interdit")

        retry_before = _required_non_negative_integer(
            retry_before_first_token_count,
            "retry_before_first_token_count",
        )
        retry_after = _required_non_negative_integer(
            retry_after_first_token_count,
            "retry_after_first_token_count",
        )
        retry_limit = _required_non_negative_integer(retry_limit, "retry_limit")
        first_token = _required_bool(first_token_emitted, "first_token_emitted")
        if retry_after > 0:
            raise ValueError("retry après premier token interdit")
        if retry_before > retry_limit:
            raise ValueError("retry illimité interdit")
        if retry_before > 0 and _is_blank(idempotency_key):
            raise ValueError("idempotence retry requise")

        parsed_local_capabilities = _required_text_tuple(
            local_capabilities_available,
            "local_capabilities_available",
            allow_empty=False,
        )
        for capability in _REQUIRED_LOCAL_CAPABILITIES:
            if capability not in parsed_local_capabilities:
                raise ValueError("fonction locale hors Gemma indisponible")

        parsed_metric_labels = _required_text_tuple(metric_public_labels, "metric_public_labels", allow_empty=False)
        for label in parsed_metric_labels:
            normalized_label = label.lower()
            for fragment in _SENSITIVE_METRIC_FRAGMENTS:
                if fragment in normalized_label:
                    raise ValueError("prompt complet interdit")

        parsed_outbox_event_ids = _required_text_tuple(outbox_event_ids, "outbox_event_ids", allow_empty=True)
        if len(set(parsed_outbox_event_ids)) != len(parsed_outbox_event_ids):
            raise ValueError("double outbox interdit")

        object.__setattr__(self, "case_id", _required_text(case_id, "case_id"))
        object.__setattr__(self, "failure_mode", parsed_failure_mode)
        object.__setattr__(self, "consumer_context", _required_context(consumer_context))
        object.__setattr__(self, "public_status", parsed_status)
        object.__setattr__(self, "diagnostic_code", _required_text(diagnostic_code, "diagnostic_code"))
        object.__setattr__(self, "complete_generation", False)
        object.__setattr__(self, "factual_response_published", False)
        object.__setattr__(self, "strategy_snapshot_created", False)
        object.__setattr__(self, "llm_benchmark_promoted", False)
        object.__setattr__(self, "alternative_provider_calls", parsed_alternative_providers)
        object.__setattr__(self, "retry_before_first_token_count", retry_before)
        object.__setattr__(self, "retry_after_first_token_count", retry_after)
        object.__setattr__(self, "retry_limit", retry_limit)
        object.__setattr__(self, "first_token_emitted", first_token)
        object.__setattr__(self, "idempotency_key", _required_text(idempotency_key, "idempotency_key"))
        object.__setattr__(
            self,
            "circuit_breaker_open_visible",
            _required_bool(circuit_breaker_open_visible, "circuit_breaker_open_visible"),
        )
        object.__setattr__(
            self,
            "circuit_breaker_close_visible",
            _required_bool(circuit_breaker_close_visible, "circuit_breaker_close_visible"),
        )
        object.__setattr__(self, "local_capabilities_available", parsed_local_capabilities)
        object.__setattr__(self, "metric_public_labels", parsed_metric_labels)
        object.__setattr__(self, "outbox_event_ids", parsed_outbox_event_ids)


@dataclass(frozen=True)
class SparkFailureDrill:
    drill_id: str
    policy_version: str
    cases: tuple[SparkFailureCase, ...]
    cases_by_failure_mode: Mapping[str, SparkFailureCase]
    consumer_contexts: tuple[str, ...]
    public_statuses: tuple[str, ...]
    local_capabilities_available: tuple[str, ...]
    acceptance_allowed: bool

    def with_replaced_case(self, replacement: SparkFailureCase) -> "SparkFailureDrill":
        if not isinstance(replacement, SparkFailureCase):
            raise ValueError("SparkFailureCase requis")
        replaced = tuple(
            replacement if item.failure_mode == replacement.failure_mode else item
            for item in self.cases
        )
        return _build_drill(
            drill_id=self.drill_id,
            policy_version=self.policy_version,
            cases=replaced,
        )


@dataclass(frozen=True)
class SparkFailureDrillPolicy:
    policy_version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_version", _required_policy_version(self.policy_version))

    def validate_drill(self, drill: SparkFailureDrill) -> None:
        if not isinstance(drill, SparkFailureDrill):
            raise ValueError("SparkFailureDrill requis")
        if drill.policy_version != self.policy_version:
            raise ValueError("version politique panne Spark incohérente")

        for mode in _REQUIRED_FAILURE_MODES:
            if mode not in drill.cases_by_failure_mode:
                raise ValueError(f"mode panne Spark absent: {mode}")

        for context in _REQUIRED_CONSUMER_CONTEXTS:
            if context not in drill.consumer_contexts:
                raise ValueError(f"consommateur V1 absent: {context}")

        for capability in _REQUIRED_LOCAL_CAPABILITIES:
            if capability not in drill.local_capabilities_available:
                raise ValueError("fonction locale hors Gemma indisponible")

        if not drill.cases_by_failure_mode[FAILURE_CIRCUIT_BREAKER_OPEN].circuit_breaker_open_visible:
            raise ValueError("circuit breaker ouvert invisible")
        if not drill.cases_by_failure_mode[FAILURE_CIRCUIT_BREAKER_CLOSED].circuit_breaker_close_visible:
            raise ValueError("circuit breaker fermé invisible")

        all_outbox_ids: list[str] = []
        for failure_case in drill.cases:
            all_outbox_ids.extend(failure_case.outbox_event_ids)
        if len(all_outbox_ids) != len(set(all_outbox_ids)):
            raise ValueError("double outbox interdit")


def build_m013_spark_failure_drill() -> SparkFailureDrill:
    cases = (
        _case(
            case_id="SPARK-FAIL-UNAVAILABLE-RA",
            failure_mode=FAILURE_SPARK_UNAVAILABLE,
            consumer_context="RA",
            public_status="LLM_UNAVAILABLE",
            retry_before_first_token_count=1,
            circuit_breaker_open_visible=True,
        ),
        _case(
            case_id="SPARK-FAIL-TIMEOUT-CV",
            failure_mode=FAILURE_FIRST_TOKEN_TIMEOUT,
            consumer_context="CV",
            public_status="LLM_FIRST_TOKEN_TIMEOUT",
            retry_before_first_token_count=1,
        ),
        _case(
            case_id="SPARK-FAIL-TLS-SD",
            failure_mode=FAILURE_TLS_REJECTED,
            consumer_context="SD",
            public_status="LLM_TLS_CERTIFICATE_INVALID",
            retry_before_first_token_count=0,
        ),
        _case(
            case_id="SPARK-FAIL-AUTH-EV",
            failure_mode=FAILURE_API_KEY_REJECTED,
            consumer_context="EV",
            public_status="LLM_AUTHENTICATION_FAILED",
            retry_before_first_token_count=0,
        ),
        _case(
            case_id="SPARK-FAIL-CUT-BEFORE-RA",
            failure_mode=FAILURE_STREAM_CUT_BEFORE_FIRST_TOKEN,
            consumer_context="RA",
            public_status="LLM_UNAVAILABLE",
            retry_before_first_token_count=1,
        ),
        _case(
            case_id="SPARK-FAIL-CUT-AFTER-CV",
            failure_mode=FAILURE_STREAM_CUT_AFTER_FIRST_TOKEN,
            consumer_context="CV",
            public_status="LLM_PARTIAL_OUTPUT",
            first_token_emitted=True,
            retry_before_first_token_count=0,
        ),
        _case(
            case_id="SPARK-FAIL-CIRCUIT-OPEN",
            failure_mode=FAILURE_CIRCUIT_BREAKER_OPEN,
            consumer_context="SD",
            public_status="LLM_CIRCUIT_OPEN",
            retry_before_first_token_count=0,
            circuit_breaker_open_visible=True,
        ),
        _case(
            case_id="SPARK-FAIL-CIRCUIT-CLOSED",
            failure_mode=FAILURE_CIRCUIT_BREAKER_CLOSED,
            consumer_context="EV",
            public_status="LLM_RECOVERED",
            retry_before_first_token_count=0,
            circuit_breaker_close_visible=True,
        ),
    )
    drill = _build_drill(
        drill_id="M013-SPARK-FAILURE-DRILL-0001",
        policy_version=SPARK_FAILURE_DRILL_POLICY_VERSION,
        cases=cases,
    )
    SparkFailureDrillPolicy(policy_version=SPARK_FAILURE_DRILL_POLICY_VERSION).validate_drill(drill)
    return drill


def _case(
    *,
    case_id: str,
    failure_mode: str,
    consumer_context: str,
    public_status: str,
    retry_before_first_token_count: int,
    first_token_emitted: bool = False,
    circuit_breaker_open_visible: bool = False,
    circuit_breaker_close_visible: bool = False,
) -> SparkFailureCase:
    return SparkFailureCase(
        case_id=case_id,
        failure_mode=failure_mode,
        consumer_context=consumer_context,
        public_status=public_status,
        diagnostic_code=public_status,
        complete_generation=False,
        factual_response_published=False,
        strategy_snapshot_created=False,
        llm_benchmark_promoted=False,
        alternative_provider_calls=(),
        retry_before_first_token_count=retry_before_first_token_count,
        retry_after_first_token_count=0,
        retry_limit=1,
        first_token_emitted=first_token_emitted,
        idempotency_key=f"idem-{case_id.lower()}",
        circuit_breaker_open_visible=circuit_breaker_open_visible,
        circuit_breaker_close_visible=circuit_breaker_close_visible,
        local_capabilities_available=_REQUIRED_LOCAL_CAPABILITIES,
        metric_public_labels=(
            "component=llm-gateway",
            f"status={public_status}",
            f"failure_case={case_id}",
        ),
        outbox_event_ids=(f"OUTBOX-{case_id}",),
    )


def _build_drill(
    *,
    drill_id: str,
    policy_version: str,
    cases: Sequence[SparkFailureCase],
) -> SparkFailureDrill:
    parsed_cases = _required_case_tuple(cases)
    cases_by_failure_mode: dict[str, SparkFailureCase] = {}
    for failure_case in parsed_cases:
        if failure_case.failure_mode in cases_by_failure_mode:
            raise ValueError("mode panne Spark dupliqué")
        cases_by_failure_mode[failure_case.failure_mode] = failure_case

    return SparkFailureDrill(
        drill_id=_required_text(drill_id, "drill_id"),
        policy_version=_required_policy_version(policy_version),
        cases=parsed_cases,
        cases_by_failure_mode=MappingProxyType(cases_by_failure_mode),
        consumer_contexts=tuple(sorted({item.consumer_context for item in parsed_cases})),
        public_statuses=tuple(sorted({item.public_status for item in parsed_cases})),
        local_capabilities_available=tuple(sorted(set().union(*(item.local_capabilities_available for item in parsed_cases)))),
        acceptance_allowed=True,
    )


def _required_case_tuple(values: Sequence[SparkFailureCase]) -> tuple[SparkFailureCase, ...]:
    if isinstance(values, str) or not isinstance(values, Sequence):
        raise ValueError("cas panne Spark invalides")
    cases = tuple(values)
    if len(cases) == 0:
        raise ValueError("cas panne Spark absents")
    for failure_case in cases:
        if not isinstance(failure_case, SparkFailureCase):
            raise ValueError("SparkFailureCase requis")
    return cases


def _required_policy_version(value: Any) -> str:
    text = _required_text(value, "policy_version")
    if text != SPARK_FAILURE_DRILL_POLICY_VERSION:
        raise ValueError("version politique panne Spark incohérente")
    return text


def _required_failure_mode(value: Any) -> str:
    text = _required_text(value, "failure_mode")
    if text not in _REQUIRED_FAILURE_MODES:
        raise ValueError("mode panne Spark inconnu")
    return text


def _required_context(value: Any) -> str:
    text = _required_text(value, "consumer_context")
    if text not in _REQUIRED_CONSUMER_CONTEXTS:
        raise ValueError("consommateur V1 inconnu")
    return text


def _required_text_tuple(values: Sequence[str], field_name: str, *, allow_empty: bool) -> tuple[str, ...]:
    if isinstance(values, str) or not isinstance(values, Sequence):
        raise ValueError(f"{field_name} invalide")
    parsed = tuple(_required_text(value, field_name) for value in values)
    if not allow_empty and len(parsed) == 0:
        raise ValueError(f"{field_name} vide")
    return parsed


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalisé")
    return value


def _required_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} non booléen")
    return value


def _required_non_negative_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} invalide")
    return value


def _is_blank(value: Any) -> bool:
    return not isinstance(value, str) or value.strip() == ""


__all__ = [
    "FAILURE_API_KEY_REJECTED",
    "FAILURE_CIRCUIT_BREAKER_CLOSED",
    "FAILURE_CIRCUIT_BREAKER_OPEN",
    "FAILURE_FIRST_TOKEN_TIMEOUT",
    "FAILURE_SPARK_UNAVAILABLE",
    "FAILURE_STREAM_CUT_AFTER_FIRST_TOKEN",
    "FAILURE_STREAM_CUT_BEFORE_FIRST_TOKEN",
    "FAILURE_TLS_REJECTED",
    "LOCAL_CAPABILITY_AUDIT",
    "LOCAL_CAPABILITY_INGESTION",
    "LOCAL_CAPABILITY_RESTORE",
    "LOCAL_CAPABILITY_SEARCH",
    "SPARK_FAILURE_DRILL_POLICY_VERSION",
    "SparkFailureCase",
    "SparkFailureDrill",
    "SparkFailureDrillPolicy",
    "build_m013_spark_failure_drill",
]
