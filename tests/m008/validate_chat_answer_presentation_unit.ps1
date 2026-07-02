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
    PublicAnswerPresentationDto,
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


def citation_payload(citation_id="CIT-M008-T008-UNIT"):
    return {
        "citation_id": citation_id,
        "evidence_id": "EVS-M008-T008-UNIT",
        "source_locator": {
            "schema_version": "1.0",
            "canonical_version_id": "CVER-M008-T008-UNIT",
            "document_id": "DOC-M008-T008-UNIT",
            "page_pdf": 4,
            "item_id": "ITEM-M008-T008-UNIT",
            "bbox": (0.1, 0.2, 0.3, 0.4),
            "content_hash": "a" * 64,
        },
        "quoted_span_hash": "b" * 64,
    }


def outcome_payload(status):
    payload = {
        "schema_version": "1.0",
        "research_case_id": "RSC-M008-T008-UNIT",
        "question": f"Question {status}.",
        "mandate": {"allowed_universe": ["documents canoniques OSTrading"]},
        "answer_id": f"ANS-M008-T008-{status.replace('_', '-')}",
        "support_status": status,
        "claim_refs": [f"CLM-M008-T008-{status.replace('_', '-')}@1"],
        "unresolved_conflicts": [],
        "knowledge_gaps": [],
        "completed_at": "2026-07-01T15:10:00Z",
    }
    if status == "INSUFFICIENT_EVIDENCE":
        payload["knowledge_gaps"] = [{"topic": "donnees manquantes", "impact": "preuve insuffisante"}]
    if status == "REQUIRES_CURRENT_DATA":
        payload["knowledge_gaps"] = [{"topic": "donnees actuelles", "impact": "verification impossible localement"}]
    if status == "CONFLICTING_EVIDENCE":
        payload["unresolved_conflicts"] = [{"summary": "sources divergentes", "claim_refs": [payload["claim_refs"][0]], "blocking": True}]
    return payload


def public_result(status):
    answer_id = f"ANS-M008-T008-{status.replace('_', '-')}"
    return PublicResearchAnswerResult(
        verified_research_outcome=VerifiedResearchOutcome.from_payload(outcome_payload(status)),
        verified_answer_ref=f"{answer_id}@1",
        answer_text=f"Reponse publique {status}.",
        citations=() if status == "REQUIRES_CURRENT_DATA" else (citation_payload(f"CIT-{status}"),),
        abstention_reason="CURRENT_DATA_REQUIRED" if status == "REQUIRES_CURRENT_DATA" else None,
    )


handler = PresentConversationAnswerHandler()
for status in (
    "SUPPORTED",
    "PARTIALLY_SUPPORTED",
    "INSUFFICIENT_EVIDENCE",
    "CONFLICTING_EVIDENCE",
    "REQUIRES_CURRENT_DATA",
):
    result = handler.present(
        PresentConversationAnswerCommand(
            conversation_id="CONV-M008-T008-UNIT",
            turn_id=f"TURN-M008-T008-{status.replace('_', '-')}",
            answer_result=public_result(status),
            occurred_at="2026-07-01T15:11:00Z",
        )
    )
    payload = result.presentation.to_payload()
    assert_equal(payload["support_status"], status, f"Le statut {status} doit etre conserve.")
    assert_equal(payload["answer_text"], f"Reponse publique {status}.", f"Le texte {status} doit etre conserve.")
    assert_false("prompt" in repr(payload), "Aucun prompt ne doit sortir.")
    assert_false("ra_storage" in repr(payload), "Aucun stockage RA ne doit sortir.")

bad_citation = citation_payload()
del bad_citation["source_locator"]["document_id"]
assert_raises(
    "source_locator document_id absent",
    lambda: handler.present(
        PresentConversationAnswerCommand(
            conversation_id="CONV-M008-T008-UNIT",
            turn_id="TURN-M008-T008-BAD-CIT",
            answer_result=PublicResearchAnswerResult(
                verified_research_outcome=VerifiedResearchOutcome.from_payload(outcome_payload("SUPPORTED")),
                verified_answer_ref="ANS-M008-T008-SUPPORTED@1",
                answer_text="Reponse publique SUPPORTED.",
                citations=(bad_citation,),
                abstention_reason=None,
            ),
            occurred_at="2026-07-01T15:11:00Z",
        )
    ),
)

class FakeOutcome:
    answer_id = "ANS-M008-T008-FAKE"
    question = "Question fake."
    support_status = "INSUFFICIENT_EVIDENCE"

    def to_payload(self):
        return {
            "answer_id": self.answer_id,
            "support_status": self.support_status,
            "knowledge_gaps": [],
            "unresolved_conflicts": [],
        }


assert_raises(
    "knowledge_gaps absentes",
    lambda: handler.present(
        PresentConversationAnswerCommand(
            conversation_id="CONV-M008-T008-UNIT",
            turn_id="TURN-M008-T008-NO-GAP",
            answer_result=PublicResearchAnswerResult(
                verified_research_outcome=FakeOutcome(),
                verified_answer_ref="ANS-M008-T008-FAKE@1",
                answer_text="Preuve insuffisante.",
                citations=(citation_payload("CIT-NO-GAP"),),
                abstention_reason=None,
            ),
            occurred_at="2026-07-01T15:11:00Z",
        )
    ),
)

class EnrichedOutcome(FakeOutcome):
    citations = ()


assert_raises(
    "verified_research_outcome enrichi interdit",
    lambda: PublicResearchAnswerResult(
        verified_research_outcome=EnrichedOutcome(),
        verified_answer_ref="ANS-M008-T008-FAKE@1",
        answer_text="Reponse.",
        citations=(citation_payload("CIT-ENRICHED"),),
        abstention_reason=None,
    ),
)

dto = PublicAnswerPresentationDto(
    conversation_id="CONV-M008-T008-UNIT",
    turn_id="TURN-M008-T008-DTO",
    answer_id="ANS-M008-T008-SUPPORTED",
    verified_answer_ref="ANS-M008-T008-SUPPORTED@1",
    answer_text="Reponse publique.",
    support_status="SUPPORTED",
    citations=(citation_payload("CIT-DTO"),),
    knowledge_gaps=(),
    unresolved_conflicts=(),
    abstention_reason=None,
    presented_at="2026-07-01T15:12:00Z",
)
assert_equal(dto.to_payload()["support_status"], "SUPPORTED", "Le DTO doit serialiser le statut.")

print("Tests unitaires T-008 presentation citations statuts M-008: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m008_answer_presentation_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-008 presentation citations statuts M-008: OK"
