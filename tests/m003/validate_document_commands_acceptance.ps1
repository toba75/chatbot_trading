$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

sys.path.insert(0, sys.argv[1])

from app.platform.job_runtime import InMemoryJobQueue, JOB_RUNTIME_CATALOG
from app.source_processing.adapters.document_http import (
    HttpRequest,
    SourceProcessingHttpAdapter,
)
from app.source_processing.application.document_commands import DocumentCommandService
from app.source_processing.application.start_document_processing import (
    DocumentInspection,
    InspectedPage,
)


class InMemoryOriginalSourceStore:
    def __init__(self):
        self.content_by_ref = {}

    def put_original_if_absent(self, document_id, fingerprint, original_content):
        storage_ref = f"artifact:source_processing.original_sources/{document_id.value}/{fingerprint.value}.pdf"
        existing_content = self.content_by_ref.get(storage_ref)
        if existing_content is not None:
            if existing_content != bytes(original_content):
                raise AssertionError("Un original existant ne doit pas être remplacé par un autre contenu.")
            return storage_ref
        self.content_by_ref[storage_ref] = bytes(original_content)
        return storage_ref

    def store_original(self, document_id, fingerprint, original_content):
        raise AssertionError("L'enregistrement doit utiliser put_original_if_absent.")


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
        raise AssertionError("L'enregistrement nominal doit utiliser les index fingerprint/work_key, pas un scan complet.")

    def save(self, source_document):
        key = source_document.document_id.value
        if key in self.documents_by_id:
            raise AssertionError("Un SourceDocument existant ne doit pas être remplacé.")
        self.documents_by_id[key] = source_document

    def save_if_absent(self, source_document):
        key = source_document.document_id.value
        existing_document = self.documents_by_id.get(key)
        if existing_document is not None:
            return existing_document
        self.documents_by_id[key] = source_document
        return None

    def find_by_document_id(self, document_id):
        return self.documents_by_id.get(document_id.value)


class ExplicitDocumentInspector:
    def __init__(self):
        self.inspections_by_ref = {}
        self.inspected_refs = []

    def inspect(self, original_storage_ref):
        self.inspected_refs.append(original_storage_ref.value)
        return self.inspections_by_ref[original_storage_ref.value]


class InMemoryProcessingRunRepository:
    def __init__(self):
        self.runs_by_document_id = {}
        self.saved_runs = []

    def save(self, processing_run):
        key = processing_run.document_id.value
        if key in self.runs_by_document_id:
            raise AssertionError("Une demande de diagnostic existante ne doit pas être remplacée.")
        self.runs_by_document_id[key] = processing_run
        self.saved_runs.append(processing_run)

    def find_by_document_id(self, document_id):
        return self.runs_by_document_id.get(document_id.value)

    def submit_processing_run(self, processing_run, job_queue, job_request):
        submission = job_queue.submit(request=job_request, recalculate=False)
        if not submission.created:
            return submission
        self.save(processing_run)
        return submission


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def metadata(edition):
    return {
        "title": "Trading Systems and Methods",
        "authors": ["Perry J. Kaufman"],
        "publication_year": 2020,
        "edition": edition,
    }


def post_document(adapter, original_content, bibliographic_metadata):
    return adapter.handle(
        HttpRequest(
            method="POST",
            path="/v1/documents",
            body={
                "original_content": original_content,
                "bibliographic_metadata": bibliographic_metadata,
            },
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


original_pdf = (
    b"%PDF-1.7\n"
    b"1 0 obj\n"
    b"<< /Type /Catalog /Pages 2 >>\n"
    b"endobj\n"
    b"trailer\n"
    b"<< /Root 1 0 R >>\n"
    b"%%EOF\n"
)
corrupted_pdf = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\n"

store = InMemoryOriginalSourceStore()
source_repository = InMemorySourceDocumentRepository()
inspector = ExplicitDocumentInspector()
processing_repository = InMemoryProcessingRunRepository()
job_queue = InMemoryJobQueue.empty(catalog=JOB_RUNTIME_CATALOG)
commands = DocumentCommandService(
    original_source_store=store,
    source_document_repository=source_repository,
    document_inspector=inspector,
    processing_run_repository=processing_repository,
    job_queue=job_queue,
    diagnosis_configuration_hash="d" * 64,
    code_version="m003-t008-document-commands",
    model_version="diagnosis-policy-v1",
)
adapter = SourceProcessingHttpAdapter(document_commands=commands)

# Given un client soumet un PDF original via POST /v1/documents.
# When la commande documentaire SP est appelée par l'adaptateur HTTP.
registered = post_document(adapter, original_pdf, metadata("1re édition"))

# Then l'enregistrement retourne une identité de document stable sans structure interne.
assert_equal(registered.status_code, 201, "L'enregistrement HTTP doit créer une source.")
assert_equal(set(registered.body.keys()), {"document_id", "document_status"}, "La réponse d'enregistrement doit rester publique.")
document_id = registered.body["document_id"]
assert_true(document_id.startswith("DOC-"), "L'identité documentaire doit utiliser le préfixe métier DOC.")
assert_equal(registered.body["document_status"], "REGISTERED", "Le statut documentaire doit être explicite.")

duplicate = post_document(adapter, original_pdf, metadata("1re édition"))
assert_equal(duplicate.status_code, 200, "Un doublon binaire ne doit pas être présenté comme une création.")
assert_equal(
    duplicate.body,
    {
        "document_id": document_id,
        "document_status": "DUPLICATE_SOURCE",
        "duplicate": True,
    },
    "La réponse HTTP doit signaler explicitement le doublon binaire.",
)

source_document = source_repository.documents_by_id[document_id]
inspector.inspections_by_ref[source_document.original_storage_ref.value] = DocumentInspection(
    source_page_count=2,
    pages=(
        InspectedPage(page_number=1, state="PRESENT"),
        InspectedPage(page_number=2, state="PRESENT"),
    ),
)

# Given le client demande ensuite le diagnostic du document enregistré.
# When POST /v1/documents/{id}/diagnose est appelé.
diagnosis = post_diagnose(adapter, document_id)

# Then le diagnostic est accepté explicitement sans exposer l'identifiant de tentative interne.
assert_equal(diagnosis.status_code, 202, "La demande de diagnostic doit être acceptée.")
assert_equal(set(diagnosis.body.keys()), {"document_id", "diagnostic_status"}, "La réponse de diagnostic ne doit pas exposer de structure interne.")
assert_equal(diagnosis.body["document_id"], document_id, "La réponse de diagnostic doit conserver l'identité métier.")
assert_equal(diagnosis.body["diagnostic_status"], "DIAGNOSTIC_REQUESTED", "Le statut de diagnostic doit être explicite.")

pending_jobs = job_queue.pending_jobs()
assert_equal(tuple(job.request.job_name for job in pending_jobs), ("DIAGNOSE",), "La demande doit créer uniquement un job DIAGNOSE.")
assert_true(
    all("CONVERT" not in job.request.job_name for job in pending_jobs),
    "La commande de diagnostic ne doit déclencher aucune conversion M-004.",
)

# Given une source inconnue est diagnostiquée.
# When l'endpoint de diagnostic est appelé.
unknown = post_diagnose(adapter, "DOC-FFFFFFFFFFFFFFFF")

# Then l'erreur métier est stable et ne devient pas un succès partiel.
assert_equal(unknown.status_code, 404, "Une source inconnue doit produire une erreur explicite.")
assert_equal(unknown.body["error_code"], "SOURCE_NOT_FOUND", "Le code d'erreur source inconnue doit être stable.")

# Given un PDF illisible est soumis.
# When l'enregistrement est appelé.
unreadable = post_document(adapter, corrupted_pdf, metadata("édition corrompue"))

# Then l'erreur source illisible est explicite et aucune source prête au diagnostic n'est créée.
assert_equal(unreadable.status_code, 422, "Une source illisible ne doit pas être acceptée.")
assert_equal(unreadable.body["error_code"], "SOURCE_UNREADABLE", "Le code d'erreur source illisible doit être stable.")
assert_equal(len(source_repository.documents_by_id), 1, "La source illisible ne doit pas être enregistrée.")
assert_equal(job_queue.created_job_count(), 1, "La source illisible ne doit créer aucun job.")

# Given le diagnostic du document a déjà été demandé.
# When le client répète la même commande.
already_requested = post_diagnose(adapter, document_id)

# Then l'idempotence est contrôlée par une erreur métier explicite sans recalcul.
assert_equal(already_requested.status_code, 409, "Un diagnostic déjà demandé doit être refusé explicitement.")
assert_equal(already_requested.body["error_code"], "DIAGNOSTIC_ALREADY_REQUESTED", "Le code d'erreur diagnostic déjà demandé doit être stable.")
assert_equal(job_queue.created_job_count(), 1, "La répétition ne doit pas créer de second job DIAGNOSE.")
assert_equal(inspector.inspected_refs, [source_document.original_storage_ref.value], "La répétition ne doit pas réinspecter l'original.")

print("Test d'acceptation T-008 commandes documentaires SP: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m003_document_commands_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-008 commandes documentaires SP: OK"
