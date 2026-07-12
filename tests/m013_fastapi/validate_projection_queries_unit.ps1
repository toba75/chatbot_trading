$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import hashlib
import sys

sys.path.insert(0, sys.argv[1])

from app.contracts.source_references import SourceLocator
from app.knowledge_access.application.projection_queries import (
    ProjectionNotRequestedView,
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


class ProjectionReadRepository:
    def __init__(self, record):
        self.record = record
        self.calls = []

    def current_projection_for_document_id(self, document_id, sample_limit):
        self.calls.append((document_id, sample_limit))
        if self.record is None or self.record.projection.document_id != document_id:
            return None
        return replace(
            self.record,
            chunk_samples=self.record.chunk_samples[:sample_limit],
        )


def projection(status=ProjectionStatus.SEARCHABLE):
    return KnowledgeProjection(
        projection_id="PROJ-M013-T009-UNIT",
        document_id="DOC-M013-T009-UNIT",
        canonical_version_id="CVER-M013-T009-CANONICAL",
        projection_profile=ProjectionProfile(
            projection_profile_id="projection-publique-v1",
            chunking_profile="hierarchical-v1",
            embedding_model="dense-public-v1",
            sparse_profile="sparse-public-v1",
            index_schema="hybrid-public-v1",
        ),
        build_fingerprint=BuildFingerprint("a" * 64),
        status=status,
    )


def chunk(number, text):
    item_hash = hashlib.sha256(f"item-{number}".encode()).hexdigest()
    locator = SourceLocator(
        schema_version="1.0",
        canonical_version_id="CVER-M013-T009-CANONICAL",
        document_id="DOC-M013-T009-UNIT",
        page_pdf=number,
        item_id=f"item-{number}",
        bbox=(1.0, 2.0, 3.0, 4.0),
        content_hash=item_hash,
    )
    return KnowledgeChunk.parent(
        chunk_id=f"KCHK-{number:032X}",
        canonical_version_id="CVER-M013-T009-CANONICAL",
        document_id="DOC-M013-T009-UNIT",
        profile_id="hierarchical",
        profile_version="1",
        text=text,
        source_locators=(locator,),
    )


def assert_raises(expected_type, callback):
    try:
        callback()
    except expected_type as exc:
        return exc
    except Exception as exc:
        raise AssertionError(
            f"Type d'erreur inattendu: {type(exc).__name__}: {exc}"
        ) from exc
    raise AssertionError(f"Erreur attendue absente: {expected_type.__name__}")


chunks = (
    chunk(1, "Premier extrait public dont le texte doit être tronqué explicitement."),
    chunk(2, "Deuxième extrait public."),
    chunk(3, "Troisième extrait public."),
)
record = ProjectionReadRecord(
    projection=projection(),
    chunk_count=11,
    chunk_samples=chunks,
    state_observed_at="2026-07-12T10:30:00Z",
)
repository = ProjectionReadRepository(record)
service = ProjectionQueryService(
    projection_read_repository=repository,
    chunk_sample_limit=2,
    text_preview_character_limit=24,
    source_locator_limit=1,
)

# Le statut et la fraîcheur viennent de l'agrégat KA, jamais du nombre de chunks.
expected_freshness = {
    ProjectionStatus.REQUESTED: "PENDING",
    ProjectionStatus.BUILDING: "PENDING",
    ProjectionStatus.BUILT: "PENDING",
    ProjectionStatus.INDEXING: "PENDING",
    ProjectionStatus.SEARCHABLE: "CURRENT",
    ProjectionStatus.STALE: "STALE",
    ProjectionStatus.FAILED: "UNAVAILABLE",
    ProjectionStatus.RETIRED: "UNAVAILABLE",
}
for status, freshness in expected_freshness.items():
    status_record = replace(record, projection=projection(status=status))
    status_service = ProjectionQueryService(
        projection_read_repository=ProjectionReadRepository(status_record),
        chunk_sample_limit=2,
        text_preview_character_limit=24,
        source_locator_limit=1,
    )
    status_view = status_service.read_projection("DOC-M013-T009-UNIT")
    assert status_view.projection_status == status.value
    assert status_view.freshness.status == freshness

# La version canonique, le profil et chunk_count sont ceux de la source de lecture KA.
view = service.read_projection("DOC-M013-T009-UNIT")
assert view.canonical_version_id == "CVER-M013-T009-CANONICAL"
assert view.profile.projection_profile_id == "projection-publique-v1"
assert view.chunk_count == 11
assert len(view.chunk_samples) == 2
assert repository.calls == [("DOC-M013-T009-UNIT", 2)]

# Les aperçus et SourceLocator sont bornés sans exposer d'identifiant de point.
sample = view.chunk_samples[0]
assert sample.text_preview == chunks[0].text[:24]
assert sample.text_preview_truncated is True
assert len(sample.source_locators) == 1
assert sample.source_locators[0].canonical_version_id == view.canonical_version_id
assert sample.source_locators[0].document_id == view.document_id
assert sample.source_locators[0].page_pdf == 1
assert sample.source_locators[0].bbox == (1.0, 2.0, 3.0, 4.0)
assert set(sample.__dataclass_fields__) == {
    "chunk_level",
    "text_preview",
    "text_preview_truncated",
    "content_hash",
    "source_locators",
}

# L'absence réelle dans le port produit uniquement PROJECTION_NOT_REQUESTED.
absent = ProjectionQueryService(
    projection_read_repository=ProjectionReadRepository(None),
    chunk_sample_limit=2,
    text_preview_character_limit=24,
    source_locator_limit=1,
).read_projection("DOC-M013-T009-ABSENT")
assert isinstance(absent, ProjectionNotRequestedView)
assert absent.projection_status == "PROJECTION_NOT_REQUESTED"

# Les contrats sont immuables et refusent les incohérences au lieu de les corriger.
assert_raises(FrozenInstanceError, lambda: setattr(view, "projection_status", "INVENTED"))
assert_raises(
    ValueError,
    lambda: ProjectionReadRecord(
        projection=projection(),
        chunk_count=1,
        chunk_samples=chunks,
        state_observed_at="2026-07-12T10:30:00Z",
    ),
)
assert_raises(ValueError, lambda: service.read_projection("not-a-document"))

print("Tests unitaires des query services de projection KA: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_projection_queries_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Validation unitaire T-009: OK"
