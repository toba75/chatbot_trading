$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$env:PYTHONPATH = $repoRoot

$python = @'
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory

from app.source_processing.adapters.postgres_document_persistence import CorpusOriginalSourceStore
from app.source_processing.domain.source_document import (
    BibliographicMetadata,
    DocumentId,
    SourceDocument,
    SourceFingerprint,
)


def assert_raises(expected_message, callback):
    try:
        callback()
    except ValueError as exc:
        assert str(exc) == expected_message, (str(exc), expected_message)
        return
    raise AssertionError(f"Erreur attendue absente: {expected_message}")


pdf = b"%PDF-1.7\noriginal-bit-a-bit\n%%EOF\n"
fingerprint = SourceFingerprint.from_content(pdf)
document_id = DocumentId.from_fingerprint(fingerprint)
metadata = BibliographicMetadata("Original", ("OSTrading",), 2026, "1")

with TemporaryDirectory() as temporary_directory:
    store = CorpusOriginalSourceStore(corpus_root=Path(temporary_directory) / "corpus")

    # Idempotence et concurrence: toutes les écritures convergent sur la même référence.
    def put():
        return store.put_original_if_absent(document_id, fingerprint, pdf)

    with ThreadPoolExecutor(max_workers=8) as executor:
        refs = tuple(executor.map(lambda _: put(), range(16)))
    assert len(set(refs)) == 1

    source = SourceDocument.register_original(
        document_id=document_id,
        fingerprint=fingerprint,
        original_storage_ref=store.storage_ref(refs[0]),
        metadata=metadata,
    )
    assert store.read_original(source) == pdf

    # Une substitution binaire sous la même identité est refusée explicitement.
    original_path = store.resolve_internal_path(source.original_storage_ref)
    original_path.write_bytes(b"%PDF-1.7\nsubstitution\n%%EOF\n")
    assert_raises("ORIGINAL_HASH_MISMATCH", lambda: store.read_original(source))

    # Aucun chemin interne n'est exposé par la référence métier.
    assert source.original_storage_ref.value.startswith("artifact:source_processing.original_sources/")
    assert str(Path(temporary_directory)) not in source.original_storage_ref.value

print("Tests unitaires du stockage original durable: OK")
'@

$python | python -
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$adapter = Get-Content -Raw (Join-Path $repoRoot "app\source_processing\adapters\postgres_document_persistence.py")
$jobRuntime = Get-Content -Raw (Join-Path $repoRoot "app\platform\job_runtime\postgres.py")

foreach ($forbidden in @("sqlite3", "json.dump", "json.load")) {
    if ($adapter.Contains($forbidden) -or $jobRuntime.Contains($forbidden)) {
        throw "Backend métier interdit détecté: $forbidden"
    }
}
if ($adapter.Contains("InMemoryJobQueue") -or $jobRuntime.Contains("InMemoryJobQueue")) {
    throw "Fallback InMemoryJobQueue interdit dans le runtime durable."
}
foreach ($marker in @("submit_in_transaction", "ON CONFLICT", "FOR UPDATE", "PsycopgConnectionFactory")) {
    if (-not ($adapter.Contains($marker) -or $jobRuntime.Contains($marker))) {
        throw "Garantie PostgreSQL absente: $marker"
    }
}

Write-Host "Validation unitaire T-005: OK"
