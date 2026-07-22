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

from app.contracts.llm_inference import LlmInferenceGateway
from app.contracts.technical_jobs import JobEnvironmentIdentity
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
    ProjectionAlreadyRequestedError,
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


PROJECT_DOCUMENT_JOB_NAME = "PROJECT_DOCUMENT"
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


class QdrantHttpClient:
    """Client REST minimal de Qdrant, sans client en mémoire alternatif."""

    def __init__(self, *, base_url: str, timeout_seconds: int, dense_dimensions: int) -> None:
        if not isinstance(base_url, str) or base_url.strip() == "":
            raise ValueError("qdrant_url invalide")
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int) or timeout_seconds < 1:
            raise ValueError("qdrant_timeout invalide")
        if isinstance(dense_dimensions, bool) or not isinstance(dense_dimensions, int) or dense_dimensions < 1:
            raise ValueError("qdrant_dimensions invalides")
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._dense_dimensions = dense_dimensions

    def ensure_collection(self, *, collection_name: str) -> None:
        response = self._request("GET", f"/collections/{collection_name}", None, allow_not_found=True)
        if response is not None:
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
            headers={} if data is None else {"Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if allow_not_found and exc.code == 404:
                return None
            raise ProjectionRuntimeError("QDRANT_HTTP_ERROR") from exc
        except (URLError, OSError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProjectionRuntimeError("QDRANT_UNAVAILABLE") from exc
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
        payload = {
            "projection_id": projection.projection_id,
            "document_id": projection.document_id,
            "canonical_version_id": projection.canonical_version_id,
        }
        try:
            code_version = version("chatbot-trading")
        except Exception as exc:
            raise ProjectionRuntimeError("CODE_VERSION_UNAVAILABLE") from exc
        with self.connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    "SELECT projection_id FROM knowledge_access.knowledge_projections "
                    "WHERE build_fingerprint = %s FOR UPDATE",
                    (projection.build_fingerprint.value,),
                )
                existing = cursor.fetchone()
                if existing is not None:
                    raise ProjectionAlreadyRequestedError(
                        projection_id=existing[0],
                        build_fingerprint=projection.build_fingerprint,
                    )
                profile = projection.projection_profile
                cursor.execute(
                    """
                    INSERT INTO knowledge_access.knowledge_projections (
                        projection_id, document_id, canonical_version_id,
                        projection_profile_id, chunking_profile, embedding_model,
                        sparse_profile, index_schema, build_fingerprint, status,
                        chunk_count, state_observed_at, aggregate_version,
                        execution_phase, completed_units, total_units, failure_error_code
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, 'REQUESTED',
                        0, CURRENT_TIMESTAMP, 0, 'QUEUED', 0, 1, NULL
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
                        self.environment,
                        self.deployment_id,
                        PROJECT_DOCUMENT_JOB_NAME,
                        projection.build_fingerprint.value,
                        self.configuration_hash,
                        code_version,
                        LOCAL_PROJECTION_PROFILE.embedding_model,
                        json.dumps(payload, separators=(",", ":")),
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
                    SELECT document.status, document.quarantine_reason, document.fingerprint,
                           version.canonical_source_id, version.canonical_version_id,
                           version.canonical_artifact_ref, version.canonical_artifact_sha256,
                           version.accepted_at, run.source_page_count
                      FROM source_processing.source_documents AS document
                      LEFT JOIN LATERAL (
                          SELECT * FROM source_processing.canonical_source_versions
                           WHERE document_id = document.document_id
                           ORDER BY accepted_at DESC
                           LIMIT 1
                      ) AS version ON TRUE
                      LEFT JOIN source_processing.document_processing_runs AS run
                        ON run.document_id = document.document_id
                     WHERE document.document_id = %s
                    """,
                    (document_id,),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        status, reason, source_sha, source_id, version_id, artifact_ref, artifact_sha, accepted_at, page_count = row
        if status == "QUARANTINED":
            return CanonicalSourceForProjection(
                document_id=document_id,
                canonical_ref=None,
                canonical_status="QUARANTINED",
                quarantine_reason=reason,
            )
        if version_id is None:
            return CanonicalSourceForProjection(
                document_id=document_id,
                canonical_ref=None,
                canonical_status="REJECTED",
                quarantine_reason=None,
            )
        if not callable(getattr(accepted_at, "isoformat", None)) or not isinstance(page_count, int):
            raise ProjectionRuntimeError("CANONICAL_SOURCE_RECORD_INVALID")
        canonical_ref = CanonicalSourceRef(
            schema_version="1.0",
            canonical_source_id=source_id,
            document_id=document_id,
            canonical_version_id=version_id,
            source_sha256=source_sha,
            canonical_artifact_sha256=artifact_sha,
            page_count=page_count,
            accepted_at=_utc_second(accepted_at),
            quality_policy_version=_QUALITY_POLICY_VERSION,
        )
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
                    SELECT document.fingerprint, version.canonical_source_id, version.document_id,
                           version.canonical_version_id, version.canonical_artifact_ref,
                           version.canonical_artifact_sha256, version.accepted_at,
                           run.source_page_count
                      FROM source_processing.canonical_source_versions AS version
                      JOIN source_processing.source_documents AS document
                        ON document.document_id = version.document_id
                      JOIN source_processing.document_processing_runs AS run
                        ON run.document_id = version.document_id
                     WHERE version.canonical_version_id = %s
                    """,
                    (canonical_version_id,),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        source_sha, source_id, document_id, version_id, artifact_ref, artifact_sha, accepted_at, page_count = row
        if not callable(getattr(accepted_at, "isoformat", None)) or not isinstance(page_count, int):
            raise ProjectionRuntimeError("CANONICAL_SOURCE_RECORD_INVALID")
        canonical_ref = CanonicalSourceRef(
            schema_version="1.0",
            canonical_source_id=source_id,
            document_id=document_id,
            canonical_version_id=version_id,
            source_sha256=source_sha,
            canonical_artifact_sha256=artifact_sha,
            page_count=page_count,
            accepted_at=_utc_second(accepted_at),
            quality_policy_version=_QUALITY_POLICY_VERSION,
        )
        artifact_path = _artifact_path(root=self.canonical_sources_root, artifact_ref=artifact_ref)
        try:
            artifact_bytes = artifact_path.read_bytes()
        except OSError as exc:
            raise ProjectionRuntimeError("CANONICAL_ARTIFACT_UNREADABLE") from exc
        if hashlib.sha256(artifact_bytes).hexdigest() != artifact_sha:
            raise ProjectionRuntimeError("CANONICAL_ARTIFACT_HASH_MISMATCH")
        try:
            artifact = json.loads(artifact_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProjectionRuntimeError("CANONICAL_ARTIFACT_INVALID") from exc
        items = _canonical_items_payload(artifact=artifact, canonical_ref=canonical_ref)
        policy = SourceLocatorValidationPolicy(
            canonical_sources_by_version_id={version_id: canonical_ref},
            version_statuses_by_version_id={version_id: ACCEPTED_CANONICAL_VERSION_STATUS},
            resolvable_item_ids_by_version_id={
                version_id: {
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
                     ORDER BY state_observed_at DESC, projection_id DESC
                     LIMIT 1
                    """,
                    (document_id,),
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

    def execute_projection(self, *, projection_id: str) -> Mapping[str, Any]:
        repository = PostgresKnowledgeProjectionRepository(
            connection_factory=self.connection_factory,
            sample_storage_limit=3,
        )
        projection = repository.projection_for_id(projection_id)
        try:
            building = repository.save_transition(projection.start_build())
            chunk_projection = ProjectCanonicalChunksHandler(
                canonical_source_reader=self,
            ).project_from_canonical_version(
                ProjectCanonicalChunksCommand(
                    canonical_version_id=building.canonical_version_id,
                    chunking_profile=ChunkingProfile(
                        profile_id=LOCAL_PROJECTION_PROFILE.chunking_profile,
                        profile_version="hierarchical-v1",
                        max_parent_items=64,
                        max_child_items=16,
                        max_child_characters=4000,
                    ),
                )
            )
            self._set_running_progress(
                projection_id=building.projection_id,
                completed_units=0,
                total_units=len(chunk_projection.chunks) + 1,
            )
            built = repository.save_transition(building.mark_built())
            indexing = repository.save_transition(built.start_indexing())
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
            )
            client.ensure_collection(collection_name=schema.collection_name)
            publication = QdrantVectorIndex(client=client).publish_generation(
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
            metadata = ProjectedBibliographicMetadataExtractor(
                inference_gateway=self.inference_gateway
            ).extract(
                ExtractProjectedBibliographicMetadataCommand(
                    document_id=indexing.document_id,
                    projection_id=indexing.projection_id,
                    evidences=_bibliographic_text_evidences(canonical_document.items),
                )
            )
            repository.save_bibliographic_metadata(
                projection_id=indexing.projection_id,
                metadata=metadata,
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
            self._mark_failed_if_possible(projection_id=projection_id, error_code=error_code)
            raise ProjectionRuntimeError(error_code) from exc

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
                    """,
                    (completed_units, total_units, projection_id),
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
                    """,
                    (completed_units, total_units, projection_id),
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
                       AND status IN ('REQUESTED', 'BUILDING', 'INDEXING')
                    """,
                    (error_code, projection_id),
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
                continue
            items.append({"text": text, "source_locator": dict(provenance)})
    if len(items) == 0:
        raise ProjectionRuntimeError("CANONICAL_CONTENT_EMPTY")
    return tuple(items)


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
    "ProjectionRuntimeService",
    "QdrantHttpClient",
]
