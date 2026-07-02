$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import inspect
import sys

sys.path.insert(0, sys.argv[1])

from app.contracts.research_outcomes import VerifiedResearchOutcome
from app.conversation.application import reuse_verified_result
from app.conversation.application.answer_conversation_turn import PublicResearchAnswerResult
from app.conversation.application.attach_verified_answer import (
    AttachVerifiedAnswerToTurnCommand,
    AttachVerifiedAnswerToTurnHandler,
    InMemoryVerifiedAnswerAttachmentStore,
)
from app.conversation.application.resolve_followup_question import ResolvedQuestion
from app.conversation.application.reuse_verified_result import (
    HistoricalAssertionRef,
    VerifiedResultReusePolicy,
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


def citation_payload():
    return {
        "citation_id": "CIT-M008-T007-UNIT",
        "evidence_id": "EVS-M008-T007-UNIT",
        "source_locator": {
            "schema_version": "1.0",
            "canonical_version_id": "CVER-M008-T007-UNIT",
            "document_id": "DOC-M008-T007-UNIT",
            "page_pdf": 3,
            "item_id": "ITEM-M008-T007-UNIT",
            "bbox": (0.1, 0.2, 0.3, 0.4),
            "content_hash": "c" * 64,
        },
        "quoted_span_hash": "d" * 64,
    }


def citation_payload_with_bbox(bbox):
    payload = citation_payload()
    payload["source_locator"] = {
        **payload["source_locator"],
        "bbox": bbox,
    }
    return payload


def outcome_payload(question, answer_id="ANS-M008-T007-UNIT", support_status="SUPPORTED"):
    return {
        "schema_version": "1.0",
        "research_case_id": "RSC-M008-T007-UNIT",
        "question": question,
        "mandate": {"allowed_universe": ["documents canoniques OSTrading"]},
        "answer_id": answer_id,
        "support_status": support_status,
        "claim_refs": ["CLM-M008-T007-UNIT@1"],
        "unresolved_conflicts": [],
        "knowledge_gaps": [],
        "completed_at": "2026-07-01T14:12:00Z",
    }


def resolved_question(text="Question documentaire verifiee."):
    return ResolvedQuestion(
        conversation_id="CONV-M008-T007-UNIT",
        turn_id="TURN-M008-T007-UNIT",
        text=text,
        active_mandate={"allowed_universe": ("documents canoniques OSTrading",)},
        selected_document_ids=("DOC-M008-T007-UNIT",),
        verified_answer_refs=(),
        occurred_at="2026-07-01T14:10:00Z",
    )


def public_result(question="Question documentaire verifiee."):
    return PublicResearchAnswerResult(
        verified_research_outcome=VerifiedResearchOutcome.from_payload(outcome_payload(question)),
        verified_answer_ref="ANS-M008-T007-UNIT@1",
        answer_text="Reponse RA publique.",
        citations=(citation_payload(),),
        abstention_reason=None,
    )


policy = VerifiedResultReusePolicy()
decision = policy.plan(
    (
        HistoricalAssertionRef("Assertion sans version.", None),
        HistoricalAssertionRef("Assertion deja versionnee.", "ANS-M008-T007-UNIT@1"),
    )
)
assert_equal(tuple(decision.assertions_to_revalidate), ("Assertion sans version.",), "Seule l'assertion non versionnee doit etre revalidee.")
assert_equal(tuple(decision.reusable_answer_refs), ("ANS-M008-T007-UNIT@1",), "La version verifiee doit etre reutilisable sans RA.")

assert_raises(
    "verified_research_outcome invalide",
    lambda: PublicResearchAnswerResult(
        verified_research_outcome=object(),
        verified_answer_ref="ANS-M008-T007-UNIT@1",
        answer_text="Reponse RA publique.",
        citations=(citation_payload(),),
        abstention_reason=None,
    ),
)
assert_raises(
    "citations absentes",
    lambda: PublicResearchAnswerResult(
        verified_research_outcome=VerifiedResearchOutcome.from_payload(outcome_payload("Question documentaire verifiee.")),
        verified_answer_ref="ANS-M008-T007-UNIT@1",
        answer_text="Reponse RA publique.",
        citations=(),
        abstention_reason=None,
    ),
)
assert_raises(
    "citation invalide",
    lambda: PublicResearchAnswerResult(
        verified_research_outcome=VerifiedResearchOutcome.from_payload(outcome_payload("Question documentaire verifiee.")),
        verified_answer_ref="ANS-M008-T007-UNIT@1",
        answer_text="Reponse RA publique.",
        citations=(citation_payload_with_bbox((0.1, float("nan"), 0.3, 0.4)),),
        abstention_reason=None,
    ),
)
assert_raises(
    "citation invalide",
    lambda: PublicResearchAnswerResult(
        verified_research_outcome=VerifiedResearchOutcome.from_payload(outcome_payload("Question documentaire verifiee.")),
        verified_answer_ref="ANS-M008-T007-UNIT@1",
        answer_text="Reponse RA publique.",
        citations=(citation_payload_with_bbox((0.1, float("inf"), 0.3, 0.4)),),
        abstention_reason=None,
    ),
)

store = InMemoryVerifiedAnswerAttachmentStore(known_turn_ids=("TURN-M008-T007-UNIT",))
handler = AttachVerifiedAnswerToTurnHandler(attachment_store=store)
attached = handler.attach(
    AttachVerifiedAnswerToTurnCommand(
        conversation_id="CONV-M008-T007-UNIT",
        turn_id="TURN-M008-T007-UNIT",
        resolved_question=resolved_question(),
        answer_result=public_result(),
        occurred_at="2026-07-01T14:11:00Z",
    )
)
assert_equal(attached.status, "VERIFIED_RESULT_ATTACHED", "Le rattachement valide doit etre publie.")
assert_equal(store.attachment_for_turn("TURN-M008-T007-UNIT"), attached.attachment, "Le store doit conserver le rattachement.")

assert_raises(
    "turn conversation inconnu",
    lambda: AttachVerifiedAnswerToTurnHandler(
        attachment_store=InMemoryVerifiedAnswerAttachmentStore(known_turn_ids=("TURN-OTHER",))
    ).attach(
        AttachVerifiedAnswerToTurnCommand(
            conversation_id="CONV-M008-T007-UNIT",
            turn_id="TURN-M008-T007-UNIT",
            resolved_question=resolved_question(),
            answer_result=public_result(),
            occurred_at="2026-07-01T14:11:00Z",
        )
    ),
)
assert_raises(
    "verified_answer deja rattachee",
    lambda: store.save(attached.attachment),
)
assert_raises(
    "question reponse incoherente",
    lambda: handler.attach(
        AttachVerifiedAnswerToTurnCommand(
            conversation_id="CONV-M008-T007-UNIT",
            turn_id="TURN-M008-T007-UNIT",
            resolved_question=resolved_question("Question documentaire verifiee."),
            answer_result=public_result("Autre question RA."),
            occurred_at="2026-07-01T14:11:00Z",
        )
    ),
)

source = inspect.getsource(reuse_verified_result)
assert_false("app.research_answering.adapters" in source, "CV ne doit pas importer un adaptateur RA interne.")
assert_false("AnswerRepository" in source, "CV ne doit pas acceder au stockage RA.")
assert_false("InMemoryVerifiedAnswerAttachmentStore" in source, "ReuseVerifiedResultHandler doit dependre du port VerifiedAnswerAttachmentStore.")

print("Tests unitaires T-007 rattachement reponse verifiee M-008: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m008_verified_answer_attachment_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-007 rattachement reponse verifiee M-008: OK"
