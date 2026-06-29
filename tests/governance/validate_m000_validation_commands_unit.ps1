$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$aggregatorPath = Join-Path $repoRoot "scripts/m000_validation_gate.ps1"
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m000_validation_commands_unit_" + [System.Guid]::NewGuid().ToString("N"))
$eAcute = [char] 0x00E9

function New-ScriptFile {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [string] $Content
    )

    $parent = Split-Path -Parent $Path
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    Set-Content -Encoding UTF8 -LiteralPath $Path -Value $Content
}

function New-TemporaryProject {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name,

        [Parameter(Mandatory = $true)]
        [string] $WrapperContent
    )

    $projectRoot = Join-Path $temporaryRoot $Name
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "scripts") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "tests/governance") -Force | Out-Null
    Copy-Item -LiteralPath $aggregatorPath -Destination (Join-Path $projectRoot "scripts/m000_validation_gate.ps1")

    New-ScriptFile -Path (Join-Path $projectRoot "scripts/ok_validation.ps1") -Content "Write-Host 'validation ok'"
    New-ScriptFile -Path (Join-Path $projectRoot "tests/governance/ok_test.ps1") -Content "Write-Host 'test ok'"
    New-ScriptFile -Path (Join-Path $projectRoot "scripts/failing_validation.ps1") -Content "throw 'validation ko'"
    New-ScriptFile -Path (Join-Path $projectRoot "scripts/test.ps1") -Content $WrapperContent

    return $projectRoot
}

function Invoke-TestGate {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProjectRoot
    )

    $scriptPath = Join-Path $ProjectRoot "scripts/test.ps1"
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

if (-not (Test-Path -LiteralPath $aggregatorPath -PathType Leaf)) {
    throw "Agrégateur de validation M-000 absent: scripts/m000_validation_gate.ps1"
}

$aggregatorContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $aggregatorPath
if ($aggregatorContent.Contains("GetEncoding(1252)") -or $aggregatorContent.Contains("UTF8.GetString")) {
    throw "L'agrégateur M-000 ne doit pas réparer silencieusement l'encodage des sorties."
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    $successWrapper = @'
$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
. (Join-Path $PSScriptRoot "m000_validation_gate.ps1")
$validationCommands = @(
    @{ Path = "scripts/ok_validation.ps1"; Arguments = @() }
)
$testCommands = @(
    @{ Path = "tests/governance/ok_test.ps1"; Arguments = @() }
)
$expectedValidationPaths = @("scripts/ok_validation.ps1")
$expectedTestPaths = @("tests/governance/ok_test.ps1")
Invoke-M000ValidationGate -GateName "test" -RepositoryRoot $repoRoot -ValidationCommands $validationCommands -TestCommands $testCommands -ExpectedValidationCount 1 -ExpectedTestCount 1 -ExpectedValidationPaths $expectedValidationPaths -ExpectedTestPaths $expectedTestPaths
'@
    $successProjectRoot = New-TemporaryProject -Name "success" -WrapperContent $successWrapper
    $successResult = Invoke-TestGate -ProjectRoot $successProjectRoot
    Assert-ExitCode -Actual $successResult.ExitCode -Expected 0 -Message "L'agrégateur doit réussir quand toutes les commandes passent."
    Assert-OutputContains -Output $successResult.Output -Expected "Validation GREEN: scripts/ok_validation.ps1" -Message "La validation réussie doit être annoncée."
    Assert-OutputContains -Output $successResult.Output -Expected "Test GREEN: tests/governance/ok_test.ps1" -Message "Le test réussi doit être annoncé."
    Assert-OutputContains -Output $successResult.Output -Expected "Gate test GREEN: 1 validation(s), 1 test(s)." -Message "Le résumé GREEN doit être stable."

    $missingWrapper = @'
$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
. (Join-Path $PSScriptRoot "m000_validation_gate.ps1")
$validationCommands = @(
    @{ Path = "scripts/missing_validation.ps1"; Arguments = @() }
)
$testCommands = @()
$expectedValidationPaths = @("scripts/missing_validation.ps1")
$expectedTestPaths = @()
Invoke-M000ValidationGate -GateName "test" -RepositoryRoot $repoRoot -ValidationCommands $validationCommands -TestCommands $testCommands -ExpectedValidationCount 1 -ExpectedTestCount 0 -ExpectedValidationPaths $expectedValidationPaths -ExpectedTestPaths $expectedTestPaths
'@
    $missingProjectRoot = New-TemporaryProject -Name "missing" -WrapperContent $missingWrapper
    $missingResult = Invoke-TestGate -ProjectRoot $missingProjectRoot
    Assert-ExitCode -Actual $missingResult.ExitCode -Expected 1 -Message "Une validation absente doit échouer."
    Assert-OutputContains -Output $missingResult.Output -Expected "Gate test RED" -Message "La gate doit annoncer son état RED."
    Assert-OutputContains -Output $missingResult.Output -Expected "Validation requise absente: scripts/missing_validation.ps1" -Message "La validation absente doit être ciblée."

    $failingWrapper = @'
$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
. (Join-Path $PSScriptRoot "m000_validation_gate.ps1")
$validationCommands = @(
    @{ Path = "scripts/failing_validation.ps1"; Arguments = @() }
)
$testCommands = @()
$expectedValidationPaths = @("scripts/failing_validation.ps1")
$expectedTestPaths = @()
Invoke-M000ValidationGate -GateName "test" -RepositoryRoot $repoRoot -ValidationCommands $validationCommands -TestCommands $testCommands -ExpectedValidationCount 1 -ExpectedTestCount 0 -ExpectedValidationPaths $expectedValidationPaths -ExpectedTestPaths $expectedTestPaths
'@
    $failingProjectRoot = New-TemporaryProject -Name "failing" -WrapperContent $failingWrapper
    $failingResult = Invoke-TestGate -ProjectRoot $failingProjectRoot
    Assert-ExitCode -Actual $failingResult.ExitCode -Expected 1 -Message "Une validation échouée doit échouer."
    Assert-OutputContains -Output $failingResult.Output -Expected "Gate test RED" -Message "La gate doit annoncer son état RED."
    Assert-OutputContains `
        -Output $failingResult.Output `
        -Expected "Validation $($eAcute)chou$($eAcute)e: scripts/failing_validation.ps1" `
        -Message "La validation échouée doit être ciblée."

    $emptyWrapper = @'
$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
. (Join-Path $PSScriptRoot "m000_validation_gate.ps1")
$validationCommands = @()
$testCommands = @()
$expectedValidationPaths = @()
$expectedTestPaths = @()
Invoke-M000ValidationGate -GateName "test" -RepositoryRoot $repoRoot -ValidationCommands $validationCommands -TestCommands $testCommands -ExpectedValidationCount 0 -ExpectedTestCount 0 -ExpectedValidationPaths $expectedValidationPaths -ExpectedTestPaths $expectedTestPaths
'@
    $emptyProjectRoot = New-TemporaryProject -Name "empty" -WrapperContent $emptyWrapper
    $emptyResult = Invoke-TestGate -ProjectRoot $emptyProjectRoot
    Assert-ExitCode -Actual $emptyResult.ExitCode -Expected 1 -Message "Une gate sans commande requise doit échouer."
    Assert-OutputContains -Output $emptyResult.Output -Expected "Gate test RED" -Message "La gate vide doit annoncer son état RED."
    Assert-OutputContains -Output $emptyResult.Output -Expected "Gate test sans commande requise." -Message "La gate vide doit être refusée explicitement."

    $duplicateWrapper = @'
$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
. (Join-Path $PSScriptRoot "m000_validation_gate.ps1")
$validationCommands = @(
    @{ Path = "scripts/ok_validation.ps1"; Arguments = @() },
    @{ Path = "scripts/ok_validation.ps1"; Arguments = @() }
)
$testCommands = @()
$expectedValidationPaths = @("scripts/ok_validation.ps1", "scripts/failing_validation.ps1")
$expectedTestPaths = @()
Invoke-M000ValidationGate -GateName "test" -RepositoryRoot $repoRoot -ValidationCommands $validationCommands -TestCommands $testCommands -ExpectedValidationCount 2 -ExpectedTestCount 0 -ExpectedValidationPaths $expectedValidationPaths -ExpectedTestPaths $expectedTestPaths
'@
    $duplicateProjectRoot = New-TemporaryProject -Name "duplicate" -WrapperContent $duplicateWrapper
    $duplicateResult = Invoke-TestGate -ProjectRoot $duplicateProjectRoot
    Assert-ExitCode -Actual $duplicateResult.ExitCode -Expected 1 -Message "Une gate avec doublon à comptage correct doit échouer."
    Assert-OutputContains -Output $duplicateResult.Output -Expected "Gate test RED" -Message "La gate avec doublon doit annoncer son état RED."
    Assert-OutputContains -Output $duplicateResult.Output -Expected "Validation dupliqué" -Message "La gate doit nommer le doublon de validation."
}
finally {
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
}

Write-Host "Tests unitaires des commandes de validation M-000: OK"
