$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_task_system.ps1"
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m000_tasks_unit_" + [System.Guid]::NewGuid().ToString("N"))
$eAcute = [char] 0x00E9
$eGrave = [char] 0x00E8
$eCircumflex = [char] 0x00EA
$aGrave = [char] 0x00E0
$aCircumflex = [char] 0x00E2

function New-TaskContent {
    param(
        [Parameter(Mandatory = $true)]
        [string] $TaskId,

        [Parameter(Mandatory = $true)]
        [string] $Title
    )

    return @"
# $TaskId - $Title

## Milestone
- Nom: M-000 - Gouvernance exécutable.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`.
- Objectif métier: rendre une tâche contrôlable automatiquement.

## Contexte DDD
- Domaine: gouvernance d'impl$($eAcute)mentation.
- Bounded context: transverse.
- Objectif m$($eAcute)tier: emp$($eCircumflex)cher une t$($aCircumflex)che non v$($eAcute)rifiable.
- Langage ubiquitaire: milestone, t$($aCircumflex)che verticale, sc$($eAcute)nario BDD, test RED, commit RED, commit GREEN, commande de validation.
- Invariants critiques: une t$($aCircumflex)che poss$($eGrave)de un sc$($eAcute)nario et des validations.
- Garde-fous: aucune correction silencieuse.

## Blocages Ou Pr$($eAcute)conditions
- État GREEN/RED connu: connu.
- Pr$($eAcute)sence des milestones amont dans master: M-000 n'a aucune d$($eAcute)pendance amont.
- D$($eAcute)cisions manquantes: aucune.
- Risques: t$($aCircumflex)che non observable.

## T$($aCircumflex)ches
### $TaskId - $Title
- But m$($eAcute)tier: contr$([char] 0x00F4)ler une t$($aCircumflex)che verticale.
- Port$($eAcute)e DDD: gouvernance transverse.
- Sc$($eAcute)nario BDD:
  - Given un milestone pr$($eCircumflex)t.
  - When une t$($aCircumflex)che est cr$($eAcute)$($eAcute)e.
  - Then la convention est contr$([char] 0x00F4)lable automatiquement.
- Tests d'acceptation $($aGrave) $($eAcute)crire: un test automatis$($eAcute) RED.
- Tests unitaires $($aGrave) $($eAcute)crire: tests des invariants de structure.
- Impl$($eAcute)mentation attendue: un validateur strict.
- Invariants et garde-fous: pas de fallback silencieux.
- D$($eAcute)pendances: T-001.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_task_system.ps1`.
- Commit RED: `test(m000): couvrir une tâche`.
- Commit GREEN: `feat(m000): publier une tâche`.
"@
}

function New-TemporaryProject {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name
    )

    $projectRoot = Join-Path $temporaryRoot $Name
    $scriptDir = Join-Path $projectRoot "scripts"
    $tasksDir = Join-Path $projectRoot "docs/tasks"
    $milestoneDir = Join-Path $tasksDir "milestone_000"

    New-Item -ItemType Directory -Path $scriptDir -Force | Out-Null
    New-Item -ItemType Directory -Path $milestoneDir -Force | Out-Null
    Copy-Item -LiteralPath $validatorPath -Destination (Join-Path $scriptDir "validate_task_system.ps1")

    @"
# Convention des tâches de milestone

- Un dossier de milestone suit exactement docs/tasks/milestone_NNN.
- Une tâche de milestone suit exactement NNNN_slug.md.
- La première tâche est 0001_verifier_precondition_green.md.
- Le slug refuse les accents, espaces et majuscules.
- Le scénario contient Given, When et Then.
- La tâche déclare `Commit RED`, `Commit GREEN` et `Commandes de validation`.
"@ | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $tasksDir "README.md")

    New-TaskContent -TaskId "T-001" -Title "V$($eAcute)rifier la pr$($eAcute)condition GREEN de gouvernance initiale" |
        Set-Content -Encoding UTF8 -LiteralPath (Join-Path $milestoneDir "0001_verifier_precondition_green.md")

    New-TaskContent -TaskId "T-002" -Title "Contr$([char] 0x00F4)ler la t$($aCircumflex)che suivante" |
        Set-Content -Encoding UTF8 -LiteralPath (Join-Path $milestoneDir "0002_controler_tache_suivante.md")

    "# Journal M-000`n" | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $milestoneDir "journal.md")

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
    $validProjectRoot = New-TemporaryProject -Name "valid"
    $validResult = Invoke-Validator -ProjectRoot $validProjectRoot
    if ($validResult.ExitCode -ne 0) {
        throw "Un dossier de tâches minimal conforme doit être accepté. Sortie du validateur: $($validResult.Output)"
    }
    Assert-ExitCode -Actual $validResult.ExitCode -Expected 0 -Message "Un dossier de tâches minimal conforme doit être accepté."

    $invalidMilestoneProjectRoot = New-TemporaryProject -Name "invalid-milestone-number"
    Rename-Item -LiteralPath (Join-Path $invalidMilestoneProjectRoot "docs/tasks/milestone_000") -NewName "milestone_00"
    $invalidMilestoneResult = Invoke-Validator -ProjectRoot $invalidMilestoneProjectRoot
    Assert-ExitCode -Actual $invalidMilestoneResult.ExitCode -Expected 1 -Message "Un numéro de milestone hors format doit être refusé."

    $invalidTaskNumberProjectRoot = New-TemporaryProject -Name "invalid-task-number"
    Rename-Item -LiteralPath (Join-Path $invalidTaskNumberProjectRoot "docs/tasks/milestone_000/0002_controler_tache_suivante.md") -NewName "0003_controler_tache_suivante.md"
    $invalidTaskNumberResult = Invoke-Validator -ProjectRoot $invalidTaskNumberProjectRoot
    Assert-ExitCode -Actual $invalidTaskNumberResult.ExitCode -Expected 1 -Message "Un numéro de tâche non séquentiel doit être refusé."

    $invalidSlugProjectRoot = New-TemporaryProject -Name "invalid-slug"
    Rename-Item -LiteralPath (Join-Path $invalidSlugProjectRoot "docs/tasks/milestone_000/0002_controler_tache_suivante.md") -NewName "0002_Controler_tache_suivante.md"
    $invalidSlugResult = Invoke-Validator -ProjectRoot $invalidSlugProjectRoot
    Assert-ExitCode -Actual $invalidSlugResult.ExitCode -Expected 1 -Message "Un slug hors format doit être refusé."

    $missingSectionProjectRoot = New-TemporaryProject -Name "missing-section"
    $taskPath = Join-Path $missingSectionProjectRoot "docs/tasks/milestone_000/0002_controler_tache_suivante.md"
    (Get-Content -Raw -Encoding UTF8 -LiteralPath $taskPath).Replace("## Contexte DDD", "## Contexte manquant") |
        Set-Content -Encoding UTF8 -LiteralPath $taskPath
    $missingSectionResult = Invoke-Validator -ProjectRoot $missingSectionProjectRoot
    Assert-ExitCode -Actual $missingSectionResult.ExitCode -Expected 1 -Message "Une section obligatoire absente doit être refusée."

    $missingGivenProjectRoot = New-TemporaryProject -Name "missing-given"
    $taskPath = Join-Path $missingGivenProjectRoot "docs/tasks/milestone_000/0002_controler_tache_suivante.md"
    (Get-Content -Raw -Encoding UTF8 -LiteralPath $taskPath).Replace("  - Given un milestone pr$($eCircumflex)t.", "  - Sachant un milestone pr$($eCircumflex)t.") |
        Set-Content -Encoding UTF8 -LiteralPath $taskPath
    $missingGivenResult = Invoke-Validator -ProjectRoot $missingGivenProjectRoot
    Assert-ExitCode -Actual $missingGivenResult.ExitCode -Expected 1 -Message "Un scénario sans Given doit être refusé."

    $missingTddFieldProjectRoot = New-TemporaryProject -Name "missing-tdd-field"
    $taskPath = Join-Path $missingTddFieldProjectRoot "docs/tasks/milestone_000/0002_controler_tache_suivante.md"
    (Get-Content -Raw -Encoding UTF8 -LiteralPath $taskPath).Replace("- Tests unitaires $($aGrave) $($eAcute)crire:", "- Tests techniques:") |
        Set-Content -Encoding UTF8 -LiteralPath $taskPath
    $missingTddFieldResult = Invoke-Validator -ProjectRoot $missingTddFieldProjectRoot
    Assert-ExitCode -Actual $missingTddFieldResult.ExitCode -Expected 1 -Message "Une tâche sans champ TDD obligatoire doit être refusée."
}
finally {
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
}

Write-Host "Tests unitaires du validateur des tâches: OK"
