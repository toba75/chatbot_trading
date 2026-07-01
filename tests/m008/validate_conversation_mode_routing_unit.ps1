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
    ModeClassificationResult,
    SelectConversationModeCommand,
    SelectConversationModeHandler,
)
from app.conversation.domain.mode_routing import (
    ConversationMode,
    ConversationModeRoutingPolicy,
    ConversationModeSelection,
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


def resolved_question(text):
    return ResolvedQuestion(
        conversation_id="CONV-M008-T006-UNIT",
        turn_id="TURN-M008-T006-UNIT",
        text=text,
        active_mandate={"allowed_universe": ("documents canoniques OSTrading",)},
        selected_document_ids=("DOC-M008-T006-UNIT",),
        verified_answer_refs=("ANS-M008-T006-UNIT@1",),
        occurred_at="2026-07-01T13:10:00Z",
    )


all_modes = tuple(mode.value for mode in ConversationMode)
policy = ConversationModeRoutingPolicy()
classifier = DeterministicModeClassifier()
handler = SelectConversationModeHandler(mode_classifier=classifier)

forced = handler.select(
    SelectConversationModeCommand(
        conversation_id="CONV-M008-T006-UNIT",
        turn_id="TURN-M008-T006-UNIT",
        resolved_question=resolved_question("Compare les deux methodes."),
        requested_mode="COMPARAISON",
        available_modes=all_modes,
        occurred_at="2026-07-01T13:11:00Z",
    )
)
assert_equal(forced.selection.mode, ConversationMode.COMPARAISON, "Un mode force valide doit etre respecte.")
assert_true("force" in forced.selection.justification.lower(), "Le mode force doit etre justifie.")

assert_raises(
    "mode conversation invalide",
    lambda: handler.select(
        SelectConversationModeCommand(
            conversation_id="CONV-M008-T006-UNIT",
            turn_id="TURN-M008-T006-UNIT",
            resolved_question=resolved_question("Analyse documentaire."),
            requested_mode="MODE_INCONNU",
            available_modes=all_modes,
            occurred_at="2026-07-01T13:12:00Z",
        )
    ),
)

assert_raises(
    "mode conversation indisponible",
    lambda: handler.select(
        SelectConversationModeCommand(
            conversation_id="CONV-M008-T006-UNIT",
            turn_id="TURN-M008-T006-UNIT",
            resolved_question=resolved_question("Tester cette strategie."),
            requested_mode=None,
            available_modes=("CHAT_DOCUMENTAIRE", "COMPARAISON"),
            occurred_at="2026-07-01T13:13:00Z",
        )
    ),
)

assert_raises(
    "justification mode vide",
    lambda: policy.select(
        conversation_id="CONV-M008-T006-UNIT",
        turn_id="TURN-M008-T006-UNIT",
        requested_mode=None,
        classifier_result=ModeClassificationResult(
            mode=ConversationMode.CALCUL,
            justification="",
            classifier_label="empty-justification",
        ),
        available_modes=all_modes,
        occurred_at="2026-07-01T13:14:00Z",
    ),
)

assert_equal(classifier.classify(resolved_question("Compare Kelly et volatility targeting.")).mode, ConversationMode.COMPARAISON, "La comparaison doit primer sur approfondi.")
assert_equal(classifier.classify(resolved_question("Fais une recherche approfondie sur Kelly.")).mode, ConversationMode.RECHERCHE_APPROFONDIE, "Approfondi doit etre distinct du documentaire.")
assert_equal(classifier.classify(resolved_question("Calcule la volatilite annualisee.")).mode, ConversationMode.CALCUL, "Le calcul doit etre distinct du backtest.")
assert_equal(classifier.classify(resolved_question("Backtest la strategie avec frais doubles.")).mode, ConversationMode.BACKTEST, "Le backtest doit etre distinct du calcul.")
assert_raises("mode conversation non classable", lambda: classifier.classify(resolved_question("Que penses-tu ?")))

selection = ConversationModeSelection(
    conversation_id="CONV-M008-T006-UNIT",
    turn_id="TURN-M008-T006-UNIT",
    mode=ConversationMode.CHAT_DOCUMENTAIRE,
    justification="Demande documentaire explicite.",
    policy_version="mode-routing-m008-v1",
    classifier_label="documentary",
    occurred_at="2026-07-01T13:15:00Z",
)
assert_equal(selection.mode, ConversationMode.CHAT_DOCUMENTAIRE, "La selection doit conserver le mode.")
assert_raises(
    "justification mode vide",
    lambda: ConversationModeSelection(
        conversation_id="CONV-M008-T006-UNIT",
        turn_id="TURN-M008-T006-UNIT",
        mode=ConversationMode.CHAT_DOCUMENTAIRE,
        justification="",
        policy_version="mode-routing-m008-v1",
        classifier_label="documentary",
        occurred_at="2026-07-01T13:15:00Z",
    ),
)
assert_raises("mode_classifier sans classify", lambda: SelectConversationModeHandler(mode_classifier=object()))

print("Tests unitaires T-006 routage modes conversation M-008: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m008_mode_routing_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-006 routage modes conversation M-008: OK"
