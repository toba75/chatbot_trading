$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_definition_of_done.ps1"
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m000_definition_of_done_unit_" + [System.Guid]::NewGuid().ToString("N"))

$eAcute = [char] 0x00E9
$eGrave = [char] 0x00E8
$aCircumflex = [char] 0x00E2
$cCedilla = [char] 0x00E7
$oCircumflex = [char] 0x00F4

$scenarioHeading = "Sc$($eAcute)nario BDD"
$scopeHeading = "Port$($eAcute)e transverse"
$proofHeading = "Crit$($eGrave)res de preuve"
$adrHeading = "ADR et d$($eAcute)cisions structurantes"
$traceabilityHeading = "Tra$($cCedilla)abilit$($eAcute)"
$closureHeading = "Refus de cl$($oCircumflex)ture"
$traceabilityGate = "Tra$($cCedilla)abilit$($eAcute)"

function New-DefinitionDocument {
    return @"
# D$($eAcute)finition d'ach$($eGrave)vement transverse

## $scenarioHeading

- Given une t$($aCircumflex)che de milestone candidate a la cloture.
- When la d$($eAcute)finition d'ach$($eGrave)vement transverse est $($eAcute)valuee.
- Then les preuves BDD, ATDD, TDD, ADR, tra$($cCedilla)abilit$($eAcute), tests, lint et commits RED/GREEN sont presentes ou la cloture est refusee explicitement.

## $scopeHeading

Cette d$($eAcute)finition s'applique a chaque tache de milestone avant declaration de cloture.

## Gates obligatoires

| Gate | Preuve requise | Refus explicite |
|---|---|---|
| BDD | Scenario Given-When-Then versionne. | Refuser la cloture sans scenario. |
| ATDD | Test d'acceptation automatise cree avant implementation. | Refuser la cloture sans preuve RED. |
| TDD | Test unitaire de chaque invariant touche. | Refuser la cloture sans preuve de boucle TDD. |
| Commit RED | Hash du commit RED contenant le scenario et les tests. | Refuser la cloture si le commit RED manque. |
| Commit GREEN | Hash du commit GREEN contenant l'implementation stricte. | Refuser la cloture si le commit GREEN manque. |
| ADR | ADR creee, remplacee ou absence d'ADR justifiee. | Refuser la cloture si une decision structurante est implicite. |
| $traceabilityGate | Ligne de matrice specs-tests-code-ADR mise a jour. | Refuser la cloture si la matrice est incoherente. |
| Tests | Commandes de tests ciblees puis pertinentes executees. | Refuser la cloture si un test echoue ou est ignore. |
| Lint | Commandes de lint ou validation statique executees. | Refuser la cloture si un lint configure echoue ou manque sans blocage trace. |

## $proofHeading

Chaque gate possede une preuve explicite, datable dans Git et reliee a une commande de validation.

## $adrHeading

Toute decision structurante est documentee dans docs/adr/ ou l'absence d'ADR est justifiee.

## $traceabilityHeading

La matrice docs/traceability/matrix.md relie exigence, test, commande, code et ADR.

## Validation finale

La validation finale execute scripts/test.ps1, scripts/lint.ps1 et les validateurs de gouvernance disponibles.

## $closureHeading

Aucune derogation implicite n'est acceptee; tout ecart devient un blocage documente.
"@
}

function New-TemporaryProject {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name,

        [Parameter(Mandatory = $true)]
        [string] $Document
    )

    $projectRoot = Join-Path $temporaryRoot $Name
    $scriptDir = Join-Path $projectRoot "scripts"
    $governanceDir = Join-Path $projectRoot "docs/governance"

    New-Item -ItemType Directory -Path $scriptDir -Force | Out-Null
    New-Item -ItemType Directory -Path $governanceDir -Force | Out-Null
    Copy-Item -LiteralPath $validatorPath -Destination (Join-Path $scriptDir "validate_definition_of_done.ps1")
    Set-Content -Encoding UTF8 -LiteralPath (Join-Path $governanceDir "definition_of_done.md") -Value $Document

    return $projectRoot
}

function Invoke-Validator {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProjectRoot
    )

    $scriptPath = Join-Path $ProjectRoot "scripts/validate_definition_of_done.ps1"
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

function Invoke-ValidatorWithPath {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProjectRoot,

        [Parameter(Mandatory = $true)]
        [string] $Path
    )

    $scriptPath = Join-Path $ProjectRoot "scripts/validate_definition_of_done.ps1"
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    try {
        $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $scriptPath -Path $Path 2>&1
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
    throw "Validateur de définition d'achèvement absent: scripts/validate_definition_of_done.ps1"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    $validDocument = New-DefinitionDocument
    $validProjectRoot = New-TemporaryProject -Name "valid" -Document $validDocument
    $validResult = Invoke-Validator -ProjectRoot $validProjectRoot
    Assert-ExitCode -Actual $validResult.ExitCode -Expected 0 -Message "Une définition minimale conforme doit être acceptée."

    $missingSectionDocument = $validDocument.Replace("## $traceabilityHeading", "## Trace documentaire")
    $missingSectionProjectRoot = New-TemporaryProject -Name "missing-section" -Document $missingSectionDocument
    $missingSectionResult = Invoke-Validator -ProjectRoot $missingSectionProjectRoot
    Assert-ExitCode -Actual $missingSectionResult.ExitCode -Expected 1 -Message "Une section obligatoire absente doit être refusée."

    $emptySectionDocument = $validDocument.Replace("La validation finale execute scripts/test.ps1, scripts/lint.ps1 et les validateurs de gouvernance disponibles.", "")
    $emptySectionProjectRoot = New-TemporaryProject -Name "empty-section" -Document $emptySectionDocument
    $emptySectionResult = Invoke-Validator -ProjectRoot $emptySectionProjectRoot
    Assert-ExitCode -Actual $emptySectionResult.ExitCode -Expected 1 -Message "Une section obligatoire vide doit être refusée."

    $missingGateDocument = [regex]::Replace($validDocument, "(?m)^\| TDD \|.+\|\r?\n?", "")
    $missingGateProjectRoot = New-TemporaryProject -Name "missing-gate" -Document $missingGateDocument
    $missingGateResult = Invoke-Validator -ProjectRoot $missingGateProjectRoot
    Assert-ExitCode -Actual $missingGateResult.ExitCode -Expected 1 -Message "Une gate obligatoire absente doit être refusée."

    $unknownGateDocument = $validDocument.Replace("| Lint | Commandes de lint ou validation statique executees. | Refuser la cloture si un lint configure echoue ou manque sans blocage trace. |", "| Lint | Commandes de lint ou validation statique executees. | Refuser la cloture si un lint configure echoue ou manque sans blocage trace. |`r`n| Revue manuelle | Validation hors gate automatique. | Refuser selon preference. |")
    $unknownGateProjectRoot = New-TemporaryProject -Name "unknown-gate" -Document $unknownGateDocument
    $unknownGateResult = Invoke-Validator -ProjectRoot $unknownGateProjectRoot
    Assert-ExitCode -Actual $unknownGateResult.ExitCode -Expected 1 -Message "Une gate non autorisée doit être refusée."

    $blankPathProjectRoot = New-TemporaryProject -Name "blank-path" -Document $validDocument
    $blankPathResult = Invoke-ValidatorWithPath -ProjectRoot $blankPathProjectRoot -Path "   "
    Assert-ExitCode -Actual $blankPathResult.ExitCode -Expected 1 -Message "Un paramètre -Path explicitement vide doit être refusé."
}
finally {
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
}

Write-Host "Tests unitaires du validateur de définition d'achèvement: OK"
