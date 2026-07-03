$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$matrixPath = Join-Path $repoRoot "docs/traceability/matrix.md"
$traceabilityValidatorPath = Join-Path $repoRoot "scripts/validate_traceability.ps1"
$testGatePath = Join-Path $repoRoot "scripts/test.ps1"
$lintGatePath = Join-Path $repoRoot "scripts/lint.ps1"
$metricsPath = Join-Path $repoRoot "docs/governance/m009_deep_research_metrics.json"

$expectedRequirements = @(
    [ordered] @{
        Id = "REQ-M009-001"
        Test = "tests/m009/validate_m009_precondition_acceptance.ps1"
        Command = "scripts/validate_m009_precondition.ps1"
        Adr = "ADR-010"
    },
    [ordered] @{
        Id = "REQ-M009-002"
        Test = "tests/m009/validate_m009_specification_acceptance.ps1"
        Command = "scripts/validate_m009_specification.ps1"
        Adr = "ADR-006; ADR-010; DDD-ADR-003; DDD-ADR-005; DDD-ADR-007; DDD-ADR-008"
    },
    [ordered] @{
        Id = "REQ-M009-003"
        Test = "tests/m009/validate_deep_research_planning_acceptance.ps1"
        Command = "tests/m009/validate_deep_research_planning_acceptance.ps1"
        Adr = "ADR-006; ADR-010; DDD-ADR-005"
    },
    [ordered] @{
        Id = "REQ-M009-004"
        Test = "tests/m009/validate_multi_query_evidence_collection_acceptance.ps1"
        Command = "tests/m009/validate_multi_query_evidence_collection_acceptance.ps1"
        Adr = "ADR-006; DDD-ADR-003; DDD-ADR-005"
    },
    [ordered] @{
        Id = "REQ-M009-005"
        Test = "tests/m009/validate_verified_claim_dependency_resolution_acceptance.ps1"
        Command = "tests/m009/validate_verified_claim_dependency_resolution_acceptance.ps1"
        Adr = "ADR-006; DDD-ADR-005; DDD-ADR-008"
    },
    [ordered] @{
        Id = "REQ-M009-006"
        Test = "tests/m009/validate_deep_contradiction_classification_acceptance.ps1"
        Command = "tests/m009/validate_deep_contradiction_classification_acceptance.ps1"
        Adr = "DDD-ADR-005; DDD-ADR-007"
    },
    [ordered] @{
        Id = "REQ-M009-007"
        Test = "tests/m009/validate_insufficient_deep_coverage_acceptance.ps1"
        Command = "tests/m009/validate_insufficient_deep_coverage_acceptance.ps1"
        Adr = "ADR-006; DDD-ADR-005; DDD-ADR-007"
    },
    [ordered] @{
        Id = "REQ-M009-008"
        Test = "tests/m009/validate_multi_source_synthesis_acceptance.ps1"
        Command = "tests/m009/validate_multi_source_synthesis_acceptance.ps1"
        Adr = "DDD-ADR-003; DDD-ADR-005; DDD-ADR-007"
    },
    [ordered] @{
        Id = "REQ-M009-009"
        Test = "tests/m009/validate_deep_research_http_contract_acceptance.ps1"
        Command = "tests/m009/validate_deep_research_http_contract_acceptance.ps1"
        Adr = "ADR-010; DDD-ADR-003; DDD-ADR-005"
    },
    [ordered] @{
        Id = "REQ-M009-010"
        Test = "tests/m009/validate_deep_research_metrics_acceptance.ps1"
        Command = "tests/m009/validate_deep_research_metrics_acceptance.ps1"
        Adr = "ADR-010; DDD-ADR-008"
    },
    [ordered] @{
        Id = "REQ-M009-011"
        Test = "tests/m009/validate_m009_traceability_acceptance.ps1"
        Command = "tests/m009/validate_m009_traceability_acceptance.ps1"
        Adr = "ADR-006; ADR-010; DDD-ADR-005; DDD-ADR-008"
    }
)

$expectedM009TestPaths = @(
    "tests/m009/validate_m009_precondition_acceptance.ps1",
    "tests/m009/validate_m009_precondition_unit.ps1",
    "tests/m009/validate_m009_specification_acceptance.ps1",
    "tests/m009/validate_m009_specification_unit.ps1",
    "tests/m009/validate_deep_research_planning_acceptance.ps1",
    "tests/m009/validate_deep_research_planning_unit.ps1",
    "tests/m009/validate_multi_query_evidence_collection_acceptance.ps1",
    "tests/m009/validate_multi_query_evidence_collection_unit.ps1",
    "tests/m009/validate_verified_claim_dependency_resolution_acceptance.ps1",
    "tests/m009/validate_verified_claim_dependency_resolution_unit.ps1",
    "tests/m009/validate_deep_contradiction_classification_acceptance.ps1",
    "tests/m009/validate_deep_contradiction_classification_unit.ps1",
    "tests/m009/validate_insufficient_deep_coverage_acceptance.ps1",
    "tests/m009/validate_insufficient_deep_coverage_unit.ps1",
    "tests/m009/validate_multi_source_synthesis_acceptance.ps1",
    "tests/m009/validate_multi_source_synthesis_unit.ps1",
    "tests/m009/validate_deep_research_http_contract_acceptance.ps1",
    "tests/m009/validate_deep_research_http_contract_unit.ps1",
    "tests/m009/validate_deep_research_metrics_acceptance.ps1",
    "tests/m009/validate_deep_research_metrics_unit.ps1",
    "tests/m009/validate_m009_traceability_acceptance.ps1",
    "tests/m009/validate_m009_traceability_unit.ps1"
)

function Assert-Condition {
    param(
        [Parameter(Mandatory = $true)]
        [bool] $Condition,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

function Assert-Raises {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ExpectedFragment,

        [Parameter(Mandatory = $true)]
        [scriptblock] $Action
    )

    try {
        & $Action
    }
    catch {
        $message = [string] $_.Exception.Message
        if (-not $message.Contains($ExpectedFragment)) {
            throw "Erreur inattendue. Attendu: $ExpectedFragment. Obtenu: $message"
        }
        return
    }

    throw "Erreur attendue absente: $ExpectedFragment"
}

function New-TraceabilitySnapshot {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable] $RequirementsById,

        [Parameter(Mandatory = $true)]
        [string] $TestGateContent,

        [Parameter(Mandatory = $true)]
        [string] $LintGateContent,

        [Parameter(Mandatory = $true)]
        [string] $MetricsContent,

        [Parameter(Mandatory = $true)]
        [string] $EndpointContent,

        [Parameter(Mandatory = $true)]
        [string] $TraceabilityValidatorContent
    )

    return [pscustomobject] @{
        RequirementsById = $RequirementsById
        TestGateContent = $TestGateContent
        LintGateContent = $LintGateContent
        MetricsContent = $MetricsContent
        EndpointContent = $EndpointContent
        TraceabilityValidatorContent = $TraceabilityValidatorContent
    }
}

function New-GreenRequirementMap {
    $requirements = @{}
    foreach ($expected in $expectedRequirements) {
        $requirements[$expected["Id"]] = [ordered] @{
            Test = $expected["Test"]
            Command = $expected["Command"]
            Adr = $expected["Adr"]
        }
    }

    return $requirements
}

function New-GreenSnapshot {
    $gateContent = ($expectedM009TestPaths -join "`n")
    $lintContent = @(
        "scripts/validate_traceability.ps1",
        "scripts/validate_m009_specification.ps1",
        "scripts/validate_architecture_boundaries.ps1"
    ) -join "`n"
    $metricsContent = @"
{
  "metric_scope": "M009_DEEP_RESEARCH",
  "normative_signals": {
    "deep_research_requested_total": 1,
    "deep_research_plan_created_total": 1,
    "deep_research_coverage_obligation_met_total": 1,
    "deep_research_coverage_obligation_missing_total": 0,
    "deep_research_query_executed_total": 2,
    "deep_research_independent_source_group_total": 1,
    "deep_research_contradiction_classified_total": 0,
    "deep_research_documentary_gap_total": 0,
    "deep_research_support_status_total": 1,
    "deep_research_public_error_total": 0,
    "deep_research_synthesis_published_total": 1,
    "deep_research_claim_version_recorded_total": 1
  }
}
"@
    $endpointContent = "POST /v1/research/deep`nRECHERCHE_APPROFONDIE`nanswer_deep_research_turn"
    $validatorContent = ($expectedRequirements | ForEach-Object { $_["Id"] }) -join "`n"

    return New-TraceabilitySnapshot `
        -RequirementsById (New-GreenRequirementMap) `
        -TestGateContent $gateContent `
        -LintGateContent $lintContent `
        -MetricsContent $metricsContent `
        -EndpointContent $endpointContent `
        -TraceabilityValidatorContent $validatorContent
}

function Assert-M009TraceabilitySnapshot {
    param(
        [Parameter(Mandatory = $true)]
        [object] $Snapshot
    )

    foreach ($expected in $expectedRequirements) {
        $requirementId = $expected["Id"]
        Assert-Condition `
            -Condition ($Snapshot.RequirementsById.ContainsKey($requirementId)) `
            -Message "Exigence M-009 absente: $requirementId"

        $requirement = $Snapshot.RequirementsById[$requirementId]
        Assert-Condition `
            -Condition ($requirement["Test"] -eq $expected["Test"]) `
            -Message "Test M-009 invalide pour ${requirementId}. Attendu: $($expected["Test"]). Obtenu: $($requirement["Test"])"
        Assert-Condition `
            -Condition ($requirement["Command"] -eq $expected["Command"]) `
            -Message "Commande M-009 invalide pour ${requirementId}. Attendu: $($expected["Command"]). Obtenu: $($requirement["Command"])"
        Assert-Condition `
            -Condition ($requirement["Adr"] -eq $expected["Adr"]) `
            -Message "ADR M-009 invalide pour ${requirementId}. Attendu: $($expected["Adr"]). Obtenu: $($requirement["Adr"])"
        Assert-Condition `
            -Condition ($Snapshot.TraceabilityValidatorContent.Contains($requirementId)) `
            -Message "Validateur de traçabilité sans exigence M-009: $requirementId"
    }

    foreach ($testPath in $expectedM009TestPaths) {
        Assert-Condition `
            -Condition ($Snapshot.TestGateContent.Contains($testPath)) `
            -Message "Gate test sans test M-009: $testPath"
    }

    foreach ($validationPath in @(
        "scripts/validate_traceability.ps1",
        "scripts/validate_m009_specification.ps1",
        "scripts/validate_architecture_boundaries.ps1"
    )) {
        Assert-Condition `
            -Condition ($Snapshot.LintGateContent.Contains($validationPath)) `
            -Message "Gate lint sans validateur requis: $validationPath"
    }

    foreach ($metricName in @(
        "deep_research_requested_total",
        "deep_research_plan_created_total",
        "deep_research_coverage_obligation_met_total",
        "deep_research_query_executed_total",
        "deep_research_claim_version_recorded_total"
    )) {
        Assert-Condition `
            -Condition ($Snapshot.MetricsContent.Contains($metricName)) `
            -Message "Métrique M-009 absente: $metricName"
    }

    foreach ($endpointMarker in @(
        "POST /v1/research/deep",
        "RECHERCHE_APPROFONDIE",
        "answer_deep_research_turn"
    )) {
        Assert-Condition `
            -Condition ($Snapshot.EndpointContent.Contains($endpointMarker)) `
            -Message "Endpoint approfondi ou routage CV absent: $endpointMarker"
    }

    foreach ($forbiddenPayload in @(
        "Texte source complet d'une preuve approfondie qui ne doit pas etre journalise.",
        "Prompt complet demandant au modele de synthétiser toutes les sources.",
        "Réponse approfondie complète qualifiée par les preuves et les limites.",
        "investisseur.prive@example.test",
        "answer_text",
        "source_text",
        "prompt_override",
        "raw_projection_payload"
    )) {
        Assert-Condition `
            -Condition (-not $Snapshot.MetricsContent.Contains($forbiddenPayload)) `
            -Message "Payload sensible M-009 exposé dans les métriques: $forbiddenPayload"
    }
}

function ConvertTo-M009RequirementMapFromMatrix {
    param(
        [Parameter(Mandatory = $true)]
        [string] $MatrixContent
    )

    $requirements = @{}
    foreach ($line in ($MatrixContent -split "`r?`n")) {
        if (-not $line.StartsWith("| REQ-M009-")) {
            continue
        }

        $cells = @($line.Trim("|").Split("|") | ForEach-Object { $_.Trim() })
        if ($cells.Count -lt 8) {
            throw "Ligne M-009 incomplète: $line"
        }

        $requirementId = $cells[0]
        $commandScript = $cells[4]
        if ($commandScript.StartsWith("powershell -NoProfile -ExecutionPolicy Bypass -File .\")) {
            $commandScript = $commandScript.Substring("powershell -NoProfile -ExecutionPolicy Bypass -File .\".Length).Replace("\", "/")
        }
        if ($commandScript -match "^(?<script>[^ ]+\.ps1)(?: .*)?$") {
            $commandScript = $Matches["script"]
        }

        $requirements[$requirementId] = [ordered] @{
            Test = $cells[3].Replace("\", "/")
            Command = $commandScript
            Adr = $cells[6]
        }
    }

    return $requirements
}

$greenSnapshot = New-GreenSnapshot
Assert-M009TraceabilitySnapshot -Snapshot $greenSnapshot

$missingRequirementSnapshot = New-GreenSnapshot
$missingRequirementSnapshot.RequirementsById.Remove("REQ-M009-011")
Assert-Raises -ExpectedFragment "Exigence M-009 absente: REQ-M009-011" -Action {
    Assert-M009TraceabilitySnapshot -Snapshot $missingRequirementSnapshot
}

$missingTestSnapshot = New-GreenSnapshot
$missingTestSnapshot.RequirementsById["REQ-M009-011"]["Test"] = "tests/m009/test_absent.ps1"
Assert-Raises -ExpectedFragment "Test M-009 invalide pour REQ-M009-011" -Action {
    Assert-M009TraceabilitySnapshot -Snapshot $missingTestSnapshot
}

$missingCommandSnapshot = New-GreenSnapshot
$missingCommandSnapshot.RequirementsById["REQ-M009-011"]["Command"] = "scripts/commande_absente.ps1"
Assert-Raises -ExpectedFragment "Commande M-009 invalide pour REQ-M009-011" -Action {
    Assert-M009TraceabilitySnapshot -Snapshot $missingCommandSnapshot
}

$missingAdrSnapshot = New-GreenSnapshot
$missingAdrSnapshot.RequirementsById["REQ-M009-011"]["Adr"] = "Non requise"
Assert-Raises -ExpectedFragment "ADR M-009 invalide pour REQ-M009-011" -Action {
    Assert-M009TraceabilitySnapshot -Snapshot $missingAdrSnapshot
}

$missingMetricSnapshot = New-GreenSnapshot
$missingMetricSnapshot.MetricsContent = $missingMetricSnapshot.MetricsContent.Replace("deep_research_claim_version_recorded_total", "metric_absente")
Assert-Raises -ExpectedFragment "Métrique M-009 absente: deep_research_claim_version_recorded_total" -Action {
    Assert-M009TraceabilitySnapshot -Snapshot $missingMetricSnapshot
}

$missingEndpointSnapshot = New-GreenSnapshot
$missingEndpointSnapshot.EndpointContent = $missingEndpointSnapshot.EndpointContent.Replace("POST /v1/research/deep", "POST /v1/research")
Assert-Raises -ExpectedFragment "Endpoint approfondi ou routage CV absent: POST /v1/research/deep" -Action {
    Assert-M009TraceabilitySnapshot -Snapshot $missingEndpointSnapshot
}

$sensitivePayloadSnapshot = New-GreenSnapshot
$sensitivePayloadSnapshot.MetricsContent = $sensitivePayloadSnapshot.MetricsContent + "`nPrompt complet demandant au modele de synthétiser toutes les sources."
Assert-Raises -ExpectedFragment "Payload sensible M-009 exposé" -Action {
    Assert-M009TraceabilitySnapshot -Snapshot $sensitivePayloadSnapshot
}

$missingGateSnapshot = New-GreenSnapshot
$missingGateSnapshot.TestGateContent = $missingGateSnapshot.TestGateContent.Replace("tests/m009/validate_m009_traceability_unit.ps1", "tests/m009/test_non_enrole.ps1")
Assert-Raises -ExpectedFragment "Gate test sans test M-009: tests/m009/validate_m009_traceability_unit.ps1" -Action {
    Assert-M009TraceabilitySnapshot -Snapshot $missingGateSnapshot
}

# Given la politique de traçabilité M-009 est définie par les exigences ci-dessus.
# When elle est appliquée aux artefacts réels du dépôt.
# Then elle échoue tant que la clôture T-011 n'est pas matérialisée dans la matrice, les gates et le validateur.
$actualMatrixContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $matrixPath
$actualSnapshot = New-TraceabilitySnapshot `
    -RequirementsById (ConvertTo-M009RequirementMapFromMatrix -MatrixContent $actualMatrixContent) `
    -TestGateContent (Get-Content -Raw -Encoding UTF8 -LiteralPath $testGatePath) `
    -LintGateContent (Get-Content -Raw -Encoding UTF8 -LiteralPath $lintGatePath) `
    -MetricsContent (Get-Content -Raw -Encoding UTF8 -LiteralPath $metricsPath) `
    -EndpointContent ((Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $repoRoot "docs/specs/m009_recherche_approfondie_multi_sources.md")) + "`n" + (Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $repoRoot "app/conversation/application/answer_deep_research_turn.py"))) `
    -TraceabilityValidatorContent (Get-Content -Raw -Encoding UTF8 -LiteralPath $traceabilityValidatorPath)

Assert-M009TraceabilitySnapshot -Snapshot $actualSnapshot

Write-Host "Tests unitaires T-011 traçabilité et gates M-009: OK"
