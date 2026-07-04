$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m006_precondition.ps1"
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m006_precondition_unit_" + [System.Guid]::NewGuid().ToString("N"))
$expectedBranch = "codex/milestone-m006-claims-verifiables"
$postMergeM007Branch = "codex/milestone-m007-reponse-documentaire-verifiee"
$postMergeM008Branch = "codex/milestone-m008-conversation-produit"
$postMergeM009Branch = "codex/milestone-m009-recherche-approfondie"
$postMergeM010Branch = "codex/milestone-m010-strategie-candidate-attribuee"
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

    Invoke-GitCommand -ProjectRoot $ProjectRoot -Arguments @("-c", "core.autocrlf=false", "-c", "user.email=m006@example.test", "-c", "user.name=M006", "add", ".")
    Invoke-GitCommand -ProjectRoot $ProjectRoot -Arguments @("-c", "core.autocrlf=false", "-c", "user.email=m006@example.test", "-c", "user.name=M006", "commit", "-m", $Message)
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
        [bool] $IncludeM004Artifacts,

        [Parameter(Mandatory = $true)]
        [bool] $IncludeM005Artifacts
    )

    $projectRoot = Join-Path $temporaryRoot $Name
    New-Item -ItemType Directory -Path $projectRoot -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "scripts") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs/governance") -Force | Out-Null

    Copy-Item -LiteralPath $validatorPath -Destination (Join-Path $projectRoot "scripts/validate_m006_precondition.ps1")
    New-ScriptFile -Path (Join-Path $projectRoot "scripts/test.ps1") -Content $TestGateContent
    New-ScriptFile -Path (Join-Path $projectRoot "scripts/lint.ps1") -Content $LintGateContent

    if ($IncludeM004Artifacts) {
        New-ScriptFile -Path (Join-Path $projectRoot "docs/tasks/milestone_004/0001_verifier_precondition_green.md") -Content "# M-004"
    }

    if ($IncludeM005Artifacts) {
        New-ScriptFile -Path (Join-Path $projectRoot "docs/tasks/milestone_005/0001_verifier_precondition_green.md") -Content "# M-005"
        New-ScriptFile -Path (Join-Path $projectRoot "docs/specs/m005_projection_connaissance_recherchable.md") -Content "# Spécification M-005"
        New-ScriptFile -Path (Join-Path $projectRoot "tests/m005/validate_m005_precondition_acceptance.ps1") -Content "# Test M-005"
        New-ScriptFile -Path (Join-Path $projectRoot "docs/governance/m005_precondition_green.md") -Content "# Rapport M-005 GREEN"
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
    Commit-TemporaryProject -ProjectRoot $ProjectRoot -Message "baseline m006 precondition"
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

    $scriptPath = Join-Path $ProjectRoot "scripts/validate_m006_precondition.ps1"
    if ([string]::IsNullOrWhiteSpace($ReportPathOverride)) {
        $reportPath = Join-Path $ProjectRoot "docs/governance/m006_precondition_green.md"
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
    throw "Validateur de précondition M-006 absent: scripts/validate_m006_precondition.ps1"
}

$greenTestGate = @'
Write-Host "Gate test GREEN: simulation M-006."
'@

$greenLintGate = @'
Write-Host "Gate lint GREEN: simulation M-006."
'@

$redTestGate = @'
Write-Host "Gate test RED: simulation M-006."
exit 1
'@

$emptyTestGate = @'
'@

$slowTestGate = @'
Write-Host "Gate test non concluant: simulation M-006."
Start-Sleep -Seconds 3
Write-Host "Sortie tardive interdite."
'@

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    $m006BranchRoot = New-TemporaryProject -Name "m006-branch" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM004Artifacts $true -IncludeM005Artifacts $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $m006BranchRoot -BranchName $expectedBranch -DivergeMasterReference $false
    $m006BranchResult = Invoke-Validator -ProjectRoot $m006BranchRoot
    Assert-ExitCode -Actual $m006BranchResult.ExitCode -Expected 0 -Message "La précondition doit autoriser explicitement la branche M-006."
    Assert-OutputContains -Output $m006BranchResult.Output -Expected "Branche M-006 autorisée: $expectedBranch" -Message "La branche M-006 doit être nommée."

    $m007BranchRoot = New-TemporaryProject -Name "m007-branch" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM004Artifacts $true -IncludeM005Artifacts $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $m007BranchRoot -BranchName $postMergeM007Branch -DivergeMasterReference $false
    $m007BranchResult = Invoke-Validator -ProjectRoot $m007BranchRoot
    Assert-ExitCode -Actual $m007BranchResult.ExitCode -Expected 0 -Message "La précondition doit autoriser explicitement la branche M-007 post-merge."
    Assert-OutputContains -Output $m007BranchResult.Output -Expected "Branche M-006 autorisée: $postMergeM007Branch" -Message "La branche M-007 autorisée doit être nommée."

    $m008BranchRoot = New-TemporaryProject -Name "m008-branch" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM004Artifacts $true -IncludeM005Artifacts $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $m008BranchRoot -BranchName $postMergeM008Branch -DivergeMasterReference $false
    $m008BranchResult = Invoke-Validator -ProjectRoot $m008BranchRoot
    Assert-ExitCode -Actual $m008BranchResult.ExitCode -Expected 0 -Message "La précondition doit autoriser explicitement la branche M-008 post-merge."
    Assert-OutputContains -Output $m008BranchResult.Output -Expected "Branche M-006 autorisée: $postMergeM008Branch" -Message "La branche M-008 autorisée doit être nommée."

    $m009BranchRoot = New-TemporaryProject -Name "m009-branch" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM004Artifacts $true -IncludeM005Artifacts $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $m009BranchRoot -BranchName $postMergeM009Branch -DivergeMasterReference $false
    $m009BranchResult = Invoke-Validator -ProjectRoot $m009BranchRoot
    Assert-ExitCode -Actual $m009BranchResult.ExitCode -Expected 0 -Message "La précondition doit autoriser explicitement la branche M-009 post-merge."
    Assert-OutputContains -Output $m009BranchResult.Output -Expected "Branche M-006 autorisée: $postMergeM009Branch" -Message "La branche M-009 autorisée doit être nommée."

    $m010BranchRoot = New-TemporaryProject -Name "m010-branch" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM004Artifacts $true -IncludeM005Artifacts $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $m010BranchRoot -BranchName $postMergeM010Branch -DivergeMasterReference $false
    $m010BranchResult = Invoke-Validator -ProjectRoot $m010BranchRoot
    Assert-ExitCode -Actual $m010BranchResult.ExitCode -Expected 0 -Message "La précondition doit autoriser explicitement la branche M-010 post-merge."
    Assert-OutputContains -Output $m010BranchResult.Output -Expected "Branche M-006 autorisée" -Message "La sortie doit annoncer une branche M-006 autorisée."
    Assert-OutputContains -Output $m010BranchResult.Output -Expected $postMergeM010Branch -Message "La branche M-010 autorisée doit être nommée."

    $masterBranchRoot = New-TemporaryProject -Name "master-branch" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM004Artifacts $true -IncludeM005Artifacts $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $masterBranchRoot -BranchName $masterBranch -DivergeMasterReference $false
    $masterBranchResult = Invoke-Validator -ProjectRoot $masterBranchRoot
    Assert-ExitCode -Actual $masterBranchResult.ExitCode -Expected 0 -Message "La précondition doit autoriser explicitement master."
    Assert-OutputContains -Output $masterBranchResult.Output -Expected "Branche M-006 autorisée: master" -Message "La branche master autorisée doit être nommée."

    $missingM004Root = New-TemporaryProject -Name "missing-m004" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM004Artifacts $false -IncludeM005Artifacts $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $missingM004Root -BranchName $expectedBranch -DivergeMasterReference $false
    $missingM004Result = Invoke-Validator -ProjectRoot $missingM004Root
    Assert-ExitCode -Actual $missingM004Result.ExitCode -Expected 1 -Message "La précondition doit refuser une preuve M-004 absente."
    Assert-OutputContains `
        -Output $missingM004Result.Output `
        -Expected "Milestone ou preuve amont absent de master: docs/tasks/milestone_004" `
        -Message "Le RED M-004 absent doit nommer le dossier manquant."

    $missingM005Root = New-TemporaryProject -Name "missing-m005" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM004Artifacts $true -IncludeM005Artifacts $false
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $missingM005Root -BranchName $expectedBranch -DivergeMasterReference $false
    $missingM005Result = Invoke-Validator -ProjectRoot $missingM005Root
    Assert-ExitCode -Actual $missingM005Result.ExitCode -Expected 1 -Message "La précondition doit refuser une preuve M-005 absente."
    Assert-OutputContains `
        -Output $missingM005Result.Output `
        -Expected "Milestone ou preuve amont absent de master: docs/tasks/milestone_005" `
        -Message "Le RED M-005 absent doit nommer le dossier manquant."

    $divergedMasterRoot = New-TemporaryProject -Name "diverged-master-reference" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM004Artifacts $true -IncludeM005Artifacts $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $divergedMasterRoot -BranchName $expectedBranch -DivergeMasterReference $true
    $divergedMasterResult = Invoke-Validator -ProjectRoot $divergedMasterRoot
    Assert-ExitCode -Actual $divergedMasterResult.ExitCode -Expected 1 -Message "La précondition doit refuser une référence master divergente."
    Assert-OutputContains `
        -Output $divergedMasterResult.Output `
        -Expected "Référence master divergente entre master et origin/master." `
        -Message "La divergence master doit être explicite."

    $invalidBranchRoot = New-TemporaryProject -Name "invalid-branch" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM004Artifacts $true -IncludeM005Artifacts $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $invalidBranchRoot -BranchName $invalidBranch -DivergeMasterReference $false
    $invalidBranchResult = Invoke-Validator -ProjectRoot $invalidBranchRoot
    Assert-ExitCode -Actual $invalidBranchResult.ExitCode -Expected 1 -Message "La précondition doit refuser une branche non autorisée."
    Assert-OutputContains `
        -Output $invalidBranchResult.Output `
        -Expected "Branche courante invalide. Autorisées:" `
        -Message "La branche non autorisée doit être nommée explicitement."
    Assert-OutputContains -Output $invalidBranchResult.Output -Expected $postMergeM010Branch -Message "La branche M-010 autorisée doit être listée."
    Assert-OutputContains -Output $invalidBranchResult.Output -Expected $invalidBranch -Message "La branche refusée doit être nommée."

    $redGateRoot = New-TemporaryProject -Name "red-gate" -TestGateContent $redTestGate -LintGateContent $greenLintGate -IncludeM004Artifacts $true -IncludeM005Artifacts $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $redGateRoot -BranchName $expectedBranch -DivergeMasterReference $false
    $redGateResult = Invoke-Validator -ProjectRoot $redGateRoot
    Assert-ExitCode -Actual $redGateResult.ExitCode -Expected 1 -Message "La précondition doit refuser une gate RED."
    Assert-OutputContains -Output $redGateResult.Output -Expected "Gate test RED" -Message "La sortie de gate RED doit être conservée."
    Assert-OutputContains -Output $redGateResult.Output -Expected "Gate M-006 RED: test" -Message "Le validateur doit nommer la gate RED."

    $emptyOutputRoot = New-TemporaryProject -Name "empty-test-output" -TestGateContent $emptyTestGate -LintGateContent $greenLintGate -IncludeM004Artifacts $true -IncludeM005Artifacts $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $emptyOutputRoot -BranchName $expectedBranch -DivergeMasterReference $false
    $emptyOutputResult = Invoke-Validator -ProjectRoot $emptyOutputRoot
    Assert-ExitCode -Actual $emptyOutputResult.ExitCode -Expected 1 -Message "La précondition doit refuser un statut GREEN déclaré sans preuve."
    Assert-OutputContains `
        -Output $emptyOutputResult.Output `
        -Expected "Gate M-006 RED: test sans sortie." `
        -Message "La sortie vide doit être nommée explicitement."

    $timeoutGateRoot = New-TemporaryProject -Name "timeout-test-output" -TestGateContent $slowTestGate -LintGateContent $greenLintGate -IncludeM004Artifacts $true -IncludeM005Artifacts $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $timeoutGateRoot -BranchName $expectedBranch -DivergeMasterReference $false
    $timeoutGateResult = Invoke-Validator -ProjectRoot $timeoutGateRoot -GateTimeoutSeconds 1
    Assert-ExitCode -Actual $timeoutGateResult.ExitCode -Expected 1 -Message "La précondition doit refuser un scripts/test.ps1 non concluant."
    Assert-OutputContains `
        -Output $timeoutGateResult.Output `
        -Expected "Gate M-006 RED: test non concluant après 1 seconde(s)." `
        -Message "Le timeout doit être nommé explicitement."

    $outsideReportRoot = New-TemporaryProject -Name "outside-report-path" -TestGateContent $greenTestGate -LintGateContent $greenLintGate -IncludeM004Artifacts $true -IncludeM005Artifacts $true
    Initialize-ProjectWithMasterAndBranch -ProjectRoot $outsideReportRoot -BranchName $expectedBranch -DivergeMasterReference $false
    $outsideReportPath = Join-Path $temporaryRoot "m006_precondition_outside.md"
    $outsideReportResult = Invoke-Validator -ProjectRoot $outsideReportRoot -ReportPathOverride $outsideReportPath
    Assert-ExitCode -Actual $outsideReportResult.ExitCode -Expected 1 -Message "La précondition doit refuser un rapport hors dépôt."
    Assert-OutputContains `
        -Output $outsideReportResult.Output `
        -Expected "Chemin de rapport M-006 hors dépôt:" `
        -Message "Le chemin hors dépôt doit être nommé explicitement."
}
finally {
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
}

Write-Host "Tests unitaires du validateur de précondition M-006: OK"
