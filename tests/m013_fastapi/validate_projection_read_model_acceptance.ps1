$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
from __future__ import annotations

import asyncio
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, sys.argv[1])

from app.contracts.source_references import SourceLocator
from app.knowledge_access.adapters.http import build_projection_query_router
from app.knowledge_access.application.projection_queries import (
    ProjectionQueryService,
    ProjectionReadRecord,
)
from app.knowledge_access.domain.chunking import KnowledgeChunk
from app.knowledge_access.domain.knowledge_projection import (
    BuildFingerprint,
    KnowledgeProjection,
    ProjectionProfile,
    ProjectionStatus,
)
from app.platform.configuration import load_application_configuration
from app.platform.orchestrator_asgi import create_orchestrator_app
from app.platform.orchestrator_composition import (
    DependencyReadiness,
    OrchestratorCompositionRoot,
)


class ProjectionReadRepository:
    def __init__(self, records):
        self.records = {
            record.projection.document_id: record for record in records
        }
        self.calls = []

    def current_projection_for_document_id(self, document_id, sample_limit):
        self.calls.append((document_id, sample_limit))
        record = self.records.get(document_id)
        if record is None:
            return None
        return replace(record, chunk_samples=record.chunk_samples[:sample_limit])


class ReadyDependency:
    async def open(self):
        return None

    async def close(self):
        return None

    def readiness(self):
        return DependencyReadiness(name="projection-read-model", status="ready")


def projection(document_id, status):
    suffix = document_id.removeprefix("DOC-")
    return KnowledgeProjection(
        projection_id=f"PROJ-{suffix}",
        document_id=document_id,
        canonical_version_id=f"CVER-{suffix}",
        projection_profile=ProjectionProfile(
            projection_profile_id="projection-publique-v1",
            chunking_profile="hierarchical-v1",
            embedding_model="dense-public-v1",
            sparse_profile="sparse-public-v1",
            index_schema="hybrid-public-v1",
        ),
        build_fingerprint=BuildFingerprint(hashlib.sha256(document_id.encode()).hexdigest()),
        status=status,
    )


def chunk(projection_value, number):
    item_text = f"item-{projection_value.document_id}-{number}"
    item_hash = hashlib.sha256(item_text.encode()).hexdigest()
    locator = SourceLocator(
        schema_version="1.0",
        canonical_version_id=projection_value.canonical_version_id,
        document_id=projection_value.document_id,
        page_pdf=number,
        item_id=f"item-{number}",
        bbox=(0.0, 0.0, 100.0, 20.0),
        content_hash=item_hash,
    )
    return KnowledgeChunk.parent(
        chunk_id=f"KCHK-{hashlib.sha256(item_text.encode()).hexdigest()[:32].upper()}",
        canonical_version_id=projection_value.canonical_version_id,
        document_id=projection_value.document_id,
        profile_id="hierarchical",
        profile_version="1",
        text=f"Extrait public numéro {number} pour {projection_value.document_id}.",
        source_locators=(locator,),
    )


def record(document_id, status, chunk_count):
    projection_value = projection(document_id, status)
    chunks = tuple(chunk(projection_value, number) for number in range(1, chunk_count + 1))
    return ProjectionReadRecord(
        projection=projection_value,
        chunk_count=chunk_count,
        chunk_samples=chunks,
        state_observed_at="2026-07-12T10:00:00Z",
    )


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
            "asgi": {"version": "3.0", "spec_version": "2.4"},
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
    raw = b"".join(
        message.get("body", b"")
        for message in sent
        if message["type"] == "http.response.body"
    )
    return start["status"], json.loads(raw.decode("utf-8"))


def assert_no_technical_storage(payload):
    forbidden = {
        "qdrant_collection",
        "collection_name",
        "point_id",
        "qdrant_point_id",
    }
    if isinstance(payload, dict):
        leaked = forbidden.intersection(payload)
        if leaked:
            raise AssertionError(f"Stockage technique exposé: {sorted(leaked)}")
        for value in payload.values():
            assert_no_technical_storage(value)
    elif isinstance(payload, list):
        for value in payload:
            assert_no_technical_storage(value)


async def scenario(repo_root):
    build = record("DOC-M013-T009-BUILD", ProjectionStatus.BUILDING, 0)
    searchable = record("DOC-M013-T009-SEARCHABLE", ProjectionStatus.SEARCHABLE, 4)
    stale = record("DOC-M013-T009-STALE", ProjectionStatus.STALE, 1)
    failed = record("DOC-M013-T009-FAILED", ProjectionStatus.FAILED, 0)
    repository = ProjectionReadRepository((build, searchable, stale, failed))
    service = ProjectionQueryService(
        projection_read_repository=repository,
        chunk_sample_limit=2,
        text_preview_character_limit=80,
        source_locator_limit=2,
    )
    configuration = load_application_configuration(
        repo_root / "config" / "application.example.yaml",
        {},
    )

    def root_factory(validated_configuration):
        return OrchestratorCompositionRoot(
            configuration=validated_configuration,
            dependencies=(ReadyDependency(),),
            document_command_router=build_projection_query_router(
                projection_queries=service
            ),
        )

    application = create_orchestrator_app(
        configuration=configuration,
        composition_root_factory=root_factory,
    )
    async with application.router.lifespan_context(application):
        absent_status, absent = await get(
            application,
            "/v1/documents/DOC-M013-T009-ABSENT/projection",
        )
        assert (absent_status, absent) == (
            200,
            {
                "document_id": "DOC-M013-T009-ABSENT",
                "projection_status": "PROJECTION_NOT_REQUESTED",
            },
        )

        build_status, build_payload = await get(
            application,
            f"/v1/documents/{build.projection.document_id}/projection",
        )
        assert build_status == 200
        assert build_payload["projection_status"] == "BUILDING"
        assert build_payload["freshness"]["status"] == "PENDING"
        assert build_payload["chunk_count"] == 0

        searchable_status, searchable_payload = await get(
            application,
            f"/v1/documents/{searchable.projection.document_id}/projection",
        )
        assert searchable_status == 200
        assert searchable_payload["projection_status"] == "SEARCHABLE"
        assert searchable_payload["freshness"] == {
            "status": "CURRENT",
            "observed_at": "2026-07-12T10:00:00Z",
        }
        assert searchable_payload["canonical_version_id"] == "CVER-M013-T009-SEARCHABLE"
        assert searchable_payload["chunk_count"] == 4
        assert len(searchable_payload["chunk_samples"]) == 2
        assert searchable_payload["chunk_samples"][0]["source_locators"][0]["page_pdf"] == 1
        assert "chunk_id" not in searchable_payload["chunk_samples"][0]

        stale_status, stale_payload = await get(
            application,
            f"/v1/documents/{stale.projection.document_id}/projection",
        )
        assert stale_status == 200
        assert stale_payload["projection_status"] == "STALE"
        assert stale_payload["freshness"]["status"] == "STALE"

        failed_status, failed_payload = await get(
            application,
            f"/v1/documents/{failed.projection.document_id}/projection",
        )
        assert failed_status == 200
        assert failed_payload["projection_status"] == "FAILED"
        assert failed_payload["freshness"]["status"] == "UNAVAILABLE"

        invalid_status, invalid = await get(
            application,
            "/v1/documents/not-a-document/projection",
        )
        assert (invalid_status, invalid) == (
            400,
            {"error_code": "HTTP_REQUEST_INVALID", "field": "document_id"},
        )

        for payload in (absent, build_payload, searchable_payload, stale_payload, failed_payload):
            assert_no_technical_storage(payload)

    assert all(sample_limit == 2 for _, sample_limit in repository.calls)


asyncio.run(scenario(Path(sys.argv[1])))
print("Test d'acceptation du read-model de projection KA: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_projection_read_model_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Validation d'acceptation T-009: OK"
