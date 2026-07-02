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
    CoverageObligation,
    ResearchCase,
    ResearchCaseStatus,
    ResearchMandate,
    ResearchMode,
    ResearchPlan,
    ResolvedQuestion,
)
from app.research_answering.domain.research_planning import (
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
        "allowed_universe": ("documents canoniques OSTrading",),
        "horizon": "connaissances documentaires stables",
        "data_requirements": ("preuves candidates KA", "claims vérifiés EG"),
        "exclusions": ("historique conversationnel comme preuve",),
        "language": "fr",
        "detail_level": "synthèse vérifiée",
    }


def command_payload():
    return {
        "resolved_question": "Quels éléments documentaires supportent la couverture de queue ?",
        "research_mandate": mandate_payload(),
        "requested_mode": "DOCUMENTARY_SIMPLE",
        "requested_by_context": "CV",
        "idempotency_key": "OPEN-RESEARCH-CASE-M007-T003-UNIT-0001",
        "occurred_at": "2026-06-30T08:15:00Z",
    }


def opened_case():
    return ResearchCase.open(
        research_case_id="RSC-M007-T003-UNIT",
        resolved_question=ResolvedQuestion("Quels documents supportent la couverture de queue ?"),
        research_mandate=ResearchMandate.from_payload(mandate_payload()),
        requested_mode=ResearchMode.DOCUMENTARY_SIMPLE,
        requested_by_context="CV",
        occurred_at="2026-06-30T08:20:00Z",
    )


def documentary_plan():
    return ResearchPlan(
        plan_id="RPLAN-M007-T003-UNIT",
        mode=ResearchMode.DOCUMENTARY_SIMPLE,
        coverage_obligations=(
            CoverageObligation(
                name="question_autonome",
                description="Valider que la question RA est autonome.",
            ),
            CoverageObligation(
                name="mandat_documentaire",
                description="Respecter le mandat documentaire explicite.",
            ),
            CoverageObligation(
                name="preuves_documentaires",
                description="Collecter des preuves candidates via les ports publiés.",
            ),
        ),
        policy_version="research-planning-m007-documentary-simple-v1",
    )


# Les objets-valeur refusent les entrées implicites ou absentes.
assert_raises("resolved_question vide", lambda: ResolvedQuestion(""))
assert_raises("resolved_question non normalisee", lambda: ResolvedQuestion(" question "))
assert_raises(
    "research_mandate absent",
    lambda: OpenResearchCaseCommand(
        resolved_question=ResolvedQuestion("Question autonome ?"),
        research_mandate=None,
        requested_mode=ResearchMode.DOCUMENTARY_SIMPLE,
        requested_by_context="CV",
        idempotency_key="OPEN-RESEARCH-CASE-M007-T003-UNIT-0002",
        occurred_at="2026-06-30T08:21:00Z",
    ),
)
assert_raises("requested_mode absent", lambda: OpenResearchCaseCommand.from_payload({key: value for key, value in command_payload().items() if key != "requested_mode"}))
assert_equal(ResearchMode.from_value("DEEP_RESEARCH"), ResearchMode.DEEP_RESEARCH, "Le mode approfondi M-009 doit être reconnu sans être traité par M-007.")
assert_raises("coverage_obligation name vide", lambda: CoverageObligation(name="", description="description"))
assert_raises(
    "coverage_obligations absentes",
    lambda: ResearchPlan(
        plan_id="RPLAN-M007-T003-EMPTY",
        mode=ResearchMode.DOCUMENTARY_SIMPLE,
        coverage_obligations=(),
        policy_version="research-planning-m007-documentary-simple-v1",
    ),
)

# Le mandat est explicite et interdit les champs de preuve conversationnelle ou de stockage interne.
mandate = ResearchMandate.from_payload(mandate_payload())
assert_equal(mandate.language, "fr", "La langue du mandat doit être explicite.")
assert_raises(
    "research_mandate champ interdit: conversation_history",
    lambda: ResearchMandate.from_payload({**mandate_payload(), "conversation_history": ("tour utilisateur",)}),
)
assert_raises(
    "research_mandate champ interdit: qdrant_collection",
    lambda: ResearchMandate.from_payload({**mandate_payload(), "qdrant_collection": "knowledge_access"}),
)
for forbidden_key in ("conversation_history", "conversation_turns", "raw_conversation", "history_as_evidence"):
    assert_raises(
        "historique conversationnel interdit",
        lambda key=forbidden_key: OpenResearchCaseCommand.from_payload(
            {**command_payload(), key: ("contenu conversationnel brut",)}
        ),
    )

# L'agrégat démarre CREATED puis refuse la collecte de preuves tant que le plan n'est pas publié.
case = opened_case()
assert_equal(case.status, ResearchCaseStatus.CREATED, "Le cas ouvert doit commencer CREATED.")
assert_equal(tuple(event.event_type for event in case.events), ("ResearchCaseOpened",), "L'ouverture doit émettre ResearchCaseOpened.")
assert_raises("recherche non planifiee", lambda: case.ensure_evidence_collection_allowed())

# La planification publie un plan immuable et refuse la planification dupliquée.
plan = documentary_plan()
planned_case = case.plan_research(plan)
assert_equal(planned_case.status, ResearchCaseStatus.PLANNED, "Le cas doit passer PLANNED.")
assert_equal(
    tuple(event.event_type for event in planned_case.events),
    ("ResearchCaseOpened", "ResearchPlanCreated"),
    "La planification doit ajouter ResearchPlanCreated.",
)
planned_case.ensure_evidence_collection_allowed()
assert_raises("research_case deja planifie", lambda: planned_case.plan_research(plan))

plan_payload = planned_case.research_plan.to_payload()
plan_payload["coverage_obligations"][0]["name"] = "obligation_mutée"
assert_equal(
    planned_case.research_plan.coverage_obligations[0].name,
    "question_autonome",
    "Modifier le payload publié ne doit pas muter le plan du domaine.",
)
assert_raises("cannot assign", lambda: setattr(planned_case.research_plan, "policy_version", "mutated"))

# Le planificateur local M-007 reste déterministe et explicite.
policy = LocalDeterministicResearchPlanningPolicy.for_m007_documentary_simple()
policy_plan = policy.plan_for(case)
assert_equal(policy_plan.policy_version, "research-planning-m007-documentary-simple-v1", "La version de politique doit être explicite.")
assert_equal(
    tuple(obligation.name for obligation in policy_plan.coverage_obligations),
    ("question_autonome", "mandat_documentaire", "preuves_documentaires"),
    "Les obligations M-007 doivent être nommées et déterministes.",
)
assert_raises(
    "research_mode non supporte par politique",
    lambda: policy.plan_for(
        ResearchCase.open(
            research_case_id="RSC-M007-T003-DEEP-REFUSED",
            resolved_question=ResolvedQuestion("Quels documents comparer en profondeur ?"),
            research_mandate=ResearchMandate.from_payload(mandate_payload()),
            requested_mode=ResearchMode.DEEP_RESEARCH,
            requested_by_context="CV",
            occurred_at="2026-06-30T08:25:00Z",
        )
    ),
)

# Le handler orchestre commande, agrégat, politique et repository strict sans accès KA/EG direct.
repository = InMemoryResearchCaseRepository.empty()
handler = OpenResearchCaseHandler(
    research_case_repository=repository,
    planning_policy=policy,
)
result = handler.open_and_plan(OpenResearchCaseCommand.from_payload(command_payload()))
assert_equal(result.status, "RESEARCH_CASE_PLANNED", "Le handler doit exposer un statut planifié.")
assert_equal(repository.case_for_id(result.research_case_id).status, ResearchCaseStatus.PLANNED, "Le repository doit conserver le cas planifié.")
assert_raises("research_case inconnu", lambda: repository.case_for_id("RSC-M007-T003-UNKNOWN"))
assert_raises(
    "research_case deja enregistre",
    lambda: repository.save(
        ResearchCase.open(
            research_case_id=result.research_case_id,
            resolved_question=ResolvedQuestion("Question concurrente ?"),
            research_mandate=ResearchMandate.from_payload(mandate_payload()),
            requested_mode=ResearchMode.DOCUMENTARY_SIMPLE,
            requested_by_context="CV",
            occurred_at="2026-06-30T08:30:00Z",
        )
    ),
)

print("Tests unitaires T-003 ResearchCase mandat explicite M-007: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m007_research_case_mandate_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-003 ResearchCase mandat explicite M-007: OK"
