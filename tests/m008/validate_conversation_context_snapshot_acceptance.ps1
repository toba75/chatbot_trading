$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

sys.path.insert(0, sys.argv[1])

from app.conversation.adapters.in_memory_context_store import InMemoryConversationContextStore
from app.conversation.application.compact_context import (
    CompactConversationContextCommand,
    CompactConversationContextHandler,
)


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def assert_false(condition, message):
    if condition:
        raise AssertionError(message)


def assert_forbidden_absent(value):
    serialized = repr(value)
    for forbidden in (
        "raw_turns",
        "prompt",
        "answer_text",
        "document_text",
        "Compare ce cadre au Kelly criterion.",
    ):
        assert_false(forbidden in serialized, f"Payload sensible interdit: {forbidden}")


store = InMemoryConversationContextStore.empty()
handler = CompactConversationContextHandler(context_store=store)

# Given une conversation contient une preference utilisateur et une reponse precedente verifiee.
command = CompactConversationContextCommand(
    conversation_id="CONV-M008-T004-ACCEPTANCE",
    active_mandate={
        "allowed_universe": ("documents canoniques OSTrading",),
        "language": "fr",
    },
    user_preferences={"tone": "concis", "citation_style": "source_locator"},
    selected_document_ids=("DOC-M008-T004-A",),
    verified_answer_refs=("ANS-M008-T004-A@1",),
    historical_assertions=("Le volatility targeting reduit certains drawdowns.",),
    ambiguities=("la",),
    occurred_at="2026-07-01T11:00:00Z",
)

# When le contexte conversationnel est compacte.
result = handler.compact(command)

# Then le snapshot conserve la preference et la reference verifiee sans recopier l'historique comme preuve factuelle.
snapshot = result.snapshot
assert_equal(result.status, "CONVERSATION_CONTEXT_COMPACTED", "Le handler doit annoncer le compactage.")
assert_equal(snapshot.conversation_id, "CONV-M008-T004-ACCEPTANCE", "La conversation doit etre conservee.")
assert_equal(snapshot.user_preferences["tone"], "concis", "La preference utilisateur doit etre conservee.")
assert_equal(tuple(snapshot.selected_document_ids), ("DOC-M008-T004-A",), "Le document selectionne doit etre conserve.")
assert_equal(tuple(snapshot.verified_answer_refs), ("ANS-M008-T004-A@1",), "La version verifiee doit etre conservee.")
assert_equal(tuple(snapshot.historical_assertions_to_revalidate), ("Le volatility targeting reduit certains drawdowns.",), "L'assertion historique non versionnee doit etre a revalider.")
assert_equal(tuple(snapshot.ambiguities), ("la",), "L'ambiguite doit rester visible.")
assert_forbidden_absent(snapshot.to_payload())

stored = store.snapshot_for_conversation("CONV-M008-T004-ACCEPTANCE")
assert_equal(stored, snapshot, "Le store doit restituer le snapshot compact.")
assert_true(tuple(event.event_type for event in result.events) == ("ConversationContextCompacted",), "Le compactage doit publier un evenement.")

print("Test d'acceptation T-004 snapshot contexte M-008: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m008_context_snapshot_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-004 snapshot contexte M-008: OK"
