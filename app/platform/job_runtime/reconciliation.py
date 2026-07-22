"""Réconciliation bornée des jobs actifs portant une ancienne configuration."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from app.contracts.technical_jobs import ClaimedJob, JobRequest
from app.platform.worker_environment import WORKER_ENVIRONMENT_MISMATCH


class EnvironmentMismatchJobQueue(Protocol):
    def claim_next_environment_mismatch(
        self,
        *,
        owner_id: str,
        lease_seconds: int,
        job_names: tuple[str, ...],
    ) -> ClaimedJob | None: ...

    def has_environment_mismatch(self, *, job_names: tuple[str, ...]) -> bool: ...

    def mark_failed(
        self,
        *,
        job_id: str,
        owner_id: str,
        claim_generation: int,
        claim_token: str,
        failure_reason: str,
    ) -> object: ...


def reconcile_stale_configuration_jobs(
    *,
    job_queue: EnvironmentMismatchJobQueue,
    job_names: tuple[str, ...],
    owner_id: str,
    lease_seconds: int,
    maximum_jobs: int,
    persist_public_failure: Callable[[JobRequest], None],
) -> int:
    """Terminalise au démarrage un lot fini de jobs du même environnement."""

    if not callable(getattr(job_queue, "claim_next_environment_mismatch", None)):
        raise ValueError("file sans claim de réconciliation")
    if not callable(getattr(job_queue, "mark_failed", None)):
        raise ValueError("file sans terminalisation de réconciliation")
    if not isinstance(job_names, tuple) or not job_names:
        raise ValueError("jobs de réconciliation invalides")
    if any(not isinstance(name, str) or not name or name != name.strip() for name in job_names):
        raise ValueError("jobs de réconciliation invalides")
    if not isinstance(owner_id, str) or not owner_id or owner_id != owner_id.strip():
        raise ValueError("owner de réconciliation invalide")
    if isinstance(lease_seconds, bool) or not isinstance(lease_seconds, int) or lease_seconds < 1:
        raise ValueError("lease de réconciliation invalide")
    if isinstance(maximum_jobs, bool) or not isinstance(maximum_jobs, int) or maximum_jobs < 1:
        raise ValueError("borne de réconciliation invalide")
    if not callable(persist_public_failure):
        raise ValueError("publication de réconciliation invalide")

    reconciled = 0
    while reconciled < maximum_jobs:
        claimed = job_queue.claim_next_environment_mismatch(
            owner_id=owner_id,
            lease_seconds=lease_seconds,
            job_names=job_names,
        )
        if claimed is None:
            return reconciled
        persist_public_failure(claimed.job.request)
        job_queue.mark_failed(
            job_id=claimed.job.job_id,
            owner_id=claimed.lease_owner,
            claim_generation=claimed.claim_generation,
            claim_token=claimed.claim_token,
            failure_reason=WORKER_ENVIRONMENT_MISMATCH,
        )
        reconciled += 1

    has_remaining = getattr(job_queue, "has_environment_mismatch", None)
    if not callable(has_remaining):
        raise ValueError("file sans inventaire de réconciliation")
    if has_remaining(job_names=job_names):
        raise RuntimeError("WORKER_ENVIRONMENT_RECONCILIATION_LIMIT_EXCEEDED")
    return reconciled


__all__ = ["EnvironmentMismatchJobQueue", "reconcile_stale_configuration_jobs"]
