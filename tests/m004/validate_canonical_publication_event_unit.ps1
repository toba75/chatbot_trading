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
from app.platform.event_bus import InMemoryTransactionalOutbox, ProducerStateMutation
from app.source_processing.application.publish_canonical_source import (
    PublishCanonicalSourceCommand,
    PublishCanonicalSourceHandler,
    StoredCanonicalArtifact,
)
from app.source_processing.application.publish_canonical_source_event import (
    CanonicalSourcePublishedEventResult,
    PublishCanonicalSourceEventCommand,
    PublishCanonicalSourceEventHandler,
    build_canonical_source_published_event,
    build_canonical_source_superseded_event,
    canonical_source_published_event_id_for,
    canonical_source_superseded_event_id_for,
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


def canonical_ref():
    return CanonicalSourceRef.from_payload(
        {
            "schema_version": "1.0",
            "canonical_source_id": "CSRC-M004-T008-UNIT",
            "document_id": "DOC-M004-T008-UNIT",
            "canonical_version_id": "CVER-M004-T008-UNIT-0001",
            "source_sha256": "a" * 64,
            "canonical_artifact_sha256": "b" * 64,
            "page_count": 2,
            "accepted_at": "2026-06-27T09:15:00Z",
            "quality_policy_version": "canonical-quality-event-unit-v1",
        }
    )


def registered_source():
    original_content = b"%PDF-1.7\ncanonical publication event unit\n%%EOF\n"
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
                "title": "Événement CanonicalSourcePublished unitaire",
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
        tool_version="docling-publication-event-unit-v1",
        artifact_hash=f"{page_number + 22:064x}",
        audit_artifact_ref=(
            "artifact:source_processing.page_conversion/"
            f"RUN-M004-T008-UNIT/page-{page_number:03d}.json"
        ),
        items=(conversion_item(page_number, text),),
    )


def page_outputs(suffix):
    return (
        page_artifact(1, f"Texte unitaire événement page 1 {suffix}."),
        page_artifact(2, f"Texte unitaire événement page 2 {suffix}."),
    )


def text_authority_manifest_for(outputs):
    policy = TextAuthoritySelectionPolicy(policy_version="text-authority-event-unit-v1")
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
        policy_version="canonical-quality-event-unit-v1",
        status=QualityDecisionStatus.PASS,
        publication_allowed=True,
        findings=(),
        publication_events=(),
    )


class RecordingCanonicalArtifactStore:
    def store_docling_json(self, request):
        return StoredCanonicalArtifact(
            artifact_ref=request.expected_artifact_ref,
            artifact_sha256=request.artifact_sha256,
        )


class MinimalOutbox:
    def __init__(self):
        self.entries = {}
        self.order = []

    def has_event(self, event_id):
        return event_id in self.entries

    def entry_for(self, event_id):
        return self.entries[event_id]

    def append_in_transaction(self, state_mutation, event):
        from app.platform.event_bus import OutboxEntry, OutboxMessageStatus

        entry = OutboxEntry(
            sequence=len(self.order) + 1,
            state_mutation=state_mutation,
            event=event,
            status=OutboxMessageStatus.PENDING,
            failure_reason=None,
        )
        self.entries[event.event_id] = entry
        self.order.append(event.event_id)
        return entry


public_ref = canonical_ref()
event = build_canonical_source_published_event(
    canonical_ref=public_ref,
    aggregate_version=3,
    correlation_id="CORR-M004-T008-UNIT",
    causation_id="CMD-PUBLISH-CANONICAL-SOURCE-M004-T008-UNIT",
)

assert_true(isinstance(event, EventEnvelope), "Le builder doit produire une EventEnvelope.")
assert_equal(event.event_id, "EVT-CANONICAL-SOURCE-PUBLISHED-CVER-M004-T008-UNIT-0001", "event_id doit dériver de la version canonique.")
assert_equal(canonical_source_published_event_id_for(public_ref.canonical_version_id), event.event_id, "event_id doit être stable.")
assert_equal(
    canonical_source_superseded_event_id_for(public_ref.canonical_version_id),
    "EVT-CANONICAL-SOURCE-SUPERSEDED-CVER-M004-T008-UNIT-0001",
    "event_id de supersession doit dériver de la nouvelle version.",
)
assert_equal(event.event_type, "CanonicalSourcePublished", "Le type d'événement doit être stable.")
assert_equal(event.event_version, 1, "event_version doit être 1.")
assert_equal(event.occurred_at, public_ref.accepted_at, "occurred_at doit venir du CanonicalSourceRef.")
assert_equal(event.aggregate_type, "CanonicalSource", "aggregate_type doit rester CanonicalSource.")
assert_equal(event.aggregate_id, public_ref.canonical_source_id, "aggregate_id doit venir du CanonicalSourceRef.")
assert_equal(event.aggregate_version, 3, "aggregate_version doit être celle fournie par la publication.")
assert_equal(event.producer_context, "SP", "SP doit être producteur unique.")
assert_equal(dict(event.payload), public_ref.to_payload(), "Le payload doit rester un CanonicalSourceRef.")
assert_equal(EventEnvelope.from_json(event.to_json()), event, "L'enveloppe doit rester sérialisable par le contrat M-001.")

for forbidden_key in (
    "artifact_ref",
    "audit_artifact_ref",
    "original_storage_ref",
    "page_outputs",
    "pages",
    "source_processing_path",
    "text",
    "tool_version",
):
    if forbidden_key in event.payload:
        raise AssertionError(f"Clé interne interdite exposée: {forbidden_key}")
for value in event.payload.values():
    if isinstance(value, str) and value.startswith("artifact:"):
        raise AssertionError("Chemin interne exposé dans le payload public.")

assert_raises(
    "canonical_version_id invalide",
    lambda: canonical_source_published_event_id_for("not-a-version-id"),
)
assert_raises(
    "aggregate_version invalide",
    lambda: build_canonical_source_published_event(
        canonical_ref=public_ref,
        aggregate_version=0,
        correlation_id="CORR-M004-T008-UNIT",
        causation_id="CMD-PUBLISH-CANONICAL-SOURCE-M004-T008-UNIT",
    ),
)
assert_raises(
    "CanonicalSourceRef public obligatoire",
    lambda: build_canonical_source_published_event(
        canonical_ref=public_ref.to_payload(),
        aggregate_version=1,
        correlation_id="CORR-M004-T008-UNIT",
        causation_id="CMD-PUBLISH-CANONICAL-SOURCE-M004-T008-UNIT",
    ),
)
superseded_event = build_canonical_source_superseded_event(
    canonical_ref=public_ref,
    previous_canonical_version_id="CVER-M004-T008-UNIT-0000",
    aggregate_version=3,
    correlation_id="CORR-M004-T008-UNIT",
    causation_id="CMD-PUBLISH-CANONICAL-SOURCE-M004-T008-UNIT",
)
assert_equal(superseded_event.event_type, "CanonicalSourceSuperseded", "Le type de supersession doit être stable.")
assert_equal(
    dict(superseded_event.payload),
    {
        "schema_version": "1.0",
        "canonical_source_id": public_ref.canonical_source_id,
        "previous_canonical_version_id": "CVER-M004-T008-UNIT-0000",
        "new_canonical_version_id": public_ref.canonical_version_id,
    },
    "Le payload de supersession doit rester borné aux deux versions.",
)

source_document = registered_source()
publication_handler = PublishCanonicalSourceHandler(artifact_store=RecordingCanonicalArtifactStore())
document_v1, manifest_v1 = docling_fixture(source_document, "CVER-M004-T008-UNIT-0002", "v1")
publication_result = publication_handler.handle(
    PublishCanonicalSourceCommand(
        source_document=source_document,
        docling_document=document_v1,
        text_authority_manifest=manifest_v1,
        quality_decision=green_quality_decision(),
        accepted_at="2026-06-27T11:15:00Z",
        existing_canonical_source=None,
    )
)

outbox = InMemoryTransactionalOutbox.empty()
handler = PublishCanonicalSourceEventHandler()
command = PublishCanonicalSourceEventCommand(
    publication_result=publication_result,
    outbox=outbox,
    correlation_id="CORR-M004-T008-UNIT-0002",
    causation_id="CMD-PUBLISH-CANONICAL-SOURCE-M004-T008-UNIT-0002",
)

first_result = handler.handle(command)
assert_true(isinstance(first_result, CanonicalSourcePublishedEventResult), "Le handler doit retourner un résultat typé.")
assert_true(first_result.created, "Le premier passage doit créer l'événement.")
assert_equal(first_result.outbox_entry.event, first_result.event, "Le résultat doit exposer l'événement inscrit.")
assert_equal(len(outbox.pending_events()), 1, "La première publication doit créer une seule entrée outbox.")
assert_equal(len(outbox.recorded_state_mutations()), 1, "La mutation productrice doit être enregistrée une seule fois.")

second_result = handler.handle(command)
assert_false(second_result.created, "Le retry doit être idempotent.")
assert_equal(second_result.outbox_entry, first_result.outbox_entry, "Le retry doit retourner l'entrée existante.")
assert_equal(len(outbox.pending_events()), 1, "Le retry ne doit pas créer d'entrée outbox.")
assert_equal(len(outbox.recorded_state_mutations()), 1, "Le retry ne doit pas créer de mutation productrice.")

minimal_outbox = MinimalOutbox()
minimal_result = handler.handle(
    PublishCanonicalSourceEventCommand(
        publication_result=publication_result,
        outbox=minimal_outbox,
        correlation_id="CORR-M004-T008-UNIT-PORT",
        causation_id="CMD-PUBLISH-CANONICAL-SOURCE-M004-T008-UNIT-PORT",
    )
)
assert_true(minimal_result.created, "Le handler doit accepter une outbox qui implémente le port minimal.")

document_v2, manifest_v2 = docling_fixture(source_document, "CVER-M004-T008-UNIT-0003", "v2")
publication_result_v2 = publication_handler.handle(
    PublishCanonicalSourceCommand(
        source_document=source_document,
        docling_document=document_v2,
        text_authority_manifest=manifest_v2,
        quality_decision=green_quality_decision(),
        accepted_at="2026-06-27T12:15:00Z",
        existing_canonical_source=publication_result.canonical_source,
    )
)
supersession_result = handler.handle(
    PublishCanonicalSourceEventCommand(
        publication_result=publication_result_v2,
        outbox=outbox,
        correlation_id="CORR-M004-T008-UNIT-0003",
        causation_id="CMD-PUBLISH-CANONICAL-SOURCE-M004-T008-UNIT-0003",
    )
)
assert_true(supersession_result.superseded_created, "Une correction doit inscrire CanonicalSourceSuperseded.")
assert_equal(
    supersession_result.superseded_event.event_type,
    "CanonicalSourceSuperseded",
    "La correction doit exposer l'événement de supersession.",
)

incoherent_outbox = InMemoryTransactionalOutbox.empty()
conflicting_event = build_canonical_source_published_event(
    canonical_ref=publication_result.canonical_ref,
    aggregate_version=1,
    correlation_id="CORR-M004-T008-OTHER",
    causation_id="CMD-PUBLISH-CANONICAL-SOURCE-M004-T008-OTHER",
)
incoherent_outbox.append_in_transaction(
    state_mutation=ProducerStateMutation(
        mutation_id="MUT-SP-CANONICAL-SOURCE-PUBLISHED-CVER-M004-T008-UNIT-0002",
        producer_context="SP",
        aggregate_type="CanonicalSource",
        aggregate_id=conflicting_event.aggregate_id,
        aggregate_version=conflicting_event.aggregate_version,
    ),
    event=conflicting_event,
)
assert_raises(
    "outbox incoh",
    lambda: handler.handle(
        PublishCanonicalSourceEventCommand(
            publication_result=publication_result,
            outbox=incoherent_outbox,
            correlation_id="CORR-M004-T008-UNIT-0002",
            causation_id="CMD-PUBLISH-CANONICAL-SOURCE-M004-T008-UNIT-0002",
        )
    ),
)
assert_raises(
    "outbox invalide",
    lambda: PublishCanonicalSourceEventCommand(
        publication_result=publication_result,
        outbox=[],
        correlation_id="CORR-M004-T008-UNIT-0002",
        causation_id="CMD-PUBLISH-CANONICAL-SOURCE-M004-T008-UNIT-0002",
    ),
)
assert_raises(
    "publication",
    lambda: PublishCanonicalSourceEventCommand(
        publication_result=publication_result.canonical_ref,
        outbox=outbox,
        correlation_id="CORR-M004-T008-UNIT-0002",
        causation_id="CMD-PUBLISH-CANONICAL-SOURCE-M004-T008-UNIT-0002",
    ),
)

print("Tests unitaires T-008 événement CanonicalSourcePublished M-004: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m004_canonical_publication_event_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-008 événement CanonicalSourcePublished M-004: OK"
