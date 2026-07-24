"""Tests unitaires du validateur de preuve M14-distribution-core."""

from __future__ import annotations

from copy import deepcopy

import pytest

from ost_gate.m014_distribution_core import (
    DistributionBaselineError,
    validate_distribution_baseline,
)


HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
HASH_D = "d" * 64
GIT_A = "a" * 40
GIT_B = "b" * 40
GIT_C = "c" * 40
GIT_D = "d" * 40


def _measurement(*, workers: int) -> dict[str, object]:
    worker_ids = [f"worker-documents-{index}" for index in range(1, workers + 1)]
    return {
        "workers": workers,
        "worker_ids": worker_ids,
        "duration_seconds": 20.5,
        "memory_limit_bytes": 2 * 1024**3,
        "peak_ram_bytes_by_worker": {
            worker_id: 1536 * 1024**2 for worker_id in worker_ids
        },
        "peak_vram_mib": 2790,
        "peak_gpu_utilization_percent": 93,
        "cuda_device": "cuda:0",
        "cuda_activity_observed": True,
        "outputs": [
            {
                "worker_id": worker_id,
                "response_sha256": HASH_A,
                "item_count": 2,
                "provenances": ["granite_docling"],
            }
            for worker_id in worker_ids
        ],
    }


def _valid_payload() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "evidence_id": "M014-DISTRIBUTION-CORE-BASELINE-20260723",
        "evidence_kind": "M014_DISTRIBUTION_CORE_LOCAL_BASELINE",
        "evidence_status": "MEASURED_LIVE",
        "synthetic": False,
        "measurement_origin": "LIVE_DOCKER_TEST_PROFILE",
        "measured_at": "2026-07-23T21:00:00+02:00",
        "git_references": {
            "master": GIT_A,
            "baseline_branch": GIT_B,
            "granite_cuda": GIT_C,
            "worker_memory_limit": GIT_D,
        },
        "environment": {
            "profile": "test",
            "deployment_id": "ostrading-test-ci",
            "configuration_hash": HASH_A,
        },
        "workload": {
            "fixture_path": "data/corpus/ostrading-environment-qualification-5-pages.pdf",
            "fixture_sha256": HASH_B,
            "page_number": 2,
            "source_page_number": 2,
            "route_name": "MIXED_PAGEWISE",
        },
        "runtime_identity": {
            "image_reference": "ostrading/worker-documents@sha256:" + HASH_C,
            "image_digest": "sha256:" + HASH_C,
            "image_revision": GIT_D,
            "asset_manifest_path": "config/docling-assets.granite.json",
            "asset_manifest_sha256": HASH_A,
            "model_repository": "ibm-granite/granite-docling-258M",
            "model_revision": GIT_B,
            "docling_version": "2.111.0",
            "torch_version": "2.13.0+cu130",
            "cuda_version": "13.0",
            "gpu_name": "NVIDIA GeForce RTX 4090 Laptop GPU",
            "gpu_driver": "610.62",
            "docker_server_version": "29.1.5",
        },
        "measurements": {
            "single_worker": _measurement(workers=1),
            "two_workers": _measurement(workers=2),
        },
        "inventory": {
            "modules": [
                "app/contracts/technical_jobs.py",
                "app/platform/job_runtime/postgres.py",
                "app/platform/job_runtime/heartbeat.py",
                "app/source_processing/adapters/worker_runtime.py",
                "app/source_processing/application/routed_document_conversion_worker.py",
            ],
            "tables": [
                "platform.technical_jobs",
                "source_processing.job_outbox",
                "source_processing.document_processing_runs",
                "source_processing.document_conversion_requests",
                "source_processing.page_manifest_entries",
                "source_processing.page_routes",
            ],
            "migrations": [
                "deploy/postgres/migrations/003_document_worker_runtime.sql",
                "deploy/postgres/migrations/008_claim_fencing_and_projection_replay.sql",
                "deploy/postgres/migrations/012_document_conversion_public_progress.sql",
                "deploy/postgres/migrations/014_document_conversion_incremental_progress.sql",
                "deploy/postgres/migrations/020_job_environment_identity.sql",
                "deploy/postgres/migrations/021_job_environment_identity_hardening.sql",
            ],
            "configurations": [
                "config/docling-assets.granite.json",
                "config/environments/test.yaml",
                "deploy/environments/compose.base.yaml",
                "deploy/environments/test.compose.yaml",
            ],
            "mechanisms": [
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
            ],
        },
        "network_scope": {
            "physical_hosts": ["local-station-amd64"],
            "locality": "LOCAL_ONLY",
            "enabled_capabilities": ["docker_local", "postgresql_local", "cuda_local"],
            "excluded_capabilities": [
                "ssh",
                "kamal",
                "colima",
                "arm64",
                "remote_worker",
            ],
        },
        "historical_context": {
            "source": "docs/specs/plan_distribution.md",
            "reused_as_live_measurement": False,
            "plan_measurements_status": "HISTORICAL_NOT_REUSED",
        },
    }


def _assert_error(payload: dict[str, object], code: str) -> None:
    with pytest.raises(DistributionBaselineError, match=code):
        validate_distribution_baseline(payload)


def _baseline_complete_est_acceptee() -> None:
    validate_distribution_baseline(_valid_payload())


def _commit_absent_est_refuse() -> None:
    payload = _valid_payload()
    del payload["git_references"]["baseline_branch"]  # type: ignore[index]
    _assert_error(payload, "M014_BASELINE_GIT_REFERENCES_INVALID")


def _metrique_absente_est_refusee() -> None:
    payload = _valid_payload()
    del payload["measurements"]["single_worker"]["duration_seconds"]  # type: ignore[index]
    _assert_error(payload, "M014_BASELINE_MEASUREMENT_FIELDS_INVALID")


def _duree_non_positive_est_refusee() -> None:
    payload = _valid_payload()
    payload["measurements"]["single_worker"]["duration_seconds"] = 0  # type: ignore[index]
    _assert_error(payload, "M014_BASELINE_DURATION_INVALID")


def _hash_invalide_est_refuse() -> None:
    payload = _valid_payload()
    payload["measurements"]["single_worker"]["outputs"][0]["response_sha256"] = "bad"  # type: ignore[index]
    _assert_error(payload, "M014_BASELINE_HASH_INVALID")


def _sorties_divergentes_sont_refusees() -> None:
    payload = _valid_payload()
    payload["measurements"]["two_workers"]["outputs"][1]["response_sha256"] = HASH_B  # type: ignore[index]
    _assert_error(payload, "M014_BASELINE_OUTPUT_DIVERGENCE")


def _limite_memoire_differente_de_deux_gio_est_refusee() -> None:
    payload = _valid_payload()
    payload["measurements"]["two_workers"]["memory_limit_bytes"] = 8 * 1024**3  # type: ignore[index]
    _assert_error(payload, "M014_BASELINE_MEMORY_LIMIT_INVALID")


def _absence_de_preuve_cuda_est_refusee() -> None:
    payload = _valid_payload()
    payload["measurements"]["single_worker"]["cuda_activity_observed"] = False  # type: ignore[index]
    _assert_error(payload, "M014_BASELINE_CUDA_PROOF_MISSING")


def _capacite_distante_active_est_refusee(forbidden: str) -> None:
    payload = _valid_payload()
    payload["network_scope"]["enabled_capabilities"].append(forbidden)  # type: ignore[index]
    _assert_error(payload, "M014_BASELINE_REMOTE_CAPABILITY_FORBIDDEN")


def _preuve_synthetique_est_refusee() -> None:
    payload = deepcopy(_valid_payload())
    payload["synthetic"] = True
    _assert_error(payload, "M014_BASELINE_LIVE_PROOF_REQUIRED")


def test_validate_baseline_unit() -> None:
    _baseline_complete_est_acceptee()
    _commit_absent_est_refuse()
    _metrique_absente_est_refusee()
    _duree_non_positive_est_refusee()
    _hash_invalide_est_refuse()
    _sorties_divergentes_sont_refusees()
    _limite_memoire_differente_de_deux_gio_est_refusee()
    _absence_de_preuve_cuda_est_refusee()
    for forbidden in ("ssh", "kamal", "colima", "arm64", "remote_worker"):
        _capacite_distante_active_est_refusee(forbidden)
    _preuve_synthetique_est_refusee()
