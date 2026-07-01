$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

sys.path.insert(0, sys.argv[1])

from app.research_answering.adapters.in_memory_research_case_repository import (
    InMemoryResearchCaseRepository,
)
from app.research_answering.application.open_research_case import (
    OpenResearchCaseCommand,
    OpenResearchCaseHandler,
)
from app.research_answering.domain.research_case import ResearchCaseStatus
from app.research_answering.domain.research_planning import (
    LocalDeterministicResearchPlanningPolicy,
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


def assert_no_forbidden_conversation_payload(value, path="payload"):
    forbidden_keys = {
        "conversation_history",
        "conversation_turns",
        "raw_conversation",
        "history_as_evidence",
    }
    if isinstance(value, dict):
        for key, child in value.items():
            assert_false(key in forbidden_keys, f"Historique conversationnel interdit dans {path}.{key}.")
            assert_no_forbidden_conversation_payload(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            assert_no_forbidden_conversation_payload(child, f"{path}[{index}]")


# Given une question autonome et un mandat documentaire explicite.
payload = {
    "resolved_question": (
        "Quels éléments documentaires supportent une réponse sur la couverture de queue "
        "dans un portefeuille convexe ?"
    ),
    "research_mandate": {
        "allowed_universe": ("documents canoniques OSTrading",),
        "horizon": "connaissances documentaires stables",
        "data_requirements": ("preuves candidates KA", "claims vérifiés EG"),
        "exclusions": (
            "historique conversationnel comme preuve",
            "données de marché actuelles non autorisées",
        ),
        "language": "fr",
        "detail_level": "synthèse vérifiée",
    },
    "requested_mode": "DOCUMENTARY_SIMPLE",
    "requested_by_context": "CV",
    "idempotency_key": "OPEN-RESEARCH-CASE-M007-T003-ACCEPTANCE-0001",
    "occurred_at": "2026-06-30T08:00:00Z",
}

repository = InMemoryResearchCaseRepository.empty()
handler = OpenResearchCaseHandler(
    research_case_repository=repository,
    planning_policy=LocalDeterministicResearchPlanningPolicy.for_m007_documentary_simple(),
)

# When RA ouvre puis planifie le cas de recherche.
result = handler.open_and_plan(OpenResearchCaseCommand.from_payload(payload))

# Then le cas passe a PLANNED avec des obligations de couverture nommées et sans utiliser l'historique conversationnel comme preuve.
assert_equal(result.status, "RESEARCH_CASE_PLANNED", "Le handler doit annoncer un cas planifié.")
assert_true(result.research_case_id.startswith("RSC-"), "Le ResearchCaseId doit être un identifiant RA.")
assert_equal(
    tuple(event.event_type for event in result.events),
    ("ResearchCaseOpened", "ResearchPlanCreated"),
    "L'ouverture et la planification doivent être traçables.",
)

research_case = repository.case_for_id(result.research_case_id)
assert_equal(research_case.status, ResearchCaseStatus.PLANNED, "Le cas doit être PLANNED.")
assert_equal(
    research_case.resolved_question.text,
    payload["resolved_question"],
    "La question autonome doit être figée.",
)
assert_equal(
    tuple(research_case.research_mandate.data_requirements),
    payload["research_mandate"]["data_requirements"],
    "Le mandat explicite doit être figé.",
)
assert_true(research_case.research_plan is not None, "Le plan RA doit être publié dans le cas.")
assert_equal(
    research_case.research_plan.policy_version,
    "research-planning-m007-documentary-simple-v1",
    "La politique de planification M-007 doit être explicite.",
)

obligation_names = tuple(
    obligation.name for obligation in research_case.research_plan.coverage_obligations
)
assert_true(len(obligation_names) >= 3, "Le plan doit nommer des obligations de couverture.")
assert_equal(len(obligation_names), len(set(obligation_names)), "Les obligations ne doivent pas être dupliquées.")
assert_true(
    {"question_autonome", "mandat_documentaire", "preuves_documentaires"}.issubset(set(obligation_names)),
    "Le plan doit couvrir question, mandat et preuves documentaires.",
)

case_payload = research_case.to_payload()
assert_no_forbidden_conversation_payload(case_payload)
assert_false(
    "qdrant" in repr(case_payload).lower(),
    "Le cas RA ne doit pas exposer d'accès KA technique direct.",
)
assert_false(
    "eg_registry" in repr(case_payload).lower(),
    "Le cas RA ne doit pas exposer le registre EG interne.",
)

print("Test d'acceptation T-003 ResearchCase mandat explicite M-007: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m007_research_case_mandate_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-003 ResearchCase mandat explicite M-007: OK"
