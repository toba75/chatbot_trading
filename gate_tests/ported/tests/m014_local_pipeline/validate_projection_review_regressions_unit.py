"""Régressions de revue M-014 pour la projection locale KA."""

from __future__ import annotations

import hashlib
import inspect
from pathlib import Path

import pytest

from app.contracts.page_execution import GranitePageTerminalStatus
from app.contracts.technical_jobs import (
    JobEnvironmentIdentity,
    JobExecutionRequirements,
    JobIdempotenceKey,
    JobPriority,
    JobRequest,
)
from app.knowledge_access.adapters.postgres_projection_read import (
    PostgresKnowledgeProjectionRepository,
)
from app.knowledge_access.adapters.projection_runtime import (
    QdrantHttpClient,
    ProjectionRuntimeError,
    _canonical_items_payload,
    projection_failure_disposition,
    projection_resume_stages,
)
from app.knowledge_access.application.project_document_contract import (
    ProjectDocumentContract,
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


def test_given_contrat_project_document_when_relay_et_worker_then_meme_dto_strict() -> None:
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
    with pytest.raises(ProjectionRuntimeError, match="PROJECTION_EXECUTION_REQUIREMENTS_REQUIRED"):
        ProjectDocumentContract.from_job_request(_job_request(requirements=None))


def test_given_etat_intermediaire_when_job_repris_then_pipeline_converge() -> None:
    assert projection_resume_stages("REQUESTED") == ("BUILD", "INDEX", "FINALIZE")
    assert projection_resume_stages("BUILDING") == ("BUILD", "INDEX", "FINALIZE")
    assert projection_resume_stages("BUILT") == ("INDEX", "FINALIZE")
    assert projection_resume_stages("INDEXING") == ("INDEX", "FINALIZE")
    assert projection_resume_stages("SEARCHABLE") == ("VERIFY",)
    assert projection_failure_disposition(
        ProjectionRuntimeError("QDRANT_UNAVAILABLE")
    ) == "RETRY"
    assert projection_failure_disposition(
        ProjectionRuntimeError("PROJECTION_COLLECTION_MISMATCH")
    ) == "FAILED"


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


def test_given_collection_qdrant_existante_when_schema_diverge_then_aucun_upsert() -> None:
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


def test_given_item_canonique_invalide_when_projection_then_pas_index_partiel() -> None:
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


def test_given_contrats_persistants_when_signatures_then_aucune_valeur_metier_implicite() -> None:
    index_parameter = inspect.signature(
        PostgresKnowledgeProjectionRepository.save_projection_outputs
    ).parameters["index_generation"]
    assert index_parameter.default is inspect.Parameter.empty
    assert "abandoned" not in {status.value for status in GranitePageTerminalStatus}


def test_given_frontiere_ka_when_code_revu_then_aucune_table_privee_sp() -> None:
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
