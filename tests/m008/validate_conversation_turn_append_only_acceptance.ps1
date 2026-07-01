$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

sys.path.insert(0, sys.argv[1])

from app.conversation.adapters.in_memory_conversation_repository import (
    InMemoryConversationRepository,
)
from app.conversation.adapters.in_memory_turn_repository import InMemoryTurnRepository
from app.conversation.application.append_turn import (
    AppendUserTurnCommand,
    AppendUserTurnHandler,
)
from app.conversation.application.start_conversation import (
    StartConversationCommand,
    StartConversationHandler,
)


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


conversation_repository = InMemoryConversationRepository.empty()
turn_repository = InMemoryTurnRepository.empty()

start_handler = StartConversationHandler(conversation_repository=conversation_repository)
append_handler = AppendUserTurnHandler(
    conversation_repository=conversation_repository,
    turn_repository=turn_repository,
)

# Given une conversation active existe pour un mandat documentaire.
started = start_handler.start(
    StartConversationCommand(
        conversation_id="CONV-M008-T003-ACCEPTANCE",
        title="Volatility targeting",
        default_mandate={
            "allowed_universe": ("documents canoniques OSTrading",),
            "language": "fr",
        },
        presentation_preferences={"citation_style": "source_locator"},
        occurred_at="2026-07-01T10:00:00Z",
    )
)

assert_equal(started.status, "CONVERSATION_CREATED", "La creation doit etre explicite.")

conversation_before = conversation_repository.conversation_for_id(
    "CONV-M008-T003-ACCEPTANCE"
)

# When l'utilisateur ajoute un message dans cette conversation.
appended = append_handler.append_user_turn(
    AppendUserTurnCommand(
        conversation_id="CONV-M008-T003-ACCEPTANCE",
        turn_id="TURN-M008-T003-0001",
        message="Compare ce cadre au Kelly criterion.",
        idempotency_key="IDEMP-M008-T003-0001",
        occurred_at="2026-07-01T10:01:00Z",
    )
)

# Then un nouveau tour append-only est cree avec son ordre, son horodatage et son appartenance a la conversation sans modifier les tours precedents.
assert_equal(appended.status, "USER_TURN_APPENDED", "Le handler doit annoncer le tour utilisateur.")
assert_equal(appended.sequence, 1, "Le premier tour doit porter l'ordre 1.")
assert_equal(appended.conversation_id, "CONV-M008-T003-ACCEPTANCE", "Le tour doit appartenir a la conversation.")

turns = turn_repository.turns_for_conversation("CONV-M008-T003-ACCEPTANCE")
assert_equal(len(turns), 1, "Le repository doit exposer un tour.")
assert_equal(turns[0].turn_id, "TURN-M008-T003-0001", "Le tour persiste doit etre consultable.")
assert_equal(turns[0].sequence, 1, "Le tour persiste doit garder son ordre.")
assert_equal(turns[0].message, "Compare ce cadre au Kelly criterion.", "Le message doit etre fige.")
assert_equal(turns[0].occurred_at, "2026-07-01T10:01:00Z", "L'horodatage doit etre fige.")

conversation_after = conversation_repository.conversation_for_id(
    "CONV-M008-T003-ACCEPTANCE"
)
assert_equal(conversation_before, conversation_after, "Ajouter un tour ne doit pas reecrire Conversation.")
assert_true(
    tuple(event.event_type for event in started.events) == ("ConversationCreated",),
    "La creation doit publier ConversationCreated.",
)
assert_true(
    tuple(event.event_type for event in appended.events) == ("UserTurnAppended",),
    "L'ajout doit publier UserTurnAppended.",
)

print("Test d'acceptation T-003 conversations append-only M-008: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m008_conversation_turn_append_only_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-003 conversations append-only M-008: OK"
