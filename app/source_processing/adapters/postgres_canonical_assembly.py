"""Persistance SP de l'assemblage et de la publication canonique M-014."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from app.contracts.technical_jobs import JobPriority
from app.platform.postgres import PostgresConnectionFactory
from app.source_processing.application.assemble_canonical_document import (
    CanonicalAssemblyPublication,
    CanonicalAssemblySnapshot,
)
from app.source_processing.domain.distribution_contracts import (
    ASSEMBLE_CANONICAL_DOCUMENT_CONTRACT_VERSION,
    PAGE_RESULT_CONTRACT_VERSION,
    AssembleCanonicalDocumentContract,
    DistributionContractError,
    LocalArtifactIdentity,
    PageResultContract,
    assemble_canonical_document_idempotence_key,
)
from app.source_processing.domain.source_document import DocumentId


_ASSEMBLY_CODE_VERSION = "m014-canonical-assembly-v1"
_ASSEMBLY_MODEL_VERSION = "no-model"


def enqueue_canonical_assembly_if_complete(
    *, cursor: Any, processing_run_id: str
) -> bool:
    """Crée au plus une commande d'assemblage dans la transaction SP courante."""

    run_id = _text(processing_run_id, "PROCESSING_RUN_ID_INVALID")
    cursor.execute(
        """
        SELECT fanout.document_id, fanout.environment, fanout.deployment_id,
               fanout.configuration_hash, fanout.page_manifest_sha256,
               fanout.total_units, request.completed_units,
               request.execution_phase, request.conversion_status
          FROM source_processing.document_page_fanouts AS fanout
          JOIN source_processing.document_conversion_requests AS request
            ON request.document_id = fanout.document_id
         WHERE fanout.processing_run_id = %s
         FOR UPDATE OF fanout, request
        """,
        (run_id,),
    )
    row = cursor.fetchone()
    if row is None:
        raise DistributionContractError("PAGE_MANIFEST_INCOMPLETE")
    cursor.execute(
        """
        SELECT COUNT(*), COUNT(*) FILTER (WHERE result_status = 'FAILED')
          FROM source_processing.page_execution_results
         WHERE processing_run_id = %s
        """,
        (run_id,),
    )
    result_counts = cursor.fetchone()
    if result_counts is None:
        raise DistributionContractError("PAGE_MANIFEST_INCOMPLETE")
    total = row[5]
    if result_counts[1] > 0:
        return False
    if (row[6], row[7], row[8], result_counts[0]) != (
        total,
        "RUNNING",
        "CONVERSION_REQUESTED",
        total,
    ):
        return False
    assembly_key = assemble_canonical_document_idempotence_key(
        processing_run_id=run_id,
        page_manifest_sha256=row[4],
        page_result_contract_version=PAGE_RESULT_CONTRACT_VERSION,
        contract_version=ASSEMBLE_CANONICAL_DOCUMENT_CONTRACT_VERSION,
    )
    relative_path = f"canonical_candidates/{run_id}/docling.json"
    contract = AssembleCanonicalDocumentContract(
        contract_version=ASSEMBLE_CANONICAL_DOCUMENT_CONTRACT_VERSION,
        environment_identity=_job_environment_identity(
            environment=row[1],
            deployment_id=row[2],
            configuration_hash=row[3],
        ),
        document_id=row[0],
        processing_run_id=run_id,
        page_count=total,
        page_manifest_sha256=row[4],
        page_result_contract_version=PAGE_RESULT_CONTRACT_VERSION,
        expected_canonical_artifact=LocalArtifactIdentity(
            environment=row[1],
            artifact_ref=f"artifact:source_processing.local/{row[1]}/{relative_path}",
            relative_path=relative_path,
        ),
        idempotence_key=assembly_key,
    )
    request = contract.to_job_request(
        priority=JobPriority.P1,
        code_version=_ASSEMBLY_CODE_VERSION,
        model_version=_ASSEMBLY_MODEL_VERSION,
    )
    payload = request.payload
    cursor.execute(
        """
        INSERT INTO source_processing.job_outbox (
            environment, deployment_id, job_name, priority, input_hash,
            configuration_hash, code_version, model_version, payload,
            trace_id, status
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, 'pending')
        ON CONFLICT (
            job_name, input_hash, configuration_hash, code_version, model_version
        ) DO NOTHING
        RETURNING outbox_id
        """,
        (
            request.environment,
            request.deployment_id,
            request.job_name,
            request.priority.value,
            request.idempotence_key.input_hash,
            request.idempotence_key.configuration_hash,
            request.idempotence_key.code_version,
            request.idempotence_key.model_version,
            _canonical_json(payload),
            f"TRACE-M014-ASSEMBLY-{run_id}",
        ),
    )
    inserted = cursor.fetchone()
    if inserted is not None:
        return True
    cursor.execute(
        """
        SELECT payload
          FROM source_processing.job_outbox
         WHERE job_name = %s AND input_hash = %s
           AND configuration_hash = %s AND code_version = %s
           AND model_version = %s
         FOR UPDATE
        """,
        request.idempotence_key.identity_tuple(),
    )
    replay = cursor.fetchone()
    if replay is None or _canonical_json(replay[0]) != _canonical_json(payload):
        raise DistributionContractError("CANONICAL_ASSEMBLY_REPLAY_DIVERGENCE")
    return False


class PostgresCanonicalAssemblyRepository:
    """Relit les faits SP puis publie version, succès et événement atomiquement."""

    def __init__(self, *, connection_factory: PostgresConnectionFactory) -> None:
        if not callable(getattr(connection_factory, "connect", None)):
            raise ValueError("connection_factory invalide")
        self._connection_factory = connection_factory

    def load_snapshot(
        self, contract: AssembleCanonicalDocumentContract
    ) -> CanonicalAssemblySnapshot:
        if not isinstance(contract, AssembleCanonicalDocumentContract):
            raise ValueError("CANONICAL_ASSEMBLY_CONTRACT_INVALID")
        from app.source_processing.adapters.postgres_document_persistence import (
            PostgresDocumentPersistence,
        )

        persistence = PostgresDocumentPersistence(
            connection_factory=self._connection_factory
        )
        source = persistence.find_by_document_id(
            DocumentId.from_value(contract.document_id)
        )
        run = persistence.find_processing_run_by_document_id(
            DocumentId.from_value(contract.document_id)
        )
        if source is None or run is None or run.processing_run_id.value != contract.processing_run_id:
            raise DistributionContractError("PAGE_MANIFEST_INCOMPLETE")
        with self._connection_factory.connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT fanout.page_manifest_sha256, fanout.total_units,
                       fanout.environment, fanout.deployment_id,
                       fanout.configuration_hash, message.created_at
                  FROM source_processing.document_page_fanouts AS fanout
                  JOIN source_processing.job_outbox AS message
                    ON message.job_name = 'ASSEMBLE_CANONICAL_DOCUMENT'
                   AND message.input_hash = %s
                   AND message.configuration_hash = fanout.configuration_hash
                 WHERE fanout.processing_run_id = %s
                """,
                (contract.idempotence_key, contract.processing_run_id),
            )
            owner = cursor.fetchone()
            if owner is None:
                raise DistributionContractError("PAGE_MANIFEST_INCOMPLETE")
            if owner[:5] != (
                contract.page_manifest_sha256,
                contract.page_count,
                contract.environment_identity.environment,
                contract.environment_identity.deployment_id,
                contract.environment_identity.configuration_hash,
            ):
                raise DistributionContractError("CANONICAL_ASSEMBLY_REPLAY_DIVERGENCE")
            cursor.execute(
                """
                SELECT result_payload
                  FROM source_processing.page_execution_results
                 WHERE processing_run_id = %s
                 ORDER BY page_number
                """,
                (contract.processing_run_id,),
            )
            results = tuple(PageResultContract.from_mapping(row[0]) for row in cursor.fetchall())
        return CanonicalAssemblySnapshot(
            source_document=source,
            processing_run=run,
            page_results=results,
            accepted_at=_utc_text(owner[5]),
        )

    def publish_atomic(self, publication: CanonicalAssemblyPublication) -> bool:
        if not isinstance(publication, CanonicalAssemblyPublication):
            raise ValueError("CANONICAL_ASSEMBLY_PUBLICATION_INVALID")
        contract = publication.contract
        canonical = publication.canonical_ref
        event_json = publication.event.to_json()
        event_fingerprint = hashlib.sha256(event_json.encode("utf-8")).hexdigest()
        with self._connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (f"sp-canonical-assembly|{contract.idempotence_key}",),
                )
                cursor.execute(
                    """
                    SELECT request.completed_units, request.total_units,
                           request.execution_phase, request.conversion_status,
                           fanout.page_manifest_sha256
                      FROM source_processing.document_conversion_requests AS request
                      JOIN source_processing.document_page_fanouts AS fanout
                        ON fanout.document_id = request.document_id
                     WHERE fanout.processing_run_id = %s
                     FOR UPDATE OF request, fanout
                    """,
                    (contract.processing_run_id,),
                )
                owner = cursor.fetchone()
                cursor.execute(
                    """
                    SELECT COUNT(*),
                           COUNT(*) FILTER (WHERE result_status = 'FAILED')
                      FROM source_processing.page_execution_results
                     WHERE processing_run_id = %s
                    """,
                    (contract.processing_run_id,),
                )
                result_counts = cursor.fetchone()
                if owner is None or result_counts is None or (*owner, *result_counts) != (
                    contract.page_count,
                    contract.page_count,
                    "RUNNING",
                    "CONVERSION_REQUESTED",
                    contract.page_manifest_sha256,
                    contract.page_count,
                    0,
                ):
                    self._return_existing_or_raise(
                        cursor=cursor,
                        publication=publication,
                        event_json=event_json,
                        event_fingerprint=event_fingerprint,
                    )
                    return False
                cursor.execute(
                    """
                    INSERT INTO source_processing.canonical_source_versions (
                        canonical_version_id, canonical_source_id, document_id,
                        canonical_artifact_ref, canonical_artifact_sha256,
                        route_name, tool_version, accepted_at,
                        canonical_assembly_id, page_count,
                        quality_policy_version, canonical_result_fingerprint
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::timestamptz,
                            %s, %s, %s, %s)
                    ON CONFLICT (canonical_version_id) DO NOTHING
                    RETURNING canonical_version_id
                    """,
                    (
                        canonical.canonical_version_id,
                        canonical.canonical_source_id,
                        canonical.document_id,
                        publication.canonical_artifact_ref,
                        canonical.canonical_artifact_sha256,
                        publication.route_name.value,
                        publication.tool_version,
                        canonical.accepted_at,
                        contract.idempotence_key,
                        canonical.page_count,
                        canonical.quality_policy_version,
                        publication.result_fingerprint,
                    ),
                )
                if cursor.fetchone() is None:
                    raise DistributionContractError(
                        "CANONICAL_ASSEMBLY_REPLAY_DIVERGENCE"
                    )
                cursor.execute(
                    """
                    UPDATE source_processing.document_conversion_requests
                       SET conversion_status = 'CANONICAL_ACCEPTED',
                           canonical_version_id = %s,
                           canonical_artifact_ref = %s,
                           canonical_artifact_sha256 = %s,
                           route_name = %s, tool_version = %s,
                           accepted_at = %s::timestamptz,
                           execution_phase = 'SUCCEEDED',
                           completed_units = total_units,
                           rejection_error_code = NULL,
                           failure_error_code = NULL
                     WHERE document_id = %s
                       AND conversion_status = 'CONVERSION_REQUESTED'
                       AND execution_phase = 'RUNNING'
                       AND completed_units = total_units
                    """,
                    (
                        canonical.canonical_version_id,
                        publication.canonical_artifact_ref,
                        canonical.canonical_artifact_sha256,
                        publication.route_name.value,
                        publication.tool_version,
                        canonical.accepted_at,
                        canonical.document_id,
                    ),
                )
                if cursor.rowcount != 1:
                    raise DistributionContractError(
                        "CANONICAL_ASSEMBLY_REPLAY_DIVERGENCE"
                    )
                cursor.execute(
                    """
                    INSERT INTO source_processing.canonical_publication_outbox (
                        event_id, canonical_version_id, environment,
                        deployment_id, configuration_hash, event_payload,
                        event_fingerprint, status, relay_generation
                    )
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, 'pending', 0)
                    ON CONFLICT (event_id) DO NOTHING
                    RETURNING event_id
                    """,
                    (
                        publication.event.event_id,
                        canonical.canonical_version_id,
                        contract.environment_identity.environment,
                        contract.environment_identity.deployment_id,
                        contract.environment_identity.configuration_hash,
                        event_json,
                        event_fingerprint,
                    ),
                )
                if cursor.fetchone() is None:
                    raise DistributionContractError(
                        "CANONICAL_ASSEMBLY_REPLAY_DIVERGENCE"
                    )
        return True

    def _return_existing_or_raise(
        self,
        *,
        cursor: Any,
        publication: CanonicalAssemblyPublication,
        event_json: str,
        event_fingerprint: str,
    ) -> None:
        canonical = publication.canonical_ref
        cursor.execute(
            """
            SELECT version.canonical_source_id, version.document_id,
                   version.canonical_artifact_ref,
                   version.canonical_artifact_sha256, version.route_name,
                   version.tool_version, version.page_count,
                   version.quality_policy_version,
                   version.canonical_result_fingerprint,
                   outbox.event_id, outbox.event_payload,
                   outbox.event_fingerprint
              FROM source_processing.canonical_source_versions AS version
              JOIN source_processing.canonical_publication_outbox AS outbox
                ON outbox.canonical_version_id = version.canonical_version_id
             WHERE version.canonical_assembly_id = %s
             FOR UPDATE OF version, outbox
            """,
            (publication.contract.idempotence_key,),
        )
        existing = cursor.fetchone()
        expected = (
            canonical.canonical_source_id,
            canonical.document_id,
            publication.canonical_artifact_ref,
            canonical.canonical_artifact_sha256,
            publication.route_name.value,
            publication.tool_version,
            canonical.page_count,
            canonical.quality_policy_version,
            publication.result_fingerprint,
            publication.event.event_id,
            json.loads(event_json),
            event_fingerprint,
        )
        if existing is None or tuple(existing) != expected:
            raise DistributionContractError("CANONICAL_ASSEMBLY_REPLAY_DIVERGENCE")

    def mark_failed(
        self,
        contract: AssembleCanonicalDocumentContract,
        *,
        error_code: str,
    ) -> None:
        if not isinstance(contract, AssembleCanonicalDocumentContract):
            raise ValueError("CANONICAL_ASSEMBLY_CONTRACT_INVALID")
        code = _text(error_code, "CANONICAL_ASSEMBLY_ERROR_CODE_INVALID")
        with self._connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE source_processing.document_conversion_requests AS request
                       SET conversion_status = 'QA_REJECTED',
                           execution_phase = 'FAILED',
                           rejection_error_code = %s,
                           failure_error_code = %s,
                           canonical_version_id = NULL,
                           canonical_artifact_ref = NULL,
                           canonical_artifact_sha256 = NULL,
                           route_name = NULL, tool_version = NULL,
                           accepted_at = NULL
                      FROM source_processing.document_page_fanouts AS fanout
                     WHERE fanout.processing_run_id = %s
                       AND request.document_id = fanout.document_id
                       AND request.conversion_status = 'CONVERSION_REQUESTED'
                       AND request.execution_phase = 'RUNNING'
                    """,
                    (code, code, contract.processing_run_id),
                )
                if cursor.rowcount != 1:
                    cursor.execute(
                        """
                        SELECT request.conversion_status,
                               request.execution_phase,
                               request.rejection_error_code,
                               request.failure_error_code
                          FROM source_processing.document_conversion_requests AS request
                          JOIN source_processing.document_page_fanouts AS fanout
                            ON fanout.document_id = request.document_id
                         WHERE fanout.processing_run_id = %s
                         FOR UPDATE OF request
                        """,
                        (contract.processing_run_id,),
                    )
                    replay = cursor.fetchone()
                    if replay == ("QA_REJECTED", "FAILED", code, code):
                        return
                    raise DistributionContractError(
                        "CANONICAL_ASSEMBLY_REPLAY_DIVERGENCE"
                    )


def _job_environment_identity(
    *, environment: str, deployment_id: str, configuration_hash: str
):
    from app.contracts.technical_jobs import JobEnvironmentIdentity

    return JobEnvironmentIdentity(
        environment=environment,
        deployment_id=deployment_id,
        configuration_hash=configuration_hash,
    )


def _canonical_json(value: Any) -> str:
    return json.dumps(
        _json_compatible(value),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _json_compatible(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_compatible(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return [_json_compatible(item) for item in value]
    return value


def _utc_text(value: Any) -> str:
    if not isinstance(value, datetime):
        raise ValueError("CANONICAL_ASSEMBLY_ACCEPTED_AT_INVALID")
    instant = value.astimezone(UTC).replace(microsecond=0)
    return instant.strftime("%Y-%m-%dT%H:%M:%SZ")


def _text(value: Any, code: str) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise ValueError(code)
    return value


__all__ = [
    "PostgresCanonicalAssemblyRepository",
    "enqueue_canonical_assembly_if_complete",
]
