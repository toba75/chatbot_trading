$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import hashlib
import sys

sys.path.insert(0, sys.argv[1])

from app.contracts.source_references import CanonicalSourceRef
from app.source_processing.application.publish_canonical_source import (
    PublishCanonicalSourceCommand,
    PublishCanonicalSourceHandler,
    StoredCanonicalArtifact,
)
from app.source_processing.domain.canonical_source import CanonicalSourceStatus
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


def assert_raises(expected_fragment, action):
    try:
        action()
    except ValueError as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


def registered_source():
    original_content = b"%PDF-1.7\ncanonical publication acceptance\n%%EOF\n"
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
                "title": "Publication canonique M-004",
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
            left=100,
            top=100,
            right=900,
            bottom=300,
            page_width=1000,
            page_height=1000,
        ),
        content_hash=content_hash_for(text),
    )


def page_artifact(page_number, text):
    return PageConversionArtifact(
        page_number=PageNumber.from_value(page_number),
        route_name=PageRouteName.NATIVE_STANDARD,
        tool_name=ConversionToolName.DOCLING_STANDARD,
        tool_version="docling-publication-v1",
        artifact_hash=hex(page_number + 10)[2:] * 64,
        audit_artifact_ref=(
            "artifact:source_processing.page_conversion/"
            f"RUN-M004-T006/page-{page_number:03d}.json"
        ),
        items=(conversion_item(page_number, text),),
    )


def page_outputs(suffix):
    return (
        page_artifact(1, f"Texte canonique page 1 {suffix}."),
        page_artifact(2, f"Texte canonique page 2 {suffix}."),
    )


def text_authority_manifest_for(outputs):
    policy = TextAuthoritySelectionPolicy(policy_version="text-authority-publication-v1")
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
        policy_version="canonical-quality-v1",
        status=QualityDecisionStatus.PASS,
        publication_allowed=True,
        findings=(),
        publication_events=(),
    )


def red_quality_decision():
    return CanonicalQualityDecision(
        policy_version="canonical-quality-v1",
        status=QualityDecisionStatus.MANUAL_REVIEW,
        publication_allowed=False,
        findings=(),
        publication_events=(),
    )


class RecordingCanonicalArtifactStore:
    def __init__(self):
        self.requests = []

    def store_docling_json(self, request):
        self.requests.append(request)
        if request.artifact_kind.value != "DOCLING_JSON":
            raise AssertionError("La publication doit stocker un Docling JSON canonique.")
        if not request.expected_artifact_ref.endswith("/docling.json"):
            raise AssertionError("L'artefact canonique doit rester un JSON Docling.")
        if b"Texte canonique" not in request.content_bytes:
            raise AssertionError("Le contenu canonique sérialisé doit être stocké.")
        return StoredCanonicalArtifact(
            artifact_ref=request.expected_artifact_ref,
            artifact_sha256=request.artifact_sha256,
        )


source_document = registered_source()
artifact_store = RecordingCanonicalArtifactStore()
handler = PublishCanonicalSourceHandler(artifact_store=artifact_store)
accepted_at_v1 = "2026-06-26T10:15:00Z"
document_v1, manifest_v1 = docling_fixture(source_document, "CVER-M004-T006-0001", "v1")

# Given une source routée, convertie, adjugée et validée par QA.
# When la publication canonique est demandée.
result_v1 = handler.handle(
    PublishCanonicalSourceCommand(
        source_document=source_document,
        docling_document=document_v1,
        text_authority_manifest=manifest_v1,
        quality_decision=green_quality_decision(),
        accepted_at=accepted_at_v1,
        existing_canonical_source=None,
    )
)

# Then une version canonique immutable est créée avec CanonicalSourceRef, hash d'artefact, page count et statut accepté.
canonical_ref = result_v1.canonical_ref
assert_true(isinstance(canonical_ref, CanonicalSourceRef), "La publication doit produire un CanonicalSourceRef public.")
assert_true(canonical_ref.canonical_source_id.startswith("CSRC-"), "L'identifiant CanonicalSource doit respecter le préfixe M-001.")
assert_equal(canonical_ref.document_id, source_document.document_id.value, "Le document_id publié doit rester le document source.")
assert_equal(canonical_ref.canonical_version_id, "CVER-M004-T006-0001", "La version publiée doit être la version Docling contrôlée.")
assert_equal(canonical_ref.source_sha256, source_document.fingerprint.value, "Le hash du PDF original doit être publié.")
assert_equal(canonical_ref.page_count, 2, "Le page_count publié doit venir du DoclingDocument contrôlé.")
assert_equal(canonical_ref.accepted_at, accepted_at_v1, "L'horodatage d'acceptation doit être explicite.")
assert_equal(canonical_ref.quality_policy_version, "canonical-quality-v1", "La politique QA doit être publiée.")
assert_equal(result_v1.canonical_source.status, CanonicalSourceStatus.PUBLISHED, "La source canonique doit être publiée.")
assert_equal(result_v1.canonical_source.current_version_id, "CVER-M004-T006-0001", "La version courante doit être la version publiée.")
assert_equal(len(artifact_store.requests), 1, "Un seul artefact Docling JSON canonique doit être stocké.")
assert_equal(
    artifact_store.requests[0].artifact_sha256,
    canonical_ref.canonical_artifact_sha256,
    "Le hash publié doit être le hash exact de l'artefact stocké.",
)
assert_equal(
    CanonicalSourceRef.from_payload(canonical_ref.to_payload()),
    canonical_ref,
    "Le CanonicalSourceRef produit doit respecter le contrat public M-001.",
)

repeat_store = RecordingCanonicalArtifactStore()
repeat_result = PublishCanonicalSourceHandler(artifact_store=repeat_store).handle(
    PublishCanonicalSourceCommand(
        source_document=source_document,
        docling_document=document_v1,
        text_authority_manifest=manifest_v1,
        quality_decision=green_quality_decision(),
        accepted_at=accepted_at_v1,
        existing_canonical_source=None,
    )
)
assert_equal(
    repeat_result.canonical_ref,
    canonical_ref,
    "La publication d'une même version contrôlée doit produire une référence déterministe.",
)

# Given une version déjà publiée.
# When une correction validée par QA est publiée.
document_v2, manifest_v2 = docling_fixture(source_document, "CVER-M004-T006-0002", "v2 corrigée")
result_v2 = handler.handle(
    PublishCanonicalSourceCommand(
        source_document=source_document,
        docling_document=document_v2,
        text_authority_manifest=manifest_v2,
        quality_decision=green_quality_decision(),
        accepted_at="2026-06-26T11:00:00Z",
        existing_canonical_source=result_v1.canonical_source,
    )
)

# Then l'ancienne version reste résoluble et la correction crée une nouvelle version sans mutation en place.
assert_equal(result_v2.canonical_source.current_version_id, "CVER-M004-T006-0002", "La correction doit devenir la version courante.")
assert_equal(len(result_v2.canonical_source.versions), 2, "La correction doit ajouter une version.")
assert_equal(
    result_v2.canonical_source.version_for("CVER-M004-T006-0001").canonical_ref,
    canonical_ref,
    "L'ancienne version publiée doit rester résoluble et inchangée.",
)
assert_true(
    result_v2.canonical_source.version_for("CVER-M004-T006-0002").canonical_ref != canonical_ref,
    "La correction doit produire une nouvelle référence canonique.",
)

assert_raises(
    "mutation en place interdite",
    lambda: handler.handle(
        PublishCanonicalSourceCommand(
            source_document=source_document,
            docling_document=document_v1,
            text_authority_manifest=manifest_v1,
            quality_decision=green_quality_decision(),
            accepted_at="2026-06-26T11:30:00Z",
            existing_canonical_source=result_v1.canonical_source,
        )
    ),
)
request_count_before_red = len(artifact_store.requests)
assert_raises(
    "QA GREEN obligatoire",
    lambda: handler.handle(
        PublishCanonicalSourceCommand(
            source_document=source_document,
            docling_document=docling_fixture(source_document, "CVER-M004-T006-0003", "red")[0],
            text_authority_manifest=docling_fixture(source_document, "CVER-M004-T006-0003", "red")[1],
            quality_decision=red_quality_decision(),
            accepted_at="2026-06-26T12:00:00Z",
            existing_canonical_source=result_v2.canonical_source,
        )
    ),
)
assert_equal(
    len(artifact_store.requests),
    request_count_before_red,
    "Une QA RED ne doit pas stocker de Docling JSON canonique.",
)
assert_raises(
    "textuelle obligatoire",
    lambda: PublishCanonicalSourceCommand(
        source_document=source_document,
        docling_document=document_v1,
        text_authority_manifest=None,
        quality_decision=green_quality_decision(),
        accepted_at="2026-06-26T12:15:00Z",
        existing_canonical_source=None,
    ),
)
assert_raises(
    "source documentaire non publiable",
    lambda: handler.handle(
        PublishCanonicalSourceCommand(
            source_document=source_document.quarantine("Quarantaine explicite avant publication canonique."),
            docling_document=docling_fixture(source_document, "CVER-M004-T006-0004", "quarantaine")[0],
            text_authority_manifest=docling_fixture(source_document, "CVER-M004-T006-0004", "quarantaine")[1],
            quality_decision=green_quality_decision(),
            accepted_at="2026-06-26T12:30:00Z",
            existing_canonical_source=None,
        )
    ),
)

print("Test d'acceptation T-006 publication canonique immuable M-004: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m004_canonical_publication_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-006 publication canonique immuable M-004: OK"
