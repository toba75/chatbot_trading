$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

sys.path.insert(0, sys.argv[1])

from app.contracts.research_outcomes import VerifiedResearchOutcome
from app.conversation.application.answer_conversation_turn import PublicResearchAnswerResult
from app.conversation.application.attach_verified_answer import InMemoryVerifiedAnswerAttachmentStore
from app.conversation.application.resolve_followup_question import ResolvedQuestion
from app.conversation.application.reuse_verified_result import (
    HistoricalAssertionRef,
    ReuseVerifiedResultCommand,
    ReuseVerifiedResultHandler,
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
        "citation_id": "CIT-M008-T007-A",
        "evidence_id": "EVS-M008-T007-A",
        "source_locator": {
            "schema_version": "1.0",
            "canonical_version_id": "CVER-M008-T007-A",
            "document_id": "DOC-M008-T007-A",
            "page_pdf": 7,
            "item_id": "ITEM-M008-T007-A",
            "bbox": (0.1, 0.2, 0.3, 0.4),
            "content_hash": "a" * 64,
        },
        "quoted_span_hash": "b" * 64,
    }


def outcome(question):
    return VerifiedResearchOutcome.from_payload(
        {
            "schema_version": "1.0",
            "research_case_id": "RSC-M008-T007-A",
            "question": question,
            "mandate": {"allowed_universe": ["documents canoniques OSTrading"]},
            "answer_id": "ANS-M008-T007-A",
            "support_status": "SUPPORTED",
            "claim_refs": ["CLM-M008-T007-A@1"],
            "unresolved_conflicts": [],
            "knowledge_gaps": [],
            "completed_at": "2026-07-01T14:02:00Z",
        }
    )


class ScriptedResearchFacade:
    def __init__(self, result):
        self.result = result
        self.requests = []

    def answer(self, request):
        self.requests.append(request)
        return self.result


resolved_question = ResolvedQuestion(
    conversation_id="CONV-M008-T007-ACCEPTANCE",
    turn_id="TURN-M008-T007-ACCEPTANCE",
    text="Verifier a nouveau si le volatility targeting reduit certains drawdowns.",
    active_mandate={"allowed_universe": ("documents canoniques OSTrading",)},
    selected_document_ids=("DOC-M008-T007-A",),
    verified_answer_refs=(),
    occurred_at="2026-07-01T14:00:00Z",
)
public_result = PublicResearchAnswerResult(
    verified_research_outcome=outcome(resolved_question.text),
    verified_answer_ref="ANS-M008-T007-A@1",
    answer_text="Reponse RA publique supportee par citation.",
    citations=(citation_payload(),),
    abstention_reason=None,
)
research_facade = ScriptedResearchFacade(public_result)
store = InMemoryVerifiedAnswerAttachmentStore(known_turn_ids=("TURN-M008-T007-ACCEPTANCE",))
handler = ReuseVerifiedResultHandler(research_facade=research_facade, attachment_store=store)

# Given une reponse precedente contient une assertion sans VerifiedAnswerVersion.
command = ReuseVerifiedResultCommand(
    conversation_id="CONV-M008-T007-ACCEPTANCE",
    turn_id="TURN-M008-T007-ACCEPTANCE",
    resolved_question=resolved_question,
    historical_assertions=(
        HistoricalAssertionRef(
            assertion_text="Le volatility targeting reduit certains drawdowns.",
            verified_answer_ref=None,
        ),
    ),
    research_mandate={"allowed_universe": ("documents canoniques OSTrading",)},
    occurred_at="2026-07-01T14:01:00Z",
)

# When l'utilisateur reutilise cette assertion dans un nouveau tour documentaire.
result = handler.reuse_or_revalidate(command)

# Then CV appelle ResearchFacade pour verifier a nouveau l'assertion avant de rattacher le resultat RA.
assert_equal(len(research_facade.requests), 1, "Une assertion non versionnee doit declencher RA.")
request = research_facade.requests[0]
assert_equal(tuple(request.historical_assertions), ("Le volatility targeting reduit certains drawdowns.",), "La demande RA doit porter l'assertion a revalider.")
assert_equal(request.requested_by_context, "CV", "La demande RA doit etre correlee a CV.")
assert_equal(result.status, "VERIFIED_RESULT_ATTACHED", "Le resultat RA doit etre rattache au tour.")
assert_equal(result.attachment.verified_answer_ref, "ANS-M008-T007-A@1", "La version verifiee doit etre conservee.")
assert_equal(result.attachment.support_status, "SUPPORTED", "Le statut documentaire RA doit etre conserve.")
assert_equal(result.attachment.answer_id, "ANS-M008-T007-A", "L'identifiant RA doit etre reference.")
assert_equal(store.attachment_for_turn("TURN-M008-T007-ACCEPTANCE"), result.attachment, "Le rattachement doit etre persiste.")
assert_false(hasattr(result.attachment.verified_research_outcome, "answer_text"), "VerifiedResearchOutcome ne doit pas porter answer_text.")
assert_equal(tuple(event.event_type for event in result.events), ("HistoricalAssertionRevalidationRequested", "VerifiedAnswerAttachedToTurn"), "Les evenements CV doivent tracer revalidation puis rattachement.")

print("Test d'acceptation T-007 revalidation historique M-008: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m008_verified_result_reuse_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-007 revalidation historique M-008: OK"
