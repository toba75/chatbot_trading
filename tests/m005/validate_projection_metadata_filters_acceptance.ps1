$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

sys.path.insert(0, sys.argv[1])

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


def assert_false(condition, message):
    if condition:
        raise AssertionError(message)


def assert_raises(expected_fragment, action):
    try:
        action()
    except ValueError as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


def metadata(
    *,
    chunk_id,
    document_id,
    author,
    published_on,
    content_type,
    canonical_quality,
):
    return ProjectionMetadata(
        projection_id="PROJ-M005-T005-FILTERABLE",
        chunk_id=chunk_id,
        canonical_version_id="CVER-M005-T005-0001",
        document_id=document_id,
        author=author,
        published_on=published_on,
        content_type=content_type,
        canonical_quality=canonical_quality,
        chunk_level="CHILD",
        content_hash="a" * 64,
    )


# Given une projection contient des chunks issus de plusieurs documents et auteurs.
candidates = (
    metadata(
        chunk_id="KCHK-M005-T005-AUTHOR-A-001",
        document_id="DOC-M005-T005-A",
        author="Anne Durand",
        published_on="2026-01-15",
        content_type="research_note",
        canonical_quality="canonical-quality-v1",
    ),
    metadata(
        chunk_id="KCHK-M005-T005-AUTHOR-A-002",
        document_id="DOC-M005-T005-B",
        author="Anne Durand",
        published_on="2026-02-03",
        content_type="research_note",
        canonical_quality="canonical-quality-v1",
    ),
    metadata(
        chunk_id="KCHK-M005-T005-AUTHOR-B-001",
        document_id="DOC-M005-T005-C",
        author="Bruno Martin",
        published_on="2026-02-20",
        content_type="research_note",
        canonical_quality="canonical-quality-v1",
    ),
    metadata(
        chunk_id="KCHK-M005-T005-AUTHOR-A-OLD",
        document_id="DOC-M005-T005-D",
        author="Anne Durand",
        published_on="2025-12-20",
        content_type="transcript",
        canonical_quality="canonical-quality-v1",
    ),
)

selector = ProjectionMetadataSelector()

# When une recherche exige un filtre d'auteur, de période et de type de contenu.
selection = selector.select(
    projection_status=ProjectionStatus.SEARCHABLE,
    metadata=candidates,
    search_filter=SearchFilter.from_payload(
        {
            "author": "Anne Durand",
            "published_on_or_after": "2026-01-01",
            "published_on_or_before": "2026-03-01",
            "content_type": "research_note",
        }
    ),
    freshness_policy=ProjectionFreshnessPolicy(require_current=True),
    diversification_policy=EvidenceDiversificationPolicy.none(),
)

# Then seuls les chunks satisfaisant explicitement le filtre sont éligibles, avec une trace consultable.
assert_equal(
    tuple(item.chunk_id for item in selection.metadata),
    ("KCHK-M005-T005-AUTHOR-A-001", "KCHK-M005-T005-AUTHOR-A-002"),
    "Le filtre doit retenir seulement les chunks auteur/période/type demandés.",
)
trace_payload = selection.trace.to_payload()
assert_equal(trace_payload["candidate_count"], 4, "La trace doit compter les candidats avant filtre.")
assert_equal(trace_payload["eligible_count"], 2, "La trace doit compter les candidats après filtre.")
assert_equal(
    tuple(entry["dimension"] for entry in trace_payload["applied_filters"]),
    ("author", "published_on", "content_type"),
    "Chaque dimension demandée doit être tracée.",
)
assert_equal(trace_payload["freshness"]["status"], "SEARCHABLE", "La fraîcheur doit être tracée.")
assert_equal(trace_payload["diversification"]["mode"], "NONE", "L'absence de diversification doit être explicite.")
assert_false(trace_payload["warnings"], "Aucun avertissement implicite ne doit être inventé.")

# Filtre inconnu refusé explicitement.
assert_raises(
    "FILTER_NOT_SUPPORTED",
    lambda: SearchFilter.from_payload({"sector": "technology"}),
)

# Projection STALE refusée sans avertissement contractuel explicite.
assert_raises(
    "PROJECTION_STALE",
    lambda: selector.select(
        projection_status=ProjectionStatus.STALE,
        metadata=candidates,
        search_filter=SearchFilter.from_payload({"author": "Anne Durand"}),
        freshness_policy=ProjectionFreshnessPolicy(require_current=True),
        diversification_policy=EvidenceDiversificationPolicy.none(),
    ),
)

# Diversité par document quand elle est demandée.
duplicated_document_candidates = (
    metadata(
        chunk_id="KCHK-M005-T005-DOC-A-001",
        document_id="DOC-M005-T005-A",
        author="Anne Durand",
        published_on="2026-01-10",
        content_type="research_note",
        canonical_quality="canonical-quality-v1",
    ),
    metadata(
        chunk_id="KCHK-M005-T005-DOC-A-002",
        document_id="DOC-M005-T005-A",
        author="Anne Durand",
        published_on="2026-01-11",
        content_type="research_note",
        canonical_quality="canonical-quality-v1",
    ),
    metadata(
        chunk_id="KCHK-M005-T005-DOC-B-001",
        document_id="DOC-M005-T005-B",
        author="Anne Durand",
        published_on="2026-01-12",
        content_type="research_note",
        canonical_quality="canonical-quality-v1",
    ),
)
diversified_selection = selector.select(
    projection_status=ProjectionStatus.SEARCHABLE,
    metadata=duplicated_document_candidates,
    search_filter=SearchFilter.from_payload({"author": "Anne Durand"}),
    freshness_policy=ProjectionFreshnessPolicy(require_current=True),
    diversification_policy=EvidenceDiversificationPolicy.per_document(max_per_document=1),
)
assert_equal(
    tuple(item.chunk_id for item in diversified_selection.metadata),
    ("KCHK-M005-T005-DOC-A-001", "KCHK-M005-T005-DOC-B-001"),
    "La diversification par document doit limiter les preuves à un chunk par document.",
)
diversification_payload = diversified_selection.trace.to_payload()["diversification"]
assert_equal(diversification_payload["mode"], "PER_DOCUMENT", "Le mode de diversification doit être tracé.")
assert_equal(diversification_payload["input_count"], 3, "La trace doit compter les candidats avant diversification.")
assert_equal(diversification_payload["output_count"], 2, "La trace doit compter les candidats après diversification.")

# Aucune métadonnée obligatoire vide ou inventée.
assert_raises(
    "author vide",
    lambda: metadata(
        chunk_id="KCHK-M005-T005-EMPTY-AUTHOR",
        document_id="DOC-M005-T005-A",
        author="",
        published_on="2026-01-15",
        content_type="research_note",
        canonical_quality="canonical-quality-v1",
    ),
)
assert_raises(
    "content_type vide",
    lambda: metadata(
        chunk_id="KCHK-M005-T005-EMPTY-TYPE",
        document_id="DOC-M005-T005-A",
        author="Anne Durand",
        published_on="2026-01-15",
        content_type="",
        canonical_quality="canonical-quality-v1",
    ),
)

print("Test d'acceptation T-005 métadonnées filtrables M-005: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m005_projection_metadata_filters_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-005 métadonnées filtrables M-005: OK"
