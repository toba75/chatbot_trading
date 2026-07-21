"""Acceptation du câblage réel des commandes documentaires ASGI."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.platform.job_runtime import JobRecord, JobStatus, JobSubmissionDecision
from app.source_processing.adapters.document_http import SourceProcessingHttpAdapter
from app.source_processing.adapters.http import build_document_command_router
from app.source_processing.adapters.pdf_document_inspector import CorpusPdfDocumentInspector
from app.source_processing.adapters.pdf_inspection_process import (
    build_m13_isolated_pdf_inspector,
)
from app.source_processing.adapters.postgres_document_persistence import (
    CorpusOriginalSourceStore,
)
from app.source_processing.application.document_commands import DocumentCommandService


def _one_page_pdf() -> bytes:
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


class SharedPersistence:
    def __init__(self) -> None:
        self.sources: dict[str, object] = {}
        self.runs: dict[str, object] = {}
        self.jobs: dict[tuple[object, ...], JobRecord] = {}

    def find_by_fingerprint(self, fingerprint):
        return next(
            (source for source in self.sources.values() if source.fingerprint == fingerprint),
            None,
        )

    def find_by_work_key(self, work_key):
        return next(
            (
                source
                for source in self.sources.values()
                if source.metadata is not None and source.metadata.work_key == work_key
            ),
            None,
        )

    def find_by_document_id(self, document_id):
        return self.sources.get(document_id.value)

    def save_if_absent(self, source_document):
        existing = self.sources.get(source_document.document_id.value)
        if existing is not None:
            return existing
        self.sources[source_document.document_id.value] = source_document
        return None


class ProcessingRuns:
    def __init__(self, persistence: SharedPersistence) -> None:
        self.persistence = persistence

    def find_by_document_id(self, document_id):
        return self.persistence.runs.get(document_id.value)

    def save(self, processing_run) -> None:
        self.persistence.runs[processing_run.document_id.value] = processing_run

    def submit_processing_run(self, processing_run, job_request):
        key = job_request.idempotence_key.identity_tuple()
        existing = self.persistence.jobs.get(key)
        if existing is not None:
            return JobSubmissionDecision(existing, False, False)
        job = JobRecord(
            sequence=len(self.persistence.jobs) + 1,
            job_id=f"JOB-M002-{len(self.persistence.jobs) + 1:06d}",
            request=job_request,
            status=JobStatus.PENDING,
            result=None,
            failure_reason=None,
        )
        self.persistence.jobs[key] = job
        self.persistence.runs[processing_run.document_id.value] = processing_run
        return JobSubmissionDecision(job, True, False)


class ForbiddenConversionAdapter:
    def handle(self, request):
        raise AssertionError("La conversion ne doit pas être appelée.")


def test_validate_document_api_wiring_acceptance() -> None:
    pdf_content = _one_page_pdf()
    with TemporaryDirectory() as temporary_directory:
        persistence = SharedPersistence()
        original_store = CorpusOriginalSourceStore(
            corpus_root=Path(temporary_directory) / "corpus"
        )
        commands = DocumentCommandService(
            original_source_store=original_store,
            source_document_repository=persistence,
            document_inspector=CorpusPdfDocumentInspector(
                original_source_store=original_store,
                inspector=build_m13_isolated_pdf_inspector(),
            ),
            processing_run_repository=ProcessingRuns(persistence),
            environment="development",
            deployment_id="ostrading-development-local",
            diagnosis_configuration_hash="a" * 64,
            code_version="acceptance-test",
            model_version="document-diagnostic-v1",
        )
        application = FastAPI()
        application.include_router(
            build_document_command_router(
                document_http_adapter=SourceProcessingHttpAdapter(commands),
                document_conversion_http_adapter=ForbiddenConversionAdapter(),
                max_pdf_bytes=1024 * 1024,
            )
        )
        client = TestClient(application)

        rejected = client.post(
            "/v1/documents",
            files={
                "original_content": (
                    "faux.pdf",
                    b"%PDF-1.7\nmarqueurs seulement\n%%EOF\n",
                    "application/pdf",
                )
            },
        )
        assert rejected.status_code == 422
        assert rejected.json()["error_code"] == "SOURCE_UNREADABLE"

        registered = client.post(
            "/v1/documents",
            files={
                "original_content": (
                    "nom-ignore.pdf",
                    pdf_content,
                    "application/pdf",
                )
            },
        )
        assert registered.status_code == 201
        assert set(registered.json()) == {"document_id", "document_status"}
        document_id = registered.json()["document_id"]
        source = next(iter(persistence.sources.values()))
        assert source.document_id.value == document_id
        assert source.metadata is None
        assert original_store.read_original(source) == pdf_content

        diagnosed = client.post(f"/v1/documents/{document_id}/diagnose")
        assert diagnosed.status_code == 202
        assert diagnosed.json() == {
            "document_id": document_id,
            "diagnostic_status": "DIAGNOSTIC_REQUESTED",
        }
        assert len(persistence.runs) == 1
        assert len(persistence.jobs) == 1
        assert next(iter(persistence.jobs.values())).request.job_name == "DIAGNOSE"
