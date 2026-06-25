$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
from __future__ import annotations

import sys

sys.path.insert(0, sys.argv[1])

from app.platform.job_runtime import (
    InMemoryJobQueue,
    JOB_RUNTIME_CATALOG,
    JobIdempotenceKey,
    JobPriority,
    JobRequest,
    JobStatus,
)


def idempotence_key(model_version: str) -> JobIdempotenceKey:
    return JobIdempotenceKey(
        job_name="VERIFY_RESPONSE",
        input_hash="a" * 64,
        configuration_hash="b" * 64,
        code_version="response-verifier@2026.06.25",
        model_version=model_version,
    )


def verify_response_request(model_version: str) -> JobRequest:
    return JobRequest(
        job_name="VERIFY_RESPONSE",
        priority=JobPriority.P0,
        idempotence_key=idempotence_key(model_version),
        payload={
            "request_id": "REQ-M002-JOB-VERIFY",
            "response_id": "ANS-000001",
        },
    )


def batch_index_request() -> JobRequest:
    return JobRequest(
        job_name="INDEX",
        priority=JobPriority.P4,
        idempotence_key=JobIdempotenceKey(
            job_name="INDEX",
            input_hash="c" * 64,
            configuration_hash="d" * 64,
            code_version="indexer@2026.06.25",
            model_version="embedding-model@1",
        ),
        payload={
            "projection_id": "KPROJ-000001",
            "batch_id": "BATCH-000001",
        },
    )


# Given un job VERIFY_RESPONSE a deja reussi avec la meme cle d'idempotence.
queue = InMemoryJobQueue.empty(catalog=JOB_RUNTIME_CATALOG)
first_submission = queue.submit(
    request=verify_response_request("gemma-4@2026-06-25"),
    recalculate=False,
)
queue.mark_succeeded(
    job_id=first_submission.job.job_id,
    result={
        "verification_status": "accepted",
        "claim_count": 4,
    },
)

batch_submission = queue.submit(
    request=batch_index_request(),
    recalculate=False,
)

# When le meme job est soumis sans option explicite de recalcul.
duplicate_submission = queue.submit(
    request=verify_response_request("gemma-4@2026-06-25"),
    recalculate=False,
)

# Then la file refuse le recalcul et retourne le resultat existant sans creer de travail.
if duplicate_submission.created:
    raise AssertionError("Le doublon exact ne doit pas creer de nouveau travail.")
if not duplicate_submission.recalculation_refused:
    raise AssertionError("Le refus de recalcul doit etre observable.")
if duplicate_submission.job.job_id != first_submission.job.job_id:
    raise AssertionError("Le doublon doit retourner le job reussi existant.")
if duplicate_submission.job.status is not JobStatus.SUCCEEDED:
    raise AssertionError(f"Le statut existant doit etre returned succeeded: {duplicate_submission.job.status}")
if duplicate_submission.job.result != {
    "verification_status": "accepted",
    "claim_count": 4,
}:
    raise AssertionError(f"Le resultat existant doit etre retourne: {duplicate_submission.job.result}")

# And une version modele differente et un recalcul explicite creent chacun un travail distinct.
model_change_submission = queue.submit(
    request=verify_response_request("gemma-4@2026-06-26"),
    recalculate=False,
)
explicit_recalculation = queue.submit(
    request=verify_response_request("gemma-4@2026-06-25"),
    recalculate=True,
)

if not model_change_submission.created:
    raise AssertionError("Une version modele differente doit creer un nouveau travail.")
if not explicit_recalculation.created:
    raise AssertionError("Un recalcul explicite doit creer un nouveau travail.")
if queue.created_job_count() != 4:
    raise AssertionError(f"Nombre de travaux crees inattendu: {queue.created_job_count()}")

pending_order = tuple(job.request.job_name for job in queue.pending_jobs())
if pending_order != ("VERIFY_RESPONSE", "VERIFY_RESPONSE", "INDEX"):
    raise AssertionError(f"Les jobs P0 doivent preceder le job P4: {pending_order}")
if batch_submission.job.job_id not in tuple(job.job_id for job in queue.pending_jobs()):
    raise AssertionError("Le job batch P4 doit rester en attente apres les jobs P0.")

print("Test d'acceptation file de jobs idempotente M-002: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m002_job_runtime_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation file de jobs idempotente M-002: OK"
