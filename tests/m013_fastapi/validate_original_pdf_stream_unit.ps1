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
from tempfile import TemporaryDirectory

sys.path.insert(0, sys.argv[1])

from fastapi import FastAPI

from app.source_processing.adapters.original_http import build_original_pdf_router
from app.source_processing.adapters.postgres_document_persistence import CorpusOriginalSourceStore
from app.source_processing.application.document_commands import SourceNotFoundError
from app.source_processing.application.original_queries import OriginalPdfQueryService
from app.source_processing.domain.source_document import (
    BibliographicMetadata,
    DocumentId,
    OriginalStorageRef,
    SourceDocument,
    SourceFingerprint,
)


def assert_raises(exception_type, expected_message, callback):
    try:
        callback()
    except exception_type as exc:
        assert str(exc) == expected_message, (str(exc), expected_message)
        return exc
    raise AssertionError(f"Erreur attendue absente: {expected_message}")


class SourceRepository:
    def __init__(self, source_document):
        self.source_document = source_document
        self.requested_ids = []

    def find_by_document_id(self, document_id):
        self.requested_ids.append(document_id)
        if document_id == self.source_document.document_id:
            return self.source_document
        return None


async def invoke_router(router, path):
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

    await router(
        {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.4"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": b"",
            "root_path": "",
            "headers": [],
            "client": ("unit", 50001),
            "server": ("orchestrator-api", 8080),
        },
        receive,
        send,
    )
    start = next(message for message in sent if message["type"] == "http.response.start")
    body_messages = [
        message for message in sent if message["type"] == "http.response.body"
    ]
    headers = {
        key.decode("latin-1").lower(): value.decode("latin-1")
        for key, value in start["headers"]
    }
    return start, headers, body_messages


async def invoke_concurrently(router, path):
    return await asyncio.gather(
        invoke_router(router, path),
        invoke_router(router, path),
        invoke_router(router, path),
    )


pdf = b"%PDF-1.7\n" + (b"stream-controle\n" * 70000) + b"%%EOF\n"
assert len(pdf) > 1024 * 1024
fingerprint = SourceFingerprint.from_content(pdf)
document_id = DocumentId.from_fingerprint(fingerprint)

with TemporaryDirectory() as temporary_directory:
    corpus_root = Path(temporary_directory) / "corpus"
    store = CorpusOriginalSourceStore(corpus_root=corpus_root)
    storage_ref = store.put_original_if_absent(document_id, fingerprint, pdf)
    source_document = SourceDocument.register_original(
        document_id=document_id,
        fingerprint=fingerprint,
        original_storage_ref=store.storage_ref(storage_ref),
        metadata=BibliographicMetadata(
            title="Nom interne et chemin interdits.pdf",
            authors=("OSTrading",),
            publication_year=2026,
            edition="1",
        ),
    )
    repository = SourceRepository(source_document)
    service = OriginalPdfQueryService(
        source_document_repository=repository,
        original_source_reader=store,
    )

    original = service.read_original(document_id.value)
    assert original.source_sha256 == fingerprint.value
    assert original.content_length == len(pdf)
    assert original.public_filename == f"{document_id.value}.pdf"
    assert repository.requested_ids == [document_id]
    chunks = tuple(original.content_chunks)
    assert b"".join(chunks) == pdf
    assert len(chunks) > 1
    assert max(map(len, chunks)) <= 64 * 1024

    not_found = assert_raises(
        SourceNotFoundError,
        "source documentaire inconnue: DOC-FFFFFFFFFFFFFFFF",
        lambda: service.read_original("DOC-FFFFFFFFFFFFFFFF"),
    )
    assert not_found.document_id == "DOC-FFFFFFFFFFFFFFFF"

    application = FastAPI()
    application.include_router(build_original_pdf_router(original_pdf_queries=service))
    start, headers, body_messages = asyncio.run(
        invoke_router(application, f"/v1/documents/{document_id.value}/original")
    )
    assert start["status"] == 200
    assert headers["content-type"] == "application/pdf"
    assert headers["content-length"] == str(len(pdf))
    assert headers["content-disposition"] == f'inline; filename="{document_id.value}.pdf"'
    assert headers["etag"] == f'"{fingerprint.value}"'
    assert b"".join(message.get("body", b"") for message in body_messages) == pdf
    streamed_messages = [message for message in body_messages if message.get("body", b"")]
    assert len(streamed_messages) > 1
    assert max(len(message["body"]) for message in streamed_messages) <= 64 * 1024
    assert any(message.get("more_body") is True for message in body_messages)
    assert body_messages[-1].get("more_body") is False
    assert temporary_directory not in str(headers)
    assert source_document.metadata.title not in str(headers)

    concurrent = asyncio.run(
        invoke_concurrently(
            application,
            f"/v1/documents/{document_id.value}/original",
        )
    )
    for concurrent_start, _, concurrent_messages in concurrent:
        assert concurrent_start["status"] == 200
        assert b"".join(message.get("body", b"") for message in concurrent_messages) == pdf

    # Même si un objet typé est corrompu hors du domaine, l'adaptateur refuse toute sortie du corpus.
    forged_ref = OriginalStorageRef.from_value(storage_ref)
    object.__setattr__(
        forged_ref,
        "value",
        "artifact:source_processing.original_sources/../outside.pdf",
    )
    assert_raises(
        ValueError,
        "ORIGINAL_STORAGE_REF_OUTSIDE_CORPUS",
        lambda: store.resolve_internal_path(forged_ref),
    )

    # Une substitution d'octets sous la référence interne attendue échoue explicitement.
    original_path = store.resolve_internal_path(source_document.original_storage_ref)
    original_path.write_bytes(b"%PDF-1.7\nsubstitution-voisine\n%%EOF\n")
    assert_raises(
        ValueError,
        "ORIGINAL_HASH_MISMATCH",
        lambda: service.read_original(document_id.value),
    )
    mismatch_start, _, mismatch_messages = asyncio.run(
        invoke_router(application, f"/v1/documents/{document_id.value}/original")
    )
    mismatch_body = b"".join(
        message.get("body", b"") for message in mismatch_messages
    )
    assert mismatch_start["status"] == 409
    assert json.loads(mismatch_body.decode("utf-8")) == {
        "error_code": "ORIGINAL_HASH_MISMATCH",
        "document_id": document_id.value,
    }

    persistence_source = (
        Path(sys.argv[1])
        / "app/source_processing/adapters/postgres_document_persistence.py"
    ).read_text(encoding="utf-8")
    assert "read_bytes()" not in persistence_source

print("Tests unitaires du streaming PDF original contrôlé: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_original_pdf_stream_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Validation unitaire T-008: OK"
