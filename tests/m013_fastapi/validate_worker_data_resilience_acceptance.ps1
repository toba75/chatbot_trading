$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
. (Join-Path $PSScriptRoot "resolve_m013_fastapi_python.ps1")
$python = Resolve-M013FastApiPython -RepoRoot $repoRoot

$env:M013_WORKER_DATA_REPO = $repoRoot
@'
import io
import tempfile
import time
from pathlib import Path

from pypdf import PdfWriter

from app.contracts.document_public_statuses import PublicDiagnosticStatus
from app.knowledge_access.domain.knowledge_projection import (
    KnowledgeProjection,
    ProjectionProfile,
)
from app.contracts.source_references import CanonicalSourceRef
from app.platform.job_runtime.postgres import JobLeaseConflictError
from app.source_processing.adapters.pypdf_diagnostic_inspector import (
    PdfDiagnosticInspector,
    PdfInspectionBudget,
    PdfInspectionError,
)
from app.source_processing.adapters.pdf_inspection_process import IsolatedPdfInspector
from app.source_processing.adapters.worker_runtime import JobLeaseHeartbeat
from app.source_processing.application.document_worker import DiagnosticInspector
from app.source_processing.domain.document_processing_run import (
    DocumentProcessingRun,
    DocumentProcessingRunStatus,
    PageManifest,
    PageManifestEntry,
    PageManifestEntryState,
    PageNumber,
    ProcessingRunId,
)
from app.source_processing.domain.source_document import (
    DocumentId,
    BibliographicMetadata,
    OriginalStorageRef,
    SourceDocument,
    SourceFingerprint,
)


class FakeStore:
    def __init__(self, path: Path):
        self.path = path

    def storage_ref(self, value):
        return value

    def resolve_internal_path(self, storage_ref):
        return self.path


class RenewingQueue:
    def __init__(self):
        self.renewals = 0
        self.finished = False

    def renew_lease(self, *, job_id, owner_id, claim_generation, claim_token, lease_seconds):
        assert job_id == "JOB-LONG" and owner_id == "WORKER-A" and lease_seconds == 1
        assert claim_generation == 1 and claim_token == "00000000-0000-4000-8000-000000000001"
        self.renewals += 1


class LostQueue(RenewingQueue):
    def renew_lease(self, **kwargs):
        raise JobLeaseConflictError()


def source_and_run():
    fingerprint = SourceFingerprint.from_content(b"worker-failure")
    document_id = DocumentId.from_fingerprint(fingerprint)
    source = SourceDocument.register_original(
        document_id=document_id,
        fingerprint=fingerprint,
        original_storage_ref=OriginalStorageRef.from_value(
            f"artifact:source_processing.original_sources/{document_id.value}/{fingerprint.value}.pdf"
        ),
        metadata=BibliographicMetadata(
            title="Worker failure",
            authors=("OSTrading",),
            publication_year=2026,
            edition="1",
        ),
    )
    manifest = PageManifest.from_entries(
        source_page_count=1,
        entries=(
            PageManifestEntry(
                page_number=PageNumber.from_value(1),
                state=PageManifestEntryState.PRESENT,
            ),
        ),
    )
    return source, DocumentProcessingRun.start(
        ProcessingRunId.from_value("RUN-M013-WORKER-FAIL"), source, manifest
    )


# Given un traitement plus long qu'un intervalle de heartbeat,
# When le worker conserve le job,
# Then plusieurs renouvellements empêchent un second claim actif.
queue = RenewingQueue()
heartbeat = JobLeaseHeartbeat(
    job_queue=queue,
    job_id="JOB-LONG",
    owner_id="WORKER-A",
    claim_generation=1,
    claim_token="00000000-0000-4000-8000-000000000001",
    lease_seconds=1,
    heartbeat_seconds=0.02,
)
heartbeat.start()
time.sleep(0.075)
heartbeat.assert_owned()
heartbeat.stop()
assert queue.renewals >= 2, queue.renewals

lost = JobLeaseHeartbeat(
    job_queue=LostQueue(),
    job_id="JOB-LONG",
    owner_id="WORKER-A",
    claim_generation=1,
    claim_token="00000000-0000-4000-8000-000000000001",
    lease_seconds=1,
    heartbeat_seconds=0.01,
)
lost.start()
time.sleep(0.03)
try:
    lost.assert_owned()
except JobLeaseConflictError:
    pass
else:
    raise AssertionError("JOB_LEASE_LOST doit interrompre la finalisation")
finally:
    lost.stop()

# Given un PDF réel mais vide et des budgets explicites,
# When l'adaptateur pypdf l'inspecte,
# Then il produit un signal borné sans importer pypdf dans la couche application.
with tempfile.TemporaryDirectory() as directory:
    pdf_path = Path(directory) / "blank.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    with pdf_path.open("wb") as stream:
        writer.write(stream)
    budget = PdfInspectionBudget(
        max_pdf_bytes=1_000_000,
        max_pages=4,
        max_elapsed_seconds=2.0,
        max_text_characters_per_page=10_000,
        max_total_text_characters=20_000,
        max_xobjects_per_page=16,
        max_process_memory_bytes=256 * 1024 * 1024,
    )
    inspector = PdfDiagnosticInspector(
        original_source_store=FakeStore(pdf_path),
        inspector=IsolatedPdfInspector(budget=budget),
    )
    assert isinstance(inspector, DiagnosticInspector)
    diagnostics = inspector.inspect("originals/a.pdf")
    assert len(diagnostics) == 1
    assert diagnostics[0].signals.corruption_state.value == "NONE"

    oversized = PdfDiagnosticInspector(
        original_source_store=FakeStore(pdf_path),
        inspector=IsolatedPdfInspector(budget=PdfInspectionBudget(
            max_pdf_bytes=8,
            max_pages=4,
            max_elapsed_seconds=2.0,
            max_text_characters_per_page=10_000,
            max_total_text_characters=20_000,
            max_xobjects_per_page=16,
            max_process_memory_bytes=256 * 1024 * 1024,
        )),
    )
    try:
        oversized.inspect("originals/a.pdf")
    except PdfInspectionError as exc:
        assert exc.error_code == "PDF_SIZE_BUDGET_EXCEEDED" and exc.retryable is False
    else:
        raise AssertionError("budget de taille PDF non appliqué")

# Given un diagnostic définitivement impossible,
# When la tentative est marquée en échec,
# Then le read-model public ne reste pas MANIFEST_CREATED/PENDING.
_, run = source_and_run()
failed = run.fail("PDF_CORRUPTED")
assert failed.status is DocumentProcessingRunStatus.FAILED
assert failed.failure_error_code == "PDF_CORRUPTED"
assert PublicDiagnosticStatus.from_value(failed.status.value).value == "FAILED"

# Given deux writers KA issus de la même version,
# When chacun produit une transition,
# Then la version attendue permet au repository PostgreSQL de refuser le writer obsolète.
projection = KnowledgeProjection.request(
    canonical_ref=CanonicalSourceRef(
        schema_version="1.0",
        canonical_source_id="CSRC-M013-KA-VERSION",
        document_id="DOC-M013-KA-VERSION",
        canonical_version_id="CVER-M013-KA-VERSION",
        source_sha256="a" * 64,
        canonical_artifact_sha256="b" * 64,
        page_count=1,
        accepted_at="2026-07-13T00:00:00Z",
        quality_policy_version="qa-v1",
    ),
    projection_profile=ProjectionProfile(
        projection_profile_id="PROF-M013-KA-VERSION",
        chunking_profile="chunk-v1",
        embedding_model="dense-v1",
        sparse_profile="sparse-v1",
        index_schema="index-v1",
    ),
)
assert projection.aggregate_version == 0
assert projection.start_build().aggregate_version == 1

repo = Path(__import__("os").environ["M013_WORKER_DATA_REPO"])
application_source = (repo / "app/source_processing/application/document_worker.py").read_text(encoding="utf-8")
assert "from pypdf" not in application_source
assert "source_processing.adapters" not in application_source
persistence_source = (repo / "app/source_processing/adapters/postgres_document_persistence.py").read_text(encoding="utf-8")
assert "def list_documents(self)" not in persistence_source
query_source = (repo / "app/source_processing/application/document_queries.py").read_text(encoding="utf-8")
for obsolete_port in ("SourceDocumentReadRepository", "ProcessingRunReadRepository", "DocumentConversionReadRepository"):
    assert obsolete_port not in query_source
ka_source = (repo / "app/knowledge_access/adapters/postgres_projection_read.py").read_text(encoding="utf-8")
assert "aggregate_version = %s" in ka_source
assert "KA_PROJECTION_VERSION_CONFLICT" in ka_source
migration = (repo / "deploy/postgres/migrations/006_worker_resilience_and_ka_version.sql").read_text(encoding="utf-8")
for marker in ("failure_error_code", "aggregate_version", "FAILED"):
    assert marker in migration

print("worker=lease-renewed; pdf=bounded-real-signals; failures=public; ka=optimistic-version")
'@ | & $python -B -
$exitCode = $LASTEXITCODE
Remove-Item Env:M013_WORKER_DATA_REPO -ErrorAction SilentlyContinue
if ($exitCode -ne 0) { throw "WORKER_DATA_RESILIENCE_ACCEPTANCE_RED" }

Write-Host "Résilience worker/données et concurrence KA: OK"
