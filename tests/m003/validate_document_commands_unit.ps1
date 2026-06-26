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
from app.source_processing.application.document_commands import (
    DiagnosisAlreadyRequestedError,
    DocumentCommandService,
    SourceNotFoundError,
    SourceUnreadableError,
)
from app.source_processing.application.start_document_processing import (
    DocumentInspection,
    InspectedPage,
)


class InMemoryOriginalSourceStore:
    def __init__(self):
        self.content_by_ref = {}

    def store_original(self, document_id, fingerprint, original_content):
        storage_ref = f"artifact:source_processing.original_sources/{document_id.value}/{fingerprint.value}.pdf"
        self.content_by_ref[storage_ref] = bytes(original_content)
        return storage_ref


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
        self.documents_by_id[source_document.document_id.value] = source_document

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
        document_id = processing_run.document_id.value
        if document_id in self.runs_by_document_id:
            raise AssertionError("Une tentative de diagnostic existante ne doit pas être remplacée.")
        self.runs_by_document_id[document_id] = processing_run
        self.saved_runs.append(processing_run)

    def find_by_document_id(self, document_id):
        return self.runs_by_document_id.get(document_id.value)


class FailingDiagnosisJobQueue:
    def __init__(self):
        self.submission_count = 0

    def submit(self, request, *, recalculate):
        self.submission_count += 1
        raise RuntimeError("runtime de jobs indisponible")


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


def metadata(edition):
    return {
        "title": "Trading Systems and Methods",
        "authors": ["Perry J. Kaufman"],
        "publication_year": 2020,
        "edition": edition,
    }


def build_service(job_queue=None):
    store = InMemoryOriginalSourceStore()
    source_repository = InMemorySourceDocumentRepository()
    inspector = ExplicitDocumentInspector()
    processing_repository = InMemoryProcessingRunRepository()
    configured_job_queue = job_queue if job_queue is not None else InMemoryJobQueue.empty(catalog=JOB_RUNTIME_CATALOG)
    service = DocumentCommandService(
        original_source_store=store,
        source_document_repository=source_repository,
        document_inspector=inspector,
        processing_run_repository=processing_repository,
        job_queue=configured_job_queue,
        diagnosis_configuration_hash="e" * 64,
        code_version="m003-t008-document-commands",
        model_version="diagnosis-policy-v1",
    )
    return service, source_repository, inspector, processing_repository, configured_job_queue


def readable_pdf(page_count):
    return (
        b"%PDF-1.7\n"
        + f"1 0 obj\n<< /Type /Catalog /Pages {page_count} >>\n".encode("ascii")
        + b"endobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"
    )


def register_readable_source(service, repository, inspector):
    acceptance = service.register_source_document(
        original_content=readable_pdf(2),
        bibliographic_metadata=metadata("1re édition"),
    )
    source_document = repository.documents_by_id[acceptance.document_id.value]
    inspector.inspections_by_ref[source_document.original_storage_ref.value] = DocumentInspection(
        source_page_count=2,
        pages=(
            InspectedPage(page_number=1, state="PRESENT"),
            InspectedPage(page_number=2, state="PRESENT"),
        ),
    )
    return acceptance, source_document


start_signature = inspect.signature(DocumentCommandService.start_document_processing)
if start_signature.parameters["document_id"].default is not inspect.Parameter.empty:
    raise AssertionError("start_document_processing.document_id ne doit pas avoir de valeur par défaut.")

service, source_repository, inspector, processing_repository, job_queue = build_service()

# Les commandes applicatives exposent l'enregistrement sans identifiant technique.
registered, source_document = register_readable_source(service, source_repository, inspector)
assert_equal(registered.document_id.value, source_document.document_id.value, "L'enregistrement doit retourner le DocumentId métier.")
assert_equal(registered.document_status, "REGISTERED", "L'enregistrement doit publier le statut documentaire.")
assert_equal(registered.duplicate, False, "Une création documentaire ne doit pas être signalée comme doublon.")
assert_true(not hasattr(registered, "original_storage_ref"), "La réponse applicative ne doit pas exposer le stockage interne.")
assert_true(not hasattr(registered, "fingerprint"), "La réponse applicative ne doit pas exposer l'empreinte comme contrat HTTP.")

duplicate = service.register_source_document(
    original_content=readable_pdf(2),
    bibliographic_metadata=metadata("1re édition"),
)
assert_equal(duplicate.document_id.value, registered.document_id.value, "Le doublon doit retourner le DocumentId existant.")
assert_equal(duplicate.document_status, "DUPLICATE_SOURCE", "Un doublon binaire doit être exposé distinctement d'une création.")
assert_equal(duplicate.duplicate, True, "La réponse applicative doit signaler le doublon binaire.")

# Une source illisible est une erreur métier explicite, pas un succès partiel.
unreadable_error = assert_raises(
    SourceUnreadableError,
    "PDF_CORRUPTED",
    lambda: service.register_source_document(
        original_content=b"%PDF-1.7\nobjet incomplet\n",
        bibliographic_metadata=metadata("édition corrompue"),
    ),
)
assert_equal(unreadable_error.reason, "PDF_CORRUPTED", "L'erreur source illisible doit conserver sa raison métier.")

# Une source inconnue ne doit pas démarrer de tentative ni de job.
assert_raises(
    SourceNotFoundError,
    "DOC-FFFFFFFFFFFFFFFF",
    lambda: service.start_document_processing(document_id="DOC-FFFFFFFFFFFFFFFF"),
)
assert_equal(len(processing_repository.saved_runs), 0, "Une source inconnue ne doit pas créer de tentative.")
assert_equal(job_queue.created_job_count(), 0, "Une source inconnue ne doit pas créer de job.")

# Une panne de soumission DIAGNOSE ne doit pas laisser de tentative orpheline.
failing_queue = FailingDiagnosisJobQueue()
failing_service, failing_source_repository, failing_inspector, failing_processing_repository, _ = build_service(
    job_queue=failing_queue
)
failing_registered, failing_source_document = register_readable_source(
    failing_service,
    failing_source_repository,
    failing_inspector,
)
assert_raises(
    RuntimeError,
    "runtime de jobs indisponible",
    lambda: failing_service.start_document_processing(document_id=failing_registered.document_id.value),
)
assert_equal(failing_queue.submission_count, 1, "La file DIAGNOSE doit être appelée une seule fois.")
assert_equal(len(failing_processing_repository.saved_runs), 0, "Une soumission DIAGNOSE échouée ne doit pas persister de tentative.")
assert_equal(
    failing_processing_repository.find_by_document_id(failing_registered.document_id),
    None,
    "Le retry doit rester possible après une panne de soumission DIAGNOSE.",
)

# La demande de diagnostic crée une tentative SP et un job DIAGNOSE idempotent, sans conversion.
diagnosis = service.start_document_processing(document_id=registered.document_id.value)
assert_equal(diagnosis.document_id.value, registered.document_id.value, "Le diagnostic doit conserver le DocumentId métier.")
assert_equal(diagnosis.diagnostic_status, "DIAGNOSTIC_REQUESTED", "Le statut de diagnostic doit être explicite.")
assert_true(not hasattr(diagnosis, "processing_run_id"), "L'identifiant de tentative ne doit pas être exposé comme contrat public.")
assert_equal(len(processing_repository.saved_runs), 1, "La première demande doit créer une seule tentative.")
assert_equal(job_queue.created_job_count(), 1, "La première demande doit créer un seul job.")
pending_job = job_queue.pending_jobs()[0]
assert_equal(pending_job.request.job_name, "DIAGNOSE", "Le job technique doit être DIAGNOSE.")
assert_equal(pending_job.request.idempotence_key.input_hash, source_document.fingerprint.value, "L'idempotence doit porter l'empreinte source.")
assert_true(
    all("CONVERT" not in job.request.job_name for job in job_queue.pending_jobs()),
    "La commande de diagnostic ne doit créer aucun job de conversion.",
)

# La répétition de la même commande est contrôlée par une erreur métier stable.
already_requested = assert_raises(
    DiagnosisAlreadyRequestedError,
    registered.document_id.value,
    lambda: service.start_document_processing(document_id=registered.document_id.value),
)
assert_equal(already_requested.document_id, registered.document_id.value, "L'erreur doit nommer le document concerné.")
assert_equal(job_queue.created_job_count(), 1, "La répétition ne doit pas créer de nouveau job.")
assert_equal(inspector.inspected_refs, [source_document.original_storage_ref.value], "La répétition ne doit pas relancer l'inspection.")

# Le domaine SP ne dépend d'aucun framework HTTP.
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

print("Tests unitaires T-008 commandes documentaires SP: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m003_document_commands_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-008 commandes documentaires SP: OK"
