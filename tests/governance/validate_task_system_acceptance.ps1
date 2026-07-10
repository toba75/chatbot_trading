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
    Initialize-TemporaryGitMaster -ProjectRoot $projectRoot
    return $projectRoot
}

function Invoke-TemporaryGit {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProjectRoot,

        [Parameter(Mandatory = $true)]
        [string[]] $Arguments,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & git -C $ProjectRoot @Arguments 2>&1
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if ($LASTEXITCODE -ne 0) {
        throw "$Message Sortie git: $($output -join "`n")"
    }
}

function Initialize-TemporaryGitMaster {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProjectRoot
    )

    Invoke-TemporaryGit -ProjectRoot $ProjectRoot -Arguments @("init", "-b", "master") -Message "Impossible d'initialiser le dépôt temporaire."
    Invoke-TemporaryGit -ProjectRoot $ProjectRoot -Arguments @("config", "user.email", "tests@example.local") -Message "Impossible de configurer l'email Git temporaire."
    Invoke-TemporaryGit -ProjectRoot $ProjectRoot -Arguments @("config", "user.name", "Tests Gouvernance") -Message "Impossible de configurer le nom Git temporaire."
    Invoke-TemporaryGit -ProjectRoot $ProjectRoot -Arguments @("add", "docs/tasks", "scripts/validate_task_system.ps1") -Message "Impossible de préparer le master temporaire."
    Invoke-TemporaryGit -ProjectRoot $ProjectRoot -Arguments @("commit", "-m", "test: publier les tâches en master") -Message "Impossible de créer le master temporaire."
}

function New-MinimalTaskContent {
    param(
        [Parameter(Mandatory = $true)]
        [string] $TaskId,

        [Parameter(Mandatory = $true)]
        [string] $MilestoneName,

        [Parameter(Mandatory = $true)]
        [string] $Title
    )

    return @"
# $TaskId - $Title

## Milestone
- Nom: $MilestoneName.
- Source: `docs/tasks/README.md`.
- Objectif métier: contrôler la gouvernance des dossiers de milestone.

## Contexte DDD
- Domaine: gouvernance d'implémentation.
- Bounded context: transverse.
- Objectif métier: distinguer un milestone clôturé d'un sous-milestone partiel.
- Langage ubiquitaire: milestone, sous-milestone, clôture, master, tâche verticale.
- Invariants critiques: un sous-milestone ne clôture pas son parent.
- Garde-fous: aucun contournement silencieux des préconditions amont.

## Blocages Ou Préconditions
- État GREEN/RED connu: connu.
- Présence des milestones amont dans master: contrôlée par le validateur.
- Décisions manquantes: aucune.
- Risques: traiter une tranche partielle comme une clôture.

## Tâches
### $TaskId - $Title
- But métier: vérifier une règle de gouvernance de milestone.
- Portée DDD: gouvernance transverse.
- Scénario BDD:
  - Given un dossier de milestone est présent.
  - When le validateur contrôle ses dépendances.
  - Then la règle de clôture est appliquée explicitement.
- Tests d'acceptation à écrire: ce scénario de gouvernance.
- Tests unitaires à écrire: aucun test unitaire supplémentaire.
- Implémentation attendue: validation stricte du chemin de milestone.
- Invariants et garde-fous: un suffixe ne vaut pas clôture du parent.
- Dépendances: docs/tasks/README.md.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_task_system.ps1`.
- Commit RED: `test(governance): couvrir sous milestone sans cloture parent`.
- Commit GREEN: `fix(governance): distinguer sous milestone et cloture parent`.
"@
}

function New-SubMilestoneProject {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name,

        [Parameter(Mandatory = $false)]
        [switch] $IncludeDownstreamMilestone
    )

    $projectRoot = Join-Path $temporaryRoot $Name
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "scripts") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs/tasks/milestone_000") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs/tasks/milestone_001-config") -Force | Out-Null
    Copy-Item -LiteralPath $validatorPath -Destination (Join-Path $projectRoot "scripts/validate_task_system.ps1")
    Copy-Item -LiteralPath (Join-Path $tasksSourceDir "README.md") -Destination (Join-Path $projectRoot "docs/tasks/README.md")

    New-MinimalTaskContent -TaskId "T-001" -MilestoneName "M-000 - Gouvernance exécutable" -Title "Vérifier la précondition GREEN de gouvernance initiale" |
        Set-Content -Encoding UTF8 -LiteralPath (Join-Path $projectRoot "docs/tasks/milestone_000/0001_verifier_precondition_green.md")

    New-MinimalTaskContent -TaskId "T-001" -MilestoneName "M-001-config - Sous-milestone de configuration" -Title "Vérifier la précondition GREEN du sous milestone" |
        Set-Content -Encoding UTF8 -LiteralPath (Join-Path $projectRoot "docs/tasks/milestone_001-config/0001_verifier_precondition_green.md")

    if ($IncludeDownstreamMilestone) {
        New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs/tasks/milestone_002") -Force | Out-Null
        New-MinimalTaskContent -TaskId "T-001" -MilestoneName "M-002 - Milestone aval" -Title "Vérifier la précondition GREEN du milestone aval" |
            Set-Content -Encoding UTF8 -LiteralPath (Join-Path $projectRoot "docs/tasks/milestone_002/0001_verifier_precondition_green.md")
    }

    Initialize-TemporaryGitMaster -ProjectRoot $projectRoot
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
    throw "Validateur des tâches absent: scripts/validate_task_system.ps1"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    # Given un milestone M-000 prêt à être exécuté.
    # When les tâches sont publiées dans docs/tasks/milestone_NNN ou docs/tasks/milestone_NNN-slug.
    # Then leur chemin, leur ordre, leur scénario BDD, leurs commits RED/GREEN et leurs validations sont contrôlables automatiquement.
    $validProjectRoot = New-TemporaryProject -Name "valid"
    $validResult = Invoke-Validator -ProjectRoot $validProjectRoot
    if ($validResult.ExitCode -ne 0) {
        throw "Les tâches M-000 et M-001 conformes doivent être acceptées. Sortie du validateur: $($validResult.Output)"
    }
    Assert-ExitCode -Actual $validResult.ExitCode -Expected 0 -Message "Les tâches M-000 et M-001 conformes doivent être acceptées."

    $validSuffixedFolderProjectRoot = New-TemporaryProject -Name "valid-suffixed-folder"
    Rename-Item -LiteralPath (Join-Path $validSuffixedFolderProjectRoot "docs/tasks/milestone_000") -NewName "milestone_000-gouvernance"
    $validSuffixedFolderResult = Invoke-Validator -ProjectRoot $validSuffixedFolderProjectRoot
    if ($validSuffixedFolderResult.ExitCode -ne 0) {
        throw "Un dossier de milestone suffixé conforme doit être accepté. Sortie du validateur: $($validSuffixedFolderResult.Output)"
    }
    Assert-ExitCode -Actual $validSuffixedFolderResult.ExitCode -Expected 0 -Message "Un dossier de milestone suffixé conforme doit être accepté."

    $validSubMilestoneProjectRoot = New-SubMilestoneProject -Name "valid-sub-milestone-without-parent"
    $validSubMilestoneResult = Invoke-Validator -ProjectRoot $validSubMilestoneProjectRoot
    if ($validSubMilestoneResult.ExitCode -ne 0) {
        throw "Un sous-milestone ne doit pas exiger la clôture de son parent. Sortie du validateur: $($validSubMilestoneResult.Output)"
    }
    Assert-ExitCode -Actual $validSubMilestoneResult.ExitCode -Expected 0 -Message "Un sous-milestone ne doit pas exiger la clôture de son parent."

    $downstreamBlockedProjectRoot = New-SubMilestoneProject -Name "downstream-blocked-by-missing-parent" -IncludeDownstreamMilestone
    $downstreamBlockedResult = Invoke-Validator -ProjectRoot $downstreamBlockedProjectRoot
    Assert-ExitCode -Actual $downstreamBlockedResult.ExitCode -Expected 1 -Message "Un sous-milestone ne doit pas clôturer son parent pour un milestone aval."
    Assert-OutputContains `
        -Output $downstreamBlockedResult.Output `
        -Expected "Milestone amont absent de master pour le dossier aval: docs/tasks/milestone_001" `
        -Message "Le blocage aval doit nommer le milestone parent non clôturé."

    $invalidTitleProjectRoot = New-TemporaryProject -Name "invalid-title-message"
    $taskPath = Join-Path $invalidTitleProjectRoot "docs/tasks/milestone_000/0001_verifier_precondition_green.md"
    (Get-Content -Raw -Encoding UTF8 -LiteralPath $taskPath).Replace("# T-001 - ", "# ") |
        Set-Content -Encoding UTF8 -LiteralPath $taskPath
    $invalidTitleResult = Invoke-Validator -ProjectRoot $invalidTitleProjectRoot
    Assert-ExitCode -Actual $invalidTitleResult.ExitCode -Expected 1 -Message "Une tâche sans titre canonique doit être refusée."
    Assert-OutputContains `
        -Output $invalidTitleResult.Output `
        -Expected "Titre de tâche invalide ou absent: 0001_verifier_precondition_green.md" `
        -Message "Le RED de titre doit rester ciblé."

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
