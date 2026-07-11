$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom

$pythonCode = @'
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import sys
import tempfile

repo_root = sys.argv[1]
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from app.platform.ui_corpus import (  # noqa: E402
    build_corpus_pdf_state_from_corpus_root,
    ui_get_pdf_content_response,
)


def assert_equal(actual: object, expected: object, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_raises(expected_fragment: str, action) -> None:
    try:
        action()
    except ValueError as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}") from exc
        return
    raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


with tempfile.TemporaryDirectory() as temporary_root:
    missing_root = Path(temporary_root) / "absent"
    unavailable_state = build_corpus_pdf_state_from_corpus_root(corpus_root=missing_root)
    assert_equal(unavailable_state.read_model_status, "READ_MODEL_UNAVAILABLE", "Un corpus absent doit etre explicite.")
    assert_equal(unavailable_state.documents, (), "Un corpus absent ne doit pas produire de documents fictifs.")

with tempfile.TemporaryDirectory() as temporary_root:
    corpus_root = Path(temporary_root) / "corpus"
    corpus_root.mkdir()
    first_content = b"%PDF-1.7\nfirst\n%%EOF\n"
    second_content = b"%PDF-1.7\nsecond\n%%EOF\n"
    (corpus_root / "b.pdf").write_bytes(second_content)
    (corpus_root / "a.pdf").write_bytes(first_content)
    (corpus_root / "ignored.PDF.tmp").write_bytes(b"%PDF-1.7\nignored")

    state = build_corpus_pdf_state_from_corpus_root(corpus_root=corpus_root)
    assert_equal(tuple(document.title for document in state.documents), ("a", "b"), "Les PDF doivent etre tries par nom.")
    assert_equal(
        tuple(document.document_id for document in state.documents),
        (
            "DOC-" + sha256(first_content).hexdigest()[:16].upper(),
            "DOC-" + sha256(second_content).hexdigest()[:16].upper(),
        ),
        "Les identites publiques doivent etre stables et derivees du contenu.",
    )
    assert_equal(
        tuple(document.projection_status for document in state.documents),
        ("PROJECTION_NOT_REQUESTED", "PROJECTION_NOT_REQUESTED"),
        "Un corpus brut ne doit pas simuler une projection KA.",
    )

    assert_raises(
        "chemin contenu PDF invalide",
        lambda: ui_get_pdf_content_response(path="/ui/documents/DOC-ABC/pdf", corpus_root=corpus_root),
    )

    unknown_status, content_type, body = ui_get_pdf_content_response(
        path="/ui/documents/DOC-FFFFFFFFFFFFFFFF/pdf/content",
        corpus_root=corpus_root,
    )
    assert_equal(unknown_status, 404, "Un document inconnu doit rester introuvable.")
    assert_equal(content_type, "text/plain; charset=utf-8", "Une erreur de contenu PDF doit rester textuelle.")
    assert_equal(body, b"PDF introuvable", "Le corps d'erreur ne doit pas divulguer de chemin.")

print("Tests unitaires connexion backend UI corpus PDF: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_ui_backend_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
try {
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $env:PYTHONIOENCODING = "utf-8"
        $output = & $pythonExecutable -B $pythonScriptPath $repoRoot 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if ($exitCode -ne 0) {
        throw "Tests unitaires connexion backend UI corpus PDF invalides. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
