$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

sys.path.insert(0, sys.argv[1])

from app.contracts.source_references import SourceLocator
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


def registered_source():
    original_content = b"%PDF-1.7\nsource locator resolution acceptance\n%%EOF\n"
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
                "title": "Résolution SourceLocator M-004",
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


def conversion_item(page_number, item_index, text):
    return PageConversionItem(
        label=PageConversionItemLabel.TEXT,
        text=text,
        geometry=PageItemGeometry(
            left=50 + item_index,
            top=100 + item_index,
            right=450 + item_index,
            bottom=180 + item_index,
            page_width=1000,
            page_height=1000,
        ),
        content_hash=f"{page_number}{item_index}" * 32,
    )


def page_artifact(page_number, texts):
    return PageConversionArtifact(
        page_number=PageNumber.from_value(page_number),
        route_name=PageRouteName.NATIVE_STANDARD,
        tool_name=ConversionToolName.DOCLING_STANDARD,
        tool_version="docling-source-locator-v1",
        artifact_hash=hex(page_number + 10)[2:] * 64,
        audit_artifact_ref=(
            "artifact:source_processing.page_conversion/"
            f"RUN-M004-T007/page-{page_number:03d}.json"
        ),
        items=tuple(
            conversion_item(page_number, item_index, text)
            for item_index, text in enumerate(texts, start=1)
        ),
    )


def docling_document(source_document):
    return PagewiseDoclingFusionService().merge(
        document_id=source_document.document_id,
        canonical_version_id="CVER-M004-T007-0001",
        source_sha256=source_document.fingerprint,
        original_storage_ref=source_document.original_storage_ref,
        page_manifest=manifest_for(2),
        page_outputs=(
            page_artifact(1, ("Capital initial 100000.", "Risque 2%.")),
            page_artifact(2, ("Stop initial 95.", "Objectif 110.")),
        ),
    )


def green_quality_decision():
    return CanonicalQualityDecision(
        policy_version="canonical-quality-source-locator-v1",
        status=QualityDecisionStatus.PASS,
        publication_allowed=True,
        findings=(),
        publication_events=(),
    )


def published_source(source_document, document):
    canonical_source_id = canonical_source_id_for(source_document.document_id)
    return CanonicalSource.publish_initial(
        source_document=source_document,
        docling_document=document,
        quality_decision=green_quality_decision(),
        canonical_artifact=CanonicalArtifact(
            artifact_ref=(
                "artifact:source_processing.canonical_sources/"
                f"{canonical_source_id}/CVER-M004-T007-0001/docling.json"
            ),
            artifact_sha256="a" * 64,
            artifact_kind=CanonicalArtifactKind.DOCLING_JSON,
        ),
        accepted_at="2026-06-27T08:30:00Z",
    )


# Given une version canonique publiée contenant une page avec plusieurs items.
source_document = registered_source()
document = docling_document(source_document)
canonical_source = published_source(source_document, document)
registry = SourceLocatorResolutionRegistry.from_canonical_source(
    canonical_source=canonical_source,
    docling_documents_by_version_id={
        "CVER-M004-T007-0001": document,
    },
    version_statuses_by_version_id={
        "CVER-M004-T007-0001": "ACCEPTED",
    },
)
validation_policy = registry.to_validation_policy()
target_item = document.pages[1].items[0]

# When un contexte aval valide un SourceLocator vers un item précis.
locator = SourceLocator.from_payload(
    target_item.provenance.to_payload(),
    validation_policy=validation_policy,
)
resolution = registry.resolve(locator)

# Then SP confirme la version, la page, l'item et le content_hash sans exposer les structures internes SP.
assert_equal(resolution.canonical_version_id, "CVER-M004-T007-0001", "La version canonique doit être confirmée.")
assert_equal(resolution.document_id, source_document.document_id.value, "Le document doit être confirmé.")
assert_equal(resolution.page_pdf, 2, "La page PDF exacte doit être confirmée.")
assert_equal(resolution.item_id, target_item.item_id, "L'item exact doit être confirmé.")
assert_equal(resolution.content_hash, target_item.content_hash, "Le hash de contenu doit être confirmé.")

public_registry_payload = registry.to_public_payload()
serialized_public_payload = repr(public_registry_payload)
assert_false("original_storage_ref" in serialized_public_payload, "Le registre publié ne doit pas exposer original_storage_ref.")
assert_false("canonical_artifact" in serialized_public_payload, "Le registre publié ne doit pas exposer l'artefact interne.")
assert_false("artifact:" in serialized_public_payload, "Le registre publié ne doit pas exposer de chemin de stockage SP.")
assert_false(target_item.text in serialized_public_payload, "Le registre publié ne doit pas exposer le texte documentaire complet.")

missing_item_payload = dict(target_item.provenance.to_payload())
missing_item_payload["item_id"] = "DOC-000000-P002-I999"
assert_raises(
    "item_id non resolvable",
    lambda: SourceLocator.from_payload(missing_item_payload, validation_policy=validation_policy),
)

outside_page_payload = dict(target_item.provenance.to_payload())
outside_page_payload["page_pdf"] = 3
assert_raises(
    "page_pdf hors version canonique",
    lambda: SourceLocator.from_payload(outside_page_payload, validation_policy=validation_policy),
)

incoherent_hash_payload = dict(target_item.provenance.to_payload())
incoherent_hash_payload["content_hash"] = "f" * 64
assert_raises(
    "content_hash incoherent",
    lambda: SourceLocator.from_payload(incoherent_hash_payload, validation_policy=validation_policy),
)

wrong_page_payload = dict(target_item.provenance.to_payload())
wrong_page_payload["page_pdf"] = 1
wrong_page_locator = SourceLocator.from_payload(wrong_page_payload, validation_policy=validation_policy)
assert_raises(
    "page_pdf incoherent avec item_id",
    lambda: registry.resolve(wrong_page_locator),
)

quarantined_registry = SourceLocatorResolutionRegistry.from_canonical_source(
    canonical_source=canonical_source,
    docling_documents_by_version_id={
        "CVER-M004-T007-0001": document,
    },
    version_statuses_by_version_id={
        "CVER-M004-T007-0001": "QUARANTINED",
    },
)
assert_raises(
    "Version canonique indisponible: QUARANTINED",
    lambda: SourceLocator.from_payload(
        target_item.provenance.to_payload(),
        validation_policy=quarantined_registry.to_validation_policy(),
    ),
)

print("Test d'acceptation T-007 résolution SourceLocator M-004: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m004_source_locator_resolution_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-007 résolution SourceLocator M-004: OK"
