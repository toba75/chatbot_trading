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
from app.research_answering.domain.research_case import (
    DeepResearchPlan,
    ResearchCaseStatus,
    ResearchMode,
)
from app.research_answering.domain.research_planning import (
    DeepResearchPlanningPolicy,
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


def assert_no_forbidden_storage_payload(value, path="payload"):
    forbidden_keys = {
        "qdrant_collection",
        "qdrant_point_id",
        "eg_registry_table",
        "sp_table",
        "prompt_override",
        "strategy_parameter",
        "market_price_override",
    }
    if isinstance(value, dict):
        for key, child in value.items():
            assert_false(key in forbidden_keys, f"Champ technique interdit dans {path}.{key}.")
            assert_no_forbidden_storage_payload(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            assert_no_forbidden_storage_payload(child, f"{path}[{index}]")


# Given une question autonome demande une synthèse multi-sources sur Kelly et volatility targeting avec un mandat explicite.
payload = {
    "resolved_question": (
        "Comment comparer Kelly et volatility targeting pour une synthèse multi-sources "
        "qui conserve preuves favorables, preuves défavorables, dépendances, limites et lacunes ?"
    ),
    "research_mandate": {
        "allowed_universe": (
            "Kelly",
            "volatility targeting",
            "portefeuille convexe documenté",
        ),
        "horizon": "connaissances documentaires stables",
        "data_requirements": (
            "methodes",
            "preuves favorables",
            "preuves defavorables",
            "dépendances",
            "limites",
            "zones non documentees",
        ),
        "exclusions": (
            "données de marché actuelles",
            "paramètre de stratégie inventé",
            "extension hors mandat utilisateur",
        ),
        "language": "fr",
        "detail_level": "synthese approfondie multi-sources",
    },
    "requested_mode": "DEEP_RESEARCH",
    "requested_by_context": "CV",
    "idempotency_key": "OPEN-DEEP-RESEARCH-M009-T003-ACCEPTANCE-0001",
    "occurred_at": "2026-07-02T09:00:00Z",
}

repository = InMemoryResearchCaseRepository.empty()
handler = OpenResearchCaseHandler(
    research_case_repository=repository,
    planning_policy=DeepResearchPlanningPolicy.for_m009_deep_research(),
)

# When RA planifie la recherche approfondie.
result = handler.open_and_plan(OpenResearchCaseCommand.from_payload(payload))

# Then le ResearchCase passe à PLANNED avec des sous-questions et obligations couvrant les angles M-009.
assert_equal(result.status, "RESEARCH_CASE_PLANNED", "Le handler doit annoncer un cas planifié.")
research_case = repository.case_for_id(result.research_case_id)
assert_equal(research_case.status, ResearchCaseStatus.PLANNED, "Le cas approfondi doit être PLANNED.")
assert_equal(research_case.requested_mode, ResearchMode.DEEP_RESEARCH, "Le mode approfondi doit être explicite.")
assert_true(isinstance(research_case.research_plan, DeepResearchPlan), "Le plan doit être un DeepResearchPlan.")
assert_equal(
    research_case.research_plan.policy_version,
    "deep-research-planning-m009-v1",
    "La version de politique approfondie doit être explicite.",
)

obligation_names = tuple(
    obligation.name for obligation in research_case.research_plan.coverage_obligations
)
assert_equal(
    obligation_names,
    (
        "methodes",
        "preuves_favorables",
        "preuves_defavorables",
        "dependances",
        "limites",
        "zones_non_documentees",
    ),
    "Les obligations approfondies doivent être complètes et déterministes.",
)
assert_equal(len(obligation_names), len(set(obligation_names)), "Les obligations ne doivent pas être dupliquées.")

sub_questions = research_case.research_plan.sub_questions
assert_true(len(sub_questions) >= 4, "Le plan approfondi doit découper la recherche en sous-questions.")
covered_obligations = {
    obligation_name
    for sub_question in sub_questions
    for obligation_name in sub_question.coverage_obligation_names
}
assert_true(
    set(obligation_names).issubset(covered_obligations),
    "Chaque obligation de couverture doit être rattachée à une sous-question.",
)

mandate_text = repr(research_case.research_mandate.to_payload()).casefold()
for sub_question in sub_questions:
    assert_true(sub_question.text.endswith("?"), "Chaque sous-question doit rester une question autonome.")
    for mandate_term in sub_question.mandate_terms:
        assert_true(
            mandate_term.casefold() in mandate_text,
            f"Sous-question hors mandat: {mandate_term}",
        )

assert_equal(
    tuple(event.event_type for event in result.events),
    ("ResearchCaseOpened", "ResearchPlanCreated"),
    "L'ouverture et la planification approfondie doivent être traçables.",
)
case_payload = research_case.to_payload()
assert_no_forbidden_storage_payload(case_payload)
assert_false(
    "DOCUMENTARY_SIMPLE" in repr(case_payload),
    "La recherche approfondie ne doit pas revenir silencieusement au mode documentaire simple.",
)
assert_false(
    "collect" in research_case.status.value.casefold(),
    "Le cas ne doit pas commencer la collecte avant la planification.",
)

print("Test d'acceptation T-003 planification recherche approfondie M-009: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m009_deep_research_planning_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-003 planification recherche approfondie M-009: OK"
