$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import ast
import inspect
from pathlib import Path
import sys

sys.path.insert(0, sys.argv[1])

from app.platform.job_runtime import InMemoryJobQueue, JOB_RUNTIME_CATALOG
from app.source_processing.adapters.document_http import (
    HttpRequest,
    SourceProcessingHttpAdapter,
)
from app.source_processing.application.document_commands import (
    CanonicalQualityRejectedError,
    ConversionAlreadyRequestedError,
    DocumentCommandService,
    DocumentConversionAcceptance,
    DocumentConversionState,
    DocumentConversionStatus,
    SourceNotFoundError,
    SourceNotRoutedError,
    SourceQuarantinedError,
)
from app.source_processing.application.start_document_processing import (
    DocumentInspection,
    InspectedPage,
)
from app.source_processing.domain.document_processing_run import (
    DiagnosticVersion,
    DocumentProcessingRun,
    DocumentProcessingRunStatus,
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


class InMemoryOriginalSourceStore:
    def __init__(self):
        self.content_by_ref = {}

    def put_original_if_absent(self, document_id, fingerprint, original_content):
        storage_ref = f"artifact:source_processing.original_sources/{document_id.value}/{fingerprint.value}.pdf"
        self.content_by_ref[storage_ref] = bytes(original_content)
        return storage_ref


class InMemorySourceDocumentRepository:
    def __init__(self):
        self.documents_by_id = {}

    def find_by_fingerprint(self, fingerprint):
        return None

    def find_by_work_key(self, work_key):
        return None

    def list_registered(self):
        return tuple(self.documents_by_id.values())

    def save(self, source_document):
        self.documents_by_id[source_document.document_id.value] = source_document

    def save_if_absent(self, source_document):
        self.documents_by_id[source_document.document_id.value] = source_document
        return None

    def find_by_document_id(self, document_id):
        return self.documents_by_id.get(document_id.value)


class ExplicitDocumentInspector:
    def __init__(self):
        self.inspections_by_ref = {}

    def inspect(self, original_storage_ref):
        return self.inspections_by_ref[original_storage_ref.value]


class InMemoryProcessingRunRepository:
    def __init__(self):
        self.runs_by_document_id = {}
        self.conversions_by_document_id = {}
        self.saved_runs = []
        self.submitted_conversion_requests = []

    def save(self, processing_run):
        self.runs_by_document_id[processing_run.document_id.value] = processing_run
        self.saved_runs.append(processing_run)

    def find_by_document_id(self, document_id):
        return self.runs_by_document_id.get(document_id.value)

    def submit_processing_run(self, processing_run, job_queue, job_request):
        submission = job_queue.submit(request=job_request, recalculate=False)
        if submission.created:
            self.save(processing_run)
        return submission

    def find_conversion_by_document_id(self, document_id):
        return self.conversions_by_document_id.get(document_id.value)

    def submit_conversion_request(self, conversion_state, job_queue, job_request):
        submission = job_queue.submit(request=job_request, recalculate=False)
        if submission.created:
            self.conversions_by_document_id[conversion_state.document_id.value] = conversion_state
            self.submitted_conversion_requests.append(conversion_state)
        return submission


class ScriptedDocumentCommands:
    def __init__(self):
        self.conversion_result = DocumentConversionAcceptance(
            document_id=DocumentId.from_value("DOC-1111111111111111"),
            conversion_status=DocumentConversionStatus.CONVERSION_REQUESTED,
            canonical_version_id=None,
        )
        self.conversion_error = None
        self.conversion_calls = []
        self.diagnosis_calls = []

    def register_source_document(self, *, original_content, bibliographic_metadata):
        raise AssertionError("Ce test ne couvre pas POST /v1/documents.")

    def start_document_processing(self, *, document_id):
        self.diagnosis_calls.append(document_id)
        raise AssertionError("POST /convert ne doit pas appeler /diagnose.")

    def request_document_conversion(self, *, document_id):
        self.conversion_calls.append(document_id)
        if self.conversion_error is not None:
            raise self.conversion_error
        return self.conversion_result


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def assert_raises(expected_type, expected_fragment, action):
    try:
        action()
    except expected_type as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
        return exc
    except Exception as exc:
        raise AssertionError(f"Type d'erreur inattendu: {type(exc).__name__}: {exc}") from exc
    raise AssertionError(f"Erreur attendue absente: {expected_type.__name__}")


def metadata():
    return {
        "title": "Commande de conversion documentaire",
        "authors": ["Perry J. Kaufman"],
        "publication_year": 2020,
        "edition": "1re edition",
    }


def source_document(suffix):
    original_content = f"%PDF-1.7\nunit conversion command {suffix}\n%%EOF\n".encode("utf-8")
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
    inspector = ExplicitDocumentInspector()
    processing_repository = InMemoryProcessingRunRepository()
    job_queue = InMemoryJobQueue.empty(catalog=JOB_RUNTIME_CATALOG)
    service = DocumentCommandService(
        original_source_store=InMemoryOriginalSourceStore(),
        source_document_repository=source_repository,
        document_inspector=inspector,
        processing_run_repository=processing_repository,
        job_queue=job_queue,
        diagnosis_configuration_hash="d" * 64,
        conversion_configuration_hash="c" * 64,
        code_version="m004-t009-document-commands",
        model_version="document-conversion-policy-v1",
    )
    return service, source_repository, inspector, processing_repository, job_queue


conversion_signature = inspect.signature(DocumentCommandService.request_document_conversion)
if conversion_signature.parameters["document_id"].default is not inspect.Parameter.empty:
    raise AssertionError("request_document_conversion.document_id ne doit pas avoir de valeur par defaut.")
init_signature = inspect.signature(DocumentCommandService.__init__)
if init_signature.parameters["conversion_configuration_hash"].default is not inspect.Parameter.empty:
    raise AssertionError("conversion_configuration_hash ne doit pas avoir de valeur par defaut.")
if not JOB_RUNTIME_CATALOG.includes("CONVERT_DOCUMENT"):
    raise AssertionError("CONVERT_DOCUMENT doit appartenir explicitement au catalogue M-002.")
if JOB_RUNTIME_CATALOG.includes("CanonicalSourcePublished"):
    raise AssertionError("Un event type ne doit pas etre accepte comme job.")

accepted_state = DocumentConversionState(
    document_id=DocumentId.from_value("DOC-1111111111111111"),
    conversion_status=DocumentConversionStatus.CANONICAL_ACCEPTED,
    canonical_version_id="CVER-M004-T009-0001",
    rejection_error_code=None,
)
accepted_payload = DocumentConversionAcceptance(
    document_id=accepted_state.document_id,
    conversion_status=accepted_state.conversion_status,
    canonical_version_id=accepted_state.canonical_version_id,
)
assert_equal(
    accepted_payload.canonical_version_id,
    "CVER-M004-T009-0001",
    "canonical_version_id doit etre autorise seulement apres acceptation canonique.",
)
assert_raises(
    ValueError,
    "canonical_version_id interdit",
    lambda: DocumentConversionAcceptance(
        document_id=DocumentId.from_value("DOC-1111111111111111"),
        conversion_status=DocumentConversionStatus.CONVERSION_REQUESTED,
        canonical_version_id="CVER-M004-T009-0001",
    ),
)
assert_raises(
    ValueError,
    "canonical_version_id obligatoire",
    lambda: DocumentConversionState(
        document_id=DocumentId.from_value("DOC-1111111111111111"),
        conversion_status=DocumentConversionStatus.CANONICAL_ACCEPTED,
        canonical_version_id=None,
        rejection_error_code=None,
    ),
)
assert_raises(
    ValueError,
    "rejection_error_code obligatoire",
    lambda: DocumentConversionState(
        document_id=DocumentId.from_value("DOC-1111111111111111"),
        conversion_status=DocumentConversionStatus.QA_REJECTED,
        canonical_version_id=None,
        rejection_error_code=None,
    ),
)

service, source_repository, inspector, processing_repository, job_queue = build_service()
document = source_document("direct")
source_repository.documents_by_id[document.document_id.value] = document
processing_repository.runs_by_document_id[document.document_id.value] = routed_run(document, "DIRECT")

# La commande applicative cree un job CONVERT_DOCUMENT idempotent et ne retourne pas l'identite technique du job.
conversion = service.request_document_conversion(document_id=document.document_id.value)
assert_equal(conversion.document_id, document.document_id, "La conversion doit conserver le DocumentId metier.")
assert_equal(conversion.conversion_status, DocumentConversionStatus.CONVERSION_REQUESTED, "Le statut public doit etre explicite.")
assert_equal(conversion.canonical_version_id, None, "La version canonique ne doit pas etre exposee avant acceptation.")
assert_true(not hasattr(conversion, "job_id"), "La reponse applicative ne doit pas exposer le job_id.")
assert_true(not hasattr(conversion, "processing_run_id"), "La reponse applicative ne doit pas exposer le processing_run_id.")

pending_job = job_queue.pending_jobs()[0]
assert_equal(pending_job.request.job_name, "CONVERT_DOCUMENT", "Le job de conversion doit etre global et explicite.")
assert_equal(pending_job.request.idempotence_key.job_name, "CONVERT_DOCUMENT", "La cle d'idempotence doit nommer le job de conversion.")
assert_equal(pending_job.request.idempotence_key.input_hash, document.fingerprint.value, "L'idempotence doit porter l'empreinte de source.")
assert_equal(pending_job.request.idempotence_key.configuration_hash, "c" * 64, "L'idempotence doit porter la configuration de conversion.")
assert_equal(pending_job.request.payload["document_id"], document.document_id.value, "Le payload de job doit porter le DocumentId.")
assert_equal(pending_job.request.payload["processing_run_id"], "RUN-M004-T009-DIRECT", "Le payload de job doit porter la tentative SP interne.")
assert_equal(pending_job.request.payload["routing_policy_version"], "routing-convert-v1", "Le payload de job doit porter la version de routage.")
assert_equal(pending_job.request.payload["route_count"], 2, "Le payload de job doit porter le nombre de routes.")
assert_equal(len(processing_repository.submitted_conversion_requests), 1, "La demande doit etre persistee une seule fois.")

assert_raises(
    ConversionAlreadyRequestedError,
    document.document_id.value,
    lambda: service.request_document_conversion(document_id=document.document_id.value),
)
assert_equal(job_queue.created_job_count(), 1, "La repetition ne doit pas creer un second job.")

unknown_error = assert_raises(
    SourceNotFoundError,
    "DOC-FFFFFFFFFFFFFFFF",
    lambda: service.request_document_conversion(document_id="DOC-FFFFFFFFFFFFFFFF"),
)
assert_equal(unknown_error.document_id, "DOC-FFFFFFFFFFFFFFFF", "L'erreur inconnue doit nommer le document.")

quarantined_document = source_document("quarantined")
source_repository.documents_by_id[quarantined_document.document_id.value] = quarantined_document.quarantine(
    "Quarantaine explicite."
)
assert_raises(
    SourceQuarantinedError,
    quarantined_document.document_id.value,
    lambda: service.request_document_conversion(document_id=quarantined_document.document_id.value),
)

not_routed_document = source_document("not-routed")
source_repository.documents_by_id[not_routed_document.document_id.value] = not_routed_document
processing_repository.runs_by_document_id[not_routed_document.document_id.value] = diagnosed_run(
    not_routed_document,
    "NOT-ROUTED",
)
not_routed_error = assert_raises(
    SourceNotRoutedError,
    "DIAGNOSED",
    lambda: service.request_document_conversion(document_id=not_routed_document.document_id.value),
)
assert_equal(not_routed_error.document_id, not_routed_document.document_id.value, "L'erreur route absente doit nommer le document.")

qa_rejected_document = source_document("qa-rejected")
source_repository.documents_by_id[qa_rejected_document.document_id.value] = qa_rejected_document
processing_repository.runs_by_document_id[qa_rejected_document.document_id.value] = routed_run(
    qa_rejected_document,
    "QA-REJECTED",
)
processing_repository.conversions_by_document_id[qa_rejected_document.document_id.value] = DocumentConversionState(
    document_id=qa_rejected_document.document_id,
    conversion_status=DocumentConversionStatus.QA_REJECTED,
    canonical_version_id=None,
    rejection_error_code="SOURCE_NOT_CANONICAL",
)
qa_error = assert_raises(
    CanonicalQualityRejectedError,
    qa_rejected_document.document_id.value,
    lambda: service.request_document_conversion(document_id=qa_rejected_document.document_id.value),
)
assert_equal(qa_error.error_code, "SOURCE_NOT_CANONICAL", "L'erreur QA doit porter le code public stable.")

# L'adaptateur HTTP ne decide ni route ni autorite; il transmet seulement le DocumentId.
scripted_commands = ScriptedDocumentCommands()
adapter = SourceProcessingHttpAdapter(document_commands=scripted_commands)
conversion_response = adapter.handle(
    HttpRequest(
        method="POST",
        path="/v1/documents/DOC-1111111111111111/convert",
        body={},
    )
)
assert_equal(conversion_response.status_code, 202, "Le mapping HTTP de conversion doit retourner 202.")
assert_equal(scripted_commands.conversion_calls, ["DOC-1111111111111111"], "L'adaptateur doit transmettre seulement le DocumentId.")
assert_equal(
    conversion_response.body,
    {
        "document_id": "DOC-1111111111111111",
        "conversion_status": "CONVERSION_REQUESTED",
    },
    "Le corps HTTP doit rester minimal tant que la version canonique n'est pas acceptee.",
)

scripted_commands.conversion_result = DocumentConversionAcceptance(
    document_id=DocumentId.from_value("DOC-1111111111111111"),
    conversion_status=DocumentConversionStatus.CANONICAL_ACCEPTED,
    canonical_version_id="CVER-M004-T009-0002",
)
accepted_response = adapter.handle(
    HttpRequest(
        method="POST",
        path="/v1/documents/DOC-1111111111111111/convert",
        body={},
    )
)
assert_equal(
    accepted_response.body,
    {
        "document_id": "DOC-1111111111111111",
        "conversion_status": "CANONICAL_ACCEPTED",
        "canonical_version_id": "CVER-M004-T009-0002",
    },
    "canonical_version_id doit apparaitre seulement apres acceptation canonique.",
)

scripted_commands.conversion_error = SourceNotRoutedError(
    document_id="DOC-2222222222222222",
    status="DIAGNOSED",
)
not_routed_response = adapter.handle(
    HttpRequest(
        method="POST",
        path="/v1/documents/DOC-2222222222222222/convert",
        body={},
    )
)
assert_equal(not_routed_response.status_code, 409, "Le mapping SOURCE_NOT_ROUTED doit retourner 409.")
assert_equal(not_routed_response.body["error_code"], "SOURCE_NOT_ROUTED", "Le code route absente doit etre stable.")

conversion_call_count_before_invalid_body = len(scripted_commands.conversion_calls)
invalid_body = adapter.handle(
    HttpRequest(
        method="POST",
        path="/v1/documents/DOC-2222222222222222/convert",
        body={"route_name": "SCAN_GRANITE"},
    )
)
assert_equal(invalid_body.status_code, 400, "Le body de conversion doit etre refuse.")
assert_equal(
    len(scripted_commands.conversion_calls),
    conversion_call_count_before_invalid_body,
    "Le body invalide ne doit pas declencher une nouvelle commande.",
)

scripted_commands.conversion_error = CanonicalQualityRejectedError(
    document_id="DOC-3333333333333333",
    error_code="PAGE_AUTHORITY_MISSING",
)
authority_missing_response = adapter.handle(
    HttpRequest(
        method="POST",
        path="/v1/documents/DOC-3333333333333333/convert",
        body={},
    )
)
assert_equal(authority_missing_response.status_code, 422, "PAGE_AUTHORITY_MISSING doit retourner 422.")
assert_equal(
    authority_missing_response.body,
    {"error_code": "PAGE_AUTHORITY_MISSING", "document_id": "DOC-3333333333333333"},
    "Le transport doit exposer seulement le code public et le document_id.",
)

# Le domaine SP ne depend d'aucun framework HTTP.
framework_roots = {"fastapi", "starlette", "flask", "django"}
domain_dir = Path(sys.argv[1]) / "app" / "source_processing" / "domain"
for path in domain_dir.glob("*.py"):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots = {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_roots = {node.module.split(".")[0]}
        else:
            imported_roots = set()
        forbidden = imported_roots & framework_roots
        if forbidden:
            raise AssertionError(f"Import framework interdit dans {path.name}: {sorted(forbidden)}")

print("Tests unitaires T-009 commande de conversion documentaire M-004: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m004_document_conversion_command_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-009 commande de conversion documentaire M-004: OK"
