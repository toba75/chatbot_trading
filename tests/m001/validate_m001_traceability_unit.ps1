$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_traceability.ps1"
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m001_traceability_unit_" + [System.Guid]::NewGuid().ToString("N"))
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

function New-RepositoryFile {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProjectRoot,

        [Parameter(Mandatory = $true)]
        [string] $RelativePath
    )

    $path = Join-Path $ProjectRoot $RelativePath
    $parent = Split-Path -Parent $path
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    "# fichier de test`n" | Set-Content -Encoding UTF8 -LiteralPath $path
}

function New-M001MatrixContent {
    $noNewDecision = "Aucune d$($eAcute)cision structurante nouvelle: la t$([char] 0x00E2)che applique les d$($eAcute)cisions existantes sans en changer le sens."
    $documentedDecision = "D$($eAcute)cision structurante document$($eAcute)e: l'ADR cit$($eAcute)e gouverne l'exigence M-001 sans changement de sens."

    return @"
| Exigence | Source | Statut | Test | Commande | Code | ADR | Justification ADR |
|---|---|---|---|---|---|---|---|
| REQ-M001-001 | docs/tasks/milestone_001/0001_verifier_precondition_green.md | Couvert | tests/governance/validate_task_system_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_task_system.ps1 | scripts/validate_task_system.ps1 | ADR-010 | $documentedDecision |
| REQ-M001-002 | docs/tasks/milestone_001/0002_publier_specification_frontieres_ddd.md | Couvert | tests/m001/validate_m001_specification_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m001_specification.ps1 -Path .\docs\specs\m001_frontieres_ddd_contrats_publies.md | docs/specs/m001_frontieres_ddd_contrats_publies.md | DDD-ADR-001; DDD-ADR-002; DDD-ADR-003 | $documentedDecision |
| REQ-M001-003 | docs/tasks/milestone_001/0003_declarer_contextes_proprietaires.md | Couvert | tests/m001/validate_context_modules_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m001\validate_context_modules_acceptance.ps1 | app/context_registry.json | DDD-ADR-001 | $documentedDecision |
| REQ-M001-004 | docs/tasks/milestone_001/0004_publier_identifiants_contrats_communs.md | Couvert | tests/m001/validate_contract_identity_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m001\validate_contract_identity_acceptance.ps1 | app/contracts/identity.py | Non requise | $noNewDecision |
| REQ-M001-005 | docs/tasks/milestone_001/0005_publier_source_locator_canonical_source_ref.md | Couvert | tests/m001/validate_source_contracts_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m001\validate_source_contracts_acceptance.ps1 | app/contracts/source_references.py | DDD-ADR-003 | $documentedDecision |
| REQ-M001-006 | docs/tasks/milestone_001/0006_publier_contrats_preuves_claims.md | Couvert | tests/m001/validate_evidence_claim_contracts_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m001\validate_evidence_claim_contracts_acceptance.ps1 | app/contracts/evidence_claims.py | DDD-ADR-005 | $documentedDecision |
| REQ-M001-007 | docs/tasks/milestone_001/0007_publier_research_outcome_acl_strategie.md | Couvert | tests/m001/validate_research_outcome_contract_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m001\validate_research_outcome_contract_acceptance.ps1 | app/contracts/research_outcomes.py | DDD-ADR-001; DDD-ADR-002; DDD-ADR-005; DDD-ADR-007 | $documentedDecision |
| REQ-M001-008 | docs/tasks/milestone_001/0008_publier_snapshot_strategie_resultat_experience.md | Couvert | tests/m001/validate_strategy_experiment_contracts_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m001\validate_strategy_experiment_contracts_acceptance.ps1 | app/contracts/strategy_experiments.py | DDD-ADR-009 | $documentedDecision |
| REQ-M001-009 | docs/tasks/milestone_001/0009_publier_enveloppe_evenement_versionnee.md | Couvert | tests/m001/validate_event_envelope_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m001\validate_event_envelope_acceptance.ps1 | app/contracts/event_envelope.py | DDD-ADR-006; DDD-ADR-008 | $documentedDecision |
| REQ-M001-010 | docs/tasks/milestone_001/0010_interdire_couplages_intercontextes.md | Couvert | tests/m001/validate_architecture_boundaries_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m001\validate_architecture_boundaries_acceptance.ps1 | scripts/validate_architecture_boundaries.py | DDD-ADR-001 | $documentedDecision |
| REQ-M001-011 | docs/tasks/milestone_001/0011_relier_m001_tracabilite_gates.md | Couvert | tests/m001/validate_m001_traceability_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability.ps1 | scripts/validate_traceability.ps1 | ADR-010 | $documentedDecision |
"@
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

function Remove-MatrixRow {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [string] $RequirementId
    )

    $lines = [System.Collections.Generic.List[string]] (Get-Content -Encoding UTF8 -LiteralPath $Path)

    for ($index = $lines.Count - 1; $index -ge 0; $index--) {
        $cells = Split-MarkdownRow -Line $lines[$index]
        if (($cells.Count -gt 0) -and ($cells[0] -eq $RequirementId)) {
            $lines.RemoveAt($index)
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
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "scripts") -Force | Out-Null
    Copy-Item -LiteralPath $validatorPath -Destination (Join-Path $projectRoot "scripts/validate_traceability.ps1")

    $requiredFiles = @(
        "scripts/validate_task_system.ps1",
        "scripts/validate_m001_specification.ps1",
        "scripts/validate_architecture_boundaries.py",
        "docs/specs/m001_frontieres_ddd_contrats_publies.md",
        "docs/tasks/milestone_001/0001_verifier_precondition_green.md",
        "docs/tasks/milestone_001/0002_publier_specification_frontieres_ddd.md",
        "docs/tasks/milestone_001/0003_declarer_contextes_proprietaires.md",
        "docs/tasks/milestone_001/0004_publier_identifiants_contrats_communs.md",
        "docs/tasks/milestone_001/0005_publier_source_locator_canonical_source_ref.md",
        "docs/tasks/milestone_001/0006_publier_contrats_preuves_claims.md",
        "docs/tasks/milestone_001/0007_publier_research_outcome_acl_strategie.md",
        "docs/tasks/milestone_001/0008_publier_snapshot_strategie_resultat_experience.md",
        "docs/tasks/milestone_001/0009_publier_enveloppe_evenement_versionnee.md",
        "docs/tasks/milestone_001/0010_interdire_couplages_intercontextes.md",
        "docs/tasks/milestone_001/0011_relier_m001_tracabilite_gates.md",
        "tests/governance/validate_task_system_acceptance.ps1",
        "tests/m001/validate_m001_specification_acceptance.ps1",
        "tests/m001/validate_context_modules_acceptance.ps1",
        "tests/m001/validate_contract_identity_acceptance.ps1",
        "tests/m001/validate_source_contracts_acceptance.ps1",
        "tests/m001/validate_source_locator_unit.ps1",
        "tests/m001/validate_evidence_claim_contracts_acceptance.ps1",
        "tests/m001/validate_evidence_claim_contracts_unit.ps1",
        "tests/m001/validate_research_outcome_contract_acceptance.ps1",
        "tests/m001/validate_strategy_experiment_contracts_acceptance.ps1",
        "tests/m001/validate_event_envelope_acceptance.ps1",
        "tests/m001/validate_architecture_boundaries_acceptance.ps1",
        "tests/m001/validate_m001_traceability_acceptance.ps1",
        "app/context_registry.json",
        "app/contracts/__init__.py",
        "app/contracts/identity.py",
        "app/contracts/source_references.py",
        "app/contracts/evidence_claims.py",
        "app/contracts/research_outcomes.py",
        "app/contracts/strategy_experiments.py",
        "app/contracts/event_envelope.py"
    )

    foreach ($relativePath in $requiredFiles) {
        New-RepositoryFile -ProjectRoot $projectRoot -RelativePath $relativePath
    }

    $adrFiles = @(
        "docs/adr/ADR-010-gates-gouvernance-powershell.md",
        "docs/adr/DDD-ADR-001-monolithe-modulaire.md",
        "docs/adr/DDD-ADR-002-cycles-de-vie-separes.md",
        "docs/adr/DDD-ADR-003-source-locator-langage-publie.md",
        "docs/adr/DDD-ADR-005-claim-agregat-central.md",
        "docs/adr/DDD-ADR-006-pas-event-sourcing-generalise.md",
        "docs/adr/DDD-ADR-007-modeles-proposent-domaine-decide.md",
        "docs/adr/DDD-ADR-008-coherence-eventuelle-entre-contextes.md",
        "docs/adr/DDD-ADR-009-snapshots-immuables-experimentation.md"
    )

    foreach ($relativePath in $adrFiles) {
        New-RepositoryFile -ProjectRoot $projectRoot -RelativePath $relativePath
    }

    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs/traceability") -Force | Out-Null
    New-M001MatrixContent | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $projectRoot "docs/traceability/matrix.md")

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

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    $validProjectRoot = New-TemporaryProject -Name "valid"
    $validResult = Invoke-Validator -ProjectRoot $validProjectRoot
    Assert-ExitCode -Actual $validResult.ExitCode -Expected 0 -Message "Les exigences M-001 couvertes doivent être acceptées."

    $missingRequirementProjectRoot = New-TemporaryProject -Name "missing-requirement"
    Remove-MatrixRow `
        -Path (Join-Path $missingRequirementProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M001-005"
    $missingRequirementResult = Invoke-Validator -ProjectRoot $missingRequirementProjectRoot
    Assert-ExitCode -Actual $missingRequirementResult.ExitCode -Expected 1 -Message "Une exigence M-001 livrée absente doit être refusée."
    Assert-OutputContains `
        -Output $missingRequirementResult.Output `
        -Expected "Exigence M-001 livr$($eAcute)e absente: REQ-M001-005" `
        -Message "L'exigence M-001 absente doit être nommée."

    $plannedRequirementProjectRoot = New-TemporaryProject -Name "planned-requirement"
    Set-MatrixCell `
        -Path (Join-Path $plannedRequirementProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M001-005" `
        -ColumnName "Statut" `
        -Value "Planifi$($eAcute)"
    $plannedRequirementResult = Invoke-Validator -ProjectRoot $plannedRequirementProjectRoot
    Assert-ExitCode -Actual $plannedRequirementResult.ExitCode -Expected 1 -Message "Une exigence M-001 livrée non couverte doit être refusée."
    Assert-OutputContains `
        -Output $plannedRequirementResult.Output `
        -Expected "Exigence M-001 livr$($eAcute)e non couverte: REQ-M001-005" `
        -Message "Le statut M-001 incorrect doit être nommé."

    $wrongTestProjectRoot = New-TemporaryProject -Name "wrong-test"
    Set-MatrixCell `
        -Path (Join-Path $wrongTestProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M001-006" `
        -ColumnName "Test" `
        -Value "tests/m001/validate_evidence_claim_contracts_unit.ps1"
    $wrongTestResult = Invoke-Validator -ProjectRoot $wrongTestProjectRoot
    Assert-ExitCode -Actual $wrongTestResult.ExitCode -Expected 1 -Message "Un lien de test M-001 incorrect doit être refusé."
    Assert-OutputContains `
        -Output $wrongTestResult.Output `
        -Expected "Test M-001 invalide pour REQ-M001-006" `
        -Message "Le test M-001 incorrect doit être nommé."

    $wrongCodeProjectRoot = New-TemporaryProject -Name "wrong-code"
    Set-MatrixCell `
        -Path (Join-Path $wrongCodeProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M001-008" `
        -ColumnName "Code" `
        -Value "app/contracts/__init__.py"
    $wrongCodeResult = Invoke-Validator -ProjectRoot $wrongCodeProjectRoot
    Assert-ExitCode -Actual $wrongCodeResult.ExitCode -Expected 1 -Message "Un lien de code M-001 incorrect doit être refusé."
    Assert-OutputContains `
        -Output $wrongCodeResult.Output `
        -Expected "Code M-001 invalide pour REQ-M001-008" `
        -Message "Le code M-001 incorrect doit être nommé."

    $wrongCommandProjectRoot = New-TemporaryProject -Name "wrong-command"
    Set-MatrixCell `
        -Path (Join-Path $wrongCommandProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M001-002" `
        -ColumnName "Commande" `
        -Value "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m001\validate_m001_specification_acceptance.ps1"
    $wrongCommandResult = Invoke-Validator -ProjectRoot $wrongCommandProjectRoot
    Assert-ExitCode -Actual $wrongCommandResult.ExitCode -Expected 1 -Message "Une commande M-001 incorrecte doit être refusée."
    Assert-OutputContains `
        -Output $wrongCommandResult.Output `
        -Expected "Commande M-001 invalide pour REQ-M001-002" `
        -Message "La commande M-001 incorrecte doit être nommée."

    $wrongAdrProjectRoot = New-TemporaryProject -Name "wrong-adr"
    Set-MatrixCell `
        -Path (Join-Path $wrongAdrProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M001-005" `
        -ColumnName "ADR" `
        -Value "Non requise"
    Set-MatrixCell `
        -Path (Join-Path $wrongAdrProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M001-005" `
        -ColumnName "Justification ADR" `
        -Value "Aucune d$($eAcute)cision structurante nouvelle: justification volontairement incoh$($eAcute)rente."
    $wrongAdrResult = Invoke-Validator -ProjectRoot $wrongAdrProjectRoot
    Assert-ExitCode -Actual $wrongAdrResult.ExitCode -Expected 1 -Message "Une ADR M-001 incorrecte doit être refusée."
    Assert-OutputContains `
        -Output $wrongAdrResult.Output `
        -Expected "ADR M-001 invalide pour REQ-M001-005" `
        -Message "L'ADR M-001 incorrecte doit être nommée."

    $wrongJustificationProjectRoot = New-TemporaryProject -Name "wrong-justification"
    Set-MatrixCell `
        -Path (Join-Path $wrongJustificationProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M001-004" `
        -ColumnName "Justification ADR" `
        -Value "Justification locale sans d$($eAcute)cision explicite."
    $wrongJustificationResult = Invoke-Validator -ProjectRoot $wrongJustificationProjectRoot
    Assert-ExitCode -Actual $wrongJustificationResult.ExitCode -Expected 1 -Message "Une justification ADR M-001 insuffisante doit être refusée."
    Assert-OutputContains `
        -Output $wrongJustificationResult.Output `
        -Expected "Justification ADR insuffisante pour REQ-M001-004" `
        -Message "La justification ADR insuffisante doit être nommée."
}
finally {
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
}

Write-Host "Tests unitaires de traçabilité M-001: OK"
