param(
    [Parameter(Mandatory = $false)]
    [string] $MatrixPath,

    [Parameter(Mandatory = $false)]
    [string] $SpecificationPath,

    [Parameter(Mandatory = $false)]
    [string] $GapReportPath,

    [Parameter(Mandatory = $false)]
    [string] $TestGatePath,

    [Parameter(Mandatory = $false)]
    [string] $LintGatePath,

    [Parameter(Mandatory = $false)]
    [string] $GovernanceTestPath
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

$expectedRequirements = @(
    [ordered] @{
        Id = "REQ-M012-001"
        Source = "docs/tasks/milestone_012/0001_verifier_precondition_green.md"
        Test = "tests/m012/validate_m012_precondition_acceptance.ps1"
        Command = "scripts/validate_m012_precondition.ps1"
        Code = "scripts/validate_m012_precondition.ps1; docs/governance/m012_precondition_green.md"
        Adr = "ADR-010"
    },
    [ordered] @{
        Id = "REQ-M012-002"
        Source = "docs/tasks/milestone_012/0002_publier_specification_evaluation_pilote.md"
        Test = "tests/m012/validate_m012_specification_acceptance.ps1"
        Command = "scripts/validate_m012_specification.ps1"
        Code = "docs/specs/m012_evaluation_pilote_calibration.md"
        Adr = "ADR-002; ADR-005; ADR-008; ADR-010; DDD-ADR-007; DDD-ADR-009; DDD-ADR-010"
    },
    [ordered] @{
        Id = "REQ-M012-003"
        Source = "docs/tasks/milestone_012/0003_constituer_corpus_pilote_representatif.md"
        Test = "tests/m012/validate_pilot_corpus_acceptance.ps1"
        Command = "tests/m012/validate_pilot_corpus_acceptance.ps1"
        Code = "app/evaluation/domain/pilot_corpus.py; docs/evaluation/m012/pilot_corpus_constitution_report.md"
        Adr = "ADR-010"
    },
    [ordered] @{
        Id = "REQ-M012-004"
        Source = "docs/tasks/milestone_012/0004_publier_jeu_annote_page_par_page.md"
        Test = "tests/m012/validate_page_annotation_set_acceptance.ps1"
        Command = "tests/m012/validate_page_annotation_set_acceptance.ps1"
        Code = "app/evaluation/domain/page_annotation.py; docs/evaluation/m012/page_annotation_set_report.md"
        Adr = "ADR-002; ADR-010"
    },
    [ordered] @{
        Id = "REQ-M012-005"
        Source = "docs/tasks/milestone_012/0005_mesurer_routes_documentaires.md"
        Test = "tests/m012/validate_document_route_benchmark_acceptance.ps1"
        Command = "tests/m012/validate_document_route_benchmark_acceptance.ps1"
        Code = "app/evaluation/domain/document_route_benchmark.py; docs/evaluation/m012/document_route_benchmark_report.md"
        Adr = "ADR-002; ADR-010"
    },
    [ordered] @{
        Id = "REQ-M012-006"
        Source = "docs/tasks/milestone_012/0006_calibrer_seuils_conversion_canonique.md"
        Test = "tests/m012/validate_document_quality_calibration_acceptance.ps1"
        Command = "tests/m012/validate_document_quality_calibration_acceptance.ps1"
        Code = "app/evaluation/domain/document_quality_calibration.py; docs/evaluation/m012/document_quality_calibration_report.md"
        Adr = "ADR-002; ADR-004; ADR-010"
    },
    [ordered] @{
        Id = "REQ-M012-007"
        Source = "docs/tasks/milestone_012/0007_mesurer_recherche_connaissances.md"
        Test = "tests/m012/validate_knowledge_search_benchmark_acceptance.ps1"
        Command = "tests/m012/validate_knowledge_search_benchmark_acceptance.ps1"
        Code = "app/evaluation/domain/knowledge_search_benchmark.py; docs/evaluation/m012/knowledge_search_benchmark_report.md"
        Adr = "ADR-005; ADR-010; DDD-ADR-004"
    },
    [ordered] @{
        Id = "REQ-M012-008"
        Source = "docs/tasks/milestone_012/0008_mesurer_reponses_verifiees_abstention.md"
        Test = "tests/m012/validate_verified_answer_benchmark_acceptance.ps1"
        Command = "tests/m012/validate_verified_answer_benchmark_acceptance.ps1"
        Code = "app/evaluation/domain/verified_answer_benchmark.py; docs/evaluation/m012/verified_answer_benchmark_report.md; docs/evaluation/m012/evidence_governance_benchmark_report.md"
        Adr = "ADR-010; DDD-ADR-007"
    },
    [ordered] @{
        Id = "REQ-M012-009"
        Source = "docs/tasks/milestone_012/0009_mesurer_llm_principal_chemin_reel.md"
        Test = "tests/m012/validate_llm_benchmark_real_path_acceptance.ps1"
        Command = "tests/m012/validate_llm_benchmark_real_path_acceptance.ps1"
        Code = "app/evaluation/domain/llm_real_path_benchmark.py; docs/evaluation/m012/llm_real_path_benchmark_report.md"
        Adr = "ADR-008; ADR-010; DDD-ADR-007"
    },
    [ordered] @{
        Id = "REQ-M012-010"
        Source = "docs/tasks/milestone_012/0010_mesurer_strategies_backtests_pilotes.md"
        Test = "tests/m012/validate_strategy_backtest_benchmark_acceptance.ps1"
        Command = "tests/m012/validate_strategy_backtest_benchmark_acceptance.ps1"
        Code = "app/evaluation/domain/strategy_backtest_benchmark.py; docs/evaluation/m012/strategy_backtest_benchmark_report.md"
        Adr = "ADR-010; DDD-ADR-009; DDD-ADR-010"
    },
    [ordered] @{
        Id = "REQ-M012-011"
        Source = "docs/tasks/milestone_012/0011_publier_decisions_calibration_promotions.md"
        Test = "tests/m012/validate_calibration_decisions_acceptance.ps1"
        Command = "tests/m012/validate_calibration_decisions_acceptance.ps1"
        Code = "app/evaluation/domain/calibration_decisions.py; docs/evaluation/m012/calibration_promotion_decisions_report.md; docs/evaluation/m012/conversation_criteria_report.md"
        Adr = "ADR-010; DDD-ADR-010"
    },
    [ordered] @{
        Id = "REQ-M012-012"
        Source = "docs/tasks/milestone_012/0012_relier_m012_ecarts_v1_tracabilite_gates.md"
        Test = "tests/m012/validate_m012_traceability_acceptance.ps1"
        Command = "scripts/validate_m012_traceability.ps1"
        Code = "scripts/validate_m012_traceability.ps1; docs/governance/m012_v1_gap_report.md; docs/tasks/milestone_012/journal.md"
        Adr = "ADR-010; DDD-ADR-010"
    }
)

$expectedM012TestPaths = @(
    "tests/m012/validate_m012_precondition_acceptance.ps1",
    "tests/m012/validate_m012_precondition_unit.ps1",
    "tests/m012/validate_m012_specification_acceptance.ps1",
    "tests/m012/validate_m012_specification_unit.ps1",
    "tests/m012/validate_pilot_corpus_acceptance.ps1",
    "tests/m012/validate_pilot_corpus_unit.ps1",
    "tests/m012/validate_page_annotation_set_acceptance.ps1",
    "tests/m012/validate_page_annotation_set_unit.ps1",
    "tests/m012/validate_document_route_benchmark_acceptance.ps1",
    "tests/m012/validate_document_route_benchmark_unit.ps1",
    "tests/m012/validate_document_quality_calibration_acceptance.ps1",
    "tests/m012/validate_document_quality_calibration_unit.ps1",
    "tests/m012/validate_knowledge_search_benchmark_acceptance.ps1",
    "tests/m012/validate_knowledge_search_benchmark_unit.ps1",
    "tests/m012/validate_verified_answer_benchmark_acceptance.ps1",
    "tests/m012/validate_verified_answer_benchmark_unit.ps1",
    "tests/m012/validate_llm_benchmark_real_path_acceptance.ps1",
    "tests/m012/validate_llm_benchmark_real_path_unit.ps1",
    "tests/m012/validate_strategy_backtest_benchmark_acceptance.ps1",
    "tests/m012/validate_strategy_backtest_benchmark_unit.ps1",
    "tests/m012/validate_calibration_decisions_acceptance.ps1",
    "tests/m012/validate_calibration_decisions_unit.ps1",
    "tests/m012/validate_m012_traceability_acceptance.ps1",
    "tests/m012/validate_m012_traceability_unit.ps1"
)

$requiredMetricNames = @(
    "source_canonical_version_ratio",
    "source_quarantine_rate",
    "source_page_without_valid_authority_rate",
    "source_adjudication_rate",
    "source_quality_supersession_total",
    "source_publication_delay_seconds",
    "document_cer",
    "document_wer",
    "document_numeric_token_accuracy",
    "document_sign_accuracy",
    "document_formula_fidelity",
    "document_cell_accuracy",
    "document_reading_order_accuracy",
    "document_page_time_seconds",
    "document_memory_bytes",
    "document_route_stability_rate",
    "document_failure_rate",
    "knowledge_projection_current_ratio",
    "knowledge_unresolvable_locator_rate",
    "knowledge_document_diversity",
    "knowledge_stale_projection_search_rate",
    "knowledge_recall_at_5",
    "knowledge_recall_at_10",
    "knowledge_recall_at_20",
    "knowledge_mrr",
    "knowledge_ndcg",
    "knowledge_expected_page_accuracy",
    "knowledge_subtheme_coverage",
    "knowledge_fr_to_en_recall_at_10",
    "evidence_claim_verified_rate",
    "evidence_claim_rejected_rate",
    "evidence_claim_review_rate",
    "evidence_unsupported_assertion_ratio",
    "evidence_verdict_distribution",
    "evidence_dependency_group_count",
    "evidence_supersession_rate",
    "evidence_verification_delay_seconds",
    "answer_support_status_rate",
    "answer_unsupported_assertion_removed_total",
    "answer_citation_precision",
    "answer_correct_abstention_rate",
    "answer_research_obligation_coverage",
    "answer_obsolete_version_reuse_rate",
    "answer_accuracy_score",
    "answer_fidelity_score",
    "answer_completeness_score",
    "answer_contradiction_management_rate",
    "answer_source_deduction_distinction_rate",
    "answer_invented_parameter_rejection_rate",
    "conversation_creation_criterion",
    "conversation_follow_up_resolution_rate",
    "conversation_mode_routing_justified_rate",
    "conversation_raw_history_fact_usage_rejection_total",
    "strategy_compilable_rate",
    "strategy_rejection_reason_distribution",
    "strategy_rule_origin_ratio",
    "strategy_parameter_without_calibration_plan_total",
    "strategy_compatibility_conflict_total",
    "strategy_version_count",
    "json_valide",
    "extraction_atomique",
    "conservation_negations",
    "exactitude_nombres",
    "conditions_application",
    "limites",
    "entailment",
    "contradiction",
    "synthese_fr_en",
    "tool_calling",
    "citations",
    "llm_gateway_latency_ms",
    "llm_network_latency_ms",
    "llm_vllm_queue_time_ms",
    "llm_time_to_first_token_ms",
    "llm_tokens_per_second",
    "llm_error_rate",
    "llm_retry_before_first_token_total",
    "llm_structured_output_stability_rate",
    "llm_spark_restart_recovery_rate",
    "experiment_reproducible_rate",
    "experiment_failure_rate_by_cause",
    "negative_experiment_retention_ratio",
    "experiment_without_complete_cost_model_total",
    "coherent_repeat_count",
    "invalidated_result_ratio"
)

$expectedGapContexts = @("SP", "KA", "EG", "RA", "CV", "SD", "LLM", "EX")
$allowedGapStatuses = @("satisfait", "bloquant", "accepté", "différé")
$forbiddenSensitivePayloads = @(
    "PROMPT_COMPLET_INTERDIT_M012",
    "secret-token-m012",
    "preuve_complete_interdite_m012",
    "reponse_complete_interdite_m012",
    "donnees_marche_completes_interdites_m012",
    "raw_prompt_payload_m012"
)

function Assert-Condition {
    param([bool] $Condition, [string] $Message)
    if (-not $Condition) {
        throw $Message
    }
}

function Resolve-RequiredPath {
    param([string] $Path, [string] $DefaultRelativePath, [string] $Label)

    if ([string]::IsNullOrWhiteSpace($Path)) {
        $candidatePath = Join-Path $repoRoot $DefaultRelativePath
    }
    elseif ([System.IO.Path]::IsPathRooted($Path)) {
        $candidatePath = $Path
    }
    else {
        $candidatePath = Join-Path $repoRoot $Path
    }

    $resolvedRepositoryRoot = [System.IO.Path]::GetFullPath($repoRoot)
    $resolvedPath = [System.IO.Path]::GetFullPath($candidatePath)
    $repositoryPrefix = $resolvedRepositoryRoot.TrimEnd("\", "/") + [System.IO.Path]::DirectorySeparatorChar
    Assert-Condition `
        -Condition ($resolvedPath.StartsWith($repositoryPrefix, [System.StringComparison]::OrdinalIgnoreCase)) `
        -Message "Chemin hors dépôt interdit ($Label): $resolvedPath"
    Assert-Condition `
        -Condition (Test-Path -LiteralPath $resolvedPath -PathType Leaf) `
        -Message "Fichier requis absent ($Label): $resolvedPath"
    return $resolvedPath
}

function Split-MarkdownRow {
    param([string] $Line)
    return @($Line.Trim().Trim("|").Split("|") | ForEach-Object { $_.Trim() })
}

function Normalize-MatrixPathCell {
    param([string] $Value)
    return @($Value.Split(";") | ForEach-Object {
        $path = $_.Trim().Replace("\", "/")
        if ($path.StartsWith("./")) {
            $path = $path.Substring(2)
        }
        $path
    } | Where-Object { $_ -ne "" }) -join "; "
}

function Get-CommandScript {
    param([string] $Command)
    $pattern = "^powershell\s+-NoProfile\s+-ExecutionPolicy\s+Bypass\s+-File\s+(?<script>\.?[\\/][^\s;|&]+)(?:\s+-Path\s+\.?[\\/][^\s;|&]+)?\s*$"
    Assert-Condition -Condition ($Command -match $pattern) -Message "Commande M-012 invalide: $Command"
    $scriptPath = $Matches["script"].Replace("\", "/")
    if ($scriptPath.StartsWith("./")) {
        return $scriptPath.Substring(2)
    }
    return $scriptPath
}

function ConvertTo-M012RequirementMap {
    param([string] $MatrixContent)
    $requirementsById = @{}
    foreach ($line in ($MatrixContent -split "`r?`n")) {
        if (-not $line.StartsWith("| REQ-M012-")) {
            continue
        }
        $cells = Split-MarkdownRow -Line $line
        Assert-Condition -Condition ($cells.Count -eq 8) -Message "Ligne M-012 incomplète: $line"
        $requirementsById[$cells[0]] = [ordered] @{
            Source = Normalize-MatrixPathCell -Value $cells[1]
            Test = Normalize-MatrixPathCell -Value $cells[3]
            Command = Get-CommandScript -Command $cells[4]
            Code = Normalize-MatrixPathCell -Value $cells[5]
            Adr = $cells[6]
        }
    }
    return $requirementsById
}

function Assert-M012RequirementRows {
    param([hashtable] $RequirementsById)
    foreach ($expected in $expectedRequirements) {
        $requirementId = $expected["Id"]
        Assert-Condition -Condition ($RequirementsById.ContainsKey($requirementId)) -Message "Exigence M-012 absente: $requirementId"
        $requirement = $RequirementsById[$requirementId]
        foreach ($cellName in @("Source", "Test", "Command", "Code", "Adr")) {
            $expectedValue = $expected[$cellName]
            $actualValue = $requirement[$cellName]
            if ($actualValue -ne $expectedValue) {
                throw "$cellName M-012 invalide pour ${requirementId}. Attendu: $expectedValue. Obtenu: $actualValue"
            }
        }
    }
}

function ConvertTo-GapStatusMap {
    param([string] $GapReportContent)
    $statusesByContext = @{}
    foreach ($line in ($GapReportContent -split "`r?`n")) {
        foreach ($context in $expectedGapContexts) {
            if ($line.StartsWith("| $context |")) {
                $cells = Split-MarkdownRow -Line $line
                if ($cells.Count -lt 8) {
                    continue
                }
                if ($cells[2] -notmatch "Critère|Qualité|Recherche|Gouvernance|Réponses|Conversation|Stratégies|Promotion|Backtests") {
                    continue
                }
                if ($cells.Count -lt 3) {
                    throw "Ligne d'écart V1 incomplète pour $context"
                }
                $statusesByContext[$context] = $cells[1]
            }
        }
    }
    return $statusesByContext
}

$resolvedMatrixPath = Resolve-RequiredPath -Path $MatrixPath -DefaultRelativePath "docs/traceability/matrix.md" -Label "matrix"
$resolvedSpecificationPath = Resolve-RequiredPath -Path $SpecificationPath -DefaultRelativePath "docs/specs/m012_evaluation_pilote_calibration.md" -Label "specification"
$resolvedGapReportPath = Resolve-RequiredPath -Path $GapReportPath -DefaultRelativePath "docs/governance/m012_v1_gap_report.md" -Label "gap report"
$resolvedTestGatePath = Resolve-RequiredPath -Path $TestGatePath -DefaultRelativePath "scripts/test.ps1" -Label "test gate"
$resolvedLintGatePath = Resolve-RequiredPath -Path $LintGatePath -DefaultRelativePath "scripts/lint.ps1" -Label "lint gate"
$resolvedGovernanceTestPath = Resolve-RequiredPath -Path $GovernanceTestPath -DefaultRelativePath "tests/governance/validate_m000_validation_commands_acceptance.ps1" -Label "governance test"
$validationRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $resolvedMatrixPath))
$evaluationReportRoot = Join-Path $validationRoot "docs/evaluation/m012"
Assert-Condition `
    -Condition (Test-Path -LiteralPath $evaluationReportRoot -PathType Container) `
    -Message "Répertoire de rapports M-012 absent: $evaluationReportRoot"

$matrixContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedMatrixPath
$specificationContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedSpecificationPath
$gapReportContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedGapReportPath
$evaluationReportContents = Get-ChildItem -LiteralPath $evaluationReportRoot -Filter "*.md" |
    Sort-Object -Property FullName |
    ForEach-Object { Get-Content -Raw -Encoding UTF8 -LiteralPath $_.FullName }
$testGateContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedTestGatePath
$lintGateContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedLintGatePath
$governanceTestContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedGovernanceTestPath

Assert-M012RequirementRows -RequirementsById (ConvertTo-M012RequirementMap -MatrixContent $matrixContent)

foreach ($testPath in $expectedM012TestPaths) {
    Assert-Condition -Condition ($testGateContent.Contains($testPath)) -Message "Gate test sans test M-012: $testPath"
}

Assert-Condition -Condition ($testGateContent.Contains('scripts/validate_m012_traceability.ps1')) -Message "Gate test sans validateur M-012"
Assert-Condition -Condition ($lintGateContent.Contains('scripts/validate_m012_traceability.ps1')) -Message "Gate lint sans validateur M-012"
Assert-Condition -Condition ($governanceTestContent.Contains('$expectedTestSummary = "Gate test GREEN: 35 validation(s), $expectedTestCount test(s)."')) -Message "Contrôle compteur test M-000 absent"
Assert-Condition -Condition ($governanceTestContent.Contains('Gate lint GREEN: 35 validation(s), 0 test(s).')) -Message "Contrôle compteur lint M-000 absent"
Assert-Condition -Condition ([regex]::IsMatch($governanceTestContent, '\$expectedTestCount\s*=\s*\d+')) -Message "Compteur test attendu M-000 absent"

$statusesByContext = ConvertTo-GapStatusMap -GapReportContent $gapReportContent
foreach ($context in $expectedGapContexts) {
    Assert-Condition -Condition ($statusesByContext.ContainsKey($context)) -Message "Écart V1 absent pour $context"
    $status = $statusesByContext[$context]
    Assert-Condition -Condition ($allowedGapStatuses -contains $status) -Message "Statut d'écart V1 invalide pour ${context}: $status"
}

foreach ($metricName in $requiredMetricNames) {
    Assert-Condition -Condition ($gapReportContent.Contains($metricName)) -Message "Métrique V1 absente du rapport: $metricName"
    Assert-Condition -Condition ($specificationContent.Contains($metricName) -or $metricName -in @("json_valide", "extraction_atomique", "conservation_negations", "exactitude_nombres", "conditions_application", "limites", "entailment", "contradiction", "synthese_fr_en", "tool_calling", "citations")) -Message "Métrique V1 absente de la spécification: $metricName"
}

foreach ($marker in @("Benchmark source", "Corpus", "Décision liée", "Commande de preuve", "Test scientifique RED", "gate logiciel GREEN")) {
    Assert-Condition -Condition ($gapReportContent.Contains($marker)) -Message "Marqueur V1 absent du rapport: $marker"
}

foreach ($sensitivePayload in $forbiddenSensitivePayloads) {
    Assert-Condition -Condition (-not $gapReportContent.Contains($sensitivePayload)) -Message "Payload sensible M-012 exposé: $sensitivePayload"
    foreach ($evaluationReportContent in $evaluationReportContents) {
        Assert-Condition -Condition (-not $evaluationReportContent.Contains($sensitivePayload)) -Message "Payload sensible M-012 exposé: $sensitivePayload"
    }
}

Write-Host "Traçabilité M-012 valide: $($expectedRequirements.Count) exigence(s), $($expectedGapContexts.Count) écart(s) V1, $($requiredMetricNames.Count) métrique(s)."
