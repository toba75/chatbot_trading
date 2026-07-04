param(
    [Parameter(Mandatory = $false)]
    [string] $Path
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$defaultSpecificationPath = "docs/specs/m010_strategie_candidate_attribuee.md"

$requiredSections = @(
    "# M-010 - Stratégie candidate attribuée",
    "## Statut",
    "## Scénario BDD",
    "## Mission SD",
    "## Contexte DDD",
    "## Langage ubiquitaire SD",
    "## Agrégats et entités SD",
    "## Objets-valeur SD",
    "## Origines autorisées",
    "## Politiques normatives M-010",
    "## Machine d'états M-010",
    "## Ports et adaptateurs SD",
    "## Événements SD",
    "## API publique SD",
    "### Champs publics interdits",
    "## Erreurs publiques",
    "## Métriques et traces",
    "## Comportements vérifiables M-010",
    "## Commandes de validation",
    "## Exclusions M-010"
)

$requiredMarkers = @(
    "Given la mission M-010 est de formaliser une hypothèse de stratégie attribuée et vérifiable.",
    "When la spécification de stratégie candidate est publiée.",
    "Then chaque comportement M-010 nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.",
    "Une stratégie n'est pas une promesse de rentabilité",
    "M-010 ne lance aucun backtest et ne produit aucun résultat d'expérience M-011.",
    "Aucun accès au stockage interne RA",
    "Aucune lecture du registre EG interne"
)

$requiredTerms = @(
    "StrategyCandidate",
    "StrategyRule",
    "StrategyParameter",
    "RuleOrigin",
    "RuleExpression",
    "ExecutionTiming",
    "DataRequirement",
    "ParameterDomain",
    "RiskConstraint",
    "ValidationPlan",
    "CompatibilityFinding",
    "CompilationDiagnostic",
    "StrategySnapshot",
    "StrategyCompiler",
    "VerifiedResearchOutcome",
    "VerifiedClaimRef",
    "SOURCE",
    "DEDUCTION",
    "DESIGN_CHOICE",
    "PARAMETER_TO_CALIBRATE",
    "USER_CONSTRAINT"
)

$requiredCommands = @(
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m010\validate_m010_specification_acceptance.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m010\validate_m010_specification_unit.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m010_specification.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1"
)

$requiredAdrIds = @(
    "ADR-010",
    "DDD-ADR-009",
    "DDD-ADR-010"
)

$expectedAggregates = @(
    "StrategyCandidate",
    "StrategyRule",
    "StrategyParameter"
)

$expectedValueObjects = @(
    "RuleOrigin",
    "RuleExpression",
    "ExecutionTiming",
    "DataRequirement",
    "ParameterDomain",
    "RiskConstraint",
    "ValidationPlan",
    "CompatibilityFinding",
    "CompilationDiagnostic",
    "StrategySnapshot"
)

$expectedPolicies = @(
    @{ Name = "RuleOriginPolicy"; Adr = @("ADR-010", "DDD-ADR-010") },
    @{ Name = "StrategyCompletenessPolicy"; Adr = @("ADR-010") },
    @{ Name = "StrategyCompatibilityPolicy"; Adr = @("ADR-010", "DDD-ADR-010") },
    @{ Name = "PointInTimeDataPolicy"; Adr = @("ADR-010") },
    @{ Name = "ExecutionFeasibilityPolicy"; Adr = @("ADR-010") },
    @{ Name = "ParameterCalibrationPolicy"; Adr = @("ADR-010") },
    @{ Name = "StrategyCompilationPolicy"; Adr = @("ADR-010", "DDD-ADR-009", "DDD-ADR-010") },
    @{ Name = "StrategySnapshotPolicy"; Adr = @("DDD-ADR-009", "DDD-ADR-010") }
)

$expectedStates = @(
    "DRAFT",
    "SPECIFIED",
    "VALIDATING",
    "INCOMPLETE",
    "INCONSISTENT",
    "COMPILABLE",
    "SNAPSHOTTED",
    "SUPERSEDED"
)

$expectedPorts = @(
    "VerifiedResearchReader",
    "VerifiedClaimReader",
    "StrategyRepository",
    "StrategyCompilerBackend",
    "RuleExpressionValidator",
    "MarketCalendarCatalog",
    "DataAvailabilityCatalog",
    "StrategySnapshotStore",
    "StrategyMetricsPublisher"
)

$expectedEvents = @(
    "StrategyCandidateCreated",
    "StrategyRuleAdded",
    "RuleOriginAssigned",
    "StrategyParameterAdded",
    "CalibrationPlanDefined",
    "StrategyConflictRecorded",
    "StrategyConflictResolved",
    "StrategyCandidateValidated",
    "StrategyCompilationRejected",
    "StrategyCompiled",
    "StrategySnapshotCreated",
    "StrategyVersionSuperseded"
)

$expectedEndpoints = @(
    "POST /v1/strategies/compile",
    "GET /v1/strategies/{id}"
)

$expectedPublicErrors = @(
    "HTTP_REQUEST_INVALID",
    "ENDPOINT_NOT_FOUND",
    "STRATEGY_NOT_FOUND",
    "STRATEGY_MANDATE_REQUIRED",
    "RULE_ORIGIN_REQUIRED",
    "SOURCE_EVIDENCE_REQUIRED",
    "DESIGN_CHOICE_JUSTIFICATION_REQUIRED",
    "PARAMETER_CALIBRATION_REQUIRED",
    "STRATEGY_CONFLICT_BLOCKING",
    "STRATEGY_COMPATIBILITY_FAILED",
    "STRATEGY_NOT_COMPILABLE",
    "STRATEGY_SNAPSHOT_IMMUTABLE",
    "BACKTEST_OUT_OF_SCOPE",
    "PUBLIC_STORAGE_FIELD_FORBIDDEN"
)

$expectedMetrics = @(
    "strategy_candidate_created_total",
    "strategy_rule_origin_assigned_total",
    "strategy_parameter_calibration_required_total",
    "strategy_candidate_validation_failed_total",
    "strategy_candidate_compilation_rejected_total",
    "strategy_candidate_compiled_total",
    "strategy_snapshot_created_total",
    "strategy_public_error_total",
    "strategy_compatibility_finding_total",
    "strategy_version_superseded_total"
)

$expectedBehaviors = @(
    @{ Name = "SD-001 - Spécification exécutable M-010"; Adr = @("ADR-010", "DDD-ADR-009", "DDD-ADR-010"); Test = "T-002"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m010_specification.ps1" },
    @{ Name = "SD-002 - Ouverture depuis résultat vérifié"; Adr = @("ADR-010", "DDD-ADR-010"); Test = "T-003"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m010\validate_strategy_candidate_opening_acceptance.ps1" },
    @{ Name = "SD-003 - Origines de règles attribuées"; Adr = @("ADR-010", "DDD-ADR-010"); Test = "T-004"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m010\validate_strategy_rule_origin_acceptance.ps1" },
    @{ Name = "SD-004 - Paramètres à calibrer cadrés"; Adr = @("ADR-010"); Test = "T-005"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m010\validate_strategy_parameter_calibration_acceptance.ps1" },
    @{ Name = "SD-005 - Compatibilité analysée"; Adr = @("ADR-010", "DDD-ADR-010"); Test = "T-006"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m010\validate_strategy_compatibility_acceptance.ps1" },
    @{ Name = "SD-006 - Diagnostics bloquants de validation"; Adr = @("ADR-010", "DDD-ADR-010"); Test = "T-007"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m010\validate_strategy_candidate_diagnostics_acceptance.ps1" },
    @{ Name = "SD-007 - Compilation déterministe sans backtest"; Adr = @("ADR-010", "DDD-ADR-009"); Test = "T-008"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m010\validate_strategy_compilation_acceptance.ps1" },
    @{ Name = "SD-008 - Snapshot immuable hashé"; Adr = @("DDD-ADR-009", "DDD-ADR-010"); Test = "T-009"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m010\validate_strategy_snapshot_acceptance.ps1" },
    @{ Name = "SD-009 - Endpoints stratégies sans stockage interne"; Adr = @("ADR-010", "DDD-ADR-009"); Test = "T-010"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m010\validate_strategy_http_contract_acceptance.ps1" },
    @{ Name = "SD-010 - Traçabilité et métriques M-010"; Adr = @("ADR-010", "DDD-ADR-009", "DDD-ADR-010"); Test = "T-011"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m010\validate_m010_traceability_acceptance.ps1" }
)

function Assert-M010Contains {
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

function Split-M010MarkdownRow {
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

function Read-M010MarkdownTable {
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

        $headers = Split-M010MarkdownRow -Line $Lines[$index]
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

    $separatorCells = Split-M010MarkdownRow -Line $Lines[$headerIndex + 1]
    if (($separatorCells.Count -ne $RequiredHeaders.Count) -or (@($separatorCells | Where-Object { $_ -notmatch "^-{3,}$" }).Count -gt 0)) {
        throw "Séparateur invalide pour la table $TableName."
    }

    $rows = New-Object System.Collections.Generic.List[hashtable]
    for ($index = $headerIndex + 2; $index -lt $Lines.Count; $index++) {
        $line = $Lines[$index]
        if ($line -notmatch "^\|") {
            break
        }

        $cells = Split-M010MarkdownRow -Line $line
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

function Assert-M010AdrToken {
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

function Assert-M010NamedRows {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable[]] $Rows,

        [Parameter(Mandatory = $true)]
        [string] $NameColumn,

        [Parameter(Mandatory = $true)]
        [string[]] $RequiredColumns,

        [Parameter(Mandatory = $true)]
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

function Assert-M010Policies {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable[]] $PolicyRows
    )

    $policiesByName = Assert-M010NamedRows `
        -Rows $PolicyRows `
        -NameColumn "Politique" `
        -RequiredColumns @("Décision", "Invariants", "ADR") `
        -ExpectedNames @($expectedPolicies | ForEach-Object { $_.Name }) `
        -Label "Politique M-010"

    foreach ($expectedPolicy in $expectedPolicies) {
        $row = $policiesByName[$expectedPolicy.Name]
        foreach ($adrId in $expectedPolicy.Adr) {
            Assert-M010AdrToken -Content $row["ADR"] -AdrId $adrId
        }
    }
}

function Assert-M010Behaviors {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable[]] $BehaviorRows
    )

    $behaviorsByName = Assert-M010NamedRows `
        -Rows $BehaviorRows `
        -NameColumn "Comportement" `
        -RequiredColumns @("Invariant", "Scénario BDD", "Test RED", "ADR", "Commande") `
        -ExpectedNames @($expectedBehaviors | ForEach-Object { $_.Name }) `
        -Label "Comportement M-010"

    foreach ($expectedBehavior in $expectedBehaviors) {
        $row = $behaviorsByName[$expectedBehavior.Name]
        if ($row["Test RED"] -ne $expectedBehavior.Test) {
            throw "Test RED invalide pour $($expectedBehavior.Name). Attendu: $($expectedBehavior.Test). Obtenu: $($row["Test RED"])"
        }
        if ($row["Commande"] -ne $expectedBehavior.Command) {
            throw "Commande invalide pour $($expectedBehavior.Name). Attendu: $($expectedBehavior.Command). Obtenu: $($row["Commande"])"
        }
        foreach ($adrId in $expectedBehavior.Adr) {
            Assert-M010AdrToken -Content $row["ADR"] -AdrId $adrId
        }
    }
}

function Assert-M010ForbiddenPatterns {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content
    )

    $forbiddenPatterns = @(
        @{ Pattern = "strat[ée]gie\s+rentable"; Message = "Promesse de rentabilité interdite" },
        @{ Pattern = "SD\s+lit\s+le\s+stockage\s+interne\s+RA"; Message = "Accès SD direct au stockage RA interdit" },
        @{ Pattern = "SD\s+lit\s+le\s+registre\s+EG\s+interne"; Message = "Accès SD direct au registre EG interdit" },
        @{ Pattern = "backtest\s+est\s+lanc[ée]"; Message = "Backtest M-010 interdit" },
        @{ Pattern = "(utilise|fabrique|accepte)\s+.*valeur\s+de\s+march[ée]\s+invent[ée]e"; Message = "Valeur de marché inventée interdite" },
        @{ Pattern = "POST /v1/strategies/compile.*(ra_repository_table|eg_registry_table|qdrant_collection).*succ[èe]s"; Message = "Exposition de stockage interne interdite" }
    )

    foreach ($forbiddenPattern in $forbiddenPatterns) {
        if ($Content -match $forbiddenPattern.Pattern) {
            throw $forbiddenPattern.Message + ": " + $Matches[0]
        }
    }
}

function Resolve-M010SpecificationPath {
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
        throw "Chemin hors dépôt interdit (spécification M-010): $resolvedCandidatePath"
    }

    return $resolvedCandidatePath
}

function Assert-M010Spec {
    param(
        [Parameter(Mandatory = $true)]
        [string] $SpecPath
    )

    if (-not (Test-Path -LiteralPath $SpecPath -PathType Leaf)) {
        throw "Spécification M-010 absente: $SpecPath"
    }

    $content = (Get-Content -Raw -Encoding UTF8 -LiteralPath $SpecPath).TrimStart([char] 0xFEFF)
    $lines = @(Get-Content -Encoding UTF8 -LiteralPath $SpecPath)
    if ($lines.Count -gt 0) {
        $lines[0] = $lines[0].TrimStart([char] 0xFEFF)
    }

    Assert-M010ForbiddenPatterns -Content $content

    foreach ($section in $requiredSections) {
        if ($lines -notcontains $section) {
            throw "Section obligatoire absente: $section"
        }
    }

    foreach ($marker in $requiredMarkers) {
        Assert-M010Contains -Content $content -Expected $marker -Message "Marqueur obligatoire absent: $marker"
    }

    foreach ($adrId in $requiredAdrIds) {
        Assert-M010AdrToken -Content $content -AdrId $adrId
    }

    foreach ($term in $requiredTerms) {
        Assert-M010Contains -Content $content -Expected $term -Message "Terme du langage SD absent: $term"
    }

    foreach ($command in $requiredCommands) {
        Assert-M010Contains -Content $content -Expected $command -Message "Commande de validation absente: $command"
    }

    $aggregateRows = Read-M010MarkdownTable -Lines $lines -RequiredHeaders @("Agrégat", "Responsabilité M-010", "Invariants", "Événements") -TableName "agrégats M-010"
    Assert-M010NamedRows -Rows $aggregateRows -NameColumn "Agrégat" -RequiredColumns @("Responsabilité M-010", "Invariants", "Événements") -ExpectedNames $expectedAggregates -Label "Agrégat M-010" | Out-Null

    $valueObjectRows = Read-M010MarkdownTable -Lines $lines -RequiredHeaders @("Objet-valeur", "Sens M-010", "Invariants") -TableName "objets-valeur M-010"
    Assert-M010NamedRows -Rows $valueObjectRows -NameColumn "Objet-valeur" -RequiredColumns @("Sens M-010", "Invariants") -ExpectedNames $expectedValueObjects -Label "Objet-valeur M-010" | Out-Null

    $originRows = Read-M010MarkdownTable -Lines $lines -RequiredHeaders @("Origine", "Exigence", "Diagnostic si absente") -TableName "origines M-010"
    Assert-M010NamedRows -Rows $originRows -NameColumn "Origine" -RequiredColumns @("Exigence", "Diagnostic si absente") -ExpectedNames @("SOURCE", "DEDUCTION", "DESIGN_CHOICE", "PARAMETER_TO_CALIBRATE", "USER_CONSTRAINT") -Label "Origine M-010" | Out-Null

    $policyRows = Read-M010MarkdownTable -Lines $lines -RequiredHeaders @("Politique", "Décision", "Invariants", "ADR") -TableName "politiques M-010"
    Assert-M010Policies -PolicyRows $policyRows

    $stateRows = Read-M010MarkdownTable -Lines $lines -RequiredHeaders @("État", "Portée", "Sens M-010", "Transition autorisée") -TableName "états M-010"
    Assert-M010NamedRows -Rows $stateRows -NameColumn "État" -RequiredColumns @("Portée", "Sens M-010", "Transition autorisée") -ExpectedNames $expectedStates -Label "État M-010" | Out-Null

    $portRows = Read-M010MarkdownTable -Lines $lines -RequiredHeaders @("Port", "Responsabilité", "Interdiction") -TableName "ports M-010"
    Assert-M010NamedRows -Rows $portRows -NameColumn "Port" -RequiredColumns @("Responsabilité", "Interdiction") -ExpectedNames $expectedPorts -Label "Port M-010" | Out-Null

    $eventRows = Read-M010MarkdownTable -Lines $lines -RequiredHeaders @("Événement", "Déclencheur", "Payload publié") -TableName "événements M-010"
    Assert-M010NamedRows -Rows $eventRows -NameColumn "Événement" -RequiredColumns @("Déclencheur", "Payload publié") -ExpectedNames $expectedEvents -Label "Événement M-010" | Out-Null

    $endpointRows = Read-M010MarkdownTable -Lines $lines -RequiredHeaders @("Endpoint", "Succès", "Erreurs publiques", "Corps public") -TableName "API M-010"
    Assert-M010NamedRows -Rows $endpointRows -NameColumn "Endpoint" -RequiredColumns @("Succès", "Erreurs publiques", "Corps public") -ExpectedNames $expectedEndpoints -Label "Endpoint M-010" | Out-Null

    $errorRows = Read-M010MarkdownTable -Lines $lines -RequiredHeaders @("Code", "Statut HTTP", "Sens public") -TableName "erreurs publiques M-010"
    Assert-M010NamedRows -Rows $errorRows -NameColumn "Code" -RequiredColumns @("Statut HTTP", "Sens public") -ExpectedNames $expectedPublicErrors -Label "Erreur publique M-010" | Out-Null

    $metricRows = Read-M010MarkdownTable -Lines $lines -RequiredHeaders @("Signal", "Type", "Invariant") -TableName "métriques M-010"
    Assert-M010NamedRows -Rows $metricRows -NameColumn "Signal" -RequiredColumns @("Type", "Invariant") -ExpectedNames $expectedMetrics -Label "Signal M-010" | Out-Null

    $behaviorRows = Read-M010MarkdownTable -Lines $lines -RequiredHeaders @("Comportement", "Invariant", "Scénario BDD", "Test RED", "ADR", "Commande") -TableName "comportements M-010"
    Assert-M010Behaviors -BehaviorRows $behaviorRows
}

$resolvedPath = Resolve-M010SpecificationPath -InputPath $Path
Assert-M010Spec -SpecPath $resolvedPath

Write-Host "Spécification M-010 valide: $($expectedBehaviors.Count) comportement(s), $($expectedPolicies.Count) politique(s), $($expectedStates.Count) état(s) contrôlé(s)."
