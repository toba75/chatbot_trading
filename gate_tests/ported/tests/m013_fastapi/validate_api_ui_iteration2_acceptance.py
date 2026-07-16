"""Acceptation API/KA/UI de l'itération 2 et du read-model ADR-038."""

from __future__ import annotations

import json
from pathlib import Path

from app.platform.orchestrator_api_models import (
    DocumentCorpusResponse,
    DocumentDiagnosticResponse,
    ProjectionResponse,
)
from app.platform.ui_document_api import (
    UI_DOCUMENT_PAGE_SIZE,
    UiDocumentApiClient,
    UiDocumentApiResponse,
)


class RecordingTransport:
    def __init__(self, responses: list[UiDocumentApiResponse]) -> None:
        self.responses = responses
        self.paths: list[str] = []

    def request(self, *, method, path, body, content_type):
        del method, body, content_type
        self.paths.append(path)
        return self.responses.pop(0)


def _response(payload: dict[str, object]) -> UiDocumentApiResponse:
    return UiDocumentApiResponse(
        status_code=200,
        content_type="application/json",
        body=json.dumps(payload).encode("utf-8"),
    )


def _pending_item(number: int) -> dict[str, object]:
    return {
        "document_id": f"DOC-M013-PAGE-{number:04d}",
        "title": None,
        "authors": None,
        "publication_year": None,
        "edition": None,
        "metadata_status": "PENDING",
        "document_status": "REGISTERED",
        "diagnostic_status": "DIAGNOSTIC_NOT_REQUESTED",
        "conversion_status": "CONVERSION_NOT_REQUESTED",
        "canonical_version_id": None,
        "projection_status": "PROJECTION_NOT_REQUESTED",
        "manual_review_reason": None,
        "failure_error_code": None,
        "conversion_action_available": False,
        "projection_action_available": False,
    }


def test_validate_api_ui_iteration2_acceptance() -> None:
    first = [_pending_item(number) for number in range(1, UI_DOCUMENT_PAGE_SIZE + 1)]
    transport = RecordingTransport(
        [_response({"documents": first, "next_cursor": first[-1]["document_id"]})]
    )
    state = UiDocumentApiClient(transport=transport).build_corpus_state(
        active_selected_document_ids=()
    )
    assert len(state.documents) == UI_DOCUMENT_PAGE_SIZE
    assert state.next_cursor == first[-1]["document_id"]
    assert transport.paths == [f"/v1/documents?limit={UI_DOCUMENT_PAGE_SIZE}"]
    assert not any(path.endswith("/projection") for path in transport.paths)

    for model in (DocumentCorpusResponse, DocumentDiagnosticResponse, ProjectionResponse):
        schema_text = json.dumps(model.model_json_schema(), sort_keys=True)
        assert 'additionalProperties\\": true' not in schema_text
        assert "typing.Any" not in schema_text
    projection_schema = ProjectionResponse.model_json_schema()
    serialized_projection_schema = json.dumps(projection_schema)
    assert "oneOf" in serialized_projection_schema or "anyOf" in serialized_projection_schema

    repository_root = next(
        parent for parent in Path(__file__).resolve().parents if (parent / "pyproject.toml").is_file()
    )
    query_router = (repository_root / "app/source_processing/adapters/query_http.py").read_text(
        encoding="utf-8"
    )
    projection_router = (
        repository_root / "app/knowledge_access/adapters/http.py"
    ).read_text(encoding="utf-8")
    assert "run_in_threadpool" in query_router
    assert "run_in_threadpool" in projection_router
    assert "Query(" in query_router and "next_cursor" in query_router

    public_services = (
        repository_root / "app/platform/orchestrator_public_services.py"
    ).read_text(encoding="utf-8")
    assert "from app.platform import local_runtime" not in public_services
    assert "local_runtime." not in public_services
    assert (repository_root / "app/conversation/application/public_chat.py").is_file()
    assert (repository_root / "app/evaluation/application/llm_real_path.py").is_file()

    local_runtime = (repository_root / "app/platform/local_runtime.py").read_text(
        encoding="utf-8"
    )
    for dead_definition in (
        "def product_chat_completions_post_response(",
        "def llm_real_path_benchmark_post_response(",
        "def search_post_response(",
        "def index_post_response(",
    ):
        assert dead_definition not in local_runtime
    assert "app.platform.application.public_contract_use_cases" not in local_runtime
    assert "def _legacy_" not in local_runtime

    asgi_source = (repository_root / "app/platform/orchestrator_asgi.py").read_text(
        encoding="utf-8"
    )
    assert "SpooledTemporaryFile" not in asgi_source
    assert "BoundedReceive" in asgi_source
