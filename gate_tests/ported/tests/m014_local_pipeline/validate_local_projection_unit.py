"""Tests unitaires T-008 du contrat de projection locale."""

from __future__ import annotations

from app.contracts.event_envelope import EventEnvelope
from app.contracts.technical_jobs import JobEnvironmentIdentity
from app.knowledge_access.adapters.projection_runtime import LOCAL_PROJECTION_PROFILE
from app.knowledge_access.application.project_published_canonical import (
    CanonicalPublicationMessage,
    ProjectionPublicationError,
    PublishedCanonicalProjectionRequest,
    canonical_publication_fingerprint,
)


IDENTITY = JobEnvironmentIdentity(
    environment="test",
    deployment_id="ostrading-test-local",
    configuration_hash="c" * 64,
)


def _event(*, event_id: str = "EVT-M014-PROJECTION-0001", artifact_hash: str = "b" * 64) -> EventEnvelope:
    return EventEnvelope.from_payload(
        {
            "event_id": event_id,
            "event_type": "CanonicalSourcePublished",
            "event_version": 1,
            "occurred_at": "2026-07-24T10:00:00Z",
            "aggregate_type": "CanonicalSource",
            "aggregate_id": "CSRC-M014-PROJECTION",
            "aggregate_version": 1,
            "correlation_id": "CORR-M014-PROJECTION",
            "causation_id": "CMD-M014-PROJECTION",
            "producer_context": "SP",
            "payload": {
                "schema_version": "1.0",
                "canonical_source_id": "CSRC-M014-PROJECTION",
                "document_id": "DOC-M014-PROJECTION",
                "canonical_version_id": "CVER-M014-PROJECTION-0001",
                "source_sha256": "a" * 64,
                "canonical_artifact_sha256": artifact_hash,
                "page_count": 2,
                "accepted_at": "2026-07-24T10:00:00Z",
                "quality_policy_version": "canonical-quality-m004-v1",
            },
        }
    )


def _message(*, identity: JobEnvironmentIdentity = IDENTITY) -> CanonicalPublicationMessage:
    event = _event()
    artifact_ref = "artifact:source_processing.canonical_sources/CVER-M014-PROJECTION-0001/docling.json"
    return CanonicalPublicationMessage(
        event=event,
        canonical_artifact_ref=artifact_ref,
        environment_identity=identity,
        event_fingerprint=canonical_publication_fingerprint(
            event=event,
            canonical_artifact_ref=artifact_ref,
            environment_identity=identity,
        ),
    )


def test_empreinte_build_et_contrat_job_sont_deterministes() -> None:
    first = PublishedCanonicalProjectionRequest.from_message(
        message=_message(),
        projection_profile=LOCAL_PROJECTION_PROFILE,
        configured_identity=IDENTITY,
        configured_collection_name="ostrading-test-knowledge-access",
        code_version="m014-local-projection-v1",
    )
    second = PublishedCanonicalProjectionRequest.from_message(
        message=_message(),
        projection_profile=LOCAL_PROJECTION_PROFILE,
        configured_identity=IDENTITY,
        configured_collection_name="ostrading-test-knowledge-access",
        code_version="m014-local-projection-v1",
    )
    assert first == second
    assert first.projection.build_fingerprint.value == first.job_request.idempotence_key.input_hash
    assert first.job_request.job_name == "PROJECT_DOCUMENT"
    assert first.job_request.payload["environment_identity"] == IDENTITY.to_mapping()
    assert first.job_request.payload["qdrant_collection_name"] == "ostrading-test-knowledge-access"
    assert first.job_request.payload["canonical_artifact_ref"].endswith("/docling.json")


def test_identite_etrangere_et_hash_divergent_sont_refuses() -> None:
    foreign = JobEnvironmentIdentity(
        environment="production",
        deployment_id="ostrading-production-local",
        configuration_hash="d" * 64,
    )
    try:
        PublishedCanonicalProjectionRequest.from_message(
            message=_message(identity=foreign),
            projection_profile=LOCAL_PROJECTION_PROFILE,
            configured_identity=IDENTITY,
            configured_collection_name="ostrading-test-knowledge-access",
            code_version="m014-local-projection-v1",
        )
    except ProjectionPublicationError as error:
        assert str(error) == "PROJECTION_ENVIRONMENT_MISMATCH"
    else:
        raise AssertionError("Une publication étrangère doit être refusée")

    event = _event()
    try:
        CanonicalPublicationMessage(
            event=event,
            canonical_artifact_ref="artifact:source_processing.canonical_sources/CVER-M014-PROJECTION-0001/docling.json",
            environment_identity=IDENTITY,
            event_fingerprint="0" * 64,
        )
    except ProjectionPublicationError as error:
        assert str(error) == "PROJECTION_EVENT_FINGERPRINT_MISMATCH"
    else:
        raise AssertionError("Une empreinte divergente doit être refusée")
