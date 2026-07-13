$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_traceability.ps1"
$matrixPath = Join-Path $repoRoot "docs/traceability/matrix.md"
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m000_traceability_acceptance_" + [System.Guid]::NewGuid().ToString("N"))

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
    $headerIndex = -1

    for ($index = 0; $index -lt $lines.Count; $index++) {
        if ($lines[$index] -match "^\|\s*Exigence\s*\|") {
            $headerIndex = $index
            break
        }
    }

    if ($headerIndex -lt 0) {
    throw "En-tête de matrice introuvable."
    }

    $headers = Split-MarkdownRow -Line $lines[$headerIndex]
    $columnIndex = [array]::IndexOf($headers, $ColumnName)

    if ($columnIndex -lt 0) {
        throw "Colonne introuvable dans la matrice: $ColumnName"
    }

    for ($index = $headerIndex + 1; $index -lt $lines.Count; $index++) {
        if ($lines[$index] -notmatch "^\|") {
            continue
        }

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

function New-TemporaryProject {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name
    )

    $projectRoot = Join-Path $temporaryRoot $Name
    New-Item -ItemType Directory -Path $projectRoot -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs") -Force | Out-Null

    Copy-Item -LiteralPath (Join-Path $repoRoot "scripts") -Destination (Join-Path $projectRoot "scripts") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "tests") -Destination (Join-Path $projectRoot "tests") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/adr") -Destination (Join-Path $projectRoot "docs/adr") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/governance") -Destination (Join-Path $projectRoot "docs/governance") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/evaluation") -Destination (Join-Path $projectRoot "docs/evaluation") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/runbooks") -Destination (Join-Path $projectRoot "docs/runbooks") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/specs") -Destination (Join-Path $projectRoot "docs/specs") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/tasks") -Destination (Join-Path $projectRoot "docs/tasks") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/traceability") -Destination (Join-Path $projectRoot "docs/traceability") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/user") -Destination (Join-Path $projectRoot "docs/user") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "app") -Destination (Join-Path $projectRoot "app") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "config") -Destination (Join-Path $projectRoot "config") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "deploy") -Destination (Join-Path $projectRoot "deploy") -Recurse

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

if (-not (Test-Path -LiteralPath $matrixPath -PathType Leaf)) {
    throw "Matrice de traçabilité absente: docs/traceability/matrix.md"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    # Given une exigence normative issue de la spécification v4.1 ou du plan de milestones.
    # When la matrice de traçabilité est contrôlée.
    # Then l'exigence possède un statut, une preuve de test, un artefact cible et une référence ADR explicite ou une justification d'absence d'ADR.
    $validProjectRoot = New-TemporaryProject -Name "valid"
    $validResult = Invoke-Validator -ProjectRoot $validProjectRoot
    Assert-ExitCode -Actual $validResult.ExitCode -Expected 0 -Message "La matrice initiale conforme doit être acceptée."

    $missingRootArtifactProjectRoot = New-TemporaryProject -Name "missing-root-artifact"
    Remove-Item -LiteralPath (Join-Path $missingRootArtifactProjectRoot "uv.lock")
    $missingRootArtifactResult = Invoke-Validator -ProjectRoot $missingRootArtifactProjectRoot
    Assert-ExitCode `
        -Actual $missingRootArtifactResult.ExitCode `
        -Expected 1 `
        -Message "Un artefact racine tracé mais absent doit être refusé."
    if (-not $missingRootArtifactResult.Output.Contains("uv.lock")) {
        throw "Le rejet doit nommer l'artefact racine absent. Sortie: $($missingRootArtifactResult.Output)"
    }

    $emptyCellProjectRoot = New-TemporaryProject -Name "empty-cell"
    Set-MatrixCell `
        -Path (Join-Path $emptyCellProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M000-001" `
        -ColumnName "Source" `
        -Value ""
    $emptyCellResult = Invoke-Validator -ProjectRoot $emptyCellProjectRoot
    Assert-ExitCode -Actual $emptyCellResult.ExitCode -Expected 1 -Message "Une cellule vide doit être refusée."

    $missingAdrProjectRoot = New-TemporaryProject -Name "missing-adr"
    Set-MatrixCell `
        -Path (Join-Path $missingAdrProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M000-002" `
        -ColumnName "ADR" `
        -Value "ADR-999"
    $missingAdrResult = Invoke-Validator -ProjectRoot $missingAdrProjectRoot
    Assert-ExitCode -Actual $missingAdrResult.ExitCode -Expected 1 -Message "Une ADR inexistante doit être refusée."

    $missingTestProjectRoot = New-TemporaryProject -Name "missing-test"
    Set-MatrixCell `
        -Path (Join-Path $missingTestProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M000-003" `
        -ColumnName "Test" `
        -Value "tests/governance/test_absent.ps1"
    $missingTestResult = Invoke-Validator -ProjectRoot $missingTestProjectRoot
    Assert-ExitCode -Actual $missingTestResult.ExitCode -Expected 1 -Message "Un test absent doit être refusé."

    $coveredWithoutCommandProjectRoot = New-TemporaryProject -Name "covered-without-command"
    Set-MatrixCell `
        -Path (Join-Path $coveredWithoutCommandProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M000-004" `
        -ColumnName "Commande" `
        -Value "Non applicable: commande absente."
    $coveredWithoutCommandResult = Invoke-Validator -ProjectRoot $coveredWithoutCommandProjectRoot
    Assert-ExitCode -Actual $coveredWithoutCommandResult.ExitCode -Expected 1 -Message "Un statut Couvert sans commande de validation doit être refusé."
}
finally {
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
}

Write-Host "Test d'acceptation de la matrice de traçabilité: OK"
