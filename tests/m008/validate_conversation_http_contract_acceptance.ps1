$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

sys.path.insert(0, sys.argv[1])

from app.contracts.research_outcomes import VerifiedResearchOutcome
from app.conversation.adapters.conversation_http import (
    ConversationHttpAdapter,
    HttpRequest,
)
from app.conversation.adapters.in_memory_conversation_repository import InMemoryConversationRepository
from app.conversation.adapters.in_memory_turn_repository import InMemoryTurnRepository
from app.conversation.application.answer_conversation_turn import PublicResearchAnswerResult
from app.conversation.application.attach_verified_answer import (
    AttachVerifiedAnswerToTurnCommand,
    AttachVerifiedAnswerToTurnHandler,
    InMemoryVerifiedAnswerAttachmentStore,
)
from app.conversation.application.resolve_followup_question import ResolvedQuestion


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_false(condition, message):
    if condition:
        raise AssertionError(message)


class SequenceIdFactory:
    def __init__(self, values):
        self.values = list(values)

    def next_id(self):
        if not self.values:
            raise AssertionError("Identifiant inattendu")
        return self.values.pop(0)


def citation_payload():
    return {
        "citation_id": "CIT-M008-T009-A",
        "evidence_id": "EVS-M008-T009-A",
        "source_locator": {
            "schema_version": "1.0",
            "canonical_version_id": "CVER-M008-T009-A",
            "document_id": "DOC-M008-T009-A",
            "page_pdf": 8,
            "item_id": "ITEM-M008-T009-A",
            "bbox": (0.1, 0.2, 0.3, 0.4),
            "content_hash": "a" * 64,
        },
        "quoted_span_hash": "b" * 64,
    }


def answer_result(question):
    return PublicResearchAnswerResult(
        verified_research_outcome=VerifiedResearchOutcome.from_payload(
            {
                "schema_version": "1.0",
                "research_case_id": "RSC-M008-T009-A",
                "question": question,
                "mandate": {"allowed_universe": ["documents canoniques OSTrading"]},
                "answer_id": "ANS-M008-T009-A",
                "support_status": "SUPPORTED",
                "claim_refs": ["CLM-M008-T009-A@1"],
                "unresolved_conflicts": [],
                "knowledge_gaps": [],
                "completed_at": "2026-07-01T16:03:00Z",
            }
        ),
        verified_answer_ref="ANS-M008-T009-A@1",
        answer_text="Reponse RA conservee hors cascade CV.",
        citations=(citation_payload(),),
        abstention_reason=None,
    )


conversation_repository = InMemoryConversationRepository.empty()
turn_repository = InMemoryTurnRepository.empty()
adapter = ConversationHttpAdapter(
    conversation_repository=conversation_repository,
    turn_repository=turn_repository,
    conversation_id_factory=SequenceIdFactory(("CONV-M008-T009-A",)),
    turn_id_factory=SequenceIdFactory(("TURN-M008-T009-A",)),
    retention_policy_version="conversation-retention-m008-v1",
)

# Given une conversation contient un tour rattache a une reponse verifiee.
created = adapter.handle(
    HttpRequest(
        method="POST",
        path="/v1/conversations",
        body={
            "title": "Conversation M-008",
            "default_mandate": {"allowed_universe": ["documents canoniques OSTrading"]},
            "presentation_preferences": {"language": "fr"},
            "occurred_at": "2026-07-01T16:00:00Z",
        },
    )
)
assert_equal(created.status_code, 201, "La conversation doit etre creee.")
message = adapter.handle(
    HttpRequest(
        method="POST",
        path="/v1/conversations/CONV-M008-T009-A/messages",
        body={
            "message": "Explique le resultat verifie.",
            "idempotency_key": "idem-m008-t009-a",
            "occurred_at": "2026-07-01T16:01:00Z",
        },
    )
)
assert_equal(message.status_code, 200, "Le message doit creer un tour.")
attachment_store = InMemoryVerifiedAnswerAttachmentStore(known_turn_ids=("TURN-M008-T009-A",))
question = ResolvedQuestion(
    conversation_id="CONV-M008-T009-A",
    turn_id="TURN-M008-T009-A",
    text="Explique le resultat verifie.",
    active_mandate={"allowed_universe": ("documents canoniques OSTrading",)},
    selected_document_ids=("DOC-M008-T009-A",),
    verified_answer_refs=(),
    occurred_at="2026-07-01T16:02:00Z",
)
attachment = AttachVerifiedAnswerToTurnHandler(attachment_store=attachment_store).attach(
    AttachVerifiedAnswerToTurnCommand(
        conversation_id="CONV-M008-T009-A",
        turn_id="TURN-M008-T009-A",
        resolved_question=question,
        answer_result=answer_result(question.text),
        occurred_at="2026-07-01T16:04:00Z",
    )
).attachment

# When l'utilisateur archive la conversation.
archived = adapter.handle(
    HttpRequest(
        method="DELETE",
        path="/v1/conversations/CONV-M008-T009-A",
        body={"occurred_at": "2026-07-01T16:05:00Z"},
    )
)

# Then la conversation passe en statut archive sans supprimer la reponse verifiee ni les preuves referencees.
assert_equal(archived.status_code, 200, "L'archive doit reussir.")
assert_equal(archived.body["status"], "ARCHIVED", "Le statut public doit etre ARCHIVED.")
assert_equal(attachment_store.attachment_for_turn("TURN-M008-T009-A"), attachment, "Le rattachement RA doit survivre a l'archive CV.")
turns = adapter.handle(
    HttpRequest(
        method="GET",
        path="/v1/conversations/CONV-M008-T009-A/turns",
        body={},
    )
)
assert_equal(turns.status_code, 200, "Les tours doivent rester consultables apres archive.")
assert_equal(turns.body["turns"][0]["turn_id"], "TURN-M008-T009-A", "Le tour doit rester lisible.")
assert_false("ra_storage" in repr(archived.body).lower(), "Aucun stockage RA ne doit etre expose.")
assert_false("answer_text" in repr(archived.body), "L'archive ne doit pas publier la reponse RA.")

print("Test d'acceptation T-009 contrat HTTP conversation M-008: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m008_conversation_http_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-009 contrat HTTP conversation M-008: OK"
