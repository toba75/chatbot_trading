"""Régressions finales de reprise, fencing et compatibilité M-014."""

from __future__ import annotations

import inspect
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from app.contracts.technical_jobs import (
    JobEnvironmentIdentity,
    JobExecutionRequirements,
    JobIdempotenceKey,
    JobPriority,
    JobRequest,
)
from app.knowledge_access.adapters.projection_runtime import (
    ProjectionRuntimeError,
    ProjectionRuntimeService,
)
from app.knowledge_access.application.project_document_contract import (
    ProjectDocumentContract,
)
from app.source_processing.adapters.local_page_artifacts import LocalPageArtifactStore
from app.source_processing.application.execute_document_page import (
    ExecuteDocumentPageHandler,
)
from app.source_processing.domain.distribution_contracts import (
    ArtifactContractError,
    LocalArtifactIdentity,
)


IDENTITY = JobEnvironmentIdentity(
    environment="test",
    deployment_id="ostrading-test-local",
    configuration_hash="c" * 64,
)


class _ForbiddenConnectionFactory:
    def connect(self):
        raise AssertionError("un job invalide ne doit muter aucune projection")


class _InferenceGateway:
    def infer(self, request):
        raise AssertionError(request)


def _invalid_projection_request() -> JobRequest:
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
        execution_requirements=JobExecutionRequirements(
            contract_name="project-canonical-document",
            contract_version="1.0",
            capacity_capability="knowledge-projection",
            capacity_slots=0,
            capacity_device=None,
            storage_environment="test",
        ),
        payload={
            # Identifiant légitime, mais contrat volontairement incomplet.
            "projection_id": "PROJ-M014-REVIEW",
        },
    )


def _artefact_remplace_de_meme_taille_est_refuse_a_la_consommation() -> None:
    with TemporaryDirectory(prefix="ostrading-m014-revalidation-") as temporary:
        root = Path(temporary).resolve()
        source = root / "source.pdf"
        source.write_bytes(b"contenu-A")
        identity = LocalArtifactIdentity(
            environment="test",
            artifact_ref="artifact:source_processing.local/test/source.pdf",
            relative_path="source.pdf",
        )
        store = LocalPageArtifactStore(profile_root=root)
        descriptor = store.materialize_verified_source(
            source_path=source,
            identity=identity,
            sha256="03ecdd753bfbd423e8f3db3830107755b8bf465bcd31b078f7d6d282a827c364",
        )
        path = store.resolve_verified_path(descriptor)
        previous_stat = path.stat()
        replacement = root / "replacement.pdf"
        replacement.write_bytes(b"contenu-B")
        os.replace(replacement, path)
        os.utime(path, ns=(previous_stat.st_atime_ns, previous_stat.st_mtime_ns))

        with pytest.raises(ArtifactContractError, match="ARTIFACT_HASH_MISMATCH"):
            store.resolve_verified_path(descriptor)


def _contrats_de_production_nont_aucun_defaut_implicite() -> None:
    project_version = inspect.signature(ProjectDocumentContract).parameters[
        "contract_version"
    ]
    locked_assets = inspect.signature(ExecuteDocumentPageHandler).parameters[
        "expected_locked_assets"
    ]
    assert project_version.default is inspect.Parameter.empty
    assert locked_assets.default is inspect.Parameter.empty


def _job_projection_invalide_ne_touche_pas_un_agregat_homonyme() -> None:
    runtime = ProjectionRuntimeService(
        connection_factory=_ForbiddenConnectionFactory(),
        canonical_sources_root=Path.cwd(),
        environment=IDENTITY.environment,
        deployment_id=IDENTITY.deployment_id,
        configuration_hash=IDENTITY.configuration_hash,
        qdrant_url="http://qdrant.test",
        qdrant_collection_name="ostrading-test-knowledge-access",
        qdrant_timeout_seconds=1,
        qdrant_api_key="q" * 32,
        max_parallel_workers=1,
        inference_gateway=_InferenceGateway(),
    )

    with pytest.raises(ProjectionRuntimeError, match="PROJECTION_JOB_PAYLOAD_INVALID"):
        runtime.execute_projection(request=_invalid_projection_request())


def _migrations_finales_restent_locales_et_revoquent_les_claims() -> None:
    root = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "pyproject.toml").is_file()
    )
    migration_027 = (
        root / "deploy/postgres/migrations/027_local_projection_review_hardening.sql"
    ).read_text(encoding="utf-8")
    migration_028 = (
        root / "deploy/postgres/migrations/028_m014_local_pipeline_compatibility.sql"
    ).read_text(encoding="utf-8")
    migration_029_path = (
        root / "deploy/postgres/migrations/029_m014_expand_contract_replay.sql"
    )
    assert "NOT EXISTS (\n       SELECT 1\n         FROM knowledge_access" not in migration_027
    assert "relay_generation = relay_generation + 1" in migration_028
    assert migration_029_path.is_file()
    migration_029 = migration_029_path.read_text(encoding="utf-8")
    for marker in (
        "m004-inline-v1",
        "contract_version",
        "knowledge_access.job_outbox",
        "platform.technical_jobs",
        "canonical_source_versions",
        "canonical_publication_outbox",
        "SEARCHABLE",
        "relay_generation",
    ):
        assert marker in migration_029


def test_reprise_et_compatibilite_finales() -> None:
    _artefact_remplace_de_meme_taille_est_refuse_a_la_consommation()
    _contrats_de_production_nont_aucun_defaut_implicite()
    _job_projection_invalide_ne_touche_pas_un_agregat_homonyme()
    _migrations_finales_restent_locales_et_revoquent_les_claims()
