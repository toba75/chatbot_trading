$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
from __future__ import annotations

import inspect
import json
from pathlib import Path
import sys

sys.path.insert(0, sys.argv[1])

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


def response(payload: dict, status: int = 200) -> UiDocumentApiResponse:
    return UiDocumentApiResponse(
        status_code=status,
        content_type="application/json",
        body=json.dumps(payload).encode("utf-8"),
    )


class RecordingTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.paths = []

    def request(self, *, method, path, body, content_type):
        del method, body, content_type
        self.paths.append(path)
        return self.responses.pop(0)


def item(number: int) -> dict:
    return {
        "document_id": f"DOC-M013-PAGE-{number:04d}",
        "title": f"Rapport {number}",
        "document_status": "REGISTERED",
        "diagnostic_status": "DIAGNOSTIC_NOT_REQUESTED",
        "conversion_status": "CONVERSION_NOT_REQUESTED",
        "canonical_version_id": None,
        "projection_status": "PROJECTION_NOT_REQUESTED",
    }


# Given plus d'une page de documents publics existe.
# When l'UI construit le corpus.
# Then elle suit le curseur borné et n'effectue aucun appel de projection 1+N.
first = [item(number) for number in range(1, UI_DOCUMENT_PAGE_SIZE + 1)]
second = [item(UI_DOCUMENT_PAGE_SIZE + 1)]
transport = RecordingTransport(
    [
        response({"documents": first, "next_cursor": first[-1]["document_id"]}),
        response({"documents": second, "next_cursor": None}),
    ]
)
state = UiDocumentApiClient(transport=transport).build_corpus_state(
    active_selected_document_ids=()
)
assert len(state.documents) == UI_DOCUMENT_PAGE_SIZE
assert state.next_cursor == first[-1]["document_id"]
assert transport.paths == [
    f"/v1/documents?limit={UI_DOCUMENT_PAGE_SIZE}",
]
assert not any(path.endswith("/projection") for path in transport.paths)

# Les modèles OpenAPI doivent typer les structures imbriquées et l'union projection.
for model in (DocumentCorpusResponse, DocumentDiagnosticResponse, ProjectionResponse):
    schema_text = json.dumps(model.model_json_schema(), sort_keys=True)
    assert "additionalProperties\": true" not in schema_text, model.__name__
    assert "typing.Any" not in schema_text, model.__name__
projection_schema = ProjectionResponse.model_json_schema()
assert "oneOf" in json.dumps(projection_schema) or "anyOf" in json.dumps(projection_schema)

repo_root = Path(sys.argv[1])
query_router = (repo_root / "app/source_processing/adapters/query_http.py").read_text(encoding="utf-8")
projection_router = (repo_root / "app/knowledge_access/adapters/http.py").read_text(encoding="utf-8")
assert "run_in_threadpool" in query_router
assert "run_in_threadpool" in projection_router
assert "Query(" in query_router and "next_cursor" in query_router

public_services = (repo_root / "app/platform/orchestrator_public_services.py").read_text(encoding="utf-8")
assert "from app.platform import local_runtime" not in public_services
assert "local_runtime." not in public_services
assert (repo_root / "app/conversation/application/public_chat.py").is_file()
assert (repo_root / "app/evaluation/application/llm_real_path.py").is_file()
local_runtime = (repo_root / "app/platform/local_runtime.py").read_text(encoding="utf-8")
for dead_definition in (
    "def product_chat_completions_post_response(",
    "def llm_real_path_benchmark_post_response(",
    "def search_post_response(",
    "def index_post_response(",
):
    assert dead_definition not in local_runtime
assert "app.platform.application.public_contract_use_cases" not in local_runtime
assert "def _legacy_" not in local_runtime

asgi_source = (repo_root / "app/platform/orchestrator_asgi.py").read_text(encoding="utf-8")
assert "SpooledTemporaryFile" not in asgi_source
assert "BoundedReceive" in asgi_source

print("Acceptation revue itération 2 API/KA/UI: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_api_ui_iter2_" + [Guid]::NewGuid().ToString("N") + ".py")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
try {
    $env:PYTHONIOENCODING = "utf-8"
    $output = & $pythonExecutable -B $pythonScriptPath $repoRoot 2>&1
    $exitCode = $LASTEXITCODE
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force -ErrorAction SilentlyContinue
}
if ($exitCode -ne 0) { throw ($output -join "`n") }
Write-Host ($output -join "`n")
