$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m013_precondition.ps1"
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_precondition_unit_" + [System.Guid]::NewGuid().ToString("N"))
$expectedBranch = "codex/milestone-m013-durcissement-acceptation-v1"
$masterBranch = "master"

function New-ScriptFile {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string] $Content
    )

    $parent = Split-Path -Parent $Path
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    Set-Content -Encoding UTF8 -LiteralPath $Path -Value $Content
}

function Invoke-GitCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProjectRoot,

        [Parameter(Mandatory = $true)]
        [string[]] $Arguments
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    try {
        $output = & git -C $ProjectRoot @Arguments 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if ($exitCode -ne 0) {
        throw "Commande Git impossible dans le dépôt temporaire: git $($Arguments -join ' '). Sortie: $($output -join "`n")"
    }
}

function Get-GitOutput {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProjectRoot,

        [Parameter(Mandatory = $true)]
        [string[]] $Arguments
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    try {
        $output = & git -C $ProjectRoot @Arguments 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if ($exitCode -ne 0) {
        throw "Commande Git impossible dans le dépôt temporaire: git $($Arguments -join ' '). Sortie: $($output -join "`n")"
    }

    return ($output -join "`n").Trim()
}

function Commit-TemporaryProject {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProjectRoot,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    Invoke-GitCommand -ProjectRoot $ProjectRoot -Arguments @("-c", "core.autocrlf=false", "-c", "user.email=m013@example.test", "-c", "user.name=M013", "add", ".")
    Invoke-GitCommand -ProjectRoot $ProjectRoot -Arguments @("-c", "core.autocrlf=false", "-c", "user.email=m013@example.test", "-c", "user.name=M013", "commit", "-m", $Message)
}

function New-M013GapReport {
    return @'
# Rapport des écarts V1 M-012

## Statut des écarts V1

| Contexte | Statut | Critère V1 | Benchmark source | Corpus | Décision liée | Commande de preuve | Justification |
|---|---|---|---|---|---|---|---|
| SP | différé | Qualité documentaire. | RBRUN-M012-DOCUMENT-ROUTES-0001 | CORPUS-M012-PILOTE-0001 | DEC-M012-SP-DEFERRED | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_document_quality_calibration_acceptance.ps1 | Test scientifique RED conservé. |
| KA | différé | Recherche de connaissances. | KSRUN-M012-KNOWLEDGE-0001 | CORPUS-M012-PILOTE-0001 | DEC-M012-KA-REJECTED | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_knowledge_search_benchmark_acceptance.ps1 | Test scientifique RED conservé. |
| EG | satisfait | Gouvernance des preuves. | EGRUN-M012-0001 | CORPUS-M012-PILOTE-0001 | DEC-M012-EG-ACCEPTED | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_verified_answer_benchmark_acceptance.ps1 | Mesure satisfaite. |
| RA | différé | Réponses vérifiées. | VARUN-M012-VERIFIED-ANSWERS-0001 | CORPUS-M012-PILOTE-0001 | DEC-M012-RA-DEFERRED | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_verified_answer_benchmark_acceptance.ps1 | Test scientifique RED conservé. |
| CV | satisfait | Conversation. | CVRUN-M012-CRITERIA-0001 | CORPUS-M012-PILOTE-0001 | DEC-M012-CV-ACCEPTED | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_calibration_decisions_acceptance.ps1 | Mesure satisfaite. |
| SD | bloquant | Stratégies candidates. | SBRUN-M012-STRATEGY-BACKTEST-0001 | CORPUS-M012-PILOTE-0001 | DEC-M012-SD-REJECTED | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_strategy_backtest_benchmark_acceptance.ps1 | Test scientifique RED conservé. |
| LLM | bloquant | Promotion du checkpoint. | LLMRUN-M012-REAL-PATH-0001 | CORPUS-M012-PILOTE-0001 | DEC-M012-LLM-REJECTED | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_llm_benchmark_real_path_acceptance.ps1 | Test scientifique RED conservé. |
| EX | satisfait | Backtests pilotes. | SBRUN-M012-EXPERIMENTS-0001 | CORPUS-M012-PILOTE-0001 | DEC-M012-EX-ACCEPTED | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_strategy_backtest_benchmark_acceptance.ps1 | Mesure satisfaite. |

## Tests scientifiques RED conservés

- Test scientifique RED conservé.
'@
}

function New-TemporaryProject {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name,

        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string] $TestGateContent,

        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string] $LintGateContent,

        [Parameter(Mandatory = $true)]
        [bool] $IncludeM012Artifacts,

        [Parameter(Mandatory = $true)]
        [bool] $IncludeGapReport,

        [Parameter(Mandatory = $false)]
        [AllowEmptyString()]
        [string] $GapReportContent = ""
    )

    $projectRoot = Join-Path $temporaryRoot $Name
    New-Item -ItemType Directory -Path $projectRoot -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "scripts") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs/governance") -Force | Out-Null

    Copy-Item -LiteralPath $validatorPath -Destination (Join-Path $projectRoot "scripts/validate_m013_precondition.ps1")
    New-ScriptFile -Path (Join-Path $projectRoot "scripts/test.ps1") -Content $TestGateContent
    New-ScriptFile -Path (Join-Path $projectRoot "scripts/lint.ps1") -Content $LintGateContent
    New-ScriptFile -Path (Join-Path $projectRoot "scripts/validate_task_system.ps1") -Content "Write-Host 'Système de tâches simulé GREEN.'"

    foreach ($upstreamValidatorName in @(
        "validate_m003_precondition.ps1",
        "validate_m004_precondition.ps1",
        "validate_m005_precondition.ps1",
        "validate_m006_precondition.ps1",
        "validate_m007_precondition.ps1",
        "validate_m008_precondition.ps1",
        "validate_m009_precondition.ps1",
        "validate_m010_precondition.ps1",
        "validate_m011_precondition.ps1",
        "validate_m012_precondition.ps1"
    )) {
        New-ScriptFile `
            -Path (Join-Path $projectRoot "scripts/$upstreamValidatorName") `
            -Content "`$allowedBranches = @(`"$expectedBranch`")"
    }

    if ($IncludeM012Artifacts) {
        New-ScriptFile -Path (Join-Path $projectRoot "docs/tasks/milestone_012/0001_verifier_precondition_green.md") -Content "# M-012"
        New-ScriptFile -Path (Join-Path $projectRoot "docs/specs/m012_evaluation_pilote_calibration.md") -Content "# Spécification M-012"
        New-ScriptFile -Path (Join-Path $projectRoot "scripts/validate_m012_specification.ps1") -Content "Write-Host 'Spécification M-012 simulée GREEN.'"
        New-ScriptFile -Path (Join-Path $projectRoot "scripts/validate_m012_traceability.ps1") -Content "Write-Host 'Traçabilité M-012 simulée GREEN.'"
        New-ScriptFile -Path (Join-Path $projectRoot "tests/m012/validate_m012_precondition_acceptance.ps1") -Content "# Test M-012"
        New-ScriptFile -Path (Join-Path $projectRoot "app/evaluation/__init__.py") -Content "# EV"
        New-ScriptFile -Path (Join-Path $projectRoot "docs/traceability/matrix.md") -Content "# Matrice"
    }

    if ($IncludeGapReport) {
        $effectiveGapReportContent = $GapReportContent
        if ([string]::IsNullOrWhiteSpace($effectiveGapReportContent)) {
            $effectiveGapReportContent = New-M013GapReport
        }
        New-ScriptFile -Path (Join-Path $projectRoot "docs/governance/m012_v1_gap_report.md") -Content $effectiveGapReportContent
    }

    return $projectRoot
}

function Initialize-ProjectWithMasterAndBranch {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProjectRoot,

        [Parameter(Mandatory = $true)]
        [string] $BranchName,

        [Parameter(Mandatory = $true)]
        [bool] $DivergeMasterReference,

        [Parameter(Mandatory = $true)]
        [bool] $AdvanceMasterAfterBranch
    )

    Invoke-GitCommand -ProjectRoot $ProjectRoot -Arguments @("init", "-b", "master")
    Commit-TemporaryProject -ProjectRoot $ProjectRoot -Message "baseline m013 precondition"
    $baselineRevision = Get-GitOutput -ProjectRoot $ProjectRoot -Arguments @("rev-parse", "master")
    Invoke-GitCommand -ProjectRoot $ProjectRoot -Arguments @("update-ref", "refs/remotes/origin/master", $baselineRevision)

    if ($BranchName -ne $masterBranch) {
        Invoke-GitCommand -ProjectRoot $ProjectRoot -Arguments @("checkout", "-b", $BranchName)
    }

    if ($AdvanceMasterAfterBranch) {
        Invoke-GitCommand -ProjectRoot $ProjectRoot -Arguments @("checkout", $masterBranch)
        New-ScriptFile -Path (Join-Path $ProjectRoot "docs/tasks/master_reference_only.md") -Content "master avancé"
        Commit-TemporaryProject -ProjectRoot $ProjectRoot -Message "advance master reference"
        $advancedMasterRevision = Get-GitOutput -ProjectRoot $ProjectRoot -Arguments @("rev-parse", $masterBranch)
        Invoke-GitCommand -ProjectRoot $ProjectRoot -Arguments @("update-ref", "refs/remotes/origin/master", $advancedMasterRevision)

        if ($BranchName -ne $masterBranch) {
            Invoke-GitCommand -ProjectRoot $ProjectRoot -Arguments @("checkout", $BranchName)
        }
    }

    if ($DivergeMasterReference) {
        Invoke-GitCommand -ProjectRoot $ProjectRoot -Arguments @("checkout", "-b", "origin-master-divergent", $masterBranch)
        New-ScriptFile -Path (Join-Path $ProjectRoot "docs/tasks/origin_reference_only.md") -Content "origin master divergé"
        Commit-TemporaryProject -ProjectRoot $ProjectRoot -Message "diverge origin master reference"
        $originRevision = Get-GitOutput -ProjectRoot $ProjectRoot -Arguments @("rev-parse", "HEAD")
        Invoke-GitCommand -ProjectRoot $ProjectRoot -Arguments @("update-ref", "refs/remotes/origin/master", $originRevision)

        if ($BranchName -ne $masterBranch) {
            Invoke-GitCommand -ProjectRoot $ProjectRoot -Arguments @("checkout", $BranchName)
        }
    }
}

function Invoke-Validator {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProjectRoot
    )

    $scriptPath = Join-Path $ProjectRoot "scripts/validate_m013_precondition.ps1"
    $reportPath = Join-Path $ProjectRoot "docs/governance/m013_precondition_green.md"
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    try {
        $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $scriptPath -Path $reportPath 2>&1
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    return [pscustomobject] @{
        ExitCode = $LASTEXITCODE
        Output = ($output -join "`n")
        ReportPath = $reportPath
    }
}

function Assert-ExitCode {
    param(
        [Parameter(Mandatory = $true)]
        [int] $Actual,

        [Parameter(Mandatory = $true)]
        [int] $Expected,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if ($Actual -ne $Expected) {
        throw "$Message Code obtenu: $Actual"
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

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
    throw "Validateur de précondition M-013 absent: scripts/validate_m013_precondition.ps1"
}

$greenTestGate = @'
Write-Host "Validation GREEN: scripts/validate_traceability.ps1"
Write-Host "Validation GREEN: scripts/validate_m012_traceability.ps1"
Write-Host "Validation GREEN: scripts/validate_adr_system.ps1"
Write-Host "Test GREEN: tests/m013/validate_m013_precondition_unit.ps1"
Write-Host "Gate test GREEN: simulation M-013."
'@

$greenLintGate = @'
Write-Host "Validation GREEN: scripts/validate_traceability.ps1"
Write-Host "Validation GREEN: scripts/validate_m012_traceability.ps1"
Write-Host "Validation GREEN: scripts/validate_adr_system.ps1"
Write-Host "Gate lint GREEN: simulation M-013."
'@

$redTestGate = @'
Write-Host "Gate test RED: simulation M-013."
exit 1
'@

$emptyTestGate = @'
'@

$missingEvidenceTestGate = @'
Write-Host "Validation GREEN: scripts/validate_traceability.ps1"
Write-Host "Validation GREEN: scripts/validate_m012_traceability.ps1"
Write-Host "Gate test GREEN: simulation M-013 sans preuve ADR ni test unitaire."
'@

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    $m013BranchRoot = New-TemporaryProject -Name "m013-branch" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM012Artifacts $true -IncludeGapReport $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $m013BranchRoot -BranchName $expectedBranch -DivergeMasterReference $false -AdvanceMasterAfterBranch $false
    $m013BranchResult = Invoke-Validator -ProjectRoot $m013BranchRoot
    Assert-ExitCode -Actual $m013BranchResult.ExitCode -Expected 0 -Message "La précondition doit autoriser explicitement la branche M-013."
    Assert-OutputContains -Output $m013BranchResult.Output -Expected "Branche M-013 autorisée" -Message "La sortie doit annoncer une branche M-013 autorisée."

    $missingM012Root = New-TemporaryProject -Name "missing-m012" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM012Artifacts $false -IncludeGapReport $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $missingM012Root -BranchName $expectedBranch -DivergeMasterReference $false -AdvanceMasterAfterBranch $false
    $missingM012Result = Invoke-Validator -ProjectRoot $missingM012Root
    Assert-ExitCode -Actual $missingM012Result.ExitCode -Expected 1 -Message "La précondition doit refuser une preuve M-012 absente."
    Assert-OutputContains `
        -Output $missingM012Result.Output `
        -Expected "Milestone ou preuve amont absent de master: docs/tasks/milestone_012" `
        -Message "Le RED M-012 absent doit nommer le dossier manquant."

    $missingGapRoot = New-TemporaryProject -Name "missing-gap-report" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM012Artifacts $true -IncludeGapReport $false
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $missingGapRoot -BranchName $expectedBranch -DivergeMasterReference $false -AdvanceMasterAfterBranch $false
    $missingGapResult = Invoke-Validator -ProjectRoot $missingGapRoot
    Assert-ExitCode -Actual $missingGapResult.ExitCode -Expected 1 -Message "La précondition doit refuser un rapport V1 absent."
    Assert-OutputContains `
        -Output $missingGapResult.Output `
        -Expected "Milestone ou preuve amont absent de master: docs/governance/m012_v1_gap_report.md" `
        -Message "Le RED du rapport d'écarts V1 absent doit être explicite."

    $gapWithoutStatus = (New-M013GapReport).Replace("| SD | bloquant |", "| SD |  |")
    $gapWithoutStatusRoot = New-TemporaryProject -Name "gap-without-status" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM012Artifacts $true -IncludeGapReport $true -GapReportContent $gapWithoutStatus
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $gapWithoutStatusRoot -BranchName $expectedBranch -DivergeMasterReference $false -AdvanceMasterAfterBranch $false
    $gapWithoutStatusResult = Invoke-Validator -ProjectRoot $gapWithoutStatusRoot
    Assert-ExitCode -Actual $gapWithoutStatusResult.ExitCode -Expected 1 -Message "La précondition doit refuser un écart V1 sans statut."
    Assert-OutputContains `
        -Output $gapWithoutStatusResult.Output `
        -Expected "Écart V1 sans statut exploitable pour SD" `
        -Message "L'écart V1 sans statut doit être nommé."

    $branchBehindMasterRoot = New-TemporaryProject -Name "branch-behind-master" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM012Artifacts $true -IncludeGapReport $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $branchBehindMasterRoot -BranchName $expectedBranch -DivergeMasterReference $false -AdvanceMasterAfterBranch $true
    $branchBehindMasterResult = Invoke-Validator -ProjectRoot $branchBehindMasterRoot
    Assert-ExitCode -Actual $branchBehindMasterResult.ExitCode -Expected 1 -Message "La précondition doit refuser une branche qui ne contient pas master."
    Assert-OutputContains `
        -Output $branchBehindMasterResult.Output `
        -Expected "La branche courante ne contient pas la révision locale master." `
        -Message "La branche en retard sur master doit être explicite."

    $divergedMasterRoot = New-TemporaryProject -Name "diverged-master-reference" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM012Artifacts $true -IncludeGapReport $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $divergedMasterRoot -BranchName $expectedBranch -DivergeMasterReference $true -AdvanceMasterAfterBranch $false
    $divergedMasterResult = Invoke-Validator -ProjectRoot $divergedMasterRoot
    Assert-ExitCode -Actual $divergedMasterResult.ExitCode -Expected 1 -Message "La précondition doit refuser une référence master divergente."
    Assert-OutputContains `
        -Output $divergedMasterResult.Output `
        -Expected "Référence master divergente entre master et origin/master." `
        -Message "La divergence master doit être explicite."

    $redGateRoot = New-TemporaryProject -Name "red-gate" -TestGateContent $redTestGate -LintGateContent $greenLintGate -IncludeM012Artifacts $true -IncludeGapReport $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $redGateRoot -BranchName $expectedBranch -DivergeMasterReference $false -AdvanceMasterAfterBranch $false
    $redGateResult = Invoke-Validator -ProjectRoot $redGateRoot
    Assert-ExitCode -Actual $redGateResult.ExitCode -Expected 1 -Message "La précondition doit refuser une gate RED."
    Assert-OutputContains -Output $redGateResult.Output -Expected "Gate test RED" -Message "La sortie de gate RED doit être conservée."
    Assert-OutputContains -Output $redGateResult.Output -Expected "Gate M-013 RED: test" -Message "Le validateur doit nommer la gate RED."

    $emptyOutputRoot = New-TemporaryProject -Name "empty-test-output" -TestGateContent $emptyTestGate -LintGateContent $greenLintGate -IncludeM012Artifacts $true -IncludeGapReport $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $emptyOutputRoot -BranchName $expectedBranch -DivergeMasterReference $false -AdvanceMasterAfterBranch $false
    $emptyOutputResult = Invoke-Validator -ProjectRoot $emptyOutputRoot
    Assert-ExitCode -Actual $emptyOutputResult.ExitCode -Expected 1 -Message "La précondition doit refuser un rapport GREEN sans sorties de commande."
    Assert-OutputContains `
        -Output $emptyOutputResult.Output `
        -Expected "Gate M-013 RED: test sans sortie." `
        -Message "La sortie vide doit être nommée explicitement."

    $missingEvidenceRoot = New-TemporaryProject -Name "missing-test-evidence" -TestGateContent $missingEvidenceTestGate -LintGateContent $greenLintGate -IncludeM012Artifacts $true -IncludeGapReport $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $missingEvidenceRoot -BranchName $expectedBranch -DivergeMasterReference $false -AdvanceMasterAfterBranch $false
    $missingEvidenceResult = Invoke-Validator -ProjectRoot $missingEvidenceRoot
    Assert-ExitCode -Actual $missingEvidenceResult.ExitCode -Expected 1 -Message "La précondition doit refuser un GREEN sans preuve obligatoire."
    Assert-OutputContains `
        -Output $missingEvidenceResult.Output `
        -Expected "Gate M-013 RED: test sans preuve obligatoire" `
        -Message "Le GREEN sans preuve obligatoire doit être nommé."

    $m003RejectsM013Root = New-TemporaryProject -Name "m003-rejects-m013" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM012Artifacts $true -IncludeGapReport $true
    New-ScriptFile `
        -Path (Join-Path $m003RejectsM013Root "scripts/validate_m003_precondition.ps1") `
        -Content '$allowedBranches = @("codex/milestone-m012-evaluation-pilote-calibration")'
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $m003RejectsM013Root -BranchName $expectedBranch -DivergeMasterReference $false -AdvanceMasterAfterBranch $false
    $m003RejectsM013Result = Invoke-Validator -ProjectRoot $m003RejectsM013Root
    Assert-ExitCode -Actual $m003RejectsM013Result.ExitCode -Expected 1 -Message "La précondition doit refuser validate_m003_precondition.ps1 quand il refuse M-013."
    Assert-OutputContains `
        -Output $m003RejectsM013Result.Output `
        -Expected "Validateur amont M-003 n'accepte pas la branche M-013: scripts/validate_m003_precondition.ps1" `
        -Message "Le refus de M-013 par M-003 doit être explicite."

    $m012IgnoresM013Root = New-TemporaryProject -Name "m012-ignores-m013" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM012Artifacts $true -IncludeGapReport $true
    New-ScriptFile `
        -Path (Join-Path $m012IgnoresM013Root "scripts/validate_m012_precondition.ps1") `
        -Content '$allowedBranches = @("master")'
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $m012IgnoresM013Root -BranchName $expectedBranch -DivergeMasterReference $false -AdvanceMasterAfterBranch $false
    $m012IgnoresM013Result = Invoke-Validator -ProjectRoot $m012IgnoresM013Root
    Assert-ExitCode -Actual $m012IgnoresM013Result.ExitCode -Expected 1 -Message "La précondition doit refuser un validateur amont qui ignore M-013."
    Assert-OutputContains `
        -Output $m012IgnoresM013Result.Output `
        -Expected "Validateur amont M-012 n'accepte pas la branche M-013: scripts/validate_m012_precondition.ps1" `
        -Message "L'acceptation amont manquante doit être explicite."
}
finally {
    $resolvedTemporaryRoot = [System.IO.Path]::GetFullPath($temporaryRoot)
    $resolvedSystemTemp = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
    if ($resolvedTemporaryRoot.StartsWith($resolvedSystemTemp, [System.StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath $temporaryRoot -PathType Container)) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}

Write-Host "Tests unitaires du validateur de précondition M-013: OK"
