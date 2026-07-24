"""Consommation SP idempotente d'une enveloppe de résultat de page."""

from __future__ import annotations

from typing import Protocol

from app.contracts.page_execution import PageCompletionMessage
from app.source_processing.domain.distribution_contracts import (
    DistributionContractError,
    PageResultContract,
    PageResultStatus,
)


class PageResultRepository(Protocol):
    def persist_page_result(
        self,
        *,
        completion_id: str,
        payload_fingerprint: str,
        result: PageResultContract,
    ) -> bool: ...


class RecordPageCompletionHandler:
    """Valide toute la preuve fenced avant la transaction propriétaire SP."""

    def __init__(self, *, repository: PageResultRepository) -> None:
        if not callable(getattr(repository, "persist_page_result", None)):
            raise ValueError("PAGE_RESULT_REPOSITORY_INCOMPLETE")
        self._repository = repository

    def record_page_completion(self, message: PageCompletionMessage) -> bool:
        if not isinstance(message, PageCompletionMessage):
            raise ValueError("PAGE_COMPLETION_MESSAGE_INVALID")
        result = PageResultContract.from_mapping(message.payload)
        execution = result.execution
        if execution is None:
            raise DistributionContractError("PAGE_EXECUTION_IDENTITY_REQUIRED")
        if (
            result.environment_identity.environment != message.environment
            or result.environment_identity.deployment_id != message.deployment_id
        ):
            raise DistributionContractError("CONTRACT_ENVIRONMENT_MISMATCH")
        if (
            execution.job_id != message.job_id
            or execution.claim_generation != message.claim_generation
            or execution.claim_token != message.claim_token
            or execution.worker_instance_id != message.worker_instance_id
        ):
            raise DistributionContractError("PAGE_RESULT_REPLAY_DIVERGENCE")
        slot = result.granite_slot_execution
        actual_slot = (
            message.slot_ordinal,
            message.slot_generation,
            message.slot_token,
        )
        expected_slot = (
            (None, None, None)
            if slot is None
            else (slot.slot_ordinal, slot.slot_generation, slot.slot_token)
        )
        if actual_slot != expected_slot:
            raise DistributionContractError("PAGE_RESULT_REPLAY_DIVERGENCE")
        expected_status = (
            "succeeded"
            if result.status is PageResultStatus.SUCCEEDED
            else "failed"
        )
        if message.terminal_status != expected_status:
            raise DistributionContractError("PAGE_RESULT_REPLAY_DIVERGENCE")
        if (
            result.status is PageResultStatus.FAILED
            and message.failure_reason != result.error_code.value
        ):
            raise DistributionContractError("PAGE_RESULT_REPLAY_DIVERGENCE")
        return self._repository.persist_page_result(
            completion_id=message.completion_id,
            payload_fingerprint=message.payload_fingerprint,
            result=result,
        )


class InMemoryPageResultRepository:
    """Double atomique minimal réservé aux preuves de protocole T-006."""

    def __init__(self, *, total_units: int, completed_units: int) -> None:
        if (
            isinstance(total_units, bool)
            or not isinstance(total_units, int)
            or total_units < 1
            or isinstance(completed_units, bool)
            or not isinstance(completed_units, int)
            or not 0 <= completed_units <= total_units
        ):
            raise ValueError("PAGE_PROGRESS_INVALID")
        self.total_units = total_units
        self.completed_units = completed_units
        self._results: dict[tuple[str, int], tuple[str, str, str]] = {}

    @property
    def result_count(self) -> int:
        return len(self._results)

    def persist_page_result(
        self,
        *,
        completion_id: str,
        payload_fingerprint: str,
        result: PageResultContract,
    ) -> bool:
        identity = (result.processing_run_id, result.page_number)
        replay = (completion_id, payload_fingerprint, result.to_json())
        existing = self._results.get(identity)
        if existing is not None:
            if existing != replay:
                raise RuntimeError("PAGE_RESULT_REPLAY_DIVERGENCE")
            return False
        if self.completed_units >= self.total_units:
            raise RuntimeError("PAGE_PROGRESS_TOTAL_EXCEEDED")
        self._results[identity] = replay
        self.completed_units += 1
        return True


__all__ = [
    "InMemoryPageResultRepository",
    "PageResultRepository",
    "RecordPageCompletionHandler",
]
