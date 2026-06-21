$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_task_system.ps1"
$tasksSourceDir = Join-Path $repoRoot "docs/tasks"
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m000_tasks_acceptance_" + [System.Guid]::NewGuid().ToString("N"))
$eAcute = [char] 0x00E9

function New-TemporaryProject {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name
    )

    $projectRoot = Join-Path $temporaryRoot $Name
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "scripts") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs") -Force | Out-Null
    Copy-Item -LiteralPath $validatorPath -Destination (Join-Path $projectRoot "scripts/validate_task_system.ps1")
    Copy-Item -LiteralPath $tasksSourceDir -Destination (Join-Path $projectRoot "docs/tasks") -Recurse
    return $projectRoot
}

function Invoke-Validator {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProjectRoot
    )

    $scriptPath = Join-Path $ProjectRoot "scripts/validate_task_system.ps1"
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    try {
        $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $scriptPath 2>&1
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    return [pscustomobject] @{
        ExitCode = $LASTEXITCODE
        Output = ($output -join "`n")
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

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
    throw "Validateur des tâches absent: scripts/validate_task_system.ps1"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    # Given un milestone M-000 prêt à être exécuté.
    # When les tâches sont publiées dans docs/tasks/milestone_NNN.
    # Then leur chemin, leur ordre, leur scénario BDD, leurs commits RED/GREEN et leurs validations sont contrôlables automatiquement.
    $validProjectRoot = New-TemporaryProject -Name "valid"
    $validResult = Invoke-Validator -ProjectRoot $validProjectRoot
    Assert-ExitCode -Actual $validResult.ExitCode -Expected 0 -Message "Les tâches M-000 conformes doivent être acceptées."

    $invalidFolderProjectRoot = New-TemporaryProject -Name "invalid-folder"
    Rename-Item -LiteralPath (Join-Path $invalidFolderProjectRoot "docs/tasks/milestone_000") -NewName "milestone_0"
    $invalidFolderResult = Invoke-Validator -ProjectRoot $invalidFolderProjectRoot
    Assert-ExitCode -Actual $invalidFolderResult.ExitCode -Expected 1 -Message "Un dossier de milestone hors format doit être refusé."

    $invalidSlugProjectRoot = New-TemporaryProject -Name "invalid-slug"
    Rename-Item -LiteralPath (Join-Path $invalidSlugProjectRoot "docs/tasks/milestone_000/0003_publier_convention_taches_milestone.md") -NewName "0003_publier_convention_tâches_milestone.md"
    $invalidSlugResult = Invoke-Validator -ProjectRoot $invalidSlugProjectRoot
    Assert-ExitCode -Actual $invalidSlugResult.ExitCode -Expected 1 -Message "Un slug accentué doit être refusé."

    $firstTaskProjectRoot = New-TemporaryProject -Name "first-task"
    Rename-Item -LiteralPath (Join-Path $firstTaskProjectRoot "docs/tasks/milestone_000/0001_verifier_precondition_green.md") -NewName "0001_lancer_milestone.md"
    $firstTaskResult = Invoke-Validator -ProjectRoot $firstTaskProjectRoot
    Assert-ExitCode -Actual $firstTaskResult.ExitCode -Expected 1 -Message "La première tâche doit être la précondition GREEN."

    $missingScenarioProjectRoot = New-TemporaryProject -Name "missing-scenario"
    $taskPath = Join-Path $missingScenarioProjectRoot "docs/tasks/milestone_000/0003_publier_convention_taches_milestone.md"
    (Get-Content -Raw -Encoding UTF8 -LiteralPath $taskPath).Replace("- Sc$($eAcute)nario BDD:", "- Sc$($eAcute)nario supprim$($eAcute):") |
        Set-Content -Encoding UTF8 -LiteralPath $taskPath
    $missingScenarioResult = Invoke-Validator -ProjectRoot $missingScenarioProjectRoot
    Assert-ExitCode -Actual $missingScenarioResult.ExitCode -Expected 1 -Message "Une tâche sans scénario BDD doit être refusée."

    $missingCommitProjectRoot = New-TemporaryProject -Name "missing-commit"
    $taskPath = Join-Path $missingCommitProjectRoot "docs/tasks/milestone_000/0003_publier_convention_taches_milestone.md"
    (Get-Content -Raw -Encoding UTF8 -LiteralPath $taskPath).Replace("- Commit GREEN:", "- Commit final:") |
        Set-Content -Encoding UTF8 -LiteralPath $taskPath
    $missingCommitResult = Invoke-Validator -ProjectRoot $missingCommitProjectRoot
    Assert-ExitCode -Actual $missingCommitResult.ExitCode -Expected 1 -Message "Une tâche sans commit GREEN déclaré doit être refusée."

    $missingValidationProjectRoot = New-TemporaryProject -Name "missing-validation"
    $taskPath = Join-Path $missingValidationProjectRoot "docs/tasks/milestone_000/0003_publier_convention_taches_milestone.md"
    (Get-Content -Raw -Encoding UTF8 -LiteralPath $taskPath).Replace("- Commandes de validation:", "- Commandes omises:") |
        Set-Content -Encoding UTF8 -LiteralPath $taskPath
    $missingValidationResult = Invoke-Validator -ProjectRoot $missingValidationProjectRoot
    Assert-ExitCode -Actual $missingValidationResult.ExitCode -Expected 1 -Message "Une tâche sans commandes de validation doit être refusée."
}
finally {
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
}

Write-Host "Test d'acceptation de la convention des tâches: OK"
