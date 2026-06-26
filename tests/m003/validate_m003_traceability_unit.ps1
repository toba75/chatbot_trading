$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_traceability.ps1"
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m003_traceability_unit_" + [System.Guid]::NewGuid().ToString("N"))
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

function New-M003MatrixContent {
    $documentedDecision = "D$($eAcute)cision structurante document$($eAcute)e: l'ADR cit$($eAcute)e gouverne l'exigence M-003 sans changement de sens."

    return @"
| Exigence | Source | Statut | Test | Commande | Code | ADR | Justification ADR |
|---|---|---|---|---|---|---|---|
| REQ-M003-001 | docs/tasks/milestone_003/0001_verifier_precondition_green.md | Couvert | tests/m003/validate_m003_precondition_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m003_precondition.ps1 -Path .\docs\governance\m003_precondition_green.md | scripts/validate_m003_precondition.ps1 | ADR-010 | $documentedDecision |
| REQ-M003-002 | docs/tasks/milestone_003/0002_publier_specification_source_routee.md | Couvert | tests/m003/validate_m003_specification_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m003_specification.ps1 -Path .\docs\specs\m003_source_enregistree_diagnostiquee_routee.md | docs/specs/m003_source_enregistree_diagnostiquee_routee.md | ADR-002; ADR-003; DDD-ADR-003 | $documentedDecision |
| REQ-M003-003 | docs/tasks/milestone_003/0003_enregistrer_source_immuable.md | Couvert | tests/m003/validate_source_registration_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m003\validate_source_registration_acceptance.ps1 | app/source_processing/domain/source_document.py | DDD-ADR-003 | $documentedDecision |
| REQ-M003-004 | docs/tasks/milestone_003/0004_creer_manifeste_pages.md | Couvert | tests/m003/validate_page_manifest_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m003\validate_page_manifest_acceptance.ps1 | app/source_processing/domain/document_processing_run.py | DDD-ADR-003 | $documentedDecision |
| REQ-M003-005 | docs/tasks/milestone_003/0005_diagnostiquer_pages_source.md | Couvert | tests/m003/validate_page_diagnostics_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m003\validate_page_diagnostics_acceptance.ps1 | app/source_processing/domain/document_processing_run.py | ADR-002; ADR-003 | $documentedDecision |
| REQ-M003-006 | docs/tasks/milestone_003/0006_decider_plan_routage_explicite.md | Couvert | tests/m003/validate_route_plan_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m003\validate_route_plan_acceptance.ps1 | app/source_processing/domain/document_processing_run.py | ADR-002; ADR-003 | $documentedDecision |
| REQ-M003-007 | docs/tasks/milestone_003/0007_bloquer_revue_quarantaine.md | Couvert | tests/m003/validate_review_quarantine_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m003\validate_review_quarantine_acceptance.ps1 | app/source_processing/domain/document_processing_run.py | ADR-002; DDD-ADR-003 | $documentedDecision |
| REQ-M003-008 | docs/tasks/milestone_003/0008_exposer_commandes_documents_sp.md | Couvert | tests/m003/validate_document_http_contract_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m003\validate_document_http_contract_acceptance.ps1 | app/source_processing/adapters/document_http.py | DDD-ADR-003; ADR-010 | $documentedDecision |
| REQ-M003-009 | docs/tasks/milestone_003/0009_relier_m003_tracabilite_gates.md | Couvert | tests/m003/validate_m003_audit_signals_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m003\validate_m003_audit_signals_acceptance.ps1 | app/source_processing/application/audit_signals.py | ADR-002; ADR-003; DDD-ADR-003 | $documentedDecision |
| REQ-M003-010 | docs/tasks/milestone_003/0009_relier_m003_tracabilite_gates.md | Couvert | tests/m003/validate_m003_traceability_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability.ps1 | scripts/validate_traceability.ps1 | ADR-010 | $documentedDecision |
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
        "scripts/validate_m003_precondition.ps1",
        "scripts/validate_m003_specification.ps1",
        "docs/governance/m003_precondition_green.md",
        "docs/specs/m003_source_enregistree_diagnostiquee_routee.md",
        "docs/tasks/milestone_003/0001_verifier_precondition_green.md",
        "docs/tasks/milestone_003/0002_publier_specification_source_routee.md",
        "docs/tasks/milestone_003/0003_enregistrer_source_immuable.md",
        "docs/tasks/milestone_003/0004_creer_manifeste_pages.md",
        "docs/tasks/milestone_003/0005_diagnostiquer_pages_source.md",
        "docs/tasks/milestone_003/0006_decider_plan_routage_explicite.md",
        "docs/tasks/milestone_003/0007_bloquer_revue_quarantaine.md",
        "docs/tasks/milestone_003/0008_exposer_commandes_documents_sp.md",
        "docs/tasks/milestone_003/0009_relier_m003_tracabilite_gates.md",
        "tests/m003/validate_m003_precondition_acceptance.ps1",
        "tests/m003/validate_m003_specification_acceptance.ps1",
        "tests/m003/validate_source_registration_acceptance.ps1",
        "tests/m003/validate_page_manifest_acceptance.ps1",
        "tests/m003/validate_page_diagnostics_acceptance.ps1",
        "tests/m003/validate_route_plan_acceptance.ps1",
        "tests/m003/validate_review_quarantine_acceptance.ps1",
        "tests/m003/validate_document_http_contract_acceptance.ps1",
        "tests/m003/validate_m003_audit_signals_acceptance.ps1",
        "tests/m003/validate_m003_traceability_acceptance.ps1",
        "app/source_processing/domain/source_document.py",
        "app/source_processing/domain/document_processing_run.py",
        "app/source_processing/adapters/document_http.py",
        "app/source_processing/application/audit_signals.py"
    )

    foreach ($relativePath in $requiredFiles) {
        New-RepositoryFile -ProjectRoot $projectRoot -RelativePath $relativePath
    }

    $adrFiles = @(
        "docs/adr/ADR-002-routage-hybride-docling.md",
        "docs/adr/ADR-003-ocrmypdf-conditionnel.md",
        "docs/adr/ADR-010-gates-gouvernance-powershell.md",
        "docs/adr/DDD-ADR-003-source-locator-langage-publie.md"
    )

    foreach ($relativePath in $adrFiles) {
        New-RepositoryFile -ProjectRoot $projectRoot -RelativePath $relativePath
    }

    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs/traceability") -Force | Out-Null
    New-M003MatrixContent | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $projectRoot "docs/traceability/matrix.md")

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
    Assert-ExitCode -Actual $validResult.ExitCode -Expected 0 -Message "Les exigences M-003 couvertes doivent être acceptées."

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

    $plannedRequirementProjectRoot = New-TemporaryProject -Name "planned-requirement"
    Set-MatrixCell `
        -Path (Join-Path $plannedRequirementProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M003-010" `
        -ColumnName "Statut" `
        -Value "Planifi$($eAcute)"
    $plannedRequirementResult = Invoke-Validator -ProjectRoot $plannedRequirementProjectRoot
    Assert-ExitCode -Actual $plannedRequirementResult.ExitCode -Expected 1 -Message "Une exigence M-003 livrée non couverte doit être refusée."
    Assert-OutputContains `
        -Output $plannedRequirementResult.Output `
        -Expected "Exigence M-003 livr$($eAcute)e non couverte: REQ-M003-010" `
        -Message "Le statut M-003 incorrect doit être nommé."

    $wrongDomainProofProjectRoot = New-TemporaryProject -Name "wrong-domain-proof"
    Set-MatrixCell `
        -Path (Join-Path $wrongDomainProofProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M003-004" `
        -ColumnName "Code" `
        -Value "app/source_processing/adapters/document_http.py"
    $wrongDomainProofResult = Invoke-Validator -ProjectRoot $wrongDomainProofProjectRoot
    Assert-ExitCode -Actual $wrongDomainProofResult.ExitCode -Expected 1 -Message "Une preuve de domaine M-003 incorrecte doit être refusée."
    Assert-OutputContains `
        -Output $wrongDomainProofResult.Output `
        -Expected "Code M-003 invalide pour REQ-M003-004" `
        -Message "La preuve de domaine M-003 incorrecte doit être nommée."

    $wrongAdapterProofProjectRoot = New-TemporaryProject -Name "wrong-adapter-proof"
    Set-MatrixCell `
        -Path (Join-Path $wrongAdapterProofProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M003-008" `
        -ColumnName "Code" `
        -Value "app/source_processing/domain/document_processing_run.py"
    $wrongAdapterProofResult = Invoke-Validator -ProjectRoot $wrongAdapterProofProjectRoot
    Assert-ExitCode -Actual $wrongAdapterProofResult.ExitCode -Expected 1 -Message "Une preuve d'adaptateur M-003 incorrecte doit être refusée."
    Assert-OutputContains `
        -Output $wrongAdapterProofResult.Output `
        -Expected "Code M-003 invalide pour REQ-M003-008" `
        -Message "La preuve d'adaptateur M-003 incorrecte doit être nommée."

    $wrongRoutingAdrProjectRoot = New-TemporaryProject -Name "wrong-routing-adr"
    Set-MatrixCell `
        -Path (Join-Path $wrongRoutingAdrProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M003-006" `
        -ColumnName "ADR" `
        -Value "DDD-ADR-003"
    $wrongRoutingAdrResult = Invoke-Validator -ProjectRoot $wrongRoutingAdrProjectRoot
    Assert-ExitCode -Actual $wrongRoutingAdrResult.ExitCode -Expected 1 -Message "Une ADR de routage M-003 incomplète doit être refusée."
    Assert-OutputContains `
        -Output $wrongRoutingAdrResult.Output `
        -Expected "ADR M-003 invalide pour REQ-M003-006" `
        -Message "L'ADR de routage M-003 incorrecte doit être nommée."

    $missingCommandProjectRoot = New-TemporaryProject -Name "missing-command"
    Set-MatrixCell `
        -Path (Join-Path $missingCommandProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M003-010" `
        -ColumnName "Commande" `
        -Value "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability_absent.ps1"
    $missingCommandResult = Invoke-Validator -ProjectRoot $missingCommandProjectRoot
    Assert-ExitCode -Actual $missingCommandResult.ExitCode -Expected 1 -Message "Une commande M-003 introuvable doit être refusée."
    Assert-OutputContains `
        -Output $missingCommandResult.Output `
        -Expected "Chemin introuvable dans la matrice (commande REQ-M003-010)" `
        -Message "La commande M-003 introuvable doit être nommée."

    $missingCodeProjectRoot = New-TemporaryProject -Name "missing-code"
    Set-MatrixCell `
        -Path (Join-Path $missingCodeProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M003-003" `
        -ColumnName "Code" `
        -Value "app/source_processing/domain/source_document_absent.py"
    $missingCodeResult = Invoke-Validator -ProjectRoot $missingCodeProjectRoot
    Assert-ExitCode -Actual $missingCodeResult.ExitCode -Expected 1 -Message "Une exigence M-003 sans code doit être refusée."
    Assert-OutputContains `
        -Output $missingCodeResult.Output `
        -Expected "Chemin introuvable dans la matrice (code REQ-M003-003)" `
        -Message "Le code M-003 absent doit être nommé."

    $missingAuditProjectRoot = New-TemporaryProject -Name "missing-audit"
    Set-MatrixCell `
        -Path (Join-Path $missingAuditProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M003-009" `
        -ColumnName "Code" `
        -Value "scripts/validate_traceability.ps1"
    $missingAuditResult = Invoke-Validator -ProjectRoot $missingAuditProjectRoot
    Assert-ExitCode -Actual $missingAuditResult.ExitCode -Expected 1 -Message "Une preuve M-003 sans métriques ni logs doit être refusée."
    Assert-OutputContains `
        -Output $missingAuditResult.Output `
        -Expected "Signal d'audit M-003 invalide pour REQ-M003-009" `
        -Message "Les métriques ou logs M-003 absents doivent être nommés."
}
finally {
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
}

Write-Host "Tests unitaires de tra$($cCedilla)abilit$($eAcute) M-003: OK"
