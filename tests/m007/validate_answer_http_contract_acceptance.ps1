$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

sys.path.insert(0, sys.argv[1])

from app.contracts.research_outcomes import VerifiedResearchOutcome
from app.research_answering.adapters.answer_http import AnswerHttpAdapter, HttpRequest
from app.research_answering.application.answer_question import AnswerQuestionResult


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
        "allowed_universe": ("documents canoniques OSTrading",),
        "horizon": "connaissances documentaires stables",
        "data_requirements": ("preuves candidates KA", "claims vérifiés EG"),
        "exclusions": ("données de marché actuelles non autorisées",),
        "language": "fr",
        "detail_level": "synthèse vérifiée",
    }


def request_body(idempotency_key):
    return {
        "resolved_question": "Quelle réponse documentaire publier ?",
        "research_mandate": mandate_payload(),
        "requested_mode": "DOCUMENTARY_SIMPLE",
        "idempotency_key": idempotency_key,
        "occurred_at": "2026-06-30T18:00:00Z",
    }


def citation_payload(status):
    status_id = status.replace("_", "-")
    return {
        "citation_id": f"CIT-M007-T009-{status_id}",
        "evidence_id": f"EVS-M007-T009-{status_id}",
        "source_locator": {
            "schema_version": "1.0",
            "canonical_version_id": f"CVER-M007-T009-{status_id}",
            "document_id": f"DOC-M007-T009-{status_id}",
            "page_pdf": 1,
            "item_id": f"item-m007-t009-{status_id.lower()}",
            "bbox": (0.1, 0.2, 0.8, 0.9),
            "content_hash": "1" * 64,
        },
        "quoted_span_hash": "2" * 64,
    }


def outcome_payload(status):
    status_id = status.replace("_", "-")
    payload = {
        "schema_version": "1.0",
        "research_case_id": f"RSC-M007-T009-{status_id}",
        "question": "Quelle réponse documentaire publier ?",
        "mandate": mandate_payload(),
        "answer_id": f"ANS-M007-T009-{status_id}",
        "support_status": status,
        "claim_refs": (f"CLM-M007-T009-{status_id}@1",),
        "unresolved_conflicts": (),
        "knowledge_gaps": (),
        "completed_at": "2026-06-30T18:01:00Z",
    }
    if status == "CONFLICTING_EVIDENCE":
        payload["unresolved_conflicts"] = (
            {
                "summary": "Claims vérifiés opposés sur une portée comparable.",
                "claim_refs": (
                    f"CLM-M007-T009-{status_id}@1",
                    "CLM-M007-T009-CONFLICT-TARGET@1",
                ),
                "blocking": True,
            },
        )
    if status == "INSUFFICIENT_EVIDENCE":
        payload["knowledge_gaps"] = (
            {
                "topic": "preuve documentaire indépendante",
                "impact": "Obligation documentaire non satisfaite.",
            },
        )
    if status == "REQUIRES_CURRENT_DATA":
        payload["claim_refs"] = ()
        payload["knowledge_gaps"] = (
            {
                "topic": "données actuelles autorisées",
                "impact": "La question requiert des données actuelles non autorisées.",
            },
        )
    return payload


def answer_result_for(status):
    citations = () if status == "REQUIRES_CURRENT_DATA" else (citation_payload(status),)
    abstention_reason = "CURRENT_DATA_REQUIRED" if status == "REQUIRES_CURRENT_DATA" else None
    return AnswerQuestionResult(
        verified_research_outcome=VerifiedResearchOutcome.from_payload(outcome_payload(status)),
        answer_text=f"Réponse documentaire publique {status}.",
        citations=citations,
        abstention_reason=abstention_reason,
    )


class ScriptedAnswerQuestionHandler:
    def __init__(self, status):
        self.status = status
        self.commands = []

    def answer(self, command):
        self.commands.append(command)
        return answer_result_for(self.status)


# Given une requête POST /v1/answer contient une question autonome, un mandat et une clé d'idempotence.
for support_status in (
    "SUPPORTED",
    "PARTIALLY_SUPPORTED",
    "CONFLICTING_EVIDENCE",
    "INSUFFICIENT_EVIDENCE",
    "REQUIRES_CURRENT_DATA",
):
    handler = ScriptedAnswerQuestionHandler(support_status)
    adapter = AnswerHttpAdapter(answer_question_handler=handler)

    # When RA produit une réponse vérifiée, partielle, conflictuelle, insuffisante ou abstinente.
    response = adapter.handle(
        HttpRequest(
            method="POST",
            path="/v1/answer",
            body=request_body(f"answer-http-m007-t009-{support_status.lower()}"),
            authenticated_context="API",
        )
    )

    # Then la réponse publique expose le statut documentaire, les citations ouvrables, les lacunes et la trace.
    assert_equal(response.status_code, 200, f"{support_status} doit être publié par POST /v1/answer.")
    assert_equal(
        set(response.body.keys()),
        {
            "schema_version",
            "research_case_id",
            "answer_id",
            "support_status",
            "answer_text",
            "citations",
            "claim_refs",
            "unresolved_conflicts",
            "knowledge_gaps",
            "abstention_reason",
            "completed_at",
        },
        "Le corps public doit rester le contrat RA M-007.",
    )
    assert_equal(response.body["support_status"], support_status, "Le statut documentaire doit être conservé.")
    assert_true(response.body["research_case_id"].startswith("RSC-"), "La trace doit nommer le ResearchCase.")
    assert_true(response.body["answer_id"].startswith("ANS-"), "La trace doit nommer l'Answer publié.")
    assert_true(response.body["completed_at"].endswith("Z"), "La trace doit conserver l'horodatage UTC.")
    if support_status == "REQUIRES_CURRENT_DATA":
        assert_equal(response.body["abstention_reason"], "CURRENT_DATA_REQUIRED", "L'abstention doit être publique.")
        assert_equal(response.body["citations"], (), "Une abstention données actuelles ne doit pas inventer de citation.")
    else:
        assert_true(len(response.body["citations"]) > 0, "Une réponse documentaire doit exposer ses citations.")
        assert_true(
            response.body["citations"][0]["source_locator"]["document_id"].startswith("DOC-"),
            "La citation doit rester ouvrable par SourceLocator.",
        )

    command = handler.commands[-1]
    assert_equal(command.resolved_question.text, "Quelle réponse documentaire publier ?", "La question doit être déléguée à RA.")
    assert_equal(command.requested_by_context, "API", "Le contexte authentifié doit être transmis sans champ public dédié.")
    assert_equal(command.requested_mode.value, "DOCUMENTARY_SIMPLE", "Le mode demandé ne doit pas être implicite.")

    rendered_body = repr(response.body).lower()
    for forbidden in (
        "prompt",
        "draft_text_as_final",
        "qdrant",
        "eg_registry_table",
        "sp_table",
        "repository",
        "evidence_set_snapshot",
        "assertion_decisions",
        "policy_version",
    ):
        assert_false(forbidden in rendered_body, f"Détail interne interdit dans la réponse publique: {forbidden}.")

print("Test d'acceptation T-009 contrat HTTP réponse documentaire M-007: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m007_answer_http_contract_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-009 contrat HTTP réponse documentaire M-007: OK"
