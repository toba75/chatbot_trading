$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, sys.argv[1])

from app.platform.configuration import load_application_configuration
from app.platform.orchestrator_asgi import create_orchestrator_app
from app.platform.orchestrator_composition import DependencyReadiness, OrchestratorCompositionRoot
from app.source_processing.adapters.original_http import build_original_pdf_router
from app.source_processing.adapters.postgres_document_persistence import CorpusOriginalSourceStore
from app.source_processing.application.original_queries import OriginalPdfQueryService
from app.source_processing.domain.source_document import (
    BibliographicMetadata,
    DocumentId,
    SourceDocument,
    SourceFingerprint,
)


class SourceRepository:
    def __init__(self, source_document):
        self.source_document = source_document

    def find_by_document_id(self, document_id):
        if self.source_document.document_id == document_id:
            return self.source_document
        return None


class ReadyDependency:
    async def open(self):
        return None

    async def close(self):
        return None

    def readiness(self):
        return DependencyReadiness(name="original-pdf", status="ready")


async def get(application, path):
    sent = []
    delivered = False

    async def receive():
        nonlocal delivered
        if delivered:
            return {"type": "http.disconnect"}
        delivered = True
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    await application(
        {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": b"",
            "root_path": "",
            "headers": [],
            "client": ("asgi-test", 50000),
            "server": ("orchestrator-api", 8080),
            "state": {},
        },
        receive,
        send,
    )
    start = next(message for message in sent if message["type"] == "http.response.start")
    headers = {
        key.decode("latin-1").lower(): value.decode("latin-1")
        for key, value in start["headers"]
    }
    body = b"".join(
        message.get("body", b"")
        for message in sent
        if message["type"] == "http.response.body"
    )
    return start["status"], headers, body


async def scenario(repo_root):
    pdf = b"%PDF-1.7\noriginal-m13-fastapi-bit-a-bit\n%%EOF\n"
    fingerprint = SourceFingerprint.from_content(pdf)
    document_id = DocumentId.from_fingerprint(fingerprint)

    with TemporaryDirectory() as temporary_directory:
        corpus_root = Path(temporary_directory) / "corpus"
        original_store = CorpusOriginalSourceStore(corpus_root=corpus_root)
        storage_ref = original_store.put_original_if_absent(
            document_id,
            fingerprint,
            pdf,
        )
        source_document = SourceDocument.register_original(
            document_id=document_id,
            fingerprint=fingerprint,
            original_storage_ref=original_store.storage_ref(storage_ref),
            metadata=BibliographicMetadata(
                title="Original contrôlé",
                authors=("OSTrading",),
                publication_year=2026,
                edition="1",
            ),
        )
        original_queries = OriginalPdfQueryService(
            source_document_repository=SourceRepository(source_document),
            original_source_reader=original_store,
        )
        configuration = load_application_configuration(
            repo_root / "config" / "application.example.yaml",
            {},
        )

        def root_factory(validated_configuration):
            return OrchestratorCompositionRoot(
                configuration=validated_configuration,
                dependencies=(ReadyDependency(),),
                document_command_router=build_original_pdf_router(
                    original_pdf_queries=original_queries
                ),
            )

        application = create_orchestrator_app(
            configuration=configuration,
            composition_root_factory=root_factory,
        )
        async with application.router.lifespan_context(application):
            status, headers, body = await get(
                application,
                f"/v1/documents/{document_id.value}/original",
            )
            assert status == 200
            assert body == pdf
            assert hashlib.sha256(body).hexdigest() == fingerprint.value
            assert headers["content-type"] == "application/pdf"
            assert headers["content-length"] == str(len(pdf))
            assert headers["etag"] == f'"{fingerprint.value}"'
            assert headers["content-disposition"] == (
                f'inline; filename="{document_id.value}.pdf"'
            )
            serialized_headers = json.dumps(headers)
            assert temporary_directory not in serialized_headers
            assert "artifact:source_processing" not in serialized_headers

            missing_status, _, missing_body = await get(
                application,
                "/v1/documents/DOC-FFFFFFFFFFFFFFFF/original",
            )
            missing = json.loads(missing_body.decode("utf-8"))
            assert (missing_status, missing) == (
                404,
                {
                    "error_code": "SOURCE_NOT_FOUND",
                    "document_id": "DOC-FFFFFFFFFFFFFFFF",
                },
            )

            invalid_status, _, invalid_body = await get(
                application,
                "/v1/documents/not-a-document-id/original",
            )
            invalid = json.loads(invalid_body.decode("utf-8"))
            assert (invalid_status, invalid) == (
                400,
                {"error_code": "HTTP_REQUEST_INVALID", "field": "document_id"},
            )


asyncio.run(scenario(Path(sys.argv[1])))
print("Test d'acceptation de récupération du PDF original: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_original_pdf_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

if ($exitCode -ne 0) {
    throw ($output -join "`n")
}

Write-Host "Validation d'acceptation T-008: OK"
