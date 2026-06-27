$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

sys.path.insert(0, sys.argv[1])

from app.contracts.source_references import CanonicalSourceRef
from app.knowledge_access.adapters.in_memory_projection_repository import (
    InMemoryKnowledgeProjectionRepository,
)
from app.knowledge_access.adapters.projection_http import (
    HttpRequest,
    KnowledgeProjectionHttpAdapter,
)
from app.knowledge_access.application.request_projection import (
    CanonicalSourceForProjection,
    RequestKnowledgeProjectionHandler,
)


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def canonical_ref(suffix):
    return CanonicalSourceRef.from_payload(
        {
            "schema_version": "1.0",
            "canonical_source_id": f"CSRC-M005-IDX-{suffix}",
            "document_id": f"DOC-M005-IDX-{suffix}",
            "canonical_version_id": f"CVER-M005-IDX-{suffix}-0001",
            "source_sha256": "c" * 64,
            "canonical_artifact_sha256": "d" * 64,
            "page_count": 2,
            "accepted_at": "2026-06-27T14:00:00Z",
            "quality_policy_version": "canonical-quality-m005-index-v1",
        }
    )


def profile_body():
    return {
        "projection_profile_id": "projection-profile-m005-index-v1",
        "chunking_profile": "chunking-index-v1",
        "embedding_model": "embedding-index-v1",
        "sparse_profile": "sparse-index-v1",
        "index_schema": "index-schema-m005-v1",
    }


class CanonicalReader:
    def __init__(self, records):
        self.records = dict(records)

    def find_projection_source_by_document_id(self, document_id):
        return self.records.get(document_id)


def build_adapter(records):
    repository = InMemoryKnowledgeProjectionRepository.empty()
    handler = RequestKnowledgeProjectionHandler(
        canonical_source_reader=CanonicalReader(records),
        projection_repository=repository,
    )
    return KnowledgeProjectionHttpAdapter(projection_commands=handler), repository


def request(method, path, body):
    return HttpRequest(method=method, path=path, body=body)


published_ref = canonical_ref("PUBLISHED")
quarantined_document_id = "DOC-M005-IDX-QUARANTINED"
non_canonical_document_id = "DOC-M005-IDX-NONCANONICAL"
adapter, repository = build_adapter(
    {
        published_ref.document_id: CanonicalSourceForProjection(
            document_id=published_ref.document_id,
            canonical_ref=published_ref,
            canonical_status="ACCEPTED",
            quarantine_reason=None,
        ),
        quarantined_document_id: CanonicalSourceForProjection(
            document_id=quarantined_document_id,
            canonical_ref=None,
            canonical_status="QUARANTINED",
            quarantine_reason="QA bloquante.",
        ),
        non_canonical_document_id: CanonicalSourceForProjection(
            document_id=non_canonical_document_id,
            canonical_ref=None,
            canonical_status="REJECTED",
            quarantine_reason=None,
        ),
    }
)

# Given le contrat public KA POST /v1/documents/{document_id}/index.
# When la version canonique publiee est demandee avec un profil complet.
# Then la reponse publique est 202 et expose seulement l'etat de projection.
accepted = adapter.handle(
    request("POST", f"/v1/documents/{published_ref.document_id}/index", profile_body())
)
assert_equal(accepted.status_code, 202, "Le contrat d'indexation doit accepter une version canonique.")
assert_equal(
    set(accepted.body.keys()),
    {"document_id", "projection_id", "projection_status", "canonical_version_id"},
    "La reponse d'indexation doit rester publique et minimale.",
)
assert_equal(accepted.body["projection_status"], "REQUESTED", "La commande ne doit pas rendre la projection SEARCHABLE.")
assert_equal(repository.projection_count(), 1, "La commande doit persister une projection.")

# Given le meme index est redemande.
# Then le contrat refuse explicitement le doublon au lieu de reconstruire silencieusement.
duplicate = adapter.handle(
    request("POST", f"/v1/documents/{published_ref.document_id}/index", profile_body())
)
assert_equal(duplicate.status_code, 409, "Un doublon de projection doit retourner 409.")
assert_equal(duplicate.body["error_code"], "PROJECTION_ALREADY_REQUESTED", "Le doublon doit porter un code public.")
assert_equal(repository.projection_count(), 1, "Le doublon ne doit pas creer de deuxieme projection.")

# Given une source inconnue, non canonique ou en quarantaine.
# Then l'endpoint ne retourne jamais 202.
unknown = adapter.handle(
    request("POST", "/v1/documents/DOC-M005-IDX-UNKNOWN/index", profile_body())
)
assert_equal(unknown.status_code, 404, "Une source inconnue doit retourner 404.")
assert_equal(unknown.body, {"error_code": "SOURCE_NOT_FOUND", "document_id": "DOC-M005-IDX-UNKNOWN"}, "SOURCE_NOT_FOUND doit etre stable.")

non_canonical = adapter.handle(
    request("POST", f"/v1/documents/{non_canonical_document_id}/index", profile_body())
)
assert_equal(non_canonical.status_code, 409, "Une source non canonique doit retourner 409.")
assert_equal(non_canonical.body["error_code"], "SOURCE_NOT_CANONICAL", "SOURCE_NOT_CANONICAL doit etre stable.")

quarantined = adapter.handle(
    request("POST", f"/v1/documents/{quarantined_document_id}/index", profile_body())
)
assert_equal(quarantined.status_code, 409, "Une source en quarantaine doit retourner 409.")
assert_equal(quarantined.body["error_code"], "SOURCE_QUARANTINED", "SOURCE_QUARANTINED doit etre stable.")

# Given un corps ambigu, vide, incomplet ou un document_id invalide.
# Then le transport refuse sans valeur par defaut ni fallback.
ambiguous_body = {**profile_body(), "embedding_profile": "alias-ambigu"}
ambiguous = adapter.handle(
    request("POST", f"/v1/documents/{published_ref.document_id}/index", ambiguous_body)
)
assert_equal(ambiguous.status_code, 400, "Un corps avec alias ambigu doit retourner 400.")
assert_equal(ambiguous.body, {"error_code": "HTTP_REQUEST_INVALID", "field": "body"}, "Le champ body doit etre nomme.")

empty_body = adapter.handle(
    request("POST", f"/v1/documents/{published_ref.document_id}/index", {})
)
assert_equal(empty_body.status_code, 400, "Un corps vide doit retourner 400.")
assert_equal(empty_body.body["error_code"], "HTTP_REQUEST_INVALID", "Le corps vide doit etre invalide.")

missing_profile_body = dict(profile_body())
del missing_profile_body["chunking_profile"]
missing_profile = adapter.handle(
    request("POST", f"/v1/documents/{published_ref.document_id}/index", missing_profile_body)
)
assert_equal(missing_profile.status_code, 422, "Un profil incomplet doit retourner 422.")
assert_equal(missing_profile.body["error_code"], "PROJECTION_PROFILE_INVALID", "Aucun profil manquant ne doit recevoir de valeur par defaut.")

invalid_document_id = adapter.handle(
    request("POST", "/v1/documents/not-a-domain-id/index", profile_body())
)
assert_equal(invalid_document_id.status_code, 400, "Un document_id invalide doit retourner 400.")
assert_equal(invalid_document_id.body, {"error_code": "HTTP_REQUEST_INVALID", "field": "document_id"}, "Le document_id invalide doit etre public.")

wrong_endpoint = adapter.handle(
    request("POST", f"/v1/documents/{published_ref.document_id}/convert", profile_body())
)
assert_equal(wrong_endpoint.status_code, 404, "L'adaptateur KA ne doit pas router l'endpoint SP /convert.")
assert_true(
    wrong_endpoint.body["error_code"] == "ENDPOINT_NOT_FOUND",
    "Le mauvais endpoint doit etre refuse explicitement.",
)

print("Test d'acceptation T-003 contrat HTTP indexation KA M-005: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m005_index_command_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-003 contrat HTTP indexation KA M-005: OK"
