$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m013_config_traceability.ps1"
$temporaryRoot = Join-Path $repoRoot (".tmp/ost_m013_config_traceability_unit_" + [System.Guid]::NewGuid().ToString("N"))
$outsideRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_config_traceability_outside_" + [System.Guid]::NewGuid().ToString("N"))

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

function Invoke-Validator {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProjectRoot
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & powershell `
            -NoProfile `
            -ExecutionPolicy Bypass `
            -File $validatorPath `
            -MatrixPath (Join-Path $ProjectRoot "docs/traceability/matrix.md") `
            -AuditPath (Join-Path $ProjectRoot "docs/governance/m013_config_audit.md") `
            -TestGatePath (Join-Path $ProjectRoot "scripts/test.ps1") `
            -LintGatePath (Join-Path $ProjectRoot "scripts/lint.ps1") `
            -EnvironmentValidatorPath (Join-Path $ProjectRoot "scripts/validate_m013_config_environment.ps1") `
            -RunbookPath (Join-Path $ProjectRoot "docs/runbooks/configuration_applicative.md") `
            -JournalPath (Join-Path $ProjectRoot "docs/tasks/milestone_013-config/journal.md") 2>&1
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    return [pscustomobject] @{
        ExitCode = $LASTEXITCODE
        Output = ($output -join "`n")
    }
}

function New-FixtureProject {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name
    )

    $projectRoot = Join-Path $temporaryRoot $Name
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs/traceability") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs/governance") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs/runbooks") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs/tasks/milestone_013-config") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "scripts") -Force | Out-Null

    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/traceability/matrix.md") -Destination (Join-Path $projectRoot "docs/traceability/matrix.md")
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/governance/m013_config_audit.md") -Destination (Join-Path $projectRoot "docs/governance/m013_config_audit.md")
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/runbooks/configuration_applicative.md") -Destination (Join-Path $projectRoot "docs/runbooks/configuration_applicative.md")
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/tasks/milestone_013-config/journal.md") -Destination (Join-Path $projectRoot "docs/tasks/milestone_013-config/journal.md")
    Copy-Item -LiteralPath (Join-Path $repoRoot "scripts/test.ps1") -Destination (Join-Path $projectRoot "scripts/test.ps1")
    Copy-Item -LiteralPath (Join-Path $repoRoot "scripts/lint.ps1") -Destination (Join-Path $projectRoot "scripts/lint.ps1")
    Copy-Item -LiteralPath (Join-Path $repoRoot "scripts/validate_m013_config_environment.ps1") -Destination (Join-Path $projectRoot "scripts/validate_m013_config_environment.ps1")

    return $projectRoot
}

function Assert-ValidatorFails {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name,

        [Parameter(Mandatory = $true)]
        [scriptblock] $Mutate,

        [Parameter(Mandatory = $true)]
        [string] $ExpectedMessage
    )

    $projectRoot = New-FixtureProject -Name $Name
    & $Mutate $projectRoot
    $result = Invoke-Validator -ProjectRoot $projectRoot

    if ($result.ExitCode -eq 0) {
        throw "Le cas RED $Name doit échouer."
    }

    Assert-OutputContains `
        -Output $result.Output `
        -Expected $ExpectedMessage `
        -Message "Le cas RED $Name doit nommer la règle violée."
}

function Remove-TreeWithRetry {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    $lastError = $null
    for ($attempt = 1; $attempt -le 5; $attempt++) {
        try {
            Remove-Item -LiteralPath $Path -Recurse -Force
            return
        }
        catch {
            $lastError = $_
            Start-Sleep -Milliseconds 250
        }
    }
    throw $lastError
}

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
    throw "Validateur de traçabilité M13-config absent: scripts/validate_m013_config_traceability.ps1"
}

$validatorContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $validatorPath
if ($validatorContent.Contains("42ef2be63")) {
    throw "Le validateur M13-config ne doit pas dépendre d'un SHA Git volatile."
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    $validProjectRoot = New-FixtureProject -Name "valid"
    $validResult = Invoke-Validator -ProjectRoot $validProjectRoot
    if ($validResult.ExitCode -ne 0) {
        throw "La fixture valide M13-config doit réussir. Sortie: $($validResult.Output)"
    }
    Assert-OutputContains `
        -Output $validResult.Output `
        -Expected "Traçabilité M13-config valide" `
        -Message "La fixture valide doit annoncer le GREEN M13-config."
    $validTestGateContent = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $validProjectRoot "scripts/test.ps1")
    if ($validTestGateContent.Contains('@{ Path = "scripts/validate_m013_reality.ps1"')) {
        throw "La gate test déterministe ne doit pas lancer M13-reality live sans configuration locale explicite."
    }

    New-Item -ItemType Directory -Path $outsideRoot | Out-Null
    $outsideMatrixPath = Join-Path $outsideRoot "outside_matrix.md"
    Copy-Item -LiteralPath (Join-Path $validProjectRoot "docs/traceability/matrix.md") -Destination $outsideMatrixPath
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $outsideOutput = & powershell `
            -NoProfile `
            -ExecutionPolicy Bypass `
            -File $validatorPath `
            -MatrixPath $outsideMatrixPath `
            -AuditPath (Join-Path $validProjectRoot "docs/governance/m013_config_audit.md") `
            -TestGatePath (Join-Path $validProjectRoot "scripts/test.ps1") `
            -LintGatePath (Join-Path $validProjectRoot "scripts/lint.ps1") `
            -EnvironmentValidatorPath (Join-Path $validProjectRoot "scripts/validate_m013_config_environment.ps1") `
            -RunbookPath (Join-Path $validProjectRoot "docs/runbooks/configuration_applicative.md") `
            -JournalPath (Join-Path $validProjectRoot "docs/tasks/milestone_013-config/journal.md") 2>&1
        $outsideExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if ($outsideExitCode -eq 0) {
        throw "Un chemin absolu hors dépôt doit être refusé."
    }
    Assert-OutputContains `
        -Output ($outsideOutput -join "`n") `
        -Expected "Chemin hors dépôt interdit (matrix)" `
        -Message "Le chemin hors dépôt doit être nommé."

    Assert-ValidatorFails `
        -Name "missing-requirement" `
        -ExpectedMessage "Exigence M13-config absente: REQ-M013-CONFIG-008" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/traceability/matrix.md"
            $lines = Get-Content -Encoding UTF8 -LiteralPath $path
            $lines | Where-Object { -not $_.StartsWith("| REQ-M013-CONFIG-008 |") } | Set-Content -Encoding UTF8 -LiteralPath $path
        }

    Assert-ValidatorFails `
        -Name "missing-audit-proof" `
        -ExpectedMessage "Audit M13-config sans preuve: REQ-M013-CONFIG-003" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/governance/m013_config_audit.md"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace("REQ-M013-CONFIG-003", "REQ-M013-CONFIG-003-ABSENTE") |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }

    Assert-ValidatorFails `
        -Name "test-gate-missing" `
        -ExpectedMessage "Gate test sans validation M13-config: scripts/validate_m013_config_traceability.ps1" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "scripts/test.ps1"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace("scripts/validate_m013_config_traceability.ps1", "scripts/validate_m013_config_traceability_absent.ps1") |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }

    Assert-ValidatorFails `
        -Name "lint-gate-missing" `
        -ExpectedMessage "Gate lint sans validation M13-config: scripts/validate_m013_config_traceability.ps1" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "scripts/lint.ps1"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace("scripts/validate_m013_config_traceability.ps1", "scripts/validate_m013_config_traceability_absent.ps1") |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }

    Assert-ValidatorFails `
        -Name "audit-cloture-m013" `
        -ExpectedMessage "Audit M13-config ne doit pas déclarer M-013 globalement clôturé" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/governance/m013_config_audit.md"
            Add-Content -Encoding UTF8 -LiteralPath $path -Value "M-013 globalement clôturé"
        }

    Assert-ValidatorFails `
        -Name "audit-v1-acceptee" `
        -ExpectedMessage "Audit M13-config ne doit pas déclarer la V1 acceptée" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/governance/m013_config_audit.md"
            Add-Content -Encoding UTF8 -LiteralPath $path -Value "V1 acceptée"
        }

    Assert-ValidatorFails `
        -Name "environment-gate-missing" `
        -ExpectedMessage "Gate environnement M13-config absente" `
        -Mutate {
            param($projectRoot)
            Remove-Item -LiteralPath (Join-Path $projectRoot "scripts/validate_m013_config_environment.ps1") -Force
        }
}
finally {
    Remove-TreeWithRetry -Path $temporaryRoot
    Remove-TreeWithRetry -Path $outsideRoot
}

Write-Host "Tests unitaires T-008 traçabilité M13-config: OK"
