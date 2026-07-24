"""Acceptation T-004 du quota Granite durable et fenced."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

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


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
CONFIGURATION_HASH = "a" * 64


def _claimed_job(*, owner: str = "worker-documents-1") -> ClaimedJob:
    identity = JobEnvironmentIdentity(
        environment="test",
        deployment_id="ostrading-test-local",
        configuration_hash=CONFIGURATION_HASH,
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
        ),
        payload={"required_capacity": "GRANITE_CUDA"},
    )
    return ClaimedJob(
        job=JobRecord(
            sequence=1,
            job_id="JOB-M002-000001",
            request=request,
            status=JobStatus.RUNNING,
            result=None,
            failure_reason=None,
        ),
        trace_id="TRACE-M014-QUOTA",
        lease_owner=owner,
        lease_expires_at=datetime.now(timezone.utc) + timedelta(seconds=30),
        claim_generation=1,
        claim_token=str(uuid4()),
        execution_attempts=1,
    )


def _slot_lease():
    from app.platform.job_runtime.granite_capacity import GraniteSlotLease

    claimed = _claimed_job()
    return GraniteSlotLease(
        claimed_job=claimed,
        slot_ordinal=1,
        slot_generation=1,
        slot_token=str(uuid4()),
        lease_until=claimed.lease_expires_at,
    )


class _CapacityRepository:
    def __init__(self, lease):
        self.lease = lease
        self.claims = 0
        self.heartbeats = 0
        self.terminals = []

    def claim_compatible_job(
        self,
        *,
        worker,
        lease_seconds,
        job_names,
        execution_requirements,
    ):
        self.claims += 1
        return self.lease

    def heartbeat(self, lease, *, lease_seconds):
        self.heartbeats += 1
        return lease

    def complete_page_execution(self, lease, envelope):
        self.terminals.append((lease, envelope))
        return lease.claimed_job.job


class _ModelProcess:
    def __init__(self, outcome):
        self._outcome = outcome

    def wait(self, *, timeout_seconds):
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome

    def terminate(self):
        raise AssertionError("annulation inattendue")


def _terminal(lease, status, payload):
    from app.platform.job_runtime.granite_capacity import (
        GranitePageTerminalEnvelope,
        GranitePageTerminalStatus,
    )

    return GranitePageTerminalEnvelope.from_payload(
        completion_id=f"COMPLETE-{lease.claimed_job.job.job_id}-{status.value}",
        status=status,
        payload=payload,
        failure_reason=(
            None if status is GranitePageTerminalStatus.SUCCEEDED else "MODEL_FAILED"
        ),
    )


def _ready_worker():
    from app.platform.job_runtime.granite_capacity import (
        GraniteWorker,
        GraniteWorkerState,
    )

    return GraniteWorker(
        worker_instance_id="worker-documents-1",
        environment_identity=JobEnvironmentIdentity(
            environment="test",
            deployment_id="ostrading-test-local",
            configuration_hash=CONFIGURATION_HASH,
        ),
        storage_environment="test",
        state=GraniteWorkerState.READY,
        capabilities=frozenset(("DOCUMENT_STANDARD", "GRANITE_CUDA")),
    )


def _troisieme_claim_attend_sans_appel_modele() -> None:
    """Given aucun slot, When un claim tente Granite, Then le modèle n'est pas appelé."""

    from app.platform.job_runtime.granite_capacity import GraniteCapacityController

    repository = _CapacityRepository(lease=None)
    controller = GraniteCapacityController(repository=repository)
    model_calls = []

    execution = controller.execute_next(
        worker=_ready_worker(),
        lease_seconds=30,
        heartbeat_seconds=5,
        job_names=("CONVERT_PAGE",),
        execution_requirements=_claimed_job().job.request.execution_requirements,
        start_model=lambda lease: model_calls.append(lease),
        success_envelope=lambda lease, result: _terminal(lease, result, {}),
        failure_envelope=lambda lease, error: _terminal(lease, error, {}),
    )

    assert execution is None
    assert repository.claims == 1
    assert model_calls == []
    assert repository.terminals == []


def _controleur_unique_libere_sous_la_meme_identite_fenced() -> None:
    """Given un slot acquis, When Granite finit, Then le contrôleur libère ce slot."""

    from app.platform.job_runtime.granite_capacity import GraniteCapacityController

    lease = _slot_lease()
    repository = _CapacityRepository(lease=lease)
    controller = GraniteCapacityController(repository=repository)

    from app.platform.job_runtime.granite_capacity import GranitePageTerminalStatus

    execution = controller.execute_next(
        worker=_ready_worker(),
        lease_seconds=30,
        heartbeat_seconds=5,
        job_names=("CONVERT_PAGE",),
        execution_requirements=lease.claimed_job.job.request.execution_requirements,
        start_model=lambda acquired: _ModelProcess({"slot": acquired.slot_ordinal}),
        success_envelope=lambda acquired, result: _terminal(
            acquired,
            GranitePageTerminalStatus.SUCCEEDED,
            result,
        ),
        failure_envelope=lambda acquired, _error: _terminal(
            acquired,
            GranitePageTerminalStatus.FAILED,
            {"error_code": "MODEL_FAILED"},
        ),
    )

    assert execution is not None
    assert execution.lease == lease
    assert execution.model_result == {"slot": 1}
    assert repository.terminals[0][0] == lease


def _echec_explicite_libere_sans_fallback() -> None:
    """Given Granite échoue, When l'erreur remonte, Then le slot est libéré et l'erreur propagée."""

    from app.platform.job_runtime.granite_capacity import GraniteCapacityController

    lease = _slot_lease()
    repository = _CapacityRepository(lease=lease)
    controller = GraniteCapacityController(repository=repository)

    from app.platform.job_runtime.granite_capacity import GranitePageTerminalStatus

    with pytest.raises(RuntimeError, match="GRANITE_CUDA_UNAVAILABLE"):
        controller.execute_next(
            worker=_ready_worker(),
            lease_seconds=30,
            heartbeat_seconds=5,
            job_names=("CONVERT_PAGE",),
            execution_requirements=lease.claimed_job.job.request.execution_requirements,
            start_model=lambda _lease: _ModelProcess(
                RuntimeError("GRANITE_CUDA_UNAVAILABLE")
            ),
            success_envelope=lambda acquired, result: _terminal(
                acquired,
                GranitePageTerminalStatus.SUCCEEDED,
                result,
            ),
            failure_envelope=lambda acquired, _error: _terminal(
                acquired,
                GranitePageTerminalStatus.FAILED,
                {"error_code": "GRANITE_CUDA_UNAVAILABLE"},
            ),
        )

    assert repository.terminals[0][0] == lease


def _migration_022_est_ascendante_et_prepare_les_deux_proprietaires() -> None:
    """Given le ledger finit en 021, When T-004 arrive, Then seule 022 est ajoutée."""

    migration = (
        REPOSITORY_ROOT
        / "deploy"
        / "postgres"
        / "migrations"
        / "022_granite_quota_and_page_results.sql"
    )
    sql = migration.read_text(encoding="utf-8")
    normalized = " ".join(sql.split()).lower()

    assert "create table platform.granite_slots" in normalized
    assert "slot_ordinal in (1, 2)" in normalized
    assert "for update skip locked" not in normalized
    assert "create table source_processing.page_execution_results" in normalized
    assert "create table platform.page_completion_outbox" in normalized
    assert "drop table" not in normalized
    assert "drop column" not in normalized
    assert "insert into platform.granite_slots" in normalized
    assert (
        "on conflict (environment, deployment_id, slot_ordinal) do nothing"
        in normalized
    )

    versions = tuple(
        int(path.name[:3]) for path in sorted((migration.parent).glob("*.sql"))
    )
    assert versions == tuple(range(1, 23))


def _adaptateur_documente_ordre_de_verrouillage_et_skip_locked() -> None:
    """L'acquisition verrouille worker, job puis slot, sans attente de verrou."""

    source = (
        REPOSITORY_ROOT / "app" / "platform" / "job_runtime" / "granite_capacity.py"
    ).read_text(encoding="utf-8")

    assert "LOCK_ORDER: document_worker -> technical_job -> granite_slot" in source
    assert source.count("SKIP LOCKED") >= 2
    assert "BoundedSemaphore" not in source
    assert "threading.Semaphore" not in source


def test_quota_granite_fenced_acceptance() -> None:
    _troisieme_claim_attend_sans_appel_modele()
    _controleur_unique_libere_sous_la_meme_identite_fenced()
    _echec_explicite_libere_sans_fallback()
    _migration_022_est_ascendante_et_prepare_les_deux_proprietaires()
    _adaptateur_documente_ordre_de_verrouillage_et_skip_locked()
