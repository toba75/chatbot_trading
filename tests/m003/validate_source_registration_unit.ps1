$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import hashlib
import sys

sys.path.insert(0, sys.argv[1])

from app.source_processing.domain.source_document import (
    BibliographicMetadata,
    DocumentId,
    DuplicateEditionPolicy,
    OriginalStorageRef,
    SourceDocument,
    SourceDocumentRegistered,
    SourceDocumentStatus,
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


def metadata_payload(edition):
    return {
        "title": "Trading Systems and Methods",
        "authors": ["Perry J. Kaufman"],
        "publication_year": 2020,
        "edition": edition,
    }


original_pdf = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<<>>\n%%EOF\n"
second_edition_pdf = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog /Edition (2) >>\nendobj\ntrailer\n<<>>\n%%EOF\n"

# SourceFingerprint calcule une empreinte stable sur le contenu binaire.
fingerprint = SourceFingerprint.from_content(original_pdf)
assert_equal(fingerprint.value, hashlib.sha256(original_pdf).hexdigest(), "SourceFingerprint doit utiliser le contenu binaire complet.")
assert_raises("contenu original vide", lambda: SourceFingerprint.from_content(b""))
assert_raises("source_sha256 invalide", lambda: SourceFingerprint.from_value("not-a-hash"))

# DocumentId est stable et ne provient pas d'un chemin local.
document_id = DocumentId.from_fingerprint(fingerprint)
assert_true(document_id.value.startswith("DOC-"), "DocumentId doit respecter le préfixe de domaine M-001.")
assert_equal(DocumentId.from_fingerprint(fingerprint), document_id, "DocumentId doit être stable pour une même empreinte.")
assert_true(
    DocumentId.from_fingerprint(SourceFingerprint.from_content(second_edition_pdf)) != document_id,
    "Deux contenus différents doivent produire deux DocumentId distincts.",
)
assert_raises("document_id invalide", lambda: DocumentId.from_value(r"C:\corpus\source.pdf"))

# Les métadonnées bibliographiques obligatoires sont explicites.
metadata = BibliographicMetadata.from_payload(metadata_payload("1re édition"))
assert_equal(metadata.title, "Trading Systems and Methods", "Le titre bibliographique doit être conservé.")
assert_equal(metadata.authors, ("Perry J. Kaufman",), "Les auteurs doivent être normalisés en tuple immuable.")
assert_equal(metadata.edition, "1re édition", "L'édition doit rester explicite.")

for field_name in ("title", "authors", "publication_year", "edition"):
    invalid_payload = metadata_payload("1re édition")
    del invalid_payload[field_name]
    assert_raises(f"{field_name} absent", lambda invalid_payload=invalid_payload: BibliographicMetadata.from_payload(invalid_payload))

empty_authors = metadata_payload("1re édition")
empty_authors["authors"] = []
assert_raises("authors vide", lambda: BibliographicMetadata.from_payload(empty_authors))

blank_edition = metadata_payload("1re édition")
blank_edition["edition"] = " "
assert_raises("edition vide", lambda: BibliographicMetadata.from_payload(blank_edition))

invalid_year = metadata_payload("1re édition")
invalid_year["publication_year"] = 0
assert_raises("publication_year invalide", lambda: BibliographicMetadata.from_payload(invalid_year))

# SourceDocument.registerOriginal crée l'agrégat enregistré sans modifier l'original.
storage_ref = OriginalStorageRef.from_value(f"artifact:source_processing.original_sources/{document_id.value}/{fingerprint.value}.pdf")
source_document = SourceDocument.register_original(
    document_id=document_id,
    fingerprint=fingerprint,
    original_storage_ref=storage_ref,
    metadata=metadata,
)
assert_equal(source_document.status, SourceDocumentStatus.REGISTERED, "registerOriginal doit produire un état enregistré explicite.")
assert_equal(source_document.original_storage_ref, storage_ref, "La référence de stockage immuable doit être conservée.")
assert_equal(len(source_document.events), 1, "L'enregistrement doit produire un seul événement de domaine.")
assert_true(isinstance(source_document.events[0], SourceDocumentRegistered), "L'événement doit être SourceDocumentRegistered.")
assert_equal(source_document.events[0].document_id, document_id, "L'événement doit porter le DocumentId.")

# DuplicateEditionPolicy distingue doublon binaire, nouvelle édition et nouvelle source.
policy = DuplicateEditionPolicy()
binary_duplicate = policy.classify(
    candidate_fingerprint=fingerprint,
    candidate_metadata=metadata,
    existing_documents=[source_document],
)
assert_equal(binary_duplicate.decision, "BINARY_DUPLICATE", "Une copie bit-à-bit identique doit être un doublon binaire explicite.")
assert_equal(binary_duplicate.matching_document_id, document_id, "Le doublon binaire doit nommer la source existante.")

distinct_edition = policy.classify(
    candidate_fingerprint=SourceFingerprint.from_content(second_edition_pdf),
    candidate_metadata=BibliographicMetadata.from_payload(metadata_payload("2e édition")),
    existing_documents=[source_document],
)
assert_equal(distinct_edition.decision, "DISTINCT_EDITION", "Une édition différente ne doit pas être fusionnée.")
assert_equal(distinct_edition.matching_document_id, document_id, "La nouvelle édition doit rester reliée à l'ouvrage existant sans fusion.")

new_work = policy.classify(
    candidate_fingerprint=SourceFingerprint.from_content(b"%PDF-1.7\nnew work\n%%EOF\n"),
    candidate_metadata=BibliographicMetadata.from_payload(
        {
            "title": "Evidence-Based Technical Analysis",
            "authors": ["David Aronson"],
            "publication_year": 2006,
            "edition": "édition originale",
        }
    ),
    existing_documents=[source_document],
)
assert_equal(new_work.decision, "NEW_SOURCE", "Un autre ouvrage doit rester une nouvelle source.")
assert_equal(new_work.matching_document_id, None, "Une nouvelle source ne doit pas avoir de correspondance implicite.")

print("Tests unitaires T-003 enregistrement immuable des sources: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m003_source_registration_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-003 enregistrement immuable des sources: OK"
