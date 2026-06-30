$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

sys.path.insert(0, sys.argv[1])

from app.evidence_governance.adapters.in_memory_claim_repository import InMemoryClaimRepository
from app.evidence_governance.application.retain_claims import SupersedeClaim, SupersedeClaimHandler
from app.evidence_governance.domain.claim_evidence import Claim, ClaimStatus, ClaimSuperseded, SupersededBy
from app.evidence_governance.domain.claim_extraction import (
    CanonicalProposition,
    ClaimCondition,
    ClaimScope,
    Limitation,
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
    except (TypeError, ValueError) as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


def scope_for():
    return ClaimScope(
        universe="portefeuilles convexes antifragiles",
        horizon="crises de volatilité",
        metric="drawdown",
        frequency="quotidienne",
    )


def claim_for(*, claim_id, claim_version=1, status=ClaimStatus.EVIDENCE_ATTACHED, text=None, **extra):
    if text is None:
        text = "Les couvertures de queue réduisent le drawdown pendant les crises de volatilité."
    return Claim(
        claim_id=claim_id,
        claim_version=claim_version,
        status=status,
        claim_type="EMPIRICAL_EFFECT",
        canonical_proposition=CanonicalProposition(text),
        scope=scope_for(),
        conditions=(ClaimCondition("crises de volatilité"),),
        limitations=(Limitation("résultat limité au span cité"),),
        evidence_associations=(),
        **extra,
    )


# Un rejet n'est valide qu'avec une raison publique et un instant de rejet.
assert_raises(
    "reason_codes requis",
    lambda: claim_for(
        claim_id="CLM-M006-T008-UNIT-REJECTED-MISSING-REASON",
        status=ClaimStatus.REJECTED,
        rejected_at="2026-06-29T21:00:00Z",
    ),
)
assert_raises(
    "rejected_at requis",
    lambda: claim_for(
        claim_id="CLM-M006-T008-UNIT-REJECTED-MISSING-DATE",
        status=ClaimStatus.REJECTED,
        rejection_reason_codes=("INSUFFICIENT_DIRECT_EVIDENCE",),
    ),
)
rejected = claim_for(
    claim_id="CLM-M006-T008-UNIT-REJECTED",
    status=ClaimStatus.REJECTED,
    rejection_reason_codes=("INSUFFICIENT_DIRECT_EVIDENCE",),
    rejected_at="2026-06-29T21:01:00Z",
)
assert_equal(rejected.rejection_reason_codes, ("INSUFFICIENT_DIRECT_EVIDENCE",), "La raison de rejet doit être conservée.")

# Une supersession n'est valide qu'avec un lien SupersededBy, une raison et un instant.
assert_raises(
    "superseded_by absent",
    lambda: claim_for(
        claim_id="CLM-M006-T008-UNIT-SUPERSEDED-MISSING-LINK",
        status=ClaimStatus.SUPERSEDED,
        supersession_reason="Nouvelle formulation.",
        superseded_at="2026-06-29T21:02:00Z",
    ),
)
assert_raises(
    "supersession_reason requis",
    lambda: claim_for(
        claim_id="CLM-M006-T008-UNIT-SUPERSEDED-MISSING-REASON",
        status=ClaimStatus.SUPERSEDED,
        superseded_by=SupersededBy(
            claim_id="CLM-M006-T008-UNIT-SUPERSEDED-MISSING-REASON",
            claim_version=2,
        ),
        superseded_at="2026-06-29T21:02:00Z",
    ),
)

old_claim = claim_for(claim_id="CLM-M006-T008-UNIT-SUPERSEDED")
new_claim = claim_for(
    claim_id=old_claim.claim_id,
    claim_version=2,
    text="Les couvertures de queue réduisent le drawdown quotidien pendant les crises de volatilité.",
)
old_superseded, event = old_claim.supersede_with(
    superseding_claim=new_claim,
    supersession_reason="Formulation précisée sans mutation de la version initiale.",
    occurred_at="2026-06-29T21:03:00Z",
)
assert_equal(old_superseded.status, ClaimStatus.SUPERSEDED, "L'ancienne version doit devenir SUPERSEDED.")
assert_equal(old_superseded.superseded_by.claim_version, 2, "Le lien SupersededBy doit viser la nouvelle version.")
assert_true(isinstance(event, ClaimSuperseded), "La supersession doit produire ClaimSuperseded.")
assert_equal(event.to_payload()["payload"]["new_claim_ref"]["claim_version"], 2, "L'événement doit publier la version cible.")

assert_raises(
    "transition claim interdite: REJECTED",
    lambda: rejected.supersede_with(
        superseding_claim=claim_for(
            claim_id=rejected.claim_id,
            claim_version=2,
            text="Nouvelle formulation refusée.",
        ),
        supersession_reason="Un rejet terminal ne se remplace pas.",
        occurred_at="2026-06-29T21:04:00Z",
    ),
)
assert_raises(
    "claim_version supersession invalide",
    lambda: old_claim.supersede_with(
        superseding_claim=claim_for(
            claim_id=old_claim.claim_id,
            claim_version=3,
            text="Version sautée.",
        ),
        supersession_reason="Version sautée.",
        occurred_at="2026-06-29T21:05:00Z",
    ),
)

# Le repository conserve les versions, interdit les nouvelles versions sans lien et refuse les mutations destructives.
repository = InMemoryClaimRepository.empty()
repository.save(old_claim)
assert_raises(
    "supersession explicite absente",
    lambda: repository.save(new_claim),
)
repository.save(old_superseded)
repository.save(new_claim)
assert_equal(repository.claim_for_version(old_claim.claim_id, 1).status, ClaimStatus.SUPERSEDED, "La version 1 doit rester consultable.")
assert_equal(repository.claim_for_version(old_claim.claim_id, 2).canonical_proposition.text, new_claim.canonical_proposition.text, "La version 2 doit être distincte.")
assert_equal(repository.claim_for_id(old_claim.claim_id).claim_version, 2, "La lecture par identifiant doit retourner la dernière version.")
assert_raises(
    "claim_version immuable",
    lambda: repository.save(
        claim_for(
            claim_id=old_claim.claim_id,
            claim_version=2,
            text="La proposition ne peut pas être changée en réutilisant le même identifiant de version.",
        )
    ),
)
assert_raises(
    "suppression claim interdite",
    lambda: repository.delete_claim_version(old_claim.claim_id, 1),
)

# Une décision négative sauvegardée ne peut pas être réécrite.
rejected_repository = InMemoryClaimRepository(claims=(rejected,))
assert_raises(
    "claim_decision immuable",
    lambda: rejected_repository.save(
        claim_for(
            claim_id=rejected.claim_id,
            status=ClaimStatus.REJECTED,
            rejection_reason_codes=("VERDICT_NOT_AUTHORIZED",),
            rejected_at="2026-06-29T21:01:00Z",
        )
    ),
)

print("Tests unitaires T-008 conservation claims rejetés et supersédés M-006: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m006_claim_retention_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-008 conservation claims rejetés et supersédés M-006: OK"
