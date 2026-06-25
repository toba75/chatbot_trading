$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
from __future__ import annotations

import inspect
import sys

sys.path.insert(0, sys.argv[1])

from app.platform.job_runtime import (
    InMemoryJobQueue,
    InMemoryJobWorkerRegistry,
    JOB_RUNTIME_CATALOG,
    JobIdempotenceKey,
    JobPriority,
    JobRecord,
    JobRequest,
    JobStatus,
)


def assert_raises(expected_fragment: str, callback) -> None:
    try:
        callback()
    except ValueError as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


def key_for(job_name: str, input_hash: str, model_version: str) -> JobIdempotenceKey:
    return JobIdempotenceKey(
        job_name=job_name,
        input_hash=input_hash,
        configuration_hash="b" * 64,
        code_version="runtime-tests@2026.06.25",
        model_version=model_version,
    )


def request_for(job_name: str, priority: JobPriority, input_hash: str = "a" * 64) -> JobRequest:
    return JobRequest(
        job_name=job_name,
        priority=priority,
        idempotence_key=key_for(job_name, input_hash, "model@1"),
        payload={
            "request_id": f"REQ-{job_name}",
            "trace_id": "TRACE-M002-JOB-UNIT",
        },
    )


submit_signature = inspect.signature(InMemoryJobQueue.submit)
if submit_signature.parameters["recalculate"].default is not inspect._empty:
    raise AssertionError("submit.recalculate ne doit pas avoir de valeur par defaut.")

if not JOB_RUNTIME_CATALOG.includes("VERIFY_RESPONSE"):
    raise AssertionError("VERIFY_RESPONSE doit appartenir au catalogue strict.")
if JOB_RUNTIME_CATALOG.includes("CanonicalSourcePublished"):
    raise AssertionError("Un event type ne doit pas etre accepte comme job.")
if JOB_RUNTIME_CATALOG.includes("UNKNOWN_JOB"):
    raise AssertionError("Un job inconnu ne doit pas etre accepte.")

assert_raises("job inconnu", lambda: JOB_RUNTIME_CATALOG.require_known_job("UNKNOWN_JOB"))
assert_raises("job inconnu", lambda: JOB_RUNTIME_CATALOG.require_known_job("CanonicalSourcePublished"))

key_v1 = key_for("VERIFY_RESPONSE", "a" * 64, "model@1")
key_v2 = key_for("VERIFY_RESPONSE", "a" * 64, "model@2")
if key_v1 == key_v2:
    raise AssertionError("La version modele doit participer a la cle d'idempotence.")
if key_v1.identity_tuple() != (
    "VERIFY_RESPONSE",
    "a" * 64,
    "b" * 64,
    "runtime-tests@2026.06.25",
    "model@1",
):
    raise AssertionError(f"Cle d'idempotence incomplete: {key_v1.identity_tuple()}")

assert_raises("input_hash invalide", lambda: key_for("VERIFY_RESPONSE", "not-a-sha256", "model@1"))
assert_raises("configuration_hash vide", lambda: JobIdempotenceKey(
    job_name="VERIFY_RESPONSE",
    input_hash="a" * 64,
    configuration_hash="",
    code_version="runtime-tests@2026.06.25",
    model_version="model@1",
))
assert_raises("code_version vide", lambda: JobIdempotenceKey(
    job_name="VERIFY_RESPONSE",
    input_hash="a" * 64,
    configuration_hash="b" * 64,
    code_version="",
    model_version="model@1",
))
assert_raises("model_version vide", lambda: JobIdempotenceKey(
    job_name="VERIFY_RESPONSE",
    input_hash="a" * 64,
    configuration_hash="b" * 64,
    code_version="runtime-tests@2026.06.25",
    model_version="",
))

assert_raises(
    "idempotence_key incoherente",
    lambda: JobRequest(
        job_name="VERIFY_RESPONSE",
        priority=JobPriority.P1,
        idempotence_key=key_for("INDEX", "c" * 64, "model@1"),
        payload={"request_id": "REQ-INCOHERENT"},
    ),
)
assert_raises(
    "priority invalide",
    lambda: JobRequest(
        job_name="VERIFY_RESPONSE",
        priority="P1",
        idempotence_key=key_v1,
        payload={"request_id": "REQ-PRIORITY"},
    ),
)
assert_raises(
    "payload non objet",
    lambda: JobRequest(
        job_name="VERIFY_RESPONSE",
        priority=JobPriority.P1,
        idempotence_key=key_v1,
        payload=("not", "a", "mapping"),
    ),
)

queue = InMemoryJobQueue.empty(catalog=JOB_RUNTIME_CATALOG)
p4_submission = queue.submit(request=request_for("INDEX", JobPriority.P4, "4" * 64), recalculate=False)
p0_submission = queue.submit(request=request_for("VERIFY_RESPONSE", JobPriority.P0, "0" * 64), recalculate=False)
p5_submission = queue.submit(request=request_for("EMBED", JobPriority.P5, "5" * 64), recalculate=False)

if tuple(job.job_id for job in queue.pending_jobs()) != (
    p0_submission.job.job_id,
    p4_submission.job.job_id,
    p5_submission.job.job_id,
):
    raise AssertionError("Les jobs pending doivent etre ordonnes par priorite puis sequence.")
if p0_submission.job.status is not JobStatus.PENDING:
    raise AssertionError("Un job soumis doit etre pending.")
if queue.status_of(p0_submission.job.job_id) is not JobStatus.PENDING:
    raise AssertionError("Le statut pending doit etre observable.")

queue.mark_running(p0_submission.job.job_id)
if queue.status_of(p0_submission.job.job_id) is not JobStatus.RUNNING:
    raise AssertionError("mark_running doit rendre le statut running observable.")

succeeded = queue.mark_succeeded(
    job_id=p0_submission.job.job_id,
    result={"verification_status": "accepted"},
)
if succeeded.status is not JobStatus.SUCCEEDED:
    raise AssertionError("mark_succeeded doit rendre le statut succeeded observable.")
if succeeded.result != {"verification_status": "accepted"}:
    raise AssertionError("Le resultat du job doit etre conserve explicitement.")
if p0_submission.job.job_id in tuple(job.job_id for job in queue.pending_jobs()):
    raise AssertionError("Un job succeeded ne doit plus etre pending.")

duplicate_submission = queue.submit(request=request_for("VERIFY_RESPONSE", JobPriority.P0, "0" * 64), recalculate=False)
if duplicate_submission.created:
    raise AssertionError("Un succes identique ne doit pas creer de nouveau travail.")
if not duplicate_submission.recalculation_refused:
    raise AssertionError("Le refus de recalcul doit etre explicite.")
if duplicate_submission.job.result != {"verification_status": "accepted"}:
    raise AssertionError("Le resultat existant doit etre retourne pour le doublon.")

explicit_recalculation = queue.submit(request=request_for("VERIFY_RESPONSE", JobPriority.P0, "0" * 64), recalculate=True)
if not explicit_recalculation.created:
    raise AssertionError("recalculate=True doit creer un nouveau travail explicite.")

assert_raises("job inconnu", lambda: queue.submit(
    request=JobRequest(
        job_name="UNKNOWN_JOB",
        priority=JobPriority.P0,
        idempotence_key=key_for("UNKNOWN_JOB", "9" * 64, "model@1"),
        payload={"request_id": "REQ-UNKNOWN"},
    ),
    recalculate=False,
))
assert_raises("recalculate non booleen", lambda: queue.submit(
    request=request_for("VERIFY_RESPONSE", JobPriority.P0, "8" * 64),
    recalculate="false",
))
assert_raises("job inconnu", lambda: queue.submit(
    request=JobRequest(
        job_name="CanonicalSourcePublished",
        priority=JobPriority.P0,
        idempotence_key=key_for("CanonicalSourcePublished", "7" * 64, "model@1"),
        payload={"event_id": "EVT-M002-JOB-0001"},
    ),
    recalculate=False,
))
assert_raises("job inconnu", lambda: queue.status_of("JOB-M002-999999"))
assert_raises("result vide", lambda: queue.mark_succeeded(job_id=p4_submission.job.job_id, result={}))
assert_raises("failure_reason vide", lambda: queue.mark_failed(job_id=p4_submission.job.job_id, failure_reason=""))

handled_payloads = []
workers = InMemoryJobWorkerRegistry.from_workers(
    workers={
        "INDEX": lambda job: {"indexed_job": job.job_id},
        "EMBED": lambda job: {"embedded_job": job.job_id},
        "VERIFY_RESPONSE": lambda job: handled_payloads.append(job.request.payload) or {"verified_job": job.job_id},
    },
    catalog=JOB_RUNTIME_CATALOG,
)
executed = queue.execute_next(worker_registry=workers)
if executed.job_id != explicit_recalculation.job.job_id:
    raise AssertionError("Le worker doit executer le prochain job prioritaire.")
if executed.status is not JobStatus.SUCCEEDED:
    raise AssertionError("execute_next doit marquer le job succeeded.")
if handled_payloads != [explicit_recalculation.job.request.payload]:
    raise AssertionError("Le worker doit recevoir le job technique, sans event type.")

missing_worker_registry = InMemoryJobWorkerRegistry.from_workers(
    workers={"INDEX": lambda job: {"indexed_job": job.job_id}},
    catalog=JOB_RUNTIME_CATALOG,
)
assert_raises("worker absent", lambda: missing_worker_registry.worker_for("VERIFY_RESPONSE"))
assert_raises("worker non appelable", lambda: InMemoryJobWorkerRegistry.from_workers(
    workers={"VERIFY_RESPONSE": "not-callable"},
    catalog=JOB_RUNTIME_CATALOG,
))

failing_queue = InMemoryJobQueue.empty(catalog=JOB_RUNTIME_CATALOG)
failing_submission = failing_queue.submit(
    request=request_for("VERIFY_RESPONSE", JobPriority.P0, "f" * 64),
    recalculate=False,
)
failing_registry = InMemoryJobWorkerRegistry.from_workers(
    workers={"VERIFY_RESPONSE": lambda job: (_ for _ in ()).throw(RuntimeError("worker verification failed"))},
    catalog=JOB_RUNTIME_CATALOG,
)
try:
    failing_queue.execute_next(worker_registry=failing_registry)
except RuntimeError as exc:
    if str(exc) != "worker verification failed":
        raise AssertionError(f"Erreur worker altérée: {exc}")
else:
    raise AssertionError("Erreur worker attendue absente.")
failed_job = failing_queue.job_for(failing_submission.job.job_id)
if failed_job.status is not JobStatus.FAILED:
    raise AssertionError(f"Un worker en échec doit marquer le job failed: {failed_job.status}")
if failed_job.failure_reason != "worker verification failed":
    raise AssertionError(f"Raison d'échec worker absente: {failed_job.failure_reason}")
retry_after_failure = failing_queue.submit(
    request=request_for("VERIFY_RESPONSE", JobPriority.P0, "f" * 64),
    recalculate=False,
)
if not retry_after_failure.created:
    raise AssertionError("Un échec ne doit pas bloquer indéfiniment la clé d'idempotence.")

duplicate_active_request = request_for("VERIFY_RESPONSE", JobPriority.P1, "d" * 64)
duplicate_active_job_1 = JobRecord(
    sequence=1,
    job_id="JOB-M002-100001",
    request=duplicate_active_request,
    status=JobStatus.PENDING,
    result=None,
    failure_reason=None,
)
duplicate_active_job_2 = JobRecord(
    sequence=2,
    job_id="JOB-M002-100002",
    request=duplicate_active_request,
    status=JobStatus.RUNNING,
    result=None,
    failure_reason=None,
)
assert_raises(
    "clé d'idempotence active dupliquée",
    lambda: InMemoryJobQueue(catalog=JOB_RUNTIME_CATALOG, jobs=(duplicate_active_job_1, duplicate_active_job_2)),
)

print("Tests unitaires file de jobs idempotente M-002: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m002_job_runtime_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires file de jobs idempotente M-002: OK"
