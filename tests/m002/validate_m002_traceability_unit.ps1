$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "tests/governance/traceability_fixture.ps1")
$validatorPath = Join-Path $repoRoot "scripts/validate_traceability.ps1"
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m002_traceability_unit_" + [System.Guid]::NewGuid().ToString("N"))
$eAcute = [char] 0x00E9
$eGrave = [char] 0x00E8
$aCircumflex = [char] 0x00E2
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

function New-M002MatrixContent {
    $documentedDecision = "D$($eAcute)cision structurante document$($eAcute)e: l'ADR cit$($eAcute)e gouverne l'exigence M-002 sans changement de sens."

    return @"
| Exigence | Source | Statut | Test | Commande | Code | ADR | Justification ADR |
|---|---|---|---|---|---|---|---|
| REQ-M002-001 | docs/tasks/milestone_002/0001_verifier_precondition_green.md | Couvert | tests/m002/validate_m002_precondition_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m002_precondition.ps1 -Path .\docs\governance\m002_precondition_green.md | scripts/validate_m002_precondition.ps1 | ADR-010 | $documentedDecision |
| REQ-M002-002 | docs/tasks/milestone_002/0002_publier_specification_plateforme_locale_sure.md | Couvert | tests/m002/validate_m002_specification_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m002_specification.ps1 -Path .\docs\specs\m002_plateforme_locale_sure.md | docs/specs/m002_plateforme_locale_sure.md | ADR-007; ADR-008; ADR-009; DDD-ADR-006; DDD-ADR-008; ADR-010 | $documentedDecision |
| REQ-M002-003 | docs/tasks/milestone_002/0003_declarer_topologie_docker_spark.md | Couvert | tests/m002/validate_platform_topology_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_platform_topology.ps1 -Path .\app\platform\topology_registry.json | app/platform/topology_registry.json | ADR-007; ADR-009; ADR-012 | $documentedDecision |
| REQ-M002-004 | docs/tasks/milestone_002/0004_configurer_stack_docker_locale.md | Couvert | tests/m002/validate_local_compose_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_local_compose.ps1 -Path .\deploy\local-compose\compose.yaml | deploy/local-compose/compose.yaml | ADR-007; ADR-008; ADR-009; ADR-012; ADR-014 | $documentedDecision |
| REQ-M002-005 | docs/tasks/milestone_002/0005_publier_contrat_gateway_llm.md | Couvert | tests/m002/validate_llm_gateway_contract_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m002\validate_llm_gateway_contract_acceptance.ps1 | app/platform/llm_gateway/__init__.py | ADR-008; ADR-009; ADR-014 | $documentedDecision |
| REQ-M002-006 | docs/tasks/milestone_002/0006_controler_pannes_inference_spark.md | Couvert | tests/m002/validate_llm_gateway_failures_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m002\validate_llm_gateway_failures_acceptance.ps1 | app/platform/llm_gateway/__init__.py | ADR-008; ADR-009; DDD-ADR-007 | $documentedDecision |
| REQ-M002-007 | docs/tasks/milestone_002/0007_livrer_outbox_evenements_idempotente.md | Couvert | tests/m002/validate_outbox_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m002\validate_outbox_acceptance.ps1 | app/platform/event_bus/outbox.py | DDD-ADR-006; DDD-ADR-008 | $documentedDecision |
| REQ-M002-008 | docs/tasks/milestone_002/0008_livrer_file_jobs_priorisee_idempotente.md | Couvert | tests/m002/validate_job_runtime_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m002\validate_job_runtime_acceptance.ps1 | app/platform/job_runtime/__init__.py | DDD-ADR-006; DDD-ADR-008 | $documentedDecision |
| REQ-M002-009 | docs/tasks/milestone_002/0009_verrouiller_frontiere_reseau_locale.md | Couvert | tests/m002/validate_network_boundary_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_network_boundary.ps1 | app/platform/security/network_boundary.py | ADR-007; ADR-008; ADR-009; ADR-012; ADR-014 | $documentedDecision |
| REQ-M002-010 | docs/tasks/milestone_002/0010_observer_gateway_sans_payloads.md | Couvert | tests/m002/validate_gateway_observability_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m002\validate_gateway_observability_acceptance.ps1 | app/platform/observability/__init__.py | ADR-008; ADR-009 | $documentedDecision |
| REQ-M002-011 | docs/tasks/milestone_002/0011_relier_m002_tracabilite_gates.md | Couvert | tests/m002/validate_m002_traceability_acceptance.ps1 | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability.ps1 | scripts/validate_traceability.ps1 | ADR-010 | $documentedDecision |
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
        "scripts/validate_m002_precondition.ps1",
        "scripts/validate_m002_specification.ps1",
        "scripts/validate_platform_topology.ps1",
        "scripts/validate_local_compose.ps1",
        "scripts/validate_network_boundary.ps1",
        "docs/governance/m002_precondition_green.md",
        "docs/specs/m002_plateforme_locale_sure.md",
        "docs/tasks/milestone_002/0001_verifier_precondition_green.md",
        "docs/tasks/milestone_002/0002_publier_specification_plateforme_locale_sure.md",
        "docs/tasks/milestone_002/0003_declarer_topologie_docker_spark.md",
        "docs/tasks/milestone_002/0004_configurer_stack_docker_locale.md",
        "docs/tasks/milestone_002/0005_publier_contrat_gateway_llm.md",
        "docs/tasks/milestone_002/0006_controler_pannes_inference_spark.md",
        "docs/tasks/milestone_002/0007_livrer_outbox_evenements_idempotente.md",
        "docs/tasks/milestone_002/0008_livrer_file_jobs_priorisee_idempotente.md",
        "docs/tasks/milestone_002/0009_verrouiller_frontiere_reseau_locale.md",
        "docs/tasks/milestone_002/0010_observer_gateway_sans_payloads.md",
        "docs/tasks/milestone_002/0011_relier_m002_tracabilite_gates.md",
        "tests/m002/validate_m002_precondition_acceptance.ps1",
        "tests/m002/validate_m002_specification_acceptance.ps1",
        "tests/m002/validate_platform_topology_acceptance.ps1",
        "tests/m002/validate_local_compose_acceptance.ps1",
        "tests/m002/validate_network_boundary_acceptance.ps1",
        "tests/m002/validate_llm_gateway_contract_acceptance.ps1",
        "tests/m002/validate_llm_gateway_failures_acceptance.ps1",
        "tests/m002/validate_outbox_acceptance.ps1",
        "tests/m002/validate_job_runtime_acceptance.ps1",
        "tests/m002/validate_gateway_observability_acceptance.ps1",
        "tests/m002/validate_m002_traceability_acceptance.ps1",
        "app/platform/topology_registry.json",
        "deploy/local-compose/compose.yaml",
        "app/platform/llm_gateway/__init__.py",
        "app/platform/event_bus/outbox.py",
        "app/platform/job_runtime/__init__.py",
        "app/platform/security/network_boundary.py",
        "app/platform/observability/__init__.py"
    )

    foreach ($relativePath in $requiredFiles) {
        New-RepositoryFile -ProjectRoot $projectRoot -RelativePath $relativePath
    }

    $adrFiles = @(
        "docs/adr/ADR-007-deploiement-local-sur-dgx-spark.md",
        "docs/adr/ADR-008-llm-principal-servi-par-vllm.md",
        "docs/adr/ADR-009-spark-sans-etat-metier.md",
        "docs/adr/ADR-010-gates-gouvernance-powershell.md",
        "docs/adr/ADR-012-python-outille-pour-validateurs-plateforme.md",
        "docs/adr/ADR-014-spark-docker-externe-sans-cle-api.md",
        "docs/adr/DDD-ADR-006-pas-event-sourcing-generalise.md",
        "docs/adr/DDD-ADR-007-modeles-proposent-domaine-decide.md",
        "docs/adr/DDD-ADR-008-coherence-eventuelle-entre-contextes.md"
    )

    foreach ($relativePath in $adrFiles) {
        New-RepositoryFile -ProjectRoot $projectRoot -RelativePath $relativePath
    }

    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs/traceability") -Force | Out-Null
    New-M002MatrixContent | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $projectRoot "docs/traceability/matrix.md")
    Copy-TraceabilityRootArtifacts -SourceRoot $repoRoot -DestinationRoot $projectRoot

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
    Assert-ExitCode -Actual $validResult.ExitCode -Expected 0 -Message "Les exigences M-002 couvertes doivent être acceptées."

    $missingRequirementProjectRoot = New-TemporaryProject -Name "missing-requirement"
    Remove-MatrixRow `
        -Path (Join-Path $missingRequirementProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M002-011"
    $missingRequirementResult = Invoke-Validator -ProjectRoot $missingRequirementProjectRoot
    Assert-ExitCode -Actual $missingRequirementResult.ExitCode -Expected 1 -Message "Une exigence M-002 livrée absente doit être refusée."
    Assert-OutputContains `
        -Output $missingRequirementResult.Output `
        -Expected "Exigence M-002 livr$($eAcute)e absente: REQ-M002-011" `
        -Message "L'exigence M-002 absente doit être nommée."

    $plannedRequirementProjectRoot = New-TemporaryProject -Name "planned-requirement"
    Set-MatrixCell `
        -Path (Join-Path $plannedRequirementProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M002-011" `
        -ColumnName "Statut" `
        -Value "Planifi$($eAcute)"
    $plannedRequirementResult = Invoke-Validator -ProjectRoot $plannedRequirementProjectRoot
    Assert-ExitCode -Actual $plannedRequirementResult.ExitCode -Expected 1 -Message "Une exigence M-002 livrée non couverte doit être refusée."
    Assert-OutputContains `
        -Output $plannedRequirementResult.Output `
        -Expected "Exigence M-002 livr$($eAcute)e non couverte: REQ-M002-011" `
        -Message "Le statut M-002 incorrect doit être nommé."

    $wrongConfigurationProofProjectRoot = New-TemporaryProject -Name "wrong-configuration-proof"
    Set-MatrixCell `
        -Path (Join-Path $wrongConfigurationProofProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M002-004" `
        -ColumnName "Code" `
        -Value "app/platform/topology_registry.json"
    $wrongConfigurationProofResult = Invoke-Validator -ProjectRoot $wrongConfigurationProofProjectRoot
    Assert-ExitCode -Actual $wrongConfigurationProofResult.ExitCode -Expected 1 -Message "Une preuve de configuration M-002 incorrecte doit être refusée."
    Assert-OutputContains `
        -Output $wrongConfigurationProofResult.Output `
        -Expected "Code M-002 invalide pour REQ-M002-004" `
        -Message "La preuve de configuration M-002 incorrecte doit être nommée."

    $wrongNetworkProofProjectRoot = New-TemporaryProject -Name "wrong-network-proof"
    Set-MatrixCell `
        -Path (Join-Path $wrongNetworkProofProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M002-009" `
        -ColumnName "Commande" `
        -Value "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m002\validate_network_boundary_acceptance.ps1"
    $wrongNetworkProofResult = Invoke-Validator -ProjectRoot $wrongNetworkProofProjectRoot
    Assert-ExitCode -Actual $wrongNetworkProofResult.ExitCode -Expected 1 -Message "Une preuve de sécurité réseau M-002 incorrecte doit être refusée."
    Assert-OutputContains `
        -Output $wrongNetworkProofResult.Output `
        -Expected "Commande M-002 invalide pour REQ-M002-009" `
        -Message "La preuve réseau M-002 incorrecte doit être nommée."

    $wrongAdrProjectRoot = New-TemporaryProject -Name "wrong-adr"
    Set-MatrixCell `
        -Path (Join-Path $wrongAdrProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M002-006" `
        -ColumnName "ADR" `
        -Value "ADR-008; ADR-009"
    $wrongAdrResult = Invoke-Validator -ProjectRoot $wrongAdrProjectRoot
    Assert-ExitCode -Actual $wrongAdrResult.ExitCode -Expected 1 -Message "Une liste d'ADR M-002 incomplète doit être refusée."
    Assert-OutputContains `
        -Output $wrongAdrResult.Output `
        -Expected "ADR M-002 invalide pour REQ-M002-006" `
        -Message "L'ADR M-002 incomplète doit être nommée."

    $missingCommandProjectRoot = New-TemporaryProject -Name "missing-command"
    Set-MatrixCell `
        -Path (Join-Path $missingCommandProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M002-011" `
        -ColumnName "Commande" `
        -Value "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability_absent.ps1"
    $missingCommandResult = Invoke-Validator -ProjectRoot $missingCommandProjectRoot
    Assert-ExitCode -Actual $missingCommandResult.ExitCode -Expected 1 -Message "Une commande M-002 introuvable doit être refusée."
    Assert-OutputContains `
        -Output $missingCommandResult.Output `
        -Expected "Chemin introuvable dans la matrice (commande REQ-M002-011)" `
        -Message "La commande M-002 introuvable doit être nommée."
}
finally {
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
}

Write-Host "Tests unitaires de tra$($cCedilla)abilit$($eAcute) M-002: OK"
