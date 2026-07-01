$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

sys.path.insert(0, sys.argv[1])

from app.conversation.adapters.conversation_http import ConversationHttpAdapter, HttpRequest
from app.conversation.adapters.in_memory_conversation_repository import InMemoryConversationRepository
from app.conversation.adapters.in_memory_turn_repository import InMemoryTurnRepository


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_false(condition, message):
    if condition:
        raise AssertionError(message)


def assert_raises(expected_fragment, action):
    try:
        action()
    except (AttributeError, TypeError, ValueError) as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


class SequenceIdFactory:
    def __init__(self, values):
        self.values = list(values)

    def next_id(self):
        if not self.values:
            raise AssertionError("Identifiant inattendu")
        return self.values.pop(0)


def adapter():
    return ConversationHttpAdapter(
        conversation_repository=InMemoryConversationRepository.empty(),
        turn_repository=InMemoryTurnRepository.empty(),
        conversation_id_factory=SequenceIdFactory(("CONV-M008-T009-UNIT",)),
        turn_id_factory=SequenceIdFactory(("TURN-M008-T009-UNIT-A", "TURN-M008-T009-UNIT-B")),
        retention_policy_version="conversation-retention-m008-v1",
    )


def create_request():
    return HttpRequest(
        method="POST",
        path="/v1/conversations",
        body={
            "title": "Conversation unitaire",
            "default_mandate": {"allowed_universe": ["documents canoniques OSTrading"]},
            "presentation_preferences": {"language": "fr"},
            "occurred_at": "2026-07-01T16:10:00Z",
        },
    )


http = adapter()
created = http.handle(create_request())
assert_equal(created.status_code, 201, "Creation conversation attendue.")
assert_equal(created.body["conversation_id"], "CONV-M008-T009-UNIT", "L'identifiant genere doit etre publie.")

read = http.handle(HttpRequest(method="GET", path="/v1/conversations/CONV-M008-T009-UNIT", body={}))
assert_equal(read.status_code, 200, "Lecture conversation attendue.")
assert_equal(read.body["status"], "ACTIVE", "Le statut initial doit etre actif.")

missing = http.handle(HttpRequest(method="GET", path="/v1/conversations/CONV-MISSING", body={}))
assert_equal(missing.status_code, 404, "Une conversation absente doit etre 404.")
assert_equal(missing.body["error_code"], "CONVERSATION_NOT_FOUND", "Le code public doit etre stable.")

invalid_payload = adapter().handle(
    HttpRequest(
        method="POST",
        path="/v1/conversations",
        body={
            "title": "Conversation interdite",
            "default_mandate": {"allowed_universe": ["documents canoniques OSTrading"]},
            "presentation_preferences": {},
            "occurred_at": "2026-07-01T16:10:00Z",
            "ra_storage": "table_interne",
        },
    )
)
assert_equal(invalid_payload.status_code, 400, "Un champ interne doit etre refuse.")
assert_equal(invalid_payload.body["error_code"], "HTTP_REQUEST_INVALID", "Le code d'erreur invalide doit etre public.")

missing_idempotency = http.handle(
    HttpRequest(
        method="POST",
        path="/v1/conversations/CONV-M008-T009-UNIT/messages",
        body={"message": "Message sans idempotence.", "occurred_at": "2026-07-01T16:11:00Z"},
    )
)
assert_equal(missing_idempotency.status_code, 400, "idempotency_key est obligatoire.")
assert_equal(missing_idempotency.body["field"], "idempotency_key", "Le champ fautif doit etre visible.")

first = http.handle(
    HttpRequest(
        method="POST",
        path="/v1/conversations/CONV-M008-T009-UNIT/messages",
        body={
            "message": "Premier message.",
            "idempotency_key": "idem-unit-a",
            "occurred_at": "2026-07-01T16:11:00Z",
        },
    )
)
second = http.handle(
    HttpRequest(
        method="POST",
        path="/v1/conversations/CONV-M008-T009-UNIT/messages",
        body={
            "message": "Second message.",
            "idempotency_key": "idem-unit-b",
            "occurred_at": "2026-07-01T16:12:00Z",
        },
    )
)
assert_equal(first.body["turn_id"], "TURN-M008-T009-UNIT-A", "Premier tour attendu.")
assert_equal(second.body["sequence"], 2, "Second tour attendu.")
turns = http.handle(HttpRequest(method="GET", path="/v1/conversations/CONV-M008-T009-UNIT/turns", body={}))
assert_equal(tuple(turn["turn_id"] for turn in turns.body["turns"]), ("TURN-M008-T009-UNIT-A", "TURN-M008-T009-UNIT-B"), "Les tours doivent rester ordonnes.")
assert_false("repository" in repr(turns.body).lower(), "Le repository interne ne doit pas etre expose.")

archived = http.handle(
    HttpRequest(
        method="DELETE",
        path="/v1/conversations/CONV-M008-T009-UNIT",
        body={"occurred_at": "2026-07-01T16:13:00Z"},
    )
)
assert_equal(archived.status_code, 200, "Archive attendue.")
archived_message = http.handle(
    HttpRequest(
        method="POST",
        path="/v1/conversations/CONV-M008-T009-UNIT/messages",
        body={
            "message": "Message refuse.",
            "idempotency_key": "idem-unit-c",
            "occurred_at": "2026-07-01T16:14:00Z",
        },
    )
)
assert_equal(archived_message.status_code, 409, "Une conversation archivee refuse les messages.")
assert_equal(archived_message.body["error_code"], "CONVERSATION_ARCHIVED", "Le code archive doit etre stable.")
archive_again = http.handle(
    HttpRequest(
        method="DELETE",
        path="/v1/conversations/CONV-M008-T009-UNIT",
        body={"occurred_at": "2026-07-01T16:15:00Z"},
    )
)
assert_equal(archive_again.status_code, 409, "Double archive refusee.")

unknown_message = adapter().handle(
    HttpRequest(
        method="POST",
        path="/v1/conversations/CONV-MISSING/messages",
        body={
            "message": "Ne cree pas implicitement.",
            "idempotency_key": "idem-missing",
            "occurred_at": "2026-07-01T16:14:00Z",
        },
    )
)
assert_equal(unknown_message.status_code, 404, "POST messages ne doit pas creer une conversation.")
assert_raises("conversation_repository sans conversation_for_id", lambda: ConversationHttpAdapter(conversation_repository=object(), turn_repository=InMemoryTurnRepository.empty(), conversation_id_factory=SequenceIdFactory(("CONV-X",)), turn_id_factory=SequenceIdFactory(("TURN-X",)), retention_policy_version="policy"))

print("Tests unitaires T-009 contrat HTTP conversation M-008: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m008_conversation_http_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-009 contrat HTTP conversation M-008: OK"
