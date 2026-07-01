$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import ast
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, sys.argv[1])

from app.contracts.research_outcomes import VerifiedResearchOutcome
from app.research_answering.adapters.answer_http import AnswerHttpAdapter, HttpRequest
from app.research_answering.application.answer_question import (
    AnswerQuestionResult,
    DocumentaryAnswerWorkflow,
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


def assert_raises(expected_type, expected_fragment, action):
    try:
        action()
    except expected_type as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    except Exception as exc:
        raise AssertionError(f"Type d'erreur inattendu: {type(exc).__name__}: {exc}") from exc
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_type.__name__}")


def mandate_payload():
    return {
        "allowed_universe": ("documents canoniques OSTrading",),
        "horizon": "connaissances documentaires stables",
        "data_requirements": ("preuves candidates KA", "claims vérifiés EG"),
        "exclusions": ("données de marché actuelles non autorisées",),
        "language": "fr",
        "detail_level": "synthèse vérifiée",
    }


def valid_body(**overrides):
    body = {
        "resolved_question": "Quelle réponse documentaire publier ?",
        "research_mandate": mandate_payload(),
        "requested_mode": "DOCUMENTARY_SIMPLE",
        "idempotency_key": "answer-http-m007-t009-unit",
        "occurred_at": "2026-06-30T18:10:00Z",
    }
    body.update(overrides)
    return body


def citation_payload():
    return {
        "citation_id": "CIT-M007-T009-UNIT-0001",
        "evidence_id": "EVS-M007-T009-UNIT-0001",
        "source_locator": {
            "schema_version": "1.0",
            "canonical_version_id": "CVER-M007-T009-UNIT",
            "document_id": "DOC-M007-T009-UNIT",
            "page_pdf": 1,
            "item_id": "item-m007-t009-unit",
            "bbox": (0.1, 0.2, 0.8, 0.9),
            "content_hash": "3" * 64,
        },
        "quoted_span_hash": "4" * 64,
    }


def outcome_payload(**overrides):
    payload = {
        "schema_version": "1.0",
        "research_case_id": "RSC-M007-T009-UNIT",
        "question": "Quelle réponse documentaire publier ?",
        "mandate": mandate_payload(),
        "answer_id": "ANS-M007-T009-UNIT",
        "support_status": "SUPPORTED",
        "claim_refs": ("CLM-M007-T009-UNIT@1",),
        "unresolved_conflicts": (),
        "knowledge_gaps": (),
        "completed_at": "2026-06-30T18:11:00Z",
    }
    payload.update(overrides)
    return payload


def answer_result(**overrides):
    result = {
        "verified_research_outcome": VerifiedResearchOutcome.from_payload(outcome_payload()),
        "answer_text": "Réponse documentaire publique supportée.",
        "citations": (citation_payload(),),
        "abstention_reason": None,
    }
    result.update(overrides)
    return AnswerQuestionResult(**result)


class RecordingAnswerQuestionHandler:
    def __init__(self, result=None, error=None):
        self.result = result if result is not None else answer_result()
        self.error = error
        self.commands = []

    def answer(self, command):
        self.commands.append(command)
        if self.error is not None:
            raise self.error
        return self.result


class WorkflowOpenHandler:
    def __init__(self):
        self.commands = []

    def open_and_plan(self, command):
        self.commands.append(command)
        return SimpleNamespace(research_case_id="RSC-M007-T009-WORKFLOW")


class WorkflowCollectHandler:
    def __init__(self):
        self.collect_commands = []
        self.seal_commands = []

    def collect(self, command):
        self.collect_commands.append(command)
        return SimpleNamespace(evidence_set=SimpleNamespace(evidence_set_id="EVS-M007-T009-WORKFLOW"))

    def seal(self, command):
        self.seal_commands.append(command)
        return SimpleNamespace(evidence_set=SimpleNamespace(evidence_set_id=command.evidence_set_id))


class WorkflowDraftHandler:
    def __init__(self):
        self.commands = []

    def draft(self, command):
        self.commands.append(command)
        return SimpleNamespace(answer=SimpleNamespace(answer_id="ANS-M007-T009-WORKFLOW"))


class WorkflowExtractorHandler:
    def __init__(self):
        self.commands = []

    def extract(self, command):
        self.commands.append(command)
        return SimpleNamespace(answer=SimpleNamespace(answer_id=command.answer_id))


class WorkflowCitation:
    def to_payload(self):
        return citation_payload()


class WorkflowEvaluateHandler:
    def __init__(self):
        self.commands = []

    def evaluate(self, command):
        self.commands.append(command)
        return SimpleNamespace(
            verified_answer_version=SimpleNamespace(
                answer_text="Réponse documentaire orchestrée.",
                citations=(WorkflowCitation(),),
            ),
            verified_research_outcome=VerifiedResearchOutcome.from_payload(
                outcome_payload(
                    research_case_id=command.research_case_id,
                    answer_id=command.answer_id,
                )
            ),
        )


def post(adapter, body=None, *, method="POST", path="/v1/answer", context="API"):
    return adapter.handle(
        HttpRequest(
            method=method,
            path=path,
            body=valid_body() if body is None else body,
            authenticated_context=context,
        )
    )


handler = RecordingAnswerQuestionHandler()
adapter = AnswerHttpAdapter(answer_question_handler=handler)
accepted = post(adapter)
assert_equal(accepted.status_code, 200, "Une requête valide doit être publiée.")
assert_equal(len(handler.commands), 1, "L'adaptateur doit déléguer exactement une commande RA.")
assert_equal(handler.commands[0].idempotency_key, "answer-http-m007-t009-unit", "La clé d'idempotence doit être obligatoire.")

workflow_open = WorkflowOpenHandler()
workflow_collect = WorkflowCollectHandler()
workflow_draft = WorkflowDraftHandler()
workflow_extract = WorkflowExtractorHandler()
workflow_evaluate = WorkflowEvaluateHandler()
workflow = DocumentaryAnswerWorkflow(
    open_research_case_handler=workflow_open,
    collect_evidence_handler=workflow_collect,
    draft_answer_handler=workflow_draft,
    extract_answer_assertions_handler=workflow_extract,
    evaluate_answer_support_handler=workflow_evaluate,
    coverage_obligations=("preuves_documentaires",),
    evidence_result_limit=3,
    support_policy_version="answer-support-m007-v1",
    citation_policy_version="citation-integrity-m007-v1",
    freshness_policy_version="answer-freshness-m007-v1",
)
workflow_result = workflow.answer(handler.commands[0])
assert_equal(workflow_result.to_public_payload()["support_status"], "SUPPORTED", "Le workflow concret doit retourner un résultat public RA.")
assert_equal(workflow_collect.collect_commands[0].result_limit, 3, "Le workflow doit transmettre la limite de collecte.")
assert_equal(workflow_collect.seal_commands[0].evidence_set_id, "EVS-M007-T009-WORKFLOW", "Le workflow doit sceller le jeu collecté.")
assert_equal(workflow_draft.commands[0].evidence_set_id, "EVS-M007-T009-WORKFLOW", "Le workflow doit rédiger depuis le jeu scellé.")
assert_equal(workflow_extract.commands[0].answer_id, "ANS-M007-T009-WORKFLOW", "Le workflow doit extraire les assertions de l'Answer rédigé.")
assert_equal(workflow_evaluate.commands[0].support_policy_version, "answer-support-m007-v1", "Le workflow doit transmettre la politique de support.")

wrong_method = post(adapter, method="GET")
assert_equal(wrong_method.status_code, 404, "Une méthode invalide ne doit pas appeler RA.")
assert_equal(wrong_method.body, {"error_code": "ENDPOINT_NOT_FOUND", "path": "/v1/answer"}, "L'erreur d'endpoint doit être stable.")

wrong_path = post(adapter, path="/v1/research/deep")
assert_equal(wrong_path.status_code, 404, "L'adaptateur T-009 ne doit pas router la recherche approfondie.")
assert_equal(wrong_path.body["error_code"], "ENDPOINT_NOT_FOUND", "Le mauvais chemin doit être explicite.")

missing_question = valid_body()
del missing_question["resolved_question"]
question_response = post(adapter, missing_question)
assert_equal(question_response.status_code, 400, "La question absente doit être refusée.")
assert_equal(question_response.body, {"error_code": "HTTP_REQUEST_INVALID", "field": "resolved_question"}, "La question absente doit nommer le champ.")

missing_mandate = valid_body()
del missing_mandate["research_mandate"]
mandate_response = post(adapter, missing_mandate)
assert_equal(mandate_response.status_code, 422, "Le mandat absent doit produire RESEARCH_MANDATE_REQUIRED.")
assert_equal(mandate_response.body, {"error_code": "RESEARCH_MANDATE_REQUIRED", "field": "research_mandate"}, "L'erreur mandat doit rester stable.")

missing_idempotency = valid_body()
del missing_idempotency["idempotency_key"]
idempotency_response = post(adapter, missing_idempotency)
assert_equal(idempotency_response.status_code, 400, "La clé d'idempotence absente doit être refusée.")
assert_equal(idempotency_response.body, {"error_code": "HTTP_REQUEST_INVALID", "field": "idempotency_key"}, "L'erreur idempotence doit être stable.")

for forbidden_field in (
    "qdrant_collection",
    "qdrant_point_id",
    "eg_registry_table",
    "sp_table",
    "prompt_override",
    "support_status_override",
    "draft_text_as_final",
):
    forbidden = post(adapter, valid_body(**{forbidden_field: "interdit"}))
    assert_equal(forbidden.status_code, 400, f"{forbidden_field} doit être refusé.")
    assert_equal(forbidden.body, {"error_code": "HTTP_REQUEST_INVALID", "field": "body"}, f"{forbidden_field} ne doit pas atteindre RA.")

forbidden_mandate = valid_body()
forbidden_mandate["research_mandate"] = mandate_payload()
forbidden_mandate["research_mandate"]["conversation_history"] = ("message précédent",)
forbidden_mandate_response = post(adapter, forbidden_mandate)
assert_equal(forbidden_mandate_response.status_code, 400, "Un champ interdit du mandat ne doit pas être requalifié en mandat absent.")
assert_equal(
    forbidden_mandate_response.body,
    {"error_code": "HTTP_REQUEST_INVALID", "field": "body"},
    "Un mandat invalide doit conserver un diagnostic de requête générique.",
)

unauthorized_handler = RecordingAnswerQuestionHandler()
unauthorized = post(AnswerHttpAdapter(answer_question_handler=unauthorized_handler), context="KA")
assert_equal(unauthorized.status_code, 403, "Un contexte non autorisé doit être refusé.")
assert_equal(unauthorized.body, {"error_code": "ANSWER_CONTEXT_FORBIDDEN"}, "L'erreur de contexte doit être publique.")
assert_equal(len(unauthorized_handler.commands), 0, "Un contexte interdit ne doit pas appeler RA.")

unsupported = post(
    AnswerHttpAdapter(answer_question_handler=RecordingAnswerQuestionHandler(error=ValueError("ANSWER_ASSERTION_UNSUPPORTED"))),
)
assert_equal(unsupported.status_code, 422, "ANSWER_ASSERTION_UNSUPPORTED doit retourner 422.")
assert_equal(unsupported.body, {"error_code": "ANSWER_ASSERTION_UNSUPPORTED"}, "L'erreur d'assertion doit rester stable.")

current_data = post(
    AnswerHttpAdapter(answer_question_handler=RecordingAnswerQuestionHandler(error=ValueError("CURRENT_DATA_REQUIRED"))),
)
assert_equal(current_data.status_code, 422, "CURRENT_DATA_REQUIRED doit retourner 422.")
assert_equal(current_data.body, {"error_code": "CURRENT_DATA_REQUIRED"}, "L'erreur de données actuelles doit rester stable.")

not_sealed = post(
    AnswerHttpAdapter(answer_question_handler=RecordingAnswerQuestionHandler(error=ValueError("EVIDENCE_SET_NOT_SEALED"))),
)
assert_equal(not_sealed.status_code, 409, "EVIDENCE_SET_NOT_SEALED doit retourner 409.")
assert_equal(not_sealed.body, {"error_code": "EVIDENCE_SET_NOT_SEALED"}, "L'erreur de scellement doit rester stable.")

for error_code, expected_status in (
    ("RESEARCH_MANDATE_REQUIRED", 422),
    ("EVIDENCE_SET_NOT_SEALED", 409),
    ("ANSWER_ASSERTION_UNSUPPORTED", 422),
    ("ANSWER_CITATION_UNRESOLVABLE", 422),
    ("ANSWER_CONFLICT_UNRESOLVED", 409),
    ("INSUFFICIENT_EVIDENCE", 422),
    ("CURRENT_DATA_REQUIRED", 422),
    ("ANSWER_PUBLICATION_FORBIDDEN", 409),
    ("RA_POLICY_MISSING", 422),
):
    response = post(
        AnswerHttpAdapter(
            answer_question_handler=RecordingAnswerQuestionHandler(
                error=ValueError(f"{error_code}: détail public"),
            )
        ),
    )
    assert_equal(response.status_code, expected_status, f"{error_code} doit mapper vers le statut HTTP attendu.")
    assert_equal(response.body, {"error_code": error_code}, f"{error_code} doit rester un code public exact.")

unknown_with_marker = post(
    AnswerHttpAdapter(
        answer_question_handler=RecordingAnswerQuestionHandler(
            error=ValueError("wrapper ANSWER_CITATION_UNRESOLVABLE"),
        )
    ),
)
assert_equal(unknown_with_marker.status_code, 400, "Un marqueur en sous-chaîne ne doit pas être mappé.")
assert_equal(
    unknown_with_marker.body,
    {"error_code": "HTTP_REQUEST_INVALID", "field": "body"},
    "Une erreur inconnue doit rester une erreur de requête générique.",
)

public_body = accepted.body
for forbidden_response_field in (
    "prompt",
    "draft",
    "repository",
    "qdrant_collection",
    "eg_registry_table",
    "sp_table",
    "evidence_set_snapshot",
    "assertion_decisions",
    "policy_version",
):
    assert_false(
        forbidden_response_field in repr(public_body).lower(),
        f"La réponse HTTP ne doit pas exposer {forbidden_response_field}.",
    )

assert_raises(
    ValueError,
    "citations absentes",
    lambda: AnswerQuestionResult(
        verified_research_outcome=VerifiedResearchOutcome.from_payload(outcome_payload()),
        answer_text="Réponse sans citation.",
        citations=(),
        abstention_reason=None,
    ),
)

leaky_citation = citation_payload()
leaky_citation["source_locator"] = dict(leaky_citation["source_locator"])
leaky_citation["source_locator"]["qdrant_collection"] = "collection-interne"
assert_raises(
    ValueError,
    "source_locator champ interdit",
    lambda: AnswerQuestionResult(
        verified_research_outcome=VerifiedResearchOutcome.from_payload(outcome_payload()),
        answer_text="Réponse avec locator interne.",
        citations=(leaky_citation,),
        abstention_reason=None,
    ),
)

abstention_outcome = VerifiedResearchOutcome.from_payload(
    outcome_payload(
        support_status="REQUIRES_CURRENT_DATA",
        knowledge_gaps=(
            {
                "topic": "données actuelles autorisées",
                "impact": "La question requiert des données actuelles non autorisées.",
            },
        ),
    )
)
abstention = AnswerQuestionResult(
    verified_research_outcome=abstention_outcome,
    answer_text="Abstention: données actuelles requises.",
    citations=(),
    abstention_reason="CURRENT_DATA_REQUIRED",
)
assert_equal(abstention.to_public_payload()["abstention_reason"], "CURRENT_DATA_REQUIRED", "L'abstention doit être explicite.")

adapter_path = Path(sys.argv[1]) / "app" / "research_answering" / "adapters" / "answer_http.py"
tree = ast.parse(adapter_path.read_text(encoding="utf-8"))
for node in ast.walk(tree):
    if isinstance(node, ast.Call):
        called_name = getattr(node.func, "id", None)
        called_attr = getattr(node.func, "attr", None)
        if called_name == "print" or called_attr in {"debug", "info", "warning", "error", "exception"}:
            raise AssertionError("L'adaptateur HTTP réponse ne doit pas écrire de log de payload.")
    if isinstance(node, ast.Import):
        imported_modules = {alias.name for alias in node.names}
    elif isinstance(node, ast.ImportFrom) and node.module is not None:
        imported_modules = {node.module}
    else:
        imported_modules = set()
    forbidden_imports = {
        "app.knowledge_access",
        "app.evidence_governance",
        "app.source_processing",
        "qdrant_client",
        "logging",
        "fastapi",
        "starlette",
        "flask",
        "django",
    }
    for imported_module in imported_modules:
        for forbidden_import in forbidden_imports:
            if imported_module == forbidden_import or imported_module.startswith(forbidden_import + "."):
                raise AssertionError(f"Import interdit dans answer_http.py: {imported_module}")

source = adapter_path.read_text(encoding="utf-8")
assert_true("AnswerQuestion" in source, "L'adaptateur doit déléguer à la commande applicative RA.")
for forbidden_storage_marker in ("qdrant_collection", "qdrant_point_id", "eg_registry_table", "sp_table"):
    assert_true(forbidden_storage_marker in source, f"Le champ interdit {forbidden_storage_marker} doit être refusé explicitement.")
for forbidden_direct_call in ("SearchKnowledge", "VerifiedClaimCatalog", "ResearchCaseRepository(", "AnswerRepository("):
    assert_false(forbidden_direct_call in source, f"L'adaptateur ne doit pas appeler directement {forbidden_direct_call}.")

print("Tests unitaires T-009 contrat HTTP réponse documentaire M-007: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m007_answer_http_contract_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-009 contrat HTTP réponse documentaire M-007: OK"
