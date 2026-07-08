$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom

$validatorPath = Join-Path $repoRoot "scripts/validate_m013_v1_gap_decisions.ps1"
$temporaryRoot = Join-Path $repoRoot (".tmp_m013_v1_gap_decisions_unit_" + [System.Guid]::NewGuid().ToString("N"))

$pythonCode = @'
import sys

repo_root = sys.argv[1]
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from app.evaluation.domain.v1_gap_decisions import (
    V1_GAP_DECISION_ACCEPTED,
    V1_GAP_DECISION_BLOCKING,
    V1_GAP_DECISION_CORRECTED,
    V1_GAP_DECISION_DEFERRED,
    V1_GAP_DECISION_POLICY_VERSION,
    V1_GAP_STATUS_BLOCKING,
    V1_GAP_STATUS_DEFERRED,
    V1_GAP_STATUS_SATISFIED,
    V1GapDecision,
    V1GapDecisionPolicy,
    build_m013_v1_gap_decision_register,
)


PROOF_COMMAND = "powershell -NoProfile -ExecutionPolicy Bypass -File .\\tests\\m012\\validate_knowledge_search_benchmark_acceptance.ps1"
CORRECTION_COMMAND = "powershell -NoProfile -ExecutionPolicy Bypass -File .\\tests\\m013\\validate_v1_gap_decisions_acceptance.ps1"


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_raises(expected_fragment, action):
    try:
        action()
    except (TypeError, ValueError) as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}") from exc
        return
    raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


def decision(**overrides):
    payload = {
        "gap_id": "V1-GAP-M012-KA-RECALL",
        "context": "KA",
        "m012_status": V1_GAP_STATUS_DEFERRED,
        "decision_status": V1_GAP_DECISION_DEFERRED,
        "v1_criterion_id": "V1-KA-RECHERCHE-PAGES",
        "benchmark_source_id": "KSRUN-M012-KNOWLEDGE-0001",
        "calibration_decision_id": "DEC-M012-KA-REJECTED",
        "source_report_path": "docs/governance/m012_v1_gap_report.md",
        "evidence_command": PROOF_COMMAND,
        "correction_command": "Non applicable: écart non corrigé par T-003.",
        "m013_green_proof": "Non applicable: T-003 conserve le test scientifique RED visible.",
        "non_acceptance_justification": "Recall@10 pilote sous seuil; report visible avant le rapport final V1.",
        "acceptance_impact": "Écart non accepté transmis au V1AcceptanceReport.",
    }
    payload.update(overrides)
    return V1GapDecision(**payload)


policy = V1GapDecisionPolicy(policy_version=V1_GAP_DECISION_POLICY_VERSION)

assert_raises("statut M-012 inconnu", lambda: decision(m012_status="ouvert"))
assert_raises("décision V1 inconnue", lambda: decision(decision_status="ouverte"))
assert_raises("décision sans preuve", lambda: decision(evidence_command=""))
assert_raises(
    "correction sans commande",
    lambda: decision(decision_status=V1_GAP_DECISION_CORRECTED, correction_command="Non applicable: correction absente."),
)
assert_raises(
    "écart bloquant accepté",
    lambda: decision(m012_status=V1_GAP_STATUS_BLOCKING, decision_status=V1_GAP_DECISION_ACCEPTED),
)
assert_raises(
    "écart différé sans justification",
    lambda: decision(decision_status=V1_GAP_DECISION_DEFERRED, non_acceptance_justification=""),
)
assert_raises("critère V1 absent", lambda: decision(v1_criterion_id=""))
assert_raises("contexte V1 incohérent", lambda: decision(v1_criterion_id="V1-SP-QUALITE-DOCUMENTAIRE"))
assert_raises(
    "décision contredit M-012",
    lambda: policy.publish_register(
        register_id="REG-M013-CONTRADICTION",
        source_statuses_by_context={"KA": V1_GAP_STATUS_SATISFIED},
        decisions=(decision(),),
    ),
)
assert_raises(
    "écart V1 dupliqué",
    lambda: policy.publish_register(
        register_id="REG-M013-DUPLICATE",
        source_statuses_by_context={"KA": V1_GAP_STATUS_DEFERRED},
        decisions=(decision(), decision(context="SP", gap_id="V1-GAP-M012-KA-RECALL")),
    ),
)

corrected = decision(
    gap_id="V1-GAP-M012-SD-CALIBRATION-PLAN",
    context="SD",
    m012_status=V1_GAP_STATUS_BLOCKING,
    decision_status=V1_GAP_DECISION_CORRECTED,
    v1_criterion_id="V1-SD-PARAMETRES-CALIBRABLES",
    benchmark_source_id="SBRUN-M012-STRATEGY-BACKTEST-0001",
    calibration_decision_id="DEC-M012-SD-REJECTED",
    evidence_command="powershell -NoProfile -ExecutionPolicy Bypass -File .\\tests\\m012\\validate_strategy_backtest_benchmark_acceptance.ps1",
    correction_command=CORRECTION_COMMAND,
    m013_green_proof="GREEN: powershell -NoProfile -ExecutionPolicy Bypass -File .\\tests\\m013\\validate_v1_gap_decisions_acceptance.ps1",
    non_acceptance_justification="Non applicable: correction prouvée par commande GREEN.",
    acceptance_impact="Ne bloque plus si le rapport final reprend la preuve GREEN.",
)
assert_equal(corrected.decision_status, V1_GAP_DECISION_CORRECTED, "Une correction explicite doit être construite.")

register = build_m013_v1_gap_decision_register()
policy.validate_register(register)
assert_equal(set(register.decisions_by_context), {"SP", "KA", "EG", "RA", "CV", "SD", "LLM", "EX"}, "Tous les écarts M-012 doivent être décidés.")
assert_equal(register.acceptance_allowed, False, "Les écarts bloquants doivent refuser l'acceptation V1.")
assert_equal(
    tuple(decision.context for decision in register.non_accepted_decisions),
    ("SP", "KA", "RA", "SD", "LLM"),
    "La liste des écarts non acceptés doit rester visible.",
)
assert any(item.decision_status == V1_GAP_DECISION_ACCEPTED for item in register.decisions), "Les écarts satisfaits doivent rester acceptés explicitement."
assert any(item.decision_status == V1_GAP_DECISION_BLOCKING for item in register.decisions), "Les écarts bloquants doivent rester visibles."

print("Tests unitaires V1GapDecisionPolicy M-013: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_v1_gap_decisions_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
try {
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $env:PYTHONIOENCODING = "utf-8"
        $output = & $pythonExecutable -B $pythonScriptPath $repoRoot 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if ($exitCode -ne 0) {
        throw "Tests unitaires V1GapDecisionPolicy M-013 invalides. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}

function Invoke-Validator {
    param(
        [Parameter(Mandatory = $true)]
        [string] $DecisionsPath,

        [Parameter(Mandatory = $true)]
        [string] $SourceGapReportPath,

        [Parameter(Mandatory = $true)]
        [string] $MatrixPath
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & powershell `
            -NoProfile `
            -ExecutionPolicy Bypass `
            -File $validatorPath `
            -DecisionsPath $DecisionsPath `
            -SourceGapReportPath $SourceGapReportPath `
            -MatrixPath $MatrixPath 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    return [pscustomobject] @{
        ExitCode = $exitCode
        Output = ($output -join "`n")
    }
}

function Assert-OutputContains {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Output,

        [Parameter(Mandatory = $true)]
        [string] $Expected,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if (-not $Output.Contains($Expected)) {
        throw "$Message Sortie obtenue: $Output"
    }
}

function New-FixtureProject {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name
    )

    $projectRoot = Join-Path $temporaryRoot $Name
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs/governance") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs/traceability") -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/governance/m013_v1_gap_decisions.md") -Destination (Join-Path $projectRoot "docs/governance/m013_v1_gap_decisions.md")
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/governance/m012_v1_gap_report.md") -Destination (Join-Path $projectRoot "docs/governance/m012_v1_gap_report.md")
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/traceability/matrix.md") -Destination (Join-Path $projectRoot "docs/traceability/matrix.md")
    return $projectRoot
}

function Assert-ValidatorFails {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name,

        [Parameter(Mandatory = $true)]
        [scriptblock] $Mutate,

        [Parameter(Mandatory = $true)]
        [string] $ExpectedMessage
    )

    $projectRoot = New-FixtureProject -Name $Name
    & $Mutate $projectRoot
    $result = Invoke-Validator `
        -DecisionsPath (Join-Path $projectRoot "docs/governance/m013_v1_gap_decisions.md") `
        -SourceGapReportPath (Join-Path $projectRoot "docs/governance/m012_v1_gap_report.md") `
        -MatrixPath (Join-Path $projectRoot "docs/traceability/matrix.md")

    if ($result.ExitCode -eq 0) {
        throw "Le cas RED $Name doit échouer."
    }

    Assert-OutputContains -Output $result.Output -Expected $ExpectedMessage -Message "Le cas RED $Name doit nommer la règle violée."
}

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
    throw "Validateur de décisions d'écarts V1 M-013 absent: scripts/validate_m013_v1_gap_decisions.ps1"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null
try {
    $validProjectRoot = New-FixtureProject -Name "valid"
    $validResult = Invoke-Validator `
        -DecisionsPath (Join-Path $validProjectRoot "docs/governance/m013_v1_gap_decisions.md") `
        -SourceGapReportPath (Join-Path $validProjectRoot "docs/governance/m012_v1_gap_report.md") `
        -MatrixPath (Join-Path $validProjectRoot "docs/traceability/matrix.md")
    if ($validResult.ExitCode -ne 0) {
        throw "La fixture valide T-003 doit réussir. Sortie: $($validResult.Output)"
    }

    Assert-ValidatorFails `
        -Name "statut-inconnu" `
        -ExpectedMessage "décision V1 inconnue" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/governance/m013_v1_gap_decisions.md"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace("| KA | différé | différé |", "| KA | différé | ouvert |") |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }

    Assert-ValidatorFails `
        -Name "sd-accepte-sans-preuve" `
        -ExpectedMessage "écart bloquant accepté" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/governance/m013_v1_gap_decisions.md"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace("| SD | bloquant | bloquant |", "| SD | bloquant | accepté |") |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }

    Assert-ValidatorFails `
        -Name "differe-sans-justification" `
        -ExpectedMessage "écart différé sans justification" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/governance/m013_v1_gap_decisions.md"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace("Recall@10 pilote sous seuil; report visible avant le rapport final V1.", "") |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }

    Assert-ValidatorFails `
        -Name "benchmark-absent" `
        -ExpectedMessage "benchmark source manque" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/governance/m013_v1_gap_decisions.md"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace("KSRUN-M012-KNOWLEDGE-0001", "") |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }

    Assert-ValidatorFails `
        -Name "decision-contredit-m012" `
        -ExpectedMessage "décision contredit M-012" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/governance/m013_v1_gap_decisions.md"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace("| RA | différé | différé |", "| RA | satisfait | différé |") |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }

    Assert-ValidatorFails `
        -Name "ecart-duplique" `
        -ExpectedMessage "écart V1 dupliqué" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/governance/m013_v1_gap_decisions.md"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace("| SP | différé | différé |", "| KA | différé | différé |") |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }

    Assert-ValidatorFails `
        -Name "critere-v1-absent" `
        -ExpectedMessage "critère V1 absent" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/governance/m013_v1_gap_decisions.md"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace("V1-KA-RECHERCHE-PAGES", "") |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }
}
finally {
    if (Test-Path -LiteralPath $temporaryRoot) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}

Write-Host "Tests unitaires du validateur décisions d'écarts V1 M-013: OK"
