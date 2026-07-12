$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, sys.argv[1])

from fastapi import FastAPI
from app.platform.orchestrator_asgi import BoundedRequestBodyMiddleware
from app.source_processing.adapters.http import build_document_command_router
from app.source_processing.adapters.document_http import SourceProcessingHttpAdapter
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
        b'Content-Disposition: form-data; name="original_content"; filename="metadata-interdite.pdf"\r\n',
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


async def post(
    application,
    path,
    body,
    content_type,
    *,
    include_content_length=True,
    receive_chunk_bytes=None,
    receive_calls=None,
):
    sent = []
    offset = 0
    delivered_empty = False

    async def receive():
        nonlocal delivered_empty, offset
        if receive_calls is not None:
            receive_calls.append(offset)
        if len(body) == 0 and not delivered_empty:
            delivered_empty = True
            return {"type": "http.request", "body": b"", "more_body": False}
        if offset >= len(body):
            return {"type": "http.disconnect"}
        chunk_size = receive_chunk_bytes or len(body)
        chunk = body[offset : offset + chunk_size]
        offset += len(chunk)
        return {
            "type": "http.request",
            "body": chunk,
            "more_body": offset < len(body),
        }

    async def send(message):
        sent.append(message)

    headers = [(b"content-type", content_type.encode("ascii"))]
    if include_content_length:
        headers.append((b"content-length", str(len(body)).encode("ascii")))
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
            "headers": headers,
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


class RouterCommands:
    def __init__(self):
        self.registration_calls = []

    def register_source_document(self, *, original_content, bibliographic_metadata):
        self.registration_calls.append((original_content, dict(bibliographic_metadata)))
        if original_content.endswith(b"corrupt\n%%EOF\n"):
            raise SourceUnreadableError("PDF_CORRUPTED")
        document_id = DocumentId.from_fingerprint(SourceFingerprint.from_content(original_content))
        return RegisterDocumentAcceptance(document_id, "REGISTERED", False)

    def start_document_processing(self, *, document_id):
        if document_id == "DOC-" + "A" * 16:
            raise SourceNotFoundError(document_id)
        if document_id == "DOC-" + "B" * 16:
            raise DiagnosisAlreadyRequestedError(document_id)
        return DocumentDiagnosisAcceptance(DocumentId.from_value(document_id), "DIAGNOSTIC_REQUESTED")


async def scenario():
    commands = RouterCommands()
    adapter = SourceProcessingHttpAdapter(commands)
    application = FastAPI()
    application.add_middleware(
        BoundedRequestBodyMiddleware,
        max_body_bytes=4096,
    )
    application.include_router(
        build_document_command_router(
            document_http_adapter=adapter,
            max_pdf_bytes=64,
        )
    )
    boundary = "ost-router-unit"
    fields = (
        ("title", "Titre explicite"),
        ("authors", "Auteur"),
        ("publication_year", "2026"),
        ("edition", "1"),
    )
    valid_pdf = b"%PDF-1.7\nbody\n%%EOF\n"
    valid_body = multipart(boundary=boundary, content=valid_pdf, fields=fields)
    multipart_type = f"multipart/form-data; boundary={boundary}"

    created = await post(application, "/v1/documents", valid_body, multipart_type)
    assert_equal(created[0], 201, "Le routeur doit déléguer le multipart valide.")
    assert_equal(len(commands.registration_calls), 1, "SP doit être appelé exactement une fois.")
    delegated_content, delegated_metadata = commands.registration_calls[0]
    assert_equal(delegated_content, valid_pdf, "Le PDF doit rester bit à bit.")
    assert_equal(
        delegated_metadata,
        {"title": "Titre explicite", "authors": ("Auteur",), "publication_year": 2026, "edition": "1"},
        "Les champs bibliographiques doivent être typés explicitement.",
    )
    if "filename" in repr(delegated_metadata) or "metadata-interdite.pdf" in repr(delegated_metadata):
        raise AssertionError("Le nom du fichier ne doit jamais devenir une métadonnée bibliographique.")

    wrong_mime = multipart(
        boundary=boundary,
        content=valid_pdf,
        fields=fields,
        content_type="application/octet-stream",
    )
    assert_equal(
        await post(application, "/v1/documents", wrong_mime, multipart_type),
        (400, {"error_code": "HTTP_REQUEST_INVALID", "field": "original_content"}),
        "Un type MIME non PDF doit être refusé avant SP.",
    )

    oversized_pdf = b"%PDF-1.7\n" + b"x" * 64 + b"\n%%EOF\n"
    oversized = multipart(boundary=boundary, content=oversized_pdf, fields=fields)
    assert_equal(
        await post(application, "/v1/documents", oversized, multipart_type),
        (400, {"error_code": "HTTP_REQUEST_INVALID", "field": "original_content"}),
        "La limite binaire explicite doit être appliquée avant SP.",
    )

    for field_name in ("title", "authors", "publication_year", "edition"):
        body = multipart(
            boundary=boundary,
            content=valid_pdf,
            fields=tuple(field for field in fields if field[0] != field_name),
        )
        assert_equal(
            await post(application, "/v1/documents", body, multipart_type),
            (400, {"error_code": "HTTP_REQUEST_INVALID", "field": field_name}),
            f"Le champ {field_name} doit être obligatoire.",
        )

    invalid_year = multipart(
        boundary=boundary,
        content=valid_pdf,
        fields=tuple((name, "20x6" if name == "publication_year" else value) for name, value in fields),
    )
    assert_equal(
        await post(application, "/v1/documents", invalid_year, multipart_type),
        (400, {"error_code": "HTTP_REQUEST_INVALID", "field": "publication_year"}),
        "L'année bibliographique doit être un entier explicite.",
    )

    oversized_metadata = (
        ("title", "T" * 513),
        ("authors", "Auteur"),
        ("publication_year", "2026"),
        ("edition", "1"),
    )
    assert_equal(
        await post(
            application,
            "/v1/documents",
            multipart(boundary=boundary, content=valid_pdf, fields=oversized_metadata),
            multipart_type,
        ),
        (400, {"error_code": "HTTP_REQUEST_INVALID", "field": "title"}),
        "Un titre de plus de 512 caractères doit être refusé.",
    )
    for field_name, fields_override in (
        (
            "authors",
            (
                ("title", "Titre"),
                ("authors", "A" * 257),
                ("publication_year", "2026"),
                ("edition", "1"),
            ),
        ),
        (
            "authors",
            (
                ("title", "Titre"),
                *(("authors", f"Auteur {index}") for index in range(17)),
                ("publication_year", "2026"),
                ("edition", "1"),
            ),
        ),
        (
            "publication_year",
            (
                ("title", "Titre"),
                ("authors", "Auteur"),
                ("publication_year", "10000"),
                ("edition", "1"),
            ),
        ),
        (
            "edition",
            (
                ("title", "Titre"),
                ("authors", "Auteur"),
                ("publication_year", "2026"),
                ("edition", "E" * 65),
            ),
        ),
    ):
        assert_equal(
            await post(
                application,
                "/v1/documents",
                multipart(boundary=boundary, content=valid_pdf, fields=fields_override),
                multipart_type,
            ),
            (400, {"error_code": "HTTP_REQUEST_INVALID", "field": field_name}),
            f"La limite métier de {field_name} doit être appliquée.",
        )

    aggregate_oversized_pdf = b"%PDF-1.7\n" + b"x" * 5000 + b"\n%%EOF\n"
    aggregate_oversized = multipart(
        boundary=boundary,
        content=aggregate_oversized_pdf,
        fields=fields,
    )
    content_length_receive_calls = []
    assert_equal(
        await post(
            application,
            "/v1/documents",
            aggregate_oversized,
            multipart_type,
            receive_calls=content_length_receive_calls,
        ),
        (413, {"error_code": "HTTP_REQUEST_TOO_LARGE", "max_body_bytes": 4096}),
        "Un Content-Length excessif doit être refusé par la frontière ASGI.",
    )
    assert_equal(
        content_length_receive_calls,
        [],
        "Un Content-Length excessif doit être refusé avant toute consommation.",
    )
    assert_equal(
        await post(
            application,
            "/v1/documents",
            aggregate_oversized,
            multipart_type,
            include_content_length=False,
            receive_chunk_bytes=128,
        ),
        (413, {"error_code": "HTTP_REQUEST_TOO_LARGE", "max_body_bytes": 4096}),
        "Un transfert chunked excessif doit être borné avant le parsing multipart.",
    )

    corrupt = multipart(
        boundary=boundary,
        content=b"%PDF-corrupt\n%%EOF\n",
        fields=fields,
    )
    assert_equal(
        await post(application, "/v1/documents", corrupt, multipart_type),
        (422, {"error_code": "SOURCE_UNREADABLE", "reason": "PDF_CORRUPTED"}),
        "L'erreur SP SOURCE_UNREADABLE doit rester publique.",
    )

    assert_equal(
        await post(application, "/v1/documents/id-invalide/diagnose", b"", "application/octet-stream"),
        (400, {"error_code": "HTTP_REQUEST_INVALID", "field": "document_id"}),
        "Un DocumentId invalide doit rester une erreur M-003.",
    )
    absent = "DOC-" + "A" * 16
    assert_equal(
        await post(application, f"/v1/documents/{absent}/diagnose", b"", "application/octet-stream"),
        (404, {"error_code": "SOURCE_NOT_FOUND", "document_id": absent}),
        "SOURCE_NOT_FOUND doit rester 404.",
    )
    repeated = "DOC-" + "B" * 16
    assert_equal(
        await post(application, f"/v1/documents/{repeated}/diagnose", b"", "application/octet-stream"),
        (409, {"error_code": "DIAGNOSTIC_ALREADY_REQUESTED", "document_id": repeated}),
        "DIAGNOSTIC_ALREADY_REQUESTED doit rester 409.",
    )
    unknown = await post(application, "/v1/document-fallback", b"", "application/octet-stream")
    assert_equal(unknown[0], 404, "Aucune route de secours ne doit exister.")
    assert_equal(len(commands.registration_calls), 2, "Seuls le PDF valide et le PDF corrompu doivent atteindre SP.")


asyncio.run(scenario())
print("Tests unitaires du routeur de commandes documentaires: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_document_router_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

$routerSource = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $repoRoot "app/source_processing/adapters/http.py")
foreach ($forbidden in @("logger.debug(original_content", "logger.info(original_content", "except Exception", "Depends(")) {
    if ($routerSource.Contains($forbidden)) {
        throw "Garde-fou routeur violé: $forbidden"
    }
}

Write-Host "Tests unitaires du routeur de commandes documentaires: OK"
