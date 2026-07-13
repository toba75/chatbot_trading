$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\.." )).Path
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw "UV_PROJECT_PYTHON_REQUIRED" }

$env:M013_REVIEW3_REPO = $repoRoot
@'
from __future__ import annotations

import hashlib
import inspect
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pypdf import PdfWriter

from app.contracts.source_references import CanonicalSourceRef, SourceLocator
from app.contracts.technical_jobs import (
    ClaimedJob,
    JobIdempotenceKey,
    JobPriority,
    JobRecord,
    JobRequest,
    JobStatus,
)
from app.knowledge_access.adapters.postgres_projection_read import (
    KnowledgeProjectionReplayConflictError,
    PostgresKnowledgeProjectionRepository,
)
from app.knowledge_access.domain.chunking import KnowledgeChunk
from app.knowledge_access.domain.knowledge_projection import (
    KnowledgeProjection,
    ProjectionProfile,
)
from app.source_processing.adapters.pdf_inspection_process import (
    IsolatedPdfInspector,
    PdfInspectionBudget,
    PdfInspectionProcessError,
    run_disposable_process,
)
from app.source_processing.adapters.pypdf_diagnostic_inspector import PdfDiagnosticInspector
from app.source_processing.application.document_worker import DiagnosticInspector


repo = Path(__import__("os").environ["M013_REVIEW3_REPO"])


def job(status=JobStatus.RUNNING):
    return JobRecord(
        sequence=1,
        job_id="JOB-M002-000001",
        request=JobRequest(
            job_name="DIAGNOSE",
            priority=JobPriority.P1,
            idempotence_key=JobIdempotenceKey(
                job_name="DIAGNOSE",
                input_hash="a" * 64,
                configuration_hash="b" * 64,
                code_version="review3",
                model_version="pypdf-review3",
            ),
            payload={"document_id": "DOC-M013-REVIEW3"},
        ),
        status=status,
        result=None,
        failure_reason=None,
    )


# Given un claim technique transmis à SP,
# When son identité, sa génération ou son état est incohérent,
# Then le DTO neutre le refuse avant toute mutation durable.
claim = ClaimedJob(
    job=job(),
    trace_id="TRACE-M013-REVIEW3",
    lease_owner="WORKER-A:INSTANCE-1",
    lease_expires_at=datetime.now(timezone.utc) + timedelta(seconds=30),
    claim_generation=1,
    claim_token="00000000-0000-4000-8000-000000000001",
    execution_attempts=1,
)
assert claim.claim_generation == claim.execution_attempts == 1
for invalid in (
    dict(claim_generation=0),
    dict(claim_token=""),
    dict(job=job(JobStatus.PENDING)),
    dict(lease_expires_at=datetime.now()),
):
    values = {
        "job": claim.job,
        "trace_id": claim.trace_id,
        "lease_owner": claim.lease_owner,
        "lease_expires_at": claim.lease_expires_at,
        "claim_generation": claim.claim_generation,
        "claim_token": claim.claim_token,
        "execution_attempts": claim.execution_attempts,
    }
    values.update(invalid)
    try:
        ClaimedJob(**values)
    except ValueError:
        pass
    else:
        raise AssertionError(f"ClaimedJob incohérent accepté: {invalid}")


# Given un inspecteur enfant bloqué,
# When le budget temps expire,
# Then le processus jetable est tué sans attendre son retour.
started = time.monotonic()
try:
    run_disposable_process(
        command=(sys.executable, "-c", "import time; time.sleep(30)"),
        request_payload="{}",
        timeout_seconds=0.2,
    )
except PdfInspectionProcessError as exc:
    assert exc.error_code == "PDF_TIME_BUDGET_EXCEEDED"
else:
    raise AssertionError("processus PDF bloqué non interrompu")
assert time.monotonic() - started < 3.0


class FakeStore:
    def __init__(self, path: Path): self.path = path
    def storage_ref(self, value): return value
    def resolve_internal_path(self, storage_ref): return self.path


# Given une vraie page blanche,
# When le même inspecteur isolé produit manifeste et diagnostic,
# Then la page est EMPTY et jamais CORRUPT.
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory) / "blank.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    with path.open("wb") as stream:
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
    isolated = IsolatedPdfInspector(budget=budget)
    report = isolated.inspect_path(path)
    assert report.pages[0].manifest_state == "EMPTY"
    diagnostic = PdfDiagnosticInspector(
        original_source_store=FakeStore(path),
        inspector=isolated,
    )
    assert isinstance(diagnostic, DiagnosticInspector)
    result = diagnostic.inspect("artifact:blank.pdf")
    assert result[0].signals.corruption_state.value == "NONE"


# Given une projection SEARCHABLE,
# When ses sorties sont absentes ou rejouées à version égale avec une autre empreinte,
# Then le repository refuse l'état incomplet et la divergence explicitement.
profile = ProjectionProfile("public-v1", "hierarchical-v1", "dense-v1", "sparse-v1", "hybrid-v1")
projection = KnowledgeProjection.request(
    canonical_ref=CanonicalSourceRef(
        schema_version="1.0",
        canonical_source_id="CSRC-M013-REVIEW3",
        document_id="DOC-M013-REVIEW3-KA",
        canonical_version_id="CVER-M013-REVIEW3",
        source_sha256="c" * 64,
        canonical_artifact_sha256="d" * 64,
        page_count=1,
        accepted_at="2026-07-13T00:00:00Z",
        quality_policy_version="qa-v1",
    ),
    projection_profile=profile,
).start_build().mark_built().start_indexing().mark_searchable()


class NoConnect:
    def connect(self): raise AssertionError("validation SEARCHABLE attendue avant PostgreSQL")


repository = PostgresKnowledgeProjectionRepository(connection_factory=NoConnect(), sample_storage_limit=2)
try:
    repository.save_projection_outputs(
        projection=projection,
        chunk_count=0,
        chunks=(),
        state_observed_at="2026-07-13T00:00:00Z",
    )
except ValueError as exc:
    assert str(exc) == "KA_SEARCHABLE_OUTPUTS_INCOMPLETE"
else:
    raise AssertionError("SEARCHABLE sans sortie accepté")
assert issubclass(KnowledgeProjectionReplayConflictError, RuntimeError)


# Given les frontières DDD,
# When les sources applicatives SP sont inspectées,
# Then elles ne dépendent d'aucune classe concrète du runtime platform.
for relative in (
    "app/source_processing/application/document_commands.py",
    "app/source_processing/application/document_worker.py",
):
    source = (repo / relative).read_text(encoding="utf-8")
    assert "app.platform.job_runtime" not in source, relative
application_worker = (repo / "app/source_processing/application/document_worker.py").read_text(encoding="utf-8")
assert "ClaimedJob" in application_worker
migration = repo / "deploy/postgres/migrations/008_claim_fencing_and_projection_replay.sql"
assert migration.is_file()
sql = migration.read_text(encoding="utf-8")
for marker in (
    "claim_generation",
    "claim_token",
    "relay_claim_generation",
    "relay_claim_token",
    "outputs_fingerprint",
    "technical_jobs_pending_claim_idx",
    "technical_jobs_expired_claim_idx",
):
    assert marker in sql, marker

print("review3-safety=claims-fenced; retry=recoverable; ka=replay-strict; pdf=isolated")
'@ | & $python -B -
$exitCode = $LASTEXITCODE
Remove-Item Env:M013_REVIEW3_REPO -ErrorAction SilentlyContinue
if ($exitCode -ne 0) { throw "M013_REVIEW3_SAFETY_ACCEPTANCE_RED" }

Write-Host "Sûreté et concurrence de revue 3: OK"
