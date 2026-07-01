$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

sys.path.insert(0, sys.argv[1])

from app.conversation.application.resolve_followup_question import (
    DeterministicQuestionResolver,
    ReferenceResolutionPolicy,
    ResolveFollowUpQuestionCommand,
    ResolveFollowUpQuestionHandler,
    ResolvedQuestion,
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


def assert_raises(expected_fragment, action):
    try:
        action()
    except (AttributeError, TypeError, ValueError) as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


def snapshot(subjects=("volatility targeting",), ambiguities=()):
    return ConversationContextSnapshot(
        conversation_id="CONV-M008-T005-UNIT",
        active_mandate={
            "allowed_universe": ("documents canoniques OSTrading",),
            "conversation_subjects": subjects,
        },
        user_preferences={"language": "fr"},
        selected_document_ids=("DOC-M008-T005-UNIT",),
        verified_answer_refs=("ANS-M008-T005-UNIT@3",),
        historical_assertions_to_revalidate=("Assertion a revalider.",),
        ambiguities=ambiguities,
        created_at="2026-07-01T12:10:00Z",
    )


def command(user_message, context_snapshot=None):
    return ResolveFollowUpQuestionCommand(
        conversation_id="CONV-M008-T005-UNIT",
        turn_id="TURN-M008-T005-UNIT",
        user_message=user_message,
        context_snapshot=context_snapshot or snapshot(),
        occurred_at="2026-07-01T12:11:00Z",
    )


policy = ReferenceResolutionPolicy()
result = policy.resolve(command("compare-la maintenant a Kelly"))
assert_equal(result.status, "QUESTION_RESOLVED", "Une reference unique doit etre resolue.")
assert_true("volatility targeting" in result.resolved_question.text, "Le sujet historique doit etre explicite.")
assert_equal(tuple(result.resolved_question.selected_document_ids), ("DOC-M008-T005-UNIT",), "Les documents selectionnes doivent etre conserves.")
assert_equal(tuple(result.resolved_question.verified_answer_refs), ("ANS-M008-T005-UNIT@3",), "Les refs verifiees doivent etre conservees.")
assert_true(result.downstream_call_permitted, "Le routage aval doit etre permis apres resolution.")

direct = policy.resolve(command("Analyse Kelly criterion"))
assert_equal(direct.status, "QUESTION_RESOLVED", "Une question autonome doit rester resolue.")
assert_equal(direct.resolved_question.text, "Analyse Kelly criterion", "La question autonome ne doit pas etre reformulee.")

ambiguous = policy.resolve(command("compare-la a Kelly", snapshot(("volatility targeting", "risk parity"))))
assert_equal(ambiguous.status, "CLARIFICATION_REQUIRED", "Plusieurs antecedents exigent clarification.")
assert_true(ambiguous.resolved_question is None, "Aucune question aval ne doit exister si la reference est ambigue.")
assert_false(ambiguous.downstream_call_permitted, "Aucun appel aval ne doit etre permis avant clarification.")
assert_equal(tuple(event.event_type for event in ambiguous.events), ("FollowUpQuestionClarificationRequired",), "La clarification doit etre signalee.")

missing_subject = policy.resolve(command("compare-la a Kelly", snapshot(())))
assert_equal(missing_subject.status, "CLARIFICATION_REQUIRED", "Un pronom sans antecedent doit exiger clarification.")

assert_raises(
    "resolved_question vide",
    lambda: ResolvedQuestion(
        conversation_id="CONV-M008-T005-UNIT",
        turn_id="TURN-M008-T005-UNIT",
        text="",
        active_mandate={"allowed_universe": ("documents canoniques OSTrading",)},
        selected_document_ids=("DOC-M008-T005-UNIT",),
        verified_answer_refs=("ANS-M008-T005-UNIT@3",),
        occurred_at="2026-07-01T12:12:00Z",
    ),
)

handler = ResolveFollowUpQuestionHandler(question_resolver=DeterministicQuestionResolver())
handled = handler.resolve(command("compare-la maintenant a Kelly"))
assert_equal(handled.status, "QUESTION_RESOLVED", "Le handler doit exposer la decision.")
assert_false(handled.raw_message_forwarded, "Le handler ne doit pas propager le message ambigu.")
assert_raises("user_message vide", lambda: handler.resolve(command("")))
assert_raises("context_snapshot invalide", lambda: handler.resolve(command("compare-la a Kelly", object())))
assert_raises("question_resolver sans resolve", lambda: ResolveFollowUpQuestionHandler(question_resolver=object()))

print("Tests unitaires T-005 resolution reference suivi M-008: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m008_followup_resolution_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-005 resolution reference suivi M-008: OK"
