$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import hashlib
import sys

sys.path.insert(0, sys.argv[1])

from app.contracts.source_references import CanonicalSourceRef
from app.source_processing.domain.canonical_source import (
    CanonicalArtifact,
    CanonicalArtifactKind,
    CanonicalSource,
    CanonicalSourceStatus,
    RegenerableExport,
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
    PageConversionCandidate,
    PageConversionItem,
    PageConversionItemLabel,
    PageItemGeometry,
    PagewiseDoclingFusionService,
    QualityDecisionStatus,
    TextAuthorityManifest,
    TextAuthoritySelectionPolicy,
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


def registered_source(suffix="UNIT"):
    original_content = f"%PDF-1.7\ncanonical publication {suffix}\n%%EOF\n".encode("utf-8")
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
                "title": f"Publication canonique unitaire {suffix}",
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


def content_hash_for(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def conversion_item(page_number, text):
    return PageConversionItem(
        label=PageConversionItemLabel.TEXT,
        text=text,
        geometry=PageItemGeometry(
            left=10,
            top=20,
            right=90,
            bottom=70,
            page_width=100,
            page_height=100,
        ),
        content_hash=content_hash_for(text),
    )


def page_artifact(page_number, text):
    return PageConversionArtifact(
        page_number=PageNumber.from_value(page_number),
        route_name=PageRouteName.NATIVE_STANDARD,
        tool_name=ConversionToolName.DOCLING_STANDARD,
        tool_version="docling-publication-unit-v1",
        artifact_hash=hex(page_number + 12)[2:] * 64,
        audit_artifact_ref=(
            "artifact:source_processing.page_conversion/"
            f"RUN-M004-T006-UNIT/page-{page_number:03d}.json"
        ),
        items=(conversion_item(page_number, text),),
    )


def page_outputs(suffix):
    return (
        page_artifact(1, f"Texte unitaire page 1 {suffix}."),
        page_artifact(2, f"Texte unitaire page 2 {suffix}."),
    )


def text_authority_manifest_for(outputs):
    policy = TextAuthoritySelectionPolicy(policy_version="text-authority-publication-unit-v1")
    return TextAuthorityManifest.from_page_decisions(
        page_manifest=manifest_for(2),
        page_decisions=tuple(
            policy.select(
                page_number=output.page_number,
                candidates=(
                    PageConversionCandidate(
                        candidate_id=f"AUTH-P{output.page_number.value:03d}",
                        page_output=output,
                    ),
                ),
                selected_candidate_ids=(f"AUTH-P{output.page_number.value:03d}",),
                justification=f"Autorité unique page {output.page_number.value}.",
            )
            for output in outputs
        ),
    )


def docling_fixture(source_document, canonical_version_id, suffix):
    outputs = page_outputs(suffix)
    text_authority_manifest = text_authority_manifest_for(outputs)
    return PagewiseDoclingFusionService().merge_authorized(
        document_id=source_document.document_id,
        canonical_version_id=canonical_version_id,
        source_sha256=source_document.fingerprint,
        original_storage_ref=source_document.original_storage_ref,
        page_manifest=manifest_for(2),
        text_authority_manifest=text_authority_manifest,
    ), text_authority_manifest


def green_quality_decision():
    return CanonicalQualityDecision(
        policy_version="canonical-quality-unit-v1",
        status=QualityDecisionStatus.PASS_WITH_WARNINGS,
        publication_allowed=True,
        findings=(),
        publication_events=(),
    )


source_document = registered_source()
canonical_source_id = canonical_source_id_for(source_document.document_id)
assert_true(canonical_source_id.startswith("CSRC-"), "CanonicalSourceId doit utiliser le préfixe public CSRC.")
assert_equal(
    canonical_source_id,
    canonical_source_id_for(source_document.document_id),
    "CanonicalSourceId doit être déterministe pour un même document.",
)

canonical_artifact = CanonicalArtifact(
    artifact_ref=f"artifact:source_processing.canonical_sources/{canonical_source_id}/CVER-M004-T006-UNIT-0001/docling.json",
    artifact_sha256="a" * 64,
    artifact_kind=CanonicalArtifactKind.DOCLING_JSON,
)
assert_equal(canonical_artifact.artifact_kind, CanonicalArtifactKind.DOCLING_JSON, "Le Docling JSON doit être le seul artefact canonique.")
assert_raises(
    "hash d'artefact canonique invalide",
    lambda: CanonicalArtifact(
        artifact_ref=f"artifact:source_processing.canonical_sources/{canonical_source_id}/CVER-M004-T006-UNIT-0001/docling.json",
        artifact_sha256="",
        artifact_kind=CanonicalArtifactKind.DOCLING_JSON,
    ),
)
assert_raises(
    "non canonique",
    lambda: CanonicalArtifact(
        artifact_ref=f"artifact:source_processing.canonical_exports/{canonical_source_id}/CVER-M004-T006-UNIT-0001/export.md",
        artifact_sha256="b" * 64,
        artifact_kind=CanonicalArtifactKind.MARKDOWN,
    ),
)

export = RegenerableExport(
    export_ref=f"artifact:source_processing.canonical_exports/{canonical_source_id}/CVER-M004-T006-UNIT-0001/export.html",
    export_sha256="c" * 64,
    export_kind=CanonicalArtifactKind.HTML,
)
assert_false(export.is_canonical, "Un export HTML doit rester régénérable et non canonique.")

document_v1, manifest_v1 = docling_fixture(source_document, "CVER-M004-T006-UNIT-0001", "v1")
source_v1 = CanonicalSource.publish_initial(
    source_document=source_document,
    docling_document=document_v1,
    text_authority_manifest=manifest_v1,
    quality_decision=green_quality_decision(),
    canonical_artifact=canonical_artifact,
    accepted_at="2026-06-26T10:15:00Z",
)
assert_equal(source_v1.status, CanonicalSourceStatus.PUBLISHED, "La source canonique doit être publiée après QA GREEN.")
assert_equal(source_v1.current_version_id, "CVER-M004-T006-UNIT-0001", "La version courante doit être explicite.")
assert_equal(source_v1.version_for("CVER-M004-T006-UNIT-0001").page_count, 2, "Le page_count doit venir du document canonique.")
assert_equal(source_v1.version_for("CVER-M004-T006-UNIT-0001").exports, (), "Les exports ne doivent pas être créés implicitement.")
assert_true(
    isinstance(source_v1.version_for("CVER-M004-T006-UNIT-0001").canonical_ref, CanonicalSourceRef),
    "Chaque version publiée doit exposer un CanonicalSourceRef public.",
)

source_with_export = source_v1.with_regenerable_export(
    canonical_version_id="CVER-M004-T006-UNIT-0001",
    export=export,
)
assert_equal(source_v1.version_for("CVER-M004-T006-UNIT-0001").exports, (), "Ajouter un export ne doit pas muter la version publiée.")
assert_equal(
    source_with_export.version_for("CVER-M004-T006-UNIT-0001").canonical_ref,
    source_v1.version_for("CVER-M004-T006-UNIT-0001").canonical_ref,
    "Un export régénérable ne doit pas changer la référence canonique.",
)
assert_equal(
    source_with_export.version_for("CVER-M004-T006-UNIT-0001").exports,
    (export,),
    "L'export doit rester rattaché comme artefact dérivé.",
)

document_v2, manifest_v2 = docling_fixture(source_document, "CVER-M004-T006-UNIT-0002", "v2 corrigée")
source_v2 = source_v1.publish_correction(
    docling_document=document_v2,
    text_authority_manifest=manifest_v2,
    quality_decision=green_quality_decision(),
    canonical_artifact=CanonicalArtifact(
        artifact_ref=f"artifact:source_processing.canonical_sources/{canonical_source_id}/CVER-M004-T006-UNIT-0002/docling.json",
        artifact_sha256="d" * 64,
        artifact_kind=CanonicalArtifactKind.DOCLING_JSON,
    ),
    accepted_at="2026-06-26T11:00:00Z",
)
assert_equal(len(source_v2.versions), 2, "Une correction doit créer une nouvelle version.")
assert_equal(source_v2.current_version_id, "CVER-M004-T006-UNIT-0002", "La correction doit devenir courante.")
assert_equal(
    source_v2.version_for("CVER-M004-T006-UNIT-0001").canonical_ref,
    source_v1.version_for("CVER-M004-T006-UNIT-0001").canonical_ref,
    "La version initiale doit rester inchangée après correction.",
)
assert_raises(
    "mutation en place interdite",
    lambda: source_v1.publish_correction(
        docling_document=document_v1,
        text_authority_manifest=manifest_v1,
        quality_decision=green_quality_decision(),
        canonical_artifact=canonical_artifact,
        accepted_at="2026-06-26T11:30:00Z",
    ),
)
assert_raises(
    "QA GREEN obligatoire",
    lambda: CanonicalSource.publish_initial(
        source_document=source_document,
        docling_document=document_v1,
        text_authority_manifest=manifest_v1,
        quality_decision=CanonicalQualityDecision(
            policy_version="canonical-quality-unit-v1",
            status=QualityDecisionStatus.QUARANTINE,
            publication_allowed=False,
            findings=(),
            publication_events=(),
        ),
        canonical_artifact=canonical_artifact,
        accepted_at="2026-06-26T12:00:00Z",
    ),
)

print("Tests unitaires T-006 publication canonique immuable M-004: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m004_canonical_publication_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-006 publication canonique immuable M-004: OK"
