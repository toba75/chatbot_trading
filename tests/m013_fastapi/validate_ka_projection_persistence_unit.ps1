$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import inspect
from pathlib import Path
import sys

sys.path.insert(0, sys.argv[1])

from app.contracts.source_references import SourceLocator
from app.knowledge_access.adapters.postgres_projection_read import (
    PostgresKnowledgeProjectionRepository,
    PostgresProjectionReadRepository,
)
from app.knowledge_access.domain.chunking import KnowledgeChunk
from app.knowledge_access.domain.knowledge_projection import (
    BuildFingerprint,
    KnowledgeProjection,
    ProjectionProfile,
    ProjectionStatus,
)


class Cursor:
    def __init__(self, projection_row, sample_rows):
        self.projection_row = projection_row
        self.sample_rows = sample_rows
        self.calls = []
        self.current = None

    def __enter__(self): return self
    def __exit__(self, *args): return False
    def execute(self, sql, parameters=()):
        self.calls.append((" ".join(sql.split()), parameters))
        if "SELECT projection_id" in sql:
            self.current = "projection"
        elif "SELECT chunk_level" in sql:
            self.current = "samples"
    def fetchone(self):
        return self.projection_row if self.current == "projection" else None
    def fetchall(self):
        return self.sample_rows if self.current == "samples" else []


class Connection:
    def __init__(self, cursor): self._cursor = cursor
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def cursor(self): return self._cursor
    def transaction(self): return self


class Factory:
    def __init__(self, cursors): self.cursors = list(cursors)
    def connect(self): return Connection(self.cursors.pop(0))


document_id = "DOC-M013-KA-PERSIST"
canonical_version_id = "CVER-M013-KA-PERSIST"
profile = ProjectionProfile(
    projection_profile_id="projection-publique-v1",
    chunking_profile="hierarchical-v1",
    embedding_model="dense-v1",
    sparse_profile="sparse-v1",
    index_schema="hybrid-v1",
)
projection = KnowledgeProjection(
    projection_id="PROJ-M013-KA-PERSIST",
    document_id=document_id,
    canonical_version_id=canonical_version_id,
    projection_profile=profile,
    build_fingerprint=BuildFingerprint(hashlib.sha256(document_id.encode()).hexdigest()),
    status=ProjectionStatus.BUILDING,
)


def chunk(number):
    text = f"Extrait persistant {number}"
    locator = SourceLocator(
        schema_version="1.0",
        canonical_version_id=canonical_version_id,
        document_id=document_id,
        page_pdf=number,
        item_id=f"item-{number}",
        bbox=(0.0, 0.0, 10.0, 10.0),
        content_hash=hashlib.sha256(f"item-{number}".encode()).hexdigest(),
    )
    return KnowledgeChunk.parent(
        chunk_id=f"KCHK-{hashlib.sha256(text.encode()).hexdigest()[:32].upper()}",
        canonical_version_id=canonical_version_id,
        document_id=document_id,
        profile_id="hierarchical",
        profile_version="1",
        text=text,
        source_locators=(locator,),
    )


writer_cursor = Cursor(None, [])
writer = PostgresKnowledgeProjectionRepository(
    connection_factory=Factory([writer_cursor]),
    sample_storage_limit=3,
)
for method_name in (
    "save_if_absent",
    "require_absent_build_fingerprint",
    "projection_for_build_fingerprint",
    "projection_for_id",
    "save_transition",
    "save_projection_outputs",
):
    assert callable(getattr(writer, method_name, None)), f"Port KA absent: {method_name}"
assert tuple(inspect.signature(writer.save_transition).parameters) == ("projection",)
writer.save_projection_outputs(
    projection=projection,
    chunk_count=3,
    chunks=(chunk(1), chunk(2), chunk(3)),
    state_observed_at="2026-07-12T10:00:00Z",
)
assert any("knowledge_projection_chunk_samples" in sql for sql, _ in writer_cursor.calls)

projection_row = (
    projection.projection_id,
    document_id,
    canonical_version_id,
    profile.projection_profile_id,
    profile.chunking_profile,
    profile.embedding_model,
    profile.sparse_profile,
    profile.index_schema,
    projection.build_fingerprint.value,
    "BUILDING",
    3,
    datetime(2026, 7, 12, 10, tzinfo=timezone.utc),
)
sample_rows = [
    (
        sample.chunk_level,
        sample.text,
        sample.content_hash,
        [
            {
                "schema_version": locator.schema_version,
                "canonical_version_id": locator.canonical_version_id,
                "document_id": locator.document_id,
                "page_pdf": locator.page_pdf,
                "item_id": locator.item_id,
                "bbox": list(locator.bbox),
                "content_hash": locator.content_hash,
            }
            for locator in sample.source_locators
        ],
        sample.chunk_id,
        sample.parent_chunk_id,
        sample.profile_id,
        sample.profile_version,
    )
    for sample in (chunk(1), chunk(2))
]
reader_cursor = Cursor(projection_row, sample_rows)
reader = PostgresProjectionReadRepository(connection_factory=Factory([reader_cursor]))
record = reader.current_projection_for_document_id(document_id, sample_limit=2)
assert record is not None
assert record.chunk_count == 3
assert len(record.chunk_samples) == 2
assert record.chunk_samples[0].source_locators[0].page_pdf == 1
sample_query = next(call for call in reader_cursor.calls if "SELECT chunk_level" in call[0])
assert sample_query[1][-1] == 2, sample_query

migration = Path(sys.argv[1]) / "deploy" / "postgres" / "migrations" / "004_knowledge_projection_chunk_samples.sql"
assert migration.is_file(), "Migration KA 004 absente"
print("Validation unitaire de persistance KA: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_ka_projection_persistence_" + [guid]::NewGuid().ToString("N") + ".py")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
try {
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $env:PYTHONIOENCODING = "utf-8"
    $output = & $pythonExecutable -B $pythonScriptPath $repoRoot 2>&1
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousErrorActionPreference
    if ($exitCode -ne 0) { throw ($output -join "`n") }
    Write-Host ($output -join "`n")
}
finally {
    $ErrorActionPreference = "Stop"
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
