from __future__ import annotations

from dataclasses import FrozenInstanceError
import inspect

import pytest


def test_worker_environment_identity_unit() -> None:
    from app.contracts.technical_jobs import (
        JobEnvironmentIdentity,
        JobIdempotenceKey,
        JobPriority,
        JobRequest,
    )
    from app.platform.worker_environment import (
        WORKER_ENVIRONMENT_MISMATCH,
        WORKER_JOB_NAMES,
        WorkerEnvironmentBinding,
        WorkerEnvironmentMismatchError,
    )

    development = JobEnvironmentIdentity(
        environment="development",
        deployment_id="ostrading-development-local",
        configuration_hash="a" * 64,
    )
    assert development.to_mapping() == {
        "environment": "development",
        "deployment_id": "ostrading-development-local",
        "configuration_hash": "a" * 64,
    }
    with pytest.raises(FrozenInstanceError):
        development.environment = "test"  # type: ignore[misc]
    for invalid_environment in ("", "local", "Development", None):
        with pytest.raises(ValueError, match="environment invalide"):
            JobEnvironmentIdentity(
                environment=invalid_environment,  # type: ignore[arg-type]
                deployment_id="ostrading-development-local",
                configuration_hash="a" * 64,
            )
    with pytest.raises(ValueError, match="deployment_id invalide"):
        JobEnvironmentIdentity(
            environment="development",
            deployment_id="",
            configuration_hash="a" * 64,
        )
    with pytest.raises(ValueError, match="configuration_hash invalide"):
        JobEnvironmentIdentity(
            environment="development",
            deployment_id="ostrading-development-local",
            configuration_hash="not-a-hash",
        )

    assert tuple(WORKER_JOB_NAMES) == (
        "worker-documents",
        "worker-projection",
    )
    assert WORKER_JOB_NAMES["worker-documents"] == (
        "DIAGNOSE",
        "CONVERT_DOCUMENT",
        "CONVERT_PAGE",
        "ASSEMBLE_CANONICAL_DOCUMENT",
    )
    assert WORKER_JOB_NAMES["worker-projection"] == ("PROJECT_DOCUMENT",)

    binding = WorkerEnvironmentBinding(
        worker_id="worker-documents",
        identity=development,
        job_names=WORKER_JOB_NAMES["worker-documents"],
    )
    assert binding.health_snapshot().to_mapping() == {
        "service": "worker-documents",
        "status": "ready",
        "environment": "development",
        "deployment_id": "ostrading-development-local",
        "configuration_hash": "a" * 64,
    }
    assert binding.instance_owner_id("00000000-0000-4000-8000-000000000001") == (
        "development:ostrading-development-local:worker-documents:"
        "00000000-0000-4000-8000-000000000001"
    )

    foreign = JobRequest(
        environment="test",
        deployment_id="ostrading-test-ci",
        job_name="DIAGNOSE",
        priority=JobPriority.P1,
        idempotence_key=JobIdempotenceKey(
            job_name="DIAGNOSE",
            input_hash="b" * 64,
            configuration_hash="a" * 64,
            code_version="worker-environment-unit",
            model_version="none",
        ),
        execution_requirements=None,
        payload={"document_id": "DOC-M013-ENV-WORKER-UNIT"},
    )
    with pytest.raises(WorkerEnvironmentMismatchError) as mismatch:
        binding.require_job_request(foreign)
    assert mismatch.value.code == WORKER_ENVIRONMENT_MISMATCH
    assert str(mismatch.value) == WORKER_ENVIRONMENT_MISMATCH

    from app.platform.job_runtime.postgres import PostgresJobQueue
    from app.platform.job_runtime.relay import RelayOutbox

    claim_source = inspect.getsource(PostgresJobQueue.claim_next)
    assert "configuration_hash <> %s" not in claim_source
    assert "configuration_hash = %s" in claim_source
    assert "reject_environment_mismatch" in RelayOutbox.__dict__
