from __future__ import annotations

from pathlib import Path


def test_worker_environment_identity_acceptance() -> None:
    from app.contracts.technical_jobs import (
        JobEnvironmentIdentity,
        JobIdempotenceKey,
        JobPriority,
        JobRequest,
    )
    from app.platform.job_runtime.relay import (
        ClaimedRelayMessage,
        JobOutboxRelay,
        RelayedJobMessage,
    )
    from app.platform.worker_environment import (
        WORKER_ENVIRONMENT_MISMATCH,
        WORKER_JOB_NAMES,
        WorkerEnvironmentBinding,
        WorkerEnvironmentMismatchError,
        execute_environment_bound_job,
    )

    development = JobEnvironmentIdentity(
        environment="development",
        deployment_id="ostrading-development-local",
        configuration_hash="d" * 64,
    )
    test_identity = JobEnvironmentIdentity(
        environment="test",
        deployment_id="ostrading-test-ci",
        configuration_hash="d" * 64,
    )

    # Given une API test a persisté un job et un message d'outbox avec son identité.
    request = JobRequest(
        environment=test_identity.environment,
        deployment_id=test_identity.deployment_id,
        job_name="DIAGNOSE",
        priority=JobPriority.P1,
        idempotence_key=JobIdempotenceKey(
            job_name="DIAGNOSE",
            input_hash="a" * 64,
            configuration_hash=test_identity.configuration_hash,
            code_version="worker-environment-acceptance",
            model_version="none",
        ),
        execution_requirements=None,
        payload={
            "document_id": "DOC-M013-ENV-WORKER-ACCEPTANCE",
            "processing_run_id": "RUN-M013-ENV-WORKER-ACCEPTANCE",
        },
    )
    message = RelayedJobMessage.from_job_request(
        message_id="OUTBOX-SP-M013-ENV-WORKER",
        request=request,
        trace_id="TRACE-M013-ENV-WORKER",
    )
    assert message.environment == "test"
    assert message.deployment_id == "ostrading-test-ci"
    assert message.as_job_request() == request

    # When un worker development évalue le travail avant le callback métier.
    binding = WorkerEnvironmentBinding(
        worker_id="worker-documents",
        identity=development,
        job_names=WORKER_JOB_NAMES["worker-documents"],
    )
    callback_calls: list[str] = []
    public_progress: list[dict[str, object]] = []
    outcome = execute_environment_bound_job(
        binding=binding,
        job_request=request,
        execute=lambda job: (
            callback_calls.append(job.job_name) or {"status": "executed"}
        ),
        persist_terminal_failure=lambda job, error_code: public_progress.append(
            {
                "environment": job.environment,
                "deployment_id": job.deployment_id,
                "phase": "FAILED",
                "completed_units": 0,
                "total_units": 1,
                "failure_error_code": error_code,
            }
        ),
    )

    # Then aucun effet métier n'a lieu et la progression productrice est terminale et stable.
    assert outcome.executed is False
    assert outcome.error_code == WORKER_ENVIRONMENT_MISMATCH
    assert callback_calls == []
    assert public_progress == [
        {
            "environment": "test",
            "deployment_id": "ostrading-test-ci",
            "phase": "FAILED",
            "completed_units": 0,
            "total_units": 1,
            "failure_error_code": WORKER_ENVIRONMENT_MISMATCH,
        }
    ]

    # Le relais refuse le message sans ACK et confie la transition terminale
    # à l'outbox productrice, avant toute insertion dans la file technique.
    claim = ClaimedRelayMessage(
        message=message,
        owner_id="development:ostrading-development-local:worker-documents:relay",
        claim_generation=1,
        claim_token="00000000-0000-4000-8000-000000000002",
    )

    class ForeignOutbox:
        def __init__(self) -> None:
            self.claimed = False
            self.rejected: list[ClaimedRelayMessage] = []

        def claim_next(self, *, owner_id: str, lease_seconds: int):
            assert owner_id == claim.owner_id
            assert lease_seconds == 30
            if self.claimed:
                return None
            self.claimed = True
            return claim

        def acknowledge(self, claimed, *, platform_job_id: str) -> None:
            raise AssertionError("Un message étranger ne doit jamais être ACK.")

        def reject_environment_mismatch(self, claimed) -> None:
            self.rejected.append(claimed)

    class BoundConsumer:
        def consume_relay_message(self, relayed_message):
            assert relayed_message == message
            raise WorkerEnvironmentMismatchError()

    foreign_outbox = ForeignOutbox()
    relayed_count = JobOutboxRelay(
        outbox=foreign_outbox,
        consumer=BoundConsumer(),
    ).relay_pending(limit=1, owner_id=claim.owner_id, lease_seconds=30)
    assert relayed_count == 0
    assert foreign_outbox.rejected == [claim]

    repository_root = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "pyproject.toml").is_file()
    )
    migration = (
        repository_root / "deploy/postgres/migrations/020_job_environment_identity.sql"
    )
    migration_text = migration.read_text(encoding="utf-8")
    for table in (
        "platform.technical_jobs",
        "source_processing.job_outbox",
        "knowledge_access.job_outbox",
    ):
        assert table in migration_text
    for column in ("environment", "deployment_id", "failure_error_code"):
        assert column in migration_text
    assert "WORKER_ENVIRONMENT_MISMATCH" in migration_text

    compose = (repository_root / "deploy/environments/compose.base.yaml").read_text(
        encoding="utf-8"
    )
    for worker_id in WORKER_JOB_NAMES:
        assert (
            "python -m app.platform.environment_compose check-worker "
            f"--worker-id {worker_id} --config /workspace/config/application.yaml"
        ) in compose
