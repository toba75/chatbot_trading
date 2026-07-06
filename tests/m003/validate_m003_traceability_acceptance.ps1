$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_traceability.ps1"
$matrixPath = Join-Path $repoRoot "docs/traceability/matrix.md"
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m003_traceability_acceptance_" + [System.Guid]::NewGuid().ToString("N"))
$eAcute = [char] 0x00E9
$cCedilla = [char] 0x00E7

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

function Remove-MatrixRow {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [string] $RequirementId
    )

    $lines = [System.Collections.Generic.List[string]] (Get-Content -Encoding UTF8 -LiteralPath $Path)

    for ($index = $lines.Count - 1; $index -ge 0; $index--) {
        if ($lines[$index] -notmatch "^\|") {
            continue
        }

        $cells = Split-MarkdownRow -Line $lines[$index]
        if (($cells.Count -gt 0) -and ($cells[0] -eq $RequirementId)) {
            $lines.RemoveAt($index)
        }
    }

    Set-Content -Encoding UTF8 -LiteralPath $Path -Value $lines
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
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/specs") -Destination (Join-Path $projectRoot "docs/specs") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/tasks") -Destination (Join-Path $projectRoot "docs/tasks") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/traceability") -Destination (Join-Path $projectRoot "docs/traceability") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "app") -Destination (Join-Path $projectRoot "app") -Recurse
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
    throw "Validateur de traçabilité absent: scripts/validate_traceability.ps1"
}

if (-not (Test-Path -LiteralPath $matrixPath -PathType Leaf)) {
    throw "Matrice de traçabilité absente: docs/traceability/matrix.md"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    # Given les comportements M-003 sont implémentés et testés.
    # When les gates de clôture sont exécutées.
    # Then chaque exigence M-003 est reliée à une preuve et la clôture est refusée si un test, une ADR, une commande ou un signal d'audit manque.
    $validProjectRoot = New-TemporaryProject -Name "valid"
    $validResult = Invoke-Validator -ProjectRoot $validProjectRoot
    Assert-ExitCode -Actual $validResult.ExitCode -Expected 0 -Message "La matrice M-003 complète doit être acceptée."

    $missingRequirementProjectRoot = New-TemporaryProject -Name "missing-requirement"
    Remove-MatrixRow `
        -Path (Join-Path $missingRequirementProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M003-010"
    $missingRequirementResult = Invoke-Validator -ProjectRoot $missingRequirementProjectRoot
    Assert-ExitCode -Actual $missingRequirementResult.ExitCode -Expected 1 -Message "Une exigence M-003 livrée absente doit être refusée."
    Assert-OutputContains `
        -Output $missingRequirementResult.Output `
        -Expected "Exigence M-003 livr$($eAcute)e absente: REQ-M003-010" `
        -Message "L'exigence M-003 absente doit être nommée."

    $coveredWithoutCommandProjectRoot = New-TemporaryProject -Name "covered-without-command"
    Set-MatrixCell `
        -Path (Join-Path $coveredWithoutCommandProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M003-010" `
        -ColumnName "Commande" `
        -Value "Non applicable: commande absente."
    $coveredWithoutCommandResult = Invoke-Validator -ProjectRoot $coveredWithoutCommandProjectRoot
    Assert-ExitCode -Actual $coveredWithoutCommandResult.ExitCode -Expected 1 -Message "Une ligne M-003 couverte sans commande doit être refusée."
    Assert-OutputContains `
        -Output $coveredWithoutCommandResult.Output `
        -Expected "REQ-M003-010" `
        -Message "La commande manquante de clôture M-003 doit être nommée."

    $missingAuditProjectRoot = New-TemporaryProject -Name "missing-audit"
    Set-MatrixCell `
        -Path (Join-Path $missingAuditProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M003-009" `
        -ColumnName "Test" `
        -Value "tests/m003/validate_m003_traceability_acceptance.ps1"
    $missingAuditResult = Invoke-Validator -ProjectRoot $missingAuditProjectRoot
    Assert-ExitCode -Actual $missingAuditResult.ExitCode -Expected 1 -Message "Une clôture M-003 sans preuve d'audit doit être refusée."
    Assert-OutputContains `
        -Output $missingAuditResult.Output `
        -Expected "Test M-003 invalide pour REQ-M003-009" `
        -Message "La preuve d'audit M-003 absente doit être nommée."
}
finally {
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
}

Write-Host "Test d'acceptation de la tra$($cCedilla)abilit$($eAcute) M-003: OK"
