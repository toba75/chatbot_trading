$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$supportedOutcomeFixturePath = Join-Path $repoRoot "tests/fixtures/m001/contracts/ra_to_sd_verified_research_outcome_v1.json"
$conflictingOutcomeFixturePath = Join-Path $repoRoot "tests/fixtures/m001/contracts/ra_to_sd_verified_research_outcome_conflicting_v1.json"

foreach ($fixturePath in @($supportedOutcomeFixturePath, $conflictingOutcomeFixturePath)) {
    if (-not (Test-Path -LiteralPath $fixturePath -PathType Leaf)) {
        throw "Fixture de contrat VerifiedResearchOutcome absente: $fixturePath"
    }
}

$pythonCode = @'
import json
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])

from app.contracts.research_outcomes import VerifiedResearchOutcome
from app.strategy_design.adapters.research_outcome_translator import (
    StrategyDesignResearchOutcomeTranslator,
)


def load_payload(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def assert_raises(expected_fragment, action):
    try:
        action()
    except ValueError as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


def assert_no_internal_ra_or_sd_keys(payload):
    forbidden_keys = {
        "answer_draft",
        "answer_repository_id",
        "compiled_strategy",
        "evidence_set_id",
        "ra_internal_state",
        "research_case_status",
        "strategy_candidate_id",
        "strategy_rule",
        "rule_expression",
    }

    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in forbidden_keys:
                raise AssertionError(f"Modèle interne exposé dans le contrat RA vers SD: {key}")
            assert_no_internal_ra_or_sd_keys(value)
    elif isinstance(payload, list):
        for item in payload:
            assert_no_internal_ra_or_sd_keys(item)


supported_payload = load_payload(sys.argv[2])
conflicting_payload = load_payload(sys.argv[3])

# Given RA a terminé un cas de recherche avec un statut de support explicite.
supported_outcome = VerifiedResearchOutcome.from_payload(supported_payload)
conflicting_outcome = VerifiedResearchOutcome.from_payload(conflicting_payload)

# When SD reçoit le VerifiedResearchOutcome via son anti-corruption layer.
translator = StrategyDesignResearchOutcomeTranslator()
supported_decisions = translator.translate(supported_outcome)
conflicting_decisions = translator.translate(conflicting_outcome)

# Then SD obtient une traduction explicite sans lire l'état interne RA ni créer une règle.
if supported_outcome.question != supported_payload["question"]:
    raise AssertionError("La question résolue doit être conservée.")
if supported_outcome.mandate["objective"] != supported_payload["mandate"]["objective"]:
    raise AssertionError("Le mandat explicite doit être conservé.")
if str(supported_outcome.claim_refs[0]) != "CLM-004812@3":
    raise AssertionError("Les claim_refs doivent rester versionnés.")

decision_types = {decision.decision_type for decision in supported_decisions}
expected_decisions = {"SOURCE_ORIGIN", "MANDATE_CONSTRAINT", "KNOWLEDGE_GAP", "SUPPORT_STATUS"}
if expected_decisions - decision_types:
    raise AssertionError(f"Décisions de traduction manquantes: {expected_decisions - decision_types}")

conflicting_decision_types = {decision.decision_type for decision in conflicting_decisions}
if "UNRESOLVED_CONFLICT" not in conflicting_decision_types:
    raise AssertionError("Les conflits non résolus doivent rester visibles pour SD.")

for decision in tuple(supported_decisions) + tuple(conflicting_decisions):
    payload = decision.to_payload()
    if payload.get("strategy_rule") is not None or payload.get("rule_expression") is not None:
        raise AssertionError("Le traducteur ne doit pas créer de règle de stratégie.")

for payload in (supported_payload, conflicting_payload):
    assert_no_internal_ra_or_sd_keys(payload)

missing_mandate = dict(supported_payload)
del missing_mandate["mandate"]
assert_raises("mandate absent", lambda: VerifiedResearchOutcome.from_payload(missing_mandate))

missing_status = dict(supported_payload)
del missing_status["support_status"]
assert_raises("support_status absent", lambda: VerifiedResearchOutcome.from_payload(missing_status))

unversioned_claim = dict(supported_payload)
unversioned_claim["claim_refs"] = ["CLM-004812"]
assert_raises("claim_refs invalide", lambda: VerifiedResearchOutcome.from_payload(unversioned_claim))

masked_conflict = dict(supported_payload)
masked_conflict["unresolved_conflicts"] = [
    {
        "summary": "Deux horizons opposés restent incompatibles.",
        "claim_refs": ["CLM-004812@3", "CLM-009001@1"],
        "blocking": True,
    }
]
assert_raises("support_status masque des conflits", lambda: VerifiedResearchOutcome.from_payload(masked_conflict))

implicit_status = dict(supported_payload)
implicit_status["support_status"] = ""
assert_raises("support_status vide", lambda: VerifiedResearchOutcome.from_payload(implicit_status))

print("Contrat VerifiedResearchOutcome RA vers SD M-001 accepté.")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m001_research_outcome_contract_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
try {
    $output = & python -B $pythonScriptPath $repoRoot $supportedOutcomeFixturePath $conflictingOutcomeFixturePath 2>&1
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
    Remove-Item -LiteralPath $pythonScriptPath -Force
}

if ($LASTEXITCODE -ne 0) {
    throw ($output -join "`n")
}

Write-Host "Test d'acceptation du contrat VerifiedResearchOutcome M-001: OK"
