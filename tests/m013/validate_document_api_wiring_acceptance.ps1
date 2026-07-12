$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, sys.argv[1])

from app.platform.configuration import load_application_configuration
from app.platform.job_runtime import JobRecord, JobStatus, JobSubmissionDecision
from app.platform.orchestrator_asgi import create_orchestrator_app
from app.platform.orchestrator_composition import (
    DependencyReadiness,
    OrchestratorCompositionRoot,
)
from app.source_processing.adapters.document_http import SourceProcessingHttpAdapter
from app.source_processing.adapters.pdf_document_inspector import CorpusPdfDocumentInspector
from app.source_processing.adapters.postgres_document_persistence import CorpusOriginalSourceStore
from app.source_processing.application.document_commands import DocumentCommandService


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Attendu={expected!r}, obtenu={actual!r}")


def one_page_pdf():
    objects = (
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n",
    )
    payload = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for item in objects:
        offsets.append(len(payload))
        payload.extend(item)
    xref_offset = len(payload)
    payload.extend(b"xref\n0 4\n0000000000 65535 f \n")
    for offset in offsets[1:]:
        payload.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    payload.extend(
        b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n"
        + str(xref_offset).encode("ascii")
        + b"\n%%EOF\n"
    )
    return bytes(payload)


def multipart_body(*, boundary, pdf_content):
    parts = []

    def field(name, value):
        parts.extend(
            (
                f"--{boundary}\r\n".encode("ascii"),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("ascii"),
                str(value).encode("utf-8"),
                b"\r\n",
            )
        )

    parts.extend(
        (
            f"--{boundary}\r\n".encode("ascii"),
            b'Content-Disposition: form-data; name="original_content"; filename="nom-ignore.pdf"\r\n',
            b"Content-Type: application/pdf\r\n\r\n",
            pdf_content,
            b"\r\n",
        )
    )
    field("title", "Document de validation")
    field("authors", "Équipe OSTrading")
    field("publication_year", "2026")
    field("edition", "1")
    parts.append(f"--{boundary}--\r\n".encode("ascii"))
    return b"".join(parts)


async def asgi_post(application, path, body, content_type):
    sent_messages = []
    delivered = False

    async def receive():
        nonlocal delivered
        if delivered:
            return {"type": "http.disconnect"}
        delivered = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        sent_messages.append(message)

    await application(
        {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": b"",
            "root_path": "",
            "headers": [
                (b"content-type", content_type.encode("ascii")),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
            "client": ("asgi-test", 50000),
            "server": ("orchestrator-api", 8080),
            "state": {},
        },
        receive,
        send,
    )
    start = next(message for message in sent_messages if message["type"] == "http.response.start")
    raw_response = b"".join(
        message.get("body", b"")
        for message in sent_messages
        if message["type"] == "http.response.body"
    )
    return start["status"], json.loads(raw_response.decode("utf-8"))


class SharedPersistence:
    def __init__(self):
        self.sources = {}
        self.runs = {}
        self.jobs = {}

    def find_by_fingerprint(self, fingerprint):
        return next((source for source in self.sources.values() if source.fingerprint == fingerprint), None)

    def find_by_work_key(self, work_key):
        return next((source for source in self.sources.values() if source.metadata.work_key == work_key), None)

    def find_by_document_id(self, document_id):
        return self.sources.get(document_id.value)

    def save_if_absent(self, source_document):
        existing = self.sources.get(source_document.document_id.value)
        if existing is not None:
            return existing
        self.sources[source_document.document_id.value] = source_document
        return None

    def save(self, processing_run):
        self.runs[processing_run.document_id.value] = processing_run

    def find_processing_run(self, document_id):
        return self.runs.get(document_id.value)

    def submit_processing_run(self, processing_run, job_queue, job_request):
        submission = job_queue.submit(job_request, recalculate=False)
        if submission.created:
            self.runs[processing_run.document_id.value] = processing_run
        return submission


class ProcessingRuns:
    def __init__(self, persistence):
        self.persistence = persistence

    def save(self, processing_run):
        self.persistence.save(processing_run)

    def find_by_document_id(self, document_id):
        return self.persistence.find_processing_run(document_id)

    def submit_processing_run(self, processing_run, job_queue, job_request):
        return self.persistence.submit_processing_run(processing_run, job_queue, job_request)


class PersistentJobQueue:
    def __init__(self, persistence):
        self.persistence = persistence

    def submit(self, request, *, recalculate):
        key = request.idempotence_key.identity_tuple()
        existing = self.persistence.jobs.get(key)
        if existing is not None:
            return JobSubmissionDecision(job=existing, created=False, recalculation_refused=False)
        job = JobRecord(
            sequence=len(self.persistence.jobs) + 1,
            job_id=f"JOB-M002-{len(self.persistence.jobs) + 1:06d}",
            request=request,
            status=JobStatus.PENDING,
            result=None,
            failure_reason=None,
        )
        self.persistence.jobs[key] = job
        return JobSubmissionDecision(job=job, created=True, recalculation_refused=False)


class ReadyDependency:
    async def open(self):
        return None

    async def close(self):
        return None

    def readiness(self):
        return DependencyReadiness(name="document-store", status="ready")


async def scenario(repo_root):
    configuration = load_application_configuration(
        config_path=repo_root / "config" / "application.example.yaml",
        environment_snapshot={},
    )
    pdf_content = one_page_pdf()
    with TemporaryDirectory() as temporary_directory:
        persistence = SharedPersistence()
        original_store = CorpusOriginalSourceStore(
            corpus_root=Path(temporary_directory) / "corpus"
        )
        commands = DocumentCommandService(
            original_source_store=original_store,
            source_document_repository=persistence,
            document_inspector=CorpusPdfDocumentInspector(original_source_store=original_store),
            processing_run_repository=ProcessingRuns(persistence),
            job_queue=PersistentJobQueue(persistence),
            diagnosis_configuration_hash="a" * 64,
            code_version="acceptance-test",
            model_version="document-diagnostic-v1",
        )
        adapter = SourceProcessingHttpAdapter(document_commands=commands)

        def root_factory(validated_configuration):
            return OrchestratorCompositionRoot(
                configuration=validated_configuration,
                dependencies=(ReadyDependency(),),
                document_http_adapter=adapter,
                document_upload_max_bytes=1024 * 1024,
            )

        application = create_orchestrator_app(
            configuration=configuration,
            composition_root_factory=root_factory,
        )
        boundary = "ost-m013-fastapi-wiring"
        body = multipart_body(boundary=boundary, pdf_content=pdf_content)

        async with application.router.lifespan_context(application):
            registered_status, registered = await asgi_post(
                application,
                "/v1/documents",
                body,
                f"multipart/form-data; boundary={boundary}",
            )
            assert_equal(registered_status, 201, "L'enregistrement ASGI doit créer la source.")
            assert_equal(set(registered), {"document_id", "document_status"}, "La réponse ne doit exposer aucun champ interne.")
            document_id = registered["document_id"]
            source = next(iter(persistence.sources.values()))
            assert_equal(source.document_id.value, document_id, "Le DocumentId public doit rester celui de SP.")
            assert_equal(original_store.read_original(source), pdf_content, "L'original doit être conservé bit à bit.")
            assert_equal(source.metadata.title, "Document de validation", "Le nom de fichier ne doit pas devenir métadonnée.")

            diagnosed_status, diagnosed = await asgi_post(
                application,
                f"/v1/documents/{document_id}/diagnose",
                b"",
                "application/octet-stream",
            )
            assert_equal(diagnosed_status, 202, "Le diagnostic doit être accepté.")
            assert_equal(
                diagnosed,
                {"document_id": document_id, "diagnostic_status": "DIAGNOSTIC_REQUESTED"},
                "Le contrat public ne doit exposer ni run ni référence interne.",
            )
            assert_equal(len(persistence.runs), 1, "La tentative DIAGNOSE doit être persistée.")
            assert_equal(len(persistence.jobs), 1, "Le job DIAGNOSE doit être persisté.")
            job = next(iter(persistence.jobs.values()))
            assert_equal(job.request.job_name, "DIAGNOSE", "Aucun diagnostic simulé ne doit remplacer le job.")


asyncio.run(scenario(Path(sys.argv[1])))
print("Test d'acceptation raccordement commandes documentaires ASGI: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_document_wiring_" + [System.Guid]::NewGuid().ToString("N") + ".py")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    $env:PYTHONIOENCODING = "utf-8"
    $output = & $pythonExecutable -B $pythonScriptPath $repoRoot 2>&1
    $exitCode = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
    Remove-Item -LiteralPath $pythonScriptPath -Force
}

if ($exitCode -ne 0) {
    throw ($output -join "`n")
}

Write-Host "Test d'acceptation raccordement commandes documentaires ASGI: OK"
