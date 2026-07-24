"""ATDD T-008 : publication canonique vers projection locale idempotente."""

import pytest

from app.contracts.technical_jobs import JobEnvironmentIdentity
from app.knowledge_access.adapters.projection_runtime import LOCAL_PROJECTION_PROFILE
from app.knowledge_access.application.project_published_canonical import (
    ProjectionPublicationError,
    PublishedCanonicalProjectionRequest,
)
from validate_local_projection_unit import IDENTITY, _message


def test_given_publication_relivree_when_ka_la_consomme_then_un_job_deterministe() -> None:
    first = PublishedCanonicalProjectionRequest.from_message(
        message=_message(),
        projection_profile=LOCAL_PROJECTION_PROFILE,
        configured_identity=IDENTITY,
        configured_collection_name="ostrading-test-knowledge-access",
        code_version="m014-local-projection-v1",
    )
    replay = PublishedCanonicalProjectionRequest.from_message(
        message=_message(),
        projection_profile=LOCAL_PROJECTION_PROFILE,
        configured_identity=IDENTITY,
        configured_collection_name="ostrading-test-knowledge-access",
        code_version="m014-local-projection-v1",
    )

    assert replay == first
    assert first.job_request.job_name == "PROJECT_DOCUMENT"
    assert first.job_request.idempotence_key.input_hash == (
        first.projection.build_fingerprint.value
    )

    foreign = JobEnvironmentIdentity(
        environment="production",
        deployment_id="ostrading-production-local",
        configuration_hash="d" * 64,
    )
    with pytest.raises(
        ProjectionPublicationError,
        match="PROJECTION_ENVIRONMENT_MISMATCH",
    ):
        PublishedCanonicalProjectionRequest.from_message(
            message=_message(identity=foreign),
            projection_profile=LOCAL_PROJECTION_PROFILE,
            configured_identity=IDENTITY,
            configured_collection_name="ostrading-test-knowledge-access",
            code_version="m014-local-projection-v1",
        )
