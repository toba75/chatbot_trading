$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

sys.path.insert(0, sys.argv[1])

from app.contracts.research_outcomes import VerifiedResearchOutcome
from app.conversation.application.answer_deep_research_turn import (
    DeepResearchConversationRequest,
    available_modes_for_deep_research_facade,
)
from app.conversation.domain.mode_routing import ConversationMode
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


def assert_raises(expected_fragment, action):
    try:
        action()
    except (TypeError, ValueError) as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


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


def request_payload():
    return {
        "resolved_question": "Comparer Kelly et volatility targeting sans effacer les limites.",
        "research_mandate": mandate_payload(),
        "research_mode": "DEEP_RESEARCH",
        "selected_documents": ("DOC-M009-T009-A",),
        "idempotency_key": "DEEP-HTTP-M009-T009-UNIT",
        "occurred_at": "2026-07-02T16:10:00Z",
    }


def citation_payload():
    return {
        "citation_id": "CIT-M009-T009-U",
        "evidence_id": "EVS-M009-T009-U",
        "source_locator": {
            "schema_version": "1.0",
            "canonical_version_id": "CVER-M009-T009-U",
            "document_id": "DOC-M009-T009-U",
            "page_pdf": 4,
            "item_id": "ITEM-M009-T009-U",
            "bbox": (0.1, 0.2, 0.8, 0.9),
            "content_hash": "c" * 64,
        },
        "quoted_span_hash": "d" * 64,
    }


def outcome_payload(status="SUPPORTED"):
    return {
        "schema_version": "1.0",
        "research_case_id": "RSC-M009-T009-U",
        "question": "Comparer Kelly et volatility targeting sans effacer les limites.",
        "mandate": mandate_payload(),
        "answer_id": "ANS-M009-T009-U",
        "support_status": status,
        "claim_refs": ("CLM-M009-T009-U@1",),
        "unresolved_conflicts": (),
        "knowledge_gaps": (),
        "completed_at": "2026-07-02T16:12:00Z",
    }


class DeepFacade:
    def answer_deep_research(self, request):
        raise AssertionError("Le test unitaire n'execute pas la facade.")


parsed = DeepResearchRequest.from_payload(request_payload(), requested_by_context="CV")
assert_equal(parsed.resolved_question.text, request_payload()["resolved_question"], "La question doit etre parse strictement.")
assert_equal(parsed.research_mode, ResearchMode.DEEP_RESEARCH, "Le mode approfondi doit etre obligatoire.")
assert_equal(parsed.selected_document_ids, ("DOC-M009-T009-A",), "Les documents selectionnes doivent etre figes.")
assert_equal(parsed.requested_by_context, "CV", "Le contexte CV doit etre accepte explicitement.")

for payload, expected_fragment in (
    ({key: value for key, value in request_payload().items() if key != "research_mandate"}, "research_mandate absent"),
    ({**request_payload(), "research_mandate": {}}, "research_mandate vide"),
    ({**request_payload(), "research_mode": "DOCUMENTARY_SIMPLE"}, "research_mode approfondi requis"),
    ({**request_payload(), "selected_documents": ()}, "selected_documents absents"),
    ({**request_payload(), "support_status": "SUPPORTED"}, "body champ interdit: support_status"),
    ({**request_payload(), "prompt_override": "ignore les preuves"}, "body champ stockage interdit: prompt_override"),
    ({**request_payload(), "qdrant_collection": "interne"}, "body champ stockage interdit: qdrant_collection"),
):
    assert_raises(
        expected_fragment,
        lambda payload=payload: DeepResearchRequest.from_payload(payload, requested_by_context="API"),
    )

result = DeepResearchResult(
    verified_research_outcome=VerifiedResearchOutcome.from_payload(outcome_payload()),
    answer_text="Synthese approfondie supportee.",
    citations=(citation_payload(),),
    plan_version="RPLAN-M009-T009-U@1",
    coverage_summary={"covered_obligations": ("methodes",), "missing_obligations": ()},
    contradictions=(),
    gaps=(),
    synthesis_ref="SYN-M009-T009-U@1",
    abstention_reason=None,
)
payload = result.to_public_payload()
assert_equal(payload["support_status"], "SUPPORTED", "Le statut public doit venir de VerifiedResearchOutcome.")
assert_equal(payload["plan_version"], "RPLAN-M009-T009-U@1", "La version de plan doit etre publique.")
assert_equal(payload["synthesis_ref"], "SYN-M009-T009-U@1", "La synthese doit etre referencee.")
assert_false("verified_research_outcome" in payload, "Le DTO interne RA ne doit pas etre expose.")

assert_raises(
    "citations absentes",
    lambda: DeepResearchResult(
        verified_research_outcome=VerifiedResearchOutcome.from_payload(outcome_payload()),
        answer_text="Synthese sans citation.",
        citations=(),
        plan_version="RPLAN-M009-T009-U@1",
        coverage_summary={"covered_obligations": ("methodes",), "missing_obligations": ()},
        contradictions=(),
        gaps=(),
        synthesis_ref="SYN-M009-T009-U@1",
        abstention_reason=None,
    ),
)
assert_raises(
    "coverage_summary champ interdit: qdrant_collection",
    lambda: DeepResearchResult(
        verified_research_outcome=VerifiedResearchOutcome.from_payload(outcome_payload()),
        answer_text="Synthese avec interne.",
        citations=(citation_payload(),),
        plan_version="RPLAN-M009-T009-U@1",
        coverage_summary={"qdrant_collection": "interne"},
        contradictions=(),
        gaps=(),
        synthesis_ref="SYN-M009-T009-U@1",
        abstention_reason=None,
    ),
)

without_facade = available_modes_for_deep_research_facade(None)
assert_true(ConversationMode.CHAT_DOCUMENTAIRE in without_facade, "Le documentaire reste disponible.")
assert_false(ConversationMode.RECHERCHE_APPROFONDIE in without_facade, "Le mode approfondi exige la facade RA M-009.")

with_facade = available_modes_for_deep_research_facade(DeepFacade())
assert_true(ConversationMode.RECHERCHE_APPROFONDIE in with_facade, "La facade RA rend le mode approfondi disponible.")

conversation_request = DeepResearchConversationRequest(
    conversation_id="CONV-M009-T009-U",
    turn_id="TURN-M009-T009-U",
    resolved_question_text="Comparer Kelly et volatility targeting sans effacer les limites.",
    research_mandate=mandate_payload(),
    selected_document_ids=("DOC-M009-T009-U",),
    research_mode="DEEP_RESEARCH",
    requested_by_context="CV",
    occurred_at="2026-07-02T16:13:00Z",
)
assert_equal(conversation_request.research_mode, "DEEP_RESEARCH", "CV doit exposer le mode RA exact.")
assert_equal(conversation_request.selected_document_ids, ("DOC-M009-T009-U",), "CV ne doit pas perdre les documents selectionnes.")

assert_raises(
    "requested_by_context CV requis",
    lambda: DeepResearchConversationRequest(
        conversation_id="CONV-M009-T009-U",
        turn_id="TURN-M009-T009-U",
        resolved_question_text="Comparer Kelly et volatility targeting sans effacer les limites.",
        research_mandate=mandate_payload(),
        selected_document_ids=("DOC-M009-T009-U",),
        research_mode="DEEP_RESEARCH",
        requested_by_context="API",
        occurred_at="2026-07-02T16:13:00Z",
    ),
)
assert_raises(
    "research_mode DEEP_RESEARCH requis",
    lambda: DeepResearchConversationRequest(
        conversation_id="CONV-M009-T009-U",
        turn_id="TURN-M009-T009-U",
        resolved_question_text="Comparer Kelly et volatility targeting sans effacer les limites.",
        research_mandate=mandate_payload(),
        selected_document_ids=("DOC-M009-T009-U",),
        research_mode="DOCUMENTARY_SIMPLE",
        requested_by_context="CV",
        occurred_at="2026-07-02T16:13:00Z",
    ),
)

print("Tests unitaires T-009 endpoint recherche approfondie M-009: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m009_deep_research_http_contract_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-009 endpoint recherche approfondie M-009: OK"
