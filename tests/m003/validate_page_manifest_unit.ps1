$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
from dataclasses import FrozenInstanceError
import sys

sys.path.insert(0, sys.argv[1])

from app.source_processing.domain.document_processing_run import (
    DocumentProcessingRun,
    DocumentProcessingRunStatus,
    DocumentProcessingStarted,
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


def assert_raises_type(expected_type, action):
    try:
        action()
    except expected_type:
        return
    except Exception as exc:
        raise AssertionError(f"Erreur inattendue: {exc}") from exc
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_type.__name__}")


def registered_source():
    original_content = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog /Pages 3 >>\nendobj\ntrailer\n<<>>\n%%EOF\n"
    fingerprint = SourceFingerprint.from_content(original_content)
    document_id = DocumentId.from_fingerprint(fingerprint)
    storage_ref = OriginalStorageRef.from_value(
        f"artifact:source_processing.original_sources/{document_id.value}/{fingerprint.value}.pdf"
    )
    return SourceDocument.register_original(
        document_id=document_id,
        fingerprint=fingerprint,
        original_storage_ref=storage_ref,
        metadata=BibliographicMetadata.from_payload(
            {
                "title": "Trading Systems and Methods",
                "authors": ["Perry J. Kaufman"],
                "publication_year": 2020,
                "edition": "1re édition",
            }
        ),
    )


def entry(page_number, state):
    return PageManifestEntry(
        page_number=PageNumber.from_value(page_number),
        state=PageManifestEntryState.from_value(state),
    )


# PageNumber refuse les pages implicites, ambiguës ou hors plage.
assert_equal(PageNumber.from_value(1).value, 1, "PageNumber doit conserver le numéro 1.")
assert_equal(PageNumber.from_value(5).value, 5, "PageNumber doit conserver le numéro 5.")
assert_raises("page_number invalide", lambda: PageNumber.from_value(0))
assert_raises("page_number invalide", lambda: PageNumber.from_value(True))
assert_raises("page_number invalide", lambda: PageNumber.from_value("1"))

# PageManifest conserve chaque page source et son état explicite.
manifest = PageManifest.from_entries(
    source_page_count=5,
    entries=(
        entry(1, "PRESENT"),
        entry(2, "PRESENT"),
        entry(3, "EMPTY"),
        entry(4, "UNREADABLE"),
        entry(5, "REJECTED"),
    ),
)
assert_equal(manifest.source_page_count, 5, "Le nombre de pages source doit être explicite.")
assert_equal(
    tuple(page_entry.page_number.value for page_entry in manifest.entries),
    (1, 2, 3, 4, 5),
    "Le manifeste doit conserver l'ordre source.",
)
assert_equal(
    tuple(page_entry.state for page_entry in manifest.entries),
    (
        PageManifestEntryState.PRESENT,
        PageManifestEntryState.PRESENT,
        PageManifestEntryState.EMPTY,
        PageManifestEntryState.UNREADABLE,
        PageManifestEntryState.REJECTED,
    ),
    "Les états de manifeste doivent représenter les pages difficiles.",
)

# Aucun tri ou réordonnancement silencieux n'est accepté.
assert_raises(
    "ordre strict",
    lambda: PageManifest.from_entries(
        source_page_count=3,
        entries=(entry(1, "PRESENT"), entry(3, "PRESENT"), entry(2, "PRESENT")),
    ),
)
assert_raises(
    "ordre strict",
    lambda: PageManifest.from_entries(
        source_page_count=2,
        entries=(entry(2, "PRESENT"), entry(1, "PRESENT")),
    ),
)

# Le manifeste doit concorder avec la source et refuser les pages hors plage.
assert_raises(
    "nombre de pages du manifeste discordant",
    lambda: PageManifest.from_entries(
        source_page_count=3,
        entries=(entry(1, "PRESENT"), entry(2, "PRESENT")),
    ),
)
assert_raises(
    "page_number hors plage",
    lambda: PageManifest.from_entries(
        source_page_count=2,
        entries=(entry(1, "PRESENT"), entry(2, "PRESENT"), entry(3, "PRESENT")),
    ),
)
assert_raises("nombre de pages source invalide", lambda: PageManifest.from_entries(source_page_count=None, entries=()))
assert_raises("page manifeste inconnu", lambda: PageManifestEntry(page_number=PageNumber.from_value(1), state="UNKNOWN"))

# DocumentProcessingRun.start crée une nouvelle tentative sans état diagnostiqué implicite.
source_document = registered_source()
run = DocumentProcessingRun.start(
    processing_run_id=ProcessingRunId.from_value("RUN-M003-T004-UNIT"),
    source_document=source_document,
    page_manifest=PageManifest.from_entries(
        source_page_count=3,
        entries=(entry(1, "PRESENT"), entry(2, "EMPTY"), entry(3, "UNREADABLE")),
    ),
)
assert_equal(run.status, DocumentProcessingRunStatus.MANIFEST_CREATED, "La tentative démarre en MANIFEST_CREATED avant diagnostic.")
assert_equal(run.document_id, source_document.document_id, "La tentative doit référencer le SourceDocument enregistré.")
assert_equal(len(run.events), 1, "Le démarrage doit produire un événement de domaine.")
assert_true(isinstance(run.events[0], DocumentProcessingStarted), "L'événement doit nommer le démarrage de traitement.")
assert_equal(run.events[0].source_page_count, 3, "L'événement doit conserver le nombre de pages source.")

# Une tentative passée est immuable et ne peut pas être réécrite en DIAGNOSED par mutation.
assert_raises_type(FrozenInstanceError, lambda: setattr(run, "status", DocumentProcessingRunStatus.DIAGNOSED))
mutable_entries = [entry(1, "PRESENT")]
immutable_manifest = PageManifest.from_entries(source_page_count=1, entries=mutable_entries)
mutable_entries.append(entry(2, "PRESENT"))
assert_equal(
    tuple(page_entry.page_number.value for page_entry in immutable_manifest.entries),
    (1,),
    "Le manifeste d'une tentative passée ne doit pas suivre une mutation externe.",
)

print("Tests unitaires T-004 manifeste complet des pages: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m003_page_manifest_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-004 manifeste complet des pages: OK"
