param(
    [Parameter(Mandatory = $false)]
    [string] $RunbookRoot,

    [Parameter(Mandatory = $false)]
    [string] $UserGuidePath,

    [Parameter(Mandatory = $false)]
    [string] $DocumentationIndexPath,

    [Parameter(Mandatory = $false)]
    [string] $MatrixPath,

    [Parameter(Mandatory = $false)]
    [string] $TestGatePath,

    [Parameter(Mandatory = $false)]
    [string] $LintGatePath
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)

$defaultRunbookRoot = "docs/runbooks"
$defaultUserGuidePath = "docs/user/v1_guide_utilisateur.md"
$defaultDocumentationIndexPath = "docs/governance/m013_documentation_index.md"
$defaultMatrixPath = "docs/traceability/matrix.md"
$defaultTestGatePath = "scripts/test.ps1"
$defaultLintGatePath = "scripts/lint.ps1"

$requiredRunbooks = @(
    @{
        Id = "exploitation_locale"
        File = "exploitation_locale.md"
        Markers = @(
            "# Runbook démarrage et arrêt local M-013",
            "M013-Runbook-LocalOperations-1.0",
            "Démarrage local",
            "Arrêt local",
            "docker compose -f .\deploy\local-compose\compose.yaml up --build",
            "docker compose -f .\deploy\local-compose\compose.yaml down",
            "scripts\validate_local_compose.ps1",
            "scripts\validate_network_boundary.ps1",
            "Résultat attendu",
            "Erreur explicite",
            "Preuve à conserver"
        )
    },
    @{
        Id = "sauvegarde_restauration"
        File = "sauvegarde_restauration.md"
        Markers = @(
            "# Runbook sauvegarde et restauration M-013",
            "M013-BackupRestoreDrill-1.0",
            "M013-BackupManifest-1.0",
            "restore_test_result",
            "docs/governance/m013_backup_restore_drill.md",
            "scripts\validate_m013_backup_restore.ps1",
            "clé hors dépôt",
            "restauration isolée",
            "aucune restauration destructive",
            "Résultat attendu",
            "Erreur explicite",
            "Preuve à conserver"
        )
    },
    @{
        Id = "spark_reseau_incidents"
        File = "spark_reseau_incidents.md"
        Markers = @(
            "# Runbook audit réseau et incidents Spark M-013",
            "M013-SecurityAuditReport-1.0",
            "M013-SPARK-FAILURE-DRILL-0001",
            "llm-gateway -> spark-inference",
            "Accès direct Spark depuis navigateur: interdit",
            "Publication de service interne: interdite",
            "docs/governance/m013_security_audit.md",
            "docs/governance/m013_spark_failure_drill.md",
            "scripts\validate_m013_security.ps1",
            "scripts\validate_m013_spark_failures.ps1"
        )
    },
    @{
        Id = "monitoring_local"
        File = "monitoring_local.md"
        Markers = @(
            "# Runbook monitoring local M-013",
            "M013-LocalMonitoringProfile-1.0",
            "M013-ResourceProfile-1.0",
            "v1_health_status",
            "v1_error_total",
            "v1_latency_ms",
            "spark_inference_availability",
            "backup_restore_result",
            "v1_gap_status",
            "network_security_violation_total",
            "scripts\validate_m013_monitoring.ps1",
            "docs/governance/m013_local_monitoring.md",
            "docs/governance/m013_resource_profile.md",
            "aucun export externe",
            "aucun endpoint public"
        )
    },
    @{
        Id = "ingestion_pdf"
        File = "ingestion_pdf.md"
        Markers = @(
            "# Runbook ingestion PDF V1 M-013",
            "ingestion PDF",
            "SourceDocumentId",
            "SourceLocator",
            "quarantaine",
            "route explicite",
            "version canonique",
            "scripts\validate_m003_specification.ps1",
            "scripts\validate_m004_specification.ps1",
            "statut public",
            "Résultat attendu",
            "Erreur explicite"
        )
    },
    @{
        Id = "conversation_v1"
        File = "conversation_v1.md"
        Markers = @(
            "# Runbook conversation V1 M-013",
            "conversation",
            "SUPPORTED",
            "PARTIALLY_SUPPORTED",
            "INSUFFICIENT_EVIDENCE",
            "CONFLICTING_EVIDENCE",
            "LLM_UNAVAILABLE",
            "citations ouvrables",
            "historique non factuel",
            "scripts\validate_m008_specification.ps1",
            "scripts\validate_m013_spark_failures.ps1",
            "Fallback silencieux: interdit"
        )
    },
    @{
        Id = "recherche_approfondie"
        File = "recherche_approfondie.md"
        Markers = @(
            "# Runbook recherche approfondie V1 M-013",
            "recherche approfondie",
            "multi-sources",
            "couverture insuffisante",
            "contradictions",
            "obligations de recherche",
            "SUPPORTED",
            "PARTIALLY_SUPPORTED",
            "INSUFFICIENT_EVIDENCE",
            "CONFLICTING_EVIDENCE",
            "scripts\validate_m009_specification.ps1",
            "Résultat attendu",
            "Erreur explicite"
        )
    },
    @{
        Id = "strategie_backtest"
        File = "strategie_backtest.md"
        Markers = @(
            "# Runbook stratégie et backtest V1 M-013",
            "stratégie candidate",
            "backtest",
            "strategy_compilable_rate",
            "strategy_rejection_reason_distribution",
            "strategy_parameter_without_calibration_plan_total",
            "strategy_compatibility_conflict_total",
            "experiment_reproducible_rate",
            "negative_experiment_retention_ratio",
            "SD | bloquant",
            "Aucune promesse financière",
            "scripts\validate_m010_specification.ps1",
            "scripts\validate_m011_specification.ps1",
            "tests\m012\validate_strategy_backtest_benchmark_acceptance.ps1"
        )
    }
)

$requiredUserGuideMarkers = @(
    "# Guide utilisateur V1 M-013",
    "M013-UserDocumentation-1.0",
    "conversation locale",
    "citations ouvrables",
    "statuts publics",
    "SUPPORTED",
    "PARTIALLY_SUPPORTED",
    "INSUFFICIENT_EVIDENCE",
    "CONFLICTING_EVIDENCE",
    "stratégie candidate attribuée",
    "expérience reproductible",
    "limites V1",
    "aucune promesse financière",
    "aucun conseil d'investissement",
    "aucun fallback silencieux",
    "aucun secret"
)

$requiredIndexMarkers = @(
    "# Index documentation M-013",
    "M013-DocumentationIndex-1.0",
    "docs/runbooks/exploitation_locale.md",
    "docs/runbooks/sauvegarde_restauration.md",
    "docs/runbooks/spark_reseau_incidents.md",
    "docs/runbooks/monitoring_local.md",
    "docs/runbooks/ingestion_pdf.md",
    "docs/runbooks/conversation_v1.md",
    "docs/runbooks/recherche_approfondie.md",
    "docs/runbooks/strategie_backtest.md",
    "docs/user/v1_guide_utilisateur.md",
    "Commandes vérifiées",
    "Limites et écarts V1",
    "Aucune publication de service interne",
    "Aucun secret",
    "Aucune promesse financière",
    "ADR: non requise"
)

$requiredGlobalMarkers = @(
    "démarrage local",
    "arrêt local",
    "sauvegarde",
    "restauration",
    "audit réseau",
    "panne Spark",
    "monitoring",
    "ingestion PDF",
    "conversation",
    "recherche approfondie",
    "stratégie",
    "backtest",
    "statuts publics",
    "limites V1",
    "écarts V1",
    "commandes vérifiées",
    "aucune publication de service interne",
    "aucun secret",
    "aucune promesse financière"
)

$requiredSparkStatuses = @(
    "LLM_UNAVAILABLE",
    "LLM_FIRST_TOKEN_TIMEOUT",
    "LLM_TLS_CERTIFICATE_INVALID",
    "LLM_AUTHENTICATION_FAILED",
    "LLM_PARTIAL_OUTPUT",
    "LLM_CIRCUIT_OPEN",
    "LLM_RECOVERED"
)

$requiredNonAcceptedGaps = @(
    @{ Context = "SP"; Marker = "SP | différé" },
    @{ Context = "KA"; Marker = "KA | différé" },
    @{ Context = "RA"; Marker = "RA | différé" },
    @{ Context = "SD"; Marker = "SD | bloquant" },
    @{ Context = "LLM"; Marker = "LLM | bloquant" }
)

$forbiddenSecretPatterns = @(
    "BEGIN PRIVATE KEY",
    "END PRIVATE KEY",
    "POSTGRES_PASSWORD\s*=",
    "QDRANT_API_KEY\s*=",
    "GEMMA_API_KEY\s*=",
    "VLLM_API_KEY\s*=",
    "Authorization:\s*Bearer",
    "SECRET_INTERDIT_M013"
)

$forbiddenFallbackPatterns = @(
    "fallback textuel",
    "réponse de secours",
    "reponse de secours",
    "mode dégradé automatique",
    "provider de secours",
    "modèle de secours",
    "modele de secours"
)

$forbiddenProfitPatterns = @(
    "garantit la rentabilité",
    "garantit la rentabilite",
    "rentabilité garantie",
    "rentabilite garantie",
    "rendement garanti",
    "profit garanti"
)

$forbiddenInternalPublicationPatterns = @(
    "0\.0\.0\.0:8443",
    "docker\s+run\s+-p",
    "spark-inference.*0\.0\.0\.0",
    "publier\s+spark\s+publiquement"
)

$destructiveCommandPatterns = @(
    "Remove-Item\s+.*-Recurse.*-Force",
    "docker\s+compose\b.*\sdown\s+-v\b",
    "docker\s+volume\s+rm\b",
    "\brm\s+-rf\b",
    "DROP\s+DATABASE"
)

function Assert-M013Condition {
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

function Assert-M013Contains {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content,

        [Parameter(Mandatory = $true)]
        [string] $Expected,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    Assert-M013Condition -Condition ($Content.Contains($Expected)) -Message $Message
}

function Resolve-M013RequiredPath {
    param(
        [Parameter(Mandatory = $false)]
        [AllowEmptyString()]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [string] $DefaultRelativePath,

        [Parameter(Mandatory = $true)]
        [string] $Label,

        [Parameter(Mandatory = $true)]
        [ValidateSet("Leaf", "Container")]
        [string] $PathType
    )

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

    Assert-M013Condition `
        -Condition ($resolvedPath.StartsWith($repositoryPrefix, [System.StringComparison]::OrdinalIgnoreCase)) `
        -Message "Chemin hors dépôt interdit ($Label): $resolvedPath"
    Assert-M013Condition `
        -Condition (Test-Path -LiteralPath $resolvedPath -PathType $PathType) `
        -Message "Fichier requis absent ($Label): $resolvedPath"

    return $resolvedPath
}

function Convert-ToM013RelativePath {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path
    )

    $relativePath = $Path.Replace("\", "/")
    if ($relativePath.StartsWith("./")) {
        $relativePath = $relativePath.Substring(2)
    }
    return $relativePath
}

function Get-M013DocumentContent {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path
    )

    return (Get-Content -Raw -Encoding UTF8 -LiteralPath $Path).TrimStart([char] 0xFEFF)
}

function Assert-M013PowerShellCommandsExist {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content
    )

    $commandMatches = [regex]::Matches(
        $Content,
        "-File\s+\.\\(?<path>(?:scripts|tests)\\[A-Za-z0-9_.\\-]+(?:\\[A-Za-z0-9_.\\-]+)*\.ps1)",
        [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
    )

    foreach ($match in $commandMatches) {
        $relativePath = Convert-ToM013RelativePath -Path $match.Groups["path"].Value
        $candidatePath = Join-Path $repoRoot $relativePath
        if (-not (Test-Path -LiteralPath $candidatePath -PathType Leaf)) {
            throw "Commande PowerShell référencée absente: $relativePath"
        }
    }
}

function Assert-M013ProofReferencesExist {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content
    )

    $pathMatches = [regex]::Matches(
        $Content,
        "(?<path>(?:docs|deploy|scripts|tests|app)[/\\][A-Za-z0-9_. /\\-]+?\.[A-Za-z0-9]+)",
        [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
    )

    $seenPaths = New-Object System.Collections.Generic.HashSet[string]
    foreach ($match in $pathMatches) {
        $relativePath = Convert-ToM013RelativePath -Path $match.Groups["path"].Value.Trim().TrimEnd(".", ",", ";", ")", "]")
        if (-not $seenPaths.Add($relativePath)) {
            continue
        }

        $candidatePath = Join-Path $repoRoot $relativePath
        if (-not (Test-Path -LiteralPath $candidatePath)) {
            throw "Preuve référencée absente: $relativePath"
        }
    }
}

function Assert-M013ForbiddenText {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content
    )

    foreach ($pattern in $forbiddenSecretPatterns) {
        if ([regex]::IsMatch($Content, $pattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)) {
            throw "Secret interdit dans la documentation M-013: $pattern"
        }
    }

    foreach ($pattern in $forbiddenFallbackPatterns) {
        if ([regex]::IsMatch($Content, $pattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)) {
            throw "Fallback textuel interdit: $pattern"
        }
    }

    foreach ($pattern in $forbiddenProfitPatterns) {
        if ([regex]::IsMatch($Content, $pattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)) {
            throw "Promesse de rentabilité interdite: $pattern"
        }
    }

    foreach ($pattern in $forbiddenInternalPublicationPatterns) {
        if ([regex]::IsMatch($Content, $pattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)) {
            throw "Publication de service interne interdite: $pattern"
        }
    }

    foreach ($pattern in $destructiveCommandPatterns) {
        if ([regex]::IsMatch($Content, $pattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)) {
            throw "Commande destructive sans précondition: $pattern"
        }
    }
}

function Assert-M013RunbookDocument {
    param(
        [Parameter(Mandatory = $true)]
        [string] $RunbookPath,

        [Parameter(Mandatory = $true)]
        [string] $RunbookId,

        [Parameter(Mandatory = $true)]
        [string[]] $Markers
    )

    if (-not (Test-Path -LiteralPath $RunbookPath -PathType Leaf)) {
        throw "Runbook critique absent: $RunbookId"
    }

    $content = Get-M013DocumentContent -Path $RunbookPath
    Assert-M013PowerShellCommandsExist -Content $content
    Assert-M013ProofReferencesExist -Content $content
    foreach ($marker in $Markers) {
        Assert-M013Contains -Content $content -Expected $marker -Message "Marqueur runbook absent ($RunbookId): $marker"
    }

    foreach ($marker in @("Commande vérifiée", "Résultat attendu", "Erreur explicite", "Preuve à conserver")) {
        Assert-M013Contains -Content $content -Expected $marker -Message "Procédure incomplète ($RunbookId): $marker"
    }
}

function Assert-M013Traceability {
    param(
        [Parameter(Mandatory = $true)]
        [string] $MatrixContent,

        [Parameter(Mandatory = $true)]
        [string] $TestGateContent,

        [Parameter(Mandatory = $true)]
        [string] $LintGateContent
    )

    foreach ($marker in @(
        "REQ-M013-010",
        "docs/tasks/milestone_013/0010_publier_runbooks_documentation_utilisateur.md",
        "tests/m013/validate_runbooks_user_docs_acceptance.ps1",
        "tests/m013/validate_runbooks_user_docs_unit.ps1",
        "scripts/validate_m013_runbooks.ps1",
        "docs/runbooks/exploitation_locale.md",
        "docs/runbooks/spark_reseau_incidents.md",
        "docs/governance/m013_documentation_index.md",
        "docs/user/v1_guide_utilisateur.md",
        "ADR-010"
    )) {
        Assert-M013Contains -Content $MatrixContent -Expected $marker -Message "Traçabilité T-010 absente: $marker"
    }

    foreach ($marker in @(
        "scripts/validate_m013_runbooks.ps1",
        "tests/m013/validate_runbooks_user_docs_acceptance.ps1",
        "tests/m013/validate_runbooks_user_docs_unit.ps1"
    )) {
        Assert-M013Contains -Content $TestGateContent -Expected $marker -Message "Gate test sans runbooks documentation M-013: $marker"
    }

    Assert-M013Contains `
        -Content $LintGateContent `
        -Expected "scripts/validate_m013_runbooks.ps1" `
        -Message "Gate lint sans validateur runbooks documentation M-013."
}

$resolvedRunbookRoot = Resolve-M013RequiredPath -Path $RunbookRoot -DefaultRelativePath $defaultRunbookRoot -Label "runbooks" -PathType Container
$resolvedUserGuidePath = Resolve-M013RequiredPath -Path $UserGuidePath -DefaultRelativePath $defaultUserGuidePath -Label "documentation utilisateur V1" -PathType Leaf
$resolvedDocumentationIndexPath = Resolve-M013RequiredPath -Path $DocumentationIndexPath -DefaultRelativePath $defaultDocumentationIndexPath -Label "index documentation M-013" -PathType Leaf
$resolvedMatrixPath = Resolve-M013RequiredPath -Path $MatrixPath -DefaultRelativePath $defaultMatrixPath -Label "matrice" -PathType Leaf
$resolvedTestGatePath = Resolve-M013RequiredPath -Path $TestGatePath -DefaultRelativePath $defaultTestGatePath -Label "gate test" -PathType Leaf
$resolvedLintGatePath = Resolve-M013RequiredPath -Path $LintGatePath -DefaultRelativePath $defaultLintGatePath -Label "gate lint" -PathType Leaf

$documentContents = New-Object System.Collections.Generic.List[string]

foreach ($runbook in $requiredRunbooks) {
    $runbookPath = Join-Path $resolvedRunbookRoot $runbook.File
    Assert-M013RunbookDocument -RunbookPath $runbookPath -RunbookId $runbook.Id -Markers $runbook.Markers
    $runbookContent = Get-M013DocumentContent -Path $runbookPath
    if ($runbook.Id -eq "spark_reseau_incidents") {
        foreach ($status in $requiredSparkStatuses) {
            Assert-M013Contains -Content $runbookContent -Expected $status -Message "Statut public absent: $status"
        }
    }
    $documentContents.Add($runbookContent)
}

$userGuideContent = Get-M013DocumentContent -Path $resolvedUserGuidePath
foreach ($marker in $requiredUserGuideMarkers) {
    Assert-M013Contains -Content $userGuideContent -Expected $marker -Message "Documentation utilisateur V1 incomplète: $marker"
}

foreach ($gap in $requiredNonAcceptedGaps) {
    Assert-M013Contains -Content $userGuideContent -Expected $gap.Marker -Message "Écart V1 non accepté absent: $($gap.Context)"
}
$documentContents.Add($userGuideContent)

$indexContent = Get-M013DocumentContent -Path $resolvedDocumentationIndexPath
foreach ($marker in $requiredIndexMarkers) {
    Assert-M013Contains -Content $indexContent -Expected $marker -Message "Index documentation M-013 incomplet: $marker"
}
$documentContents.Add($indexContent)

$combinedContent = ($documentContents.ToArray() -join "`n")
foreach ($marker in $requiredGlobalMarkers) {
    Assert-M013Contains -Content $combinedContent.ToLowerInvariant() -Expected $marker.ToLowerInvariant() -Message "Couverture documentaire M-013 absente: $marker"
}

Assert-M013PowerShellCommandsExist -Content $combinedContent
Assert-M013ProofReferencesExist -Content $combinedContent
Assert-M013ForbiddenText -Content $combinedContent

$matrixContent = Get-M013DocumentContent -Path $resolvedMatrixPath
$testGateContent = Get-M013DocumentContent -Path $resolvedTestGatePath
$lintGateContent = Get-M013DocumentContent -Path $resolvedLintGatePath
Assert-M013Traceability -MatrixContent $matrixContent -TestGateContent $testGateContent -LintGateContent $lintGateContent

Write-Host "Runbooks documentation utilisateur M-013 valides: $($requiredRunbooks.Count) runbook(s), documentation utilisateur V1, commandes vérifiées, écarts V1 non acceptés visibles, aucun secret, aucun service interne publié, aucune promesse financière."

