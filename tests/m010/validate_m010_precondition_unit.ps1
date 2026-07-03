$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m010_precondition.ps1"
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m010_precondition_unit_" + [System.Guid]::NewGuid().ToString("N"))
$expectedBranch = "codex/milestone-m010-strategie-candidate-attribuee"
$masterBranch = "master"
$invalidBranch = "codex/milestone-hors-contrat"

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

    Invoke-GitCommand -ProjectRoot $ProjectRoot -Arguments @("-c", "core.autocrlf=false", "-c", "user.email=m010@example.test", "-c", "user.name=M010", "add", ".")
    Invoke-GitCommand -ProjectRoot $ProjectRoot -Arguments @("-c", "core.autocrlf=false", "-c", "user.email=m010@example.test", "-c", "user.name=M010", "commit", "-m", $Message)
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
        [bool] $IncludeM009Artifacts
    )

    $projectRoot = Join-Path $temporaryRoot $Name
    New-Item -ItemType Directory -Path $projectRoot -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "scripts") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs/governance") -Force | Out-Null

    Copy-Item -LiteralPath $validatorPath -Destination (Join-Path $projectRoot "scripts/validate_m010_precondition.ps1")
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
        "validate_m009_precondition.ps1"
    )) {
        New-ScriptFile `
            -Path (Join-Path $projectRoot "scripts/$upstreamValidatorName") `
            -Content "`$allowedBranches = @(`"$expectedBranch`")"
    }

    if ($IncludeM009Artifacts) {
        New-ScriptFile -Path (Join-Path $projectRoot "docs/tasks/milestone_009/0001_verifier_precondition_green.md") -Content "# M-009"
        New-ScriptFile -Path (Join-Path $projectRoot "docs/specs/m009_recherche_approfondie_multi_sources.md") -Content "# Spécification M-009"
        New-ScriptFile -Path (Join-Path $projectRoot "scripts/validate_m009_specification.ps1") -Content "Write-Host 'Spécification M-009 simulée GREEN.'"
        New-ScriptFile -Path (Join-Path $projectRoot "tests/m009/validate_m009_precondition_acceptance.ps1") -Content "# Test M-009"
        New-ScriptFile -Path (Join-Path $projectRoot "app/research_answering/__init__.py") -Content "# RA"
        New-ScriptFile -Path (Join-Path $projectRoot "app/strategy_design/adapters/research_outcome_translator.py") -Content "# Traduction RA vers SD"
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
    Commit-TemporaryProject -ProjectRoot $ProjectRoot -Message "baseline m010 precondition"
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
        [string] $ProjectRoot,

        [Parameter(Mandatory = $false)]
        [string] $ReportPathOverride,

        [Parameter(Mandatory = $false)]
        [int] $GateTimeoutSeconds
    )

    $scriptPath = Join-Path $ProjectRoot "scripts/validate_m010_precondition.ps1"
    if ([string]::IsNullOrWhiteSpace($ReportPathOverride)) {
        $reportPath = Join-Path $ProjectRoot "docs/governance/m010_precondition_green.md"
    }
    else {
        $reportPath = $ReportPathOverride
    }

    $arguments = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $scriptPath, "-Path", $reportPath)
    if ($GateTimeoutSeconds -gt 0) {
        $arguments += @("-GateTimeoutSeconds", [string] $GateTimeoutSeconds)
    }

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    try {
        $output = & powershell @arguments 2>&1
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
    throw "Validateur de précondition M-010 absent: scripts/validate_m010_precondition.ps1"
}

$greenTestGate = @'
Write-Host "Validation GREEN: scripts/validate_traceability.ps1"
Write-Host "Validation GREEN: scripts/validate_adr_system.ps1"
Write-Host "Validation GREEN: scripts/validate_architecture_boundaries.ps1"
Write-Host "Test GREEN: tests/m003/validate_m003_precondition_acceptance.ps1"
Write-Host "Test GREEN: tests/m009/validate_m009_precondition_acceptance.ps1"
Write-Host "Test GREEN: tests/m010/validate_m010_precondition_unit.ps1"
Write-Host "Gate test GREEN: simulation M-010."
'@

$greenLintGate = @'
Write-Host "Validation GREEN: scripts/validate_traceability.ps1"
Write-Host "Validation GREEN: scripts/validate_adr_system.ps1"
Write-Host "Validation GREEN: scripts/validate_architecture_boundaries.ps1"
Write-Host "Gate lint GREEN: simulation M-010."
'@

$redTestGate = @'
Write-Host "Gate test RED: simulation M-010."
exit 1
'@

$emptyTestGate = @'
'@

$slowTestGate = @'
Write-Host "Gate test non concluant: simulation M-010."
Start-Sleep -Seconds 3
Write-Host "Sortie tardive interdite."
'@

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    $m010BranchRoot = New-TemporaryProject -Name "m010-branch" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM009Artifacts $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $m010BranchRoot -BranchName $expectedBranch -DivergeMasterReference $false -AdvanceMasterAfterBranch $false
    $m010BranchResult = Invoke-Validator -ProjectRoot $m010BranchRoot
    Assert-ExitCode -Actual $m010BranchResult.ExitCode -Expected 0 -Message "La précondition doit autoriser explicitement la branche M-010."
    Assert-OutputContains -Output $m010BranchResult.Output -Expected "Branche M-010 autorisée" -Message "La sortie doit annoncer une branche M-010 autorisée."
    Assert-OutputContains -Output $m010BranchResult.Output -Expected $expectedBranch -Message "La branche M-010 doit être nommée."

    $masterBranchRoot = New-TemporaryProject -Name "master-branch" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM009Artifacts $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $masterBranchRoot -BranchName $masterBranch -DivergeMasterReference $false -AdvanceMasterAfterBranch $false
    $masterBranchResult = Invoke-Validator -ProjectRoot $masterBranchRoot
    Assert-ExitCode -Actual $masterBranchResult.ExitCode -Expected 0 -Message "La précondition doit autoriser explicitement master."
    Assert-OutputContains -Output $masterBranchResult.Output -Expected "Branche M-010 autorisée: master" -Message "La branche master autorisée doit être nommée."

    $missingM009Root = New-TemporaryProject -Name "missing-m009" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM009Artifacts $false
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $missingM009Root -BranchName $expectedBranch -DivergeMasterReference $false -AdvanceMasterAfterBranch $false
    $missingM009Result = Invoke-Validator -ProjectRoot $missingM009Root
    Assert-ExitCode -Actual $missingM009Result.ExitCode -Expected 1 -Message "La précondition doit refuser une preuve M-009 absente."
    Assert-OutputContains `
        -Output $missingM009Result.Output `
        -Expected "Milestone ou preuve amont absent de master: docs/tasks/milestone_009" `
        -Message "Le RED M-009 absent doit nommer le dossier manquant."

    $missingTranslatorRoot = New-TemporaryProject -Name "missing-ra-sd-translator" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM009Artifacts $true
    Remove-Item -LiteralPath (Join-Path $missingTranslatorRoot "app/strategy_design/adapters/research_outcome_translator.py") -Force
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $missingTranslatorRoot -BranchName $expectedBranch -DivergeMasterReference $false -AdvanceMasterAfterBranch $false
    $missingTranslatorResult = Invoke-Validator -ProjectRoot $missingTranslatorRoot
    Assert-ExitCode -Actual $missingTranslatorResult.ExitCode -Expected 1 -Message "La précondition doit refuser le langage RA vers SD absent."
    Assert-OutputContains `
        -Output $missingTranslatorResult.Output `
        -Expected "Milestone ou preuve amont absent de master: app/strategy_design/adapters/research_outcome_translator.py" `
        -Message "Le RED adaptateur RA vers SD absent doit nommer le fichier manquant."

    $divergedMasterRoot = New-TemporaryProject -Name "diverged-master-reference" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM009Artifacts $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $divergedMasterRoot -BranchName $expectedBranch -DivergeMasterReference $true -AdvanceMasterAfterBranch $false
    $divergedMasterResult = Invoke-Validator -ProjectRoot $divergedMasterRoot
    Assert-ExitCode -Actual $divergedMasterResult.ExitCode -Expected 1 -Message "La précondition doit refuser une référence master divergente."
    Assert-OutputContains `
        -Output $divergedMasterResult.Output `
        -Expected "Référence master divergente entre master et origin/master." `
        -Message "La divergence master doit être explicite."

    $branchBehindMasterRoot = New-TemporaryProject -Name "branch-behind-master" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM009Artifacts $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $branchBehindMasterRoot -BranchName $expectedBranch -DivergeMasterReference $false -AdvanceMasterAfterBranch $true
    $branchBehindMasterResult = Invoke-Validator -ProjectRoot $branchBehindMasterRoot
    Assert-ExitCode -Actual $branchBehindMasterResult.ExitCode -Expected 1 -Message "La précondition doit refuser une branche qui ne contient pas master."
    Assert-OutputContains `
        -Output $branchBehindMasterResult.Output `
        -Expected "La branche courante ne contient pas la révision locale master." `
        -Message "La branche en retard sur master doit être explicite."

    $invalidBranchRoot = New-TemporaryProject -Name "invalid-branch" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM009Artifacts $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $invalidBranchRoot -BranchName $invalidBranch -DivergeMasterReference $false -AdvanceMasterAfterBranch $false
    $invalidBranchResult = Invoke-Validator -ProjectRoot $invalidBranchRoot
    Assert-ExitCode -Actual $invalidBranchResult.ExitCode -Expected 1 -Message "La précondition doit refuser une branche non autorisée."
    Assert-OutputContains `
        -Output $invalidBranchResult.Output `
        -Expected "Branche courante invalide. Autorisées:" `
        -Message "La branche non autorisée doit être nommée explicitement."
    Assert-OutputContains -Output $invalidBranchResult.Output -Expected $expectedBranch -Message "La branche M-010 autorisée doit être listée."
    Assert-OutputContains -Output $invalidBranchResult.Output -Expected $invalidBranch -Message "La branche refusée doit être nommée."

    $redGateRoot = New-TemporaryProject -Name "red-gate" -TestGateContent $redTestGate -LintGateContent $greenLintGate -IncludeM009Artifacts $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $redGateRoot -BranchName $expectedBranch -DivergeMasterReference $false -AdvanceMasterAfterBranch $false
    $redGateResult = Invoke-Validator -ProjectRoot $redGateRoot
    Assert-ExitCode -Actual $redGateResult.ExitCode -Expected 1 -Message "La précondition doit refuser une gate RED."
    Assert-OutputContains -Output $redGateResult.Output -Expected "Gate test RED" -Message "La sortie de gate RED doit être conservée."
    Assert-OutputContains -Output $redGateResult.Output -Expected "Gate M-010 RED: test" -Message "Le validateur doit nommer la gate RED."

    $emptyOutputRoot = New-TemporaryProject -Name "empty-test-output" -TestGateContent $emptyTestGate -LintGateContent $greenLintGate -IncludeM009Artifacts $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $emptyOutputRoot -BranchName $expectedBranch -DivergeMasterReference $false -AdvanceMasterAfterBranch $false
    $emptyOutputResult = Invoke-Validator -ProjectRoot $emptyOutputRoot
    Assert-ExitCode -Actual $emptyOutputResult.ExitCode -Expected 1 -Message "La précondition doit refuser un statut GREEN déclaré sans preuve."
    Assert-OutputContains `
        -Output $emptyOutputResult.Output `
        -Expected "Gate M-010 RED: test sans sortie." `
        -Message "La sortie vide doit être nommée explicitement."

    $timeoutGateRoot = New-TemporaryProject -Name "timeout-test-output" -TestGateContent $slowTestGate -LintGateContent $greenLintGate -IncludeM009Artifacts $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $timeoutGateRoot -BranchName $expectedBranch -DivergeMasterReference $false -AdvanceMasterAfterBranch $false
    $timeoutGateResult = Invoke-Validator -ProjectRoot $timeoutGateRoot -GateTimeoutSeconds 1
    Assert-ExitCode -Actual $timeoutGateResult.ExitCode -Expected 1 -Message "La précondition doit refuser un scripts/test.ps1 non concluant."
    Assert-OutputContains `
        -Output $timeoutGateResult.Output `
        -Expected "Gate M-010 RED: test non concluant après 1 seconde(s)." `
        -Message "Le timeout doit être nommé explicitement."

    $m003RejectsM010Root = New-TemporaryProject -Name "m003-rejects-m010" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM009Artifacts $true
    New-ScriptFile `
        -Path (Join-Path $m003RejectsM010Root "scripts/validate_m003_precondition.ps1") `
        -Content '$allowedBranches = @("codex/milestone-m009-recherche-approfondie")'
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $m003RejectsM010Root -BranchName $expectedBranch -DivergeMasterReference $false -AdvanceMasterAfterBranch $false
    $m003RejectsM010Result = Invoke-Validator -ProjectRoot $m003RejectsM010Root
    Assert-ExitCode -Actual $m003RejectsM010Result.ExitCode -Expected 1 -Message "La précondition doit refuser validate_m003_precondition.ps1 quand il refuse M-010."
    Assert-OutputContains `
        -Output $m003RejectsM010Result.Output `
        -Expected "Validateur amont M-003 n'accepte pas la branche M-010: scripts/validate_m003_precondition.ps1" `
        -Message "Le refus de M-010 par M-003 doit être explicite."

    $missingUpstreamRoot = New-TemporaryProject -Name "missing-upstream-acceptance" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM009Artifacts $true
    New-ScriptFile `
        -Path (Join-Path $missingUpstreamRoot "scripts/validate_m009_precondition.ps1") `
        -Content '$allowedBranches = @("master")'
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $missingUpstreamRoot -BranchName $expectedBranch -DivergeMasterReference $false -AdvanceMasterAfterBranch $false
    $missingUpstreamResult = Invoke-Validator -ProjectRoot $missingUpstreamRoot
    Assert-ExitCode -Actual $missingUpstreamResult.ExitCode -Expected 1 -Message "La précondition doit refuser un validateur amont qui ignore M-010."
    Assert-OutputContains `
        -Output $missingUpstreamResult.Output `
        -Expected "Validateur amont M-009 n'accepte pas la branche M-010: scripts/validate_m009_precondition.ps1" `
        -Message "L'acceptation amont manquante doit être explicite."

    $outsideReportRoot = New-TemporaryProject -Name "outside-report-path" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM009Artifacts $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $outsideReportRoot -BranchName $expectedBranch -DivergeMasterReference $false -AdvanceMasterAfterBranch $false
    $outsideReportPath = Join-Path $temporaryRoot "m010_precondition_outside.md"
    $outsideReportResult = Invoke-Validator -ProjectRoot $outsideReportRoot -ReportPathOverride $outsideReportPath
    Assert-ExitCode -Actual $outsideReportResult.ExitCode -Expected 1 -Message "La précondition doit refuser un rapport hors dépôt."
    Assert-OutputContains `
        -Output $outsideReportResult.Output `
        -Expected "Chemin de rapport M-010 hors dépôt:" `
        -Message "Le chemin hors dépôt doit être nommé explicitement."
}
finally {
    $resolvedTemporaryRoot = [System.IO.Path]::GetFullPath($temporaryRoot)
    $resolvedSystemTemp = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
    if ($resolvedTemporaryRoot.StartsWith($resolvedSystemTemp, [System.StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath $temporaryRoot -PathType Container)) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}

Write-Host "Tests unitaires du validateur de précondition M-010: OK"
