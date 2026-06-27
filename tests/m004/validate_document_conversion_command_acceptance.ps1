$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

sys.path.insert(0, sys.argv[1])

from app.platform.job_runtime import InMemoryJobQueue, JOB_RUNTIME_CATALOG
from app.source_processing.application.canonical_audit_signals import (
    build_canonical_audit_signals,
)
from app.source_processing.adapters.document_http import (
    HttpRequest,
    SourceProcessingConversionHttpAdapter,
)
from app.source_processing.application.document_commands import (
    DocumentConversionCommandService,
    DocumentConversionState,
    DocumentConversionStatus,
)
from app.source_processing.domain.document_processing_run import (
    DiagnosticVersion,
    DocumentProcessingRun,
    PageDecision,
    PageDecisionState,
    PageDiagnosticSignals,
    PageManifest,
    PageManifestEntry,
    PageManifestEntryState,
    PageNumber,
    PageRoutingConfiguration,
    ProcessingRunId,
    RoutingPolicyVersion,
)
from app.source_processing.domain.source_document import (
    BibliographicMetadata,
    DocumentId,
    OriginalStorageRef,
    SourceDocument,
    SourceFingerprint,
)


class InMemorySourceDocumentRepository:
    def __init__(self):
        self.documents_by_id = {}

    def find_by_fingerprint(self, fingerprint):
        for document in self.documents_by_id.values():
            if document.fingerprint == fingerprint:
                return document
        return None

    def find_by_work_key(self, work_key):
        for document in self.documents_by_id.values():
            if document.metadata.work_key == work_key:
                return document
        return None

    def list_registered(self):
        return tuple(self.documents_by_id.values())

    def save(self, source_document):
        self.documents_by_id[source_document.document_id.value] = source_document

    def save_if_absent(self, source_document):
        existing_document = self.documents_by_id.get(source_document.document_id.value)
        if existing_document is not None:
            return existing_document
        self.documents_by_id[source_document.document_id.value] = source_document
        return None

    def find_by_document_id(self, document_id):
        return self.documents_by_id.get(document_id.value)


class InMemoryProcessingRunRepository:
    def __init__(self):
        self.runs_by_document_id = {}
        self.saved_runs = []

    def save(self, processing_run):
        self.runs_by_document_id[processing_run.document_id.value] = processing_run
        self.saved_runs.append(processing_run)

    def find_by_document_id(self, document_id):
        return self.runs_by_document_id.get(document_id.value)

    def submit_processing_run(self, processing_run, job_queue, job_request):
        submission = job_queue.submit(request=job_request, recalculate=False)
        if not submission.created:
            return submission
        self.save(processing_run)
        return submission

class InMemoryDocumentConversionRepository:
    def __init__(self):
        self.conversions_by_document_id = {}
        self.submitted_conversion_requests = []

    def find_conversion_by_document_id(self, document_id):
        return self.conversions_by_document_id.get(document_id.value)

    def submit_conversion_request(self, conversion_state, job_queue, job_request):
        submission = job_queue.submit(request=job_request, recalculate=False)
        if not submission.created:
            return submission
        self.conversions_by_document_id[conversion_state.document_id.value] = conversion_state
        self.submitted_conversion_requests.append(conversion_state)
        return submission


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def assert_last_audit_event(service, *, document_id, status, error_code, page_count):
    audit_event = service.canonical_audit_events()[-1]
    assert_equal(audit_event.document_id, document_id, "L'audit prÃ©-canonique doit nommer le document.")
    assert_equal(audit_event.phase, "document_conversion_request", "L'audit prÃ©-canonique doit nommer la phase de commande.")
    assert_equal(audit_event.status, status, "L'audit prÃ©-canonique doit tracer le statut public.")
    assert_equal(audit_event.error_code, error_code, "L'audit prÃ©-canonique doit tracer le code d'erreur public.")
    assert_equal(audit_event.page_count, page_count, "L'audit prÃ©-canonique doit tracer le nombre de pages sans contenu documentaire.")
    log_mapping = audit_event.to_log_mapping()
    assert_equal(log_mapping["canonical_version_id"], None, "L'audit prÃ©-canonique ne doit pas inventer de version canonique.")
    assert_equal(log_mapping["artifact_hash"], None, "L'audit prÃ©-canonique ne doit pas inventer de hash d'artefact.")
    build_canonical_audit_signals(service.canonical_audit_events())


def metadata():
    return {
        "title": "Commande de conversion documentaire",
        "authors": ["Perry J. Kaufman"],
        "publication_year": 2020,
        "edition": "1re edition",
    }


def source_document(suffix):
    original_content = f"%PDF-1.7\nconversion command {suffix}\n%%EOF\n".encode("utf-8")
    fingerprint = SourceFingerprint.from_content(original_content)
    document_id = DocumentId.from_fingerprint(fingerprint)
    storage_ref = OriginalStorageRef.from_value(
        f"artifact:source_processing.original_sources/{document_id.value}/{fingerprint.value}.pdf"
    )
    return SourceDocument.register_original(
        document_id=document_id,
        fingerprint=fingerprint,
        original_storage_ref=storage_ref,
        metadata=BibliographicMetadata.from_payload(metadata()),
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


def page_decision(page_number):
    return PageDecision(
        page_number=PageNumber.from_value(page_number),
        page_state=PageDecisionState.NATIVE_OK,
        signals=PageDiagnosticSignals(
            native_text_state="RELIABLE",
            image_state="NONE",
            existing_ocr_state="NONE",
            layout_complexity="SIMPLE",
            corruption_state="NONE",
            mixed_content_detected=False,
            has_table=False,
            has_formula=False,
        ),
        diagnostic_version=DiagnosticVersion.from_value("diag-convert-v1"),
        justification=f"Page {page_number} routable en texte natif fiable.",
    )


def routed_run(document, run_suffix):
    started_run = DocumentProcessingRun.start(
        processing_run_id=ProcessingRunId.from_value(f"RUN-M004-T009-{run_suffix}"),
        source_document=document,
        page_manifest=manifest_for(2),
    )
    diagnosed_run = started_run.record_page_diagnostics(
        (page_decision(1), page_decision(2))
    )
    return diagnosed_run.decide_route_plan(
        PageRoutingConfiguration(
            routing_policy_version=RoutingPolicyVersion.from_value("routing-convert-v1"),
            auto_confidence_min=0.90,
            benchmark_confidence_min=0.85,
        )
    )


def diagnosed_run(document, run_suffix):
    started_run = DocumentProcessingRun.start(
        processing_run_id=ProcessingRunId.from_value(f"RUN-M004-T009-{run_suffix}"),
        source_document=document,
        page_manifest=manifest_for(1),
    )
    return started_run.record_page_diagnostics((page_decision(1),))


def build_service():
    source_repository = InMemorySourceDocumentRepository()
    processing_repository = InMemoryProcessingRunRepository()
    conversion_repository = InMemoryDocumentConversionRepository()
    job_queue = InMemoryJobQueue.empty(catalog=JOB_RUNTIME_CATALOG)
    service = DocumentConversionCommandService(
        source_document_repository=source_repository,
        processing_run_repository=processing_repository,
        document_conversion_repository=conversion_repository,
        job_queue=job_queue,
        conversion_configuration_hash="c" * 64,
        code_version="m004-t009-document-commands",
        model_version="document-conversion-policy-v1",
    )
    return service, source_repository, processing_repository, conversion_repository, job_queue


def post_convert(adapter, document_id, body=None):
    return adapter.handle(
        HttpRequest(
            method="POST",
            path=f"/v1/documents/{document_id}/convert",
            body={} if body is None else body,
        )
    )


def post_diagnose(adapter, document_id):
    return adapter.handle(
        HttpRequest(
            method="POST",
            path=f"/v1/documents/{document_id}/diagnose",
            body={},
        )
    )


service, source_repository, processing_repository, conversion_repository, job_queue = build_service()
adapter = SourceProcessingConversionHttpAdapter(document_conversion_commands=service)
routed_source = source_document("accepted")
source_repository.documents_by_id[routed_source.document_id.value] = routed_source
processing_repository.runs_by_document_id[routed_source.document_id.value] = routed_run(
    routed_source,
    "ACCEPTED",
)

# Given un document enregistre, diagnostique et route.
# When le client appelle POST /v1/documents/{id}/convert.
accepted = post_convert(adapter, routed_source.document_id.value)

# Then la conversion canonique est acceptÃ©e comme job idempotent sans exposer d'identifiant technique.
assert_equal(accepted.status_code, 202, "La commande de conversion doit retourner 202.")
assert_equal(
    accepted.body,
    {
        "document_id": routed_source.document_id.value,
        "conversion_status": "CONVERSION_REQUESTED",
    },
    "La rÃ©ponse de conversion doit rester publique et minimale.",
)
for forbidden_key in (
    "job_id",
    "processing_run_id",
    "route_name",
    "authority",
    "source_sha256",
    "original_storage_ref",
):
    assert_true(forbidden_key not in accepted.body, f"La rÃ©ponse ne doit pas exposer {forbidden_key}.")
assert_last_audit_event(
    service,
    document_id=routed_source.document_id.value,
    status="REQUESTED",
    error_code=None,
    page_count=2,
)

pending_jobs = job_queue.pending_jobs()
assert_equal(tuple(job.request.job_name for job in pending_jobs), ("CONVERT_DOCUMENT",), "La commande doit crÃ©er le job global explicite de conversion.")
assert_equal(
    pending_jobs[0].request.payload["document_id"],
    routed_source.document_id.value,
    "Le payload de job doit porter le DocumentId public.",
)
assert_equal(len(conversion_repository.submitted_conversion_requests), 1, "La demande de conversion doit Ãªtre persistÃ©e une seule fois.")

# Given une source inconnue est convertie.
unknown = post_convert(adapter, "DOC-FFFFFFFFFFFFFFFF")
assert_equal(unknown.status_code, 404, "Une source inconnue doit retourner 404.")
assert_equal(
    unknown.body,
    {"error_code": "SOURCE_NOT_FOUND", "document_id": "DOC-FFFFFFFFFFFFFFFF"},
    "Le code source inconnue doit rester stable.",
)
assert_last_audit_event(
    service,
    document_id="DOC-FFFFFFFFFFFFFFFF",
    status="REJECTED",
    error_code="SOURCE_NOT_FOUND",
    page_count=0,
)

# Given une source en quarantaine existe.
quarantined_source = source_document("quarantined")
source_repository.documents_by_id[quarantined_source.document_id.value] = quarantined_source.quarantine(
    "Quarantaine explicite avant conversion."
)
quarantined = post_convert(adapter, quarantined_source.document_id.value)
assert_equal(quarantined.status_code, 409, "Une source en quarantaine doit retourner 409.")
assert_equal(quarantined.body["error_code"], "SOURCE_QUARANTINED", "Le code quarantaine doit Ãªtre stable.")
assert_last_audit_event(
    service,
    document_id=quarantined_source.document_id.value,
    status="QUARANTINED",
    error_code="SOURCE_QUARANTINED",
    page_count=0,
)

# Given un document enregistrÃ© n'a pas de route approuvÃ©e.
not_routed_source = source_document("not-routed")
source_repository.documents_by_id[not_routed_source.document_id.value] = not_routed_source
processing_repository.runs_by_document_id[not_routed_source.document_id.value] = diagnosed_run(
    not_routed_source,
    "NOT-ROUTED",
)
not_routed = post_convert(adapter, not_routed_source.document_id.value)
assert_equal(not_routed.status_code, 409, "Une source non routÃ©e doit retourner 409.")
assert_equal(
    not_routed.body,
    {"error_code": "SOURCE_NOT_ROUTED", "document_id": not_routed_source.document_id.value},
    "Le code route absente doit Ãªtre stable et ne pas exposer le statut interne.",
)
assert_last_audit_event(
    service,
    document_id=not_routed_source.document_id.value,
    status="REJECTED",
    error_code="SOURCE_NOT_ROUTED",
    page_count=1,
)

# Given une conversion a dÃ©jÃ  Ã©tÃ© demandÃ©e.
already_requested_source = source_document("already-requested")
source_repository.documents_by_id[already_requested_source.document_id.value] = already_requested_source
processing_repository.runs_by_document_id[already_requested_source.document_id.value] = routed_run(
    already_requested_source,
    "ALREADY",
)
conversion_repository.conversions_by_document_id[already_requested_source.document_id.value] = DocumentConversionState(
    document_id=already_requested_source.document_id,
    conversion_status=DocumentConversionStatus.CONVERSION_REQUESTED,
    canonical_version_id=None,
    rejection_error_code=None,
)
already_requested = post_convert(adapter, already_requested_source.document_id.value)
assert_equal(already_requested.status_code, 409, "Une conversion dÃ©jÃ  demandÃ©e doit retourner 409.")
assert_equal(already_requested.body["error_code"], "CONVERSION_ALREADY_REQUESTED", "Le code de doublon conversion doit Ãªtre stable.")
assert_last_audit_event(
    service,
    document_id=already_requested_source.document_id.value,
    status="REJECTED",
    error_code="CONVERSION_ALREADY_REQUESTED",
    page_count=2,
)

# Given la QA canonique a refusÃ© la publication.
qa_rejected_source = source_document("qa-rejected")
source_repository.documents_by_id[qa_rejected_source.document_id.value] = qa_rejected_source
processing_repository.runs_by_document_id[qa_rejected_source.document_id.value] = routed_run(
    qa_rejected_source,
    "QA-REJECTED",
)
conversion_repository.conversions_by_document_id[qa_rejected_source.document_id.value] = DocumentConversionState(
    document_id=qa_rejected_source.document_id,
    conversion_status=DocumentConversionStatus.QA_REJECTED,
    canonical_version_id=None,
    rejection_error_code="PAGE_AUTHORITY_MISSING",
)
qa_rejected = post_convert(adapter, qa_rejected_source.document_id.value)
assert_equal(qa_rejected.status_code, 422, "Une QA refusÃ©e doit retourner 422.")
assert_equal(
    qa_rejected.body,
    {"error_code": "PAGE_AUTHORITY_MISSING", "document_id": qa_rejected_source.document_id.value},
    "Le code d'autoritÃ© manquante doit Ãªtre atteignable sans raison interne.",
)
assert_last_audit_event(
    service,
    document_id=qa_rejected_source.document_id.value,
    status="REJECTED",
    error_code="PAGE_AUTHORITY_MISSING",
    page_count=2,
)

# Given le client tente d'imposer une route ou une autoritÃ© depuis HTTP.
# When l'endpoint de conversion reÃ§oit un corps non vide.
# Then le transport refuse la requÃªte au lieu de dÃ©cider Ã  la place du domaine.
invalid_body = post_convert(
    adapter,
    routed_source.document_id.value,
    body={"route_name": "SCAN_GRANITE", "authority": "GRANITE"},
)
assert_equal(invalid_body.status_code, 400, "Le transport ne doit pas accepter de dÃ©cision de route.")
assert_equal(invalid_body.body, {"error_code": "HTTP_REQUEST_INVALID", "field": "body"}, "Le corps de conversion doit Ãªtre vide.")
assert_equal(
    len(conversion_repository.submitted_conversion_requests),
    1,
    "Le body invalide ne doit pas persister de demande de conversion.",
)

# Given un diagnostic est demandé à l'adapter de conversion M-004.
# When POST /diagnose est appelé.
# Then l'adapter M-004 refuse le routage au lieu de déclencher un job de conversion.
diagnosed_source = source_document("diagnose-only")
source_repository.documents_by_id[diagnosed_source.document_id.value] = diagnosed_source
diagnosis = post_diagnose(adapter, diagnosed_source.document_id.value)
assert_equal(diagnosis.status_code, 404, "L'adapter de conversion ne doit pas router /diagnose.")
assert_equal(
    tuple(job.request.job_name for job in job_queue.pending_jobs()),
    ("CONVERT_DOCUMENT",),
    "Le diagnostic envoyé au port M-004 ne doit pas créer de job.",
)
assert_equal(
    len(conversion_repository.submitted_conversion_requests),
    1,
    "Le diagnostic ne doit pas persister de demande de conversion.",
)

print("Test d'acceptation T-009 commande de conversion documentaire M-004: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m004_document_conversion_command_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-009 commande de conversion documentaire M-004: OK"
