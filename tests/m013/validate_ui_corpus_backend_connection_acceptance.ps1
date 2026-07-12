$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom

$pythonCode = @'
from __future__ import annotations

from pathlib import Path
import sys
import tempfile

repo_root = sys.argv[1]
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from app.platform.configuration import load_application_configuration  # noqa: E402
from app.platform.local_runtime import _build_ui_corpus_state  # noqa: E402
from app.platform.ui_corpus import ui_get_response  # noqa: E402
from app.platform.ui_document_api import (  # noqa: E402
    UiDocumentApiClient,
    UiDocumentApiResponse,
)


def assert_equal(actual: object, expected: object, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_contains(text: str, expected: str, message: str) -> None:
    if expected not in text:
        raise AssertionError(f"{message} Texte obtenu: {text!r}")


def assert_not_contains(text: str, forbidden: str, message: str) -> None:
    if forbidden in text:
        raise AssertionError(f"{message} Texte obtenu: {text!r}")


class RecordingTransport:
    def __init__(self) -> None:
        self.paths: list[str] = []
        self.responses = [
            UiDocumentApiResponse(
                200,
                "application/json",
                b'{"documents":[{"document_id":"DOC-M013-UI-API01","title":"Depuis API",'
                b'"document_status":"SOURCE_REGISTERED","diagnostic_status":"DIAGNOSTIC_NOT_REQUESTED",'
                b'"conversion_status":"CONVERSION_NOT_REQUESTED","canonical_version_id":null}]}',
            ),
            UiDocumentApiResponse(
                200,
                "application/json",
                b'{"document_id":"DOC-M013-UI-API01","projection_status":"PROJECTION_NOT_REQUESTED"}',
            ),
        ]

    def request(self, *, method: str, path: str, body: bytes | None, content_type: str | None) -> UiDocumentApiResponse:
        self.paths.append(path)
        return self.responses.pop(0)


def runtime_configuration_for(corpus_root: Path):
    template_path = Path(repo_root) / "config" / "application.yaml"
    config_text = template_path.read_text(encoding="utf-8")
    config_text = config_text.replace(
        "  corpus_root: data/corpus",
        f'  corpus_root: "{corpus_root.as_posix()}"',
    )
    config_path = corpus_root.parent / "application.yaml"
    config_path.write_text(config_text, encoding="utf-8")
    return load_application_configuration(config_path=config_path, environment_snapshot={})


with tempfile.TemporaryDirectory() as temporary_root:
    corpus_root = Path(temporary_root) / "corpus"
    corpus_root.mkdir()
    (corpus_root / "Ne doit pas être lu.pdf").write_bytes(b"%PDF-1.7\ninterdit\n%%EOF\n")
    configuration = runtime_configuration_for(corpus_root)
    transport = RecordingTransport()
    client = UiDocumentApiClient(transport=transport)

    # Given un fichier existe dans corpus_root et l'API expose un autre document.
    # When le runtime UI construit le corpus.
    # Then seul le read-model HTTP public est rendu, sans lecture de fichier ni fallback.
    state = _build_ui_corpus_state(
        application_configuration=configuration,
        api_client=client,
    )
    assert_equal(state.read_model_status, "READ_MODEL_READY", "Le runtime doit refléter le contrat API prêt.")
    assert_equal(state.documents[0].title, "Depuis API", "Le document doit venir de l'orchestrateur.")
    assert_equal(
        transport.paths,
        ["/v1/documents", "/v1/documents/DOC-M013-UI-API01/projection"],
        "Le trajet doit rester borné aux contrats documentaires publics.",
    )

    screen_status, screen_type, screen_body = ui_get_response(path="/ui/corpus-pdf", state=state)
    assert_equal(screen_status, 200, "L'écran raccordé doit être consultable.")
    assert_equal(screen_type, "text/html; charset=utf-8", "L'écran doit rester HTML.")
    assert_contains(screen_body, "Depuis API", "Le read-model API doit être visible.")
    assert_contains(screen_body, ">Diagnostiquer</button>", "La commande doit être active pour DIAGNOSTIC_NOT_REQUESTED.")
    assert_not_contains(screen_body, "Ne doit pas être lu", "Le stockage direct ne doit pas fuiter dans l'UI.")

runtime_source = (Path(repo_root) / "app" / "platform" / "local_runtime.py").read_text(encoding="utf-8")
ui_source = (Path(repo_root) / "app" / "platform" / "ui_corpus.py").read_text(encoding="utf-8")
for forbidden in (
    "build_unconnected_corpus_pdf_state",
    "ORCHESTRATOR_API_CONTRACT_NOT_WIRED",
    "UI_FUNCTION_NOT_OPERATIONAL",
    "_UI_DIAGNOSTIC_REQUESTED_DOCUMENT_IDS",
):
    assert_not_contains(runtime_source + ui_source, forbidden, "L'ancien chemin UI non raccordé doit être retiré.")
for forbidden in (".iterdir()", ".read_bytes()", "hashlib.sha256"):
    assert_not_contains(ui_source, forbidden, "L'adaptateur UI ne doit pas lire ni identifier directement les PDF.")

print("Test d'acceptation frontière UI vers API orchestratrice: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_ui_backend_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Test d'acceptation frontière UI vers API orchestratrice invalide. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
