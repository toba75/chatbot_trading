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
from app.platform.local_runtime import (  # noqa: E402
    _build_ui_corpus_state,
    _local_post_response,
)
from app.platform.ui_corpus import (  # noqa: E402
    ui_get_response,
    ui_unavailable_pdf_content_response,
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

    # Given un PDF existe dans le stockage configuré mais GET /v1/documents n'est pas câblé.
    # When le runtime UI construit son écran.
    # Then il n'accède pas au corpus et laisse la fonction explicitement non opérationnelle.
    state = _build_ui_corpus_state(application_configuration=configuration)
    assert_equal(state.read_model_status, "READ_MODEL_NOT_CONNECTED", "Le runtime doit refléter le contrat API absent.")
    assert_equal(state.documents, (), "Le PDF local ne doit pas contourner l'API orchestratrice.")

    screen_status, screen_type, screen_body = ui_get_response(path="/ui/corpus-pdf", state=state)
    assert_equal(screen_status, 200, "L'écran bloqué doit rester consultable.")
    assert_equal(screen_type, "text/html; charset=utf-8", "L'écran doit rester HTML.")
    assert_contains(screen_body, "ORCHESTRATOR_API_CONTRACT_NOT_WIRED", "Le défaut de câblage doit être public.")
    assert_not_contains(screen_body, "Ne doit pas être lu", "Le stockage direct ne doit pas fuiter dans l'UI.")

    diagnosis_path = "/v1/documents/DOC-FFFFFFFFFFFFFFFF/diagnose"
    api_status, api_body = _local_post_response(
        service_id="orchestrator-api",
        path=diagnosis_path,
        body={},
        application_configuration=configuration,
    )
    assert_equal(api_status, 404, "Le contrat documentaire est réellement absent de l'API actuelle.")
    assert_equal(api_body["error_code"], "ENDPOINT_NOT_FOUND", "L'API doit prouver l'absence du contrat.")

    ui_status, ui_body = _local_post_response(
        service_id="ui",
        path=diagnosis_path,
        body={},
        application_configuration=configuration,
    )
    assert_equal(ui_status, 503, "L'UI ne doit pas simuler le diagnostic absent.")
    assert_equal(ui_body["error_code"], "UI_FUNCTION_NOT_OPERATIONAL", "Le blocage UI doit être stable.")
    assert_equal(ui_body["reason"], "ORCHESTRATOR_API_CONTRACT_NOT_WIRED", "Le défaut de câblage doit être nommé.")
    assert_not_contains(str(ui_body), "DIAGNOSTIC_REQUESTED", "Aucun état diagnostic ne doit être fabriqué.")

    content_status, _, content_body = ui_unavailable_pdf_content_response(
        path="/ui/documents/DOC-FFFFFFFFFFFFFFFF/pdf/content",
    )
    assert_equal(content_status, 503, "Le PDF ne doit pas être servi depuis le stockage UI.")
    assert_not_contains(content_body.decode("utf-8"), str(corpus_root), "Le chemin local ne doit pas être exposé.")

runtime_source = (Path(repo_root) / "app" / "platform" / "local_runtime.py").read_text(encoding="utf-8")
ui_source = (Path(repo_root) / "app" / "platform" / "ui_corpus.py").read_text(encoding="utf-8")
for forbidden in (
    "_UI_DIAGNOSTIC_REQUESTED_DOCUMENT_IDS",
    "ui_request_diagnostic_response",
    "apply_diagnostic_requests_to_corpus_state",
):
    assert_not_contains(runtime_source, forbidden, "Le runtime UI ne doit conserver aucun état métier substitutif.")
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
