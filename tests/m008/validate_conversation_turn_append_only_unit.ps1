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
from app.conversation.domain.conversation import (
    Conversation,
    ConversationStatus,
    ConversationTurn,
    ConversationTurnRole,
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
    except (AttributeError, TypeError, ValueError) as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


def conversation_payload():
    return {
        "conversation_id": "CONV-M008-T003-UNIT",
        "title": "Volatility targeting",
        "default_mandate": {"allowed_universe": ("documents canoniques OSTrading",)},
        "presentation_preferences": {"citation_style": "source_locator"},
        "occurred_at": "2026-07-01T10:10:00Z",
    }


conversation = Conversation.start(**conversation_payload())
assert_equal(conversation.status, ConversationStatus.ACTIVE, "La conversation doit etre active.")
assert_equal(tuple(event.event_type for event in conversation.events), ("ConversationCreated",), "La creation doit emettre un evenement.")
assert_raises("conversation_id invalide", lambda: Conversation.start(**{**conversation_payload(), "conversation_id": "BAD-1"}))
assert_raises("title vide", lambda: Conversation.start(**{**conversation_payload(), "title": ""}))
assert_raises("default_mandate vide", lambda: Conversation.start(**{**conversation_payload(), "default_mandate": {}}))
assert_raises("presentation_preferences non objet", lambda: Conversation.start(**{**conversation_payload(), "presentation_preferences": ()}))
assert_raises("occurred_at invalide", lambda: Conversation.start(**{**conversation_payload(), "occurred_at": "2026-07-01"}))

turn = ConversationTurn.user_turn(
    conversation_id=conversation.conversation_id,
    turn_id="TURN-M008-T003-UNIT-0001",
    sequence=1,
    message="Compare le volatility targeting a Kelly.",
    idempotency_key="IDEMP-M008-T003-UNIT-0001",
    occurred_at="2026-07-01T10:11:00Z",
)
assert_equal(turn.role, ConversationTurnRole.USER, "Le tour doit etre utilisateur.")
assert_equal(tuple(event.event_type for event in turn.events), ("UserTurnAppended",), "Le tour doit emettre UserTurnAppended.")
assert_raises("turn_id invalide", lambda: ConversationTurn.user_turn(conversation.conversation_id, "BAD", 1, "message", "IDEMP-M008-T003-X", "2026-07-01T10:11:00Z"))
assert_raises("sequence invalide", lambda: ConversationTurn.user_turn(conversation.conversation_id, "TURN-M008-T003-X", 0, "message", "IDEMP-M008-T003-X", "2026-07-01T10:11:00Z"))
assert_raises("message vide", lambda: ConversationTurn.user_turn(conversation.conversation_id, "TURN-M008-T003-X", 1, "", "IDEMP-M008-T003-X", "2026-07-01T10:11:00Z"))
assert_raises("cannot assign", lambda: setattr(turn, "message", "mutation interdite"))

conversation_repository = InMemoryConversationRepository.empty()
turn_repository = InMemoryTurnRepository.empty()
conversation_repository.save(conversation)
assert_equal(conversation_repository.conversation_count(), 1, "La conversation doit etre persistee.")
assert_raises("conversation deja enregistree", lambda: conversation_repository.save(Conversation.start(**{**conversation_payload(), "title": "Autre titre"})))
assert_raises("conversation inconnue", lambda: conversation_repository.conversation_for_id("CONV-M008-T003-UNKNOWN"))

turn_repository.save(turn)
assert_equal(turn_repository.next_sequence_for_conversation(conversation.conversation_id), 2, "La sequence suivante doit etre stricte.")
assert_equal(tuple(item.turn_id for item in turn_repository.turns_for_conversation(conversation.conversation_id)), ("TURN-M008-T003-UNIT-0001",), "Les tours doivent rester ordonnes.")
assert_raises("turn deja enregistre", lambda: turn_repository.save(ConversationTurn.user_turn(conversation.conversation_id, "TURN-M008-T003-UNIT-0001", 2, "autre message", "IDEMP-M008-T003-UNIT-0002", "2026-07-01T10:12:00Z")))
assert_raises("sequence conversation incoherente", lambda: turn_repository.save(ConversationTurn.user_turn(conversation.conversation_id, "TURN-M008-T003-UNIT-0002", 3, "autre message", "IDEMP-M008-T003-UNIT-0002", "2026-07-01T10:12:00Z")))

other_turn_repository = InMemoryTurnRepository.empty()
append_handler = AppendUserTurnHandler(
    conversation_repository=conversation_repository,
    turn_repository=other_turn_repository,
)
result = append_handler.append_user_turn(
    AppendUserTurnCommand(
        conversation_id=conversation.conversation_id,
        turn_id="TURN-M008-T003-UNIT-0002",
        message="Ajoute un deuxieme tour.",
        idempotency_key="IDEMP-M008-T003-UNIT-0003",
        occurred_at="2026-07-01T10:13:00Z",
    )
)
assert_equal(result.sequence, 1, "Un repository vide doit commencer a la sequence 1.")
assert_raises(
    "conversation inconnue",
    lambda: append_handler.append_user_turn(
        AppendUserTurnCommand(
            conversation_id="CONV-M008-T003-UNKNOWN",
            turn_id="TURN-M008-T003-UNIT-0003",
            message="tour orphelin",
            idempotency_key="IDEMP-M008-T003-UNIT-0004",
            occurred_at="2026-07-01T10:14:00Z",
        )
    ),
)

archived = conversation.archive(
    archived_at="2026-07-01T10:15:00Z",
    retention_policy_version="conversation-retention-m008-v1",
)
conversation_repository.update(archived)
assert_equal(archived.status, ConversationStatus.ARCHIVED, "La conversation doit etre archivee.")
assert_raises(
    "conversation archivee",
    lambda: append_handler.append_user_turn(
        AppendUserTurnCommand(
            conversation_id=conversation.conversation_id,
            turn_id="TURN-M008-T003-UNIT-0004",
            message="tour refuse",
            idempotency_key="IDEMP-M008-T003-UNIT-0005",
            occurred_at="2026-07-01T10:16:00Z",
        )
    ),
)

start_handler = StartConversationHandler(conversation_repository=InMemoryConversationRepository.empty())
started = start_handler.start(StartConversationCommand(**conversation_payload()))
assert_equal(started.status, "CONVERSATION_CREATED", "Le handler de creation doit exposer le statut public.")

print("Tests unitaires T-003 conversations append-only M-008: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m008_conversation_turn_append_only_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-003 conversations append-only M-008: OK"
