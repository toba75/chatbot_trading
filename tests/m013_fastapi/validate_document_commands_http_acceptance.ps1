$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
from __future__ import annotations

import asyncio
from dataclasses import replace
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, sys.argv[1])

from app.platform.configuration import load_application_configuration
from app.platform.orchestrator_asgi import create_orchestrator_app
from app.platform.orchestrator_composition import DependencyReadiness, OrchestratorCompositionRoot
from app.source_processing.adapters.document_http import SourceProcessingHttpAdapter
from app.source_processing.adapters.http import build_document_command_router
from app.source_processing.application.document_commands import (
    DiagnosisAlreadyRequestedError,
    DocumentDiagnosisAcceptance,
    RegisterDocumentAcceptance,
    SourceNotFoundError,
    SourceUnreadableError,
)
from app.source_processing.domain.source_document import DocumentId, SourceFingerprint


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Attendu={expected!r}, obtenu={actual!r}")


def multipart(*, boundary, content, fields, content_type="application/pdf"):
    chunks = [
        f"--{boundary}\r\n".encode("ascii"),
        b'Content-Disposition: form-data; name="original_content"; filename="interdit-comme-titre.pdf"\r\n',
        f"Content-Type: {content_type}\r\n\r\n".encode("ascii"),
        content,
        b"\r\n",
    ]
    for name, value in fields:
        chunks.extend(
            (
                f"--{boundary}\r\n".encode("ascii"),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("ascii"),
                str(value).encode("utf-8"),
                b"\r\n",
            )
        )
    chunks.append(f"--{boundary}--\r\n".encode("ascii"))
    return b"".join(chunks)


async def post(application, path, body, content_type, token):
    sent = []
    delivered = False

    async def receive():
        nonlocal delivered
        if delivered:
            return {"type": "http.disconnect"}
        delivered = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        sent.append(message)

    await application(
        {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": b"",
            "root_path": "",
            "headers": [
                (b"content-type", content_type.encode("ascii")),
                (b"content-length", str(len(body)).encode("ascii")),
                (b"authorization", f"Bearer {token}".encode("ascii")),
            ],
            "client": ("asgi-test", 50000),
            "server": ("orchestrator-api", 8080),
            "state": {},
        },
        receive,
        send,
    )
    start = next(message for message in sent if message["type"] == "http.response.start")
    raw = b"".join(message.get("body", b"") for message in sent if message["type"] == "http.response.body")
    return start["status"], json.loads(raw.decode("utf-8"))


class ContractCommands:
    def __init__(self):
        self.registered = {}
        self.diagnosed = set()

    def register_source_document(self, *, original_content, bibliographic_metadata):
        if original_content == b"%PDF-corrompu\n%%EOF\n":
            raise SourceUnreadableError("PDF_CORRUPTED")
        fingerprint = SourceFingerprint.from_content(original_content)
        document_id = DocumentId.from_fingerprint(fingerprint)
        if fingerprint.value in self.registered:
            return RegisterDocumentAcceptance(document_id, "DUPLICATE_SOURCE", True)
        self.registered[fingerprint.value] = (document_id, dict(bibliographic_metadata))
        return RegisterDocumentAcceptance(document_id, "REGISTERED", False)

    def register_source_document_path(self, *, original_path, bibliographic_metadata):
        return self.register_source_document(
            original_content=original_path.read_bytes(),
            bibliographic_metadata=bibliographic_metadata,
        )

    def start_document_processing(self, *, document_id):
        known_ids = {entry[0].value for entry in self.registered.values()}
        if document_id not in known_ids:
            raise SourceNotFoundError(document_id)
        if document_id in self.diagnosed:
            raise DiagnosisAlreadyRequestedError(document_id)
        self.diagnosed.add(document_id)
        return DocumentDiagnosisAcceptance(DocumentId.from_value(document_id), "DIAGNOSTIC_REQUESTED")


class ReadyDependency:
    async def open(self):
        return None

    async def close(self):
        return None

    def readiness(self):
        return DependencyReadiness(name="document-contract", status="ready")


async def scenario(repo_root):
    configuration = load_application_configuration(repo_root / "config" / "application.example.yaml", {})
    token = "m013-fastapi-acceptance-token-00000001"
    token_directory = TemporaryDirectory(prefix="ost-m013-auth-")
    token_path = Path(token_directory.name) / "local_api_token"
    token_path.write_text(token, encoding="ascii")
    configuration = replace(
        configuration,
        security=replace(
            configuration.security,
            secrets=replace(
                configuration.security.secrets,
                local_api_token_path=str(token_path),
            ),
        ),
    )
    commands = ContractCommands()
    adapter = SourceProcessingHttpAdapter(commands)

    def root_factory(validated_configuration):
        return OrchestratorCompositionRoot(
            configuration=validated_configuration,
            dependencies=(ReadyDependency(),),
            document_command_router=build_document_command_router(
                document_http_adapter=adapter,
                max_pdf_bytes=1024 * 1024,
            ),
        )

    application = create_orchestrator_app(configuration=configuration, composition_root_factory=root_factory)
    fields = (
        ("title", "Rapport annuel explicite"),
        ("authors", "Auteur A"),
        ("authors", "Auteur B"),
        ("publication_year", "2026"),
        ("edition", "1"),
    )
    pdf = b"%PDF-1.7\n1 0 obj<<>>endobj\n%%EOF\n"
    boundary = "ost-multipart-acceptance"
    body = multipart(boundary=boundary, content=pdf, fields=fields)
    content_type = f"multipart/form-data; boundary={boundary}"

    async with application.router.lifespan_context(application):
        created = await post(application, "/v1/documents", body, content_type, token)
        assert_equal(created[0], 201, "Le multipart valide doit créer la source.")
        document_id = created[1]["document_id"]
        assert_equal(set(created[1]), {"document_id", "document_status"}, "Aucun identifiant interne ne doit sortir.")
        metadata = next(iter(commands.registered.values()))[1]
        assert_equal(metadata["title"], "Rapport annuel explicite", "Le titre doit venir du formulaire explicite.")
        assert_equal(metadata["authors"], ("Auteur A", "Auteur B"), "Les auteurs explicites doivent être conservés.")

        duplicate = await post(application, "/v1/documents", body, content_type, token)
        assert_equal(
            duplicate,
            (200, {"document_id": document_id, "document_status": "DUPLICATE_SOURCE", "duplicate": True}),
            "Le doublon binaire doit rester explicite.",
        )

        corrupt_body = multipart(
            boundary=boundary,
            content=b"%PDF-corrompu\n%%EOF\n",
            fields=fields,
        )
        assert_equal(
            await post(application, "/v1/documents", corrupt_body, content_type, token),
            (422, {"error_code": "SOURCE_UNREADABLE", "reason": "PDF_CORRUPTED"}),
            "Une source illisible doit conserver l'erreur M-003.",
        )

        missing_fields = tuple(field for field in fields if field[0] != "title")
        missing_body = multipart(boundary=boundary, content=pdf, fields=missing_fields)
        assert_equal(
            await post(application, "/v1/documents", missing_body, content_type, token),
            (400, {"error_code": "HTTP_REQUEST_INVALID", "field": "title"}),
            "Une métadonnée obligatoire absente doit être refusée avant SP.",
        )

        assert_equal(
            await post(application, f"/v1/documents/{document_id}/diagnose", b"", "application/octet-stream", token),
            (202, {"document_id": document_id, "diagnostic_status": "DIAGNOSTIC_REQUESTED"}),
            "La demande DIAGNOSE doit être acceptée une seule fois.",
        )
        assert_equal(
            await post(application, f"/v1/documents/{document_id}/diagnose", b"", "application/octet-stream", token),
            (409, {"error_code": "DIAGNOSTIC_ALREADY_REQUESTED", "document_id": document_id}),
            "La répétition doit produire l'erreur publique idempotente.",
        )
        absent = "DOC-" + "F" * 16
        assert_equal(
            await post(application, f"/v1/documents/{absent}/diagnose", b"", "application/octet-stream", token),
            (404, {"error_code": "SOURCE_NOT_FOUND", "document_id": absent}),
            "Une source absente doit rester 404.",
        )
    token_directory.cleanup()


asyncio.run(scenario(Path(sys.argv[1])))
print("Test d'acceptation HTTP des commandes documentaires ASGI: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_document_http_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation HTTP des commandes documentaires ASGI: OK"
