"""Renouvellement clôturé des leases de jobs pendant les calculs longs."""

from __future__ import annotations

from collections.abc import Callable
import threading
from typing import Any

from app.platform.job_runtime.postgres import JobLeaseConflictError


class JobLeaseHeartbeat:
    """Renouvelle une lease et sérialise sa transition terminale."""

    def __init__(
        self,
        *,
        job_queue: Any,
        job_id: str,
        owner_id: str,
        claim_generation: int,
        claim_token: str,
        lease_seconds: int,
        heartbeat_seconds: float,
    ) -> None:
        if not callable(getattr(job_queue, "renew_lease", None)):
            raise ValueError("job_queue sans renouvellement")
        if not isinstance(job_id, str) or job_id.strip() == "":
            raise ValueError("job_id heartbeat invalide")
        if not isinstance(owner_id, str) or owner_id.strip() == "":
            raise ValueError("owner_id heartbeat invalide")
        if isinstance(lease_seconds, bool) or not isinstance(lease_seconds, int) or lease_seconds < 1:
            raise ValueError("lease_seconds heartbeat invalide")
        if (
            isinstance(heartbeat_seconds, bool)
            or not isinstance(heartbeat_seconds, (int, float))
            or heartbeat_seconds <= 0
            or heartbeat_seconds >= lease_seconds
        ):
            raise ValueError("heartbeat_seconds invalide")
        if (
            isinstance(claim_generation, bool)
            or not isinstance(claim_generation, int)
            or claim_generation < 1
        ):
            raise ValueError("claim_generation heartbeat invalide")
        if not isinstance(claim_token, str) or claim_token.strip() == "":
            raise ValueError("claim_token heartbeat invalide")
        self._job_queue = job_queue
        self._job_id = job_id
        self._owner_id = owner_id
        self._claim_generation = claim_generation
        self._claim_token = claim_token
        self._lease_seconds = lease_seconds
        self._heartbeat_seconds = float(heartbeat_seconds)
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._failure: Exception | None = None
        self._finalized = False
        self._paused = False
        self._thread = threading.Thread(
            target=self._run,
            name=f"lease-heartbeat-{job_id}",
            daemon=True,
        )

    def start(self) -> None:
        self._thread.start()

    def assert_owned(self) -> None:
        with self._lock:
            self._raise_failure()

    def pause(self) -> None:
        """Suspend le renouvellement simple avant la prise du slot Granite."""

        with self._lock:
            self._raise_failure()
            if self._finalized or self._paused:
                raise RuntimeError("JOB_LEASE_HEARTBEAT_PAUSE_INVALID")
            self._paused = True

    def resume(self) -> None:
        """Rend l'autorité au heartbeat simple après libération du slot."""

        with self._lock:
            self._raise_failure()
            if self._finalized or not self._paused:
                raise RuntimeError("JOB_LEASE_HEARTBEAT_RESUME_INVALID")
            self._paused = False

    def finalize(self, transition: Callable[[], Any]) -> Any:
        if not callable(transition):
            raise ValueError("transition finale invalide")
        with self._lock:
            self._raise_failure()
            result = transition()
            self._finalized = True
            self._stop.set()
            return result

    def stop(self) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=max(1.0, self._heartbeat_seconds * 2))
        if self._thread.is_alive():
            raise RuntimeError("JOB_LEASE_HEARTBEAT_STOP_TIMEOUT")

    def _run(self) -> None:
        while not self._stop.wait(self._heartbeat_seconds):
            with self._lock:
                if self._finalized:
                    return
                if self._paused:
                    continue
                try:
                    self._job_queue.renew_lease(
                        job_id=self._job_id,
                        owner_id=self._owner_id,
                        claim_generation=self._claim_generation,
                        claim_token=self._claim_token,
                        lease_seconds=self._lease_seconds,
                    )
                except Exception as exc:
                    self._failure = exc
                    self._stop.set()
                    return

    def _raise_failure(self) -> None:
        if self._failure is None:
            return
        if isinstance(self._failure, JobLeaseConflictError):
            raise self._failure
        raise RuntimeError("JOB_LEASE_RENEWAL_FAILED") from self._failure


class JobHeartbeatCoordinator:
    """Relie le worker construit une fois au heartbeat du job courant."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._heartbeat: JobLeaseHeartbeat | None = None

    def bind(self, heartbeat: JobLeaseHeartbeat) -> None:
        if not isinstance(heartbeat, JobLeaseHeartbeat):
            raise ValueError("heartbeat à lier invalide")
        with self._lock:
            if self._heartbeat is not None:
                raise RuntimeError("JOB_HEARTBEAT_ALREADY_BOUND")
            self._heartbeat = heartbeat

    def unbind(self, heartbeat: JobLeaseHeartbeat) -> None:
        with self._lock:
            if self._heartbeat is not heartbeat:
                raise RuntimeError("JOB_HEARTBEAT_BINDING_MISMATCH")
            self._heartbeat = None

    def pause(self) -> None:
        self._bound().pause()

    def resume(self) -> None:
        self._bound().resume()

    def _bound(self) -> JobLeaseHeartbeat:
        with self._lock:
            heartbeat = self._heartbeat
        if heartbeat is None:
            raise RuntimeError("JOB_HEARTBEAT_NOT_BOUND")
        return heartbeat


__all__ = ["JobHeartbeatCoordinator", "JobLeaseHeartbeat"]
