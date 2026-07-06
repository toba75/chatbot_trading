param(
    [Parameter(Mandatory = $false)]
    [string] $Path
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$defaultSpecificationPath = "docs/specs/m012_evaluation_pilote_calibration.md"

$requiredSections = @(
    "# M-012 - Évaluation pilote et calibration",
    "## Statut",
    "## Scénario BDD",
    "## Mission M-012",
    "## Contexte DDD",
    "## Langage ubiquitaire M-012",
    "## Artefacts d'évaluation M-012",
    "## Politiques normatives M-012",
    "## Corpus pilote borné",
    "## Annotations page par page",
    "## Métriques normatives par contexte",
    "## Critères CV V1",
    "## Benchmark LLM principal",
    "## Benchmark EX",
    "## Décisions de calibration",
    "## Rapport d'écarts V1",
    "## Erreurs publiques",
    "## Comportements vérifiables M-012",
    "## Commandes de validation",
    "## Exclusions M-012"
)

$requiredMarkers = @(
    "Given la mission M-012 est de mesurer le système sur corpus pilote avant acceptation V1.",
    "When la spécification d'évaluation pilote est publiée.",
    "Then chaque comportement M-012 nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.",
    "Un test scientifique échoué reste visible même si les tests logiciels sont GREEN.",
    "Aucune valeur de seuil non sourcée",
    "Aucun champ de stockage interne dans le contrat public."
)

$requiredArtifacts = @(
    "PilotCorpus",
    "PilotDocument",
    "PageAnnotation",
    "EvaluationRun",
    "BenchmarkResult",
    "CalibrationDecision",
    "PromotionDecision",
    "V1GapReport"
)

$requiredCommands = @(
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_m012_specification_acceptance.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_m012_specification_unit.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m012_specification.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1"
)

$requiredAdrIds = @(
    "ADR-002",
    "ADR-005",
    "ADR-008",
    "ADR-010",
    "DDD-ADR-007",
    "DDD-ADR-009",
    "DDD-ADR-010"
)

$expectedMetricsByContext = @{
    SP = @(
        "source_canonical_version_ratio",
        "source_quarantine_rate",
        "source_page_without_valid_authority_rate",
        "source_adjudication_rate",
        "source_quality_supersession_total",
        "source_publication_delay_seconds",
        "document_cer_wer",
        "document_numeric_token_accuracy",
        "document_sign_accuracy",
        "document_formula_fidelity",
        "document_cell_accuracy",
        "document_reading_order_accuracy",
        "document_page_time_seconds",
        "document_memory_bytes",
        "document_route_stability_rate"
    )
    KA = @(
        "knowledge_projection_current_ratio",
        "knowledge_unresolvable_locator_rate",
        "knowledge_result_diversity_average",
        "knowledge_stale_projection_search_rate",
        "knowledge_recall_at_5",
        "knowledge_recall_at_10",
        "knowledge_recall_at_20",
        "knowledge_mrr",
        "knowledge_ndcg",
        "knowledge_expected_page_accuracy",
        "knowledge_subtopic_coverage_rate",
        "knowledge_fr_to_en_performance"
    )
    EG = @(
        "evidence_claim_verified_rate",
        "evidence_claim_rejected_rate",
        "evidence_claim_review_rate",
        "evidence_unsupported_assertion_ratio",
        "evidence_verdict_distribution",
        "evidence_dependency_group_count",
        "evidence_supersession_rate",
        "evidence_verification_delay_seconds"
    )
    RA = @(
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
        "answer_invented_parameter_rejection_rate"
    )
    CV = @(
        "conversation_creation_criterion",
        "conversation_follow_up_resolution_rate",
        "conversation_mode_routing_justified_rate",
        "conversation_raw_history_fact_usage_rejection_total",
        "conversation_prompt_payload_rejected_total",
        "conversation_public_error_total"
    )
    SD = @(
        "strategy_compilable_rate",
        "strategy_rejection_reason_distribution",
        "strategy_rule_origin_ratio",
        "strategy_parameter_without_calibration_plan_total",
        "strategy_compatibility_conflict_total",
        "strategy_version_count"
    )
    EX = @(
        "experiment_reproducible_rate",
        "experiment_failure_rate_by_cause",
        "negative_experiment_retention_ratio",
        "experiment_without_complete_cost_model_total",
        "coherent_repeat_count",
        "invalidated_result_ratio"
    )
}

$expectedCvCriteria = @(
    "conversation",
    "question de suivi",
    "routage de mode",
    "absence d'usage factuel de l'historique brut"
)

$expectedLlmCheckpoints = @(
    "nvidia/Gemma-4-31B-IT-NVFP4",
    "YCWTG/gemma-4-31B-it-NVFP4A16-GPTQ",
    "google/gemma-4-31B-it-qat-w4a16-ct"
)

$expectedLlmTasks = @(
    "JSON valide",
    "extraction atomique",
    "conservation des négations",
    "exactitude des nombres",
    "conditions d'application",
    "limites",
    "entailment",
    "contradiction",
    "synthèse FR/EN",
    "tool calling",
    "citations"
)

$expectedLlmMetrics = @(
    "llm_gateway_latency_ms",
    "llm_network_latency_ms",
    "llm_vllm_queue_time_ms",
    "llm_time_to_first_token_ms",
    "llm_tokens_per_second",
    "llm_error_rate",
    "llm_retry_before_first_token_total",
    "llm_structured_output_stability_rate",
    "llm_spark_restart_recovery_rate"
)

$expectedPublicErrors = @(
    "HTTP_REQUEST_INVALID",
    "ENDPOINT_NOT_FOUND",
    "PILOT_CORPUS_OUT_OF_BOUNDS",
    "PILOT_DOCUMENT_STRATUM_REQUIRED",
    "PAGE_ANNOTATION_REQUIRED",
    "BENCHMARK_RESULT_REQUIRED",
    "SCIENTIFIC_RESULT_RED",
    "CALIBRATION_DECISION_REQUIRED",
    "V1_GAP_REPORT_REQUIRED",
    "PUBLIC_STORAGE_FIELD_FORBIDDEN",
    "FALLBACK_FORBIDDEN"
)

$expectedBehaviors = @(
    @{ Name = "EV-001 - Spécification exécutable M-012"; Test = "T-002"; Adr = @("ADR-002", "ADR-005", "ADR-008", "ADR-010", "DDD-ADR-007", "DDD-ADR-009", "DDD-ADR-010"); Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m012_specification.ps1" },
    @{ Name = "EV-002 - Corpus pilote représentatif"; Test = "T-003"; Adr = @("ADR-010"); Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_pilot_corpus_acceptance.ps1" },
    @{ Name = "EV-003 - Jeu annoté page par page"; Test = "T-004"; Adr = @("ADR-002", "ADR-010"); Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_page_annotation_set_acceptance.ps1" },
    @{ Name = "EV-004 - Benchmarks de routes documentaires"; Test = "T-005"; Adr = @("ADR-002", "ADR-010"); Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_document_route_benchmark_acceptance.ps1" },
    @{ Name = "EV-005 - Calibration documentaire"; Test = "T-006"; Adr = @("ADR-002", "ADR-010"); Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_document_quality_calibration_acceptance.ps1" },
    @{ Name = "EV-006 - Recherche de connaissances"; Test = "T-007"; Adr = @("ADR-005", "ADR-010"); Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_knowledge_search_benchmark_acceptance.ps1" },
    @{ Name = "EV-007 - Réponses vérifiées, abstention et preuves"; Test = "T-008"; Adr = @("ADR-010", "DDD-ADR-007"); Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_verified_answer_benchmark_acceptance.ps1" },
    @{ Name = "EV-008 - LLM principal par chemin réel"; Test = "T-009"; Adr = @("ADR-008", "ADR-010", "DDD-ADR-007"); Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_llm_benchmark_real_path_acceptance.ps1" },
    @{ Name = "EV-009 - Stratégies et backtests pilotes"; Test = "T-010"; Adr = @("ADR-010", "DDD-ADR-009", "DDD-ADR-010"); Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_strategy_backtest_benchmark_acceptance.ps1" },
    @{ Name = "EV-010 - Décisions de calibration et promotion"; Test = "T-011"; Adr = @("ADR-010", "DDD-ADR-010"); Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_calibration_decisions_acceptance.ps1" },
    @{ Name = "EV-011 - Écarts V1 et traçabilité gates"; Test = "T-012"; Adr = @("ADR-010", "DDD-ADR-010"); Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_m012_traceability_acceptance.ps1" }
)

function Assert-M012Contains {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content,

        [Parameter(Mandatory = $true)]
        [string] $Expected,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if (-not $Content.Contains($Expected)) {
        throw $Message
    }
}

function Split-M012MarkdownRow {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Line
    )

    $trimmed = $Line.Trim()
    if (-not ($trimmed.StartsWith("|") -and $trimmed.EndsWith("|"))) {
        throw "Ligne de table Markdown invalide: $Line"
    }

    return @($trimmed.Trim("|").Split("|") | ForEach-Object { $_.Trim() })
}

function Read-M012MarkdownTable {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string[]] $Lines,

        [Parameter(Mandatory = $true)]
        [string[]] $RequiredHeaders,

        [Parameter(Mandatory = $true)]
        [string] $TableName
    )

    $headerIndex = -1
    for ($index = 0; $index -lt $Lines.Count; $index++) {
        if ($Lines[$index] -notmatch "^\|") {
            continue
        }

        $headers = Split-M012MarkdownRow -Line $Lines[$index]
        if (($headers.Count -eq $RequiredHeaders.Count) -and (@(Compare-Object -ReferenceObject $RequiredHeaders -DifferenceObject $headers -SyncWindow 0).Count -eq 0)) {
            $headerIndex = $index
            break
        }
    }

    if ($headerIndex -lt 0) {
        throw "Table $TableName absente ou en-têtes invalides: $($RequiredHeaders -join ', ')"
    }

    if (($headerIndex + 1) -ge $Lines.Count) {
        throw "Séparateur absent pour la table $TableName."
    }

    $separatorCells = Split-M012MarkdownRow -Line $Lines[$headerIndex + 1]
    if (($separatorCells.Count -ne $RequiredHeaders.Count) -or (@($separatorCells | Where-Object { $_ -notmatch "^-{3,}$" }).Count -gt 0)) {
        throw "Séparateur invalide pour la table $TableName."
    }

    $rows = New-Object System.Collections.Generic.List[hashtable]
    for ($index = $headerIndex + 2; $index -lt $Lines.Count; $index++) {
        $line = $Lines[$index]
        if ($line -notmatch "^\|") {
            break
        }

        $cells = Split-M012MarkdownRow -Line $line
        if ($cells.Count -ne $RequiredHeaders.Count) {
            throw "Ligne de table $TableName avec nombre de cellules invalide: $line"
        }

        $row = @{}
        for ($cellIndex = 0; $cellIndex -lt $RequiredHeaders.Count; $cellIndex++) {
            $row[$RequiredHeaders[$cellIndex]] = $cells[$cellIndex]
        }
        $rows.Add($row)
    }

    if ($rows.Count -eq 0) {
        throw "Table $TableName sans ligne."
    }

    return $rows.ToArray()
}

function Assert-M012AdrToken {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content,

        [Parameter(Mandatory = $true)]
        [string] $AdrId
    )

    $pattern = "(?<![A-Z0-9-])" + [regex]::Escape($AdrId) + "(?![A-Z0-9-])"
    if (-not [regex]::IsMatch($Content, $pattern)) {
        throw "ADR applicable absente: $AdrId"
    }
}

function Assert-M012NamedRows {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable[]] $Rows,

        [Parameter(Mandatory = $true)]
        [string] $NameColumn,

        [Parameter(Mandatory = $true)]
        [string[]] $RequiredColumns,

        [Parameter(Mandatory = $true)]
        [AllowEmptyCollection()]
        [string[]] $ExpectedNames,

        [Parameter(Mandatory = $true)]
        [string] $Label
    )

    $rowsByName = @{}
    foreach ($row in $Rows) {
        $name = $row[$NameColumn]
        if ([string]::IsNullOrWhiteSpace($name)) {
            throw "$Label sans nom."
        }
        if ($rowsByName.ContainsKey($name)) {
            throw "$Label dupliqué: $name"
        }

        foreach ($requiredColumn in $RequiredColumns) {
            if ([string]::IsNullOrWhiteSpace($row[$requiredColumn])) {
                throw "Colonne $requiredColumn vide pour $name."
            }
        }

        $rowsByName[$name] = $row
    }

    foreach ($expectedName in $ExpectedNames) {
        if (-not $rowsByName.ContainsKey($expectedName)) {
            throw "$Label attendu absent: $expectedName"
        }
    }

    return $rowsByName
}

function Assert-M012Metrics {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable[]] $MetricRows
    )

    $metricsByName = Assert-M012NamedRows `
        -Rows $MetricRows `
        -NameColumn "Signal" `
        -RequiredColumns @("Contexte", "Source normative", "Invariant") `
        -ExpectedNames @() `
        -Label "Métrique M-012"

    foreach ($contextName in $expectedMetricsByContext.Keys) {
        foreach ($metricName in $expectedMetricsByContext[$contextName]) {
            if (-not $metricsByName.ContainsKey($metricName)) {
                throw "Métrique $contextName M-012 absente: $metricName"
            }
            $actualContext = $metricsByName[$metricName]["Contexte"]
            if ($actualContext -ne $contextName) {
                throw "Contexte invalide pour la métrique M-012 $metricName. Attendu: $contextName. Obtenu: $actualContext"
            }
        }
    }
}

function Assert-M012Behaviors {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable[]] $BehaviorRows
    )

    $behaviorsByName = Assert-M012NamedRows `
        -Rows $BehaviorRows `
        -NameColumn "Comportement" `
        -RequiredColumns @("Invariant", "Scénario BDD", "Test RED", "ADR", "Commande") `
        -ExpectedNames @($expectedBehaviors | ForEach-Object { $_.Name }) `
        -Label "Comportement M-012"

    foreach ($expectedBehavior in $expectedBehaviors) {
        $row = $behaviorsByName[$expectedBehavior.Name]
        if ($row["Test RED"] -ne $expectedBehavior.Test) {
            throw "Test RED invalide pour $($expectedBehavior.Name). Attendu: $($expectedBehavior.Test). Obtenu: $($row["Test RED"])"
        }
        if ($row["Commande"] -ne $expectedBehavior.Command) {
            throw "Commande invalide pour $($expectedBehavior.Name). Attendu: $($expectedBehavior.Command). Obtenu: $($row["Commande"])"
        }
        foreach ($adrId in $expectedBehavior.Adr) {
            Assert-M012AdrToken -Content $row["ADR"] -AdrId $adrId
        }
    }
}

function Assert-M012ForbiddenPatterns {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content
    )

    $forbiddenPatterns = @(
        @{ Pattern = "fallback silencieux autoris"; Message = "Fallback silencieux autorisé interdit" },
        @{ Pattern = "seuil par d[ée]faut"; Message = "Seuil par défaut interdit" },
        @{ Pattern = "stockage interne.*contrat public.*autor"; Message = "Stockage interne public interdit" },
        @{ Pattern = "test scientifique.*masqu[ée].*GREEN"; Message = "Résultat scientifique masqué interdit" }
    )

    foreach ($forbiddenPattern in $forbiddenPatterns) {
        if ($Content -match $forbiddenPattern.Pattern) {
            throw $forbiddenPattern.Message + ": " + $Matches[0]
        }
    }
}

function Resolve-M012SpecificationPath {
    param(
        [Parameter(Mandatory = $false)]
        [AllowEmptyString()]
        [string] $InputPath
    )

    if ([string]::IsNullOrWhiteSpace($InputPath)) {
        $candidatePath = Join-Path $repoRoot $defaultSpecificationPath
    }
    elseif ([System.IO.Path]::IsPathRooted($InputPath)) {
        $candidatePath = $InputPath
    }
    else {
        $candidatePath = Join-Path $repoRoot $InputPath
    }

    $resolvedRepositoryRoot = [System.IO.Path]::GetFullPath($repoRoot)
    $resolvedCandidatePath = [System.IO.Path]::GetFullPath($candidatePath)
    $repositoryPrefix = $resolvedRepositoryRoot.TrimEnd("\", "/") + [System.IO.Path]::DirectorySeparatorChar

    if (-not $resolvedCandidatePath.StartsWith($repositoryPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Chemin hors dépôt interdit (spécification M-012): $resolvedCandidatePath"
    }

    return $resolvedCandidatePath
}

function Assert-M012Spec {
    param(
        [Parameter(Mandatory = $true)]
        [string] $SpecPath
    )

    if (-not (Test-Path -LiteralPath $SpecPath -PathType Leaf)) {
        throw "Spécification M-012 absente: $SpecPath"
    }

    $content = (Get-Content -Raw -Encoding UTF8 -LiteralPath $SpecPath).TrimStart([char] 0xFEFF)
    $lines = @(Get-Content -Encoding UTF8 -LiteralPath $SpecPath)
    if ($lines.Count -gt 0) {
        $lines[0] = $lines[0].TrimStart([char] 0xFEFF)
    }

    Assert-M012ForbiddenPatterns -Content $content

    foreach ($section in $requiredSections) {
        if ($lines -notcontains $section) {
            throw "Section obligatoire absente: $section"
        }
    }

    foreach ($marker in $requiredMarkers) {
        Assert-M012Contains -Content $content -Expected $marker -Message "Marqueur obligatoire absent: $marker"
    }

    Assert-M012Contains -Content $content -Expected "50 à 100 PDF" -Message "Borne de corpus pilote absente: 50 à 100 PDF"
    Assert-M012Contains -Content $content -Expected "Aucun fallback silencieux n'est autorisé dans M-012." -Message "Exclusion M-012 absente: Aucun fallback silencieux n'est autorisé dans M-012."

    foreach ($artifact in $requiredArtifacts) {
        Assert-M012Contains -Content $content -Expected $artifact -Message "Artefact M-012 attendu absent: $artifact"
    }

    foreach ($adrId in $requiredAdrIds) {
        Assert-M012AdrToken -Content $content -AdrId $adrId
    }

    foreach ($command in $requiredCommands) {
        Assert-M012Contains -Content $content -Expected $command -Message "Commande de validation absente: $command"
    }

    foreach ($criterion in $expectedCvCriteria) {
        Assert-M012Contains -Content $content -Expected $criterion -Message "Critère CV M-012 absent: $criterion"
    }

    foreach ($checkpoint in $expectedLlmCheckpoints) {
        Assert-M012Contains -Content $content -Expected $checkpoint -Message "Benchmark LLM M-012 absent: $checkpoint"
    }

    foreach ($llmTask in $expectedLlmTasks) {
        Assert-M012Contains -Content $content -Expected $llmTask -Message "Tâche LLM M-012 absente: $llmTask"
    }

    foreach ($llmMetric in $expectedLlmMetrics) {
        Assert-M012Contains -Content $content -Expected $llmMetric -Message "Métrique LLM M-012 absente: $llmMetric"
    }

    $artifactRows = Read-M012MarkdownTable -Lines $lines -RequiredHeaders @("Artefact", "Responsabilité", "Invariants") -TableName "artefacts M-012"
    Assert-M012NamedRows -Rows $artifactRows -NameColumn "Artefact" -RequiredColumns @("Responsabilité", "Invariants") -ExpectedNames $requiredArtifacts -Label "Artefact M-012" | Out-Null

    $policyRows = Read-M012MarkdownTable -Lines $lines -RequiredHeaders @("Politique", "Décision", "Invariants", "ADR") -TableName "politiques M-012"
    Assert-M012NamedRows -Rows $policyRows -NameColumn "Politique" -RequiredColumns @("Décision", "Invariants", "ADR") -ExpectedNames @("PilotCorpusCoveragePolicy", "PageAnnotationPolicy", "DocumentRouteBenchmarkPolicy", "ScientificMetricPolicy", "KnowledgeBenchmarkPolicy", "EvidenceAnswerBenchmarkPolicy", "ConversationCriterionPolicy", "LlmRealPathBenchmarkPolicy", "StrategyExperimentBenchmarkPolicy", "CalibrationDecisionPolicy", "V1GapReportPolicy") -Label "Politique M-012" | Out-Null

    $metricRows = Read-M012MarkdownTable -Lines $lines -RequiredHeaders @("Signal", "Contexte", "Source normative", "Invariant") -TableName "métriques M-012"
    Assert-M012Metrics -MetricRows $metricRows

    $errorRows = Read-M012MarkdownTable -Lines $lines -RequiredHeaders @("Code", "Statut HTTP", "Sens public") -TableName "erreurs publiques M-012"
    Assert-M012NamedRows -Rows $errorRows -NameColumn "Code" -RequiredColumns @("Statut HTTP", "Sens public") -ExpectedNames $expectedPublicErrors -Label "Erreur publique M-012" | Out-Null

    $behaviorRows = Read-M012MarkdownTable -Lines $lines -RequiredHeaders @("Comportement", "Invariant", "Scénario BDD", "Test RED", "ADR", "Commande") -TableName "comportements M-012"
    Assert-M012Behaviors -BehaviorRows $behaviorRows
}

$resolvedPath = Resolve-M012SpecificationPath -InputPath $Path
Assert-M012Spec -SpecPath $resolvedPath

Write-Host "Spécification M-012 valide: $($expectedBehaviors.Count) comportement(s), $($requiredArtifacts.Count) artefact(s), $($expectedMetricsByContext.Keys.Count) contexte(s) métriques contrôlé(s)."
