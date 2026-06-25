$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

sys.path.insert(0, sys.argv[1])

from app.contracts.research_outcomes import (
    ALLOWED_RESEARCH_SUPPORT_STATUSES,
    CONFLICTING_EVIDENCE_STATUS,
    SUPPORTED_STATUS,
    VersionedClaimRef,
    VerifiedResearchOutcome,
)
from app.strategy_design.adapters.research_outcome_translator import (
    ResearchOutcomeTranslationDecision,
    StrategyDesignResearchOutcomeTranslator,
)


def assert_raises(expected_fragment, action):
    try:
        action()
    except ValueError as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


def base_payload():
    return {
        "schema_version": "1.0",
        "research_case_id": "RSC-000055",
        "question": "Quelles conditions documentées soutiennent un suivi de tendance quotidien sur futures ?",
        "mandate": {
            "objective": "formaliser une hypothèse de stratégie testable",
            "universe": ["futures"],
            "frequency": "daily",
            "must_preserve_conflicts": True,
        },
        "answer_id": "ANS-000055",
        "support_status": SUPPORTED_STATUS,
        "claim_refs": ["CLM-004812@3"],
        "unresolved_conflicts": [],
        "knowledge_gaps": [
            {
                "topic": "coûts de transaction récents",
                "impact": "paramètre à calibrer avant compilation",
            }
        ],
        "completed_at": "2026-06-21T09:30:00Z",
    }


def conflicting_payload():
    payload = base_payload()
    payload["support_status"] = CONFLICTING_EVIDENCE_STATUS
    payload["claim_refs"] = ["CLM-004812@3", "CLM-009001@1"]
    payload["unresolved_conflicts"] = [
        {
            "summary": "Les preuves divergent entre horizon quotidien et horizon mensuel.",
            "claim_refs": ["CLM-004812@3", "CLM-009001@1"],
            "blocking": True,
        }
    ]
    return payload


outcome = VerifiedResearchOutcome.from_payload(base_payload())
if VerifiedResearchOutcome.from_json(outcome.to_json()) != outcome:
    raise AssertionError("Le round-trip unitaire VerifiedResearchOutcome doit rester stable.")
if VerifiedResearchOutcome.from_json(outcome.to_json()).to_json() != outcome.to_json():
    raise AssertionError("La sérialisation VerifiedResearchOutcome doit être déterministe.")

initial_json = outcome.to_json()
try:
    outcome.mandate["objective"] = "mutation interdite"
except TypeError:
    pass
else:
    raise AssertionError("VerifiedResearchOutcome.mandate doit etre immuable apres validation.")
if outcome.to_json() != initial_json:
    raise AssertionError("Une mutation externe ne doit pas modifier VerifiedResearchOutcome.")

if str(VersionedClaimRef.parse("CLM-004812@3")) != "CLM-004812@3":
    raise AssertionError("VersionedClaimRef doit conserver claim_id et version.")

for status in ALLOWED_RESEARCH_SUPPORT_STATUSES:
    payload = conflicting_payload() if status == CONFLICTING_EVIDENCE_STATUS else base_payload()
    payload["support_status"] = status
    VerifiedResearchOutcome.from_payload(payload)

missing_mandate = base_payload()
del missing_mandate["mandate"]
assert_raises("mandate absent", lambda: VerifiedResearchOutcome.from_payload(missing_mandate))

empty_mandate = base_payload()
empty_mandate["mandate"] = {}
assert_raises("mandate vide", lambda: VerifiedResearchOutcome.from_payload(empty_mandate))

missing_status = base_payload()
del missing_status["support_status"]
assert_raises("support_status absent", lambda: VerifiedResearchOutcome.from_payload(missing_status))

blank_status = base_payload()
blank_status["support_status"] = ""
assert_raises("support_status vide", lambda: VerifiedResearchOutcome.from_payload(blank_status))

unknown_status = base_payload()
unknown_status["support_status"] = "DRAFT"
assert_raises("support_status non autoris", lambda: VerifiedResearchOutcome.from_payload(unknown_status))

missing_claim_refs = base_payload()
del missing_claim_refs["claim_refs"]
assert_raises("claim_refs absent", lambda: VerifiedResearchOutcome.from_payload(missing_claim_refs))

empty_claim_refs = base_payload()
empty_claim_refs["claim_refs"] = []
assert_raises("claim_refs vide", lambda: VerifiedResearchOutcome.from_payload(empty_claim_refs))

unversioned_claim = base_payload()
unversioned_claim["claim_refs"] = ["CLM-004812"]
assert_raises("claim_refs invalide", lambda: VerifiedResearchOutcome.from_payload(unversioned_claim))

zero_version_claim = base_payload()
zero_version_claim["claim_refs"] = ["CLM-004812@0"]
assert_raises("claim_refs invalide", lambda: VerifiedResearchOutcome.from_payload(zero_version_claim))

wrong_prefix_claim = base_payload()
wrong_prefix_claim["claim_refs"] = ["ANS-004812@3"]
assert_raises("claim_refs invalide", lambda: VerifiedResearchOutcome.from_payload(wrong_prefix_claim))

missing_conflicts = base_payload()
del missing_conflicts["unresolved_conflicts"]
assert_raises("unresolved_conflicts absent", lambda: VerifiedResearchOutcome.from_payload(missing_conflicts))

conflicting_without_conflicts = conflicting_payload()
conflicting_without_conflicts["unresolved_conflicts"] = []
assert_raises(
    "unresolved_conflicts requis pour CONFLICTING_EVIDENCE",
    lambda: VerifiedResearchOutcome.from_payload(conflicting_without_conflicts),
)

supported_with_conflict = conflicting_payload()
supported_with_conflict["support_status"] = SUPPORTED_STATUS
assert_raises(
    "support_status masque des conflits",
    lambda: VerifiedResearchOutcome.from_payload(supported_with_conflict),
)

invalid_conflict = conflicting_payload()
invalid_conflict["unresolved_conflicts"] = [{"claim_refs": ["CLM-004812@3"], "blocking": True}]
assert_raises("unresolved_conflicts invalide", lambda: VerifiedResearchOutcome.from_payload(invalid_conflict))

internal_conflict = conflicting_payload()
internal_conflict["unresolved_conflicts"] = [
    dict(internal_conflict["unresolved_conflicts"][0])
]
internal_conflict["unresolved_conflicts"][0]["ra_internal_state"] = "interne"
assert_raises("champ interdit", lambda: VerifiedResearchOutcome.from_payload(internal_conflict))

missing_gaps = base_payload()
del missing_gaps["knowledge_gaps"]
assert_raises("knowledge_gaps absent", lambda: VerifiedResearchOutcome.from_payload(missing_gaps))

invalid_gap = base_payload()
invalid_gap["knowledge_gaps"] = [{"impact": "paramètre à calibrer"}]
assert_raises("knowledge_gaps invalide", lambda: VerifiedResearchOutcome.from_payload(invalid_gap))

internal_gap = base_payload()
internal_gap["knowledge_gaps"] = [dict(internal_gap["knowledge_gaps"][0])]
internal_gap["knowledge_gaps"][0]["answer_draft"] = "brouillon interne"
assert_raises("champ interdit", lambda: VerifiedResearchOutcome.from_payload(internal_gap))

internal_answer_key = base_payload()
internal_answer_key["mandate"] = dict(internal_answer_key["mandate"])
internal_answer_key["mandate"]["answer_draft"] = "brouillon interne"
assert_raises("cle interdite", lambda: VerifiedResearchOutcome.from_payload(internal_answer_key))

top_level_extra_key = base_payload()
top_level_extra_key["answer_draft"] = "brouillon interne"
assert_raises("champ interdit", lambda: VerifiedResearchOutcome.from_payload(top_level_extra_key))

impossible_completed_at = base_payload()
impossible_completed_at["completed_at"] = "2026-02-30T09:30:00Z"
assert_raises("completed_at invalide", lambda: VerifiedResearchOutcome.from_payload(impossible_completed_at))

non_finite_mandate_value = base_payload()
non_finite_mandate_value["mandate"] = dict(non_finite_mandate_value["mandate"])
non_finite_mandate_value["mandate"]["score"] = float("inf")
assert_raises("valeur de contrat invalide", lambda: VerifiedResearchOutcome.from_payload(non_finite_mandate_value))

insufficient_without_gap = base_payload()
insufficient_without_gap["support_status"] = "INSUFFICIENT_EVIDENCE"
insufficient_without_gap["knowledge_gaps"] = []
assert_raises("knowledge_gaps requis", lambda: VerifiedResearchOutcome.from_payload(insufficient_without_gap))

requires_current_without_gap = base_payload()
requires_current_without_gap["support_status"] = "REQUIRES_CURRENT_DATA"
requires_current_without_gap["knowledge_gaps"] = []
assert_raises("knowledge_gaps requis", lambda: VerifiedResearchOutcome.from_payload(requires_current_without_gap))

translator = StrategyDesignResearchOutcomeTranslator()
decisions = translator.translate(outcome)
decision_payloads = [decision.to_payload() for decision in decisions]
if any("strategy_rule" in payload or "rule_expression" in payload for payload in decision_payloads):
    raise AssertionError("Le traducteur SD ne doit pas compiler de stratégie.")
if any(payload["source_answer_id"] != "ANS-000055" for payload in decision_payloads):
    raise AssertionError("Chaque décision de traduction doit rester liée à la réponse RA.")
assert_raises("VerifiedResearchOutcome attendu", lambda: translator.translate(base_payload()))

decision_json = decisions[0].to_payload()
try:
    decisions[0].details["support_status"] = "MUTATED"
except TypeError:
    pass
else:
    raise AssertionError("ResearchOutcomeTranslationDecision.details doit etre immuable.")
if decisions[0].to_payload() != decision_json:
    raise AssertionError("Une mutation externe ne doit pas modifier la decision de traduction.")

assert_raises(
    "cle interdite",
    lambda: ResearchOutcomeTranslationDecision(
        decision_type="FORBIDDEN_DETAIL",
        source_research_case_id="RSC-000055",
        source_answer_id="ANS-000055",
        source_claim_refs=("CLM-004812@3",),
        description="Detail interne refuse.",
        blocking=False,
        details={"answer_draft": "brouillon interne"},
    ),
)
assert_raises(
    "valeur de traduction invalide",
    lambda: ResearchOutcomeTranslationDecision(
        decision_type="NON_FINITE_DETAIL",
        source_research_case_id="RSC-000055",
        source_answer_id="ANS-000055",
        source_claim_refs=("CLM-004812@3",),
        description="Score non fini refuse.",
        blocking=False,
        details={"score": float("nan")},
    ),
)

print("Invariants unitaires VerifiedResearchOutcome M-001: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m001_research_outcome_contract_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
try {
    $output = & $pythonExecutable -B $pythonScriptPath $repoRoot 2>&1
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
    Remove-Item -LiteralPath $pythonScriptPath -Force
}

if ($LASTEXITCODE -ne 0) {
    throw ($output -join "`n")
}

Write-Host "Tests unitaires VerifiedResearchOutcome M-001: OK"
