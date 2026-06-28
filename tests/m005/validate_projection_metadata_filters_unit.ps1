$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import hashlib
import sys

sys.path.insert(0, sys.argv[1])

from app.contracts.source_references import SourceLocator
from app.knowledge_access.domain.chunking import KnowledgeChunk
from app.knowledge_access.domain.knowledge_projection import ProjectionStatus
from app.knowledge_access.domain.projection_metadata import (
    EvidenceDiversificationPolicy,
    ProjectionFreshnessPolicy,
    ProjectionMetadata,
    ProjectionMetadataSelector,
    SearchFilter,
)


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def assert_raises(expected_fragment, action):
    try:
        action()
    except (TypeError, ValueError) as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


def content_hash_for(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def locator(text, *, document_id="DOC-M005-T005-UNIT"):
    return SourceLocator(
        schema_version="1.0",
        canonical_version_id="CVER-M005-T005-UNIT-0001",
        document_id=document_id,
        page_pdf=1,
        item_id=f"{document_id}-P001-I001",
        bbox=(0.1, 0.1, 0.8, 0.2),
        content_hash=content_hash_for(text),
    )


def chunk(text, *, chunk_id="KCHK-M005-T005-UNIT-001", document_id="DOC-M005-T005-UNIT"):
    source_locator = locator(text, document_id=document_id)
    return KnowledgeChunk.child(
        chunk_id=chunk_id,
        parent_chunk_id="KCHK-M005-T005-UNIT-PARENT",
        canonical_version_id=source_locator.canonical_version_id,
        document_id=source_locator.document_id,
        profile_id="chunking-profile-m005-t005",
        profile_version="hierarchical-v1",
        text=text,
        source_locators=(source_locator,),
    )


def metadata(
    *,
    chunk_id="KCHK-M005-T005-UNIT-001",
    document_id="DOC-M005-T005-UNIT",
    author="Anne Durand",
    published_on="2026-01-15",
    content_type="research_note",
    canonical_quality="canonical-quality-v1",
):
    return ProjectionMetadata(
        projection_id="PROJ-M005-T005-UNIT",
        chunk_id=chunk_id,
        canonical_version_id="CVER-M005-T005-UNIT-0001",
        document_id=document_id,
        author=author,
        published_on=published_on,
        content_type=content_type,
        canonical_quality=canonical_quality,
        chunk_level="CHILD",
        content_hash="b" * 64,
    )


# ProjectionMetadata reprend les identifiants et hash du chunk, mais refuse d'inventer les métadonnées métier.
source_chunk = chunk("Le passage filtrable conserve sa provenance.")
derived_metadata = ProjectionMetadata.from_chunk(
    projection_id="PROJ-M005-T005-UNIT",
    chunk=source_chunk,
    author="Anne Durand",
    published_on="2026-01-15",
    content_type="research_note",
    canonical_quality="canonical-quality-v1",
)
assert_equal(derived_metadata.chunk_id, source_chunk.chunk_id, "Le chunk_id doit venir du chunk.")
assert_equal(derived_metadata.document_id, source_chunk.document_id, "Le document_id doit venir du chunk.")
assert_equal(derived_metadata.canonical_version_id, source_chunk.canonical_version_id, "La version canonique doit venir du chunk.")
assert_equal(derived_metadata.chunk_level, source_chunk.chunk_level, "Le type de chunk doit venir du chunk.")
assert_equal(derived_metadata.content_hash, source_chunk.content_hash, "Le content_hash doit venir du chunk.")
assert_equal(derived_metadata.published_on.isoformat(), "2026-01-15", "La date doit être normalisée.")

assert_raises(
    "author vide",
    lambda: ProjectionMetadata.from_chunk(
        projection_id="PROJ-M005-T005-UNIT",
        chunk=source_chunk,
        author="",
        published_on="2026-01-15",
        content_type="research_note",
        canonical_quality="canonical-quality-v1",
    ),
)
assert_raises(
    "published_on invalide",
    lambda: metadata(published_on="15/01/2026"),
)
assert_raises(
    "canonical_quality vide",
    lambda: metadata(canonical_quality=""),
)
assert_raises(
    "content_type vide",
    lambda: metadata(content_type=""),
)

# SearchFilter refuse toute dimension inconnue ou valeur vide.
author_filter = SearchFilter.from_payload({"author": "Anne Durand"})
assert_true(author_filter.matches(metadata(author="Anne Durand")), "Le filtre auteur doit matcher l'auteur demandé.")
assert_true(not author_filter.matches(metadata(author="Bruno Martin")), "Le filtre auteur doit exclure les autres auteurs.")
assert_raises("FILTER_NOT_SUPPORTED", lambda: SearchFilter.from_payload({"sector": "tech"}))
assert_raises("author vide", lambda: SearchFilter.from_payload({"author": ""}))
assert_raises(
    "periode incoherente",
    lambda: SearchFilter.from_payload(
        {
            "published_on_or_after": "2026-04-01",
            "published_on_or_before": "2026-03-01",
        }
    ),
)

# ProjectionFreshnessPolicy refuse une projection STALE sans avertissement contractuel explicite.
freshness_policy = ProjectionFreshnessPolicy(require_current=True)
freshness_decision = freshness_policy.evaluate(ProjectionStatus.SEARCHABLE)
assert_equal(freshness_decision.to_payload()["status"], "SEARCHABLE", "SEARCHABLE doit être accepté.")
assert_raises("PROJECTION_STALE", lambda: freshness_policy.evaluate(ProjectionStatus.STALE))
explicit_stale_decision = ProjectionFreshnessPolicy(require_current=False).evaluate(
    ProjectionStatus.STALE,
    contractual_warning="PROJECTION_STALE_EXPLICITLY_ACCEPTED",
)
assert_equal(
    explicit_stale_decision.to_payload()["warnings"],
    ("PROJECTION_STALE_EXPLICITLY_ACCEPTED",),
    "Un avertissement contractuel explicite doit être conservé.",
)

# EvidenceDiversificationPolicy limite explicitement les doublons documentaires.
items = (
    metadata(chunk_id="KCHK-M005-T005-DOC-A-001", document_id="DOC-M005-T005-DOC-A"),
    metadata(chunk_id="KCHK-M005-T005-DOC-A-002", document_id="DOC-M005-T005-DOC-A"),
    metadata(chunk_id="KCHK-M005-T005-DOC-B-001", document_id="DOC-M005-T005-DOC-B"),
)
diversified, diversification_trace = EvidenceDiversificationPolicy.per_document(
    max_per_document=1
).apply(items)
assert_equal(
    tuple(item.chunk_id for item in diversified),
    ("KCHK-M005-T005-DOC-A-001", "KCHK-M005-T005-DOC-B-001"),
    "La diversification doit conserver le premier candidat de chaque document.",
)
assert_equal(diversification_trace.to_payload()["mode"], "PER_DOCUMENT", "La trace doit exposer le mode.")
assert_raises(
    "max_per_document invalide",
    lambda: EvidenceDiversificationPolicy.per_document(max_per_document=0),
)

# La trace de filtre est sérialisable et stable.
selection = ProjectionMetadataSelector().select(
    projection_status=ProjectionStatus.SEARCHABLE,
    metadata=items,
    search_filter=SearchFilter.from_payload({"content_type": "research_note"}),
    freshness_policy=ProjectionFreshnessPolicy(require_current=True),
    diversification_policy=EvidenceDiversificationPolicy.none(),
)
payload = selection.trace.to_payload()
assert_equal(payload["applied_filters"][0]["dimension"], "content_type", "La dimension filtrée doit être tracée.")
assert_equal(payload["applied_filters"][0]["eligible_count"], 3, "La trace doit compter les éligibles.")
assert_equal(payload["diversification"]["mode"], "NONE", "Le mode sans diversification doit être explicite.")

print("Tests unitaires T-005 métadonnées filtrables M-005: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m005_projection_metadata_filters_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
try {
    $env:PYTHONIOENCODING = "utf-8"
    $output = & $pythonExecutable -B $pythonScriptPath $repoRoot 2>&1
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
    Remove-Item -LiteralPath $pythonScriptPath -Force
}

if ($LASTEXITCODE -ne 0) {
    throw ($output -join "`n")
}

Write-Host "Tests unitaires T-005 métadonnées filtrables M-005: OK"
