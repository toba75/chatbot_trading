$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_definition_of_done.ps1"
$definitionPath = Join-Path $repoRoot "docs/governance/definition_of_done.md"
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m000_definition_of_done_acceptance_" + [System.Guid]::NewGuid().ToString("N"))

function Split-MarkdownRow {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Line
    )

    return @($Line.Trim().Trim("|").Split("|") | ForEach-Object { $_.Trim() })
}

function Join-MarkdownRow {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyCollection()]
        [AllowEmptyString()]
        [string[]] $Cells
    )

    return "| " + ($Cells -join " | ") + " |"
}

function Remove-GateRow {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [string] $Gate
    )

    $lines = [System.Collections.Generic.List[string]] (Get-Content -Encoding UTF8 -LiteralPath $Path)

    for ($index = $lines.Count - 1; $index -ge 0; $index--) {
        if ($lines[$index] -match "^\|\s*$([regex]::Escape($Gate))\s*\|") {
            $lines.RemoveAt($index)
        }
    }

    Set-Content -Encoding UTF8 -LiteralPath $Path -Value $lines
}

function Set-GateCell {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [string] $Gate,

        [Parameter(Mandatory = $true)]
        [string] $ColumnName,

        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string] $Value
    )

    $lines = [System.Collections.Generic.List[string]] (Get-Content -Encoding UTF8 -LiteralPath $Path)
    $headerIndex = -1

    for ($index = 0; $index -lt $lines.Count; $index++) {
        if ($lines[$index] -match "^\|\s*Gate\s*\|") {
            $headerIndex = $index
            break
        }
    }

    if ($headerIndex -lt 0) {
        throw "Table des gates introuvable."
    }

    $headers = Split-MarkdownRow -Line $lines[$headerIndex]
    $columnIndex = [array]::IndexOf($headers, $ColumnName)

    if ($columnIndex -lt 0) {
        throw "Colonne de gate introuvable: $ColumnName"
    }

    for ($index = $headerIndex + 2; $index -lt $lines.Count; $index++) {
        if ($lines[$index] -notmatch "^\|") {
            break
        }

        $cells = Split-MarkdownRow -Line $lines[$index]
        if (($cells.Count -gt 0) -and ($cells[0] -eq $Gate)) {
            $cells[$columnIndex] = $Value
            $lines[$index] = Join-MarkdownRow -Cells $cells
            Set-Content -Encoding UTF8 -LiteralPath $Path -Value $lines
            return
        }
    }

    throw "Gate introuvable: $Gate"
}

function New-TemporaryProject {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name
    )

    $projectRoot = Join-Path $temporaryRoot $Name
    New-Item -ItemType Directory -Path $projectRoot -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs") -Force | Out-Null

    Copy-Item -LiteralPath (Join-Path $repoRoot "scripts") -Destination (Join-Path $projectRoot "scripts") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/governance") -Destination (Join-Path $projectRoot "docs/governance") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/evaluation") -Destination (Join-Path $projectRoot "docs/evaluation") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/traceability") -Destination (Join-Path $projectRoot "docs/traceability") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/adr") -Destination (Join-Path $projectRoot "docs/adr") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/specs") -Destination (Join-Path $projectRoot "docs/specs") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/tasks") -Destination (Join-Path $projectRoot "docs/tasks") -Recurse

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

if (-not (Test-Path -LiteralPath $definitionPath -PathType Leaf)) {
    throw "Définition d'achèvement absente: docs/governance/definition_of_done.md"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    # Given une tâche de milestone candidate à la clôture.
    # When la définition d'achèvement transverse est évaluée.
    # Then les preuves BDD, ATDD, TDD, ADR, traçabilité, tests, lint et commits RED/GREEN sont présentes ou la clôture est refusée explicitement.
    $validProjectRoot = New-TemporaryProject -Name "valid"
    $validResult = Invoke-Validator -ProjectRoot $validProjectRoot
    Assert-ExitCode -Actual $validResult.ExitCode -Expected 0 -Message "Une définition d'achèvement complète doit être acceptée."

    $missingLintProjectRoot = New-TemporaryProject -Name "missing-lint"
    Remove-GateRow `
        -Path (Join-Path $missingLintProjectRoot "docs/governance/definition_of_done.md") `
        -Gate "Lint"
    $missingLintResult = Invoke-Validator -ProjectRoot $missingLintProjectRoot
    Assert-ExitCode -Actual $missingLintResult.ExitCode -Expected 1 -Message "Une clôture sans gate Lint doit être refusée."

    # Given une tâche UI candidate à la clôture.
    # When la preuve de passage exclusif par orchestrator-api est absente.
    # Then la clôture est refusée sans mock, stub, fake ni fallback de substitution.
    $missingUiApiBoundaryProjectRoot = New-TemporaryProject -Name "missing-ui-api-boundary"
    Remove-GateRow `
        -Path (Join-Path $missingUiApiBoundaryProjectRoot "docs/governance/definition_of_done.md") `
        -Gate "Frontière UI/API"
    $missingUiApiBoundaryResult = Invoke-Validator -ProjectRoot $missingUiApiBoundaryProjectRoot
    Assert-ExitCode -Actual $missingUiApiBoundaryResult.ExitCode -Expected 1 -Message "Une clôture sans gate Frontière UI/API doit être refusée."

    $emptyAdrProofProjectRoot = New-TemporaryProject -Name "empty-adr-proof"
    Set-GateCell `
        -Path (Join-Path $emptyAdrProofProjectRoot "docs/governance/definition_of_done.md") `
        -Gate "ADR" `
        -ColumnName "Preuve requise" `
        -Value ""
    $emptyAdrProofResult = Invoke-Validator -ProjectRoot $emptyAdrProofProjectRoot
    Assert-ExitCode -Actual $emptyAdrProofResult.ExitCode -Expected 1 -Message "Une gate ADR sans preuve requise doit être refusée."
}
finally {
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
}

Write-Host "Test d'acceptation de la définition d'achèvement transverse: OK"
