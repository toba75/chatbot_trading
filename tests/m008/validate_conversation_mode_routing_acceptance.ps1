$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

sys.path.insert(0, sys.argv[1])

from app.conversation.application.resolve_followup_question import ResolvedQuestion
from app.conversation.application.select_mode import (
    DeterministicModeClassifier,
    SelectConversationModeCommand,
    SelectConversationModeHandler,
)
from app.conversation.domain.mode_routing import ConversationMode


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def assert_false(condition, message):
    if condition:
        raise AssertionError(message)


def question(text):
    return ResolvedQuestion(
        conversation_id="CONV-M008-T006-ACCEPTANCE",
        turn_id="TURN-M008-T006-ACCEPTANCE",
        text=text,
        active_mandate={"allowed_universe": ("documents canoniques OSTrading",)},
        selected_document_ids=("DOC-M008-T006-A",),
        verified_answer_refs=("ANS-M008-T006-A@1",),
        occurred_at="2026-07-01T13:00:00Z",
    )


all_modes = tuple(mode.value for mode in ConversationMode)
handler = SelectConversationModeHandler(mode_classifier=DeterministicModeClassifier())

# Given une question autonome demande de tester une strategie avec des couts doubles.
command = SelectConversationModeCommand(
    conversation_id="CONV-M008-T006-ACCEPTANCE",
    turn_id="TURN-M008-T006-ACCEPTANCE",
    resolved_question=question("Tester la strategie momentum avec des couts doubles sur 2018-2024."),
    requested_mode=None,
    available_modes=all_modes,
    occurred_at="2026-07-01T13:01:00Z",
)

# When le mode conversationnel est selectionne.
result = handler.select(command)

# Then le tour enregistre BACKTEST avec une justification et ne bascule pas silencieusement vers CHAT_DOCUMENTAIRE.
assert_equal(result.status, "MODE_SELECTED", "Le statut doit annoncer le mode selectionne.")
assert_equal(result.selection.mode, ConversationMode.BACKTEST, "La demande doit etre routee en BACKTEST.")
assert_true("backtest" in result.selection.justification.lower(), "La justification doit nommer le backtest.")
assert_false(result.selection.mode == ConversationMode.CHAT_DOCUMENTAIRE, "Le routage ne doit pas revenir au documentaire.")
assert_equal(result.downstream_context, "EX", "Le backtest doit pointer vers EX sans executer EX.")
assert_equal(tuple(event.event_type for event in result.events), ("ConversationModeSelected",), "L'evenement de mode doit etre publie.")

samples = {
    "Explique le resultat avec les citations documentaires.": ConversationMode.CHAT_DOCUMENTAIRE,
    "Fais une recherche approfondie sur ce risque.": ConversationMode.RECHERCHE_APPROFONDIE,
    "Compare volatility targeting et Kelly.": ConversationMode.COMPARAISON,
    "Conçois une strategie de rotation sectorielle.": ConversationMode.CONCEPTION_STRATEGIE,
    "Calcule le drawdown maximal.": ConversationMode.CALCUL,
    "Clarifie cette reference ambigue.": ConversationMode.CLARIFICATION_INTERNE,
}
for text, expected_mode in samples.items():
    selected = handler.select(
        SelectConversationModeCommand(
            conversation_id="CONV-M008-T006-ACCEPTANCE",
            turn_id="TURN-M008-T006-ACCEPTANCE",
            resolved_question=question(text),
            requested_mode=None,
            available_modes=all_modes,
            occurred_at="2026-07-01T13:02:00Z",
        )
    )
    assert_equal(selected.selection.mode, expected_mode, f"Mode attendu pour: {text}")
    assert_true(selected.selection.justification.strip() != "", "La justification ne doit jamais etre vide.")

print("Test d'acceptation T-006 routage modes conversation M-008: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m008_mode_routing_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-006 routage modes conversation M-008: OK"
