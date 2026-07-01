$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m008_precondition.ps1"
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m008_precondition_unit_" + [System.Guid]::NewGuid().ToString("N"))
$expectedBranch = "codex/milestone-m008-conversation-produit"
$masterBranch = "master"
$invalidBranch = "codex/milestone-hors-contrat"

function New-ScriptFile {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string] $Content
    )

    $parent = Split-Path -Parent $Path
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    Set-Content -Encoding UTF8 -LiteralPath $Path -Value $Content
}

function Invoke-GitCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProjectRoot,

        [Parameter(Mandatory = $true)]
        [string[]] $Arguments
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    try {
        $output = & git -C $ProjectRoot @Arguments 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if ($exitCode -ne 0) {
        throw "Commande Git impossible dans le dépôt temporaire: git $($Arguments -join ' '). Sortie: $($output -join "`n")"
    }
}

function Get-GitOutput {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProjectRoot,

        [Parameter(Mandatory = $true)]
        [string[]] $Arguments
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    try {
        $output = & git -C $ProjectRoot @Arguments 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if ($exitCode -ne 0) {
        throw "Commande Git impossible dans le dépôt temporaire: git $($Arguments -join ' '). Sortie: $($output -join "`n")"
    }

    return ($output -join "`n").Trim()
}

function Commit-TemporaryProject {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProjectRoot,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    Invoke-GitCommand -ProjectRoot $ProjectRoot -Arguments @("-c", "core.autocrlf=false", "-c", "user.email=m008@example.test", "-c", "user.name=M008", "add", ".")
    Invoke-GitCommand -ProjectRoot $ProjectRoot -Arguments @("-c", "core.autocrlf=false", "-c", "user.email=m008@example.test", "-c", "user.name=M008", "commit", "-m", $Message)
}

function New-TemporaryProject {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name,

        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string] $TestGateContent,

        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string] $LintGateContent,

        [Parameter(Mandatory = $true)]
        [bool] $IncludeM007Artifacts
    )

    $projectRoot = Join-Path $temporaryRoot $Name
    New-Item -ItemType Directory -Path $projectRoot -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "scripts") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs/governance") -Force | Out-Null

    Copy-Item -LiteralPath $validatorPath -Destination (Join-Path $projectRoot "scripts/validate_m008_precondition.ps1")
    New-ScriptFile -Path (Join-Path $projectRoot "scripts/test.ps1") -Content $TestGateContent
    New-ScriptFile -Path (Join-Path $projectRoot "scripts/lint.ps1") -Content $LintGateContent

    if ($IncludeM007Artifacts) {
        New-ScriptFile -Path (Join-Path $projectRoot "docs/tasks/milestone_007/0001_verifier_precondition_green.md") -Content "# M-007"
        New-ScriptFile -Path (Join-Path $projectRoot "docs/specs/m007_reponse_documentaire_verifiee.md") -Content "# Spécification M-007"
        New-ScriptFile -Path (Join-Path $projectRoot "tests/m007/validate_m007_precondition_acceptance.ps1") -Content "# Test M-007"
        New-ScriptFile -Path (Join-Path $projectRoot "docs/governance/m007_precondition_green.md") -Content "# Rapport M-007 GREEN"
    }

    return $projectRoot
}

function Initialize-ProjectWithMasterAndBranch {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProjectRoot,

        [Parameter(Mandatory = $true)]
        [string] $BranchName,

        [Parameter(Mandatory = $true)]
        [bool] $DivergeMasterReference
    )

    Invoke-GitCommand -ProjectRoot $ProjectRoot -Arguments @("init", "-b", "master")
    Commit-TemporaryProject -ProjectRoot $ProjectRoot -Message "baseline m008 precondition"
    $baselineRevision = Get-GitOutput -ProjectRoot $ProjectRoot -Arguments @("rev-parse", "master")
    Invoke-GitCommand -ProjectRoot $ProjectRoot -Arguments @("update-ref", "refs/remotes/origin/master", $baselineRevision)

    if ($BranchName -ne $masterBranch) {
        Invoke-GitCommand -ProjectRoot $ProjectRoot -Arguments @("checkout", "-b", $BranchName)
    }

    if ($DivergeMasterReference) {
        Invoke-GitCommand -ProjectRoot $ProjectRoot -Arguments @("checkout", "-b", "origin-master-divergent", "master")
        New-ScriptFile -Path (Join-Path $ProjectRoot "docs/tasks/origin_reference_only.md") -Content "origin master divergé"
        Commit-TemporaryProject -ProjectRoot $ProjectRoot -Message "diverge origin master reference"
        $originRevision = Get-GitOutput -ProjectRoot $ProjectRoot -Arguments @("rev-parse", "HEAD")
        Invoke-GitCommand -ProjectRoot $ProjectRoot -Arguments @("update-ref", "refs/remotes/origin/master", $originRevision)

        if ($BranchName -ne $masterBranch) {
            Invoke-GitCommand -ProjectRoot $ProjectRoot -Arguments @("checkout", $BranchName)
        }
    }
}

function Invoke-Validator {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProjectRoot,

        [Parameter(Mandatory = $false)]
        [string] $ReportPathOverride,

        [Parameter(Mandatory = $false)]
        [int] $GateTimeoutSeconds
    )

    $scriptPath = Join-Path $ProjectRoot "scripts/validate_m008_precondition.ps1"
    if ([string]::IsNullOrWhiteSpace($ReportPathOverride)) {
        $reportPath = Join-Path $ProjectRoot "docs/governance/m008_precondition_green.md"
    }
    else {
        $reportPath = $ReportPathOverride
    }

    $arguments = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $scriptPath, "-Path", $reportPath)
    if ($GateTimeoutSeconds -gt 0) {
        $arguments += @("-GateTimeoutSeconds", [string] $GateTimeoutSeconds)
    }

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    try {
        $output = & powershell @arguments 2>&1
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    return [pscustomobject] @{
        ExitCode = $LASTEXITCODE
        Output = ($output -join "`n")
        ReportPath = $reportPath
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
    throw "Validateur de précondition M-008 absent: scripts/validate_m008_precondition.ps1"
}

$greenTestGate = @'
Write-Host "Gate test GREEN: simulation M-008."
'@

$greenLintGate = @'
Write-Host "Gate lint GREEN: simulation M-008."
'@

$redTestGate = @'
Write-Host "Gate test RED: simulation M-008."
exit 1
'@

$emptyTestGate = @'
'@

$slowTestGate = @'
Write-Host "Gate test non concluant: simulation M-008."
Start-Sleep -Seconds 3
Write-Host "Sortie tardive interdite."
'@

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    $m008BranchRoot = New-TemporaryProject -Name "m008-branch" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM007Artifacts $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $m008BranchRoot -BranchName $expectedBranch -DivergeMasterReference $false
    $m008BranchResult = Invoke-Validator -ProjectRoot $m008BranchRoot
    Assert-ExitCode -Actual $m008BranchResult.ExitCode -Expected 0 -Message "La précondition doit autoriser explicitement la branche M-008."
    Assert-OutputContains -Output $m008BranchResult.Output -Expected "Branche M-008 autorisée: $expectedBranch" -Message "La branche M-008 doit être nommée."

    $masterBranchRoot = New-TemporaryProject -Name "master-branch" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM007Artifacts $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $masterBranchRoot -BranchName $masterBranch -DivergeMasterReference $false
    $masterBranchResult = Invoke-Validator -ProjectRoot $masterBranchRoot
    Assert-ExitCode -Actual $masterBranchResult.ExitCode -Expected 0 -Message "La précondition doit autoriser explicitement master."
    Assert-OutputContains -Output $masterBranchResult.Output -Expected "Branche M-008 autorisée: master" -Message "La branche master autorisée doit être nommée."

    $missingM007Root = New-TemporaryProject -Name "missing-m007" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM007Artifacts $false
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $missingM007Root -BranchName $expectedBranch -DivergeMasterReference $false
    $missingM007Result = Invoke-Validator -ProjectRoot $missingM007Root
    Assert-ExitCode -Actual $missingM007Result.ExitCode -Expected 1 -Message "La précondition doit refuser une preuve M-007 absente."
    Assert-OutputContains `
        -Output $missingM007Result.Output `
        -Expected "Milestone ou preuve amont absent de master: docs/tasks/milestone_007" `
        -Message "Le RED M-007 absent doit nommer le dossier manquant."

    $missingM007SpecRoot = New-TemporaryProject -Name "missing-m007-spec" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM007Artifacts $true
    Remove-Item -LiteralPath (Join-Path $missingM007SpecRoot "docs/specs/m007_reponse_documentaire_verifiee.md") -Force
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $missingM007SpecRoot -BranchName $expectedBranch -DivergeMasterReference $false
    $missingM007SpecResult = Invoke-Validator -ProjectRoot $missingM007SpecRoot
    Assert-ExitCode -Actual $missingM007SpecResult.ExitCode -Expected 1 -Message "La précondition doit refuser une spécification M-007 absente."
    Assert-OutputContains `
        -Output $missingM007SpecResult.Output `
        -Expected "Milestone ou preuve amont absent de master: docs/specs/m007_reponse_documentaire_verifiee.md" `
        -Message "Le RED spécification M-007 absent doit nommer le fichier manquant."

    $divergedMasterRoot = New-TemporaryProject -Name "diverged-master-reference" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM007Artifacts $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $divergedMasterRoot -BranchName $expectedBranch -DivergeMasterReference $true
    $divergedMasterResult = Invoke-Validator -ProjectRoot $divergedMasterRoot
    Assert-ExitCode -Actual $divergedMasterResult.ExitCode -Expected 1 -Message "La précondition doit refuser une référence master divergente."
    Assert-OutputContains `
        -Output $divergedMasterResult.Output `
        -Expected "Référence master divergente entre master et origin/master." `
        -Message "La divergence master doit être explicite."

    $invalidBranchRoot = New-TemporaryProject -Name "invalid-branch" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM007Artifacts $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $invalidBranchRoot -BranchName $invalidBranch -DivergeMasterReference $false
    $invalidBranchResult = Invoke-Validator -ProjectRoot $invalidBranchRoot
    Assert-ExitCode -Actual $invalidBranchResult.ExitCode -Expected 1 -Message "La précondition doit refuser une branche non autorisée."
    Assert-OutputContains `
        -Output $invalidBranchResult.Output `
        -Expected "Branche courante invalide. Autorisées: master, $expectedBranch. Obtenu: $invalidBranch" `
        -Message "La branche non autorisée doit être nommée explicitement."

    $redGateRoot = New-TemporaryProject -Name "red-gate" -TestGateContent $redTestGate -LintGateContent $greenLintGate -IncludeM007Artifacts $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $redGateRoot -BranchName $expectedBranch -DivergeMasterReference $false
    $redGateResult = Invoke-Validator -ProjectRoot $redGateRoot
    Assert-ExitCode -Actual $redGateResult.ExitCode -Expected 1 -Message "La précondition doit refuser une gate RED."
    Assert-OutputContains -Output $redGateResult.Output -Expected "Gate test RED" -Message "La sortie de gate RED doit être conservée."
    Assert-OutputContains -Output $redGateResult.Output -Expected "Gate M-008 RED: test" -Message "Le validateur doit nommer la gate RED."

    $emptyOutputRoot = New-TemporaryProject -Name "empty-test-output" -TestGateContent $emptyTestGate -LintGateContent $greenLintGate -IncludeM007Artifacts $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $emptyOutputRoot -BranchName $expectedBranch -DivergeMasterReference $false
    $emptyOutputResult = Invoke-Validator -ProjectRoot $emptyOutputRoot
    Assert-ExitCode -Actual $emptyOutputResult.ExitCode -Expected 1 -Message "La précondition doit refuser un statut GREEN déclaré sans preuve."
    Assert-OutputContains `
        -Output $emptyOutputResult.Output `
        -Expected "Gate M-008 RED: test sans sortie." `
        -Message "La sortie vide doit être nommée explicitement."

    $timeoutGateRoot = New-TemporaryProject -Name "timeout-test-output" -TestGateContent $slowTestGate -LintGateContent $greenLintGate -IncludeM007Artifacts $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $timeoutGateRoot -BranchName $expectedBranch -DivergeMasterReference $false
    $timeoutGateResult = Invoke-Validator -ProjectRoot $timeoutGateRoot -GateTimeoutSeconds 1
    Assert-ExitCode -Actual $timeoutGateResult.ExitCode -Expected 1 -Message "La précondition doit refuser un scripts/test.ps1 non concluant."
    Assert-OutputContains `
        -Output $timeoutGateResult.Output `
        -Expected "Gate M-008 RED: test non concluant après 1 seconde(s)." `
        -Message "Le timeout doit être nommé explicitement."

    $outsideReportRoot = New-TemporaryProject -Name "outside-report-path" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM007Artifacts $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $outsideReportRoot -BranchName $expectedBranch -DivergeMasterReference $false
    $outsideReportPath = Join-Path $temporaryRoot "m008_precondition_outside.md"
    $outsideReportResult = Invoke-Validator -ProjectRoot $outsideReportRoot -ReportPathOverride $outsideReportPath
    Assert-ExitCode -Actual $outsideReportResult.ExitCode -Expected 1 -Message "La précondition doit refuser un rapport hors dépôt."
    Assert-OutputContains `
        -Output $outsideReportResult.Output `
        -Expected "Chemin de rapport M-008 hors dépôt:" `
        -Message "Le chemin hors dépôt doit être nommé explicitement."
}
finally {
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
}

Write-Host "Tests unitaires du validateur de précondition M-008: OK"
