$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

sys.path.insert(0, sys.argv[1])

from app.source_processing.adapters.document_http import (
    HttpRequest,
    SourceProcessingHttpAdapter,
)
from app.source_processing.application.document_commands import (
    DiagnosisAlreadyRequestedError,
    DocumentDiagnosisAcceptance,
    RegisterDocumentAcceptance,
    SourceNotFoundError,
    SourceUnreadableError,
)
from app.source_processing.domain.source_document import DocumentId


class ScriptedDocumentCommands:
    def __init__(self):
        self.register_result = RegisterDocumentAcceptance(
            document_id=DocumentId.from_value("DOC-1111111111111111"),
            document_status="REGISTERED",
            duplicate=False,
        )
        self.diagnosis_result = DocumentDiagnosisAcceptance(
            document_id=DocumentId.from_value("DOC-1111111111111111"),
            diagnostic_status="DIAGNOSTIC_REQUESTED",
        )
        self.register_error = None
        self.diagnosis_error = None
        self.register_calls = []
        self.diagnosis_calls = []

    def register_source_document(self, *, original_content, bibliographic_metadata):
        self.register_calls.append(
            {
                "original_content": original_content,
                "bibliographic_metadata": bibliographic_metadata,
            }
        )
        if self.register_error is not None:
            raise self.register_error
        return self.register_result

    def start_document_processing(self, *, document_id):
        self.diagnosis_calls.append(document_id)
        if self.diagnosis_error is not None:
            raise self.diagnosis_error
        return self.diagnosis_result

class M3OnlyDocumentCommands:
    def __init__(self):
        self.diagnosis_result = DocumentDiagnosisAcceptance(
            document_id=DocumentId.from_value("DOC-1111111111111111"),
            diagnostic_status="DIAGNOSTIC_REQUESTED",
        )
        self.diagnosis_calls = []

    def register_source_document(self, *, original_content, bibliographic_metadata):
        return RegisterDocumentAcceptance(
            document_id=DocumentId.from_value("DOC-1111111111111111"),
            document_status="REGISTERED",
            duplicate=False,
        )

    def start_document_processing(self, *, document_id):
        self.diagnosis_calls.append(document_id)
        return self.diagnosis_result


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def metadata():
    return {
        "title": "Trading Systems and Methods",
        "authors": ["Perry J. Kaufman"],
        "publication_year": 2020,
        "edition": "1re édition",
    }


def post_document(adapter, content):
    return adapter.handle(
        HttpRequest(
            method="POST",
            path="/v1/documents",
            body={
                "original_content": content,
                "bibliographic_metadata": metadata(),
            },
        )
    )


def post_diagnose(adapter, document_id):
    return adapter.handle(
        HttpRequest(
            method="POST",
            path=f"/v1/documents/{document_id}/diagnose",
            body={},
        )
    )


commands = ScriptedDocumentCommands()
adapter = SourceProcessingHttpAdapter(document_commands=commands)

m3_only_commands = M3OnlyDocumentCommands()
m3_only_adapter = SourceProcessingHttpAdapter(document_commands=m3_only_commands)
m3_only_response = post_diagnose(m3_only_adapter, "DOC-1111111111111111")
assert_equal(m3_only_response.status_code, 202, "Un port M-003 sans conversion doit encore servir /diagnose.")
assert_equal(m3_only_commands.diagnosis_calls, ["DOC-1111111111111111"], "Le port M-003 doit recevoir la commande diagnose.")
m3_convert_response = m3_only_adapter.handle(
    HttpRequest(
        method="POST",
        path="/v1/documents/DOC-1111111111111111/convert",
        body={},
    )
)
assert_equal(m3_convert_response.status_code, 404, "L'adaptateur M-003 ne doit pas router /convert.")

# Given le contrat HTTP documentaire SP.
# When POST /v1/documents est appelé.
registered = post_document(adapter, b"%PDF-1.7\n%%EOF\n")

# Then le contrat retourne uniquement l'identité métier et le statut documentaire.
assert_equal(registered.status_code, 201, "POST /v1/documents doit retourner 201.")
assert_equal(
    registered.body,
    {"document_id": "DOC-1111111111111111", "document_status": "REGISTERED"},
    "La réponse d'enregistrement doit être stable et minimale.",
)
assert_equal(len(commands.register_calls), 1, "L'adaptateur doit déléguer une seule commande d'enregistrement.")

# Given l'application signale un doublon binaire déjà enregistré.
# When POST /v1/documents est appelé avec le même contenu.
commands.register_result = RegisterDocumentAcceptance(
    document_id=DocumentId.from_value("DOC-1111111111111111"),
    document_status="DUPLICATE_SOURCE",
    duplicate=True,
)
duplicate = post_document(adapter, b"%PDF-1.7\n%%EOF\n")

# Then l'API ne présente pas le doublon comme une création nouvelle.
assert_equal(duplicate.status_code, 200, "Un doublon binaire doit retourner une réponse non-création.")
assert_equal(
    duplicate.body,
    {
        "document_id": "DOC-1111111111111111",
        "document_status": "DUPLICATE_SOURCE",
        "duplicate": True,
    },
    "La réponse de doublon doit être distincte d'une création.",
)
commands.register_result = RegisterDocumentAcceptance(
    document_id=DocumentId.from_value("DOC-1111111111111111"),
    document_status="REGISTERED",
    duplicate=False,
)

# Given un document enregistré.
# When POST /v1/documents/{id}/diagnose est appelé.
diagnosis = post_diagnose(adapter, "DOC-1111111111111111")

# Then le contrat retourne une acceptation de diagnostic sans identifiant interne.
assert_equal(diagnosis.status_code, 202, "POST /v1/documents/{id}/diagnose doit retourner 202.")
assert_equal(
    diagnosis.body,
    {
        "document_id": "DOC-1111111111111111",
        "diagnostic_status": "DIAGNOSTIC_REQUESTED",
    },
    "La réponse de diagnostic doit être stable et minimale.",
)
assert_equal(commands.diagnosis_calls, ["DOC-1111111111111111"], "L'adaptateur doit déléguer avec le DocumentId public.")
for forbidden_key in ("processing_run_id", "original_storage_ref", "route", "conversion_status"):
    assert_true(forbidden_key not in diagnosis.body, f"La réponse ne doit pas exposer {forbidden_key}.")

# Given une source illisible est refusée par l'application.
# When l'adaptateur mappe l'erreur métier.
commands.register_error = SourceUnreadableError(reason="PDF_CORRUPTED")
unreadable = post_document(adapter, b"%PDF-1.7\nincomplet\n")

# Then l'erreur HTTP est explicite et stable.
assert_equal(unreadable.status_code, 422, "Une source illisible doit retourner 422.")
assert_equal(
    unreadable.body,
    {"error_code": "SOURCE_UNREADABLE", "reason": "PDF_CORRUPTED"},
    "Le mapping source illisible doit rester stable.",
)

# Given une source inconnue est refusée par l'application.
# When l'adaptateur mappe l'erreur métier.
commands.diagnosis_error = SourceNotFoundError(document_id="DOC-2222222222222222")
not_found = post_diagnose(adapter, "DOC-2222222222222222")

# Then le code public ne masque pas l'erreur SP.
assert_equal(not_found.status_code, 404, "Une source inconnue doit retourner 404.")
assert_equal(
    not_found.body,
    {"error_code": "SOURCE_NOT_FOUND", "document_id": "DOC-2222222222222222"},
    "Le mapping source inconnue doit rester stable.",
)

# Given un diagnostic déjà demandé est refusé par l'application.
# When l'adaptateur mappe l'erreur métier.
commands.diagnosis_error = DiagnosisAlreadyRequestedError(document_id="DOC-1111111111111111")
already_requested = post_diagnose(adapter, "DOC-1111111111111111")

# Then la répétition n'est pas transformée en acceptation silencieuse.
assert_equal(already_requested.status_code, 409, "Un diagnostic déjà demandé doit retourner 409.")
assert_equal(
    already_requested.body,
    {
        "error_code": "DIAGNOSTIC_ALREADY_REQUESTED",
        "document_id": "DOC-1111111111111111",
    },
    "Le mapping diagnostic déjà demandé doit rester stable.",
)

# Given une source non publiable est refusée pendant le diagnostic.
# When l'adaptateur mappe l'erreur métier.
commands.diagnosis_error = SourceUnreadableError(
    reason="source documentaire non publiable: QUARANTINED"
)
unreadable_diagnosis = post_diagnose(adapter, "DOC-1111111111111111")

# Then l'erreur HTTP est explicite et stable.
assert_equal(unreadable_diagnosis.status_code, 422, "Une source non publiable doit retourner 422.")
assert_equal(
    unreadable_diagnosis.body,
    {
        "error_code": "SOURCE_UNREADABLE",
        "reason": "source documentaire non publiable: QUARANTINED",
    },
    "Le mapping diagnostic source non publiable doit rester stable.",
)

# Given une requête client omet le contenu original obligatoire.
# When l'adaptateur reçoit POST /v1/documents.
missing_original = adapter.handle(
    HttpRequest(
        method="POST",
        path="/v1/documents",
        body={"bibliographic_metadata": metadata()},
    )
)

# Then l'erreur de contrat client est une réponse stable, pas une exception transport.
assert_equal(missing_original.status_code, 400, "Un contenu original absent doit retourner 400.")
assert_equal(
    missing_original.body,
    {"error_code": "HTTP_REQUEST_INVALID", "field": "original_content"},
    "Le corps d'erreur client doit rester stable.",
)

# Given une requête client omet les métadonnées bibliographiques obligatoires.
# When l'adaptateur reçoit POST /v1/documents.
missing_metadata = adapter.handle(
    HttpRequest(
        method="POST",
        path="/v1/documents",
        body={"original_content": b"%PDF-1.7\n%%EOF\n"},
    )
)

# Then l'erreur nomme le champ refusé.
assert_equal(missing_metadata.status_code, 400, "Des métadonnées absentes doivent retourner 400.")
assert_equal(
    missing_metadata.body,
    {"error_code": "HTTP_REQUEST_INVALID", "field": "bibliographic_metadata"},
    "Le champ bibliographique absent doit être nommé.",
)

# Given l'identifiant public ne respecte pas le contrat DOC.
# When l'endpoint de diagnostic est appelé.
invalid_document_id = post_diagnose(adapter, "not-a-doc")

# Then l'erreur est une réponse client stable.
assert_equal(invalid_document_id.status_code, 400, "Un DocumentId invalide doit retourner 400.")
assert_equal(
    invalid_document_id.body,
    {"error_code": "HTTP_REQUEST_INVALID", "field": "document_id"},
    "Le DocumentId invalide doit être nommé.",
)

# Given l'identifiant public est absent dans le chemin de diagnostic.
# When l'endpoint de diagnostic est appelé.
empty_document_id = post_diagnose(adapter, "")

# Then l'erreur reste une réponse client stable.
assert_equal(empty_document_id.status_code, 400, "Un DocumentId absent doit retourner 400.")
assert_equal(
    empty_document_id.body,
    {"error_code": "HTTP_REQUEST_INVALID", "field": "document_id"},
    "Le DocumentId absent doit être nommé.",
)

print("Test d'acceptation T-008 contrat HTTP documentaire SP: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m003_document_http_contract_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-008 contrat HTTP documentaire SP: OK"
