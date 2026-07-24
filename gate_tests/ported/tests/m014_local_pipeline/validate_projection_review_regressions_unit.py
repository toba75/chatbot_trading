"""Régressions de revue M-014 pour la projection locale KA."""

from __future__ import annotations

import hashlib
import inspect
from pathlib import Path

import pytest
from psycopg import OperationalError

from app.contracts.page_execution import GranitePageTerminalStatus
from app.contracts.technical_jobs import (
    JobEnvironmentIdentity,
    JobExecutionRequirements,
    JobIdempotenceKey,
    JobPriority,
    JobRequest,
)
from app.knowledge_access.adapters.postgres_projection_read import (
    KnowledgeProjectionVersionConflictError,
    PostgresKnowledgeProjectionRepository,
)
from app.knowledge_access.adapters.projection_runtime import (
    QdrantHttpClient,
    ProjectionRuntimeError,
    _canonical_items_payload,
    projection_failure_disposition,
)
from app.knowledge_access.adapters.qdrant_vector_index import QdrantVectorIndex
from app.knowledge_access.application.project_document_contract import (
    ProjectDocumentContract,
    ProjectDocumentContractError,
)
from app.knowledge_access.domain.knowledge_projection import BuildFingerprint
from app.knowledge_access.domain.projection_index import (
    VectorIndexPoint,
    VectorIndexPublishRequest,
    VectorIndexSchema,
)


IDENTITY = JobEnvironmentIdentity(
    environment="test",
    deployment_id="ostrading-test-local",
    configuration_hash="c" * 64,
)


def _contract_payload() -> dict[str, object]:
    return {
        "contract_version": "1.0",
        "projection_id": "PROJ-M014-REVIEW",
        "document_id": "DOC-M014-REVIEW",
        "canonical_version_id": "CVER-M014-REVIEW",
        "canonical_artifact_ref": (
            "artifact:source_processing.canonical_sources/"
            "CVER-M014-REVIEW/docling.json"
        ),
        "canonical_artifact_sha256": "a" * 64,
        "build_fingerprint": "b" * 64,
        "projection_profile": {
            "projection_profile_id": "local-hash-projection-v1",
            "chunking_profile": "hierarchical-pagewise-v1",
            "embedding_model": "hashing-dense-256-v1",
            "sparse_profile": "lexical-tf-v1",
            "index_schema": "qdrant-hybrid-v1",
        },
        "qdrant_collection_name": "ostrading-test-knowledge-access",
        "environment_identity": IDENTITY.to_mapping(),
        "causation_event_id": "EVT-M014-REVIEW",
    }


def _job_request(*, requirements: JobExecutionRequirements | None) -> JobRequest:
    return JobRequest(
        environment=IDENTITY.environment,
        deployment_id=IDENTITY.deployment_id,
        job_name="PROJECT_DOCUMENT",
        priority=JobPriority.P1,
        idempotence_key=JobIdempotenceKey(
            job_name="PROJECT_DOCUMENT",
            input_hash="b" * 64,
            configuration_hash=IDENTITY.configuration_hash,
            code_version="m014-local-projection-v1",
            model_version="hashing-dense-256-v1",
        ),
        execution_requirements=requirements,
        payload=_contract_payload(),
    )


def _contrat_project_document_reste_unique_et_strict() -> None:
    contract = ProjectDocumentContract.from_mapping(_contract_payload())
    assert contract.to_mapping() == _contract_payload()
    requirements = contract.execution_requirements()
    assert requirements == JobExecutionRequirements(
        contract_name="project-canonical-document",
        contract_version="1.0",
        capacity_capability="knowledge-projection",
        capacity_slots=0,
        capacity_device=None,
        storage_environment="test",
    )
    assert ProjectDocumentContract.from_job_request(
        _job_request(requirements=requirements)
    ) == contract
    with pytest.raises(
        ProjectDocumentContractError,
        match="PROJECTION_EXECUTION_REQUIREMENTS_REQUIRED",
    ):
        ProjectDocumentContract.from_job_request(_job_request(requirements=None))


def _pipeline_classe_les_reprises_sans_table_parallele() -> None:
    assert projection_failure_disposition(
        ProjectionRuntimeError("QDRANT_UNAVAILABLE")
    ) == "RETRY"
    assert projection_failure_disposition(
        ProjectionRuntimeError("PROJECTION_COLLECTION_MISMATCH")
    ) == "FAILED"
    assert projection_failure_disposition(
        KnowledgeProjectionVersionConflictError()
    ) == "RETRY"
    assert projection_failure_disposition(
        OperationalError("connexion PostgreSQL interrompue")
    ) == "RETRY"


class _ExistingCollectionClient(QdrantHttpClient):
    def __init__(self, response: dict[str, object]) -> None:
        super().__init__(
            base_url="http://qdrant.test",
            timeout_seconds=1,
            dense_dimensions=256,
            api_key="q" * 32,
        )
        self.response = response

    def _request(  # type: ignore[override]
        self,
        method: str,
        path: str,
        body: object,
        *,
        allow_not_found: bool = False,
    ) -> dict[str, object]:
        del method, path, body, allow_not_found
        return self.response


def _collection_qdrant_divergente_est_refusee() -> None:
    client = _ExistingCollectionClient(
        {
            "result": {
                "config": {
                    "params": {
                        "vectors": {"dense": {"size": 128, "distance": "Cosine"}},
                        "sparse_vectors": {"sparse": {}},
                    }
                }
            }
        }
    )
    with pytest.raises(ProjectionRuntimeError, match="PROJECTION_COLLECTION_MISMATCH"):
        client.ensure_collection(collection_name="ostrading-test-knowledge-access")


class _ExactGenerationClient:
    def __init__(self, points):
        self.points = list(points)
        self.delete_count = 0

    def count(self, *, collection_name, count_filter, exact):
        del collection_name, count_filter
        assert exact is True
        return len(self.points)

    def scroll(self, *, collection_name, scroll_filter):
        del collection_name, scroll_filter
        return tuple(self.points)

    def delete(self, *, collection_name, points_selector):
        del collection_name, points_selector
        self.delete_count += 1
        self.points = []

    def upsert(self, *, collection_name, points):
        del collection_name
        self.points.extend(points)


def _generation_qdrant_de_meme_taille_mais_etrangere_est_reparee() -> None:
    schema = VectorIndexSchema(
        schema_version="qdrant-m014-review-v1",
        collection_name="ostrading-test-knowledge-access",
        dense_dimensions=2,
        distance="cosine",
        payload_schema_version="payload-m014-review-v1",
    )
    point = VectorIndexPoint(
        point_id="KCHK-M014-REVIEW-0001",
        chunk_id="KCHK-M014-REVIEW-0001",
        content_hash="d" * 64,
        dense_vector=(0.1, 0.2),
        sparse_weights=(("preuve", 1.0),),
        payload={
            "chunk_id": "KCHK-M014-REVIEW-0001",
            "content_hash": "d" * 64,
        },
    )
    request = VectorIndexPublishRequest(
        collection_name=schema.collection_name,
        index_generation="IDX-M014-REVIEW-0001",
        schema=schema,
        build_fingerprint=BuildFingerprint("b" * 64),
        points=(point,),
        expected_point_count=1,
    )
    client = _ExactGenerationClient(
        (
            {
                "id": "00000000-0000-4000-8000-000000000001",
                "vector": {"dense": [9.0, 9.0], "sparse": {"indices": [1], "values": [9.0]}},
                "payload": {"index_generation": request.index_generation},
            },
        )
    )
    index = QdrantVectorIndex(client=client)
    publication = index.repair_generation(
        request,
        max_parallel_batches=1,
        batch_size=1,
        on_batch_published=lambda _completed: None,
        fence_mutation=lambda operation: operation(),
    )
    assert publication.idempotent is False
    assert client.delete_count == 1
    assert index.verify_generation(request) is True
    client.points[0]["payload"]["content_hash"] = "e" * 64
    assert index.verify_generation(request) is False
    assert client.delete_count == 1


def _claim_perdu_interdit_le_batch_qdrant_suivant() -> None:
    schema = VectorIndexSchema(
        schema_version="qdrant-m014-fencing-v1",
        collection_name="ostrading-test-knowledge-access",
        dense_dimensions=2,
        distance="cosine",
        payload_schema_version="payload-m014-fencing-v1",
    )
    point = VectorIndexPoint(
        point_id="KCHK-M014-FENCING-0001",
        chunk_id="KCHK-M014-FENCING-0001",
        content_hash="d" * 64,
        dense_vector=(0.1, 0.2),
        sparse_weights=(("preuve", 1.0),),
        payload={
            "chunk_id": "KCHK-M014-FENCING-0001",
            "content_hash": "d" * 64,
        },
    )
    request = VectorIndexPublishRequest(
        collection_name=schema.collection_name,
        index_generation="IDX-M014-FENCING-0001",
        schema=schema,
        build_fingerprint=BuildFingerprint("b" * 64),
        points=(point,),
        expected_point_count=1,
    )
    client = _ExactGenerationClient(
        (
            {
                "id": "00000000-0000-4000-8000-000000000001",
                "vector": {
                    "dense": [9.0, 9.0],
                    "sparse": {"indices": [1], "values": [9.0]},
                },
                "payload": {"index_generation": request.index_generation},
            },
        )
    )
    mutations = 0

    def fence(operation):
        nonlocal mutations
        mutations += 1
        if mutations == 2:
            raise KnowledgeProjectionVersionConflictError()
        return operation()

    with pytest.raises(KnowledgeProjectionVersionConflictError):
        QdrantVectorIndex(client=client).repair_generation(
            request,
            max_parallel_batches=1,
            batch_size=1,
            on_batch_published=lambda _completed: None,
            fence_mutation=fence,
        )

    assert client.delete_count == 1
    assert client.points == []


def _item_canonique_invalide_interdit_index_partiel() -> None:
    artifact_hash = hashlib.sha256(b"artefact").hexdigest()
    canonical_ref = type(
        "CanonicalRefStub",
        (),
        {
            "canonical_version_id": "CVER-M014-REVIEW",
            "canonical_artifact_sha256": artifact_hash,
        },
    )()
    artifact = {
        "canonical_version_id": "CVER-M014-REVIEW",
        "pages": [
            {
                "items": [
                    {"text": "Item valide", "provenance": {"item_id": "item-1"}},
                    {"text": "", "provenance": {"item_id": "item-2"}},
                ]
            }
        ],
    }
    with pytest.raises(ProjectionRuntimeError, match="CANONICAL_ARTIFACT_INVALID"):
        _canonical_items_payload(artifact=artifact, canonical_ref=canonical_ref)


def _contrats_persistants_nont_aucune_valeur_metier_implicite() -> None:
    index_parameter = inspect.signature(
        PostgresKnowledgeProjectionRepository.save_projection_outputs
    ).parameters["index_generation"]
    assert index_parameter.default is inspect.Parameter.empty
    assert "abandoned" not in {status.value for status in GranitePageTerminalStatus}


def _frontiere_ka_ne_lit_aucune_table_privee_sp() -> None:
    root = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "pyproject.toml").is_file()
    )
    relay = (
        root / "app/knowledge_access/adapters/postgres_canonical_publication_relay.py"
    ).read_text(encoding="utf-8")
    migration = (
        root / "deploy/postgres/migrations/027_local_projection_review_hardening.sql"
    )
    assert "source_processing.canonical_source_versions" not in relay
    assert migration.is_file()
    migration_text = migration.read_text(encoding="utf-8")
    assert "canonical_artifact_ref" in migration_text
    assert "ALTER COLUMN delivery_count DROP DEFAULT" in migration_text
    assert "VALIDATE CONSTRAINT knowledge_projections_generation_coherence" in migration_text
    assert "knowledge_projections_latest_publication_idx" in migration_text


def test_validate_projection_review_regressions_unit() -> None:
    _contrat_project_document_reste_unique_et_strict()
    _pipeline_classe_les_reprises_sans_table_parallele()
    _collection_qdrant_divergente_est_refusee()
    _generation_qdrant_de_meme_taille_mais_etrangere_est_reparee()
    _claim_perdu_interdit_le_batch_qdrant_suivant()
    _item_canonique_invalide_interdit_index_partiel()
    _contrats_persistants_nont_aucune_valeur_metier_implicite()
    _frontiere_ka_ne_lit_aucune_table_privee_sp()
