$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m002_precondition.ps1"
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m002_precondition_unit_" + [System.Guid]::NewGuid().ToString("N"))
$expectedBranch = "codex/milestone-m002-plateforme-locale-sure"

function New-ScriptFile {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
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

function Commit-TemporaryProject {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProjectRoot,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    Invoke-GitCommand -ProjectRoot $ProjectRoot -Arguments @("-c", "core.autocrlf=false", "-c", "user.email=m002@example.test", "-c", "user.name=M002", "add", ".")
    Invoke-GitCommand -ProjectRoot $ProjectRoot -Arguments @("-c", "core.autocrlf=false", "-c", "user.email=m002@example.test", "-c", "user.name=M002", "commit", "-m", $Message)
}

function New-TemporaryProject {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name,

        [Parameter(Mandatory = $true)]
        [string] $TestGateContent,

        [Parameter(Mandatory = $true)]
        [string] $LintGateContent,

        [Parameter(Mandatory = $true)]
        [bool] $IncludeMilestone001
    )

    $projectRoot = Join-Path $temporaryRoot $Name
    New-Item -ItemType Directory -Path $projectRoot -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "scripts") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs/governance") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs/tasks/milestone_000") -Force | Out-Null

    Copy-Item -LiteralPath $validatorPath -Destination (Join-Path $projectRoot "scripts/validate_m002_precondition.ps1")
    New-ScriptFile -Path (Join-Path $projectRoot "scripts/test.ps1") -Content $TestGateContent
    New-ScriptFile -Path (Join-Path $projectRoot "scripts/lint.ps1") -Content $LintGateContent
    New-ScriptFile -Path (Join-Path $projectRoot "docs/tasks/milestone_000/0001_verifier_precondition_green.md") -Content "# M-000"

    if ($IncludeMilestone001) {
        New-ScriptFile -Path (Join-Path $projectRoot "docs/tasks/milestone_001/0001_verifier_precondition_green.md") -Content "# M-001"
    }

    return $projectRoot
}

function Initialize-ProjectWithMasterAndBranch {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProjectRoot,

        [Parameter(Mandatory = $true)]
        [bool] $DivergeMaster
    )

    Invoke-GitCommand -ProjectRoot $ProjectRoot -Arguments @("init", "-b", "master")
    Commit-TemporaryProject -ProjectRoot $ProjectRoot -Message "baseline m002 precondition"
    Invoke-GitCommand -ProjectRoot $ProjectRoot -Arguments @("checkout", "-b", $expectedBranch)

    if ($DivergeMaster) {
        Invoke-GitCommand -ProjectRoot $ProjectRoot -Arguments @("checkout", "master")
        New-ScriptFile -Path (Join-Path $ProjectRoot "docs/tasks/master_only.md") -Content "master divergé"
        Commit-TemporaryProject -ProjectRoot $ProjectRoot -Message "diverge master"
        Invoke-GitCommand -ProjectRoot $ProjectRoot -Arguments @("checkout", $expectedBranch)
    }
}

function Initialize-ProjectWithoutMaster {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProjectRoot
    )

    Invoke-GitCommand -ProjectRoot $ProjectRoot -Arguments @("init", "-b", $expectedBranch)
    Commit-TemporaryProject -ProjectRoot $ProjectRoot -Message "baseline without master"
}

function Invoke-Validator {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProjectRoot
    )

    $scriptPath = Join-Path $ProjectRoot "scripts/validate_m002_precondition.ps1"
    $reportPath = Join-Path $ProjectRoot "docs/governance/m002_precondition_green.md"
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
    throw "Validateur de précondition M-002 absent: scripts/validate_m002_precondition.ps1"
}

$greenTestGate = @'
Write-Host "Gate test GREEN: simulation M-002."
'@

$greenLintGate = @'
Write-Host "Gate lint GREEN: simulation M-002."
'@

$redTestGate = @'
Write-Host "Gate test RED: simulation M-002."
exit 1
'@

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    $withoutMasterRoot = New-TemporaryProject -Name "without-master" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeMilestone001 $true
    Initialize-ProjectWithoutMaster -ProjectRoot $withoutMasterRoot
    $withoutMasterResult = Invoke-Validator -ProjectRoot $withoutMasterRoot
    Assert-ExitCode -Actual $withoutMasterResult.ExitCode -Expected 1 -Message "La précondition doit refuser un dépôt sans master local."
    Assert-OutputContains -Output $withoutMasterResult.Output -Expected "Référence locale master absente." -Message "Le RED master absent doit être explicite."

    $missingMilestoneRoot = New-TemporaryProject -Name "missing-milestone" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeMilestone001 $false
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $missingMilestoneRoot -DivergeMaster $false
    $missingMilestoneResult = Invoke-Validator -ProjectRoot $missingMilestoneRoot
    Assert-ExitCode -Actual $missingMilestoneResult.ExitCode -Expected 1 -Message "La précondition doit refuser un milestone amont absent."
    Assert-OutputContains `
        -Output $missingMilestoneResult.Output `
        -Expected "Milestone amont absent de master: docs/tasks/milestone_001" `
        -Message "Le RED milestone absent doit nommer le dossier manquant."

    $redGateRoot = New-TemporaryProject -Name "red-gate" -TestGateContent $redTestGate -LintGateContent $greenLintGate -IncludeMilestone001 $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $redGateRoot -DivergeMaster $false
    $redGateResult = Invoke-Validator -ProjectRoot $redGateRoot
    Assert-ExitCode -Actual $redGateResult.ExitCode -Expected 1 -Message "La précondition doit refuser une gate RED."
    Assert-OutputContains -Output $redGateResult.Output -Expected "Gate test RED" -Message "La sortie de gate RED doit être conservée."
    Assert-OutputContains -Output $redGateResult.Output -Expected "Gate M-002 RED: test" -Message "Le validateur doit nommer la gate RED."

    $divergedBranchRoot = New-TemporaryProject -Name "diverged-branch" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeMilestone001 $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $divergedBranchRoot -DivergeMaster $true
    $divergedBranchResult = Invoke-Validator -ProjectRoot $divergedBranchRoot
    Assert-ExitCode -Actual $divergedBranchResult.ExitCode -Expected 1 -Message "La précondition doit refuser une branche qui ne contient pas master."
    Assert-OutputContains `
        -Output $divergedBranchResult.Output `
        -Expected "La branche courante ne contient pas la révision locale master." `
        -Message "La divergence de branche doit être explicite."
}
finally {
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
}

Write-Host "Tests unitaires du validateur de précondition M-002: OK"
