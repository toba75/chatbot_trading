$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

sys.path.insert(0, sys.argv[1])

from app.contracts.research_outcomes import VerifiedResearchOutcome
from app.research_answering.domain.answer import (
    AbstentionPolicy,
    AbstentionReason,
    AnswerFreshnessPolicy,
)
from app.research_answering.domain.contradiction_assessment import SupportStatus


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_is_none(actual, message):
    if actual is not None:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_not_contains(text, forbidden_fragment, message):
    if forbidden_fragment in text:
        raise AssertionError(f"{message} Fragment interdit: {forbidden_fragment!r}")


def assert_raises(expected_fragment, action):
    try:
        action()
    except ValueError as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


def freshness_policy():
    return AnswerFreshnessPolicy(
        policy_version="answer-freshness-m007-v1",
        current_support_policy_version="answer-support-m007-v1",
        accepted_canonical_version_ids=("CVER-M007-T008-UNIT",),
    )


def mandate_without_current_source():
    return {
        "allowed_universe": ("documents canoniques OSTrading",),
        "horizon": "prix de marché récent",
        "data_requirements": ("preuves candidates KA", "claims vérifiés EG"),
        "exclusions": ("données de marché actuelles non autorisées",),
        "language": "fr",
        "detail_level": "abstention vérifiée",
    }


def mandate_with_untrusted_current_source():
    return {
        "allowed_universe": ("capture manuelle non vérifiée",),
        "horizon": "prix de marché récent",
        "data_requirements": ("données de marché actuelles autorisées",),
        "exclusions": ("aucun stockage interne publié",),
        "language": "fr",
        "detail_level": "abstention vérifiée",
    }


def mandate_forbidding_external_access():
    return {
        "allowed_universe": ("source de données de marché actuelle autorisée",),
        "horizon": "prix de marché récent",
        "data_requirements": ("données de marché actuelles autorisées",),
        "exclusions": ("accès externe interdit",),
        "language": "fr",
        "detail_level": "abstention vérifiée",
    }


def mandate_with_authorized_current_source():
    return {
        "allowed_universe": ("source de donnees de marche actuelle autorisee",),
        "horizon": "prix de marché récent",
        "data_requirements": ("donnees de marche actuelles autorisees",),
        "exclusions": ("aucun stockage interne publié",),
        "language": "fr",
        "detail_level": "réponse avec donnée actuelle prouvée",
    }


def requires_current_payload():
    return {
        "schema_version": "1.0",
        "research_case_id": "RSC-M007-T008-UNIT",
        "question": "Quel est le prix actuel de NVDA ?",
        "mandate": mandate_without_current_source(),
        "answer_id": "ANS-M007-T008-UNIT",
        "support_status": "REQUIRES_CURRENT_DATA",
        "claim_refs": [],
        "unresolved_conflicts": [],
        "knowledge_gaps": [
            {
                "topic": "données actuelles autorisées",
                "impact": "La question requiert des données actuelles non autorisées.",
            }
        ],
        "completed_at": "2026-06-30T18:00:00Z",
    }


policy = freshness_policy()

# Une question de prix récent sans source actuelle autorisée déclenche l'abstention.
reason = policy.current_data_abstention_reason(
    question="Quel est le prix actuel de NVDA ?",
    mandate=mandate_without_current_source(),
)
assert_equal(
    reason,
    AbstentionReason.CURRENT_DATA_REQUIRED,
    "La source actuelle absente doit déclencher CURRENT_DATA_REQUIRED.",
)

# Une mention de donnée actuelle dans le mandat ne suffit pas si la source n'est pas autorisée.
reason = policy.current_data_abstention_reason(
    question="Quel est le prix actuel de BTC ?",
    mandate=mandate_with_untrusted_current_source(),
)
assert_equal(
    reason,
    AbstentionReason.CURRENT_DATA_REQUIRED,
    "Une source actuelle non autorisée doit déclencher CURRENT_DATA_REQUIRED.",
)

# Le mandat qui interdit l'externe bloque explicitement la donnée actuelle.
reason = policy.current_data_abstention_reason(
    question="Quel niveau de marché maintenant pour l'indice ?",
    mandate=mandate_forbidding_external_access(),
)
assert_equal(
    reason,
    AbstentionReason.CURRENT_DATA_REQUIRED,
    "Un mandat interdisant l'externe doit déclencher CURRENT_DATA_REQUIRED.",
)

# Une question stable ne doit pas être convertie en abstention de fraîcheur.
assert_is_none(
    policy.current_data_abstention_reason(
        question="Quelle règle documentaire gouverne les citations ?",
        mandate=mandate_without_current_source(),
    ),
    "Une question documentaire stable ne doit pas déclencher une donnée actuelle.",
)

# Une autorisation explicite laisse passer la suite de vérification sans appel implicite.
assert_is_none(
    policy.current_data_abstention_reason(
        question="Quel est le prix actuel de NVDA ?",
        mandate=mandate_with_authorized_current_source(),
    ),
    "Une source actuelle explicitement autorisée ne doit pas déclencher l'abstention.",
)

assert_equal(
    AbstentionReason.CURRENT_DATA_REQUIRED.public_error_code,
    "CURRENT_DATA_REQUIRED",
    "La raison d'abstention doit exposer l'erreur publique.",
)
assert_equal(
    AbstentionReason.CURRENT_DATA_REQUIRED.support_status,
    SupportStatus.REQUIRES_CURRENT_DATA,
    "La raison d'abstention doit mapper vers REQUIRES_CURRENT_DATA.",
)

abstention_policy = AbstentionPolicy(policy_version="abstention-policy-m007-v1")
answer_text = abstention_policy.answer_text_for(AbstentionReason.CURRENT_DATA_REQUIRED)
assert_equal(
    answer_text,
    abstention_policy.answer_text_for(AbstentionReason.CURRENT_DATA_REQUIRED),
    "Le texte public d'abstention doit être déterministe.",
)
if "CURRENT_DATA_REQUIRED" not in answer_text:
    raise AssertionError("Le texte public d'abstention doit exposer CURRENT_DATA_REQUIRED.")
assert_not_contains(
    answer_text,
    "140",
    "Le texte d'abstention ne doit pas reprendre une valeur de marché inventée.",
)
assert_not_contains(
    answer_text,
    "USD",
    "Le texte d'abstention ne doit pas reprendre une devise inventée.",
)

outcome = VerifiedResearchOutcome.from_payload(requires_current_payload())
assert_equal(
    outcome.support_status,
    "REQUIRES_CURRENT_DATA",
    "Le contrat RA doit accepter l'abstention pour donnée actuelle.",
)
assert_equal(
    tuple(outcome.claim_refs),
    (),
    "REQUIRES_CURRENT_DATA ne doit pas exiger de claim de marché inventé.",
)

partially_supported_without_claim = requires_current_payload()
partially_supported_without_claim["support_status"] = "PARTIALLY_SUPPORTED"
assert_raises(
    "claim_refs vide",
    lambda: VerifiedResearchOutcome.from_payload(partially_supported_without_claim),
)

print("Tests unitaires T-008 abstention données actuelles M-007: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m007_current_data_abstention_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-008 abstention données actuelles M-007: OK"
