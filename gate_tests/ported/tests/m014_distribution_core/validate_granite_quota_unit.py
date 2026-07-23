"""Tests unitaires T-004 des identités et transitions du quota Granite."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid1, uuid4

import pytest

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


def _claimed_job() -> ClaimedJob:
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
            code_version="m014-red",
            model_version="granite-locked",
        ),
        execution_requirements=JobExecutionRequirements(
            contract_name="CONVERT_PAGE",
            contract_version="1.0",
            capacity_capability="GRANITE_CUDA",
            capacity_slots=1,
            capacity_device="cuda:0",
            storage_environment="test",
            source_artifact_ref="artifact:source_processing.local/test/source.pdf",
            result_artifact_ref="artifact:source_processing.local/test/page-1.json",
            route_name="SCAN_GRANITE",
        ),
        payload={"required_capacity": "GRANITE_CUDA"},
    )
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=30)
    return ClaimedJob(
        job=JobRecord(
            sequence=1,
            job_id="JOB-M002-000001",
            request=request,
            status=JobStatus.RUNNING,
            result=None,
            failure_reason=None,
        ),
        trace_id="TRACE-M014-QUOTA-UNIT",
        lease_owner="worker-documents-1",
        lease_expires_at=expires_at,
        claim_generation=1,
        claim_token=str(uuid4()),
        execution_attempts=1,
    )


def _identite_slot_exige_ordinal_generation_uuid4_et_echeance_commune() -> None:
    from app.platform.job_runtime.granite_capacity import GraniteSlotLease

    claimed = _claimed_job()
    token = str(uuid4())
    lease = GraniteSlotLease(
        claimed_job=claimed,
        slot_ordinal=2,
        slot_generation=7,
        slot_token=token,
        lease_until=claimed.lease_expires_at,
    )

    assert lease.slot_ordinal == 2
    assert lease.slot_generation == 7
    assert UUID(lease.slot_token).version == 4

    invalid_values = (
        {"slot_ordinal": 3, "slot_generation": 7, "slot_token": token},
        {"slot_ordinal": 1, "slot_generation": 0, "slot_token": token},
        {"slot_ordinal": 1, "slot_generation": 7, "slot_token": str(uuid1())},
    )
    for values in invalid_values:
        with pytest.raises(ValueError, match="GRANITE_SLOT_IDENTITY_INVALID"):
            GraniteSlotLease(
                claimed_job=claimed,
                lease_until=claimed.lease_expires_at,
                **values,
            )

    with pytest.raises(ValueError, match="GRANITE_SLOT_LEASE_DEADLINE_MISMATCH"):
        GraniteSlotLease(
            claimed_job=claimed,
            slot_ordinal=1,
            slot_generation=7,
            slot_token=token,
            lease_until=claimed.lease_expires_at + timedelta(seconds=1),
        )


def _worker_generaliste_refuse_stockage_etranger_et_capacite_partielle() -> None:
    from app.platform.job_runtime.granite_capacity import (
        GraniteCapacityConfigurationError,
        GraniteWorker,
        GraniteWorkerState,
    )

    identity = JobEnvironmentIdentity(
        environment="test",
        deployment_id="ostrading-test-local",
        configuration_hash="a" * 64,
    )
    worker = GraniteWorker(
        worker_instance_id="worker-documents-1",
        environment_identity=identity,
        storage_environment="test",
        state=GraniteWorkerState.READY,
        capabilities=frozenset(("DOCUMENT_STANDARD", "GRANITE_CUDA")),
    )
    assert worker.state is GraniteWorkerState.READY

    with pytest.raises(
        GraniteCapacityConfigurationError,
        match="GRANITE_CAPACITY_CONFIGURATION_INVALID",
    ):
        GraniteWorker(
            worker_instance_id="worker-documents-1",
            environment_identity=identity,
            storage_environment="production",
            state=GraniteWorkerState.READY,
            capabilities=frozenset(("DOCUMENT_STANDARD", "GRANITE_CUDA")),
        )

    with pytest.raises(
        GraniteCapacityConfigurationError,
        match="GRANITE_CAPACITY_CONFIGURATION_INVALID",
    ):
        GraniteWorker(
            worker_instance_id="worker-documents-1",
            environment_identity=identity,
            storage_environment="test",
            state=GraniteWorkerState.READY,
            capabilities=frozenset(("GRANITE_CUDA",)),
        )


def _duree_invalide_et_perte_de_double_fencing_sont_explicites() -> None:
    from app.platform.job_runtime.granite_capacity import (
        GraniteCapacityConfigurationError,
        GraniteCapacityController,
        GraniteSlotLeaseLostError,
    )

    class Repository:
        def claim_compatible_job(self, **_kwargs):
            return None

        def heartbeat(self, *_args, **_kwargs):
            raise AssertionError("heartbeat inattendu")

        def complete_page_execution(self, *_args, **_kwargs):
            raise AssertionError("terminal inattendu")

    controller = GraniteCapacityController(repository=Repository())
    with pytest.raises(
        GraniteCapacityConfigurationError,
        match="GRANITE_CAPACITY_CONFIGURATION_INVALID",
    ):
        controller.execute_next(
            worker=object(),
            lease_seconds=0,
            heartbeat_seconds=1,
            job_names=("CONVERT_PAGE",),
            execution_requirements=_claimed_job().job.request.execution_requirements,
            start_model=lambda _lease: None,
            success_envelope=lambda _lease, _result: None,
            failure_envelope=lambda _lease, _error: None,
        )

    conflict = GraniteSlotLeaseLostError()
    assert conflict.code == "JOB_LEASE_LOST"
    assert str(conflict) == "JOB_LEASE_LOST"


def test_quota_granite_fenced_unit() -> None:
    _identite_slot_exige_ordinal_generation_uuid4_et_echeance_commune()
    _worker_generaliste_refuse_stockage_etranger_et_capacite_partielle()
    _duree_invalide_et_perte_de_double_fencing_sont_explicites()
