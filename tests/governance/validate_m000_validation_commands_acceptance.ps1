$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$testCommandPath = Join-Path $repoRoot "scripts/test.ps1"
$lintCommandPath = Join-Path $repoRoot "scripts/lint.ps1"
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m000_validation_commands_acceptance_" + [System.Guid]::NewGuid().ToString("N"))
$eAcute = [char] 0x00E9

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
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/specs") -Destination (Join-Path $projectRoot "docs/specs") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/tasks") -Destination (Join-Path $projectRoot "docs/tasks") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/traceability") -Destination (Join-Path $projectRoot "docs/traceability") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "app") -Destination (Join-Path $projectRoot "app") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "deploy") -Destination (Join-Path $projectRoot "deploy") -Recurse

    return $projectRoot
}

function Invoke-ProjectCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProjectRoot,

        [Parameter(Mandatory = $true)]
        [string] $RelativePath
    )

    $scriptPath = Join-Path $ProjectRoot $RelativePath
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    Push-Location -LiteralPath $ProjectRoot

    try {
        $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $scriptPath 2>&1
    }
    finally {
        Pop-Location
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

function Assert-OutputNotContains {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Output,

        [Parameter(Mandatory = $true)]
        [string] $Forbidden,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if ($Output.Contains($Forbidden)) {
        throw "$Message Sortie obtenue: $Output"
    }
}

function Initialize-GitBaseline {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProjectRoot
    )

    & git -C $ProjectRoot init -b master 2>$null | Out-Null
    & git -C $ProjectRoot -c core.autocrlf=false -c user.email="m000@example.test" -c user.name="M000" add . 2>$null | Out-Null
    & git -C $ProjectRoot -c core.autocrlf=false -c user.email="m000@example.test" -c user.name="M000" commit -m "baseline m000 validation commands" 2>$null | Out-Null
}

if (-not (Test-Path -LiteralPath $testCommandPath -PathType Leaf)) {
    throw "Commande de test M-000 absente: scripts/test.ps1"
}

if (-not (Test-Path -LiteralPath $lintCommandPath -PathType Leaf)) {
    throw "Commande de lint M-000 absente: scripts/lint.ps1"
}

$validationCommandsDocumentPath = Join-Path $repoRoot "docs/governance/m000_validation_commands.md"
if (-not (Test-Path -LiteralPath $validationCommandsDocumentPath -PathType Leaf)) {
    throw "Documentation des commandes M-000 absente: docs/governance/m000_validation_commands.md"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    # Given les artefacts de gouvernance M-000 sont présents.
    # When les gates globales de test et de lint sont exécutées.
    # Then elles retournent GREEN sur un dépôt valide ou RED avec la validation fautive nommée.
    $validProjectRoot = New-TemporaryProject -Name "valid"
    Initialize-GitBaseline -ProjectRoot $validProjectRoot
    $testResult = Invoke-ProjectCommand -ProjectRoot $validProjectRoot -RelativePath "scripts/test.ps1"
    Assert-ExitCode -Actual $testResult.ExitCode -Expected 0 -Message "La gate de test M-000 conforme doit réussir."
    Assert-OutputContains -Output $testResult.Output -Expected "Gate test GREEN" -Message "La gate de test doit annoncer son état GREEN."
    Assert-OutputContains -Output $testResult.Output -Expected "Gate test GREEN: 10 validation(s), 41 test(s)." -Message "La gate de test doit prouver le nombre exact de validations et tests."
    Assert-OutputContains -Output $testResult.Output -Expected "Test GREEN: tests/governance/validate_m000_precondition_report_acceptance.ps1" -Message "La gate de test doit exécuter le test d'acceptation T-001."
    Assert-OutputContains -Output $testResult.Output -Expected "Test GREEN: tests/governance/validate_definition_of_done_unit.ps1" -Message "La gate de test doit exécuter le dernier test unitaire T-005."
    Assert-OutputContains -Output $testResult.Output -Expected "Test GREEN: tests/governance/validate_m000_validation_commands_unit.ps1" -Message "La gate de test doit exécuter le self-test unitaire T-006."
    Assert-OutputContains -Output $testResult.Output -Expected "Test GREEN: tests/m001/validate_m001_traceability_unit.ps1" -Message "La gate de test doit exécuter le test unitaire de traçabilité M-001."
    Assert-OutputContains -Output $testResult.Output -Expected "Test GREEN: tests/m002/validate_m002_specification_acceptance.ps1" -Message "La gate de test doit exécuter le test d'acceptation de spécification M-002."
    Assert-OutputContains -Output $testResult.Output -Expected "Test GREEN: tests/m002/validate_m002_specification_unit.ps1" -Message "La gate de test doit exécuter le test unitaire de spécification M-002."
    Assert-OutputContains -Output $testResult.Output -Expected "Test GREEN: tests/m002/validate_platform_topology_acceptance.ps1" -Message "La gate de test doit exécuter le test d'acceptation de topologie M-002."
    Assert-OutputContains -Output $testResult.Output -Expected "Test GREEN: tests/m002/validate_platform_topology_unit.ps1" -Message "La gate de test doit exécuter le test unitaire de topologie M-002."
    Assert-OutputContains -Output $testResult.Output -Expected "Validation GREEN: scripts/validate_local_compose.ps1" -Message "La gate de test doit exécuter le validateur Compose local M-002."
    Assert-OutputContains -Output $testResult.Output -Expected "Test GREEN: tests/m002/validate_local_compose_acceptance.ps1" -Message "La gate de test doit exécuter le test d'acceptation Compose local M-002."
    Assert-OutputContains -Output $testResult.Output -Expected "Test GREEN: tests/m002/validate_local_compose_unit.ps1" -Message "La gate de test doit exécuter le test unitaire Compose local M-002."
    Assert-OutputContains -Output $testResult.Output -Expected "Test GREEN: tests/m002/validate_llm_gateway_contract_acceptance.ps1" -Message "La gate de test doit exécuter le test d'acceptation contrat gateway LLM M-002."
    Assert-OutputContains -Output $testResult.Output -Expected "Test GREEN: tests/m002/validate_llm_gateway_contract_unit.ps1" -Message "La gate de test doit exécuter le test unitaire contrat gateway LLM M-002."
    Assert-OutputContains -Output $testResult.Output -Expected "Test GREEN: tests/m002/validate_llm_gateway_failures_acceptance.ps1" -Message "La gate de test doit exécuter le test d'acceptation pannes gateway LLM M-002."
    Assert-OutputContains -Output $testResult.Output -Expected "Test GREEN: tests/m002/validate_llm_gateway_failures_unit.ps1" -Message "La gate de test doit exécuter le test unitaire pannes gateway LLM M-002."
    Assert-OutputNotContains -Output $testResult.Output -Forbidden "Ã" -Message "La sortie de la gate de test doit rester lisible en français accentué."

    $lintResult = Invoke-ProjectCommand -ProjectRoot $validProjectRoot -RelativePath "scripts/lint.ps1"
    Assert-ExitCode -Actual $lintResult.ExitCode -Expected 0 -Message "La gate de lint M-000 conforme doit réussir."
    Assert-OutputContains -Output $lintResult.Output -Expected "Gate lint GREEN" -Message "La gate de lint doit annoncer son état GREEN."
    Assert-OutputContains -Output $lintResult.Output -Expected "Gate lint GREEN: 10 validation(s), 0 test(s)." -Message "La gate de lint doit prouver le nombre exact de validations et tests."
    Assert-OutputContains -Output $lintResult.Output -Expected "Validation GREEN: scripts/validate_local_compose.ps1" -Message "La gate de lint doit exécuter le validateur Compose local M-002."
    Assert-OutputNotContains -Output $lintResult.Output -Forbidden "Ã" -Message "La sortie de la gate de lint doit rester lisible en français accentué."

    $validationCommandsDocument = Get-Content -Raw -Encoding UTF8 -LiteralPath $validationCommandsDocumentPath
    Assert-OutputContains -Output $validationCommandsDocument -Expected "git fetch origin --prune" -Message "La documentation des gates doit déclarer la synchronisation Git préalable."
    Assert-OutputContains -Output $validationCommandsDocument -Expected "master" -Message "La documentation des gates doit déclarer la référence locale master."

    $missingValidationProjectRoot = New-TemporaryProject -Name "missing-validation"
    Initialize-GitBaseline -ProjectRoot $missingValidationProjectRoot
    Remove-Item -LiteralPath (Join-Path $missingValidationProjectRoot "scripts/validate_traceability.ps1")
    $missingValidationResult = Invoke-ProjectCommand -ProjectRoot $missingValidationProjectRoot -RelativePath "scripts/lint.ps1"
    Assert-ExitCode -Actual $missingValidationResult.ExitCode -Expected 1 -Message "Une validation requise absente doit produire un RED."
    Assert-OutputContains -Output $missingValidationResult.Output -Expected "Gate lint RED" -Message "La gate de lint doit annoncer son état RED."
    Assert-OutputContains `
        -Output $missingValidationResult.Output `
        -Expected "Validation requise absente: scripts/validate_traceability.ps1" `
        -Message "La validation absente doit être nommée."

    $failingValidationProjectRoot = New-TemporaryProject -Name "failing-validation"
    Initialize-GitBaseline -ProjectRoot $failingValidationProjectRoot
    Set-MatrixCell `
        -Path (Join-Path $failingValidationProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M000-004" `
        -ColumnName "Commande" `
        -Value "Non applicable: commande rendue invalide pour le test."
    $failingValidationResult = Invoke-ProjectCommand -ProjectRoot $failingValidationProjectRoot -RelativePath "scripts/lint.ps1"
    Assert-ExitCode -Actual $failingValidationResult.ExitCode -Expected 1 -Message "Une validation requise échouée doit produire un RED."
    Assert-OutputContains -Output $failingValidationResult.Output -Expected "Gate lint RED" -Message "La gate de lint doit annoncer son état RED."
    Assert-OutputContains `
        -Output $failingValidationResult.Output `
        -Expected "Validation $($eAcute)chou$($eAcute)e: scripts/validate_traceability.ps1" `
        -Message "La validation échouée doit être nommée."

    $missingTestCommandProjectRoot = New-TemporaryProject -Name "missing-test-command"
    Initialize-GitBaseline -ProjectRoot $missingTestCommandProjectRoot
    $testScriptPath = Join-Path $missingTestCommandProjectRoot "scripts/test.ps1"
    (Get-Content -Raw -Encoding UTF8 -LiteralPath $testScriptPath).Replace('    @{ Path = "tests/governance/validate_m000_precondition_report_acceptance.ps1"; Arguments = @() },', '') |
        Set-Content -Encoding UTF8 -LiteralPath $testScriptPath
    $missingTestCommandResult = Invoke-ProjectCommand -ProjectRoot $missingTestCommandProjectRoot -RelativePath "scripts/test.ps1"
    Assert-ExitCode -Actual $missingTestCommandResult.ExitCode -Expected 1 -Message "Une gate amputée d'un test requis doit produire un RED."
    Assert-OutputContains `
        -Output $missingTestCommandResult.Output `
        -Expected "Gate test attend 41 test(s)" `
        -Message "La gate amputée doit nommer l'écart de comptage des tests."
}
finally {
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
}

Write-Host "Test d'acceptation des commandes de validation M-000: OK"
