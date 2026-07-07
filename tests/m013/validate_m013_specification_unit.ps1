$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m013_specification.ps1"
$temporaryRoot = Join-Path $repoRoot (".tmp/ost_m013_specification_unit_" + [System.Guid]::NewGuid().ToString("N"))

function New-ValidM013SpecificationContent {
    $canonicalSpecPath = Join-Path $repoRoot "docs/specs/m013_durcissement_acceptation_v1.md"
    if (-not (Test-Path -LiteralPath $canonicalSpecPath -PathType Leaf)) {
        throw "Spécification canonique M-013 absente pour le fixture unitaire: docs/specs/m013_durcissement_acceptation_v1.md"
    }

    return Get-Content -Raw -Encoding UTF8 -LiteralPath $canonicalSpecPath
}

function Invoke-M013SpecificationValidator {
    param(
        [Parameter(Mandatory = $true)]
        [string] $SpecPath
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $validatorPath -Path $SpecPath 2>&1
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

function New-TemporarySpec {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name,

        [Parameter(Mandatory = $true)]
        [string] $Content
    )

    $specPath = Join-Path $temporaryRoot "$Name.md"
    $Content | Set-Content -Encoding UTF8 -LiteralPath $specPath
    return $specPath
}

function Assert-M013RejectedSpec {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name,

        [Parameter(Mandatory = $true)]
        [string] $Content,

        [Parameter(Mandatory = $true)]
        [string] $ExpectedOutput,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    $specPath = New-TemporarySpec -Name $Name -Content $Content
    $result = Invoke-M013SpecificationValidator -SpecPath $specPath
    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message $Message
    Assert-OutputContains -Output $result.Output -Expected $ExpectedOutput -Message "Le refus doit nommer l'écart attendu."
}

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
    throw "Validateur de spécification M-013 absent: scripts/validate_m013_specification.ps1"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    $validContent = New-ValidM013SpecificationContent
    $validSpecPath = New-TemporarySpec -Name "valid" -Content $validContent
    $validResult = Invoke-M013SpecificationValidator -SpecPath $validSpecPath
    Assert-ExitCode -Actual $validResult.ExitCode -Expected 0 -Message "Une spécification M-013 conforme doit être acceptée."

    Assert-M013RejectedSpec `
        -Name "mission-absente" `
        -Content ($validContent.Replace("## Mission M-013", "## Mission incomplète")) `
        -ExpectedOutput "Section obligatoire absente: ## Mission M-013" `
        -Message "Une mission M-013 absente doit être refusée."

    Assert-M013RejectedSpec `
        -Name "criteres-v1-absents" `
        -Content ($validContent.Replace("## Critères V1 et écarts M-012", "## Critères reportés")) `
        -ExpectedOutput "Section obligatoire absente: ## Critères V1 et écarts M-012" `
        -Message "Les critères V1 doivent être obligatoires."

    Assert-M013RejectedSpec `
        -Name "rapport-m012-absent" `
        -Content ($validContent.Replace("docs/governance/m012_v1_gap_report.md", "docs/governance/rapport_v1.md")) `
        -ExpectedOutput "Rapport M-012 obligatoire absent: docs/governance/m012_v1_gap_report.md" `
        -Message "Le rapport d'écarts M-012 doit être obligatoire."

    Assert-M013RejectedSpec `
        -Name "statuts-ecarts-absents" `
        -Content ($validContent.Replace("## Statuts d'écarts V1", "## Écarts sans statut")) `
        -ExpectedOutput "Section obligatoire absente: ## Statuts d'écarts V1" `
        -Message "Les statuts d'écarts V1 doivent être obligatoires."

    Assert-M013RejectedSpec `
        -Name "securite-reseau-absente" `
        -Content ($validContent.Replace("## Sécurité réseau Spark", "## Sécurité générale")) `
        -ExpectedOutput "Section obligatoire absente: ## Sécurité réseau Spark" `
        -Message "La sécurité réseau Spark doit être obligatoire."

    Assert-M013RejectedSpec `
        -Name "sauvegarde-absente" `
        -Content ($validContent.Replace("BackupRestoreDrill", "RestoreDrill")) `
        -ExpectedOutput "Artefact M-013 attendu absent: BackupRestoreDrill" `
        -Message "La sauvegarde doit être obligatoire."

    Assert-M013RejectedSpec `
        -Name "restauration-absente" `
        -Content ($validContent.Replace("restore_test_result", "restore_result")) `
        -ExpectedOutput "Preuve de restauration absente: restore_test_result" `
        -Message "La restauration testée doit être obligatoire."

    Assert-M013RejectedSpec `
        -Name "retention-absente" `
        -Content ($validContent.Replace("RetentionPolicy", "ConservationPolicy")) `
        -ExpectedOutput "Artefact M-013 attendu absent: RetentionPolicy" `
        -Message "La rétention doit être obligatoire."

    Assert-M013RejectedSpec `
        -Name "monitoring-absent" `
        -Content ($validContent.Replace("LocalMonitoringProfile", "MonitoringProfile")) `
        -ExpectedOutput "Artefact M-013 attendu absent: LocalMonitoringProfile" `
        -Message "Le monitoring local doit être obligatoire."

    Assert-M013RejectedSpec `
        -Name "runbooks-absents" `
        -Content ($validContent.Replace("Runbook", "GuideExploitant")) `
        -ExpectedOutput "Artefact M-013 attendu absent: Runbook" `
        -Message "Les runbooks doivent être obligatoires."

    Assert-M013RejectedSpec `
        -Name "documentation-utilisateur-absente" `
        -Content ($validContent.Replace("## Documentation utilisateur", "## Documentation interne")) `
        -ExpectedOutput "Section obligatoire absente: ## Documentation utilisateur" `
        -Message "La documentation utilisateur doit être obligatoire."

    Assert-M013RejectedSpec `
        -Name "anti-patterns-absents" `
        -Content ($validContent.Replace("## Anti-patterns interdits V1", "## Revue technique")) `
        -ExpectedOutput "Section obligatoire absente: ## Anti-patterns interdits V1" `
        -Message "Les anti-patterns interdits doivent être obligatoires."

    Assert-M013RejectedSpec `
        -Name "rapport-acceptation-absent" `
        -Content ($validContent.Replace("V1AcceptanceReport", "AcceptanceReport")) `
        -ExpectedOutput "Artefact M-013 attendu absent: V1AcceptanceReport" `
        -Message "Le rapport d'acceptation V1 doit être obligatoire."

    Assert-M013RejectedSpec `
        -Name "adr-manquante" `
        -Content ($validContent.Replace("ADR-007", "ADR-999")) `
        -ExpectedOutput "ADR applicable absente: ADR-007" `
        -Message "Les ADR applicables doivent être obligatoires."
}
finally {
    if (Test-Path -LiteralPath $temporaryRoot) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}

Write-Host "Tests unitaires du validateur de spécification M-013: OK"
