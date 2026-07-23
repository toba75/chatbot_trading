"""Validation stricte de la preuve de baseline locale M14-distribution-core."""

from __future__ import annotations

from datetime import datetime
from pathlib import PurePosixPath
import re
from typing import Any, Mapping, Sequence


_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_GIT_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_EVIDENCE_ID_PATTERN = re.compile(r"^M014-DISTRIBUTION-CORE-BASELINE-[0-9]{8}$")
_MEMORY_LIMIT_BYTES = 2 * 1024**3
_MEASUREMENT_FIELDS = frozenset(
    {
        "workers",
        "worker_ids",
        "duration_seconds",
        "memory_limit_bytes",
        "peak_ram_bytes_by_worker",
        "peak_vram_mib",
        "peak_gpu_utilization_percent",
        "cuda_device",
        "cuda_activity_observed",
        "outputs",
    }
)
_REQUIRED_MECHANISMS = frozenset(
    {
        "POSTGRESQL_JOB_QUEUE",
        "FOR_UPDATE_SKIP_LOCKED",
        "LEASE",
        "CLAIM_GENERATION",
        "CLAIM_TOKEN",
        "FENCED_MUTATIONS",
        "PERSISTED_PUBLIC_PROGRESS",
        "SHARED_DOCLING_LIMITER",
        "GRANITE_CUDA_STRICT",
        "LOCAL_PROFILE_VOLUMES",
        "TWO_DOCUMENT_WORKER_REPLICAS",
    }
)
_REQUIRED_MODULES = frozenset(
    {
        "app/contracts/technical_jobs.py",
        "app/platform/job_runtime/postgres.py",
        "app/platform/job_runtime/heartbeat.py",
        "app/source_processing/adapters/worker_runtime.py",
        "app/source_processing/application/routed_document_conversion_worker.py",
    }
)
_REQUIRED_TABLES = frozenset(
    {
        "platform.technical_jobs",
        "source_processing.job_outbox",
        "source_processing.document_processing_runs",
        "source_processing.document_conversion_requests",
        "source_processing.page_manifest_entries",
        "source_processing.page_routes",
    }
)
_REQUIRED_MIGRATIONS = frozenset(
    {
        "deploy/postgres/migrations/003_document_worker_runtime.sql",
        "deploy/postgres/migrations/008_claim_fencing_and_projection_replay.sql",
        "deploy/postgres/migrations/012_document_conversion_public_progress.sql",
        "deploy/postgres/migrations/014_document_conversion_incremental_progress.sql",
        "deploy/postgres/migrations/020_job_environment_identity.sql",
        "deploy/postgres/migrations/021_job_environment_identity_hardening.sql",
    }
)
_REQUIRED_CONFIGURATIONS = frozenset(
    {
        "config/docling-assets.granite.json",
        "config/environments/test.yaml",
        "deploy/environments/compose.base.yaml",
        "deploy/environments/test.compose.yaml",
    }
)
_EXCLUDED_CAPABILITIES = (
    "ssh",
    "kamal",
    "colima",
    "arm64",
    "remote_worker",
)
_ENABLED_CAPABILITIES = frozenset({"docker_local", "postgresql_local", "cuda_local"})


class DistributionBaselineError(ValueError):
    """Erreur stable d'une preuve de baseline absente, synthétique ou incomplète."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def validate_distribution_baseline(payload: Mapping[str, Any]) -> None:
    """Valide la preuve complète sans déduire ni compléter aucun champ."""

    root = _mapping(
        payload,
        {
            "schema_version",
            "evidence_id",
            "evidence_kind",
            "evidence_status",
            "synthetic",
            "measurement_origin",
            "measured_at",
            "git_references",
            "environment",
            "workload",
            "runtime_identity",
            "measurements",
            "inventory",
            "network_scope",
            "historical_context",
        },
        "M014_BASELINE_FIELDS_INVALID",
    )
    if (
        root["schema_version"] != "1.0"
        or not isinstance(root["evidence_id"], str)
        or _EVIDENCE_ID_PATTERN.fullmatch(root["evidence_id"]) is None
        or root["evidence_kind"] != "M014_DISTRIBUTION_CORE_LOCAL_BASELINE"
    ):
        raise DistributionBaselineError("M014_BASELINE_IDENTITY_INVALID")
    if (
        root["evidence_status"] != "MEASURED_LIVE"
        or root["synthetic"] is not False
        or root["measurement_origin"] != "LIVE_DOCKER_TEST_PROFILE"
    ):
        raise DistributionBaselineError("M014_BASELINE_LIVE_PROOF_REQUIRED")
    measured_at = root["measured_at"]
    if (
        not isinstance(measured_at, str)
        or datetime.fromisoformat(measured_at).tzinfo is None
    ):
        raise DistributionBaselineError("M014_BASELINE_MEASURED_AT_INVALID")

    _validate_git_references(root["git_references"])
    _validate_environment(root["environment"])
    _validate_workload(root["workload"])
    _validate_runtime_identity(root["runtime_identity"])
    _validate_inventory(root["inventory"])
    _validate_network_scope(root["network_scope"])
    _validate_historical_context(root["historical_context"])

    measurements = _mapping(
        root["measurements"],
        {"single_worker", "two_workers"},
        "M014_BASELINE_MEASUREMENTS_INVALID",
    )
    fingerprints: list[str] = []
    fingerprints.extend(
        _validate_measurement(measurements["single_worker"], expected_workers=1)
    )
    fingerprints.extend(
        _validate_measurement(measurements["two_workers"], expected_workers=2)
    )
    if len(set(fingerprints)) != 1:
        raise DistributionBaselineError("M014_BASELINE_OUTPUT_DIVERGENCE")


def _validate_git_references(value: Any) -> None:
    references = _mapping(
        value,
        {"master", "baseline_branch", "granite_cuda", "worker_memory_limit"},
        "M014_BASELINE_GIT_REFERENCES_INVALID",
    )
    if any(
        not isinstance(commit, str) or _GIT_COMMIT_PATTERN.fullmatch(commit) is None
        for commit in references.values()
    ):
        raise DistributionBaselineError("M014_BASELINE_GIT_REFERENCES_INVALID")


def _validate_environment(value: Any) -> None:
    environment = _mapping(
        value,
        {"profile", "deployment_id", "configuration_hash"},
        "M014_BASELINE_ENVIRONMENT_INVALID",
    )
    if (
        environment["profile"] != "test"
        or environment["deployment_id"] != "ostrading-test-ci"
        or not _is_sha256(environment["configuration_hash"])
    ):
        raise DistributionBaselineError("M014_BASELINE_ENVIRONMENT_INVALID")


def _validate_workload(value: Any) -> None:
    workload = _mapping(
        value,
        {
            "fixture_path",
            "fixture_sha256",
            "page_number",
            "source_page_number",
            "route_name",
        },
        "M014_BASELINE_WORKLOAD_INVALID",
    )
    if (
        workload["fixture_path"]
        != "data/corpus/ostrading-environment-qualification-5-pages.pdf"
        or not _is_sha256(workload["fixture_sha256"])
        or workload["page_number"] != 2
        or workload["source_page_number"] != 2
        or workload["route_name"] != "MIXED_PAGEWISE"
    ):
        raise DistributionBaselineError("M014_BASELINE_WORKLOAD_INVALID")


def _validate_runtime_identity(value: Any) -> None:
    runtime = _mapping(
        value,
        {
            "image_reference",
            "image_digest",
            "image_revision",
            "asset_manifest_path",
            "asset_manifest_sha256",
            "model_repository",
            "model_revision",
            "docling_version",
            "torch_version",
            "cuda_version",
            "gpu_name",
            "gpu_driver",
            "docker_server_version",
        },
        "M014_BASELINE_RUNTIME_IDENTITY_INVALID",
    )
    image_digest = runtime["image_digest"]
    if (
        not isinstance(image_digest, str)
        or not image_digest.startswith("sha256:")
        or not _is_sha256(image_digest.removeprefix("sha256:"))
        or runtime["image_reference"] != f"ostrading/worker-documents@{image_digest}"
        or not isinstance(runtime["image_revision"], str)
        or _GIT_COMMIT_PATTERN.fullmatch(runtime["image_revision"]) is None
        or runtime["asset_manifest_path"] != "config/docling-assets.granite.json"
        or not _is_sha256(runtime["asset_manifest_sha256"])
        or runtime["model_repository"] != "ibm-granite/granite-docling-258M"
        or not isinstance(runtime["model_revision"], str)
        or _GIT_COMMIT_PATTERN.fullmatch(runtime["model_revision"]) is None
        or runtime["docling_version"] != "2.111.0"
        or runtime["torch_version"] != "2.13.0+cu130"
        or runtime["cuda_version"] != "13.0"
        or runtime["gpu_name"] != "NVIDIA GeForce RTX 4090 Laptop GPU"
        or not _non_empty_text(runtime["gpu_driver"])
        or not _non_empty_text(runtime["docker_server_version"])
    ):
        raise DistributionBaselineError("M014_BASELINE_RUNTIME_IDENTITY_INVALID")


def _validate_measurement(value: Any, *, expected_workers: int) -> list[str]:
    measurement = _mapping(
        value,
        _MEASUREMENT_FIELDS,
        "M014_BASELINE_MEASUREMENT_FIELDS_INVALID",
    )
    if measurement["workers"] != expected_workers:
        raise DistributionBaselineError("M014_BASELINE_WORKER_COUNT_INVALID")
    worker_ids = _text_sequence(measurement["worker_ids"])
    if len(worker_ids) != expected_workers or len(set(worker_ids)) != expected_workers:
        raise DistributionBaselineError("M014_BASELINE_WORKER_IDENTITIES_INVALID")
    duration = measurement["duration_seconds"]
    if (
        isinstance(duration, bool)
        or not isinstance(duration, int | float)
        or duration <= 0
    ):
        raise DistributionBaselineError("M014_BASELINE_DURATION_INVALID")
    if measurement["memory_limit_bytes"] != _MEMORY_LIMIT_BYTES:
        raise DistributionBaselineError("M014_BASELINE_MEMORY_LIMIT_INVALID")
    ram_by_worker = _mapping(
        measurement["peak_ram_bytes_by_worker"],
        set(worker_ids),
        "M014_BASELINE_RAM_METRICS_INVALID",
    )
    if any(
        isinstance(peak, bool)
        or not isinstance(peak, int)
        or peak <= 0
        or peak > _MEMORY_LIMIT_BYTES
        for peak in ram_by_worker.values()
    ):
        raise DistributionBaselineError("M014_BASELINE_RAM_METRICS_INVALID")
    for field_name in ("peak_vram_mib", "peak_gpu_utilization_percent"):
        metric = measurement[field_name]
        if (
            isinstance(metric, bool)
            or not isinstance(metric, int | float)
            or metric <= 0
        ):
            raise DistributionBaselineError("M014_BASELINE_CUDA_PROOF_MISSING")
    if (
        measurement["peak_gpu_utilization_percent"] > 100
        or measurement["cuda_device"] != "cuda:0"
        or measurement["cuda_activity_observed"] is not True
    ):
        raise DistributionBaselineError("M014_BASELINE_CUDA_PROOF_MISSING")
    outputs = measurement["outputs"]
    if (
        isinstance(outputs, str)
        or not isinstance(outputs, Sequence)
        or len(outputs) != expected_workers
    ):
        raise DistributionBaselineError("M014_BASELINE_OUTPUTS_INVALID")
    output_ids: list[str] = []
    fingerprints: list[str] = []
    for output_value in outputs:
        output = _mapping(
            output_value,
            {"worker_id", "response_sha256", "item_count", "provenances"},
            "M014_BASELINE_OUTPUTS_INVALID",
        )
        worker_id = output["worker_id"]
        if not isinstance(worker_id, str) or worker_id not in worker_ids:
            raise DistributionBaselineError("M014_BASELINE_OUTPUTS_INVALID")
        if not _is_sha256(output["response_sha256"]):
            raise DistributionBaselineError("M014_BASELINE_HASH_INVALID")
        if (
            isinstance(output["item_count"], bool)
            or not isinstance(output["item_count"], int)
            or output["item_count"] <= 0
            or _text_sequence(output["provenances"]) != ("granite_docling",)
        ):
            raise DistributionBaselineError("M014_BASELINE_OUTPUTS_INVALID")
        output_ids.append(worker_id)
        fingerprints.append(output["response_sha256"])
    if set(output_ids) != set(worker_ids) or len(set(output_ids)) != expected_workers:
        raise DistributionBaselineError("M014_BASELINE_OUTPUTS_INVALID")
    return fingerprints


def _validate_inventory(value: Any) -> None:
    inventory = _mapping(
        value,
        {"modules", "tables", "migrations", "configurations", "mechanisms"},
        "M014_BASELINE_INVENTORY_INVALID",
    )
    collections = (
        (_text_sequence(inventory["modules"]), _REQUIRED_MODULES),
        (_text_sequence(inventory["tables"]), _REQUIRED_TABLES),
        (_text_sequence(inventory["migrations"]), _REQUIRED_MIGRATIONS),
        (_text_sequence(inventory["configurations"]), _REQUIRED_CONFIGURATIONS),
        (_text_sequence(inventory["mechanisms"]), _REQUIRED_MECHANISMS),
    )
    if any(frozenset(observed) != expected for observed, expected in collections):
        raise DistributionBaselineError("M014_BASELINE_INVENTORY_INVALID")
    for path in (*collections[0][0], *collections[2][0], *collections[3][0]):
        if PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts:
            raise DistributionBaselineError("M014_BASELINE_INVENTORY_INVALID")


def _validate_network_scope(value: Any) -> None:
    network = _mapping(
        value,
        {"physical_hosts", "locality", "enabled_capabilities", "excluded_capabilities"},
        "M014_BASELINE_NETWORK_SCOPE_INVALID",
    )
    enabled = _text_sequence(network["enabled_capabilities"])
    if any(capability in enabled for capability in _EXCLUDED_CAPABILITIES):
        raise DistributionBaselineError("M014_BASELINE_REMOTE_CAPABILITY_FORBIDDEN")
    if (
        _text_sequence(network["physical_hosts"]) != ("local-station-amd64",)
        or network["locality"] != "LOCAL_ONLY"
        or frozenset(enabled) != _ENABLED_CAPABILITIES
        or _text_sequence(network["excluded_capabilities"]) != _EXCLUDED_CAPABILITIES
    ):
        raise DistributionBaselineError("M014_BASELINE_NETWORK_SCOPE_INVALID")


def _validate_historical_context(value: Any) -> None:
    historical = _mapping(
        value,
        {"source", "reused_as_live_measurement", "plan_measurements_status"},
        "M014_BASELINE_HISTORICAL_CONTEXT_INVALID",
    )
    if (
        historical["source"] != "docs/specs/plan_distribution.md"
        or historical["reused_as_live_measurement"] is not False
        or historical["plan_measurements_status"] != "HISTORICAL_NOT_REUSED"
    ):
        raise DistributionBaselineError("M014_BASELINE_HISTORICAL_CONTEXT_INVALID")


def _mapping(
    value: Any, expected_fields: set[str] | frozenset[str], code: str
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != set(expected_fields):
        raise DistributionBaselineError(code)
    return value


def _text_sequence(value: Any) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise DistributionBaselineError("M014_BASELINE_SEQUENCE_INVALID")
    parsed = tuple(value)
    if len(parsed) == 0 or any(not _non_empty_text(item) for item in parsed):
        raise DistributionBaselineError("M014_BASELINE_SEQUENCE_INVALID")
    return parsed


def _non_empty_text(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != "" and value == value.strip()


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and _SHA256_PATTERN.fullmatch(value) is not None


__all__ = ["DistributionBaselineError", "validate_distribution_baseline"]
