$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_traceability.ps1"
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m000_traceability_unit_" + [System.Guid]::NewGuid().ToString("N"))
$eAcute = [char] 0x00E9
$eGrave = [char] 0x00E8
$aGrave = [char] 0x00E0

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

function Set-MatrixCell {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [string] $RequirementId,

        [Parameter(Mandatory = $true)]
        [string] $ColumnName,

        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string] $Value
    )

    $lines = [System.Collections.Generic.List[string]] (Get-Content -Encoding UTF8 -LiteralPath $Path)
    $headers = Split-MarkdownRow -Line $lines[0]
    $columnIndex = [array]::IndexOf($headers, $ColumnName)

    if ($columnIndex -lt 0) {
        throw "Colonne introuvable dans la matrice: $ColumnName"
    }

    for ($index = 2; $index -lt $lines.Count; $index++) {
        $cells = Split-MarkdownRow -Line $lines[$index]
        if (($cells.Count -gt 0) -and ($cells[0] -eq $RequirementId)) {
            $cells[$columnIndex] = $Value
            $lines[$index] = Join-MarkdownRow -Cells $cells
            Set-Content -Encoding UTF8 -LiteralPath $Path -Value $lines
            return
        }
    }

    throw "Exigence introuvable dans la matrice: $RequirementId"
}

function New-MatrixContent {
    return @"
| Exigence | Source | Statut | Test | Commande | Code | ADR | Justification ADR |
|---|---|---|---|---|---|---|---|
| REQ-M000-901 | docs/specs/specification.md | Couvert | tests/governance/example_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\example.ps1 | scripts/example.ps1 | ADR-001 | D$($eAcute)cision structurante d$($eAcute)j$($aGrave) publi$($eAcute)e. |
| REQ-M000-902 | docs/specs/specification.md | Partiel | tests/governance/example_acceptance.ps1 | Non applicable: couverture partielle document$($eAcute)e. | scripts/example.ps1 | Non requise | Aucune d$($eAcute)cision structurante nouvelle pour ce contr$([char] 0x00F4)le partiel. |
| REQ-M000-903 | docs/specs/specification.md | Planifi$($eAcute) | tests/governance/example_acceptance.ps1 | Non applicable: exigence planifi$($eAcute)e. | scripts/example.ps1 | Non requise | Aucune d$($eAcute)cision structurante nouvelle pour cette planification. |
| REQ-M000-904 | docs/specs/specification.md | Hors p$($eAcute)rim$($eGrave)tre M-000 | tests/governance/example_acceptance.ps1 | Non applicable: hors p$($eAcute)rim$($eGrave)tre du milestone. | scripts/example.ps1 | Non requise | Aucune d$($eAcute)cision structurante nouvelle car le code m$($eAcute)tier est hors p$($eAcute)rim$($eGrave)tre. |
"@
}

function New-TemporaryProject {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name
    )

    $projectRoot = Join-Path $temporaryRoot $Name
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "scripts") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs/adr") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs/specs") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs/traceability") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "tests/governance") -Force | Out-Null

    Copy-Item -LiteralPath $validatorPath -Destination (Join-Path $projectRoot "scripts/validate_traceability.ps1")

    "# ADR-001 - Test`n" | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $projectRoot "docs/adr/ADR-001-test.md")
    "# Specification`n" | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $projectRoot "docs/specs/specification.md")
    "# Test`n" | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $projectRoot "tests/governance/example_acceptance.ps1")
    "# Script`n" | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $projectRoot "scripts/example.ps1")
    New-MatrixContent | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $projectRoot "docs/traceability/matrix.md")

    return $projectRoot
}

function Invoke-Validator {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProjectRoot
    )

    $scriptPath = Join-Path $ProjectRoot "scripts/validate_traceability.ps1"
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
    throw "Validateur de traçabilité absent: scripts/validate_traceability.ps1"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    $validProjectRoot = New-TemporaryProject -Name "valid-statuses"
    $validResult = Invoke-Validator -ProjectRoot $validProjectRoot
    Assert-ExitCode -Actual $validResult.ExitCode -Expected 0 -Message "Les statuts autorisés doivent être acceptés."

    $emptyCellProjectRoot = New-TemporaryProject -Name "empty-cell"
    Set-MatrixCell `
        -Path (Join-Path $emptyCellProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M000-901" `
        -ColumnName "Source" `
        -Value ""
    $emptyCellResult = Invoke-Validator -ProjectRoot $emptyCellProjectRoot
    Assert-ExitCode -Actual $emptyCellResult.ExitCode -Expected 1 -Message "Une cellule vide doit être refusée."

    $invalidStatusProjectRoot = New-TemporaryProject -Name "invalid-status"
    Set-MatrixCell `
        -Path (Join-Path $invalidStatusProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M000-901" `
        -ColumnName "Statut" `
        -Value "Termin$($eAcute)"
    $invalidStatusResult = Invoke-Validator -ProjectRoot $invalidStatusProjectRoot
    Assert-ExitCode -Actual $invalidStatusResult.ExitCode -Expected 1 -Message "Un statut non autorisé doit être refusé."

    $missingAdrProjectRoot = New-TemporaryProject -Name "missing-adr"
    Set-MatrixCell `
        -Path (Join-Path $missingAdrProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M000-901" `
        -ColumnName "ADR" `
        -Value "ADR-999"
    $missingAdrResult = Invoke-Validator -ProjectRoot $missingAdrProjectRoot
    Assert-ExitCode -Actual $missingAdrResult.ExitCode -Expected 1 -Message "Une ADR inexistante doit être refusée."

    $missingTestProjectRoot = New-TemporaryProject -Name "missing-test"
    Set-MatrixCell `
        -Path (Join-Path $missingTestProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M000-901" `
        -ColumnName "Test" `
        -Value "tests/governance/test_absent.ps1"
    $missingTestResult = Invoke-Validator -ProjectRoot $missingTestProjectRoot
    Assert-ExitCode -Actual $missingTestResult.ExitCode -Expected 1 -Message "Un test absent doit être refusé."

    $coveredWithoutCommandProjectRoot = New-TemporaryProject -Name "covered-without-command"
    Set-MatrixCell `
        -Path (Join-Path $coveredWithoutCommandProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M000-901" `
        -ColumnName "Commande" `
        -Value "Non applicable: commande manquante."
    $coveredWithoutCommandResult = Invoke-Validator -ProjectRoot $coveredWithoutCommandProjectRoot
    Assert-ExitCode -Actual $coveredWithoutCommandResult.ExitCode -Expected 1 -Message "Un statut Couvert sans commande de validation doit être refusé."

    $missingCodeProjectRoot = New-TemporaryProject -Name "missing-code"
    Set-MatrixCell `
        -Path (Join-Path $missingCodeProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M000-901" `
        -ColumnName "Code" `
        -Value "scripts/code_absent.ps1"
    $missingCodeResult = Invoke-Validator -ProjectRoot $missingCodeProjectRoot
    Assert-ExitCode -Actual $missingCodeResult.ExitCode -Expected 1 -Message "Un artefact de code absent doit être refusé."
}
finally {
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
}

Write-Host "Tests unitaires du validateur de traçabilité: OK"
