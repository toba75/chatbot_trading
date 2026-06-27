$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import hashlib
import sys

sys.path.insert(0, sys.argv[1])

from app.contracts.event_envelope import EventEnvelope
from app.contracts.source_references import CanonicalSourceRef
from app.platform.event_bus import InMemoryTransactionalOutbox, OutboxMessageStatus
from app.source_processing.application.publish_canonical_source import (
    PublishCanonicalSourceCommand,
    PublishCanonicalSourceHandler,
    StoredCanonicalArtifact,
)
from app.source_processing.application.publish_canonical_source_event import (
    PublishCanonicalSourceEventCommand,
    PublishCanonicalSourceEventHandler,
    build_canonical_source_published_event,
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


def assert_no_internal_sp_payload(value):
    forbidden_keys = {
        "artifact_ref",
        "audit_artifact_ref",
        "conversion_candidates",
        "docling_document",
        "internal_model",
        "item_text",
        "items",
        "original_storage_ref",
        "page_outputs",
        "pages",
        "route_name",
        "source_processing_path",
        "storage_path",
        "text",
        "tool_name",
        "tool_version",
    }

    if isinstance(value, dict):
        for key, nested_value in value.items():
            if key in forbidden_keys:
                raise AssertionError(f"Payload interne SP exposé: {key}")
            assert_no_internal_sp_payload(nested_value)
    elif isinstance(value, (list, tuple)):
        for nested_value in value:
            assert_no_internal_sp_payload(nested_value)
    elif isinstance(value, str):
        if value.startswith("artifact:"):
            raise AssertionError(f"Chemin d'artefact exposé dans l'événement: {value}")
        if "Texte canonique" in value:
            raise AssertionError("Texte documentaire exposé dans l'événement.")


def registered_source():
    original_content = b"%PDF-1.7\ncanonical publication event acceptance\n%%EOF\n"
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
                "title": "Événement CanonicalSourcePublished M-004",
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
        tool_version="docling-publication-event-v1",
        artifact_hash=f"{page_number + 20:064x}",
        audit_artifact_ref=(
            "artifact:source_processing.page_conversion/"
            f"RUN-M004-T008/page-{page_number:03d}.json"
        ),
        items=(conversion_item(page_number, text),),
    )


def page_outputs(suffix):
    return (
        page_artifact(1, f"Texte canonique page 1 {suffix}."),
        page_artifact(2, f"Texte canonique page 2 {suffix}."),
    )


def text_authority_manifest_for(outputs):
    policy = TextAuthoritySelectionPolicy(policy_version="text-authority-event-v1")
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
        policy_version="canonical-quality-event-v1",
        status=QualityDecisionStatus.PASS,
        publication_allowed=True,
        findings=(),
        publication_events=(),
    )


def red_quality_decision():
    return CanonicalQualityDecision(
        policy_version="canonical-quality-event-v1",
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
        return StoredCanonicalArtifact(
            artifact_ref=request.expected_artifact_ref,
            artifact_sha256=request.artifact_sha256,
        )


source_document = registered_source()
artifact_store = RecordingCanonicalArtifactStore()
publication_handler = PublishCanonicalSourceHandler(artifact_store=artifact_store)
event_handler = PublishCanonicalSourceEventHandler()
outbox = InMemoryTransactionalOutbox.empty()

# Given une version canonique vient d'être publiée par SP.
document_v1, manifest_v1 = docling_fixture(source_document, "CVER-M004-T008-0001", "v1")
publication_v1 = publication_handler.handle(
    PublishCanonicalSourceCommand(
        source_document=source_document,
        docling_document=document_v1,
        text_authority_manifest=manifest_v1,
        quality_decision=green_quality_decision(),
        accepted_at="2026-06-27T09:15:00Z",
        existing_canonical_source=None,
    )
)

# When l'intégration intercontextes est traitée.
event_result_v1 = event_handler.handle(
    PublishCanonicalSourceEventCommand(
        publication_result=publication_v1,
        outbox=outbox,
        correlation_id="CORR-M004-T008-0001",
        causation_id="CMD-PUBLISH-CANONICAL-SOURCE-M004-T008-0001",
    )
)

# Then un événement CanonicalSourcePublished versionné est inscrit dans l'outbox avec un payload CanonicalSourceRef.
event_v1 = event_result_v1.event
assert_true(isinstance(event_v1, EventEnvelope), "L'intégration doit produire une EventEnvelope publique.")
assert_true(event_result_v1.created, "La première publication d'événement doit créer une entrée outbox.")
assert_equal(event_v1.event_id, "EVT-CANONICAL-SOURCE-PUBLISHED-CVER-M004-T008-0001", "event_id doit être déterministe par version canonique.")
assert_equal(event_v1.event_type, "CanonicalSourcePublished", "Le type d'événement doit être CanonicalSourcePublished.")
assert_equal(event_v1.event_version, 1, "La version d'événement doit être explicite.")
assert_equal(event_v1.producer_context, "SP", "SP doit rester l'unique producteur.")
assert_equal(event_v1.aggregate_type, "CanonicalSource", "L'agrégat producteur doit être CanonicalSource.")
assert_equal(event_v1.aggregate_id, publication_v1.canonical_ref.canonical_source_id, "aggregate_id doit être le CanonicalSourceId public.")
assert_equal(event_v1.aggregate_version, 1, "La première version canonique doit porter aggregate_version 1.")
assert_equal(event_v1.occurred_at, publication_v1.canonical_ref.accepted_at, "occurred_at doit reprendre l'acceptation canonique.")
assert_equal(dict(event_v1.payload), publication_v1.canonical_ref.to_payload(), "Le payload doit être le CanonicalSourceRef contractuel.")
assert_equal(
    CanonicalSourceRef.from_payload(dict(event_v1.payload)),
    publication_v1.canonical_ref,
    "Le payload CanonicalSourcePublished doit respecter le contrat M-001.",
)
assert_no_internal_sp_payload(dict(event_v1.payload))

entry_v1 = outbox.entry_for(event_v1.event_id)
assert_equal(entry_v1, event_result_v1.outbox_entry, "L'entrée retournée doit être celle de l'outbox.")
assert_true(entry_v1.status is OutboxMessageStatus.PENDING, "L'événement publié doit démarrer en pending.")
assert_equal(outbox.recorded_state_mutations()[0].mutation_id, "MUT-SP-CANONICAL-SOURCE-PUBLISHED-CVER-M004-T008-0001", "La mutation productrice doit être déterministe.")
assert_equal(outbox.recorded_state_mutations()[0].aggregate_id, event_v1.aggregate_id, "La mutation doit cibler le même agrégat.")
assert_equal(outbox.recorded_state_mutations()[0].aggregate_version, event_v1.aggregate_version, "La mutation doit cibler la même version d'agrégat.")

# Given le même traitement est relancé après retry.
# When le handler est rappelé avec la même version canonique.
# Then il retourne l'entrée existante sans doublonner l'outbox.
retry_result_v1 = event_handler.handle(
    PublishCanonicalSourceEventCommand(
        publication_result=publication_v1,
        outbox=outbox,
        correlation_id="CORR-M004-T008-0001",
        causation_id="CMD-PUBLISH-CANONICAL-SOURCE-M004-T008-0001",
    )
)
assert_false(retry_result_v1.created, "Un retry ne doit pas créer un second événement.")
assert_equal(retry_result_v1.outbox_entry, entry_v1, "Le retry doit retourner l'entrée outbox existante.")
assert_equal(len(outbox.pending_events()), 1, "L'outbox doit conserver un seul événement par version canonique.")
assert_equal(len(outbox.recorded_state_mutations()), 1, "Le retry ne doit pas ajouter de mutation productrice.")

# Given une correction crée une nouvelle version canonique.
# When l'événement est publié pour cette nouvelle version.
# Then un second événement distinct est inscrit sans muter le premier.
document_v2, manifest_v2 = docling_fixture(source_document, "CVER-M004-T008-0002", "v2 corrigée")
publication_v2 = publication_handler.handle(
    PublishCanonicalSourceCommand(
        source_document=source_document,
        docling_document=document_v2,
        text_authority_manifest=manifest_v2,
        quality_decision=green_quality_decision(),
        accepted_at="2026-06-27T10:00:00Z",
        existing_canonical_source=publication_v1.canonical_source,
    )
)
event_result_v2 = event_handler.handle(
    PublishCanonicalSourceEventCommand(
        publication_result=publication_v2,
        outbox=outbox,
        correlation_id="CORR-M004-T008-0002",
        causation_id="CMD-PUBLISH-CANONICAL-SOURCE-M004-T008-0002",
    )
)
assert_true(event_result_v2.created, "Une correction publiée doit produire un nouvel événement.")
assert_true(event_result_v2.superseded_created, "Une correction publiée doit produire l'événement de supersession.")
assert_equal(
    event_result_v2.superseded_event.event_type,
    "CanonicalSourceSuperseded",
    "La correction doit publier CanonicalSourceSuperseded avant CanonicalSourcePublished.",
)
assert_equal(
    dict(event_result_v2.superseded_event.payload),
    {
        "schema_version": "1.0",
        "canonical_source_id": publication_v1.canonical_ref.canonical_source_id,
        "previous_canonical_version_id": "CVER-M004-T008-0001",
        "new_canonical_version_id": "CVER-M004-T008-0002",
    },
    "La supersession doit relier l'ancienne et la nouvelle version sans texte ni stockage interne.",
)
assert_equal(event_result_v2.event.aggregate_version, 2, "La correction doit porter aggregate_version 2.")
assert_equal(
    tuple(entry.event.event_id for entry in outbox.pending_events()),
    (
        "EVT-CANONICAL-SOURCE-PUBLISHED-CVER-M004-T008-0001",
        "EVT-CANONICAL-SOURCE-SUPERSEDED-CVER-M004-T008-0002",
        "EVT-CANONICAL-SOURCE-PUBLISHED-CVER-M004-T008-0002",
    ),
    "Les événements outbox doivent rester ordonnés par version d'agrégat.",
)

# Given aucune publication acceptée n'existe.
# When l'intégration est appelée avant publication ou après QA RED.
# Then aucun événement n'est produit.
assert_raises(
    "publication",
    lambda: event_handler.handle(
        PublishCanonicalSourceEventCommand(
            publication_result=publication_v1.canonical_ref,
            outbox=outbox,
            correlation_id="CORR-M004-T008-0003",
            causation_id="CMD-PUBLISH-CANONICAL-SOURCE-M004-T008-0003",
        )
    ),
)
assert_raises(
    "QA GREEN obligatoire",
    lambda: publication_handler.handle(
        PublishCanonicalSourceCommand(
            source_document=source_document,
            docling_document=docling_fixture(source_document, "CVER-M004-T008-0003", "qa red")[0],
            text_authority_manifest=docling_fixture(source_document, "CVER-M004-T008-0003", "qa red")[1],
            quality_decision=red_quality_decision(),
            accepted_at="2026-06-27T10:30:00Z",
            existing_canonical_source=publication_v2.canonical_source,
        )
    ),
)
assert_equal(len(outbox.pending_events()), 3, "Une QA RED ne doit produire aucun événement outbox.")

# Given un modèle interne SP est fourni comme payload.
# When l'événement CanonicalSourcePublished est construit.
# Then le payload interne est refusé avant enveloppe.
assert_raises(
    "CanonicalSourceRef public obligatoire",
    lambda: build_canonical_source_published_event(
        canonical_ref=publication_v1.published_version,
        aggregate_version=1,
        correlation_id="CORR-M004-T008-0004",
        causation_id="CMD-PUBLISH-CANONICAL-SOURCE-M004-T008-0004",
    ),
)

print("Test d'acceptation T-008 événement CanonicalSourcePublished M-004: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m004_canonical_publication_event_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-008 événement CanonicalSourcePublished M-004: OK"
