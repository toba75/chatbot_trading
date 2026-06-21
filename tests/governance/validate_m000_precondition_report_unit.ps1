$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m000_precondition_report.ps1"
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m000_precondition_" + [System.Guid]::NewGuid().ToString("N"))

function New-ValidReportContent {
    return @'
# Rapport de précondition GREEN M-000

## Scénario BDD

- Given le dépôt `master` contient la spécification v4.1 et le registre ADR.
- When la précondition de M-000 est vérifiée.
- Then l'état des validations existantes, des commandes absentes et des tâches versionnées est déclaré sans ambiguïté.

## Révision master

**Révision master observée :** `0123456789abcdef0123456789abcdef01234567`

## Validations exécutées

| Commande | Date UTC | Résultat | Observation |
|---|---|---|---|
| `git fetch origin --prune` | `2026-06-21T15:30:00Z` | `GREEN` | Remote synchronisé. |
| `git ls-tree -r --name-only master -- docs/tasks docs/adr docs/specs` | `2026-06-21T15:31:00Z` | `GREEN` | Artefacts amont listés. |
| `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_adr_system.ps1` | `2026-06-21T15:32:00Z` | `GREEN` | Système ADR valide. |

## Commandes de validation absentes

| Commande | Date UTC | Résultat | Observation |
|---|---|---|---|
| `.\scripts\test.ps1` | `2026-06-21T15:33:00Z` | `RED` | Commande absente à créer par M-000. |
| `.\scripts\lint.ps1` | `2026-06-21T15:34:00Z` | `RED` | Commande absente à créer par M-000. |

## Tâches versionnées

| Élément | Date UTC | Résultat | Observation |
|---|---|---|---|
| `docs/tasks/milestone_000 dans master` | `2026-06-21T15:35:00Z` | `RED` | Dossier absent de master au moment de l'audit. |
'@
}

function Invoke-Validator {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ReportPath
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    try {
        $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $validatorPath -Path $ReportPath 2>&1
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
    throw "Validateur de rapport absent: scripts/validate_m000_precondition_report.ps1"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    $validReportPath = Join-Path $temporaryRoot "valid.md"
    New-ValidReportContent | Set-Content -Encoding UTF8 -LiteralPath $validReportPath
    $validResult = Invoke-Validator -ReportPath $validReportPath
    Assert-ExitCode -Actual $validResult.ExitCode -Expected 0 -Message "Un rapport complet doit être accepté."

    $emptyMasterRevisionPath = Join-Path $temporaryRoot "empty-master-revision.md"
    (New-ValidReportContent).Replace('`0123456789abcdef0123456789abcdef01234567`', '``') |
        Set-Content -Encoding UTF8 -LiteralPath $emptyMasterRevisionPath
    $emptyMasterRevisionResult = Invoke-Validator -ReportPath $emptyMasterRevisionPath
    Assert-ExitCode -Actual $emptyMasterRevisionResult.ExitCode -Expected 1 -Message "Une révision master vide doit être refusée."

    $unknownStatePath = Join-Path $temporaryRoot "unknown-state.md"
    (New-ValidReportContent).Replace('| `GREEN` | Système ADR valide.', '| `UNKNOWN` | Système ADR valide.') |
        Set-Content -Encoding UTF8 -LiteralPath $unknownStatePath
    $unknownStateResult = Invoke-Validator -ReportPath $unknownStatePath
    Assert-ExitCode -Actual $unknownStateResult.ExitCode -Expected 1 -Message "Un état inconnu doit être refusé."

    $undatedCommandPath = Join-Path $temporaryRoot "undated-command.md"
    (New-ValidReportContent).Replace('| `2026-06-21T15:30:00Z` | `GREEN` | Remote synchronisé.', '| | `GREEN` | Remote synchronisé.') |
        Set-Content -Encoding UTF8 -LiteralPath $undatedCommandPath
    $undatedCommandResult = Invoke-Validator -ReportPath $undatedCommandPath
    Assert-ExitCode -Actual $undatedCommandResult.ExitCode -Expected 1 -Message "Une commande non datée doit être refusée."
}
finally {
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
}

Write-Host "Tests unitaires du validateur M-000 précondition: OK"
