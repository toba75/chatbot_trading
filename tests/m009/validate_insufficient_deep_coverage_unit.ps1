$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys
from types import SimpleNamespace

sys.path.insert(0, sys.argv[1])

from app.research_answering.domain.contradiction_assessment import SupportStatus
from app.research_answering.domain.evidence_set import (
    DeepCoverageRequirement,
    DeepEvidenceCoveragePolicy,
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


def candidate(*, obligations, polarity="FAVORABLE", source_kind="SECONDARY"):
    return SimpleNamespace(
        covered_obligations=obligations,
        evidence_polarity=polarity,
        source_kind=source_kind,
    )


def requirement(
    *,
    obligation,
    critical,
    polarity="ANY",
    primary=False,
    reason_code="COVERAGE_OBLIGATION_MISSING",
    public_reason="Couverture documentaire requise absente.",
):
    return DeepCoverageRequirement(
        obligation_name=obligation,
        critical=critical,
        required_polarity=polarity,
        requires_primary_source=primary,
        reason_code=reason_code,
        public_reason=public_reason,
    )


def policy_for(*requirements):
    return DeepEvidenceCoveragePolicy(
        coverage_requirements=requirements,
        policy_version="deep-evidence-coverage-m009-v1",
    )


# Une obligation critique absente produit INSUFFICIENT_EVIDENCE.
critical_policy = policy_for(
    requirement(
        obligation="preuves_favorables",
        critical=True,
        polarity="FAVORABLE",
        reason_code="FAVORABLE_EVIDENCE_MISSING",
    ),
    requirement(
        obligation="preuves_defavorables",
        critical=True,
        polarity="UNFAVORABLE",
        reason_code="UNFAVORABLE_EVIDENCE_MISSING",
        public_reason="Aucune preuve defavorable admissible ne couvre le mandat.",
    ),
)
critical_evaluation = critical_policy.evaluate(
    (candidate(obligations=("preuves_favorables",), polarity="FAVORABLE"),)
)
assert_equal(
    critical_evaluation.support_status,
    SupportStatus.INSUFFICIENT_EVIDENCE,
    "Une obligation critique manquante doit bloquer SUPPORTED.",
)
assert_equal(
    critical_evaluation.missing_obligations,
    ("preuves_defavorables",),
    "L'obligation critique manquante doit etre conservee.",
)
assert_equal(
    critical_evaluation.critical_missing_obligations,
    ("preuves_defavorables",),
    "La criticite doit rester explicite.",
)

# Une obligation non critique absente qualifie la sortie sans produire un support complet.
qualified_policy = policy_for(
    requirement(obligation="methodes", critical=True),
    requirement(
        obligation="zones_non_documentees",
        critical=False,
        reason_code="DOCUMENTARY_ZONE_UNCOVERED",
        public_reason="Les zones non documentees doivent rester visibles.",
    ),
)
qualified_evaluation = qualified_policy.evaluate(
    (candidate(obligations=("methodes",), polarity="NEUTRAL", source_kind="PRIMARY"),)
)
assert_equal(
    qualified_evaluation.support_status,
    SupportStatus.PARTIALLY_SUPPORTED,
    "Une lacune non critique doit qualifier la reponse.",
)
assert_equal(
    qualified_evaluation.qualified_obligations,
    ("zones_non_documentees",),
    "L'obligation non critique doit etre qualifiee.",
)

# Une obligation de preuve defavorable n'est pas satisfaite par une preuve favorable.
unfavorable_policy = policy_for(
    requirement(
        obligation="preuves_defavorables",
        critical=True,
        polarity="UNFAVORABLE",
        reason_code="UNFAVORABLE_EVIDENCE_MISSING",
        public_reason="Aucune preuve defavorable admissible ne couvre le mandat.",
    ),
)
unfavorable_evaluation = unfavorable_policy.evaluate(
    (candidate(obligations=("preuves_defavorables",), polarity="FAVORABLE"),)
)
assert_equal(
    unfavorable_evaluation.support_status,
    SupportStatus.INSUFFICIENT_EVIDENCE,
    "Une preuve favorable ne doit pas couvrir l'obligation defavorable.",
)
assert_equal(
    unfavorable_evaluation.reason_codes,
    ("UNFAVORABLE_EVIDENCE_MISSING",),
    "La raison d'absence de preuve defavorable doit etre publique.",
)

# Une exigence de source primaire n'est pas satisfaite par une source secondaire.
primary_policy = policy_for(
    requirement(
        obligation="methodes",
        critical=True,
        primary=True,
        reason_code="PRIMARY_SOURCE_MISSING",
        public_reason="Aucune source primaire admissible ne documente les methodes.",
    ),
)
primary_evaluation = primary_policy.evaluate(
    (candidate(obligations=("methodes",), polarity="NEUTRAL", source_kind="SECONDARY"),)
)
assert_equal(
    primary_evaluation.support_status,
    SupportStatus.INSUFFICIENT_EVIDENCE,
    "Une source secondaire ne doit pas couvrir une obligation primaire critique.",
)
assert_equal(primary_evaluation.reason_codes, ("PRIMARY_SOURCE_MISSING",), "La source primaire absente doit etre nommee.")

# CURRENT_DATA_REQUIRED reste une politique separee de la couverture documentaire.
assert_raises(
    "CURRENT_DATA_REQUIRED separe de couverture documentaire",
    lambda: requirement(
        obligation="donnees_actuelles",
        critical=True,
        reason_code="CURRENT_DATA_REQUIRED",
        public_reason="Donnees actuelles requises.",
    ),
)

# Les lacunes dupliquees et les raisons publiques absentes sont refusees.
assert_raises(
    "coverage_requirement dupliquee",
    lambda: policy_for(
        requirement(obligation="methodes", critical=True),
        requirement(obligation="methodes", critical=False),
    ),
)
assert_raises(
    "public_reason vide",
    lambda: requirement(
        obligation="methodes",
        critical=True,
        public_reason="",
    ),
)

# Une couverture complete peut rester SUPPORTED.
supported = policy_for(
    requirement(obligation="methodes", critical=True, primary=True),
    requirement(obligation="preuves_defavorables", critical=True, polarity="UNFAVORABLE"),
).evaluate(
    (
        candidate(obligations=("methodes",), polarity="NEUTRAL", source_kind="PRIMARY"),
        candidate(obligations=("preuves_defavorables",), polarity="UNFAVORABLE", source_kind="SECONDARY"),
    )
)
assert_equal(supported.support_status, SupportStatus.SUPPORTED, "Une couverture complete doit rester supportable.")
assert_equal(supported.missing_obligations, (), "Aucune lacune ne doit etre inventee.")
assert_true("methodes" in supported.covered_obligations, "Les obligations couvertes doivent rester auditables.")

print("Tests unitaires T-007 couverture approfondie insuffisante M-009: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m009_insufficient_deep_coverage_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-007 couverture approfondie insuffisante M-009: OK"
