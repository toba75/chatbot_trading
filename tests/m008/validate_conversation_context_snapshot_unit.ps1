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
from app.conversation.domain.context_snapshot import (
    ConversationContextCompactionPolicy,
    ConversationContextSnapshot,
)


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


def command_payload():
    return {
        "conversation_id": "CONV-M008-T004-UNIT",
        "active_mandate": {"allowed_universe": ("documents canoniques OSTrading",)},
        "user_preferences": {"language": "fr"},
        "selected_document_ids": ("DOC-M008-T004-UNIT",),
        "verified_answer_refs": ("ANS-M008-T004-UNIT@1",),
        "historical_assertions": ("Assertion historique sans version.",),
        "ambiguities": ("ce resultat",),
        "occurred_at": "2026-07-01T11:10:00Z",
    }


policy = ConversationContextCompactionPolicy()
snapshot = policy.compact(**command_payload())
assert_equal(snapshot.conversation_id, "CONV-M008-T004-UNIT", "La conversation doit etre portee.")
assert_equal(tuple(snapshot.historical_assertions_to_revalidate), ("Assertion historique sans version.",), "Une assertion sans version doit etre revalidee.")
assert_equal(tuple(snapshot.verified_answer_refs), ("ANS-M008-T004-UNIT@1",), "La version verifiee doit etre conservee.")
assert_equal(tuple(snapshot.selected_document_ids), ("DOC-M008-T004-UNIT",), "Le document selectionne doit etre conserve.")

payload = snapshot.to_payload()
assert_false("raw_turns" in repr(payload), "Les tours bruts ne doivent pas etre recopies.")
assert_false("prompt" in repr(payload), "Aucun prompt ne doit etre persiste.")
assert_false("answer_text" in repr(payload), "Le texte de reponse RA ne doit pas etre duplique.")

assert_raises("conversation_id invalide", lambda: policy.compact(**{**command_payload(), "conversation_id": "BAD"}))
assert_raises("active_mandate vide", lambda: policy.compact(**{**command_payload(), "active_mandate": {}}))
assert_raises("document_id invalide", lambda: policy.compact(**{**command_payload(), "selected_document_ids": ("BAD-DOC",)}))
assert_raises("verified_answer_ref invalide", lambda: policy.compact(**{**command_payload(), "verified_answer_refs": ("ANS-M008-T004-UNIT",)}))
assert_raises("historical_assertion vide", lambda: policy.compact(**{**command_payload(), "historical_assertions": ("",)}))
assert_raises("cle interdite: raw_turns", lambda: policy.compact(**{**command_payload(), "user_preferences": {"raw_turns": "texte"}}))
assert_raises("cle interdite: answer_text", lambda: policy.compact(**{**command_payload(), "active_mandate": {"answer_text": "texte RA"}}))

snapshot_with_only_versioned_refs = policy.compact(
    **{**command_payload(), "historical_assertions": ()}
)
assert_equal(tuple(snapshot_with_only_versioned_refs.historical_assertions_to_revalidate), (), "Une assertion deja versionnee ne doit pas etre revalidee.")

assert_raises(
    "cannot assign",
    lambda: setattr(snapshot, "conversation_id", "CONV-MUTATED"),
)

store = InMemoryConversationContextStore.empty()
handler = CompactConversationContextHandler(context_store=store)
result = handler.compact(CompactConversationContextCommand(**command_payload()))
assert_equal(result.status, "CONVERSATION_CONTEXT_COMPACTED", "Le handler doit exposer un statut public.")
assert_equal(store.snapshot_for_conversation("CONV-M008-T004-UNIT"), result.snapshot, "Le store doit conserver le snapshot.")
assert_raises("snapshot conversation inconnu", lambda: store.snapshot_for_conversation("CONV-M008-T004-UNKNOWN"))

assert_raises(
    "conversation_context_snapshot invalide",
    lambda: InMemoryConversationContextStore(snapshots=(object(),)),
)
assert_raises(
    "snapshot deja enregistre",
    lambda: store.save(
        ConversationContextSnapshot(
            conversation_id="CONV-M008-T004-UNIT",
            active_mandate={"allowed_universe": ("autre",)},
            user_preferences={},
            selected_document_ids=(),
            verified_answer_refs=(),
            historical_assertions_to_revalidate=(),
            ambiguities=(),
            created_at="2026-07-01T11:11:00Z",
        )
    ),
)

print("Tests unitaires T-004 snapshot contexte M-008: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m008_context_snapshot_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-004 snapshot contexte M-008: OK"
