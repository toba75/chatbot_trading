$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

sys.path.insert(0, sys.argv[1])

from app.contracts.research_outcomes import VerifiedResearchOutcome
from app.conversation.application.answer_conversation_turn import PublicResearchAnswerResult
from app.conversation.application.present_conversation_answer import (
    PresentConversationAnswerCommand,
    PresentConversationAnswerHandler,
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


def citation_payload():
    return {
        "citation_id": "CIT-M008-T008-A",
        "evidence_id": "EVS-M008-T008-A",
        "source_locator": {
            "schema_version": "1.0",
            "canonical_version_id": "CVER-M008-T008-A",
            "document_id": "DOC-M008-T008-A",
            "page_pdf": 5,
            "item_id": "ITEM-M008-T008-A",
            "bbox": (0.1, 0.2, 0.3, 0.4),
            "content_hash": "e" * 64,
        },
        "quoted_span_hash": "f" * 64,
    }


# Given un tour assistant reference une reponse RA PARTIALLY_SUPPORTED avec une citation et une lacune.
answer_result = PublicResearchAnswerResult(
    verified_research_outcome=VerifiedResearchOutcome.from_payload(
        {
            "schema_version": "1.0",
            "research_case_id": "RSC-M008-T008-A",
            "question": "Comparer volatility targeting et Kelly.",
            "mandate": {"allowed_universe": ["documents canoniques OSTrading"]},
            "answer_id": "ANS-M008-T008-A",
            "support_status": "PARTIALLY_SUPPORTED",
            "claim_refs": ["CLM-M008-T008-A@1"],
            "unresolved_conflicts": [],
            "knowledge_gaps": [{"topic": "couts de transaction recents", "impact": "precision limitee"}],
            "completed_at": "2026-07-01T15:00:00Z",
        }
    ),
    verified_answer_ref="ANS-M008-T008-A@1",
    answer_text="Reponse partiellement supportee avec une limite explicite.",
    citations=(citation_payload(),),
    abstention_reason=None,
)
handler = PresentConversationAnswerHandler()

# When la reponse produit du tour est construite.
result = handler.present(
    PresentConversationAnswerCommand(
        conversation_id="CONV-M008-T008-ACCEPTANCE",
        turn_id="TURN-M008-T008-ACCEPTANCE",
        answer_result=answer_result,
        occurred_at="2026-07-01T15:01:00Z",
    )
)

# Then le statut, la citation ouvrable et la lacune sont visibles sans publier de prompt ni de stockage interne.
presentation = result.presentation
payload = presentation.to_payload()
assert_equal(result.status, "CONVERSATION_PUBLIC_RESPONSE_PRESENTED", "Le statut applicatif doit annoncer la presentation.")
assert_equal(payload["support_status"], "PARTIALLY_SUPPORTED", "Le statut documentaire doit etre visible.")
assert_equal(payload["answer_text"], "Reponse partiellement supportee avec une limite explicite.", "Le texte public RA doit etre conserve.")
assert_equal(payload["citations"][0]["source_locator"]["document_id"], "DOC-M008-T008-A", "La citation ouvrable doit etre exposee.")
assert_equal(payload["knowledge_gaps"][0]["topic"], "couts de transaction recents", "La lacune RA doit rester visible.")
assert_false("prompt" in repr(payload), "Aucun prompt ne doit etre publie.")
assert_false("qdrant" in repr(payload).lower(), "Aucun stockage interne ne doit etre publie.")
assert_false(hasattr(answer_result.verified_research_outcome, "citations"), "Les citations ne doivent pas provenir de VerifiedResearchOutcome.")
assert_equal(tuple(event.event_type for event in result.events), ("ConversationPublicResponsePresented",), "L'evenement de presentation doit etre publie.")

print("Test d'acceptation T-008 presentation citations statuts M-008: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m008_answer_presentation_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-008 presentation citations statuts M-008: OK"
