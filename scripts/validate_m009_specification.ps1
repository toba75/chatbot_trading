param(
    [Parameter(Mandatory = $false)]
    [string] $Path
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$defaultSpecificationPath = "docs/specs/m009_recherche_approfondie_multi_sources.md"

$requiredSections = @(
    "# M-009 - Recherche approfondie multi-sources",
    "## Statut",
    "## Scénario BDD",
    "## Mission RA approfondie",
    "## Contexte DDD",
    "## Langage ubiquitaire RA approfondie",
    "## Agrégats RA approfondie",
    "## Objets-valeur RA approfondie",
    "## Politiques normatives M-009",
    "## Machine d'états M-009",
    "## Ports et adaptateurs RA approfondie",
    "## Événements RA approfondie",
    "## API publique RA approfondie",
    "## Erreurs publiques",
    "## Métriques et traces",
    "## Comportements vérifiables M-009",
    "## Commandes de validation",
    "## Exclusions M-009"
)

$requiredAdrIds = @(
    "ADR-006",
    "ADR-010",
    "DDD-ADR-003",
    "DDD-ADR-005",
    "DDD-ADR-007",
    "DDD-ADR-008"
)

$requiredMarkers = @(
    "Given la mission M-009 est d'analyser plusieurs sources sans effacer nuances, limites et contradictions.",
    "When la spécification de recherche approfondie est publiée.",
    "Then chaque comportement M-009 nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.",
    "Une recherche approfondie possède un plan et des obligations de couverture.",
    "Les versions de projection et de claims sont enregistrées.",
    "Une contradiction pertinente n'est pas omise.",
    "La fréquence de citation ne devient pas consensus.",
    "Source, déduction et choix de conception restent distingués.",
    "RA consomme KnowledgeSearch sans accès direct à Qdrant",
    "RA consomme VerifiedClaimCatalog sans lecture du registre EG interne",
    "Aucune synthèse SUPPORTED n'est publiée sans couverture minimale.",
    "M-009 ne livre pas la stratégie candidate attribuée M-010 ni l'expérience reproductible M-011."
)

$requiredTerms = @(
    "ResearchCase",
    "Answer",
    "ResearchMandate",
    "ResearchMode",
    "RECHERCHE_APPROFONDIE",
    "DeepResearchPlan",
    "ResearchSubQuestion",
    "CoverageObligation",
    "EvidencePolarity",
    "IndependentEvidenceGroup",
    "VerifiedClaimRef",
    "VerifiedClaimVersionRef",
    "ProjectionVersionRef",
    "ConditionalContradiction",
    "DocumentaryGap",
    "MultiSourceSynthesis",
    "DeepResearchSupportStatus",
    "KnowledgeSearch",
    "VerifiedClaimCatalog",
    "ProjectionVersionCatalog",
    "POST /v1/research/deep",
    "SUPPORTED",
    "PARTIALLY_SUPPORTED",
    "INSUFFICIENT_COVERAGE",
    "CONFLICTING_EVIDENCE",
    "REQUIRES_CURRENT_DATA",
    "DEEP_RESEARCH_MANDATE_REQUIRED",
    "COVERAGE_OBLIGATION_MISSING",
    "COVERAGE_INSUFFICIENT",
    "CLAIM_DEPENDENCY_UNRESOLVED",
    "CONTRADICTION_UNCLASSIFIED",
    "PUBLIC_STORAGE_FIELD_FORBIDDEN"
)

$requiredCommands = @(
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_m009_specification_acceptance.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_m009_specification_unit.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m009_specification.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1"
)

$expectedAggregates = @(
    "ResearchCase",
    "Answer"
)

$expectedValueObjects = @(
    "ResearchMandate",
    "ResearchMode",
    "DeepResearchPlan",
    "ResearchSubQuestion",
    "CoverageObligation",
    "EvidencePolarity",
    "IndependentEvidenceGroup",
    "ProjectionVersionRef",
    "VerifiedClaimVersionRef",
    "ConditionalContradiction",
    "DocumentaryGap",
    "MultiSourceSynthesis",
    "DeepResearchSupportStatus"
)

$expectedPolicies = @(
    @{ Name = "DeepResearchMandatePolicy"; Adr = @("ADR-010", "DDD-ADR-007") },
    @{ Name = "ResearchModePolicy"; Adr = @("ADR-010", "DDD-ADR-007") },
    @{ Name = "DeepResearchPlanningPolicy"; Adr = @("ADR-006", "DDD-ADR-005") },
    @{ Name = "CoverageObligationPolicy"; Adr = @("ADR-006", "DDD-ADR-003", "DDD-ADR-005") },
    @{ Name = "SourceDiversificationPolicy"; Adr = @("ADR-006", "DDD-ADR-005") },
    @{ Name = "VerifiedClaimDependencyPolicy"; Adr = @("ADR-006", "DDD-ADR-005", "DDD-ADR-008") },
    @{ Name = "ConditionalContradictionPolicy"; Adr = @("DDD-ADR-005", "DDD-ADR-007") },
    @{ Name = "DeepResearchSupportPolicy"; Adr = @("ADR-006", "DDD-ADR-005", "DDD-ADR-007") },
    @{ Name = "MultiSourceSynthesisPolicy"; Adr = @("DDD-ADR-003", "DDD-ADR-007") },
    @{ Name = "DeepResearchObservabilityPolicy"; Adr = @("ADR-010", "DDD-ADR-008") }
)

$expectedStates = @(
    "DEEP_REQUESTED",
    "DEEP_PLANNED",
    "COVERAGE_OBLIGATIONS_DECLARED",
    "COLLECTING_MULTI_QUERY_EVIDENCE",
    "EVIDENCE_DIVERSIFIED",
    "CLAIM_DEPENDENCIES_RESOLVED",
    "CONTRADICTIONS_CLASSIFIED",
    "COVERAGE_INSUFFICIENT",
    "SYNTHESIZING_MULTI_SOURCE",
    "SUPPORT_EVALUATED",
    "COMPLETED",
    "REJECTED"
)

$expectedPorts = @(
    "KnowledgeSearch",
    "ProjectionVersionCatalog",
    "VerifiedClaimCatalog",
    "DeepResearchPlanner",
    "CoverageObligationEvaluator",
    "EvidenceDiversifier",
    "ClaimDependencyResolver",
    "ContradictionClassifier",
    "MultiSourceSynthesizer",
    "CitationResolver",
    "ResearchCaseRepository",
    "DeepResearchMetricsPublisher"
)

$expectedEvents = @(
    "DeepResearchRequested",
    "DeepResearchPlanCreated",
    "CoverageObligationDeclared",
    "DeepResearchEvidenceCollected",
    "EvidenceDiversificationCompleted",
    "ClaimDependencyGroupResolved",
    "ConditionalContradictionDetected",
    "DocumentaryGapRecorded",
    "DeepResearchCoverageInsufficient",
    "MultiSourceSynthesisDrafted",
    "DeepResearchSupportEvaluated",
    "DeepResearchCompleted",
    "DeepResearchPublicationBlocked"
)

$expectedEndpoints = @(
    "POST /v1/research/deep"
)

$expectedPublicErrors = @(
    "HTTP_REQUEST_INVALID",
    "ENDPOINT_NOT_FOUND",
    "DEEP_RESEARCH_MANDATE_REQUIRED",
    "DEEP_RESEARCH_MODE_REQUIRED",
    "DEEP_RESEARCH_PLAN_REQUIRED",
    "COVERAGE_OBLIGATION_MISSING",
    "COVERAGE_INSUFFICIENT",
    "SOURCE_DIVERSIFICATION_INSUFFICIENT",
    "CLAIM_DEPENDENCY_UNRESOLVED",
    "CONTRADICTION_UNCLASSIFIED",
    "DEEP_RESEARCH_SYNTHESIS_UNSUPPORTED",
    "CURRENT_DATA_REQUIRED",
    "DEEP_RESEARCH_POLICY_MISSING",
    "PUBLIC_STORAGE_FIELD_FORBIDDEN"
)

$expectedMetrics = @(
    "deep_research_requested_total",
    "deep_research_plan_created_total",
    "deep_research_coverage_obligation_met_total",
    "deep_research_coverage_obligation_missing_total",
    "deep_research_query_executed_total",
    "deep_research_independent_source_group_total",
    "deep_research_contradiction_classified_total",
    "deep_research_documentary_gap_total",
    "deep_research_support_status_total",
    "deep_research_public_error_total",
    "deep_research_synthesis_published_total",
    "deep_research_claim_version_recorded_total"
)

$expectedBehaviors = @(
    @{ Name = "DRA-001 - Spécification exécutable M-009"; Adr = @("ADR-006", "ADR-010", "DDD-ADR-003", "DDD-ADR-005", "DDD-ADR-007", "DDD-ADR-008"); Test = "T-002"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m009_specification.ps1" },
    @{ Name = "DRA-002 - Plan de recherche avec obligations"; Adr = @("ADR-006", "ADR-010", "DDD-ADR-005"); Test = "T-003"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_deep_research_planning_acceptance.ps1" },
    @{ Name = "DRA-003 - Collecte multi-requêtes diversifiée"; Adr = @("ADR-006", "DDD-ADR-003", "DDD-ADR-005"); Test = "T-004"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_multi_query_evidence_collection_acceptance.ps1" },
    @{ Name = "DRA-004 - Claims et dépendances EG indépendantes"; Adr = @("ADR-006", "DDD-ADR-005", "DDD-ADR-008"); Test = "T-005"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_deep_research_claim_dependencies_acceptance.ps1" },
    @{ Name = "DRA-005 - Contradictions conditionnelles"; Adr = @("DDD-ADR-005", "DDD-ADR-007"); Test = "T-006"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_deep_research_conditional_contradictions_acceptance.ps1" },
    @{ Name = "DRA-006 - Couverture insuffisante explicite"; Adr = @("ADR-006", "DDD-ADR-005", "DDD-ADR-007"); Test = "T-007"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_deep_research_insufficient_coverage_acceptance.ps1" },
    @{ Name = "DRA-007 - Synthèse multi-sources traçable"; Adr = @("DDD-ADR-003", "DDD-ADR-005", "DDD-ADR-007"); Test = "T-008"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_deep_research_synthesis_acceptance.ps1" },
    @{ Name = "DRA-008 - Endpoint recherche approfondie"; Adr = @("ADR-010", "DDD-ADR-003", "DDD-ADR-005"); Test = "T-009"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_deep_research_http_contract_acceptance.ps1" },
    @{ Name = "DRA-009 - Métriques de couverture et audit"; Adr = @("ADR-010", "DDD-ADR-008"); Test = "T-010"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_m009_coverage_metrics_acceptance.ps1" },
    @{ Name = "DRA-010 - Traçabilité et gates M-009"; Adr = @("ADR-006", "ADR-010", "DDD-ADR-005", "DDD-ADR-008"); Test = "T-011"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_m009_traceability_acceptance.ps1" }
)

function Normalize-M009Cell {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string] $Value
    )

    return ($Value.Trim() -replace "`"", "" -replace "\*\*", "" -replace "``", "" -replace "<br\s*/?>", " ")
}

function Split-M009MarkdownRow {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Line
    )

    $trimmedLine = $Line.Trim()
    if ($trimmedLine.StartsWith("|")) {
        $trimmedLine = $trimmedLine.Substring(1)
    }
    if ($trimmedLine.EndsWith("|")) {
        $trimmedLine = $trimmedLine.Substring(0, $trimmedLine.Length - 1)
    }

    return @($trimmedLine -split "\|" | ForEach-Object { Normalize-M009Cell -Value $_ })
}

function Test-M009SeparatorRow {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Line
    )

    return ($Line.Trim() -match "^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$")
}

function Read-M009MarkdownTable {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string[]] $Lines,

        [Parameter(Mandatory = $true)]
        [string[]] $RequiredHeaders,

        [Parameter(Mandatory = $true)]
        [string] $TableName
    )

    for ($lineIndex = 0; $lineIndex -lt $Lines.Count; $lineIndex++) {
        if (-not $Lines[$lineIndex].Trim().StartsWith("|")) {
            continue
        }

        $headers = Split-M009MarkdownRow -Line $Lines[$lineIndex]
        $containsAllHeaders = $true
        foreach ($requiredHeader in $RequiredHeaders) {
            if ($headers -notcontains $requiredHeader) {
                $containsAllHeaders = $false
                break
            }
        }

        if (-not $containsAllHeaders) {
            continue
        }

        if (($lineIndex + 1) -ge $Lines.Count -or -not (Test-M009SeparatorRow -Line $Lines[$lineIndex + 1])) {
            throw "Table $TableName invalide: ligne de séparation absente."
        }

        $rows = @()
        $rowIndex = $lineIndex + 2
        while ($rowIndex -lt $Lines.Count -and $Lines[$rowIndex].Trim().StartsWith("|")) {
            if (Test-M009SeparatorRow -Line $Lines[$rowIndex]) {
                $rowIndex++
                continue
            }

            $cells = Split-M009MarkdownRow -Line $Lines[$rowIndex]
            if ($cells.Count -ne $headers.Count) {
                throw "Table $TableName invalide: nombre de cellules incohérent ligne $($rowIndex + 1)."
            }

            $row = @{}
            for ($cellIndex = 0; $cellIndex -lt $headers.Count; $cellIndex++) {
                $row[[string] $headers[$cellIndex]] = [string] $cells[$cellIndex]
            }
            $rows += ,$row
            $rowIndex++
        }

        if (@($rows).Count -eq 0) {
            throw "Table $TableName invalide: aucune ligne de données."
        }

        return @($rows)
    }

    throw "Table $TableName absente."
}

function Assert-M009Contains {
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

function Assert-M009AdrToken {
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

function Assert-M009ForbiddenPatterns {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content
    )

    $forbiddenPatterns = @(
        @{ Pattern = "RA\s+lit\s+Qdrant\s+directement"; Message = "Accès RA direct à Qdrant interdit" },
        @{ Pattern = "RA\s+acc[èe]de\s+directement\s+[àa]\s+Qdrant"; Message = "Accès RA direct à Qdrant interdit" },
        @{ Pattern = "RA\s+lit\s+le\s+registre\s+EG\s+interne\s+directement"; Message = "Accès RA direct au registre EG interne interdit" },
        @{ Pattern = "RA\s+acc[èe]de\s+directement\s+au\s+registre\s+EG\s+interne"; Message = "Accès RA direct au registre EG interne interdit" },
        @{ Pattern = "fr[ée]quence\s+de\s+citation\s+devient\s+consensus"; Message = "Confusion fréquence/consensus interdite" },
        @{ Pattern = "nombre\s+brut\s+de\s+mentions\s+devient\s+consensus"; Message = "Confusion fréquence/consensus interdite" },
        @{ Pattern = "score\s+probabiliste\s+.*devient\s+.*v[ée]rit[ée]"; Message = "Score probabiliste présenté comme vérité interdit" },
        @{ Pattern = "synth[èe]se\s+SUPPORTED\s+sans\s+couverture"; Message = "Synthèse supportée sans couverture minimale interdite" },
        @{ Pattern = "param[èe]tre\s+de\s+strat[ée]gie\s+invent[ée]"; Message = "Paramètre de stratégie inventé interdit" },
        @{ Pattern = "valeur\s+de\s+march[ée]\s+actuelle\s+fabriqu[ée]e"; Message = "Valeur de marché actuelle fabriquée interdite" },
        @{ Pattern = "POST /v1/research/deep.*(qdrant_collection|eg_registry_table|sp_table).*succ[èe]s"; Message = "Exposition de stockage interne interdite" }
    )

    foreach ($forbiddenPattern in $forbiddenPatterns) {
        if ($Content -match $forbiddenPattern.Pattern) {
            throw $forbiddenPattern.Message + ": " + $Matches[0]
        }
    }
}

function Resolve-M009SpecificationPath {
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
        throw "Chemin hors dépôt interdit (spécification M-009): $resolvedCandidatePath"
    }

    return $resolvedCandidatePath
}

function Assert-M009NamedRows {
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

function Assert-M009Policies {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable[]] $PolicyRows
    )

    $policiesByName = Assert-M009NamedRows `
        -Rows $PolicyRows `
        -NameColumn "Politique" `
        -RequiredColumns @("Décision", "Invariants", "ADR") `
        -ExpectedNames @($expectedPolicies | ForEach-Object { $_.Name }) `
        -Label "Politique M-009"

    foreach ($expectedPolicy in $expectedPolicies) {
        $row = $policiesByName[$expectedPolicy.Name]
        foreach ($adrId in $expectedPolicy.Adr) {
            Assert-M009AdrToken -Content $row["ADR"] -AdrId $adrId
        }
    }
}

function Assert-M009Behaviors {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable[]] $BehaviorRows
    )

    $behaviorsByName = Assert-M009NamedRows `
        -Rows $BehaviorRows `
        -NameColumn "Comportement" `
        -RequiredColumns @("Invariant", "Scénario BDD", "Test RED", "ADR", "Commande") `
        -ExpectedNames @($expectedBehaviors | ForEach-Object { $_.Name }) `
        -Label "Comportement M-009"

    foreach ($expectedBehavior in $expectedBehaviors) {
        $row = $behaviorsByName[$expectedBehavior.Name]
        if ($row["Test RED"] -ne $expectedBehavior.Test) {
            throw "Test RED invalide pour $($expectedBehavior.Name). Attendu: $($expectedBehavior.Test). Obtenu: $($row["Test RED"])"
        }
        if ($row["Commande"] -ne $expectedBehavior.Command) {
            throw "Commande invalide pour $($expectedBehavior.Name). Attendu: $($expectedBehavior.Command). Obtenu: $($row["Commande"])"
        }
        foreach ($adrId in $expectedBehavior.Adr) {
            Assert-M009AdrToken -Content $row["ADR"] -AdrId $adrId
        }
    }
}

function Assert-M009Spec {
    param(
        [Parameter(Mandatory = $true)]
        [string] $SpecPath
    )

    if (-not (Test-Path -LiteralPath $SpecPath -PathType Leaf)) {
        throw "Spécification M-009 absente: $SpecPath"
    }

    $content = (Get-Content -Raw -Encoding UTF8 -LiteralPath $SpecPath).TrimStart([char] 0xFEFF)
    $lines = @(Get-Content -Encoding UTF8 -LiteralPath $SpecPath)
    if ($lines.Count -gt 0) {
        $lines[0] = $lines[0].TrimStart([char] 0xFEFF)
    }

    Assert-M009ForbiddenPatterns -Content $content

    foreach ($section in $requiredSections) {
        if ($lines -notcontains $section) {
            throw "Section obligatoire absente: $section"
        }
    }

    foreach ($marker in $requiredMarkers) {
        Assert-M009Contains -Content $content -Expected $marker -Message "Marqueur obligatoire absent: $marker"
    }

    foreach ($adrId in $requiredAdrIds) {
        Assert-M009AdrToken -Content $content -AdrId $adrId
    }

    foreach ($term in $requiredTerms) {
        Assert-M009Contains -Content $content -Expected $term -Message "Terme du langage RA approfondie absent: $term"
    }

    foreach ($command in $requiredCommands) {
        Assert-M009Contains -Content $content -Expected $command -Message "Commande de validation absente: $command"
    }

    $aggregateRows = Read-M009MarkdownTable -Lines $lines -RequiredHeaders @("Agrégat", "Responsabilité M-009", "Invariants", "Événements") -TableName "agrégats M-009"
    Assert-M009NamedRows -Rows $aggregateRows -NameColumn "Agrégat" -RequiredColumns @("Responsabilité M-009", "Invariants", "Événements") -ExpectedNames $expectedAggregates -Label "Agrégat M-009" | Out-Null

    $valueObjectRows = Read-M009MarkdownTable -Lines $lines -RequiredHeaders @("Objet-valeur", "Sens M-009", "Invariants") -TableName "objets-valeur M-009"
    Assert-M009NamedRows -Rows $valueObjectRows -NameColumn "Objet-valeur" -RequiredColumns @("Sens M-009", "Invariants") -ExpectedNames $expectedValueObjects -Label "Objet-valeur M-009" | Out-Null

    $policyRows = Read-M009MarkdownTable -Lines $lines -RequiredHeaders @("Politique", "Décision", "Invariants", "ADR") -TableName "politiques M-009"
    Assert-M009Policies -PolicyRows $policyRows

    $stateRows = Read-M009MarkdownTable -Lines $lines -RequiredHeaders @("État", "Portée", "Sens M-009", "Transition autorisée") -TableName "états M-009"
    Assert-M009NamedRows -Rows $stateRows -NameColumn "État" -RequiredColumns @("Portée", "Sens M-009", "Transition autorisée") -ExpectedNames $expectedStates -Label "État M-009" | Out-Null

    $portRows = Read-M009MarkdownTable -Lines $lines -RequiredHeaders @("Port", "Responsabilité", "Interdiction") -TableName "ports M-009"
    Assert-M009NamedRows -Rows $portRows -NameColumn "Port" -RequiredColumns @("Responsabilité", "Interdiction") -ExpectedNames $expectedPorts -Label "Port M-009" | Out-Null

    $eventRows = Read-M009MarkdownTable -Lines $lines -RequiredHeaders @("Événement", "Déclencheur", "Payload publié") -TableName "événements M-009"
    Assert-M009NamedRows -Rows $eventRows -NameColumn "Événement" -RequiredColumns @("Déclencheur", "Payload publié") -ExpectedNames $expectedEvents -Label "Événement M-009" | Out-Null

    $endpointRows = Read-M009MarkdownTable -Lines $lines -RequiredHeaders @("Endpoint", "Succès", "Erreurs publiques", "Corps public") -TableName "API M-009"
    Assert-M009NamedRows -Rows $endpointRows -NameColumn "Endpoint" -RequiredColumns @("Succès", "Erreurs publiques", "Corps public") -ExpectedNames $expectedEndpoints -Label "Endpoint M-009" | Out-Null

    $errorRows = Read-M009MarkdownTable -Lines $lines -RequiredHeaders @("Code", "Statut HTTP", "Sens public") -TableName "erreurs publiques M-009"
    Assert-M009NamedRows -Rows $errorRows -NameColumn "Code" -RequiredColumns @("Statut HTTP", "Sens public") -ExpectedNames $expectedPublicErrors -Label "Erreur publique M-009" | Out-Null

    $metricRows = Read-M009MarkdownTable -Lines $lines -RequiredHeaders @("Signal", "Type", "Invariant") -TableName "métriques M-009"
    Assert-M009NamedRows -Rows $metricRows -NameColumn "Signal" -RequiredColumns @("Type", "Invariant") -ExpectedNames $expectedMetrics -Label "Signal M-009" | Out-Null

    $behaviorRows = Read-M009MarkdownTable -Lines $lines -RequiredHeaders @("Comportement", "Invariant", "Scénario BDD", "Test RED", "ADR", "Commande") -TableName "comportements M-009"
    Assert-M009Behaviors -BehaviorRows $behaviorRows
}

$resolvedPath = Resolve-M009SpecificationPath -InputPath $Path
Assert-M009Spec -SpecPath $resolvedPath

Write-Host "Spécification M-009 valide: $($expectedBehaviors.Count) comportement(s), $($expectedPolicies.Count) politique(s), $($expectedStates.Count) état(s) contrôlé(s)."
