"""Persistance PostgreSQL SP atomique d'un résultat et de sa progression."""

from __future__ import annotations

import json
from typing import Any

from app.platform.postgres import PostgresConnectionFactory
from app.source_processing.adapters.postgres_canonical_assembly import (
    enqueue_canonical_assembly_if_complete,
)
from app.source_processing.domain.distribution_contracts import (
    DistributionContractError,
    PageResultContract,
    PageResultStatus,
)


class PostgresPageResultRepository:
    """Consommateur SP local : aucune table platform n'est lue ou écrite."""

    def __init__(self, *, connection_factory: PostgresConnectionFactory) -> None:
        if not callable(getattr(connection_factory, "connect", None)):
            raise ValueError("connection_factory invalide")
        self._connection_factory = connection_factory

    def persist_page_result(
        self,
        *,
        completion_id: str,
        payload_fingerprint: str,
        result: PageResultContract,
    ) -> bool:
        if not isinstance(result, PageResultContract):
            raise ValueError("PAGE_RESULT_INVALID")
        if result.status is PageResultStatus.SKIP_EMPTY or result.execution is None:
            raise DistributionContractError("PAGE_EXECUTION_IDENTITY_REQUIRED")
        completion = _text(completion_id, "PAGE_COMPLETION_ID_INVALID")
        fingerprint = _sha256(
            payload_fingerprint,
            "PAGE_RESULT_FINGERPRINT_INVALID",
        )
        result_json = result.to_json()
        execution = result.execution
        slot = result.granite_slot_execution
        with self._connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (completion,),
                )
                cursor.execute(
                    """
                    SELECT completion_id, result_fingerprint, result_payload
                      FROM source_processing.page_execution_results
                     WHERE processing_run_id = %s AND page_number = %s
                     FOR UPDATE
                    """,
                    (result.processing_run_id, result.page_number),
                )
                replay = cursor.fetchone()
                if replay is not None:
                    if (
                        replay[0] != completion
                        or replay[1] != fingerprint
                        or _canonical_json(replay[2]) != result_json
                    ):
                        raise DistributionContractError(
                            "PAGE_RESULT_REPLAY_DIVERGENCE"
                        )
                    return False
                cursor.execute(
                    """
                    SELECT fanout.environment, fanout.deployment_id,
                           fanout.configuration_hash, fanout.total_units,
                           request.completed_units, request.execution_phase,
                           request.conversion_status, route.route_name
                      FROM source_processing.document_page_fanouts AS fanout
                      JOIN source_processing.document_conversion_requests AS request
                        ON request.document_id = fanout.document_id
                      JOIN source_processing.page_manifest_entries AS manifest
                        ON manifest.processing_run_id = fanout.processing_run_id
                       AND manifest.page_number = %s
                      JOIN source_processing.page_routes AS route
                        ON route.processing_run_id = manifest.processing_run_id
                       AND route.page_number = manifest.page_number
                     WHERE fanout.processing_run_id = %s
                     FOR UPDATE OF fanout, request, manifest, route
                    """,
                    (result.page_number, result.processing_run_id),
                )
                owner = cursor.fetchone()
                if owner is None:
                    raise DistributionContractError("PAGE_MANIFEST_INCOMPLETE")
                identity = result.environment_identity
                if owner[:3] != (
                    identity.environment,
                    identity.deployment_id,
                    identity.configuration_hash,
                ):
                    raise DistributionContractError("CONTRACT_ENVIRONMENT_MISMATCH")
                total_units = owner[3]
                completed_units = owner[4]
                if (
                    owner[5] != "RUNNING"
                    or owner[6] != "CONVERSION_REQUESTED"
                    or owner[7] != result.route_name.value
                ):
                    raise DistributionContractError("PAGE_RESULT_STATE_INVALID")
                if completed_units >= total_units:
                    raise DistributionContractError("PAGE_PROGRESS_TOTAL_EXCEEDED")
                cursor.execute(
                    """
                    INSERT INTO source_processing.page_execution_results (
                        processing_run_id, page_number, completion_id, job_id,
                        claim_generation, claim_token, worker_instance_id,
                        slot_ordinal, slot_generation, slot_token,
                        result_contract_version, route_name, result_status,
                        result_payload, result_fingerprint
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s::uuid, %s,
                        %s, %s, %s::uuid, %s, %s, %s, %s::jsonb, %s
                    )
                    """,
                    (
                        result.processing_run_id,
                        result.page_number,
                        completion,
                        execution.job_id,
                        execution.claim_generation,
                        execution.claim_token,
                        execution.worker_instance_id,
                        None if slot is None else slot.slot_ordinal,
                        None if slot is None else slot.slot_generation,
                        None if slot is None else slot.slot_token,
                        result.contract_version,
                        result.route_name.value,
                        result.status.value,
                        result_json,
                        fingerprint,
                    ),
                )
                if result.status is PageResultStatus.FAILED:
                    error_code = result.error_code.value
                    cursor.execute(
                        """
                        UPDATE source_processing.document_conversion_requests AS request
                           SET conversion_status = 'QA_REJECTED',
                               rejection_error_code = %s,
                               execution_phase = 'FAILED',
                               completed_units = completed_units + 1,
                               failure_error_code = %s
                          FROM source_processing.document_page_fanouts AS fanout
                         WHERE fanout.processing_run_id = %s
                           AND request.document_id = fanout.document_id
                           AND request.conversion_status = 'CONVERSION_REQUESTED'
                           AND request.execution_phase = 'RUNNING'
                           AND request.completed_units < request.total_units
                        RETURNING request.completed_units
                        """,
                        (error_code, error_code, result.processing_run_id),
                    )
                else:
                    cursor.execute(
                        """
                        UPDATE source_processing.document_conversion_requests AS request
                           SET completed_units = completed_units + 1
                          FROM source_processing.document_page_fanouts AS fanout
                         WHERE fanout.processing_run_id = %s
                           AND request.document_id = fanout.document_id
                           AND request.conversion_status = 'CONVERSION_REQUESTED'
                           AND request.execution_phase = 'RUNNING'
                           AND request.completed_units < request.total_units
                        RETURNING request.completed_units
                        """,
                        (result.processing_run_id,),
                    )
                progress = cursor.fetchone()
                if progress is None or progress[0] != completed_units + 1:
                    raise DistributionContractError("PAGE_PROGRESS_PERSISTENCE_FAILED")
                enqueue_canonical_assembly_if_complete(
                    cursor=cursor,
                    processing_run_id=result.processing_run_id,
                )
        return True


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _sha256(value: Any, code: str) -> str:
    text = _text(value, code)
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise ValueError(code)
    return text


def _text(value: Any, code: str) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise ValueError(code)
    return value


__all__ = ["PostgresPageResultRepository"]
