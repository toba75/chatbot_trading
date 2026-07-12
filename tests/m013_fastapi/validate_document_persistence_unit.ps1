$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$env:PYTHONPATH = $repoRoot

$python = @'
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory

from app.platform.configuration import load_application_configuration
from app.platform.job_runtime import (
    JOB_RUNTIME_CATALOG,
    JobIdempotenceKey,
    JobPriority,
    JobRecord,
    JobRequest,
    JobStatus,
    JobSubmissionDecision,
)
from app.platform.job_runtime.postgres import PostgresJobQueue
from app.platform.request_context import bind_trace_id, reset_trace_id
from app.source_processing.adapters.postgres_document_persistence import (
    CorpusOriginalSourceStore,
    OutboxSubmissionDecision,
    PostgresDocumentPersistence,
    build_document_persistence,
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


def assert_raises(expected_message, callback):
    try:
        callback()
    except ValueError as exc:
        assert str(exc) == expected_message, (str(exc), expected_message)
        return
    raise AssertionError(f"Erreur attendue absente: {expected_message}")


pdf = b"%PDF-1.7\noriginal-bit-a-bit\n%%EOF\n"
fingerprint = SourceFingerprint.from_content(pdf)
document_id = DocumentId.from_fingerprint(fingerprint)
metadata = BibliographicMetadata("Original", ("OSTrading",), 2026, "1")

with TemporaryDirectory() as temporary_directory:
    store = CorpusOriginalSourceStore(corpus_root=Path(temporary_directory) / "corpus")

    # Idempotence et concurrence: toutes les écritures convergent sur la même référence.
    def put():
        return store.put_original_if_absent(document_id, fingerprint, pdf)

    with ThreadPoolExecutor(max_workers=8) as executor:
        refs = tuple(executor.map(lambda _: put(), range(16)))
    assert len(set(refs)) == 1

    source = SourceDocument.register_original(
        document_id=document_id,
        fingerprint=fingerprint,
        original_storage_ref=store.storage_ref(refs[0]),
        metadata=metadata,
    )
    assert store.read_original(source) == pdf

    # Une substitution binaire sous la même identité est refusée explicitement.
    original_path = store.resolve_internal_path(source.original_storage_ref)
    original_path.write_bytes(b"%PDF-1.7\nsubstitution\n%%EOF\n")
    assert_raises("ORIGINAL_HASH_MISMATCH", lambda: store.read_original(source))

    # Aucun chemin interne n'est exposé par la référence métier.
    assert source.original_storage_ref.value.startswith("artifact:source_processing.original_sources/")
    assert str(Path(temporary_directory)) not in source.original_storage_ref.value


# La construction runtime ne lit que la configuration M13-config et ne propose aucun backend mémoire.
configuration = load_application_configuration(
    Path("config/application.yaml"),
    environment_snapshot={},
)
adapters = build_document_persistence(configuration)
assert isinstance(adapters.source_document_repository, PostgresDocumentPersistence)
assert isinstance(adapters.job_queue, PostgresJobQueue)


class TransactionState:
    def __init__(self):
        self.committed = False
        self.rolled_back = False


class Transaction:
    def __init__(self, state):
        self.state = state

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        if exc_type is None:
            self.state.committed = True
        else:
            self.state.rolled_back = True
        return False


class Connection:
    def __init__(self, state):
        self.state = state

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def transaction(self):
        return Transaction(self.state)


class ConnectionFactory:
    def __init__(self, state):
        self.state = state

    def connect(self):
        return Connection(self.state)


class FailingPersistence(PostgresDocumentPersistence):
    def _enqueue_job_outbox(self, *, connection, job_request, trace_id):
        assert trace_id == "TRACE-M13-PERSISTENCE-UNIT"
        return OutboxSubmissionDecision(outbox_id="OUTBOX-SP-0000000001", created=True)

    def _save_processing_run(self, connection, processing_run, *, insert_only=False):
        raise RuntimeError("PROCESSING_RUN_PERSISTENCE_FAILED")


class TransactionalQueue:
    def submit_in_transaction(self, connection, request, *, recalculate):
        job = JobRecord(
            sequence=1,
            job_id="JOB-M002-000001",
            request=request,
            status=JobStatus.PENDING,
            result=None,
            failure_reason=None,
        )
        return JobSubmissionDecision(job=job, created=True, recalculation_refused=False)


manifest = PageManifest.from_entries(
    source_page_count=1,
    entries=(PageManifestEntry(PageNumber.from_value(1), PageManifestEntryState.PRESENT),),
)
processing_run = DocumentProcessingRun.start(
    ProcessingRunId.from_value(f"RUN-DIAGNOSE-{document_id.value}"),
    source,
    manifest,
)
request = JobRequest(
    job_name="DIAGNOSE",
    priority=JobPriority.P1,
    idempotence_key=JobIdempotenceKey(
        job_name="DIAGNOSE",
        input_hash=fingerprint.value,
        configuration_hash="b" * 64,
        code_version="unit",
        model_version="none",
    ),
    payload={"document_id": document_id.value},
)
transaction_state = TransactionState()
failing_persistence = FailingPersistence(
    connection_factory=ConnectionFactory(transaction_state)
)
queue = PostgresJobQueue(
    connection_factory=ConnectionFactory(transaction_state),
    catalog=JOB_RUNTIME_CATALOG,
)
trace_token = bind_trace_id("TRACE-M13-PERSISTENCE-UNIT")
try:
    try:
        failing_persistence.submit_processing_run(processing_run, queue, request)
    except RuntimeError as exc:
        assert str(exc) == "PROCESSING_RUN_PERSISTENCE_FAILED"
    else:
        raise AssertionError("Échec de persistance attendu absent")
finally:
    reset_trace_id(trace_token)
assert transaction_state.rolled_back is True
assert transaction_state.committed is False

print("Tests unitaires du stockage original durable: OK")
'@

$python | python -
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$adapter = Get-Content -Raw (Join-Path $repoRoot "app\source_processing\adapters\postgres_document_persistence.py")
$jobRuntime = Get-Content -Raw (Join-Path $repoRoot "app\platform\job_runtime\postgres.py")
$postgresConnection = Get-Content -Raw (Join-Path $repoRoot "app\platform\postgres.py")

foreach ($forbidden in @("sqlite3", "json.dump(", "json.load(")) {
    if ($adapter.Contains($forbidden) -or $jobRuntime.Contains($forbidden) -or $postgresConnection.Contains($forbidden)) {
        throw "Backend métier interdit détecté: $forbidden"
    }
}
if ($adapter.Contains("InMemoryJobQueue") -or $jobRuntime.Contains("InMemoryJobQueue")) {
    throw "Fallback InMemoryJobQueue interdit dans le runtime durable."
}
foreach ($marker in @("submit_in_transaction", "ON CONFLICT", "FOR UPDATE", "PsycopgConnectionFactory")) {
    if (-not ($adapter.Contains($marker) -or $jobRuntime.Contains($marker) -or $postgresConnection.Contains($marker))) {
        throw "Garantie PostgreSQL absente: $marker"
    }
}

Write-Host "Validation unitaire T-005: OK"
