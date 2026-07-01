$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

sys.path.insert(0, sys.argv[1])

from app.conversation.application.resolve_followup_question import (
    DeterministicQuestionResolver,
    ResolveFollowUpQuestionCommand,
    ResolveFollowUpQuestionHandler,
)
from app.conversation.domain.context_snapshot import ConversationContextSnapshot


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def assert_false(condition, message):
    if condition:
        raise AssertionError(message)


# Given une conversation portant sur le volatility targeting.
snapshot = ConversationContextSnapshot(
    conversation_id="CONV-M008-T005-ACCEPTANCE",
    active_mandate={
        "allowed_universe": ("documents canoniques OSTrading",),
        "conversation_subjects": ("volatility targeting",),
        "language": "fr",
    },
    user_preferences={"tone": "concis"},
    selected_document_ids=("DOC-M008-T005-VOL",),
    verified_answer_refs=("ANS-M008-T005-VOL@2",),
    historical_assertions_to_revalidate=(),
    ambiguities=(),
    created_at="2026-07-01T12:00:00Z",
)
handler = ResolveFollowUpQuestionHandler(question_resolver=DeterministicQuestionResolver())

# When l'utilisateur ecrit compare-la maintenant a Kelly.
result = handler.resolve(
    ResolveFollowUpQuestionCommand(
        conversation_id="CONV-M008-T005-ACCEPTANCE",
        turn_id="TURN-M008-T005-ACCEPTANCE",
        user_message="compare-la maintenant a Kelly",
        context_snapshot=snapshot,
        occurred_at="2026-07-01T12:01:00Z",
    )
)

# Then une question autonome mentionnant explicitement le volatility targeting et Kelly est produite avant tout appel a RA.
assert_equal(result.status, "QUESTION_RESOLVED", "Le suivi doit etre resolu.")
assert_true(result.downstream_call_permitted, "L'appel aval doit etre permis seulement apres resolution.")
assert_false(result.raw_message_forwarded, "Le message ambigu ne doit pas etre transmis comme question aval.")
resolved = result.resolved_question
assert_true(resolved is not None, "La question autonome doit etre presente.")
assert_true("volatility targeting" in resolved.text, "La question autonome doit mentionner le sujet resolu.")
assert_true("Kelly" in resolved.text, "La question autonome doit mentionner Kelly.")
assert_false("compare-la" in resolved.text, "La question autonome ne doit pas conserver le pronom ambigu.")
assert_equal(tuple(resolved.selected_document_ids), ("DOC-M008-T005-VOL",), "Les documents selectionnes doivent suivre la question resolue.")
assert_equal(tuple(resolved.verified_answer_refs), ("ANS-M008-T005-VOL@2",), "La reference verifiee doit suivre la question resolue.")
assert_equal(result.downstream_payload["question"], resolved.text, "Le payload aval doit porter la question autonome.")
assert_equal(tuple(event.event_type for event in result.events), ("FollowUpQuestionResolved",), "L'evenement de resolution doit etre publie.")

print("Test d'acceptation T-005 resolution reference suivi M-008: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m008_followup_resolution_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-005 resolution reference suivi M-008: OK"
