$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

sys.path.insert(0, sys.argv[1])

from app.source_processing.application.start_document_processing import (
    DocumentInspection,
    InspectedPage,
    StartDocumentProcessingCommand,
    StartDocumentProcessingHandler,
)
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
    BibliographicMetadata,
    DocumentId,
    OriginalStorageRef,
    SourceDocument,
    SourceFingerprint,
)


class ExplicitDocumentInspector:
    def __init__(self, inspections_by_storage_ref):
        self.inspections_by_storage_ref = inspections_by_storage_ref
        self.inspected_refs = []

    def inspect(self, original_storage_ref):
        self.inspected_refs.append(original_storage_ref.value)
        return self.inspections_by_storage_ref[original_storage_ref.value]


class InMemoryProcessingRunRepository:
    def __init__(self, existing_runs):
        self.runs_by_id = {
            run.processing_run_id.value: run
            for run in existing_runs
        }
        self.saved_runs = []

    def save(self, processing_run):
        key = processing_run.processing_run_id.value
        if key in self.runs_by_id:
            raise AssertionError("Une tentative de traitement existante ne doit pas être remplacée.")
        self.runs_by_id[key] = processing_run
        self.saved_runs.append(processing_run)


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def assert_raises(expected_fragment, action):
    try:
        action()
    except ValueError as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


def metadata_payload(title):
    return {
        "title": title,
        "authors": ["Perry J. Kaufman"],
        "publication_year": 2020,
        "edition": "1re édition",
    }


def registered_source(original_content, title):
    fingerprint = SourceFingerprint.from_content(original_content)
    document_id = DocumentId.from_fingerprint(fingerprint)
    storage_ref = OriginalStorageRef.from_value(
        f"artifact:source_processing.original_sources/{document_id.value}/{fingerprint.value}.pdf"
    )
    return SourceDocument.register_original(
        document_id=document_id,
        fingerprint=fingerprint,
        original_storage_ref=storage_ref,
        metadata=BibliographicMetadata.from_payload(metadata_payload(title)),
    )


def one_page_manifest():
    return PageManifest.from_entries(
        source_page_count=1,
        entries=(
            PageManifestEntry(
                page_number=PageNumber.from_value(1),
                state=PageManifestEntryState.PRESENT,
            ),
        ),
    )


nominal_pdf = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog /Pages 2 >>\nendobj\ntrailer\n<<>>\n%%EOF\n"
mixed_pdf = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog /Pages 5 >>\nendobj\ntrailer\n<<>>\n%%EOF\n"
unknown_pages_pdf = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog /Pages ? >>\nendobj\ntrailer\n<<>>\n%%EOF\n"

nominal_source = registered_source(nominal_pdf, "Source nominale")
mixed_source = registered_source(mixed_pdf, "Source avec pages difficiles")
unknown_pages_source = registered_source(unknown_pages_pdf, "Source au nombre de pages inconnu")

historical_run = DocumentProcessingRun.start(
    processing_run_id=ProcessingRunId.from_value("RUN-HISTORIQUE-M003-T004"),
    source_document=nominal_source,
    page_manifest=one_page_manifest(),
)
historical_snapshot = historical_run

inspector = ExplicitDocumentInspector(
    {
        nominal_source.original_storage_ref.value: DocumentInspection(
            source_page_count=2,
            pages=(
                InspectedPage(page_number=1, state="PRESENT"),
                InspectedPage(page_number=2, state="PRESENT"),
            ),
        ),
        mixed_source.original_storage_ref.value: DocumentInspection(
            source_page_count=5,
            pages=(
                InspectedPage(page_number=1, state="PRESENT"),
                InspectedPage(page_number=2, state="PRESENT"),
                InspectedPage(page_number=3, state="EMPTY"),
                InspectedPage(page_number=4, state="UNREADABLE"),
                InspectedPage(page_number=5, state="REJECTED"),
            ),
        ),
        unknown_pages_source.original_storage_ref.value: DocumentInspection(
            source_page_count=None,
            pages=(),
        ),
    }
)
repository = InMemoryProcessingRunRepository(existing_runs=[historical_run])
handler = StartDocumentProcessingHandler(
    document_inspector=inspector,
    processing_run_repository=repository,
)

# Given une source documentaire enregistrée avec un PDF nominal.
# When une tentative de traitement est démarrée.
nominal_run = handler.handle(
    StartDocumentProcessingCommand(
        processing_run_id=ProcessingRunId.from_value("RUN-M003-T004-NOMINAL"),
        source_document=nominal_source,
    )
)

# Then le manifeste contient toutes les pages dans l'ordre source.
assert_equal(nominal_run.status, DocumentProcessingRunStatus.CREATED, "La tentative doit être créée avant diagnostic.")
assert_equal(nominal_run.page_manifest.source_page_count, 2, "Le nombre de pages source doit être conservé.")
assert_equal(
    tuple(entry.page_number.value for entry in nominal_run.page_manifest.entries),
    (1, 2),
    "Le manifeste nominal doit suivre l'ordre source.",
)
assert_equal(
    tuple(entry.state for entry in nominal_run.page_manifest.entries),
    (PageManifestEntryState.PRESENT, PageManifestEntryState.PRESENT),
    "Les pages nominales doivent être présentes explicitement.",
)

# Given une source documentaire enregistrée avec un PDF de cinq pages dont une page vide.
# When une tentative de traitement est démarrée.
mixed_run = handler.handle(
    StartDocumentProcessingCommand(
        processing_run_id=ProcessingRunId.from_value("RUN-M003-T004-MIXED"),
        source_document=mixed_source,
    )
)

# Then le manifeste contient cinq entrées ordonnées, la page vide est explicitement représentée
# et aucune tentative existante n'est modifiée.
assert_equal(mixed_run.page_manifest.source_page_count, 5, "Le manifeste doit concorder avec la source de cinq pages.")
assert_equal(
    tuple(entry.page_number.value for entry in mixed_run.page_manifest.entries),
    (1, 2, 3, 4, 5),
    "Le manifeste ne doit pas trier ou réordonner silencieusement les pages.",
)
assert_equal(
    tuple(entry.state for entry in mixed_run.page_manifest.entries),
    (
        PageManifestEntryState.PRESENT,
        PageManifestEntryState.PRESENT,
        PageManifestEntryState.EMPTY,
        PageManifestEntryState.UNREADABLE,
        PageManifestEntryState.REJECTED,
    ),
    "Les pages vide, illisible et rejetée doivent rester visibles dans le manifeste.",
)
assert_equal(historical_run, historical_snapshot, "Une tentative passée ne doit pas être réécrite.")
assert_true(
    repository.runs_by_id[historical_run.processing_run_id.value] is historical_run,
    "Le dépôt ne doit pas remplacer une tentative historique.",
)

# Given l'inspecteur ne peut pas fournir le nombre de pages source.
# When une tentative de traitement est démarrée.
# Then la poursuite est refusée explicitement.
assert_raises(
    "nombre de pages source inconnu",
    lambda: handler.handle(
        StartDocumentProcessingCommand(
            processing_run_id=ProcessingRunId.from_value("RUN-M003-T004-UNKNOWN"),
            source_document=unknown_pages_source,
        )
    ),
)
assert_equal(len(repository.saved_runs), 2, "Un nombre de pages inconnu ne doit pas créer de tentative persistée.")

print("Test d'acceptation T-004 manifeste complet des pages: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m003_page_manifest_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
try {
    $output = & $pythonExecutable -B $pythonScriptPath $repoRoot 2>&1
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
    Remove-Item -LiteralPath $pythonScriptPath -Force
}

if ($LASTEXITCODE -ne 0) {
    throw ($output -join "`n")
}

Write-Host "Test d'acceptation T-004 manifeste complet des pages: OK"
