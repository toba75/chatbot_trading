$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

sys.path.insert(0, sys.argv[1])

from app.contracts.source_references import SourceLocator, SourceLocatorValidationPolicy
from app.source_processing.application.source_locator_resolution import (
    SourceLocatorResolutionRegistry,
)
from app.source_processing.domain.canonical_source import (
    CanonicalArtifact,
    CanonicalArtifactKind,
    CanonicalSource,
    canonical_source_id_for,
)
from app.source_processing.domain.document_processing_run import (
    PageManifest,
    PageManifestEntry,
    PageManifestEntryState,
    PageNumber,
    PageRouteName,
)
from app.source_processing.domain.page_conversion import (
    CanonicalQualityDecision,
    ConversionToolName,
    PageConversionArtifact,
    PageConversionItem,
    PageConversionItemLabel,
    PageItemGeometry,
    PagewiseDoclingFusionService,
    QualityDecisionStatus,
)
from app.source_processing.domain.source_document import (
    BibliographicMetadata,
    DocumentId,
    OriginalStorageRef,
    SourceDocument,
    SourceFingerprint,
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


def registered_source(suffix):
    original_content = f"%PDF-1.7\nsource locator resolution unit {suffix}\n%%EOF\n".encode("utf-8")
    fingerprint = SourceFingerprint.from_content(original_content)
    document_id = DocumentId.from_fingerprint(fingerprint)
    storage_ref = OriginalStorageRef.from_value(
        f"artifact:source_processing.original_sources/{document_id.value}/{fingerprint.value}.pdf"
    )
    return SourceDocument.register_original(
        document_id=document_id,
        fingerprint=fingerprint,
        original_storage_ref=storage_ref,
        metadata=BibliographicMetadata.from_payload(
            {
                "title": f"Résolution SourceLocator unitaire {suffix}",
                "authors": ["Perry J. Kaufman"],
                "publication_year": 2020,
                "edition": "1re édition",
            }
        ),
    )


def manifest_for(page_count):
    return PageManifest.from_entries(
        source_page_count=page_count,
        entries=tuple(
            PageManifestEntry(
                page_number=PageNumber.from_value(page_number),
                state=PageManifestEntryState.PRESENT,
            )
            for page_number in range(1, page_count + 1)
        ),
    )


def conversion_item(page_number, item_index, text, hash_prefix):
    return PageConversionItem(
        label=PageConversionItemLabel.TEXT,
        text=text,
        geometry=PageItemGeometry(
            left=25 + item_index,
            top=50 + item_index,
            right=475 + item_index,
            bottom=250 + item_index,
            page_width=1000,
            page_height=1000,
        ),
        content_hash=f"{hash_prefix}{item_index}" * 32,
    )


def page_artifact(page_number, hash_prefix):
    return PageConversionArtifact(
        page_number=PageNumber.from_value(page_number),
        route_name=PageRouteName.NATIVE_STANDARD,
        tool_name=ConversionToolName.DOCLING_STANDARD,
        tool_version="docling-source-locator-unit-v1",
        artifact_hash=hex(page_number + 13)[2:] * 64,
        audit_artifact_ref=(
            "artifact:source_processing.page_conversion/"
            f"RUN-M004-T007-UNIT/page-{page_number:03d}.json"
        ),
        items=(
            conversion_item(page_number, 1, f"Texte page {page_number} item 1.", hash_prefix),
            conversion_item(page_number, 2, f"Texte page {page_number} item 2.", hash_prefix),
        ),
    )


def docling_document(source_document, canonical_version_id, hash_prefix):
    return PagewiseDoclingFusionService().merge(
        document_id=source_document.document_id,
        canonical_version_id=canonical_version_id,
        source_sha256=source_document.fingerprint,
        original_storage_ref=source_document.original_storage_ref,
        page_manifest=manifest_for(2),
        page_outputs=(
            page_artifact(1, hash_prefix),
            page_artifact(2, hash_prefix),
        ),
    )


def green_quality_decision():
    return CanonicalQualityDecision(
        policy_version="canonical-quality-source-locator-unit-v1",
        status=QualityDecisionStatus.PASS,
        publication_allowed=True,
        findings=(),
        publication_events=(),
    )


def published_source(source_document, document, artifact_hash):
    canonical_source_id = canonical_source_id_for(source_document.document_id)
    return CanonicalSource.publish_initial(
        source_document=source_document,
        docling_document=document,
        quality_decision=green_quality_decision(),
        canonical_artifact=CanonicalArtifact(
            artifact_ref=(
                "artifact:source_processing.canonical_sources/"
                f"{canonical_source_id}/{document.canonical_version_id}/docling.json"
            ),
            artifact_sha256=artifact_hash,
            artifact_kind=CanonicalArtifactKind.DOCLING_JSON,
        ),
        accepted_at="2026-06-27T09:00:00Z",
    )


source_document = registered_source("stable")
document_a = docling_document(source_document, "CVER-M004-T007-UNIT-0001", "a")
document_b = docling_document(source_document, "CVER-M004-T007-UNIT-0001", "a")
source = published_source(source_document, document_a, "b" * 64)

registry = SourceLocatorResolutionRegistry.from_canonical_source(
    canonical_source=source,
    docling_documents_by_version_id={document_a.canonical_version_id: document_a},
    version_statuses_by_version_id={document_a.canonical_version_id: "ACCEPTED"},
)

policy = registry.to_validation_policy()
assert_true(isinstance(policy, SourceLocatorValidationPolicy), "Le registre doit produire une SourceLocatorValidationPolicy.")
assert_equal(
    document_a.pages[0].items[0].item_id,
    document_b.pages[0].items[0].item_id,
    "L'item_id doit rester stable pour un même document, une même version, une même page et un même rang.",
)
assert_equal(
    document_a.pages[0].items[0].content_hash,
    document_b.pages[0].items[0].content_hash,
    "Le content_hash d'un item inchangé doit rester stable.",
)
assert_equal(
    dict(policy.resolvable_item_ids_by_version_id[document_a.canonical_version_id]),
    {
        item.item_id: item.content_hash
        for page in document_a.pages
        for item in page.items
    },
    "La politique doit exposer le mapping item_id -> content_hash attendu.",
)

target_item = document_a.pages[0].items[1]
locator = SourceLocator.from_payload(target_item.provenance.to_payload(), validation_policy=policy)
resolved = registry.resolve(locator)
assert_equal(resolved.page_pdf, 1, "Le registre doit résoudre la page PDF de l'item.")
assert_equal(resolved.bbox, target_item.bbox, "Le registre doit résoudre la bbox canonique de l'item.")

wrong_bbox_payload = dict(target_item.provenance.to_payload())
wrong_bbox_payload["bbox"] = [0.2, 0.2, 0.8, 0.8]
wrong_bbox_locator = SourceLocator.from_payload(wrong_bbox_payload, validation_policy=policy)
assert_raises(
    "bbox incoherente avec item_id",
    lambda: registry.resolve(wrong_bbox_locator),
)

assert_raises(
    "DoclingDocument de version absent",
    lambda: SourceLocatorResolutionRegistry.from_canonical_source(
        canonical_source=source,
        docling_documents_by_version_id={},
        version_statuses_by_version_id={document_a.canonical_version_id: "ACCEPTED"},
    ),
)

document_wrong_version = docling_document(source_document, "CVER-M004-T007-UNIT-9999", "c")
assert_raises(
    "DoclingDocument hors version canonique",
    lambda: SourceLocatorResolutionRegistry.from_canonical_source(
        canonical_source=source,
        docling_documents_by_version_id={document_a.canonical_version_id: document_wrong_version},
        version_statuses_by_version_id={document_a.canonical_version_id: "ACCEPTED"},
    ),
)

assert_raises(
    "Statut de version canonique absent",
    lambda: SourceLocatorResolutionRegistry.from_canonical_source(
        canonical_source=source,
        docling_documents_by_version_id={document_a.canonical_version_id: document_a},
        version_statuses_by_version_id={},
    ),
)

assert_raises(
    "DoclingDocument de version inconnu",
    lambda: SourceLocatorResolutionRegistry.from_canonical_source(
        canonical_source=source,
        docling_documents_by_version_id={
            document_a.canonical_version_id: document_a,
            "CVER-M004-T007-UNIT-EXTRA": document_wrong_version,
        },
        version_statuses_by_version_id={document_a.canonical_version_id: "ACCEPTED"},
    ),
)

retired_registry = SourceLocatorResolutionRegistry.from_canonical_source(
    canonical_source=source,
    docling_documents_by_version_id={document_a.canonical_version_id: document_a},
    version_statuses_by_version_id={document_a.canonical_version_id: "RETIRED"},
)
assert_raises(
    "Version canonique indisponible: RETIRED",
    lambda: SourceLocator.from_payload(
        target_item.provenance.to_payload(),
        validation_policy=retired_registry.to_validation_policy(),
    ),
)

public_payload = registry.to_public_payload()
for version_payload in public_payload["versions"]:
    assert_equal(
        tuple(version_payload.keys()),
        ("canonical_version_id", "document_id", "status", "page_count", "items"),
        "Le payload public de version doit rester borné au langage publié.",
    )
    for item_payload in version_payload["items"]:
        assert_equal(
            tuple(item_payload.keys()),
            ("page_pdf", "item_id", "bbox", "content_hash"),
            "Le payload public d'item ne doit pas exposer d'identifiant interne.",
        )
        assert_false("artifact" in repr(item_payload), "Un item public ne doit pas exposer d'artefact SP.")
        assert_false("storage" in repr(item_payload), "Un item public ne doit pas exposer de stockage SP.")

print("Tests unitaires T-007 résolution SourceLocator M-004: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m004_source_locator_resolution_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-007 résolution SourceLocator M-004: OK"
