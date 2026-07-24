"""Runtime local réel de projection KA : commande, artefact, index et état public."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.contracts.event_envelope import EventEnvelope
from app.contracts.llm_inference import LlmInferenceGateway
from app.contracts.technical_jobs import JobEnvironmentIdentity, JobRequest
from app.contracts.source_references import (
    ACCEPTED_CANONICAL_VERSION_STATUS,
    CanonicalSourceRef,
    SourceLocatorValidationPolicy,
)
from app.knowledge_access.adapters.postgres_projection_read import (
    KnowledgeProjectionVersionConflictError,
    PostgresKnowledgeProjectionRepository,
)
from app.knowledge_access.adapters.qdrant_vector_index import QdrantVectorIndex
from app.knowledge_access.application.chunk_canonical_source import (
    ProjectCanonicalChunksCommand,
    ProjectCanonicalChunksHandler,
)
from app.knowledge_access.application.encode_projection import (
    DenseEncodingRequest,
    EncodeProjectionCommand,
    ProjectionEncodingHandler,
    SparseEncodingRequest,
)
from app.knowledge_access.application.extract_projected_bibliographic_metadata import (
    ExtractProjectedBibliographicMetadataCommand,
    ProjectedBibliographicMetadataExtractor,
    ProjectedTextEvidence,
)
from app.knowledge_access.application.request_projection import (
    CanonicalSourceForProjection,
    ProjectionEligibilityPolicy,
    ProjectionProfileInvalidError,
    RequestKnowledgeProjectionAcceptance,
    RequestKnowledgeProjectionCommand,
    SourceNotFoundError,
)
from app.knowledge_access.domain.chunking import (
    CanonicalChunkDocument,
    ChunkingProfile,
)
from app.knowledge_access.domain.knowledge_projection import (
    KnowledgeProjection,
    ProjectionProfile,
    ProjectionStatus,
)
from app.knowledge_access.application.project_document_contract import (
    PROJECT_DOCUMENT_JOB_NAME,
    ProjectDocumentContract,
    ProjectDocumentContractError,
)
from app.knowledge_access.domain.projection_encoding import (
    DenseEncodingProfile,
    DenseEncodingVector,
    ProjectionEncodingProfile,
    SparseEncodingProfile,
    SparseEncodingVector,
    SparseTokenWeight,
)
from app.knowledge_access.domain.projection_index import (
    VectorIndexPoint,
    VectorIndexPublishRequest,
    VectorIndexSchema,
    index_generation_for,
)
from app.platform.postgres import PostgresConnectionFactory


LOCAL_PROJECTION_PROFILE = ProjectionProfile(
    projection_profile_id="local-hash-projection-v1",
    chunking_profile="hierarchical-pagewise-v1",
    embedding_model="hashing-dense-256-v1",
    sparse_profile="lexical-tf-v1",
    index_schema="qdrant-hybrid-v1",
)
_DENSE_DIMENSIONS = 256
_CANONICAL_ARTIFACT_PREFIX = "artifact:source_processing.canonical_sources/"
_TOKEN_PATTERN = re.compile(r"[\w'-]+", re.UNICODE)
_QUALITY_POLICY_VERSION = "canonical-quality-m004-v1"
_PROJECTION_INDEX_BATCH_SIZE = 32


class ProjectionRuntimeError(RuntimeError):
    """Échec stable du pipeline réel de projection."""

    def __init__(self, error_code: str) -> None:
        self.error_code = _error_code(error_code)
        super().__init__(self.error_code)


class ProjectionRetryableError(ProjectionRuntimeError):
    """Indisponibilité transitoire : le job reste réclamable après sa lease."""


class QdrantHttpClient:
    """Client REST minimal de Qdrant, sans client en mémoire alternatif."""

    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: int,
        dense_dimensions: int,
        api_key: str,
    ) -> None:
        if not isinstance(base_url, str) or base_url.strip() == "":
            raise ValueError("qdrant_url invalide")
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int) or timeout_seconds < 1:
            raise ValueError("qdrant_timeout invalide")
        if isinstance(dense_dimensions, bool) or not isinstance(dense_dimensions, int) or dense_dimensions < 1:
            raise ValueError("qdrant_dimensions invalides")
        if not isinstance(api_key, str) or len(api_key.encode("utf-8")) < 32:
            raise ValueError("qdrant_api_key invalide")
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._dense_dimensions = dense_dimensions
        self._api_key = api_key

    def ensure_collection(self, *, collection_name: str) -> None:
        response = self._request("GET", f"/collections/{collection_name}", None, allow_not_found=True)
        if response is not None:
            _validate_qdrant_collection(
                response,
                expected_dense_dimensions=self._dense_dimensions,
            )
            return
        self._request(
            "PUT",
            f"/collections/{collection_name}",
            {
                "vectors": {"dense": {"size": self._dense_dimensions, "distance": "Cosine"}},
                "sparse_vectors": {"sparse": {}},
            },
        )

    def upsert(self, *, collection_name: str, points: Sequence[Mapping[str, Any]]) -> object:
        self.ensure_collection(collection_name=collection_name)
        self._request(
            "PUT",
            f"/collections/{collection_name}/points?wait=true",
            {"points": list(points)},
        )
        return object()

    def delete(self, *, collection_name: str, points_selector: Mapping[str, Any]) -> object:
        self._request(
            "POST",
            f"/collections/{collection_name}/points/delete?wait=true",
            dict(points_selector),
        )
        return object()

    def count(self, *, collection_name: str, count_filter: Mapping[str, Any], exact: bool) -> int:
        payload = self._request(
            "POST",
            f"/collections/{collection_name}/points/count",
            {"filter": dict(count_filter), "exact": exact},
        )
        try:
            count = payload["result"]["count"]
        except (KeyError, TypeError) as exc:
            raise ProjectionRuntimeError("QDRANT_RESPONSE_INVALID") from exc
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ProjectionRuntimeError("QDRANT_RESPONSE_INVALID")
        return count

    def _request(
        self,
        method: str,
        path: str,
        body: Mapping[str, Any] | None,
        *,
        allow_not_found: bool = False,
    ) -> Mapping[str, Any] | None:
        data = None if body is None else json.dumps(body, separators=(",", ":")).encode("utf-8")
        request = Request(
            f"{self._base_url}{path}",
            data=data,
            method=method,
            headers=(
                {"api-key": self._api_key}
                if data is None
                else {"api-key": self._api_key, "Content-Type": "application/json"}
            ),
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if allow_not_found and exc.code == 404:
                return None
            if exc.code == 429 or exc.code >= 500:
                raise ProjectionRetryableError("QDRANT_UNAVAILABLE") from exc
            raise ProjectionRuntimeError("QDRANT_HTTP_ERROR") from exc
        except (URLError, OSError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProjectionRetryableError("QDRANT_UNAVAILABLE") from exc
        if not isinstance(payload, Mapping):
            raise ProjectionRuntimeError("QDRANT_RESPONSE_INVALID")
        return payload


class HashingDenseEncoder:
    """Encodeur dense local explicite et déterministe, versionné dans le profil."""

    def encode_dense(self, request: DenseEncodingRequest) -> DenseEncodingVector:
        if request.profile.dimensions != _DENSE_DIMENSIONS:
            raise ProjectionRuntimeError("PROJECTION_DENSE_DIMENSIONS_INVALID")
        values = [0.0] * _DENSE_DIMENSIONS
        tokens = _tokens(request.text)
        if len(tokens) == 0:
            raise ProjectionRuntimeError("PROJECTION_CHUNK_EMPTY")
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % _DENSE_DIMENSIONS
            values[index] += 1.0 if digest[4] % 2 == 0 else -1.0
        norm = math.sqrt(sum(value * value for value in values))
        if norm == 0.0:
            raise ProjectionRuntimeError("PROJECTION_DENSE_VECTOR_EMPTY")
        return DenseEncodingVector(values=tuple(value / norm for value in values))


class LexicalSparseEncoder:
    """Encodeur sparse TF explicite, sans modèle de repli caché."""

    def encode_sparse(self, request: SparseEncodingRequest) -> SparseEncodingVector:
        counts = Counter(_tokens(request.text))
        if len(counts) == 0:
            raise ProjectionRuntimeError("PROJECTION_CHUNK_EMPTY")
        return SparseEncodingVector(
            weights=tuple(
                SparseTokenWeight(token=token, weight=float(count))
                for token, count in sorted(counts.items())
            )
        )


@dataclass(frozen=True, slots=True)
class ProjectionRuntimeService:
    """Écrit atomiquement la demande KA et son message d'outbox."""

    connection_factory: PostgresConnectionFactory
    canonical_sources_root: Path
    environment: str
    deployment_id: str
    configuration_hash: str
    qdrant_url: str
    qdrant_collection_name: str
    qdrant_timeout_seconds: int
    qdrant_api_key: str
    max_parallel_workers: int
    inference_gateway: LlmInferenceGateway

    def __post_init__(self) -> None:
        if not callable(getattr(self.connection_factory, "connect", None)):
            raise ValueError("connection_factory projection invalide")
        if not isinstance(self.canonical_sources_root, Path):
            raise ValueError("canonical_sources_root invalide")
        if not re.fullmatch(r"[a-f0-9]{64}", self.configuration_hash):
            raise ValueError("configuration_hash projection invalide")
        JobEnvironmentIdentity(
            environment=self.environment,
            deployment_id=self.deployment_id,
            configuration_hash=self.configuration_hash,
        )
        _required_resource_name(self.qdrant_collection_name, "collection Qdrant projection invalide")
        if not isinstance(self.qdrant_api_key, str) or len(self.qdrant_api_key.encode("utf-8")) < 32:
            raise ValueError("clé API Qdrant projection invalide")
        _required_positive_int(self.max_parallel_workers, "parallélisme projection invalide")
        if not callable(getattr(self.inference_gateway, "infer", None)):
            raise ValueError("gateway bibliographique de projection invalide")

    def request_projection(
        self,
        command: RequestKnowledgeProjectionCommand,
    ) -> RequestKnowledgeProjectionAcceptance:
        if not isinstance(command, RequestKnowledgeProjectionCommand):
            raise ValueError("commande projection invalide")
        if command.projection_profile != LOCAL_PROJECTION_PROFILE:
            raise ProjectionProfileInvalidError("PROJECTION_PROFILE_UNSUPPORTED")
        source = self.find_projection_source_by_document_id(command.document_id)
        if source is None:
            raise SourceNotFoundError(command.document_id)
        canonical_ref = ProjectionEligibilityPolicy().require_eligible(source)
        projection = KnowledgeProjection.request(
            canonical_ref=canonical_ref,
            projection_profile=command.projection_profile,
        )
        trace_id = f"TRACE-KA-{projection.projection_id}"
        publication = self._publication_for_version_id(projection.canonical_version_id)
        try:
            code_version = version("chatbot-trading")
        except Exception as exc:
            raise ProjectionRuntimeError("CODE_VERSION_UNAVAILABLE") from exc
        request = ProjectDocumentContract(
            projection_id=projection.projection_id,
            document_id=projection.document_id,
            canonical_version_id=projection.canonical_version_id,
            canonical_artifact_ref=publication[1],
            canonical_artifact_sha256=canonical_ref.canonical_artifact_sha256,
            build_fingerprint=projection.build_fingerprint.value,
            projection_profile=projection.projection_profile,
            qdrant_collection_name=self.qdrant_collection_name,
            environment_identity=JobEnvironmentIdentity(
                environment=self.environment,
                deployment_id=self.deployment_id,
                configuration_hash=self.configuration_hash,
            ),
            causation_event_id=publication[0],
        ).to_job_request(code_version=code_version)
        with self.connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT projection_id, status, aggregate_version
                      FROM knowledge_access.knowledge_projections
                     WHERE build_fingerprint = %s
                       AND environment = %s
                       AND deployment_id = %s
                       AND configuration_hash = %s
                     FOR UPDATE
                    """,
                    (
                        projection.build_fingerprint.value,
                        self.environment,
                        self.deployment_id,
                        self.configuration_hash,
                    ),
                )
                existing = cursor.fetchone()
                if existing is not None:
                    if existing[0] != projection.projection_id:
                        raise ProjectionRuntimeError("PROJECTION_BUILD_REPLAY_DIVERGENCE")
                    current = KnowledgeProjection(
                        projection_id=projection.projection_id,
                        document_id=projection.document_id,
                        canonical_version_id=projection.canonical_version_id,
                        projection_profile=projection.projection_profile,
                        build_fingerprint=projection.build_fingerprint,
                        status=ProjectionStatus.from_value(existing[1]),
                        aggregate_version=existing[2],
                    )
                    return RequestKnowledgeProjectionAcceptance.from_projection(current)
                cursor.execute(
                    """
                    SELECT projection_id
                      FROM knowledge_access.knowledge_projections
                     WHERE build_fingerprint = %s
                     FOR UPDATE
                    """,
                    (projection.build_fingerprint.value,),
                )
                if cursor.fetchone() is not None:
                    raise ProjectionRuntimeError("PROJECTION_ENVIRONMENT_MISMATCH")
                profile = projection.projection_profile
                cursor.execute(
                    """
                    INSERT INTO knowledge_access.knowledge_projections (
                        projection_id, document_id, canonical_version_id,
                        projection_profile_id, chunking_profile, embedding_model,
                        sparse_profile, index_schema, build_fingerprint, status,
                        chunk_count, state_observed_at, aggregate_version,
                        execution_phase, completed_units, total_units, failure_error_code,
                        environment, deployment_id, configuration_hash,
                        qdrant_collection_name
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, 'REQUESTED',
                        0, CURRENT_TIMESTAMP, 0, 'QUEUED', 0, 1, NULL,
                        %s, %s, %s, %s
                    )
                    """,
                    (
                        projection.projection_id,
                        projection.document_id,
                        projection.canonical_version_id,
                        profile.projection_profile_id,
                        profile.chunking_profile,
                        profile.embedding_model,
                        profile.sparse_profile,
                        profile.index_schema,
                        projection.build_fingerprint.value,
                        request.environment,
                        request.deployment_id,
                        request.idempotence_key.configuration_hash,
                        self.qdrant_collection_name,
                    ),
                )
                cursor.execute(
                    """
                    INSERT INTO knowledge_access.job_outbox (
                        environment, deployment_id,
                        job_name, priority, input_hash, configuration_hash,
                        code_version, model_version, payload, trace_id, status
                    ) VALUES (%s, %s, %s, 'P1', %s, %s, %s, %s, %s::jsonb, %s, 'pending')
                    """,
                    (
                        request.environment,
                        request.deployment_id,
                        request.job_name,
                        request.idempotence_key.input_hash,
                        request.idempotence_key.configuration_hash,
                        request.idempotence_key.code_version,
                        request.idempotence_key.model_version,
                        json.dumps(dict(request.payload), separators=(",", ":")),
                        trace_id,
                    ),
                )
        return RequestKnowledgeProjectionAcceptance.from_projection(projection)

    def find_projection_source_by_document_id(
        self,
        document_id: str,
    ) -> CanonicalSourceForProjection | None:
        with self.connection_factory.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT event_payload
                      FROM knowledge_access.canonical_publication_inbox
                     WHERE document_id = %s
                       AND environment = %s
                       AND deployment_id = %s
                       AND configuration_hash = %s
                     ORDER BY received_at DESC, event_id DESC
                     LIMIT 1
                    """,
                    (
                        document_id,
                        self.environment,
                        self.deployment_id,
                        self.configuration_hash,
                    ),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        canonical_ref = CanonicalSourceRef.from_payload(_event_payload(row[0]))
        if canonical_ref.document_id != document_id:
            raise ProjectionRuntimeError("CANONICAL_SOURCE_RECORD_INVALID")
        return CanonicalSourceForProjection(
            document_id=document_id,
            canonical_ref=canonical_ref,
            canonical_status=ACCEPTED_CANONICAL_VERSION_STATUS,
            quarantine_reason=None,
        )

    def find_chunking_source_by_version_id(self, canonical_version_id: str) -> CanonicalChunkDocument | None:
        with self.connection_factory.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT event_payload, canonical_artifact_ref
                      FROM knowledge_access.canonical_publication_inbox
                     WHERE canonical_version_id = %s
                       AND environment = %s
                       AND deployment_id = %s
                       AND configuration_hash = %s
                    """,
                    (
                        canonical_version_id,
                        self.environment,
                        self.deployment_id,
                        self.configuration_hash,
                    ),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        canonical_ref = CanonicalSourceRef.from_payload(_event_payload(row[0]))
        artifact_ref = row[1]
        artifact_path = _artifact_path(root=self.canonical_sources_root, artifact_ref=artifact_ref)
        try:
            artifact_bytes = artifact_path.read_bytes()
        except OSError as exc:
            raise ProjectionRuntimeError("CANONICAL_ARTIFACT_UNREADABLE") from exc
        if hashlib.sha256(artifact_bytes).hexdigest() != canonical_ref.canonical_artifact_sha256:
            raise ProjectionRuntimeError("CANONICAL_ARTIFACT_HASH_MISMATCH")
        try:
            artifact = json.loads(artifact_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProjectionRuntimeError("CANONICAL_ARTIFACT_INVALID") from exc
        items = _canonical_items_payload(artifact=artifact, canonical_ref=canonical_ref)
        policy = SourceLocatorValidationPolicy(
            canonical_sources_by_version_id={canonical_ref.canonical_version_id: canonical_ref},
            version_statuses_by_version_id={
                canonical_ref.canonical_version_id: ACCEPTED_CANONICAL_VERSION_STATUS
            },
            resolvable_item_ids_by_version_id={
                canonical_ref.canonical_version_id: {
                    item["source_locator"]["item_id"]: item["source_locator"]["content_hash"]
                    for item in items
                }
            },
        )
        return CanonicalChunkDocument.from_payload(
            {
                "schema_version": "1.0",
                "canonical_ref": canonical_ref.to_payload(),
                "version_status": ACCEPTED_CANONICAL_VERSION_STATUS,
                "items": items,
            },
            validation_policy=policy,
        )

    def read_projection_progress(self, document_id: str) -> Mapping[str, Any]:
        with self.connection_factory.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT execution_phase, completed_units, total_units, failure_error_code
                      FROM knowledge_access.knowledge_projections
                     WHERE document_id = %s
                       AND environment = %s
                       AND deployment_id = %s
                       AND configuration_hash = %s
                     ORDER BY state_observed_at DESC, projection_id DESC
                     LIMIT 1
                    """,
                    (
                        document_id,
                        self.environment,
                        self.deployment_id,
                        self.configuration_hash,
                    ),
                )
                row = cursor.fetchone()
        if row is None:
            return {
                "action_name": "PROJECT_DOCUMENT",
                "phase": "NOT_REQUESTED",
                "completed_units": 0,
                "total_units": None,
                "failure_error_code": None,
                "environment": self.environment,
                "deployment_id": self.deployment_id,
                "configuration_hash": self.configuration_hash,
            }
        return {
            "action_name": "PROJECT_DOCUMENT",
            "phase": row[0],
            "completed_units": row[1],
            "total_units": row[2],
            "failure_error_code": row[3],
            "environment": self.environment,
            "deployment_id": self.deployment_id,
            "configuration_hash": self.configuration_hash,
        }

    def execute_projection(self, *, request: JobRequest) -> Mapping[str, Any]:
        projection_id = _projection_id_hint(request)
        try:
            contract = self._validated_contract(request)
            projection_id = contract.projection_id
            self._require_projection_identity(projection_id)
            repository = PostgresKnowledgeProjectionRepository(
                connection_factory=self.connection_factory,
                sample_storage_limit=3,
            )
            projection = repository.projection_for_id(projection_id)
            if (
                contract.document_id != projection.document_id
                or contract.canonical_version_id != projection.canonical_version_id
                or contract.build_fingerprint != projection.build_fingerprint.value
                or contract.projection_profile
                != projection.projection_profile
            ):
                raise ProjectionRuntimeError("PROJECTION_JOB_REPLAY_DIVERGENCE")
            publication = self._publication_for_version_id(
                projection.canonical_version_id
            )
            if (
                contract.causation_event_id != publication[0]
                or contract.canonical_artifact_ref != publication[1]
                or contract.canonical_artifact_sha256 != publication[2]
            ):
                raise ProjectionRuntimeError("PROJECTION_JOB_REPLAY_DIVERGENCE")
            stages = projection_resume_stages(projection.status.value)
            if stages == ("VERIFY",):
                return self._replay_searchable_projection(projection=projection)
            if projection.status is ProjectionStatus.REQUESTED:
                building = repository.save_transition(projection.start_build())
            elif projection.status is ProjectionStatus.BUILDING:
                building = projection
            else:
                building = None
            chunk_projection = ProjectCanonicalChunksHandler(
                canonical_source_reader=self,
            ).project_from_canonical_version(
                ProjectCanonicalChunksCommand(
                    canonical_version_id=projection.canonical_version_id,
                    chunking_profile=ChunkingProfile(
                        profile_id=LOCAL_PROJECTION_PROFILE.chunking_profile,
                        profile_version="hierarchical-v1",
                        max_parent_items=64,
                        max_child_items=16,
                        max_child_characters=4000,
                    ),
                )
            )
            if building is not None:
                self._set_running_progress(
                    projection_id=building.projection_id,
                    completed_units=0,
                    total_units=len(chunk_projection.chunks) + 1,
                )
                built = repository.save_transition(building.mark_built())
            elif projection.status is ProjectionStatus.BUILT:
                built = projection
            else:
                built = None
            if built is not None:
                indexing = repository.save_transition(built.start_indexing())
            elif projection.status is ProjectionStatus.INDEXING:
                indexing = projection
            else:
                raise ProjectionRuntimeError("PROJECTION_STATE_NOT_RESUMABLE")
            encoded = ProjectionEncodingHandler(
                dense_encoder=HashingDenseEncoder(),
                sparse_encoder=LexicalSparseEncoder(),
                max_parallel_chunks=self.max_parallel_workers,
            ).encode_projection(
                EncodeProjectionCommand(
                    projection_id=indexing.projection_id,
                    build_fingerprint=indexing.build_fingerprint,
                    chunk_projection=chunk_projection,
                    encoding_profile=_encoding_profile(),
                )
            )
            schema = _index_schema(collection_name=self.qdrant_collection_name)
            generation = index_generation_for(
                projection=indexing,
                encoded_projection=encoded,
                index_schema=schema,
            )
            points = tuple(
                VectorIndexPoint.from_encoded_chunk(
                    projection=indexing,
                    encoded_chunk=chunk,
                    index_schema=schema,
                )
                for chunk in encoded.encoded_chunks
            )
            client = QdrantHttpClient(
                base_url=self.qdrant_url,
                timeout_seconds=self.qdrant_timeout_seconds,
                dense_dimensions=_DENSE_DIMENSIONS,
                api_key=self.qdrant_api_key,
            )
            client.ensure_collection(collection_name=schema.collection_name)
            publication = QdrantVectorIndex(client=client).repair_generation(
                VectorIndexPublishRequest(
                    collection_name=schema.collection_name,
                    index_generation=generation,
                    schema=schema,
                    build_fingerprint=encoded.build_fingerprint,
                    points=points,
                    expected_point_count=len(points),
                ),
                max_parallel_batches=self.max_parallel_workers,
                batch_size=_PROJECTION_INDEX_BATCH_SIZE,
                on_batch_published=lambda completed_units: self._set_running_progress(
                    projection_id=indexing.projection_id,
                    completed_units=completed_units,
                    total_units=len(points) + 1,
                ),
            )
            if publication.published_point_count != len(points):
                raise ProjectionRuntimeError("INDEX_PARTIAL")
            canonical_document = self.find_chunking_source_by_version_id(
                indexing.canonical_version_id
            )
            if canonical_document is None:
                raise ProjectionRuntimeError("CANONICAL_SOURCE_NOT_FOUND")
            self._ensure_bibliographic_metadata(
                repository=repository,
                projection=indexing,
                canonical_document=canonical_document,
            )
            self._set_running_progress(
                projection_id=indexing.projection_id,
                completed_units=len(points) + 1,
                total_units=len(points) + 1,
            )
            searchable = indexing.mark_searchable()
            repository.save_projection_outputs(
                projection=searchable,
                chunk_count=len(chunk_projection.chunks),
                chunks=chunk_projection.chunks[:3],
                state_observed_at=_now(),
                index_generation=generation,
            )
            self._mark_succeeded(
                projection_id=searchable.projection_id,
                completed_units=len(chunk_projection.chunks) + 1,
                total_units=len(chunk_projection.chunks) + 1,
            )
            return {
                "projection_id": searchable.projection_id,
                "chunk_count": len(chunk_projection.chunks),
                "index_generation": generation,
                "published_point_count": publication.published_point_count,
                "bibliographic_metadata_status": "EXTRACTED",
            }
        except Exception as exc:
            error_code = _projection_error_code(exc)
            if projection_failure_disposition(exc) == "RETRY":
                raise ProjectionRetryableError(error_code) from exc
            if projection_id is not None:
                self._mark_failed_if_possible(
                    projection_id=projection_id,
                    error_code=error_code,
                )
            raise ProjectionRuntimeError(error_code) from exc

    def _validated_contract(self, request: JobRequest) -> ProjectDocumentContract:
        expected_identity = JobEnvironmentIdentity(
            environment=self.environment,
            deployment_id=self.deployment_id,
            configuration_hash=self.configuration_hash,
        )
        try:
            contract = ProjectDocumentContract.from_job_request(request)
        except ProjectDocumentContractError as error:
            raise ProjectionRuntimeError(error.code) from error
        if contract.environment_identity != expected_identity:
            raise ProjectionRuntimeError("PROJECTION_ENVIRONMENT_MISMATCH")
        if contract.qdrant_collection_name != self.qdrant_collection_name:
            raise ProjectionRuntimeError("PROJECTION_COLLECTION_MISMATCH")
        return contract

    def _require_projection_identity(self, projection_id: str) -> None:
        with self.connection_factory.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT environment, deployment_id, configuration_hash,
                           qdrant_collection_name
                      FROM knowledge_access.knowledge_projections
                     WHERE projection_id = %s
                    """,
                    (projection_id,),
                )
                row = cursor.fetchone()
        if row is None:
            raise ProjectionRuntimeError("PROJECTION_NOT_FOUND")
        if tuple(row) != (
            self.environment,
            self.deployment_id,
            self.configuration_hash,
            self.qdrant_collection_name,
        ):
            raise ProjectionRuntimeError("PROJECTION_ENVIRONMENT_MISMATCH")

    def _publication_for_version_id(self, canonical_version_id: str) -> tuple[str, str, str]:
        with self.connection_factory.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT event_id, canonical_artifact_ref,
                           canonical_artifact_sha256
                      FROM knowledge_access.canonical_publication_inbox
                     WHERE canonical_version_id = %s
                       AND environment = %s
                       AND deployment_id = %s
                       AND configuration_hash = %s
                    """,
                    (
                        canonical_version_id,
                        self.environment,
                        self.deployment_id,
                        self.configuration_hash,
                    ),
                )
                row = cursor.fetchone()
        if row is None:
            raise ProjectionRuntimeError("CANONICAL_SOURCE_NOT_FOUND")
        return str(row[0]), str(row[1]), str(row[2])

    def _ensure_bibliographic_metadata(
        self,
        *,
        repository: PostgresKnowledgeProjectionRepository,
        projection: KnowledgeProjection,
        canonical_document: CanonicalChunkDocument,
    ) -> None:
        with self.connection_factory.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT bibliographic_metadata_status
                      FROM knowledge_access.knowledge_projections
                     WHERE projection_id = %s
                       AND environment = %s
                       AND deployment_id = %s
                       AND configuration_hash = %s
                    """,
                    (
                        projection.projection_id,
                        self.environment,
                        self.deployment_id,
                        self.configuration_hash,
                    ),
                )
                row = cursor.fetchone()
        if row == ("EXTRACTED",):
            return
        if row != ("PENDING",):
            raise ProjectionRuntimeError("BIBLIOGRAPHIC_METADATA_STATE_INVALID")
        metadata = ProjectedBibliographicMetadataExtractor(
            inference_gateway=self.inference_gateway
        ).extract(
            ExtractProjectedBibliographicMetadataCommand(
                document_id=projection.document_id,
                projection_id=projection.projection_id,
                evidences=_bibliographic_text_evidences(canonical_document.items),
            )
        )
        repository.save_bibliographic_metadata(
            projection_id=projection.projection_id,
            metadata=metadata,
        )

    def _replay_searchable_projection(
        self,
        *,
        projection: KnowledgeProjection,
    ) -> Mapping[str, Any]:
        with self.connection_factory.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT chunk_count, index_generation, execution_phase,
                           completed_units, total_units, qdrant_collection_name
                      FROM knowledge_access.knowledge_projections
                     WHERE projection_id = %s
                       AND environment = %s
                       AND deployment_id = %s
                       AND configuration_hash = %s
                    """,
                    (
                        projection.projection_id,
                        self.environment,
                        self.deployment_id,
                        self.configuration_hash,
                    ),
                )
                row = cursor.fetchone()
        if (
            row is None
            or not isinstance(row[0], int)
            or row[0] < 1
            or not isinstance(row[1], str)
            or row[2] != "SUCCEEDED"
            or row[3] != row[4]
            or row[5] != self.qdrant_collection_name
        ):
            raise ProjectionRuntimeError("PROJECTION_REPLAY_INCOMPLETE")
        client = QdrantHttpClient(
            base_url=self.qdrant_url,
            timeout_seconds=self.qdrant_timeout_seconds,
            dense_dimensions=_DENSE_DIMENSIONS,
            api_key=self.qdrant_api_key,
        )
        indexed = client.count(
            collection_name=self.qdrant_collection_name,
            count_filter={
                "must": [
                    {"key": "index_generation", "match": {"value": row[1]}},
                ]
            },
            exact=True,
        )
        if indexed != row[0]:
            raise ProjectionRuntimeError("PROJECTION_REPLAY_INCOMPLETE")
        return {
            "projection_id": projection.projection_id,
            "chunk_count": row[0],
            "index_generation": row[1],
            "published_point_count": indexed,
            "bibliographic_metadata_status": "EXTRACTED",
        }

    def _set_running_progress(self, *, projection_id: str, completed_units: int, total_units: int) -> None:
        if total_units < 1 or completed_units < 0 or completed_units > total_units:
            raise ValueError("progression projection invalide")
        with self.connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE knowledge_access.knowledge_projections
                       SET execution_phase = 'RUNNING', completed_units = %s,
                           total_units = %s, state_observed_at = CURRENT_TIMESTAMP
                     WHERE projection_id = %s AND status IN ('BUILDING', 'BUILT', 'INDEXING')
                       AND environment = %s
                       AND deployment_id = %s
                       AND configuration_hash = %s
                    """,
                    (
                        completed_units,
                        total_units,
                        projection_id,
                        self.environment,
                        self.deployment_id,
                        self.configuration_hash,
                    ),
                )
                if cursor.rowcount != 1:
                    raise KnowledgeProjectionVersionConflictError()

    def _mark_succeeded(self, *, projection_id: str, completed_units: int, total_units: int) -> None:
        with self.connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE knowledge_access.knowledge_projections
                       SET execution_phase = 'SUCCEEDED', completed_units = %s,
                           total_units = %s, failure_error_code = NULL,
                           state_observed_at = CURRENT_TIMESTAMP
                     WHERE projection_id = %s AND status = 'SEARCHABLE'
                       AND environment = %s
                       AND deployment_id = %s
                       AND configuration_hash = %s
                    """,
                    (
                        completed_units,
                        total_units,
                        projection_id,
                        self.environment,
                        self.deployment_id,
                        self.configuration_hash,
                    ),
                )
                if cursor.rowcount != 1:
                    raise KnowledgeProjectionVersionConflictError()

    def _mark_failed_if_possible(self, *, projection_id: str, error_code: str) -> None:
        with self.connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE knowledge_access.knowledge_projections
                       SET status = 'FAILED', execution_phase = 'FAILED',
                           failure_error_code = %s, state_observed_at = CURRENT_TIMESTAMP,
                           aggregate_version = aggregate_version + 1
                     WHERE projection_id = %s
                       AND status IN ('REQUESTED', 'BUILDING', 'BUILT', 'INDEXING')
                       AND environment = %s
                       AND deployment_id = %s
                       AND configuration_hash = %s
                    """,
                    (
                        error_code,
                        projection_id,
                        self.environment,
                        self.deployment_id,
                        self.configuration_hash,
                    ),
                )


def _canonical_items_payload(*, artifact: Any, canonical_ref: CanonicalSourceRef) -> tuple[dict[str, Any], ...]:
    if not isinstance(artifact, Mapping) or artifact.get("canonical_version_id") != canonical_ref.canonical_version_id:
        raise ProjectionRuntimeError("CANONICAL_ARTIFACT_INVALID")
    pages = artifact.get("pages")
    if not isinstance(pages, list):
        raise ProjectionRuntimeError("CANONICAL_ARTIFACT_INVALID")
    items: list[dict[str, Any]] = []
    for page in pages:
        if not isinstance(page, Mapping) or not isinstance(page.get("items"), list):
            raise ProjectionRuntimeError("CANONICAL_ARTIFACT_INVALID")
        for item in page["items"]:
            if not isinstance(item, Mapping):
                raise ProjectionRuntimeError("CANONICAL_ARTIFACT_INVALID")
            text = item.get("text")
            provenance = item.get("provenance")
            if not isinstance(text, str) or text.strip() == "" or not isinstance(provenance, Mapping):
                raise ProjectionRuntimeError("CANONICAL_ARTIFACT_INVALID")
            items.append({"text": text, "source_locator": dict(provenance)})
    if len(items) == 0:
        raise ProjectionRuntimeError("CANONICAL_CONTENT_EMPTY")
    return tuple(items)


def projection_resume_stages(status: str) -> tuple[str, ...]:
    """Étapes déterministes à rejouer depuis chaque état public persistant."""

    stages = {
        "REQUESTED": ("BUILD", "INDEX", "FINALIZE"),
        "BUILDING": ("BUILD", "INDEX", "FINALIZE"),
        "BUILT": ("INDEX", "FINALIZE"),
        "INDEXING": ("INDEX", "FINALIZE"),
        "SEARCHABLE": ("VERIFY",),
    }
    try:
        return stages[status]
    except (KeyError, TypeError) as error:
        raise ProjectionRuntimeError("PROJECTION_STATE_NOT_RESUMABLE") from error


def projection_failure_disposition(exception: Exception) -> str:
    """Décide explicitement si la lease doit expirer ou l'état terminaliser."""

    if isinstance(exception, ProjectionRetryableError):
        return "RETRY"
    code = _projection_error_code(exception)
    if code in {"QDRANT_UNAVAILABLE"}:
        return "RETRY"
    return "FAILED"


def _projection_id_hint(request: Any) -> str | None:
    if not isinstance(request, JobRequest):
        return None
    value = request.payload.get("projection_id")
    if not isinstance(value, str) or not value.startswith("PROJ-"):
        return None
    return value


def _validate_qdrant_collection(
    response: Mapping[str, Any],
    *,
    expected_dense_dimensions: int,
) -> None:
    try:
        result = response["result"]
        config = result["config"]
        params = config["params"]
        vectors = params["vectors"]
        dense = vectors["dense"]
        sparse_vectors = params["sparse_vectors"]
        if (
            not isinstance(result, Mapping)
            or not isinstance(config, Mapping)
            or not isinstance(params, Mapping)
            or not isinstance(vectors, Mapping)
            or not isinstance(dense, Mapping)
            or dense.get("size") != expected_dense_dimensions
            or dense.get("distance") != "Cosine"
            or not isinstance(sparse_vectors, Mapping)
            or "sparse" not in sparse_vectors
            or not isinstance(sparse_vectors["sparse"], Mapping)
        ):
            raise ValueError
    except (KeyError, TypeError, ValueError) as error:
        raise ProjectionRuntimeError("PROJECTION_COLLECTION_MISMATCH") from error


def _bibliographic_text_evidences(items: Sequence[Any]) -> tuple[ProjectedTextEvidence, ...]:
    page_texts: dict[int, list[str]] = {}
    for item in items:
        page_pdf = getattr(item, "page_pdf", None)
        text = getattr(item, "text", None)
        if not isinstance(page_pdf, int) or not 1 <= page_pdf <= 12:
            continue
        if not isinstance(text, str) or text.strip() == "":
            continue
        page_texts.setdefault(page_pdf, []).append(text)
    evidences: list[ProjectedTextEvidence] = []
    remaining = 40_000
    for page_pdf in sorted(page_texts):
        combined = "\n".join(page_texts[page_pdf])
        if remaining <= 0:
            break
        bounded = combined[:remaining]
        if bounded.strip() == "":
            continue
        evidences.append(ProjectedTextEvidence(page_pdf=page_pdf, text=bounded))
        remaining -= len(bounded)
    if len(evidences) == 0:
        raise ProjectionRuntimeError("BIBLIOGRAPHIC_METADATA_EVIDENCE_MISSING")
    return tuple(evidences)


def _event_payload(value: Any) -> Mapping[str, Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ProjectionRuntimeError("CANONICAL_SOURCE_RECORD_INVALID") from exc
    if not isinstance(value, Mapping):
        raise ProjectionRuntimeError("CANONICAL_SOURCE_RECORD_INVALID")
    event = EventEnvelope.from_payload(dict(value))
    if event.event_type != "CanonicalSourcePublished" or event.producer_context != "SP":
        raise ProjectionRuntimeError("CANONICAL_SOURCE_RECORD_INVALID")
    return dict(event.payload)


def _artifact_path(*, root: Path, artifact_ref: Any) -> Path:
    if not isinstance(artifact_ref, str) or not artifact_ref.startswith(_CANONICAL_ARTIFACT_PREFIX):
        raise ProjectionRuntimeError("CANONICAL_ARTIFACT_REF_INVALID")
    relative = Path(artifact_ref.removeprefix(_CANONICAL_ARTIFACT_PREFIX))
    if relative.is_absolute() or ".." in relative.parts:
        raise ProjectionRuntimeError("CANONICAL_ARTIFACT_REF_INVALID")
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ProjectionRuntimeError("CANONICAL_ARTIFACT_REF_INVALID") from exc
    return path


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(match.group(0).casefold() for match in _TOKEN_PATTERN.finditer(value))


def _encoding_profile() -> ProjectionEncodingProfile:
    return ProjectionEncodingProfile(
        profile_id="local-hash-lexical-v1",
        profile_version="1",
        dense=DenseEncodingProfile(
            profile_id=LOCAL_PROJECTION_PROFILE.embedding_model,
            model_name="hashing-dense",
            model_version="1",
            dimensions=_DENSE_DIMENSIONS,
            parameters_hash=hashlib.sha256(b"hashing-dense-256-v1").hexdigest(),
        ),
        sparse=SparseEncodingProfile(
            profile_id=LOCAL_PROJECTION_PROFILE.sparse_profile,
            model_name="lexical-term-frequency",
            model_version="1",
            parameters_hash=hashlib.sha256(b"lexical-tf-v1").hexdigest(),
        ),
    )


def _index_schema(*, collection_name: str) -> VectorIndexSchema:
    return VectorIndexSchema(
        schema_version=LOCAL_PROJECTION_PROFILE.index_schema,
        collection_name=_required_resource_name(collection_name, "collection Qdrant projection invalide"),
        dense_dimensions=_DENSE_DIMENSIONS,
        distance="cosine",
        payload_schema_version="1",
    )


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _utc_second(value: Any) -> str:
    if not callable(getattr(value, "astimezone", None)):
        raise ProjectionRuntimeError("CANONICAL_SOURCE_RECORD_INVALID")
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _error_code(value: Any) -> str:
    if isinstance(value, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{2,127}", value):
        return value
    raise ValueError("error_code projection invalide")


def _required_positive_int(value: Any, message: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(message)
    return value


def _required_resource_name(value: Any, message: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[a-z0-9]+(?:[-_][a-z0-9]+)*", value) is None:
        raise ValueError(message)
    return value


def _projection_error_code(exception: Exception) -> str:
    if isinstance(exception, ProjectionRuntimeError):
        return exception.error_code
    candidate = getattr(exception, "error_code", None)
    if isinstance(candidate, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{2,127}", candidate):
        return candidate
    return "PROJECTION_WORKER_UNEXPECTED_ERROR"


__all__ = [
    "LOCAL_PROJECTION_PROFILE",
    "PROJECT_DOCUMENT_JOB_NAME",
    "ProjectionRuntimeError",
    "ProjectionRetryableError",
    "ProjectionRuntimeService",
    "QdrantHttpClient",
    "projection_failure_disposition",
    "projection_resume_stages",
]
