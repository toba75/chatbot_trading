$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_definition_of_done.ps1"
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m000_definition_of_done_unit_" + [System.Guid]::NewGuid().ToString("N"))

$eAcute = [char] 0x00E9
$eGrave = [char] 0x00E8
$eCircumflex = [char] 0x00EA
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

- Given une t$($aCircumflex)che de milestone candidate $($aGrave) la cl$($oCircumflex)ture.
- When la d$($eAcute)finition d'ach$($eGrave)vement transverse est $($eAcute)valuee.
- Then les preuves BDD, ATDD, TDD, ADR, tra$($cCedilla)abilit$($eAcute), tests, lint et commits RED/GREEN sont pr$($eAcute)sentes ou la cl$($oCircumflex)ture est refus$($eAcute)e explicitement.

## $scopeHeading

Cette d$($eAcute)finition s'applique $($aGrave) chaque t$($aCircumflex)che de milestone avant d$($eAcute)claration de cl$($oCircumflex)ture.

## Gates obligatoires

| Gate | Preuve requise | Refus explicite |
|---|---|---|
| BDD | Sc$($eAcute)nario Given-When-Then versionn$($eAcute). | Refuser la cl$($oCircumflex)ture sans sc$($eAcute)nario. |
| ATDD | Test d'acceptation automatis$($eAcute) cr$($eAcute)$($eAcute) avant impl$($eAcute)mentation. | Refuser la cl$($oCircumflex)ture sans preuve RED. |
| TDD | Test unitaire de chaque invariant touch$($eAcute). | Refuser la cl$($oCircumflex)ture sans preuve de boucle TDD. |
| Commit RED | Hash du commit RED contenant le sc$($eAcute)nario et les tests. | Refuser la cl$($oCircumflex)ture si le commit RED manque. |
| Commit GREEN | Hash du commit GREEN contenant l'impl$($eAcute)mentation stricte. | Refuser la cl$($oCircumflex)ture si le commit GREEN manque. |
| ADR | ADR cr$($eAcute)$($eAcute)e, remplac$($eAcute)e ou absence d'ADR justifi$($eAcute)e. | Refuser la cl$($oCircumflex)ture si une d$($eAcute)cision structurante est implicite. |
| $traceabilityGate | Ligne de matrice specs-tests-code-ADR mise $($aGrave) jour. | Refuser la cl$($oCircumflex)ture si la matrice est incoh$($eAcute)rente. |
| Tests | Commandes de tests cibl$($eAcute)es puis pertinentes ex$($eAcute)cut$($eAcute)es. | Refuser la cl$($oCircumflex)ture si un test $($eAcute)choue ou est ignor$($eAcute). |
| Lint | Commandes de lint ou validation statique ex$($eAcute)cut$($eAcute)es. | Refuser la cl$($oCircumflex)ture si un lint configur$($eAcute) $($eAcute)choue ou manque sans blocage trac$($eAcute). |

## $proofHeading

Chaque gate poss$($eGrave)de une preuve explicite, datable dans Git et reli$($eAcute)e $($aGrave) une commande de validation.

## $adrHeading

Toute d$($eAcute)cision structurante est document$($eAcute)e dans docs/adr/ ou l'absence d'ADR est justifi$($eAcute)e.

## $traceabilityHeading

La matrice docs/traceability/matrix.md relie exigence, test, commande, code et ADR.

## Validation finale

La validation finale ex$($eAcute)cute scripts/test.ps1, scripts/lint.ps1 et les validateurs de gouvernance disponibles.

## $closureHeading

Aucune d$($eAcute)rogation implicite n'est accept$($eAcute)e; tout $($eAcute)cart devient un blocage document$($eAcute).
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

    $emptySectionDocument = $validDocument.Replace("La validation finale ex$($eAcute)cute scripts/test.ps1, scripts/lint.ps1 et les validateurs de gouvernance disponibles.", "")
    $emptySectionProjectRoot = New-TemporaryProject -Name "empty-section" -Document $emptySectionDocument
    $emptySectionResult = Invoke-Validator -ProjectRoot $emptySectionProjectRoot
    Assert-ExitCode -Actual $emptySectionResult.ExitCode -Expected 1 -Message "Une section obligatoire vide doit être refusée."

    $missingGateDocument = [regex]::Replace($validDocument, "(?m)^\| TDD \|.+\|\r?\n?", "")
    $missingGateProjectRoot = New-TemporaryProject -Name "missing-gate" -Document $missingGateDocument
    $missingGateResult = Invoke-Validator -ProjectRoot $missingGateProjectRoot
    Assert-ExitCode -Actual $missingGateResult.ExitCode -Expected 1 -Message "Une gate obligatoire absente doit être refusée."

    $lintGateRow = "| Lint | Commandes de lint ou validation statique ex$($eAcute)cut$($eAcute)es. | Refuser la cl$($oCircumflex)ture si un lint configur$($eAcute) $($eAcute)choue ou manque sans blocage trac$($eAcute). |"
    $unknownGateDocument = $validDocument.Replace($lintGateRow, "$lintGateRow`r`n| Revue manuelle | Validation hors gate automatique. | Refuser selon pr$($eAcute)f$($eAcute)rence. |")
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
