$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
from __future__ import annotations

from dataclasses import FrozenInstanceError
import sys

sys.path.insert(0, sys.argv[1])

from app.source_processing.application.document_commands import (
    DocumentConversionState,
    DocumentConversionStatus,
)
from app.source_processing.application.document_queries import (
    ConversionNotRequestedError,
    DiagnosticNotRequestedError,
    DocumentQueryService,
    DocumentStateSnapshot,
    SourceNotFoundError,
)
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
        self.documents = tuple(documents)

    def list_documents(self):
        return tuple(reversed(self.documents))

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
        assert limit == 3
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


def source(label):
    content = f"%PDF-1.7\nunit-{label}\n%%EOF\n".encode("utf-8")
    fingerprint = SourceFingerprint.from_content(content)
    document_id = DocumentId.from_fingerprint(fingerprint)
    return SourceDocument.register_original(
        document_id=document_id,
        fingerprint=fingerprint,
        original_storage_ref=OriginalStorageRef.from_value(
            f"artifact:source_processing.original_sources/{document_id.value}/{fingerprint.value}.pdf"
        ),
        metadata=BibliographicMetadata(
            title=f"Titre {label}",
            authors=("Auteur",),
            publication_year=2026,
            edition="1",
        ),
    )


def page_decision(number):
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
            has_table=False,
            has_formula=number == 3,
        ),
        diagnostic_version=DiagnosticVersion.from_value("diag-unit-v1"),
        justification=f"Décision page {number}.",
    )


def routed_run(document):
    page_numbers = (1, 2, 3)
    manifest = PageManifest.from_entries(
        source_page_count=3,
        entries=tuple(
            PageManifestEntry(
                page_number=PageNumber.from_value(number),
                state=PageManifestEntryState.PRESENT,
            )
            for number in page_numbers
        ),
    )
    started = DocumentProcessingRun.start(
        processing_run_id=ProcessingRunId.from_value("RUN-M013-T007-UNIT"),
        source_document=document,
        page_manifest=manifest,
    )
    diagnosed = started.record_page_diagnostics(
        tuple(page_decision(number) for number in page_numbers)
    )
    return diagnosed.decide_route_plan(
        PageRoutingConfiguration(
            routing_policy_version=RoutingPolicyVersion.from_value("routing-unit-v1"),
            auto_confidence_min=0.90,
            benchmark_confidence_min=0.85,
        )
    )


def assert_raises(expected_type, action):
    try:
        action()
    except expected_type as exc:
        return exc
    except Exception as exc:
        raise AssertionError(
            f"Type d'erreur inattendu: {type(exc).__name__}: {exc}"
        ) from exc
    raise AssertionError(f"Erreur attendue absente: {expected_type.__name__}")


document = source("routed")
source_only = source("source-only")
processing = routed_run(document)
conversion = DocumentConversionState(
    document_id=document.document_id,
    conversion_status=DocumentConversionStatus.CANONICAL_ACCEPTED,
    canonical_version_id="CVER-M013-T007-UNIT",
    rejection_error_code=None,
)
service = DocumentQueryService(
    document_snapshot_repository=SnapshotRepository(
        SourceRepository((document, source_only)),
        ProcessingRepository((processing,)),
        ConversionRepository((conversion,)),
    ),
)

# La projection du corpus vient uniquement des absences ou états réels des repositories.
corpus = service.list_documents(limit=2, cursor=None)
assert tuple(item.document_id for item in corpus.documents) == tuple(
    sorted((document.document_id.value, source_only.document_id.value))
)
source_only_item = next(
    item for item in corpus.documents if item.document_id == source_only.document_id.value
)
assert source_only_item.diagnostic_status == "DIAGNOSTIC_NOT_REQUESTED"
assert source_only_item.conversion_status == "CONVERSION_NOT_REQUESTED"
assert source_only_item.canonical_version_id is None
assert corpus.next_cursor is None

# Les pages restent dans l'ordre du manifeste et les DTO sont immuables.
diagnostic = service.read_diagnostic(document.document_id.value)
assert tuple(entry.page_number for entry in diagnostic.manifest) == (1, 2, 3)
assert tuple(page.page_number for page in diagnostic.pages) == (1, 2, 3)
assert diagnostic.diagnosed_page_count == 3
assert diagnostic.pages[2].diagnostic.has_formula is True
assert all(page.route is not None for page in diagnostic.pages)
assert_raises(
    FrozenInstanceError,
    lambda: setattr(diagnostic, "diagnostic_status", "INVENTED"),
)

# La nullabilité de la conversion est explicite et ne divulgue aucun champ technique.
conversion_view = service.read_conversion(document.document_id.value)
assert conversion_view.canonical_version_id == "CVER-M013-T007-UNIT"
assert conversion_view.qa_rejection_error_code is None
assert set(conversion_view.__dataclass_fields__) == {
    "document_id",
    "conversion_status",
    "qa_rejection_error_code",
    "canonical_version_id",
}

# Les erreurs sont produites uniquement après lecture des repositories propriétaires.
unknown_id = "DOC-FFFFFFFFFFFFFFFF"
not_found = assert_raises(
    SourceNotFoundError,
    lambda: service.read_diagnostic(unknown_id),
)
assert not_found.document_id == unknown_id
diagnostic_absent = assert_raises(
    DiagnosticNotRequestedError,
    lambda: service.read_diagnostic(source_only.document_id.value),
)
assert diagnostic_absent.document_id == source_only.document_id.value
conversion_absent = assert_raises(
    ConversionNotRequestedError,
    lambda: service.read_conversion(source_only.document_id.value),
)
assert conversion_absent.document_id == source_only.document_id.value

print("Tests unitaires des query services documentaires SP: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_document_queries_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Validation unitaire T-007: OK"
