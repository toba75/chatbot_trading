$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m003_precondition.ps1"
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m003_precondition_unit_" + [System.Guid]::NewGuid().ToString("N"))
$expectedBranch = "codex/milestone-m003-source-routee"

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

    Invoke-GitCommand -ProjectRoot $ProjectRoot -Arguments @("-c", "core.autocrlf=false", "-c", "user.email=m003@example.test", "-c", "user.name=M003", "add", ".")
    Invoke-GitCommand -ProjectRoot $ProjectRoot -Arguments @("-c", "core.autocrlf=false", "-c", "user.email=m003@example.test", "-c", "user.name=M003", "commit", "-m", $Message)
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
        [bool] $IncludeMilestone002
    )

    $projectRoot = Join-Path $temporaryRoot $Name
    New-Item -ItemType Directory -Path $projectRoot -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "scripts") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs/governance") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs/tasks/milestone_000") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs/tasks/milestone_001") -Force | Out-Null

    Copy-Item -LiteralPath $validatorPath -Destination (Join-Path $projectRoot "scripts/validate_m003_precondition.ps1")
    New-ScriptFile -Path (Join-Path $projectRoot "scripts/test.ps1") -Content $TestGateContent
    New-ScriptFile -Path (Join-Path $projectRoot "scripts/lint.ps1") -Content $LintGateContent
    New-ScriptFile -Path (Join-Path $projectRoot "docs/tasks/milestone_000/0001_verifier_precondition_green.md") -Content "# M-000"
    New-ScriptFile -Path (Join-Path $projectRoot "docs/tasks/milestone_001/0001_verifier_precondition_green.md") -Content "# M-001"

    if ($IncludeMilestone002) {
        New-ScriptFile -Path (Join-Path $projectRoot "docs/tasks/milestone_002/0001_verifier_precondition_green.md") -Content "# M-002"
    }

    return $projectRoot
}

function Initialize-ProjectWithMasterAndBranch {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProjectRoot,

        [Parameter(Mandatory = $true)]
        [bool] $DivergeMasterReference
    )

    Invoke-GitCommand -ProjectRoot $ProjectRoot -Arguments @("init", "-b", "master")
    Commit-TemporaryProject -ProjectRoot $ProjectRoot -Message "baseline m003 precondition"
    $baselineRevision = Get-GitOutput -ProjectRoot $ProjectRoot -Arguments @("rev-parse", "master")
    Invoke-GitCommand -ProjectRoot $ProjectRoot -Arguments @("update-ref", "refs/remotes/origin/master", $baselineRevision)
    Invoke-GitCommand -ProjectRoot $ProjectRoot -Arguments @("checkout", "-b", $expectedBranch)

    if ($DivergeMasterReference) {
        Invoke-GitCommand -ProjectRoot $ProjectRoot -Arguments @("checkout", "master")
        New-ScriptFile -Path (Join-Path $ProjectRoot "docs/tasks/master_reference_only.md") -Content "master local divergé"
        Commit-TemporaryProject -ProjectRoot $ProjectRoot -Message "diverge master reference"
        Invoke-GitCommand -ProjectRoot $ProjectRoot -Arguments @("checkout", $expectedBranch)
    }
}

function Invoke-Validator {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProjectRoot
    )

    $scriptPath = Join-Path $ProjectRoot "scripts/validate_m003_precondition.ps1"
    $reportPath = Join-Path $ProjectRoot "docs/governance/m003_precondition_green.md"
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
    throw "Validateur de précondition M-003 absent: scripts/validate_m003_precondition.ps1"
}

$greenTestGate = @'
Write-Host "Gate test GREEN: simulation M-003."
'@

$greenLintGate = @'
Write-Host "Gate lint GREEN: simulation M-003."
'@

$redTestGate = @'
Write-Host "Gate test RED: simulation M-003."
exit 1
'@

$emptyTestGate = @'
'@

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    $missingMilestoneRoot = New-TemporaryProject -Name "missing-milestone" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeMilestone002 $false
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $missingMilestoneRoot -DivergeMasterReference $false
    $missingMilestoneResult = Invoke-Validator -ProjectRoot $missingMilestoneRoot
    Assert-ExitCode -Actual $missingMilestoneResult.ExitCode -Expected 1 -Message "La précondition doit refuser un milestone amont absent."
    Assert-OutputContains `
        -Output $missingMilestoneResult.Output `
        -Expected "Milestone amont absent de master: docs/tasks/milestone_002" `
        -Message "Le RED milestone absent doit nommer le dossier manquant."

    $divergedMasterRoot = New-TemporaryProject -Name "diverged-master-reference" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeMilestone002 $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $divergedMasterRoot -DivergeMasterReference $true
    $divergedMasterResult = Invoke-Validator -ProjectRoot $divergedMasterRoot
    Assert-ExitCode -Actual $divergedMasterResult.ExitCode -Expected 1 -Message "La précondition doit refuser une référence master divergente."
    Assert-OutputContains `
        -Output $divergedMasterResult.Output `
        -Expected "Référence master divergente entre master et origin/master." `
        -Message "La divergence master doit être explicite."

    $redGateRoot = New-TemporaryProject -Name "red-gate" -TestGateContent $redTestGate -LintGateContent $greenLintGate -IncludeMilestone002 $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $redGateRoot -DivergeMasterReference $false
    $redGateResult = Invoke-Validator -ProjectRoot $redGateRoot
    Assert-ExitCode -Actual $redGateResult.ExitCode -Expected 1 -Message "La précondition doit refuser une gate RED."
    Assert-OutputContains -Output $redGateResult.Output -Expected "Gate test RED" -Message "La sortie de gate RED doit être conservée."
    Assert-OutputContains -Output $redGateResult.Output -Expected "Gate M-003 RED: test" -Message "Le validateur doit nommer la gate RED."

    $emptyOutputRoot = New-TemporaryProject -Name "empty-test-output" -TestGateContent $emptyTestGate -LintGateContent $greenLintGate -IncludeMilestone002 $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $emptyOutputRoot -DivergeMasterReference $false
    $emptyOutputResult = Invoke-Validator -ProjectRoot $emptyOutputRoot
    Assert-ExitCode -Actual $emptyOutputResult.ExitCode -Expected 1 -Message "La précondition doit refuser une sortie de test vide."
    Assert-OutputContains `
        -Output $emptyOutputResult.Output `
        -Expected "Gate M-003 RED: test sans sortie." `
        -Message "La sortie vide doit être nommée explicitement."
}
finally {
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
}

Write-Host "Tests unitaires du validateur de précondition M-003: OK"
