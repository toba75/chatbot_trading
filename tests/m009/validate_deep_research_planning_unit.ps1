$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

sys.path.insert(0, sys.argv[1])

from app.research_answering.domain.research_case import (
    CoverageObligation,
    DeepResearchPlan,
    ResearchCase,
    ResearchMode,
    ResearchMandate,
    ResearchSubQuestion,
    ResolvedQuestion,
)
from app.research_answering.domain.research_planning import (
    DeepResearchPlanningPolicy,
    LocalDeterministicResearchPlanningPolicy,
)


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def assert_raises(expected_fragment, action):
    try:
        action()
    except (AttributeError, TypeError, ValueError) as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


def mandate_payload():
    return {
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
    }


def deep_case():
    return ResearchCase.open(
        research_case_id="RSC-M009-T003-DEEP",
        resolved_question=ResolvedQuestion(
            "Comment comparer Kelly et volatility targeting sans effacer limites et contradictions ?"
        ),
        research_mandate=ResearchMandate.from_payload(mandate_payload()),
        requested_mode=ResearchMode.DEEP_RESEARCH,
        requested_by_context="CV",
        occurred_at="2026-07-02T09:15:00Z",
    )


def documentary_case():
    return ResearchCase.open(
        research_case_id="RSC-M009-T003-DOC",
        resolved_question=ResolvedQuestion("Quels documents supportent la couverture de queue ?"),
        research_mandate=ResearchMandate.from_payload(mandate_payload()),
        requested_mode=ResearchMode.DOCUMENTARY_SIMPLE,
        requested_by_context="CV",
        occurred_at="2026-07-02T09:20:00Z",
    )


def valid_obligations():
    return (
        CoverageObligation(name="methodes", description="Comparer les méthodes déclarées dans le mandat."),
        CoverageObligation(name="preuves_favorables", description="Chercher les preuves favorables autorisées."),
        CoverageObligation(name="preuves_defavorables", description="Chercher les preuves défavorables autorisées."),
        CoverageObligation(name="dependances", description="Identifier dépendances et répétitions documentaires."),
        CoverageObligation(name="limites", description="Nommer les limites et conditions de portée."),
        CoverageObligation(name="zones_non_documentees", description="Nommer les lacunes et zones non documentées."),
    )


def valid_sub_questions():
    return (
        ResearchSubQuestion(
            sub_question_id="RSQ-METHODES",
            text="Quelles méthodes du mandat comparent Kelly et volatility targeting ?",
            coverage_obligation_names=("methodes", "dependances"),
            mandate_terms=("methodes", "Kelly", "volatility targeting"),
        ),
        ResearchSubQuestion(
            sub_question_id="RSQ-PREUVES-FAVORABLES",
            text="Quelles preuves favorables documentent Kelly et volatility targeting ?",
            coverage_obligation_names=("preuves_favorables",),
            mandate_terms=("preuves favorables", "Kelly", "volatility targeting"),
        ),
        ResearchSubQuestion(
            sub_question_id="RSQ-PREUVES-DEFAVORABLES",
            text="Quelles preuves défavorables documentent Kelly et volatility targeting ?",
            coverage_obligation_names=("preuves_defavorables",),
            mandate_terms=("preuves defavorables", "Kelly", "volatility targeting"),
        ),
        ResearchSubQuestion(
            sub_question_id="RSQ-LIMITES-LACUNES",
            text="Quelles limites et zones non documentées bornent la synthèse ?",
            coverage_obligation_names=("limites", "zones_non_documentees"),
            mandate_terms=("limites", "zones non documentees", "synthese approfondie multi-sources"),
        ),
    )


def custom_policy(*, obligations=None, sub_questions=None):
    return DeepResearchPlanningPolicy(
        policy_version="deep-research-planning-m009-v1",
        coverage_obligations=valid_obligations() if obligations is None else obligations,
        sub_questions=valid_sub_questions() if sub_questions is None else sub_questions,
    )


# ResearchMode expose le mode approfondi explicite sans fallback.
assert_equal(ResearchMode.from_value("DEEP_RESEARCH"), ResearchMode.DEEP_RESEARCH, "Le mode approfondi doit être accepté.")
assert_raises("research_mode inconnu", lambda: ResearchMode.from_value("RECHERCHE_APPROFONDIE"))

# La politique M-007 reste documentaire simple et refuse le mode approfondi.
assert_raises(
    "research_mode non supporte par politique",
    lambda: LocalDeterministicResearchPlanningPolicy.for_m007_documentary_simple().plan_for(deep_case()),
)

# La politique M-009 refuse le mode documentaire simple.
assert_raises(
    "research_mode approfondi requis",
    lambda: DeepResearchPlanningPolicy.for_m009_deep_research().plan_for(documentary_case()),
)

# Un plan approfondi valide est déterministe et couvre toutes les obligations obligatoires.
policy = DeepResearchPlanningPolicy.for_m009_deep_research()
first_plan = policy.plan_for(deep_case())
second_plan = policy.plan_for(deep_case())
assert_true(isinstance(first_plan, DeepResearchPlan), "Le plan M-009 doit être un DeepResearchPlan.")
assert_equal(first_plan.to_payload(), second_plan.to_payload(), "La politique approfondie doit être déterministe.")
assert_equal(
    tuple(obligation.name for obligation in first_plan.coverage_obligations),
    (
        "methodes",
        "preuves_favorables",
        "preuves_defavorables",
        "dependances",
        "limites",
        "zones_non_documentees",
    ),
    "L'ordre des obligations approfondies doit être stable.",
)

# Garde-fous du plan approfondi.
assert_raises(
    "research_sub_questions absentes",
    lambda: custom_policy(sub_questions=()).plan_for(deep_case()),
)
assert_raises(
    "coverage_obligation dupliquee",
    lambda: custom_policy(obligations=valid_obligations() + (valid_obligations()[0],)).plan_for(deep_case()),
)
assert_raises(
    "mandate_term hors mandat",
    lambda: custom_policy(
        sub_questions=(
            ResearchSubQuestion(
                sub_question_id="RSQ-HORS-MANDAT",
                text="Faut-il inclure les prix Bitcoin intraday ?",
                coverage_obligation_names=("methodes",),
                mandate_terms=("Bitcoin intraday",),
            ),
        )
    ).plan_for(deep_case()),
)
assert_raises(
    "coverage_obligation obligatoire absente: preuves_defavorables",
    lambda: custom_policy(
        obligations=tuple(
            obligation for obligation in valid_obligations() if obligation.name != "preuves_defavorables"
        )
    ).plan_for(deep_case()),
)
assert_raises(
    "coverage_obligation obligatoire absente: limites",
    lambda: custom_policy(
        obligations=tuple(obligation for obligation in valid_obligations() if obligation.name != "limites")
    ).plan_for(deep_case()),
)
assert_raises(
    "coverage_obligations non deterministes",
    lambda: custom_policy(obligations=tuple(reversed(valid_obligations()))).plan_for(deep_case()),
)

print("Tests unitaires T-003 planification recherche approfondie M-009: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m009_deep_research_planning_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-003 planification recherche approfondie M-009: OK"
