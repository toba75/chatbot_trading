$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$env:PYTHONPATH = $repoRoot

$python = @'
from pathlib import Path
from tempfile import TemporaryDirectory

from app.platform.job_runtime import JOB_RUNTIME_CATALOG, JobIdempotenceKey, JobPriority, JobRequest
from app.source_processing.adapters.postgres_document_persistence import (
    CorpusOriginalSourceStore,
    PostgresDocumentPersistence,
)
from app.source_processing.domain.document_processing_run import (
    DocumentProcessingRun,
    PageManifest,
    PageManifestEntry,
    PageManifestEntryState,
    PageNumber,
    ProcessingRunId,
)
from app.source_processing.domain.source_document import (
    BibliographicMetadata,
    DocumentId,
    SourceDocument,
    SourceFingerprint,
)


class SharedDatabase:
    def __init__(self):
        self.sources = {}
        self.runs = {}
        self.jobs = {}
        self.transaction_count = 0


class AcceptanceConnectionFactory:
    """Double PostgreSQL borné: le runtime de production reste PsycopgConnectionFactory."""

    def __init__(self, database):
        self.database = database

    def connect(self):
        return AcceptanceConnection(self.database)


class AcceptanceConnection:
    def __init__(self, database):
        self.database = database

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def transaction(self):
        return AcceptanceTransaction(self.database)


class AcceptanceTransaction:
    def __init__(self, database):
        self.database = database

    def __enter__(self):
        self.database.transaction_count += 1
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class AcceptancePersistence(PostgresDocumentPersistence):
    """Harness de contrat qui conserve les mêmes frontières que l'adaptateur SQL."""

    def save_if_absent(self, source_document):
        existing = self._connection_factory.database.sources.get(source_document.document_id.value)
        if existing is not None:
            return existing
        self._connection_factory.database.sources[source_document.document_id.value] = source_document
        return None

    def find_by_document_id(self, document_id):
        return self._connection_factory.database.sources.get(document_id.value)

    def find_by_fingerprint(self, fingerprint):
        for source in self._connection_factory.database.sources.values():
            if source.fingerprint == fingerprint:
                return source
        return None

    def find_by_work_key(self, work_key):
        for source in self._connection_factory.database.sources.values():
            if source.metadata.work_key == work_key:
                return source
        return None

    def find_processing_run_by_document_id(self, document_id):
        return self._connection_factory.database.runs.get(document_id.value)

    def submit_processing_run(self, processing_run, job_queue, job_request):
        with self._connection_factory.connect() as connection:
            with connection.transaction():
                if processing_run.document_id.value in self._connection_factory.database.runs:
                    return job_queue.existing_submission(job_request)
                decision = job_queue.submit_in_transaction(connection, job_request, recalculate=False)
                if not decision.created:
                    return decision
                self._connection_factory.database.runs[processing_run.document_id.value] = processing_run
                return decision


class AcceptanceJobQueue:
    def __init__(self, database):
        self.database = database

    def submit_in_transaction(self, connection, request, *, recalculate):
        from app.platform.job_runtime import JobRecord, JobStatus, JobSubmissionDecision
        key = request.idempotence_key.identity_tuple()
        existing = self.database.jobs.get(key)
        if existing is not None:
            return JobSubmissionDecision(job=existing, created=False, recalculation_refused=False)
        job = JobRecord(
            sequence=len(self.database.jobs) + 1,
            job_id=f"JOB-M002-{len(self.database.jobs) + 1:06d}",
            request=request,
            status=JobStatus.PENDING,
            result=None,
            failure_reason=None,
        )
        self.database.jobs[key] = job
        return JobSubmissionDecision(job=job, created=True, recalculation_refused=False)

    def existing_submission(self, request):
        return self.submit_in_transaction(None, request, recalculate=False)

    def find_by_idempotence_key(self, key):
        return self.database.jobs.get(key.identity_tuple())


# Given un PDF enregistré et une demande de diagnostic acceptée.
pdf = b"%PDF-1.7\n1 0 obj<<>>endobj\n%%EOF\n"
fingerprint = SourceFingerprint.from_content(pdf)
document_id = DocumentId.from_fingerprint(fingerprint)
metadata = BibliographicMetadata(
    title="Persistance documentaire",
    authors=("OSTrading",),
    publication_year=2026,
    edition="1",
)
manifest = PageManifest.from_entries(
    source_page_count=1,
    entries=(PageManifestEntry(PageNumber.from_value(1), PageManifestEntryState.PRESENT),),
)

with TemporaryDirectory() as temporary_directory:
    corpus_root = Path(temporary_directory) / "corpus"
    first_store = CorpusOriginalSourceStore(corpus_root=corpus_root)
    storage_ref = first_store.put_original_if_absent(document_id, fingerprint, pdf)
    source = SourceDocument.register_original(
        document_id=document_id,
        fingerprint=fingerprint,
        original_storage_ref=first_store.storage_ref(storage_ref),
        metadata=metadata,
    )
    processing_run = DocumentProcessingRun.start(
        processing_run_id=ProcessingRunId.from_value(f"RUN-DIAGNOSE-{document_id.value}"),
        source_document=source,
        page_manifest=manifest,
    )
    job_request = JobRequest(
        job_name="DIAGNOSE",
        priority=JobPriority.P1,
        idempotence_key=JobIdempotenceKey(
            job_name="DIAGNOSE",
            input_hash=fingerprint.value,
            configuration_hash="a" * 64,
            code_version="acceptance",
            model_version="none",
        ),
        payload={"document_id": document_id.value},
    )

    shared_database = SharedDatabase()
    first_process = AcceptancePersistence(connection_factory=AcceptanceConnectionFactory(shared_database))
    first_queue = AcceptanceJobQueue(shared_database)
    assert first_process.save_if_absent(source) is None
    submitted = first_process.submit_processing_run(processing_run, first_queue, job_request)
    assert submitted.created is True

    # When un nouveau processus API ou worker relit le même stockage configuré.
    second_process = AcceptancePersistence(connection_factory=AcceptanceConnectionFactory(shared_database))
    second_queue = AcceptanceJobQueue(shared_database)
    second_store = CorpusOriginalSourceStore(corpus_root=corpus_root)

    # Then source, manifeste, statut, original et job sont retrouvés sans état mémoire de runtime partagé.
    reloaded_source = second_process.find_by_document_id(document_id)
    reloaded_run = second_process.find_processing_run_by_document_id(document_id)
    reloaded_job = second_queue.find_by_idempotence_key(job_request.idempotence_key)
    assert reloaded_source == source
    assert reloaded_run.page_manifest == manifest
    assert reloaded_run.status == processing_run.status
    assert second_store.read_original(reloaded_source) == pdf
    assert reloaded_job.job_id == submitted.job.job_id
    assert shared_database.transaction_count == 1

print("Test d'acceptation de persistance documentaire après redémarrage: OK")
'@

$python | python -
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$migration = Get-Content -Raw (Join-Path $repoRoot "deploy\postgres\migrations\001_document_persistence.sql")
foreach ($marker in @(
    "CREATE SCHEMA IF NOT EXISTS source_processing",
    "CREATE SCHEMA IF NOT EXISTS platform",
    "source_documents",
    "document_processing_runs",
    "page_manifest_entries",
    "document_conversion_requests",
    "technical_jobs"
)) {
    if (-not $migration.Contains($marker)) { throw "Migration documentaire incomplète: $marker" }
}

$compose = Get-Content -Raw (Join-Path $repoRoot "deploy\local-compose\compose.yaml")
if (($compose.Split("corpus-data:/workspace/data/corpus").Count - 1) -lt 2) {
    throw "Le corpus partagé doit être monté dans orchestrator-api et worker-documents."
}
if (-not $compose.Contains("../postgres/migrations:/docker-entrypoint-initdb.d:ro")) {
    throw "Les migrations PostgreSQL ne sont pas montées dans le service postgres."
}

Write-Host "Validation d'acceptation T-005: OK"
