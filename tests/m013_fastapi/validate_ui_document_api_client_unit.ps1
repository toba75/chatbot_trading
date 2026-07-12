$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom

$pythonCode = @'
from __future__ import annotations

import sys

repo_root = sys.argv[1]
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from app.platform.ui_document_api import (  # noqa: E402
    UiDocumentApiClient,
    UiDocumentApiResponse,
    UiDocumentApiUnavailableError,
)


def assert_equal(actual: object, expected: object, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_raises(expected_type: type[BaseException], expected_fragment: str, action) -> None:
    try:
        action()
    except expected_type as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}") from exc
        return
    raise AssertionError(f"Erreur attendue absente: {expected_type.__name__}")


class RecordingTransport:
    def __init__(self, responses: list[UiDocumentApiResponse]) -> None:
        self.responses = list(responses)
        self.requests: list[tuple[str, str, bytes | None, str | None]] = []

    def request(self, *, method: str, path: str, body: bytes | None, content_type: str | None) -> UiDocumentApiResponse:
        self.requests.append((method, path, body, content_type))
        if not self.responses:
            raise AssertionError("Réponse de transport absente")
        return self.responses.pop(0)


def json_response(status_code: int, body: str) -> UiDocumentApiResponse:
    return UiDocumentApiResponse(
        status_code=status_code,
        content_type="application/json; charset=utf-8",
        body=body.encode("utf-8"),
    )


# Given les contrats documentaires publics sont disponibles.
# When le client UI construit le corpus et lit une étape.
# Then il n'émet que des URL relatives publiques et parse strictement les DTO.
transport = RecordingTransport(
    [
        json_response(
            200,
            '{"documents":[{"document_id":"DOC-M013-FASTAPI-UI01","title":"Rapport",'
            '"document_status":"REGISTERED","diagnostic_status":"DIAGNOSTIC_NOT_REQUESTED",'
            '"conversion_status":"CONVERSION_NOT_REQUESTED","canonical_version_id":null}]}',
        ),
        json_response(
            200,
            '{"document_id":"DOC-M013-FASTAPI-UI01","projection_status":"PROJECTION_NOT_REQUESTED"}',
        ),
        json_response(
            409,
            '{"error_code":"DIAGNOSTIC_NOT_REQUESTED","document_id":"DOC-M013-FASTAPI-UI01"}',
        ),
        json_response(
            202,
            '{"document_id":"DOC-M013-FASTAPI-UI01","diagnostic_status":"DIAGNOSTIC_REQUESTED"}',
        ),
    ]
)
client = UiDocumentApiClient(transport=transport)
state = client.build_corpus_state(active_selected_document_ids=())
assert_equal(state.read_model_status, "READ_MODEL_READY", "Le corpus doit provenir de l'API.")
assert_equal(state.documents[0].projection_status, "PROJECTION_NOT_REQUESTED", "La projection publique doit être lue.")
diagnostic_error = client.read_diagnostic("DOC-M013-FASTAPI-UI01")
assert_equal(diagnostic_error.status_code, 409, "L'absence de diagnostic doit rester publique.")
command = client.forward_document_command(
    path="/v1/documents/DOC-M013-FASTAPI-UI01/diagnose",
    body=b"",
    content_type="application/octet-stream",
)
assert_equal(command.status_code, 202, "La commande doit conserver le statut HTTP public.")
assert_equal(
    [request[1] for request in transport.requests],
    [
        "/v1/documents",
        "/v1/documents/DOC-M013-FASTAPI-UI01/projection",
        "/v1/documents/DOC-M013-FASTAPI-UI01/diagnostic",
        "/v1/documents/DOC-M013-FASTAPI-UI01/diagnose",
    ],
    "Le client UI doit utiliser exclusivement des URL publiques relatives.",
)

for _, path, _, _ in transport.requests:
    if not path.startswith("/v1/documents") or "://" in path:
        raise AssertionError(f"URL UI non publique ou absolue: {path}")

# Les données internes, champs supplémentaires et statuts inconnus sont refusés.
internal_transport = RecordingTransport(
    [
        json_response(
            200,
            '{"documents":[{"document_id":"DOC-M013-FASTAPI-UI01","title":"Rapport",'
            '"document_status":"REGISTERED","diagnostic_status":"DIAGNOSTIC_NOT_REQUESTED",'
            '"conversion_status":"CONVERSION_NOT_REQUESTED","canonical_version_id":null,'
            '"original_storage_ref":"/var/lib/private.pdf"}]}',
        )
    ]
)
assert_raises(
    ValueError,
    "original_storage_ref",
    lambda: UiDocumentApiClient(transport=internal_transport).build_corpus_state(
        active_selected_document_ids=()
    ),
)

unknown_status_transport = RecordingTransport(
    [
        json_response(
            200,
            '{"documents":[{"document_id":"DOC-M013-FASTAPI-UI01","title":"Rapport",'
            '"document_status":"REGISTERED","diagnostic_status":"DIAGNOSTIC_INVENTED",'
            '"conversion_status":"CONVERSION_NOT_REQUESTED","canonical_version_id":null}]}',
        )
    ]
)
assert_raises(
    ValueError,
    "statut diagnostic public invalide",
    lambda: UiDocumentApiClient(transport=unknown_status_transport).build_corpus_state(
        active_selected_document_ids=()
    ),
)

class UnavailableTransport:
    def request(self, *, method: str, path: str, body: bytes | None, content_type: str | None) -> UiDocumentApiResponse:
        raise UiDocumentApiUnavailableError("ORCHESTRATOR_API_UNAVAILABLE")


assert_raises(
    UiDocumentApiUnavailableError,
    "ORCHESTRATOR_API_UNAVAILABLE",
    lambda: UiDocumentApiClient(transport=UnavailableTransport()).build_corpus_state(
        active_selected_document_ids=()
    ),
)

print("Tests unitaires client documentaire UI: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_fastapi_ui_client_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Tests unitaires client documentaire UI invalides. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
