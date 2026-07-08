$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom

$validatorPath = Join-Path $repoRoot "scripts/validate_m013_acceptance.ps1"
$temporaryRoot = Join-Path $repoRoot (".tmp_m013_acceptance_report_unit_" + [System.Guid]::NewGuid().ToString("N"))

$pythonCode = @'
import sys

repo_root = sys.argv[1]
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from app.evaluation.domain.v1_acceptance_report import (
    V1_ACCEPTANCE_REPORT_POLICY_VERSION,
    V1_ACCEPTANCE_STATUS_ACCEPTED,
    V1_ACCEPTANCE_STATUS_BLOCKING,
    V1_ACCEPTANCE_STATUS_DEFERRED,
    V1_ACCEPTANCE_STATUS_REJECTED,
    V1AcceptanceCriterionVerdict,
    V1AcceptanceFinalGate,
    V1AcceptanceReportPolicy,
    build_m013_v1_acceptance_report,
)


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


COMMAND = "powershell -NoProfile -ExecutionPolicy Bypass -File .\\tests\\m013\\validate_m013_specification_acceptance.ps1"


def criterion(**overrides):
    payload = {
        "criterion_id": "V1-EG-GOUVERNANCE-PREUVES",
        "context": "EG",
        "verdict": V1_ACCEPTANCE_STATUS_ACCEPTED,
        "evidence_artifact": "docs/governance/m013_v1_gap_decisions.md",
        "evidence_command": COMMAND,
        "adr_refs": ("ADR-010", "DDD-ADR-011"),
        "gap_status": "satisfait",
        "decision": "accepté",
        "final_impact": "Ne bloque pas l'acceptation V1.",
    }
    payload.update(overrides)
    return V1AcceptanceCriterionVerdict(**payload)


def final_gate(**overrides):
    payload = {
        "gate_id": "GATE-M013-UNIT",
        "command": COMMAND,
        "status": "GREEN",
        "evidence_artifact": "docs/governance/m013_v1_acceptance_report.md",
    }
    payload.update(overrides)
    return V1AcceptanceFinalGate(**payload)


# Given les décisions M-013 contiennent des critères satisfaits, différés et bloquants.
# When V1AcceptanceReportPolicy publie le rapport final.
# Then chaque critère possède verdict, preuve, ADR et commande, et tout bloquant
# refuse le verdict acceptée.
policy = V1AcceptanceReportPolicy(policy_version=V1_ACCEPTANCE_REPORT_POLICY_VERSION)
assert_raises("critère V1 absent", lambda: criterion(criterion_id=""))
assert_raises("verdict V1 inconnu", lambda: criterion(verdict="ouvert"))
assert_raises("preuve par verdict absente", lambda: criterion(evidence_artifact=""))
assert_raises("commande finale absente", lambda: criterion(evidence_command=""))
assert_raises("ADR reliée absente", lambda: criterion(adr_refs=()))
assert_raises("écart bloquant accepté", lambda: criterion(gap_status="bloquant", verdict=V1_ACCEPTANCE_STATUS_ACCEPTED))
assert_raises("écart différé accepté sans décision", lambda: criterion(gap_status="différé", verdict=V1_ACCEPTANCE_STATUS_ACCEPTED, decision="différé"))
assert_raises("contexte V1 incohérent", lambda: criterion(criterion_id="V1-SP-QUALITE-DOCUMENTAIRE", context="KA"))
assert_raises("statut de gate finale inconnu", lambda: final_gate(status="UNKNOWN"))
assert_raises("commande finale absente", lambda: final_gate(command=""))

report = build_m013_v1_acceptance_report()
policy.validate_report(report)
assert_equal(len(report.criteria), 8, "Tous les critères V1 doivent être couverts.")
assert_equal(tuple(item.context for item in report.non_accepted_gaps), ("SP", "KA", "RA", "SD", "LLM"), "Les écarts non acceptés doivent rester visibles.")
assert_equal(tuple(item.context for item in report.blocking_gaps), ("SD", "LLM"), "Les bloquants doivent rester visibles.")
assert_equal(report.final_verdict, V1_ACCEPTANCE_STATUS_REJECTED, "Le verdict final doit refuser l'acceptation.")
assert_equal(report.acceptance_allowed, False, "L'acceptation V1 doit être refusée.")
assert any(item.verdict == V1_ACCEPTANCE_STATUS_DEFERRED for item in report.criteria), "Un verdict différé doit rester distingué."
assert any(item.verdict == V1_ACCEPTANCE_STATUS_BLOCKING for item in report.criteria), "Un verdict bloquant doit rester distingué."
assert any(item.verdict == V1_ACCEPTANCE_STATUS_ACCEPTED for item in report.criteria), "Les critères satisfaits doivent rester acceptés explicitement."

assert_raises(
    "critère V1 absent: V1-LLM-CHECKPOINT-PRINCIPAL",
    lambda: policy.publish_report(
        report_id="REPORT-M013-INCOMPLET",
        specification_version="docs/specs/m013_durcissement_acceptation_v1.md",
        criteria=tuple(item for item in report.criteria if item.criterion_id != "V1-LLM-CHECKPOINT-PRINCIPAL"),
        final_gates=report.final_gates,
        traceability_requirement_id="REQ-M013-012",
        definition_of_done_ref="docs/governance/definition_of_done.md",
    ),
)
accepted_report = policy.publish_report(
    report_id="REPORT-M013-ACCEPTE",
    specification_version="docs/specs/m013_durcissement_acceptation_v1.md",
    criteria=tuple(
        criterion(
            criterion_id=item.criterion_id,
            context=item.context,
            verdict=V1_ACCEPTANCE_STATUS_ACCEPTED,
            evidence_artifact=item.evidence_artifact,
            evidence_command=item.evidence_command,
            adr_refs=item.adr_refs,
            gap_status="satisfait",
            decision="accepté",
            final_impact="Critère V1 satisfait et accepté.",
        )
        for item in report.criteria
    ),
    final_gates=tuple(
        final_gate(
            gate_id=item.gate_id,
            command=item.command,
            status="GREEN",
            evidence_artifact=item.evidence_artifact,
        )
        for item in report.final_gates
    ),
    traceability_requirement_id="REQ-M013-012",
    definition_of_done_ref="docs/governance/definition_of_done.md",
)
policy.validate_report(accepted_report)
assert_equal(accepted_report.final_verdict, V1_ACCEPTANCE_STATUS_ACCEPTED, "Un rapport sans écart et avec gates GREEN doit être accepté.")
assert_equal(accepted_report.acceptance_allowed, True, "La politique ne doit pas imposer d'écart non accepté durable.")

print("Tests unitaires V1AcceptanceReportPolicy M-013: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_acceptance_report_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Tests unitaires V1AcceptanceReportPolicy M-013 invalides. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}

function Invoke-Validator {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProjectRoot
    )

    $reportPath = Join-Path $ProjectRoot "docs/governance/m013_v1_acceptance_report.md"
    $matrixPath = Join-Path $ProjectRoot "docs/traceability/matrix.md"
    $testGatePath = Join-Path $ProjectRoot "scripts/test.ps1"
    $lintGatePath = Join-Path $ProjectRoot "scripts/lint.ps1"

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & powershell `
            -NoProfile `
            -ExecutionPolicy Bypass `
            -File $validatorPath `
            -ReportPath $reportPath `
            -MatrixPath $matrixPath `
            -TestGatePath $testGatePath `
            -LintGatePath $lintGatePath 2>&1
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
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "scripts") -Force | Out-Null

    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/governance/m013_v1_acceptance_report.md") -Destination (Join-Path $projectRoot "docs/governance/m013_v1_acceptance_report.md")
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/traceability/matrix.md") -Destination (Join-Path $projectRoot "docs/traceability/matrix.md")
    Copy-Item -LiteralPath (Join-Path $repoRoot "scripts/test.ps1") -Destination (Join-Path $projectRoot "scripts/test.ps1")
    Copy-Item -LiteralPath (Join-Path $repoRoot "scripts/lint.ps1") -Destination (Join-Path $projectRoot "scripts/lint.ps1")

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
    $result = Invoke-Validator -ProjectRoot $projectRoot

    if ($result.ExitCode -eq 0) {
        throw "Le cas RED $Name doit échouer."
    }

    Assert-OutputContains `
        -Output $result.Output `
        -Expected $ExpectedMessage `
        -Message "Le cas RED $Name doit nommer la règle violée."
}

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
    throw "Validateur rapport d'acceptation V1 M-013 absent: scripts/validate_m013_acceptance.ps1"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null
try {
    $validProjectRoot = New-FixtureProject -Name "valid"
    $validResult = Invoke-Validator -ProjectRoot $validProjectRoot
    if ($validResult.ExitCode -ne 0) {
        throw "La fixture valide T-012 doit réussir. Sortie: $($validResult.Output)"
    }
    Assert-OutputContains `
        -Output $validResult.Output `
        -Expected "Rapport d'acceptation V1 M-013 valide" `
        -Message "La fixture valide doit annoncer le GREEN T-012."

    Assert-ValidatorFails `
        -Name "critere-absent" `
        -ExpectedMessage "critère V1 absent: V1-CV-CONVERSATION-PRODUIT" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/governance/m013_v1_acceptance_report.md"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace("| V1-CV-CONVERSATION-PRODUIT | CV | accepté |", "| V1-CV-CONVERSATION-ABSENT | CV | accepté |") |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }

    Assert-ValidatorFails `
        -Name "preuve-absente" `
        -ExpectedMessage "preuve par verdict absente: V1-EG-GOUVERNANCE-PREUVES" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/governance/m013_v1_acceptance_report.md"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace("docs/governance/m013_v1_gap_decisions.md", "") |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }

    Assert-ValidatorFails `
        -Name "bloquant-accepte" `
        -ExpectedMessage "écart bloquant accepté: V1-SD-PARAMETRES-CALIBRABLES" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/governance/m013_v1_acceptance_report.md"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace("| V1-SD-PARAMETRES-CALIBRABLES | SD | bloquant |", "| V1-SD-PARAMETRES-CALIBRABLES | SD | accepté |") |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }

    Assert-ValidatorFails `
        -Name "commande-finale-absente" `
        -ExpectedMessage "commande finale absente: scripts/validate_m013_acceptance.ps1" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/governance/m013_v1_acceptance_report.md"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace("powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_acceptance.ps1", "") |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }

    Assert-ValidatorFails `
        -Name "secret-documente" `
        -ExpectedMessage "Secret interdit dans le rapport d'acceptation V1 M-013" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/governance/m013_v1_acceptance_report.md"
            Add-Content -Encoding UTF8 -LiteralPath $path -Value "`nAuthorization: Bearer SECRET_INTERDIT_M013"
        }

    Assert-ValidatorFails `
        -Name "traceabilite-absente" `
        -ExpectedMessage "Traçabilité T-012 absente: REQ-M013-012" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/traceability/matrix.md"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace("REQ-M013-012", "REQ-M013-XXX") |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }
}
finally {
    if (Test-Path -LiteralPath $temporaryRoot) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}

Write-Host "Tests unitaires du validateur rapport d'acceptation V1 M-013: OK"
