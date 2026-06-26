$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import hashlib
import sys

sys.path.insert(0, sys.argv[1])

from app.source_processing.application.register_source_document import (
    RegisterSourceDocumentCommand,
    RegisterSourceDocumentHandler,
)
from app.source_processing.domain.source_document import SourceDocumentStatus


class InMemoryOriginalSourceStore:
    def __init__(self):
        self.content_by_ref = {}
        self.write_operations = []

    def store_original(self, document_id, fingerprint, original_content):
        raise AssertionError("L'enregistrement doit utiliser put_original_if_absent.")

    def put_original_if_absent(self, document_id, fingerprint, original_content):
        storage_ref = f"artifact:source_processing.original_sources/{document_id.value}/{fingerprint.value}.pdf"
        existing_content = self.content_by_ref.get(storage_ref)
        if existing_content is not None:
            if existing_content != bytes(original_content):
                raise AssertionError("Un original existant ne doit pas être remplacé par un autre contenu.")
            return storage_ref
        self.content_by_ref[storage_ref] = bytes(original_content)
        self.write_operations.append(storage_ref)
        return storage_ref


class InMemorySourceDocumentRepository:
    def __init__(self):
        self.documents_by_id = {}

    def find_by_fingerprint(self, fingerprint):
        for document in self.documents_by_id.values():
            if document.fingerprint == fingerprint:
                return document
        return None

    def find_by_work_key(self, work_key):
        for document in self.documents_by_id.values():
            if document.metadata.work_key == work_key:
                return document
        return None

    def list_registered(self):
        raise AssertionError("L'enregistrement nominal doit utiliser les index fingerprint/work_key, pas un scan complet.")

    def save(self, source_document):
        key = source_document.document_id.value
        if key in self.documents_by_id:
            raise AssertionError("Un SourceDocument enregistré ne doit pas être remplacé.")
        self.documents_by_id[key] = source_document

    def save_if_absent(self, source_document):
        key = source_document.document_id.value
        existing_document = self.documents_by_id.get(key)
        if existing_document is not None:
            return existing_document
        self.documents_by_id[key] = source_document
        return None


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def metadata(edition):
    return {
        "title": "Trading Systems and Methods",
        "authors": ["Perry J. Kaufman"],
        "publication_year": 2020,
        "edition": edition,
    }


original_pdf = (
    b"%PDF-1.7\n"
    b"1 0 obj\n"
    b"<< /Type /Catalog /Version /1.7 >>\n"
    b"endobj\n"
    b"trailer\n"
    b"<< /Root 1 0 R >>\n"
    b"%%EOF\n"
)
distinct_edition_pdf = (
    b"%PDF-1.7\n"
    b"1 0 obj\n"
    b"<< /Type /Catalog /Version /1.7 /Edition (second edition) >>\n"
    b"endobj\n"
    b"trailer\n"
    b"<< /Root 1 0 R >>\n"
    b"%%EOF\n"
)
corrupted_pdf = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\n"

store = InMemoryOriginalSourceStore()
repository = InMemorySourceDocumentRepository()
handler = RegisterSourceDocumentHandler(
    original_source_store=store,
    source_document_repository=repository,
)

# Given un PDF original lisible est ajouté au corpus avec des métadonnées bibliographiques validées.
# When la source documentaire est enregistrée.
registered = handler.handle(
    RegisterSourceDocumentCommand(
        original_content=original_pdf,
        bibliographic_metadata=metadata("1re édition"),
    )
)

# Then le système calcule son empreinte stable et conserve une référence d'original immuable.
expected_fingerprint = hashlib.sha256(original_pdf).hexdigest()
assert_equal(registered.decision, "REGISTERED", "La source nominale doit être enregistrée.")
assert_equal(registered.source_document.status, SourceDocumentStatus.REGISTERED, "La source doit être prête au diagnostic.")
assert_equal(registered.source_document.fingerprint.value, expected_fingerprint, "L'empreinte doit être calculée sur le contenu binaire.")
assert_equal(store.content_by_ref[registered.source_document.original_storage_ref.value], original_pdf, "L'original stocké doit rester bit-à-bit identique.")
assert_equal(len(store.write_operations), 1, "L'enregistrement nominal doit écrire l'original une seule fois.")

# Given la même copie binaire est ajoutée une seconde fois.
# When la source documentaire est enregistrée.
binary_duplicate = handler.handle(
    RegisterSourceDocumentCommand(
        original_content=original_pdf,
        bibliographic_metadata=metadata("1re édition"),
    )
)

# Then le doublon binaire est explicite et l'original existant n'est pas réécrit.
assert_equal(binary_duplicate.decision, "BINARY_DUPLICATE", "La copie binaire exacte doit être signalée explicitement.")
assert_equal(binary_duplicate.duplicate_document_id, registered.source_document.document_id, "Le doublon doit pointer vers le SourceDocument existant.")
assert_equal(len(store.write_operations), 1, "Le doublon binaire ne doit pas réécrire l'original.")
assert_equal(len(repository.documents_by_id), 1, "Le doublon binaire ne doit pas créer une fusion silencieuse.")

# Given une édition distincte du même ouvrage est ajoutée.
# When la source documentaire est enregistrée.
distinct_edition = handler.handle(
    RegisterSourceDocumentCommand(
        original_content=distinct_edition_pdf,
        bibliographic_metadata=metadata("2e édition"),
    )
)

# Then elle reçoit son identité propre au lieu d'être fusionnée automatiquement.
assert_equal(distinct_edition.decision, "DISTINCT_EDITION_REGISTERED", "Une édition distincte doit être enregistrée séparément.")
assert_true(
    distinct_edition.source_document.document_id != registered.source_document.document_id,
    "Deux éditions différentes ne doivent pas partager le même DocumentId.",
)
assert_equal(distinct_edition.source_document.metadata.edition, "2e édition", "L'édition bibliographique doit rester explicite.")
assert_equal(len(repository.documents_by_id), 2, "Une édition distincte doit créer un SourceDocument séparé.")

# Given un PDF corrompu est ajouté au corpus.
# When la source documentaire est enregistrée.
corrupted_review = handler.handle(
    RegisterSourceDocumentCommand(
        original_content=corrupted_pdf,
        bibliographic_metadata=metadata("3e édition corrompue"),
    )
)

# Then il part en revue explicite sans devenir source prête au diagnostic.
assert_equal(corrupted_review.decision, "REVIEW_REQUIRED", "Un PDF corrompu doit demander une revue explicite.")
assert_equal(corrupted_review.review_reason, "PDF_CORRUPTED", "La raison de revue doit nommer le PDF corrompu.")
assert_equal(corrupted_review.source_document, None, "Un PDF corrompu ne doit pas produire de SourceDocument prêt au diagnostic.")
assert_equal(len(repository.documents_by_id), 2, "Un PDF corrompu ne doit pas être enregistré comme source prête.")

print("Test d'acceptation T-003 enregistrement immuable des sources: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m003_source_registration_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-003 enregistrement immuable des sources: OK"
