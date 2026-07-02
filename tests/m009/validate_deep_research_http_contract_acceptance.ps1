$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

sys.path.insert(0, sys.argv[1])

from app.contracts.research_outcomes import VerifiedResearchOutcome
from app.conversation.application.answer_deep_research_turn import (
    AnswerDeepResearchConversationTurnCommand,
    AnswerDeepResearchConversationTurnHandler,
    DeepResearchConversationRequest,
)
from app.conversation.application.answer_conversation_turn import PublicResearchAnswerResult
from app.conversation.application.attach_verified_answer import InMemoryVerifiedAnswerAttachmentStore
from app.conversation.application.resolve_followup_question import ResolvedQuestion
from app.conversation.domain.mode_routing import ConversationMode
from app.research_answering.adapters.answer_http import AnswerHttpAdapter, HttpRequest
from app.research_answering.application.deep_research import (
    DeepResearchRequest,
    DeepResearchResult,
)
from app.research_answering.domain.research_case import ResearchMode


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def assert_false(condition, message):
    if condition:
        raise AssertionError(message)


def mandate_payload():
    return {
        "allowed_universe": (
            "Kelly",
            "volatility targeting",
            "documents canoniques OSTrading",
        ),
        "horizon": "connaissances documentaires stables",
        "data_requirements": (
            "methodes",
            "preuves favorables",
            "preuves defavorables",
            "dependances",
            "limites",
            "zones non documentees",
        ),
        "exclusions": (
            "donnees de marche actuelles",
            "parametre de strategie invente",
        ),
        "language": "fr",
        "detail_level": "synthese approfondie multi-sources",
    }


def deep_request_body():
    return {
        "resolved_question": "Comparer Kelly et volatility targeting sans effacer les limites.",
        "research_mandate": mandate_payload(),
        "research_mode": "DEEP_RESEARCH",
        "selected_documents": ("DOC-M009-T009-A", "DOC-M009-T009-B"),
        "idempotency_key": "DEEP-HTTP-M009-T009-ACCEPTANCE",
        "occurred_at": "2026-07-02T16:00:00Z",
    }


def citation_payload():
    return {
        "citation_id": "CIT-M009-T009-A",
        "evidence_id": "EVS-M009-T009-A",
        "source_locator": {
            "schema_version": "1.0",
            "canonical_version_id": "CVER-M009-T009-A",
            "document_id": "DOC-M009-T009-A",
            "page_pdf": 3,
            "item_id": "ITEM-M009-T009-A",
            "bbox": (0.1, 0.2, 0.8, 0.9),
            "content_hash": "a" * 64,
        },
        "quoted_span_hash": "b" * 64,
    }


def outcome_payload(question):
    return {
        "schema_version": "1.0",
        "research_case_id": "RSC-M009-T009-A",
        "question": question,
        "mandate": mandate_payload(),
        "answer_id": "ANS-M009-T009-A",
        "support_status": "PARTIALLY_SUPPORTED",
        "claim_refs": ("CLM-M009-T009-A@1", "CLM-M009-T009-B@1"),
        "unresolved_conflicts": (),
        "knowledge_gaps": (),
        "completed_at": "2026-07-02T16:04:00Z",
    }


def deep_result(question):
    return DeepResearchResult(
        verified_research_outcome=VerifiedResearchOutcome.from_payload(outcome_payload(question)),
        answer_text="Synthese approfondie qualifiee par limites et citations.",
        citations=(citation_payload(),),
        plan_version="RPLAN-M009-T009-A@1",
        coverage_summary={
            "covered_obligations": (
                "methodes",
                "preuves_favorables",
                "preuves_defavorables",
            ),
            "missing_obligations": ("zones_non_documentees",),
        },
        contradictions=(
            {
                "contradiction_id": "REL-M009-T009-A",
                "classification": "DIFFERENT_HORIZON",
                "public_reason": "Les horizons documentaires ne sont pas comparables.",
            },
        ),
        gaps=(
            {
                "gap_id": "GAP-M009-T009-A",
                "affected_obligation": "zones_non_documentees",
                "public_reason": "Une limite documentaire reste non couverte.",
            },
        ),
        synthesis_ref="SYN-M009-T009-A@1",
        abstention_reason=None,
    )


class RecordingAnswerQuestionHandler:
    def __init__(self):
        self.commands = []

    def answer(self, command):
        self.commands.append(command)
        raise AssertionError("POST /v1/research/deep ne doit pas appeler la reponse documentaire simple.")


class RecordingDeepResearchHandler:
    def __init__(self):
        self.commands = []

    def research(self, command):
        self.commands.append(command)
        return deep_result(command.resolved_question.text)


class RecordingDeepResearchConversationFacade:
    def __init__(self):
        self.requests = []

    def answer_deep_research(self, request):
        self.requests.append(request)
        return PublicResearchAnswerResult(
            verified_research_outcome=VerifiedResearchOutcome.from_payload(
                outcome_payload(request.resolved_question.text)
            ),
            verified_answer_ref="ANS-M009-T009-A@1",
            answer_text="Synthese approfondie rattachee au tour.",
            citations=(citation_payload(),),
            abstention_reason=None,
        )


# Given un mandat approfondi valide est envoye sur le endpoint RA public dedie.
simple_handler = RecordingAnswerQuestionHandler()
deep_handler = RecordingDeepResearchHandler()
adapter = AnswerHttpAdapter(
    answer_question_handler=simple_handler,
    deep_research_handler=deep_handler,
)

# When l'API POST /v1/research/deep est appelee explicitement.
response = adapter.handle(
    HttpRequest(
        method="POST",
        path="/v1/research/deep",
        body=deep_request_body(),
        authenticated_context="API",
    )
)

# Then RA expose le contrat M-009 sans stockage interne ni fallback documentaire simple.
assert_equal(response.status_code, 200, "Le endpoint approfondi doit publier une reponse RA.")
assert_equal(len(simple_handler.commands), 0, "La reponse documentaire simple ne doit pas etre appelee.")
assert_equal(len(deep_handler.commands), 1, "La facade RA approfondie doit recevoir la commande.")
command = deep_handler.commands[0]
assert_true(isinstance(command, DeepResearchRequest), "Le handler doit recevoir DeepResearchRequest.")
assert_equal(command.research_mode, ResearchMode.DEEP_RESEARCH, "Le mode RA approfondi doit etre explicite.")
assert_equal(command.requested_by_context, "API", "Le contexte authentifie doit rester transport.")
assert_equal(command.selected_document_ids, ("DOC-M009-T009-A", "DOC-M009-T009-B"), "Les documents selectionnes doivent etre transmis.")

assert_equal(
    set(response.body.keys()),
    {
        "schema_version",
        "research_case_id",
        "answer_id",
        "support_status",
        "answer_text",
        "plan_version",
        "coverage_summary",
        "citations",
        "contradictions",
        "gaps",
        "synthesis_ref",
        "claim_refs",
        "abstention_reason",
        "completed_at",
    },
    "Le corps public M-009 doit etre stable.",
)
assert_equal(response.body["support_status"], "PARTIALLY_SUPPORTED", "Le statut vient de RA, pas du client.")
assert_true(response.body["synthesis_ref"].startswith("SYN-"), "La synthese publiee doit etre referencee.")
rendered_body = repr(response.body).lower()
for forbidden in (
    "qdrant",
    "eg_registry_table",
    "sp_table",
    "ra_storage",
    "raw_projection_payload",
    "prompt_override",
    "support_status_override",
    "strategy_parameter",
    "market_price_override",
):
    assert_false(forbidden in rendered_body, f"Detail interne interdit dans la reponse publique: {forbidden}.")

for invalid_body, expected_status, expected_code in (
    ({**deep_request_body(), "support_status": "SUPPORTED"}, 400, "HTTP_REQUEST_INVALID"),
    ({key: value for key, value in deep_request_body().items() if key != "research_mandate"}, 422, "DEEP_RESEARCH_MANDATE_REQUIRED"),
    ({**deep_request_body(), "research_mode": "DOCUMENTARY_SIMPLE"}, 422, "DEEP_RESEARCH_MODE_REQUIRED"),
    ({**deep_request_body(), "qdrant_collection": "collection-interne"}, 400, "PUBLIC_STORAGE_FIELD_FORBIDDEN"),
):
    invalid_response = adapter.handle(
        HttpRequest(
            method="POST",
            path="/v1/research/deep",
            body=invalid_body,
            authenticated_context="CV",
        )
    )
    assert_equal(invalid_response.status_code, expected_status, f"Statut attendu pour {expected_code}.")
    assert_equal(invalid_response.body["error_code"], expected_code, f"Erreur publique attendue pour {expected_code}.")

# Given CV force le mode RECHERCHE_APPROFONDIE sur une question resolue.
resolved_question = ResolvedQuestion(
    conversation_id="CONV-M009-T009-A",
    turn_id="TURN-M009-T009-A",
    text="Comparer Kelly et volatility targeting sans effacer les limites.",
    active_mandate=mandate_payload(),
    selected_document_ids=("DOC-M009-T009-A", "DOC-M009-T009-B"),
    verified_answer_refs=(),
    occurred_at="2026-07-02T16:01:00Z",
)

# Then ce mode est indisponible tant que la facade RA M-009 n'est pas fournie.
without_facade = AnswerDeepResearchConversationTurnHandler(
    deep_research_facade=None,
    attachment_store=InMemoryVerifiedAnswerAttachmentStore(known_turn_ids=("TURN-M009-T009-A",)),
)
try:
    without_facade.answer(
        AnswerDeepResearchConversationTurnCommand(
            conversation_id="CONV-M009-T009-A",
            turn_id="TURN-M009-T009-A",
            resolved_question=resolved_question,
            requested_mode=ConversationMode.RECHERCHE_APPROFONDIE,
            research_mandate=mandate_payload(),
            occurred_at="2026-07-02T16:02:00Z",
        )
    )
except ValueError as exc:
    assert_true("mode conversation indisponible" in str(exc), "Le refus doit nommer le mode indisponible.")
else:
    raise AssertionError("RECHERCHE_APPROFONDIE ne doit pas etre disponible sans facade RA M-009.")

# When la facade RA M-009 existe, CV appelle RA et rattache le resultat verifie au tour.
deep_facade = RecordingDeepResearchConversationFacade()
store = InMemoryVerifiedAnswerAttachmentStore(known_turn_ids=("TURN-M009-T009-A",))
handler = AnswerDeepResearchConversationTurnHandler(
    deep_research_facade=deep_facade,
    attachment_store=store,
)
cv_result = handler.answer(
    AnswerDeepResearchConversationTurnCommand(
        conversation_id="CONV-M009-T009-A",
        turn_id="TURN-M009-T009-A",
        resolved_question=resolved_question,
        requested_mode=ConversationMode.RECHERCHE_APPROFONDIE,
        research_mandate=mandate_payload(),
        occurred_at="2026-07-02T16:02:00Z",
    )
)

assert_equal(cv_result.status, "DEEP_RESEARCH_RESULT_ATTACHED", "Le resultat approfondi doit etre rattache.")
assert_equal(cv_result.selection.mode, ConversationMode.RECHERCHE_APPROFONDIE, "Le mode CV doit etre conserve.")
assert_equal(len(deep_facade.requests), 1, "CV doit appeler la facade RA approfondie.")
facade_request = deep_facade.requests[0]
assert_true(isinstance(facade_request, DeepResearchConversationRequest), "CV doit transmettre une requete explicite a RA.")
assert_equal(facade_request.research_mode, "DEEP_RESEARCH", "CV doit traduire RECHERCHE_APPROFONDIE vers le mode RA.")
assert_equal(cv_result.attachment.verified_answer_ref, "ANS-M009-T009-A@1", "Le tour doit porter la reference verifiee.")
assert_equal(store.attachment_for_turn("TURN-M009-T009-A"), cv_result.attachment, "Le rattachement doit etre persiste.")
assert_equal(
    tuple(event.event_type for event in cv_result.events),
    ("ConversationModeSelected", "VerifiedAnswerAttachedToTurn"),
    "Les evenements doivent tracer selection puis rattachement.",
)

print("Test d'acceptation T-009 endpoint recherche approfondie M-009: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m009_deep_research_http_contract_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-009 endpoint recherche approfondie M-009: OK"
