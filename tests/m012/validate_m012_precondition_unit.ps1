$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m012_precondition.ps1"
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m012_precondition_unit_" + [System.Guid]::NewGuid().ToString("N"))
$expectedBranch = "codex/milestone-m012-evaluation-pilote-calibration"
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

    Invoke-GitCommand -ProjectRoot $ProjectRoot -Arguments @("-c", "core.autocrlf=false", "-c", "user.email=m012@example.test", "-c", "user.name=M012", "add", ".")
    Invoke-GitCommand -ProjectRoot $ProjectRoot -Arguments @("-c", "core.autocrlf=false", "-c", "user.email=m012@example.test", "-c", "user.name=M012", "commit", "-m", $Message)
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
        [bool] $IncludeM011Artifacts
    )

    $projectRoot = Join-Path $temporaryRoot $Name
    New-Item -ItemType Directory -Path $projectRoot -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "scripts") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs/governance") -Force | Out-Null

    Copy-Item -LiteralPath $validatorPath -Destination (Join-Path $projectRoot "scripts/validate_m012_precondition.ps1")
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
        "validate_m011_precondition.ps1"
    )) {
        New-ScriptFile `
            -Path (Join-Path $projectRoot "scripts/$upstreamValidatorName") `
            -Content "`$allowedBranches = @(`"$expectedBranch`")"
    }

    if ($IncludeM011Artifacts) {
        New-ScriptFile -Path (Join-Path $projectRoot "docs/tasks/milestone_011/0001_verifier_precondition_green.md") -Content "# M-011"
        New-ScriptFile -Path (Join-Path $projectRoot "docs/specs/m011_experience_reproductible.md") -Content "# Spécification M-011"
        New-ScriptFile -Path (Join-Path $projectRoot "scripts/validate_m011_specification.ps1") -Content "Write-Host 'Spécification M-011 simulée GREEN.'"
        New-ScriptFile -Path (Join-Path $projectRoot "scripts/validate_m011_traceability.ps1") -Content "Write-Host 'Traçabilité M-011 simulée GREEN.'"
        New-ScriptFile -Path (Join-Path $projectRoot "tests/m011/validate_m011_precondition_acceptance.ps1") -Content "# Test M-011"
        New-ScriptFile -Path (Join-Path $projectRoot "app/experimentation/__init__.py") -Content "# EX"
        New-ScriptFile -Path (Join-Path $projectRoot "app/contracts/strategy_experiments.py") -Content "# Contrats SD/EX"
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
    Commit-TemporaryProject -ProjectRoot $ProjectRoot -Message "baseline m012 precondition"
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
        [int] $GateTimeoutSeconds
    )

    $scriptPath = Join-Path $ProjectRoot "scripts/validate_m012_precondition.ps1"
    $reportPath = Join-Path $ProjectRoot "docs/governance/m012_precondition_green.md"
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
    throw "Validateur de précondition M-012 absent: scripts/validate_m012_precondition.ps1"
}

$greenTestGate = @'
Write-Host "Validation GREEN: scripts/validate_traceability.ps1"
Write-Host "Validation GREEN: scripts/validate_adr_system.ps1"
Write-Host "Validation GREEN: scripts/validate_architecture_boundaries.ps1"
Write-Host "Test GREEN: tests/m012/validate_m012_precondition_unit.ps1"
Write-Host "Gate test GREEN: simulation M-012."
'@

$greenLintGate = @'
Write-Host "Validation GREEN: scripts/validate_traceability.ps1"
Write-Host "Validation GREEN: scripts/validate_adr_system.ps1"
Write-Host "Validation GREEN: scripts/validate_architecture_boundaries.ps1"
Write-Host "Gate lint GREEN: simulation M-012."
'@

$redTestGate = @'
Write-Host "Gate test RED: simulation M-012."
exit 1
'@

$emptyTestGate = @'
'@

$slowTestGate = @'
Write-Host "Gate test non concluant: simulation M-012."
Start-Sleep -Seconds 3
Write-Host "Sortie tardive interdite."
'@

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    $m012BranchRoot = New-TemporaryProject -Name "m012-branch" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM011Artifacts $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $m012BranchRoot -BranchName $expectedBranch -DivergeMasterReference $false -AdvanceMasterAfterBranch $false
    $m012BranchResult = Invoke-Validator -ProjectRoot $m012BranchRoot
    Assert-ExitCode -Actual $m012BranchResult.ExitCode -Expected 0 -Message "La précondition doit autoriser explicitement la branche M-012."
    Assert-OutputContains -Output $m012BranchResult.Output -Expected "Branche M-012 autorisée" -Message "La sortie doit annoncer une branche M-012 autorisée."

    $missingM011Root = New-TemporaryProject -Name "missing-m011" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM011Artifacts $false
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $missingM011Root -BranchName $expectedBranch -DivergeMasterReference $false -AdvanceMasterAfterBranch $false
    $missingM011Result = Invoke-Validator -ProjectRoot $missingM011Root
    Assert-ExitCode -Actual $missingM011Result.ExitCode -Expected 1 -Message "La précondition doit refuser une preuve M-011 absente."
    Assert-OutputContains `
        -Output $missingM011Result.Output `
        -Expected "Milestone ou preuve amont absent de master: docs/tasks/milestone_011" `
        -Message "Le RED M-011 absent doit nommer le dossier manquant."

    $branchBehindMasterRoot = New-TemporaryProject -Name "branch-behind-master" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM011Artifacts $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $branchBehindMasterRoot -BranchName $expectedBranch -DivergeMasterReference $false -AdvanceMasterAfterBranch $true
    $branchBehindMasterResult = Invoke-Validator -ProjectRoot $branchBehindMasterRoot
    Assert-ExitCode -Actual $branchBehindMasterResult.ExitCode -Expected 1 -Message "La précondition doit refuser une branche qui ne contient pas master."
    Assert-OutputContains `
        -Output $branchBehindMasterResult.Output `
        -Expected "La branche courante ne contient pas la révision locale master." `
        -Message "La branche en retard sur master doit être explicite."

    $divergedMasterRoot = New-TemporaryProject -Name "diverged-master-reference" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM011Artifacts $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $divergedMasterRoot -BranchName $expectedBranch -DivergeMasterReference $true -AdvanceMasterAfterBranch $false
    $divergedMasterResult = Invoke-Validator -ProjectRoot $divergedMasterRoot
    Assert-ExitCode -Actual $divergedMasterResult.ExitCode -Expected 1 -Message "La précondition doit refuser une référence master divergente."
    Assert-OutputContains `
        -Output $divergedMasterResult.Output `
        -Expected "Référence master divergente entre master et origin/master." `
        -Message "La divergence master doit être explicite."

    $redGateRoot = New-TemporaryProject -Name "red-gate" -TestGateContent $redTestGate -LintGateContent $greenLintGate -IncludeM011Artifacts $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $redGateRoot -BranchName $expectedBranch -DivergeMasterReference $false -AdvanceMasterAfterBranch $false
    $redGateResult = Invoke-Validator -ProjectRoot $redGateRoot
    Assert-ExitCode -Actual $redGateResult.ExitCode -Expected 1 -Message "La précondition doit refuser une gate RED."
    Assert-OutputContains -Output $redGateResult.Output -Expected "Gate test RED" -Message "La sortie de gate RED doit être conservée."
    Assert-OutputContains -Output $redGateResult.Output -Expected "Gate M-012 RED: test" -Message "Le validateur doit nommer la gate RED."

    $emptyOutputRoot = New-TemporaryProject -Name "empty-test-output" -TestGateContent $emptyTestGate -LintGateContent $greenLintGate -IncludeM011Artifacts $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $emptyOutputRoot -BranchName $expectedBranch -DivergeMasterReference $false -AdvanceMasterAfterBranch $false
    $emptyOutputResult = Invoke-Validator -ProjectRoot $emptyOutputRoot
    Assert-ExitCode -Actual $emptyOutputResult.ExitCode -Expected 1 -Message "La précondition doit refuser un rapport GREEN sans sorties de commande."
    Assert-OutputContains `
        -Output $emptyOutputResult.Output `
        -Expected "Gate M-012 RED: test sans sortie." `
        -Message "La sortie vide doit être nommée explicitement."

    $timeoutGateRoot = New-TemporaryProject -Name "timeout-test-output" -TestGateContent $slowTestGate -LintGateContent $greenLintGate -IncludeM011Artifacts $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $timeoutGateRoot -BranchName $expectedBranch -DivergeMasterReference $false -AdvanceMasterAfterBranch $false
    $timeoutGateResult = Invoke-Validator -ProjectRoot $timeoutGateRoot -GateTimeoutSeconds 1
    Assert-ExitCode -Actual $timeoutGateResult.ExitCode -Expected 1 -Message "La précondition doit refuser un scripts/test.ps1 non concluant."
    Assert-OutputContains `
        -Output $timeoutGateResult.Output `
        -Expected "Gate M-012 RED: test non concluant après 1 seconde(s)." `
        -Message "Le timeout doit être nommé explicitement."

    $m003RejectsM012Root = New-TemporaryProject -Name "m003-rejects-m012" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM011Artifacts $true
    New-ScriptFile `
        -Path (Join-Path $m003RejectsM012Root "scripts/validate_m003_precondition.ps1") `
        -Content '$allowedBranches = @("codex/milestone-m011-experience-reproductible")'
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $m003RejectsM012Root -BranchName $expectedBranch -DivergeMasterReference $false -AdvanceMasterAfterBranch $false
    $m003RejectsM012Result = Invoke-Validator -ProjectRoot $m003RejectsM012Root
    Assert-ExitCode -Actual $m003RejectsM012Result.ExitCode -Expected 1 -Message "La précondition doit refuser validate_m003_precondition.ps1 quand il refuse M-012."
    Assert-OutputContains `
        -Output $m003RejectsM012Result.Output `
        -Expected "Validateur amont M-003 n'accepte pas la branche M-012: scripts/validate_m003_precondition.ps1" `
        -Message "Le refus de M-012 par M-003 doit être explicite."

    $m011IgnoresM012Root = New-TemporaryProject -Name "m011-ignores-m012" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM011Artifacts $true
    New-ScriptFile `
        -Path (Join-Path $m011IgnoresM012Root "scripts/validate_m011_precondition.ps1") `
        -Content '$allowedBranches = @("master")'
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $m011IgnoresM012Root -BranchName $expectedBranch -DivergeMasterReference $false -AdvanceMasterAfterBranch $false
    $m011IgnoresM012Result = Invoke-Validator -ProjectRoot $m011IgnoresM012Root
    Assert-ExitCode -Actual $m011IgnoresM012Result.ExitCode -Expected 1 -Message "La précondition doit refuser un validateur amont qui ignore M-012."
    Assert-OutputContains `
        -Output $m011IgnoresM012Result.Output `
        -Expected "Validateur amont M-011 n'accepte pas la branche M-012: scripts/validate_m011_precondition.ps1" `
        -Message "L'acceptation amont manquante doit être explicite."
}
finally {
    $resolvedTemporaryRoot = [System.IO.Path]::GetFullPath($temporaryRoot)
    $resolvedSystemTemp = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
    if ($resolvedTemporaryRoot.StartsWith($resolvedSystemTemp, [System.StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath $temporaryRoot -PathType Container)) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}

Write-Host "Tests unitaires du validateur de précondition M-012: OK"
