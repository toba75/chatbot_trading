"""Tests unitaires T-004 du runtime Granite supervisé et terminal."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import inspect
from pathlib import Path
from uuid import uuid4

import pytest
import yaml

from app.contracts.technical_jobs import (
    ClaimedJob,
    JobEnvironmentIdentity,
    JobExecutionRequirements,
    JobIdempotenceKey,
    JobPriority,
    JobRecord,
    JobRequest,
    JobStatus,
)
from app.platform.job_runtime.granite_capacity import (
    GraniteCapacityController,
    GraniteModelStillRunning,
    GranitePageTerminalEnvelope,
    GranitePageTerminalStatus,
    GraniteSlotLease,
    GraniteSlotLeaseLostError,
    GraniteWorker,
    GraniteWorkerState,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


def _requirements() -> JobExecutionRequirements:
    return JobExecutionRequirements(
        contract_name="CONVERT_PAGE",
        contract_version="1.0",
        capacity_capability="GRANITE_CUDA",
        capacity_slots=1,
        capacity_device="cuda:0",
        storage_environment="test",
        source_artifact_ref="artifact:source_processing.local/test/source.pdf",
        result_artifact_ref="artifact:source_processing.local/test/page-1.json",
        route_name="SCAN_GRANITE",
    )


def _lease() -> GraniteSlotLease:
    identity = JobEnvironmentIdentity(
        environment="test",
        deployment_id="ostrading-test-local",
        configuration_hash="a" * 64,
    )
    request = JobRequest(
        environment=identity.environment,
        deployment_id=identity.deployment_id,
        job_name="CONVERT_PAGE",
        priority=JobPriority.P1,
        idempotence_key=JobIdempotenceKey(
            job_name="CONVERT_PAGE",
            input_hash="b" * 64,
            configuration_hash=identity.configuration_hash,
            code_version="m014-runtime",
            model_version="granite-locked",
        ),
        execution_requirements=_requirements(),
        payload={"contract_version": "1.0"},
    )
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=30)
    claimed = ClaimedJob(
        job=JobRecord(
            sequence=1,
            job_id="JOB-M002-000001",
            request=request,
            status=JobStatus.RUNNING,
            result=None,
            failure_reason=None,
        ),
        trace_id="TRACE-M014-RUNTIME",
        lease_owner="worker-documents-1",
        lease_expires_at=expires_at,
        claim_generation=1,
        claim_token=str(uuid4()),
        execution_attempts=1,
    )
    return GraniteSlotLease(
        claimed_job=claimed,
        slot_ordinal=1,
        slot_generation=1,
        slot_token=str(uuid4()),
        lease_until=expires_at,
    )


def _worker() -> GraniteWorker:
    return GraniteWorker(
        worker_instance_id="worker-documents-1",
        environment_identity=_lease().claimed_job.job.request.environment_identity,
        storage_environment="test",
        state=GraniteWorkerState.READY,
        capabilities=frozenset(("DOCUMENT_STANDARD", "GRANITE_CUDA")),
    )


def _terminal(
    lease: GraniteSlotLease,
    status: GranitePageTerminalStatus,
    payload: dict[str, object],
) -> GranitePageTerminalEnvelope:
    return GranitePageTerminalEnvelope.from_payload(
        completion_id=f"COMPLETE-{lease.claimed_job.job.job_id}-{status.value}",
        status=status,
        payload=payload,
        failure_reason=(
            None if status is GranitePageTerminalStatus.SUCCEEDED else "MODEL_FAILED"
        ),
    )


class _Process:
    def __init__(self, outcomes: list[object]) -> None:
        self._outcomes = outcomes
        self.terminated = False
        self.wait_timeouts: list[float] = []

    def wait(self, *, timeout_seconds: float):
        self.wait_timeouts.append(timeout_seconds)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    def terminate(self) -> None:
        self.terminated = True


class _Repository:
    def __init__(self, *, heartbeat_failure: Exception | None = None) -> None:
        self.lease = _lease()
        self.heartbeat_failure = heartbeat_failure
        self.heartbeats = 0
        self.terminals: list[GranitePageTerminalEnvelope] = []
        self.claim_enabled = True
        self.terminal_failure: Exception | None = None
        self.legacy_acquisitions: list[GraniteSlotLease | None] = []
        self.releases: list[GraniteSlotLease] = []

    def claim_compatible_job(self, **_arguments):
        return self.lease if self.claim_enabled else None

    def heartbeat(self, lease, *, lease_seconds):
        assert lease_seconds == 30
        self.heartbeats += 1
        if self.heartbeat_failure is not None:
            raise self.heartbeat_failure
        return lease

    def complete_page_execution(self, lease, envelope):
        assert lease == self.lease
        if self.terminal_failure is not None:
            raise self.terminal_failure
        self.terminals.append(envelope)
        return lease.claimed_job.job

    def acquire_for_claimed_job(self, *, worker, claimed_job):
        assert claimed_job == self.lease.claimed_job
        if self.legacy_acquisitions:
            return self.legacy_acquisitions.pop(0)
        return self.lease

    def release(self, lease):
        self.releases.append(lease)


def test_runtime_granite_supervise_heartbeat_annulation_et_terminal_atomique() -> None:
    """Given un job Granite leased, When il bloque ou perd sa lease, Then le processus reste supervisé."""

    repository = _Repository()
    process = _Process(
        [GraniteModelStillRunning(), GraniteModelStillRunning(), {"answer": "ok"}]
    )
    execution = GraniteCapacityController(repository=repository).execute_next(
        worker=_worker(),
        lease_seconds=30,
        heartbeat_seconds=0.01,
        job_names=("CONVERT_PAGE",),
        execution_requirements=_requirements(),
        start_model=lambda _lease: process,
        success_envelope=lambda lease, result: _terminal(
            lease,
            GranitePageTerminalStatus.SUCCEEDED,
            result,
        ),
        failure_envelope=lambda lease, _error: _terminal(
            lease,
            GranitePageTerminalStatus.FAILED,
            {"error_code": "MODEL_FAILED"},
        ),
    )
    assert execution is not None
    assert execution.model_result == {"answer": "ok"}
    assert repository.heartbeats == 2
    assert len(repository.terminals) == 1
    assert repository.terminals[0].status is GranitePageTerminalStatus.SUCCEEDED
    assert process.terminated is False

    lost_repository = _Repository(heartbeat_failure=GraniteSlotLeaseLostError())
    blocked_process = _Process([GraniteModelStillRunning()])
    with pytest.raises(GraniteSlotLeaseLostError, match="JOB_LEASE_LOST"):
        GraniteCapacityController(repository=lost_repository).execute_next(
            worker=_worker(),
            lease_seconds=30,
            heartbeat_seconds=0.01,
            job_names=("CONVERT_PAGE",),
            execution_requirements=_requirements(),
            start_model=lambda _lease: blocked_process,
            success_envelope=lambda lease, result: _terminal(
                lease, GranitePageTerminalStatus.SUCCEEDED, result
            ),
            failure_envelope=lambda lease, _error: _terminal(
                lease,
                GranitePageTerminalStatus.FAILED,
                {"error_code": "MODEL_FAILED"},
            ),
        )
    assert blocked_process.terminated is True
    assert lost_repository.terminals == []

    primary = RuntimeError("GRANITE_MODEL_PRIMARY")
    compensation = RuntimeError("GRANITE_TERMINAL_COMPENSATION_FAILED")
    failing_repository = _Repository()
    failing_repository.terminal_failure = compensation
    with pytest.raises(ExceptionGroup) as captured:
        GraniteCapacityController(repository=failing_repository).execute_next(
            worker=_worker(),
            lease_seconds=30,
            heartbeat_seconds=0.01,
            job_names=("CONVERT_PAGE",),
            execution_requirements=_requirements(),
            start_model=lambda _lease: _Process([primary]),
            success_envelope=lambda lease, result: _terminal(
                lease, GranitePageTerminalStatus.SUCCEEDED, result
            ),
            failure_envelope=lambda lease, _error: _terminal(
                lease,
                GranitePageTerminalStatus.FAILED,
                {"error_code": "MODEL_FAILED"},
            ),
        )
    assert captured.value.exceptions == (primary, compensation)

    waiting_repository = _Repository()
    waiting_repository.claim_enabled = False
    model_started: list[object] = []
    assert (
        GraniteCapacityController(repository=waiting_repository).execute_next(
            worker=_worker(),
            lease_seconds=30,
            heartbeat_seconds=0.01,
            job_names=("CONVERT_PAGE",),
            execution_requirements=_requirements(),
            start_model=lambda lease: model_started.append(lease),
            success_envelope=lambda lease, result: _terminal(
                lease, GranitePageTerminalStatus.SUCCEEDED, result
            ),
            failure_envelope=lambda lease, _error: _terminal(
                lease,
                GranitePageTerminalStatus.FAILED,
                {"error_code": "MODEL_FAILED"},
            ),
        )
        is None
    )
    assert model_started == []

    legacy_repository = _Repository()
    legacy_repository.legacy_acquisitions = [None, legacy_repository.lease]
    legacy_model_starts: list[GraniteSlotLease] = []
    legacy_execution = GraniteCapacityController(
        repository=legacy_repository
    ).execute_claimed_job(
        worker=_worker(),
        claimed_job=legacy_repository.lease.claimed_job,
        lease_seconds=30,
        heartbeat_seconds=0.01,
        start_model=lambda lease: (
            legacy_model_starts.append(lease) or _Process([{"legacy": "ok"}])
        ),
    )
    assert legacy_execution.model_result == {"legacy": "ok"}
    assert legacy_model_starts == [legacy_repository.lease]
    assert legacy_repository.releases == [legacy_repository.lease]

    parameter = inspect.signature(JobRequest).parameters["execution_requirements"]
    assert parameter.default is inspect.Parameter.empty

    for relative_path in (
        "config/application.example.yaml",
        "config/environments/development.yaml",
        "config/environments/test.yaml",
        "config/environments/production.yaml",
        "deploy/local-compose/application.compose.yaml",
    ):
        configuration = yaml.safe_load(
            (REPOSITORY_ROOT / relative_path).read_text("utf-8")
        )
        assert configuration["services"]["workers"]["granite_concurrency"] == 1

    quota_source = (
        REPOSITORY_ROOT / "app/platform/job_runtime/granite_capacity.py"
    ).read_text("utf-8")
    assert "payload ->" not in quota_source
    assert "%(environment)s" in quota_source

    composition_source = (
        REPOSITORY_ROOT / "app/platform/job_runtime/composition.py"
    ).read_text("utf-8")
    assert "GraniteCapacityController" in composition_source
    assert "PostgresGraniteWorkerRegistry" in composition_source

    for converter_path in (
        "app/source_processing/adapters/docling_granite_conversion.py",
        "app/source_processing/adapters/gemma_vision_conversion.py",
    ):
        converter_source = (REPOSITORY_ROOT / converter_path).read_text("utf-8")
        assert "subprocess.Popen" in converter_source
        assert "subprocess.run(" not in converter_source
