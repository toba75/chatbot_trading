from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.platform.orchestrator_api_models import IndexRequest, ProjectionCommandRequest


def test_given_the_legacy_index_contract_and_the_real_projection_command_when_their_payloads_are_validated_then_their_requirements_remain_separate() -> None:
    """Given-When-Then : la commande KA n'altère pas le contrat historique."""

    legacy_payload = IndexRequest.model_validate({})

    assert legacy_payload.model_dump(mode="json") == {}
    with pytest.raises(ValidationError):
        ProjectionCommandRequest.model_validate({})
    assert ProjectionCommandRequest.model_validate(
        {
            "projection_profile_id": "local-hash-projection-v1",
            "chunking_profile": "hierarchical-pagewise-v1",
            "embedding_model": "hashing-dense-256-v1",
            "sparse_profile": "lexical-tf-v1",
            "index_schema": "qdrant-hybrid-v1",
        }
    ).index_schema == "qdrant-hybrid-v1"
