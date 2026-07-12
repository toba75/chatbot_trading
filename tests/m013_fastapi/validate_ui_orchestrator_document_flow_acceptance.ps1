$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
from __future__ import annotations

import hashlib
from pathlib import Path
import socket
import sys
from threading import Thread
import time

import uvicorn

sys.path.insert(0, sys.argv[1])

from app.knowledge_access.adapters.http import build_projection_query_router
from app.knowledge_access.application.projection_queries import ProjectionNotRequestedView
from app.platform.configuration import load_application_configuration
from app.platform.orchestrator_asgi import create_orchestrator_app
from app.platform.orchestrator_composition import DependencyReadiness, OrchestratorCompositionRoot
from app.platform.ui_corpus import render_document_inspection
from app.platform.ui_document_api import UiDocumentApiClient, UrllibUiDocumentApiTransport
from app.platform.orchestrator_runtime import (
    OrchestratorDocumentCorpusItem,
    OrchestratorDocumentCorpusPage,
)
from app.source_processing.adapters.document_http import SourceProcessingHttpAdapter
from app.source_processing.adapters.http import build_document_command_router
from app.source_processing.adapters.original_http import build_original_pdf_router
from app.source_processing.adapters.query_http import build_document_query_router
from app.source_processing.application.document_commands import (
    DocumentDiagnosisAcceptance,
    RegisterDocumentAcceptance,
)
from app.source_processing.application.document_queries import (
    DiagnosticPageView,
    DocumentConversionView,
    DocumentDiagnosticView,
    PageManifestEntryView,
)
from app.source_processing.application.original_queries import OriginalPdfContent
from app.source_processing.domain.source_document import DocumentId, SourceFingerprint
from fastapi import APIRouter


PDF = b"%PDF-1.7\n1 0 obj<<>>endobj\n%%EOF\n"


def multipart(boundary):
    fields = (
        ("title", "Rapport API réelle"),
        ("authors", "Auteur"),
        ("publication_year", "2026"),
        ("edition", "1"),
    )
    chunks = [
        f"--{boundary}\r\n".encode(),
        b'Content-Disposition: form-data; name="original_content"; filename="rapport.pdf"\r\n',
        b"Content-Type: application/pdf\r\n\r\n",
        PDF,
        b"\r\n",
    ]
    for name, value in fields:
        chunks.extend((
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
            value.encode("utf-8"),
            b"\r\n",
        ))
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks)


class ProductPorts:
    def __init__(self):
        self.document_id = None
        self.title = None
        self.diagnosed = False

    def register_source_document(self, *, original_content, bibliographic_metadata):
        assert original_content == PDF
        fingerprint = SourceFingerprint.from_content(original_content)
        self.document_id = DocumentId.from_fingerprint(fingerprint)
        self.title = bibliographic_metadata["title"]
        return RegisterDocumentAcceptance(self.document_id, "REGISTERED", False)

    def start_document_processing(self, *, document_id):
        assert self.document_id is not None and document_id == self.document_id.value
        self.diagnosed = True
        return DocumentDiagnosisAcceptance(self.document_id, "DIAGNOSTIC_REQUESTED")

    def list_documents(self, *, limit, cursor):
        assert limit == 100 and cursor is None
        assert self.document_id is not None and self.title is not None
        return OrchestratorDocumentCorpusPage(documents=(OrchestratorDocumentCorpusItem(
            document_id=self.document_id.value,
            title=self.title,
            document_status="REGISTERED",
            diagnostic_status="MANIFEST_CREATED" if self.diagnosed else "DIAGNOSTIC_NOT_REQUESTED",
            conversion_status="QA_REJECTED",
            canonical_version_id=None,
            projection_status="SEARCHABLE",
        ),), next_cursor=None)

    def read_diagnostic(self, document_id):
        assert self.document_id is not None and document_id == self.document_id.value
        return DocumentDiagnosticView(
            document_id=document_id,
            diagnostic_status="MANIFEST_CREATED",
            source_page_count=1,
            diagnosed_page_count=0,
            manual_review_reason=None,
            manifest=(PageManifestEntryView(page_number=1, manifest_status="PRESENT"),),
            pages=(DiagnosticPageView(
                page_number=1,
                manifest_status="PRESENT",
                diagnostic=None,
                route=None,
            ),),
        )

    def read_conversion(self, document_id):
        assert self.document_id is not None and document_id == self.document_id.value
        return DocumentConversionView(
            document_id=document_id,
            conversion_status="QA_REJECTED",
            qa_rejection_error_code="PAGE_AUTHORITY_MISSING",
            canonical_version_id=None,
        )

    def read_projection(self, document_id):
        assert self.document_id is not None and document_id == self.document_id.value
        return ProjectionNotRequestedView(
            document_id=document_id,
            projection_status="PROJECTION_NOT_REQUESTED",
        )

    def read_original(self, document_id):
        assert self.document_id is not None and document_id == self.document_id.value
        chunks = iter((PDF,))
        return OriginalPdfContent(
            document_id=document_id,
            source_sha256=hashlib.sha256(PDF).hexdigest(),
            content_length=len(PDF),
            content_chunks=chunks,
            close=lambda: None,
        )


class ReadyDependency:
    async def open(self): return None
    async def close(self): return None
    def readiness(self): return DependencyReadiness(name="ui-real-fastapi", status="ready")


configuration = load_application_configuration(
    Path(sys.argv[1]) / "config" / "application.example.yaml",
    {},
)
ports = ProductPorts()
router = APIRouter()
router.include_router(build_document_command_router(
    document_http_adapter=SourceProcessingHttpAdapter(ports),
    max_pdf_bytes=1024 * 1024,
))
router.include_router(build_document_query_router(document_queries=ports))
router.include_router(build_projection_query_router(projection_queries=ports))
router.include_router(build_original_pdf_router(original_pdf_queries=ports))


def root_factory(validated_configuration):
    return OrchestratorCompositionRoot(
        configuration=validated_configuration,
        dependencies=(ReadyDependency(),),
        document_command_router=router,
    )


application = create_orchestrator_app(
    configuration=configuration,
    composition_root_factory=root_factory,
)
with socket.socket() as probe:
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
server = uvicorn.Server(uvicorn.Config(
    application,
    host="127.0.0.1",
    port=port,
    log_level="critical",
    lifespan="on",
))
thread = Thread(target=server.run, daemon=True)
thread.start()
deadline = time.monotonic() + 10
while not server.started and time.monotonic() < deadline:
    time.sleep(0.01)
if not server.started:
    raise AssertionError("Uvicorn réel non démarré")

try:
    client = UiDocumentApiClient(transport=UrllibUiDocumentApiTransport(
        orchestrator_origin=f"http://127.0.0.1:{port}",
        timeout_seconds=5,
    ))
    boundary = "ost-ui-real-fastapi"
    registration = client.forward_document_command(
        path="/v1/documents",
        body=multipart(boundary),
        content_type=f"multipart/form-data; boundary={boundary}",
    )
    assert registration.status_code == 201
    document_id = registration.payload["document_id"]
    diagnosis = client.forward_document_command(
        path=f"/v1/documents/{document_id}/diagnose",
        body=b"",
        content_type="application/octet-stream",
    )
    assert diagnosis.status_code == 202
    state = client.build_corpus_state(active_selected_document_ids=())
    assert state.documents[0].source_status == "REGISTERED"
    assert state.documents[0].diagnostic_status == "MANIFEST_CREATED"
    diagnostic = client.read_diagnostic(document_id)
    assert "Page 1" in render_document_inspection(title="Diagnostic", response=diagnostic)
    conversion = client.read_conversion(document_id)
    assert conversion.payload["conversion_status"] == "QA_REJECTED"
    projection = client.read_projection(document_id)
    assert projection.payload["projection_status"] == "PROJECTION_NOT_REQUESTED"
    original = client.read_original_pdf(document_id)
    assert original.body == PDF
finally:
    server.should_exit = True
    thread.join(timeout=10)
    if thread.is_alive():
        raise AssertionError("Uvicorn réel non arrêté")

print("Test d'acceptation UI vers application FastAPI réelle: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_ui_real_fastapi_" + [guid]::NewGuid().ToString("N") + ".py")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    $env:PYTHONIOENCODING = "utf-8"
    $output = & $pythonExecutable -B $pythonScriptPath $repoRoot 2>&1
    $exitCode = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
if ($exitCode -ne 0) { throw ($output -join "`n") }
Write-Host ($output -join "`n")
