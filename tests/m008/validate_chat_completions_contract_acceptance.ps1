$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

sys.path.insert(0, sys.argv[1])

from app.contracts.research_outcomes import VerifiedResearchOutcome
from app.conversation.adapters.chat_completions_http import (
    ChatCompletionsHttpAdapter,
    HttpRequest,
)
from app.conversation.adapters.conversation_http import (
    ConversationHttpAdapter,
    HttpRequest as ConversationHttpRequest,
)
from app.conversation.adapters.in_memory_conversation_repository import InMemoryConversationRepository
from app.conversation.adapters.in_memory_turn_repository import InMemoryTurnRepository
from app.conversation.application.answer_conversation_turn import PublicResearchAnswerResult


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
        "citation_id": "CIT-M008-T010-A",
        "evidence_id": "EVS-M008-T010-A",
        "source_locator": {
            "schema_version": "1.0",
            "canonical_version_id": "CVER-M008-T010-A",
            "document_id": "DOC-M008-T010-A",
            "page_pdf": 10,
            "item_id": "ITEM-M008-T010-A",
            "bbox": (0.1, 0.2, 0.3, 0.4),
            "content_hash": "a" * 64,
        },
        "quoted_span_hash": "b" * 64,
    }


def outcome(question):
    return VerifiedResearchOutcome.from_payload(
        {
            "schema_version": "1.0",
            "research_case_id": "RSC-M008-T010-A",
            "question": question,
            "mandate": {"allowed_universe": ["documents canoniques OSTrading"]},
            "answer_id": "ANS-M008-T010-A",
            "support_status": "SUPPORTED",
            "claim_refs": ["CLM-M008-T010-A@1"],
            "unresolved_conflicts": [],
            "knowledge_gaps": [],
            "completed_at": "2026-07-01T17:03:00Z",
        }
    )


class ScriptedAnswerProvider:
    def __init__(self):
        self.requests = []

    def answer(self, request):
        self.requests.append(request)
        return PublicResearchAnswerResult(
            verified_research_outcome=outcome(request.user_message),
            verified_answer_ref="ANS-M008-T010-A@1",
            answer_text="Le volatility targeting reduit certains drawdowns selon la preuve citee.",
            citations=(citation_payload(),),
            abstention_reason=None,
        )


conversation_repository = InMemoryConversationRepository.empty()
turn_repository = InMemoryTurnRepository.empty()
conversation_http = ConversationHttpAdapter(
    conversation_repository=conversation_repository,
    turn_repository=turn_repository,
    conversation_id_factory=SequenceIdFactory(("CONV-M008-T010-A",)),
    turn_id_factory=SequenceIdFactory(("TURN-M008-T010-UNUSED",)),
    retention_policy_version="conversation-retention-m008-v1",
)
created = conversation_http.handle(
    ConversationHttpRequest(
        method="POST",
        path="/v1/conversations",
        body={
            "title": "Conversation compatible chat",
            "default_mandate": {"allowed_universe": ["documents canoniques OSTrading"]},
            "presentation_preferences": {"language": "fr"},
            "occurred_at": "2026-07-01T17:00:00Z",
        },
    )
)
assert_equal(created.status_code, 201, "La conversation explicite doit exister avant chat completions.")

answer_provider = ScriptedAnswerProvider()
chat_http = ChatCompletionsHttpAdapter(
    conversation_repository=conversation_repository,
    turn_repository=turn_repository,
    turn_id_factory=SequenceIdFactory(("TURN-M008-T010-A",)),
    answer_provider=answer_provider,
)

# Given un client appelle /v1/chat/completions avec un conversation_id et un message utilisateur.
request = HttpRequest(
    method="POST",
    path="/v1/chat/completions",
    body={
        "model": "ostrading-chat-m008",
        "conversation_id": "CONV-M008-T010-A",
        "messages": (
            {
                "role": "user",
                "content": "Explique pourquoi le volatility targeting reduit certains drawdowns.",
            },
        ),
        "idempotency_key": "idem-m008-t010-a",
        "occurred_at": "2026-07-01T17:01:00Z",
    },
)

# When CV traite la requete compatible.
response = chat_http.handle(request)

# Then un tour CV est cree et la reponse expose texte, statut documentaire et citations dans les champs produit.
assert_equal(response.status_code, 200, "La completion compatible doit reussir.")
assert_equal(response.body["object"], "chat.completion", "L'objet compatible doit etre publie.")
assert_equal(response.body["choices"][0]["message"]["role"], "assistant", "La reponse doit rester un message assistant.")
assert_equal(
    response.body["choices"][0]["message"]["content"],
    "Le volatility targeting reduit certains drawdowns selon la preuve citee.",
    "Le texte assistant doit venir du DTO public RA.",
)
product = response.body["ost_product"]
assert_equal(product["conversation_id"], "CONV-M008-T010-A", "L'extension produit doit conserver la conversation.")
assert_equal(product["turn_id"], "TURN-M008-T010-A", "L'extension produit doit conserver le tour CV.")
assert_equal(product["support_status"], "SUPPORTED", "Le statut documentaire RA doit etre expose.")
assert_equal(product["verified_answer_ref"], "ANS-M008-T010-A@1", "La version de reponse verifiee doit etre exposee.")
assert_equal(product["citations"][0]["source_locator"]["document_id"], "DOC-M008-T010-A", "La citation ouvrable doit etre exposee.")
assert_equal(turn_repository.turn_for_id("TURN-M008-T010-A").message, request.body["messages"][0]["content"], "Le message utilisateur doit etre trace dans un tour CV.")
assert_equal(len(answer_provider.requests), 1, "CV doit appeler le port de reponse une seule fois.")
provider_request = answer_provider.requests[0]
assert_equal(provider_request.conversation_id, "CONV-M008-T010-A", "La requete applicative doit porter la conversation.")
assert_equal(provider_request.turn_id, "TURN-M008-T010-A", "La requete applicative doit porter le tour.")
assert_equal(provider_request.requested_by_context, "CV", "La requete applicative doit rester cote CV.")
assert_equal(tuple(provider_request.research_mandate["allowed_universe"]), ("documents canoniques OSTrading",), "Le mandat conversationnel doit etre repris explicitement.")
serialized = repr(response.body).lower()
assert_false("ra_storage" in serialized, "Le stockage RA ne doit pas etre expose.")
assert_false("qdrant" in serialized, "Le stockage KA ne doit pas etre expose.")
assert_false("prompt_override" in serialized, "Aucun prompt override ne doit sortir.")
assert_false("vllm" in serialized, "Le protocole LLM local ne doit pas etre expose.")

print("Test d'acceptation T-010 contrat chat completions M-008: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m008_chat_completions_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-010 contrat chat completions M-008: OK"
