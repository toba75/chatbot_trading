$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_traceability.ps1"
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m004_traceability_unit_" + [System.Guid]::NewGuid().ToString("N"))
$eAcute = [char] 0x00E9
$eGrave = [char] 0x00E8
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

function New-M004MatrixContent {
    $documentedDecision = "D$($eAcute)cision structurante document$($eAcute)e: l'ADR cit$($eAcute)e gouverne l'exigence M-004 sans changement de sens."

    return @"
| Exigence | Source | Statut | Test | Commande | Code | ADR | Justification ADR |
|---|---|---|---|---|---|---|---|
| REQ-M004-001 | docs/tasks/milestone_004/0001_verifier_precondition_green.md | Couvert | tests/m004/validate_m004_precondition_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m004_precondition.ps1 -Path .\docs\governance\m004_precondition_green.md | scripts/validate_m004_precondition.ps1 | ADR-010 | $documentedDecision |
| REQ-M004-002 | docs/tasks/milestone_004/0002_publier_specification_version_canonique.md | Couvert | tests/m004/validate_m004_specification_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m004_specification.ps1 -Path .\docs\specs\m004_version_canonique_publiee.md | docs/specs/m004_version_canonique_publiee.md | ADR-001; ADR-002; ADR-003; ADR-004; DDD-ADR-003 | $documentedDecision |
| REQ-M004-003 | docs/tasks/milestone_004/0003_convertir_pages_selon_route_explicite.md | Couvert | tests/m004/validate_page_conversion_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m004\validate_page_conversion_acceptance.ps1 | app/source_processing/application/convert_routed_pages.py | ADR-001; ADR-002; ADR-003; ADR-004; DDD-ADR-003 | $documentedDecision |
| REQ-M004-004 | docs/tasks/milestone_004/0004_adjuger_autorite_textuelle_page.md | Couvert | tests/m004/validate_text_authority_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m004\validate_text_authority_acceptance.ps1 | app/source_processing/domain/page_conversion.py | ADR-004 | $documentedDecision |
| REQ-M004-005 | docs/tasks/milestone_004/0005_controler_qualite_version_canonique.md | Couvert | tests/m004/validate_canonical_quality_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m004\validate_canonical_quality_acceptance.ps1 | app/source_processing/domain/page_conversion.py | ADR-001; ADR-002; ADR-003; ADR-004 | $documentedDecision |
| REQ-M004-006 | docs/tasks/milestone_004/0006_publier_version_canonique_immuable.md | Couvert | tests/m004/validate_canonical_publication_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m004\validate_canonical_publication_acceptance.ps1 | app/source_processing/domain/canonical_source.py | ADR-001; DDD-ADR-003 | $documentedDecision |
| REQ-M004-007 | docs/tasks/milestone_004/0007_rendre_source_locator_resolvable.md | Couvert | tests/m004/validate_source_locator_resolution_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m004\validate_source_locator_resolution_acceptance.ps1 | app/source_processing/application/source_locator_resolution.py | DDD-ADR-003 | $documentedDecision |
| REQ-M004-008 | docs/tasks/milestone_004/0008_publier_evenement_canonical_source_published.md | Couvert | tests/m004/validate_canonical_publication_event_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m004\validate_canonical_publication_event_acceptance.ps1 | app/source_processing/application/publish_canonical_source_event.py | ADR-001; DDD-ADR-003; DDD-ADR-006; DDD-ADR-008 | $documentedDecision |
| REQ-M004-009 | docs/tasks/milestone_004/0009_exposer_commande_conversion_documentaire.md | Couvert | tests/m004/validate_document_conversion_command_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m004\validate_document_conversion_command_acceptance.ps1 | app/source_processing/application/document_commands.py | ADR-010; DDD-ADR-003; DDD-ADR-006; DDD-ADR-008 | $documentedDecision |
| REQ-M004-010 | docs/tasks/milestone_004/0010_relier_m004_tracabilite_gates.md | Couvert | tests/m004/validate_m004_traceability_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m004\validate_m004_traceability_acceptance.ps1 | app/source_processing/application/canonical_audit_signals.py | ADR-001; ADR-004; ADR-010; DDD-ADR-003; DDD-ADR-006; DDD-ADR-008 | $documentedDecision |
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
        "scripts/validate_m004_precondition.ps1",
        "scripts/validate_m004_specification.ps1",
        "docs/governance/m004_precondition_green.md",
        "docs/specs/m004_version_canonique_publiee.md",
        "docs/tasks/milestone_004/0001_verifier_precondition_green.md",
        "docs/tasks/milestone_004/0002_publier_specification_version_canonique.md",
        "docs/tasks/milestone_004/0003_convertir_pages_selon_route_explicite.md",
        "docs/tasks/milestone_004/0004_adjuger_autorite_textuelle_page.md",
        "docs/tasks/milestone_004/0005_controler_qualite_version_canonique.md",
        "docs/tasks/milestone_004/0006_publier_version_canonique_immuable.md",
        "docs/tasks/milestone_004/0007_rendre_source_locator_resolvable.md",
        "docs/tasks/milestone_004/0008_publier_evenement_canonical_source_published.md",
        "docs/tasks/milestone_004/0009_exposer_commande_conversion_documentaire.md",
        "docs/tasks/milestone_004/0010_relier_m004_tracabilite_gates.md",
        "tests/m004/validate_m004_precondition_acceptance.ps1",
        "tests/m004/validate_m004_specification_acceptance.ps1",
        "tests/m004/validate_page_conversion_acceptance.ps1",
        "tests/m004/validate_text_authority_acceptance.ps1",
        "tests/m004/validate_canonical_quality_acceptance.ps1",
        "tests/m004/validate_canonical_publication_acceptance.ps1",
        "tests/m004/validate_source_locator_resolution_acceptance.ps1",
        "tests/m004/validate_canonical_publication_event_acceptance.ps1",
        "tests/m004/validate_document_conversion_command_acceptance.ps1",
        "tests/m004/validate_m004_traceability_acceptance.ps1",
        "app/source_processing/application/convert_routed_pages.py",
        "app/source_processing/application/source_locator_resolution.py",
        "app/source_processing/application/publish_canonical_source_event.py",
        "app/source_processing/application/document_commands.py",
        "app/source_processing/application/canonical_audit_signals.py",
        "app/source_processing/domain/page_conversion.py",
        "app/source_processing/domain/canonical_source.py"
    )

    foreach ($relativePath in $requiredFiles) {
        New-RepositoryFile -ProjectRoot $projectRoot -RelativePath $relativePath
    }

    $adrFiles = @(
        "docs/adr/ADR-001-artefacts-canoniques.md",
        "docs/adr/ADR-002-routage-hybride-docling.md",
        "docs/adr/ADR-003-ocrmypdf-conditionnel.md",
        "docs/adr/ADR-004-autorite-textuelle-unique-par-page.md",
        "docs/adr/ADR-010-gates-gouvernance-powershell.md",
        "docs/adr/DDD-ADR-003-source-locator-langage-publie.md",
        "docs/adr/DDD-ADR-006-pas-event-sourcing-generalise.md",
        "docs/adr/DDD-ADR-008-coherence-eventuelle-entre-contextes.md"
    )

    foreach ($relativePath in $adrFiles) {
        New-RepositoryFile -ProjectRoot $projectRoot -RelativePath $relativePath
    }

    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs/traceability") -Force | Out-Null
    New-M004MatrixContent | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $projectRoot "docs/traceability/matrix.md")

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
    throw "Validateur de tra$($cCedilla)abilit$($eAcute) absent: scripts/validate_traceability.ps1"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    $validProjectRoot = New-TemporaryProject -Name "valid"
    $validResult = Invoke-Validator -ProjectRoot $validProjectRoot
    Assert-ExitCode -Actual $validResult.ExitCode -Expected 0 -Message "Les exigences M-004 couvertes doivent être acceptées."

    $missingRequirementProjectRoot = New-TemporaryProject -Name "missing-requirement"
    Remove-MatrixRow `
        -Path (Join-Path $missingRequirementProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M004-010"
    $missingRequirementResult = Invoke-Validator -ProjectRoot $missingRequirementProjectRoot
    Assert-ExitCode -Actual $missingRequirementResult.ExitCode -Expected 1 -Message "Une exigence M-004 livrée absente doit être refusée."
    Assert-OutputContains `
        -Output $missingRequirementResult.Output `
        -Expected "Exigence M-004 livr$($eAcute)e absente: REQ-M004-010" `
        -Message "L'exigence M-004 absente doit être nommée."

    $plannedRequirementProjectRoot = New-TemporaryProject -Name "planned-requirement"
    Set-MatrixCell `
        -Path (Join-Path $plannedRequirementProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M004-010" `
        -ColumnName "Statut" `
        -Value "Planifi$($eAcute)"
    $plannedRequirementResult = Invoke-Validator -ProjectRoot $plannedRequirementProjectRoot
    Assert-ExitCode -Actual $plannedRequirementResult.ExitCode -Expected 1 -Message "Une exigence M-004 livrée non couverte doit être refusée."
    Assert-OutputContains `
        -Output $plannedRequirementResult.Output `
        -Expected "Exigence M-004 livr$($eAcute)e non couverte: REQ-M004-010" `
        -Message "Le statut M-004 incorrect doit être nommé."

    $wrongDomainProofProjectRoot = New-TemporaryProject -Name "wrong-domain-proof"
    Set-MatrixCell `
        -Path (Join-Path $wrongDomainProofProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M004-006" `
        -ColumnName "Code" `
        -Value "app/source_processing/application/document_commands.py"
    $wrongDomainProofResult = Invoke-Validator -ProjectRoot $wrongDomainProofProjectRoot
    Assert-ExitCode -Actual $wrongDomainProofResult.ExitCode -Expected 1 -Message "Une preuve de domaine M-004 incorrecte doit être refusée."
    Assert-OutputContains `
        -Output $wrongDomainProofResult.Output `
        -Expected "Code M-004 invalide pour REQ-M004-006" `
        -Message "La preuve de domaine M-004 incorrecte doit être nommée."

    $wrongAdapterProofProjectRoot = New-TemporaryProject -Name "wrong-adapter-proof"
    Set-MatrixCell `
        -Path (Join-Path $wrongAdapterProofProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M004-009" `
        -ColumnName "Code" `
        -Value "app/source_processing/domain/canonical_source.py"
    $wrongAdapterProofResult = Invoke-Validator -ProjectRoot $wrongAdapterProofProjectRoot
    Assert-ExitCode -Actual $wrongAdapterProofResult.ExitCode -Expected 1 -Message "Une preuve d'adaptateur M-004 incorrecte doit être refusée."
    Assert-OutputContains `
        -Output $wrongAdapterProofResult.Output `
        -Expected "Code M-004 invalide pour REQ-M004-009" `
        -Message "La preuve d'adaptateur M-004 incorrecte doit être nommée."

    $wrongCanonicalAdrProjectRoot = New-TemporaryProject -Name "wrong-canonical-adr"
    Set-MatrixCell `
        -Path (Join-Path $wrongCanonicalAdrProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M004-005" `
        -ColumnName "ADR" `
        -Value "DDD-ADR-003"
    $wrongCanonicalAdrResult = Invoke-Validator -ProjectRoot $wrongCanonicalAdrProjectRoot
    Assert-ExitCode -Actual $wrongCanonicalAdrResult.ExitCode -Expected 1 -Message "Une ADR canonique M-004 incomplète doit être refusée."
    Assert-OutputContains `
        -Output $wrongCanonicalAdrResult.Output `
        -Expected "ADR M-004 invalide pour REQ-M004-005" `
        -Message "L'ADR canonique M-004 incorrecte doit être nommée."

    $missingCommandProjectRoot = New-TemporaryProject -Name "missing-command"
    Set-MatrixCell `
        -Path (Join-Path $missingCommandProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M004-010" `
        -ColumnName "Commande" `
        -Value "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m004\validate_m004_traceability_absent.ps1"
    $missingCommandResult = Invoke-Validator -ProjectRoot $missingCommandProjectRoot
    Assert-ExitCode -Actual $missingCommandResult.ExitCode -Expected 1 -Message "Une commande M-004 introuvable doit être refusée."
    Assert-OutputContains `
        -Output $missingCommandResult.Output `
        -Expected "Chemin introuvable dans la matrice (commande REQ-M004-010)" `
        -Message "La commande M-004 introuvable doit être nommée."

    $missingCodeProjectRoot = New-TemporaryProject -Name "missing-code"
    Set-MatrixCell `
        -Path (Join-Path $missingCodeProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M004-007" `
        -ColumnName "Code" `
        -Value "app/source_processing/application/source_locator_absent.py"
    $missingCodeResult = Invoke-Validator -ProjectRoot $missingCodeProjectRoot
    Assert-ExitCode -Actual $missingCodeResult.ExitCode -Expected 1 -Message "Une exigence M-004 sans code doit être refusée."
    Assert-OutputContains `
        -Output $missingCodeResult.Output `
        -Expected "Chemin introuvable dans la matrice (code REQ-M004-007)" `
        -Message "Le code M-004 absent doit être nommé."

    $missingAuditProjectRoot = New-TemporaryProject -Name "missing-audit"
    Set-MatrixCell `
        -Path (Join-Path $missingAuditProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M004-010" `
        -ColumnName "Code" `
        -Value "scripts/validate_traceability.ps1"
    $missingAuditResult = Invoke-Validator -ProjectRoot $missingAuditProjectRoot
    Assert-ExitCode -Actual $missingAuditResult.ExitCode -Expected 1 -Message "Une preuve M-004 sans métriques ni logs doit être refusée."
    Assert-OutputContains `
        -Output $missingAuditResult.Output `
        -Expected "Code M-004 invalide pour REQ-M004-010" `
        -Message "Les métriques ou logs M-004 absents doivent être nommés."
}
finally {
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
}

Write-Host "Tests unitaires de tra$($cCedilla)abilit$($eAcute) M-004: OK"
