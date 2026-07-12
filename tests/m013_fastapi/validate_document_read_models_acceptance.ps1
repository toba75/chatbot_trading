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

sys.path.insert(0, sys.argv[1])

from app.platform.configuration import load_application_configuration
from app.platform.orchestrator_asgi import create_orchestrator_app
from app.platform.orchestrator_composition import DependencyReadiness, OrchestratorCompositionRoot
from app.source_processing.adapters.query_http import build_document_query_router
from app.source_processing.application.document_commands import (
    DocumentConversionState,
    DocumentConversionStatus,
)
from app.source_processing.application.document_queries import DocumentQueryService, DocumentStateSnapshot
from app.source_processing.domain.document_processing_run import (
    DiagnosticVersion,
    DocumentProcessingRun,
    PageDecision,
    PageDecisionState,
    PageDiagnosticSignals,
    PageManifest,
    PageManifestEntry,
    PageManifestEntryState,
    PageNumber,
    PageRoutingConfiguration,
    ProcessingRunId,
    RoutingPolicyVersion,
)
from app.source_processing.domain.source_document import (
    BibliographicMetadata,
    DocumentId,
    OriginalStorageRef,
    SourceDocument,
    SourceFingerprint,
)


class SourceRepository:
    def __init__(self, documents):
        self.documents = tuple(reversed(documents))

    def list_documents(self):
        return self.documents

    def find_by_document_id(self, document_id):
        return next(
            (document for document in self.documents if document.document_id == document_id),
            None,
        )


class ProcessingRepository:
    def __init__(self, runs):
        self.runs = {run.document_id.value: run for run in runs}

    def find_by_document_id(self, document_id):
        return self.runs.get(document_id.value)


class ConversionRepository:
    def __init__(self, conversions):
        self.conversions = {
            conversion.document_id.value: conversion for conversion in conversions
        }

    def find_conversion_by_document_id(self, document_id):
        return self.conversions.get(document_id.value)


class SnapshotRepository:
    def __init__(self, sources, runs, conversions):
        self.sources = sources
        self.runs = runs
        self.conversions = conversions

    def list_document_snapshots(self, *, limit, after_document_id):
        assert limit == 101
        assert after_document_id is None
        return tuple(self.find_document_snapshot(document.document_id) for document in self.sources.list_documents())

    def find_document_snapshot(self, document_id):
        source = self.sources.find_by_document_id(document_id)
        if source is None:
            return None
        return DocumentStateSnapshot(
            source_document=source,
            processing_run=self.runs.find_by_document_id(document_id),
            conversion=self.conversions.find_conversion_by_document_id(document_id),
        )


class ReadyDependency:
    async def open(self):
        return None

    async def close(self):
        return None

    def readiness(self):
        return DependencyReadiness(name="document-read-models", status="ready")


def source(label):
    content = f"%PDF-1.7\n{label}\n%%EOF\n".encode("utf-8")
    fingerprint = SourceFingerprint.from_content(content)
    document_id = DocumentId.from_fingerprint(fingerprint)
    return SourceDocument.register_original(
        document_id=document_id,
        fingerprint=fingerprint,
        original_storage_ref=OriginalStorageRef.from_value(
            f"artifact:source_processing.original_sources/{document_id.value}/{fingerprint.value}.pdf"
        ),
        metadata=BibliographicMetadata(
            title=f"Document {label}",
            authors=("Auteur explicite",),
            publication_year=2026,
            edition="1",
        ),
    )


def manifest(page_count):
    return PageManifest.from_entries(
        source_page_count=page_count,
        entries=tuple(
            PageManifestEntry(
                page_number=PageNumber.from_value(number),
                state=PageManifestEntryState.PRESENT,
            )
            for number in range(1, page_count + 1)
        ),
    )


def decision(number):
    return PageDecision(
        page_number=PageNumber.from_value(number),
        page_state=PageDecisionState.NATIVE_OK,
        signals=PageDiagnosticSignals(
            native_text_state="RELIABLE",
            image_state="NONE",
            existing_ocr_state="NONE",
            layout_complexity="SIMPLE",
            corruption_state="NONE",
            mixed_content_detected=False,
            has_table=number == 2,
            has_formula=False,
        ),
        diagnostic_version=DiagnosticVersion.from_value("diag-read-v1"),
        justification=f"Diagnostic public page {number}.",
    )


def requested_run(document, suffix):
    return DocumentProcessingRun.start(
        processing_run_id=ProcessingRunId.from_value(f"RUN-M013-T007-{suffix}"),
        source_document=document,
        page_manifest=manifest(2),
    )


def routed_run(document, suffix):
    diagnosed = requested_run(document, suffix).record_page_diagnostics(
        (decision(1), decision(2))
    )
    return diagnosed.decide_route_plan(
        PageRoutingConfiguration(
            routing_policy_version=RoutingPolicyVersion.from_value("routing-read-v1"),
            auto_confidence_min=0.90,
            benchmark_confidence_min=0.85,
        )
    )


async def get(application, path, query=""):
    sent = []
    delivered = False

    async def receive():
        nonlocal delivered
        if delivered:
            return {"type": "http.disconnect"}
        delivered = True
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    await application(
        {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": query.encode("ascii"),
            "root_path": "",
            "headers": [],
            "client": ("asgi-test", 50000),
            "server": ("orchestrator-api", 8080),
            "state": {},
        },
        receive,
        send,
    )
    start = next(message for message in sent if message["type"] == "http.response.start")
    raw = b"".join(
        message.get("body", b"")
        for message in sent
        if message["type"] == "http.response.body"
    )
    return start["status"], json.loads(raw.decode("utf-8"))


def assert_no_internal_fields(payload):
    forbidden = {
        "original_storage_ref",
        "processing_run_id",
        "job_id",
        "table",
        "artifact_ref",
        "canonical_artifact_ref",
    }
    if isinstance(payload, dict):
        leaked = forbidden.intersection(payload)
        if leaked:
            raise AssertionError(f"Champs internes exposés: {sorted(leaked)}")
        for value in payload.values():
            assert_no_internal_fields(value)
    elif isinstance(payload, list):
        for value in payload:
            assert_no_internal_fields(value)


async def scenario(repo_root):
    source_only = source("source-only")
    requested = source("diagnostic-requested")
    routed = source("routed")
    accepted = source("accepted")
    rejected = source("rejected")
    requested_processing = requested_run(requested, "REQUESTED")
    routed_processing = routed_run(routed, "ROUTED")
    accepted_processing = routed_run(accepted, "ACCEPTED")
    rejected_processing = routed_run(rejected, "REJECTED")

    query_service = DocumentQueryService(
        document_snapshot_repository=SnapshotRepository(
            SourceRepository((source_only, requested, routed, accepted, rejected)),
            ProcessingRepository(
            (
                requested_processing,
                routed_processing,
                accepted_processing,
                rejected_processing,
            )
            ),
            ConversionRepository(
            (
                DocumentConversionState(
                    document_id=accepted.document_id,
                    conversion_status=DocumentConversionStatus.CANONICAL_ACCEPTED,
                    canonical_version_id="CVER-M013-T007-ACCEPTED",
                    rejection_error_code=None,
                ),
                DocumentConversionState(
                    document_id=rejected.document_id,
                    conversion_status=DocumentConversionStatus.QA_REJECTED,
                    canonical_version_id=None,
                    rejection_error_code="PAGE_AUTHORITY_MISSING",
                ),
            )
            ),
        ),
    )
    configuration = load_application_configuration(
        repo_root / "config" / "application.example.yaml", {}
    )

    def root_factory(validated_configuration):
        return OrchestratorCompositionRoot(
            configuration=validated_configuration,
            dependencies=(ReadyDependency(),),
            document_command_router=build_document_query_router(
                document_queries=query_service
            ),
        )

    application = create_orchestrator_app(
        configuration=configuration,
        composition_root_factory=root_factory,
    )
    async with application.router.lifespan_context(application):
        corpus_status, corpus = await get(application, "/v1/documents", "limit=100")
        assert corpus_status == 200
        assert len(corpus["documents"]) == 5
        assert corpus["next_cursor"] is None
        source_item = next(
            item for item in corpus["documents"] if item["document_id"] == source_only.document_id.value
        )
        assert source_item["diagnostic_status"] == "DIAGNOSTIC_NOT_REQUESTED"
        assert source_item["conversion_status"] == "CONVERSION_NOT_REQUESTED"

        not_requested_status, not_requested = await get(
            application,
            f"/v1/documents/{source_only.document_id.value}/diagnostic",
        )
        assert (not_requested_status, not_requested["error_code"]) == (
            409,
            "DIAGNOSTIC_NOT_REQUESTED",
        )

        requested_status, requested_payload = await get(
            application,
            f"/v1/documents/{requested.document_id.value}/diagnostic",
        )
        assert requested_status == 200
        assert requested_payload["diagnostic_status"] == "MANIFEST_CREATED"
        assert requested_payload["diagnosed_page_count"] == 0
        assert [entry["page_number"] for entry in requested_payload["manifest"]] == [1, 2]
        assert [page["page_number"] for page in requested_payload["pages"]] == [1, 2]
        assert all(page["diagnostic"] is None for page in requested_payload["pages"])

        routed_status, routed_payload = await get(
            application,
            f"/v1/documents/{routed.document_id.value}/diagnostic",
        )
        assert routed_status == 200
        assert routed_payload["diagnostic_status"] == "ROUTE_PLANNED"
        assert [page["page_number"] for page in routed_payload["pages"]] == [1, 2]
        assert all(page["route"] is not None for page in routed_payload["pages"])
        assert routed_payload["pages"][1]["diagnostic"]["has_table"] is True

        accepted_status, accepted_payload = await get(
            application,
            f"/v1/documents/{accepted.document_id.value}/conversion",
        )
        assert accepted_status == 200
        assert accepted_payload == {
            "document_id": accepted.document_id.value,
            "conversion_status": "CANONICAL_ACCEPTED",
            "qa_rejection_error_code": None,
            "canonical_version_id": "CVER-M013-T007-ACCEPTED",
        }

        rejected_status, rejected_payload = await get(
            application,
            f"/v1/documents/{rejected.document_id.value}/conversion",
        )
        assert rejected_status == 200
        assert rejected_payload["conversion_status"] == "QA_REJECTED"
        assert rejected_payload["qa_rejection_error_code"] == "PAGE_AUTHORITY_MISSING"
        assert rejected_payload["canonical_version_id"] is None

        conversion_missing_status, conversion_missing = await get(
            application,
            f"/v1/documents/{routed.document_id.value}/conversion",
        )
        assert (conversion_missing_status, conversion_missing["error_code"]) == (
            409,
            "CONVERSION_NOT_REQUESTED",
        )

        missing_status, missing_payload = await get(
            application,
            "/v1/documents/DOC-FFFFFFFFFFFFFFFF/diagnostic",
        )
        assert (missing_status, missing_payload["error_code"]) == (
            404,
            "SOURCE_NOT_FOUND",
        )

        for payload in (
            corpus,
            requested_payload,
            routed_payload,
            accepted_payload,
            rejected_payload,
        ):
            assert_no_internal_fields(payload)


asyncio.run(scenario(Path(sys.argv[1])))
print("Test d'acceptation des read-models documentaires SP: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_document_read_models_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Validation d'acceptation T-007: OK"
