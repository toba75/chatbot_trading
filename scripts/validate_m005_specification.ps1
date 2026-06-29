param(
    [Parameter(Mandatory = $false)]
    [string] $Path
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$defaultSpecificationPath = "docs/specs/m005_projection_connaissance_recherchable.md"
$eAcute = [char] 0x00E9
$eGrave = [char] 0x00E8
$aGrave = [char] 0x00E0
$cCedilla = [char] 0x00E7
$oCircumflex = [char] 0x00F4
$capitalEAcute = [char] 0x00C9
$scenarioHeader = "## Sc$($eAcute)nario BDD"
$aggregateHeader = "## Agr$($eAcute)gat KnowledgeProjection"
$stateHeader = "## Machine d'$($eAcute)tats M-005"
$eventHeader = "## $($capitalEAcute)v$($eAcute)nements KA"
$metricHeader = "## M$($eAcute)triques et traces"
$behaviorHeader = "## Comportements v$($eAcute)rifiables M-005"
$stateColumn = "$($capitalEAcute)tat"
$eventColumn = "$($capitalEAcute)v$($eAcute)nement"
$responsibilityColumn = "Responsabilit$($eAcute)"
$decisionColumn = "D$($eAcute)cision"
$scopeColumn = "Port$($eAcute)e"
$transitionColumn = "Transition autoris$($eAcute)e"
$successColumn = "Succ$($eGrave)s"
$publishedPayloadColumn = "Payload publi$($eAcute)"
$triggerColumn = "D$($eAcute)clencheur"
$scenarioColumn = "Sc$($eAcute)nario BDD"
$aggregateColumn = "Agr$($eAcute)gat"
$eventsColumn = "$($capitalEAcute)v$($eAcute)nements"
$truthPattern = "v(?:e|$($eAcute))rit(?:e|$($eAcute))"

$requiredSections = @(
    "# M-005 - Projection de connaissance recherchable",
    "## Statut",
    $scenarioHeader,
    "## Mission KA",
    "## Contexte DDD",
    "## Langage ubiquitaire KA",
    $aggregateHeader,
    "## Objets-valeur KA",
    "## Politiques normatives M-005",
    $stateHeader,
    "## Ports et adaptateurs KA",
    $eventHeader,
    "## API publique KA",
    "## Erreurs publiques",
    $metricHeader,
    $behaviorHeader,
    "## Commandes de validation",
    "## Exclusions M-006 et M-007"
)

$requiredAdrIds = @(
    "ADR-001",
    "ADR-005",
    "ADR-006",
    "ADR-007",
    "ADR-009",
    "ADR-010",
    "DDD-ADR-003",
    "DDD-ADR-004",
    "DDD-ADR-008"
)

$requiredMarkers = @(
    "Given une version canonique M-004 publi$($eAcute)e.",
    "When la sp$($eAcute)cification M-005 est publi$($eAcute)e.",
    "Then chaque comportement de projection et recherche nomme son invariant, son sc$($eAcute)nario BDD, son test RED, ses ADR applicables et sa commande de validation.",
    "Qdrant reste une projection r$($eAcute)g$($eAcute)n$($eAcute)rable",
    "QdrantVectorIndex",
    "authenticated_context",
    "requested_by_context",
    "aucun claim EG dans l'index documentaire",
    "RA consomme `KnowledgeSearchPort` sans acc$($eGrave)s direct $($aGrave) Qdrant",
    "un score n'est pas une v$($eAcute)rit$($eAcute) m$($eAcute)tier"
)

$requiredTerms = @(
    "KnowledgeProjection",
    "ProjectionStatus",
    "SearchKnowledge",
    "RequestKnowledgeProjection",
    "SearchScoreBundle",
    "SearchTracePolicy",
    "SearchTraceStore",
    "KnowledgeSearchPort",
    "POST /v1/documents/{document_id}/index",
    "POST /v1/search",
    "PROJECTION_STALE",
    "FILTER_NOT_SUPPORTED",
    "SEARCH_INDEX_UNAVAILABLE"
)

$requiredCommands = @(
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m005\validate_m005_specification_acceptance.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m005\validate_m005_specification_unit.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m005_specification.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1"
)

$expectedValueObjects = @(
    "KnowledgeProjectionId",
    "CanonicalVersionRef",
    "ProjectionProfile",
    "BuildFingerprint",
    "SourceLocator",
    "ContentHash",
    "SearchScoreBundle",
    "SearchTraceId"
)

$expectedPolicies = @(
    @{ Name = "ProjectionEligibilityPolicy"; Adr = @("DDD-ADR-004", "DDD-ADR-008") },
    @{ Name = "ProjectionFreshnessPolicy"; Adr = @("DDD-ADR-004") },
    @{ Name = "HybridRetrievalPolicy"; Adr = @("ADR-005") },
    @{ Name = "SearchTracePolicy"; Adr = @("ADR-010", "DDD-ADR-008") },
    @{ Name = "EvidenceCandidatePolicy"; Adr = @("ADR-006") }
)

$expectedStates = @(
    "REQUESTED",
    "BUILDING",
    "BUILT",
    "INDEXING",
    "SEARCHABLE",
    "STALE",
    "FAILED",
    "RETIRED"
)

$expectedPorts = @(
    "CanonicalSourceReader",
    "KnowledgeProjectionRepository",
    "VectorIndex",
    "DenseEncoder",
    "SparseEncoder",
    "KnowledgeSearchPort",
    "SearchTraceStore"
)

$expectedEvents = @(
    "KnowledgeProjectionRequested",
    "KnowledgeProjectionBuilt",
    "KnowledgeProjectionBecameSearchable",
    "KnowledgeProjectionFailed",
    "KnowledgeProjectionBecameStale",
    "KnowledgeProjectionRetired",
    "SearchKnowledgePerformed"
)

$expectedEndpoints = @(
    "POST /v1/documents/{document_id}/index",
    "POST /v1/search"
)

$expectedMetrics = @(
    "knowledge_projection_build_total",
    "knowledge_projection_searchable_total",
    "knowledge_projection_failed_total",
    "knowledge_search_latency_seconds",
    "knowledge_search_stale_projection_total",
    "knowledge_search_recall_at_k",
    "knowledge_search_mrr",
    "knowledge_search_ndcg",
    "search_trace_persisted_total"
)

$expectedBehaviors = @(
    @{ Name = "KA-001 - Sp$($eAcute)cification ex$($eAcute)cutable M-005"; Adr = @("ADR-001", "ADR-005", "ADR-006", "ADR-007", "ADR-009", "ADR-010", "DDD-ADR-003", "DDD-ADR-004", "DDD-ADR-008"); Test = "T-002"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m005_specification.ps1" },
    @{ Name = "KA-002 - Projection depuis version canonique"; Adr = @("DDD-ADR-004", "DDD-ADR-008", "ADR-010"); Test = "T-003"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m005\validate_knowledge_projection_acceptance.ps1" },
    @{ Name = "KA-003 - Chunking tra$($cCedilla)able"; Adr = @("ADR-001", "ADR-006", "DDD-ADR-003", "DDD-ADR-004"); Test = "T-004"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m005\validate_hierarchical_chunking_acceptance.ps1" },
    @{ Name = "KA-004 - M$($eAcute)tadonn$($eAcute)es filtrables"; Adr = @("ADR-005", "DDD-ADR-004"); Test = "T-005"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m005\validate_projection_metadata_filters_acceptance.ps1" },
    @{ Name = "KA-005 - Encodage dense et sparse"; Adr = @("ADR-005", "ADR-007", "ADR-009", "DDD-ADR-004"); Test = "T-006"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m005\validate_projection_encoding_acceptance.ps1" },
    @{ Name = "KA-006 - Index Qdrant r$($eAcute)g$($eAcute)n$($eAcute)rable"; Adr = @("ADR-005", "DDD-ADR-004", "DDD-ADR-008"); Test = "T-007"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m005\validate_qdrant_projection_acceptance.ps1" },
    @{ Name = "KA-007 - Recherche hybride tra$($cCedilla)able"; Adr = @("ADR-005", "ADR-006", "DDD-ADR-003", "DDD-ADR-004", "DDD-ADR-008"); Test = "T-008"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m005\validate_hybrid_search_acceptance.ps1" },
    @{ Name = "KA-008 - Commande de recherche publique"; Adr = @("ADR-005", "ADR-006", "ADR-010", "DDD-ADR-003", "DDD-ADR-004"); Test = "T-009"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m005\validate_search_command_acceptance.ps1" },
    @{ Name = "KA-009 - Tra$($cCedilla)abilit$($eAcute) et m$($eAcute)triques M-005"; Adr = @("ADR-005", "ADR-006", "ADR-010", "DDD-ADR-004", "DDD-ADR-008"); Test = "T-010"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m005\validate_m005_traceability_acceptance.ps1" }
)

function Normalize-M005Cell {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string] $Value
    )

    return ($Value.Trim() -replace "`"", "" -replace "\*\*", "" -replace "``", "" -replace "<br\s*/?>", " ")
}

function Split-M005MarkdownRow {
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

    return @($trimmedLine -split "\|" | ForEach-Object { Normalize-M005Cell -Value $_ })
}

function Test-M005SeparatorRow {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Line
    )

    return ($Line.Trim() -match "^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$")
}

function Read-M005MarkdownTable {
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

        $headers = Split-M005MarkdownRow -Line $Lines[$lineIndex]
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

        if (($lineIndex + 1) -ge $Lines.Count -or -not (Test-M005SeparatorRow -Line $Lines[$lineIndex + 1])) {
            throw "Table $TableName invalide: ligne de séparation absente."
        }

        $rows = @()
        $rowIndex = $lineIndex + 2
        while ($rowIndex -lt $Lines.Count -and $Lines[$rowIndex].Trim().StartsWith("|")) {
            if (Test-M005SeparatorRow -Line $Lines[$rowIndex]) {
                $rowIndex++
                continue
            }

            $cells = Split-M005MarkdownRow -Line $Lines[$rowIndex]
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

function Assert-M005Contains {
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

function Assert-M005AdrToken {
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

function Assert-M005ForbiddenPatterns {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content
    )

    $forbiddenPatterns = @(
        @{ Pattern = "Qdrant\s+(?:est|devient|constitue)\s+la\s+source\s+de\s+$truthPattern"; Message = "Qdrant source de v$($eAcute)rit$($eAcute) interdit" },
        @{ Pattern = "(?:index\s+documentaire|Qdrant)\s+stocke\s+les\s+claims"; Message = "Claim EG dans l'index documentaire interdit" },
        @{ Pattern = "claims\s+EG\s+dans\s+l'index\s+documentaire"; Message = "Claim EG dans l'index documentaire interdit" },
        @{ Pattern = "RA\s+lit\s+Qdrant\s+directement"; Message = "Acc$($eGrave)s RA direct $($aGrave) Qdrant interdit" },
        @{ Pattern = "RA\s+acc[èe]de\s+directement\s+[àa]\s+Qdrant"; Message = "Acc$($eGrave)s RA direct $($aGrave) Qdrant interdit" },
        @{ Pattern = "score\s+hybride\s+(?:est|devient|constitue)\s+une\s+$truthPattern"; Message = "Score trait$($eAcute) comme v$($eAcute)rit$($eAcute) interdit" },
        @{ Pattern = "score\s+.*trait(?:e|$($eAcute))\s+comme\s+$truthPattern"; Message = "Score trait$($eAcute) comme v$($eAcute)rit$($eAcute) interdit" },
        @{ Pattern = "fallback\s+(?:dense|lexical|sparse|hybride).*(?:silencieux\s+autoris[ée]|silencieux\s+activ[ée]|silencieux\s+permis)"; Message = "Fallback silencieux interdit" }
    )

    foreach ($forbiddenPattern in $forbiddenPatterns) {
        if ($Content -match $forbiddenPattern.Pattern) {
            throw $forbiddenPattern.Message + ": " + $Matches[0]
        }
    }
}

function Resolve-M005SpecificationPath {
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
        throw "Chemin hors d$($eAcute)p$($oCircumflex)t interdit (sp$($eAcute)cification M-005): $resolvedCandidatePath"
    }

    return $resolvedCandidatePath
}

function Assert-M005ValueObjects {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable[]] $ValueObjectRows
    )

    $valueObjectsByName = @{}
    foreach ($row in $ValueObjectRows) {
        $valueObjectName = $row["Objet-valeur"]
        if ([string]::IsNullOrWhiteSpace($valueObjectName)) {
            throw "Objet-valeur M-005 sans nom."
        }
        if ($valueObjectsByName.ContainsKey($valueObjectName)) {
            throw "Objet-valeur M-005 dupliqué: $valueObjectName"
        }

        foreach ($requiredColumn in @("Sens M-005", "Invariants")) {
            if ([string]::IsNullOrWhiteSpace($row[$requiredColumn])) {
                throw "Colonne $requiredColumn vide pour $valueObjectName."
            }
        }

        $valueObjectsByName[$valueObjectName] = $row
    }

    foreach ($expectedValueObject in $expectedValueObjects) {
        if (-not $valueObjectsByName.ContainsKey($expectedValueObject)) {
            throw "Objet-valeur attendu absent: $expectedValueObject"
        }
    }
}

function Assert-M005Policies {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable[]] $PolicyRows
    )

    $policiesByName = @{}
    foreach ($row in $PolicyRows) {
        $policyName = $row["Politique"]
        if ([string]::IsNullOrWhiteSpace($policyName)) {
            throw "Politique M-005 sans nom."
        }
        if ($policiesByName.ContainsKey($policyName)) {
            throw "Politique M-005 dupliquée: $policyName"
        }

        foreach ($requiredColumn in @($decisionColumn, "Invariants", "ADR")) {
            if ([string]::IsNullOrWhiteSpace($row[$requiredColumn])) {
                throw "Colonne $requiredColumn vide pour $policyName."
            }
        }

        $policiesByName[$policyName] = $row
    }

    foreach ($expectedPolicy in $expectedPolicies) {
        if (-not $policiesByName.ContainsKey($expectedPolicy.Name)) {
            throw "Politique attendue absente: $($expectedPolicy.Name)"
        }

        $row = $policiesByName[$expectedPolicy.Name]
        foreach ($adrId in $expectedPolicy.Adr) {
            Assert-M005AdrToken -Content $row["ADR"] -AdrId $adrId
        }
    }
}

function Assert-M005States {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable[]] $StateRows
    )

    $statesByName = @{}
    foreach ($row in $StateRows) {
        $stateName = $row[$stateColumn]
        if ([string]::IsNullOrWhiteSpace($stateName)) {
            throw "État M-005 sans nom."
        }
        if ($statesByName.ContainsKey($stateName)) {
            throw "État M-005 dupliqué: $stateName"
        }

        foreach ($requiredColumn in @($scopeColumn, "Sens M-005", $transitionColumn)) {
            if ([string]::IsNullOrWhiteSpace($row[$requiredColumn])) {
                throw "Colonne $requiredColumn vide pour $stateName."
            }
        }

        $statesByName[$stateName] = $row
    }

    foreach ($expectedState in $expectedStates) {
        if (-not $statesByName.ContainsKey($expectedState)) {
            throw "État attendu absent: $expectedState"
        }
    }
}

function Assert-M005Ports {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable[]] $PortRows
    )

    $portsByName = @{}
    foreach ($row in $PortRows) {
        $portName = $row["Port"]
        if ([string]::IsNullOrWhiteSpace($portName)) {
            throw "Port M-005 sans nom."
        }
        if ($portsByName.ContainsKey($portName)) {
            throw "Port M-005 dupliqué: $portName"
        }

        foreach ($requiredColumn in @($responsibilityColumn, "Interdiction")) {
            if ([string]::IsNullOrWhiteSpace($row[$requiredColumn])) {
                throw "Colonne $requiredColumn vide pour $portName."
            }
        }

        $portsByName[$portName] = $row
    }

    foreach ($expectedPort in $expectedPorts) {
        if (-not $portsByName.ContainsKey($expectedPort)) {
            throw "Port attendu absent: $expectedPort"
        }
    }
}

function Assert-M005Events {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable[]] $EventRows
    )

    $eventsByName = @{}
    foreach ($row in $EventRows) {
        $eventName = $row[$eventColumn]
        if ([string]::IsNullOrWhiteSpace($eventName)) {
            throw "Événement M-005 sans nom."
        }
        if ($eventsByName.ContainsKey($eventName)) {
            throw "Événement M-005 dupliqué: $eventName"
        }

        foreach ($requiredColumn in @($triggerColumn, $publishedPayloadColumn)) {
            if ([string]::IsNullOrWhiteSpace($row[$requiredColumn])) {
                throw "Colonne $requiredColumn vide pour $eventName."
            }
        }

        $eventsByName[$eventName] = $row
    }

    foreach ($expectedEvent in $expectedEvents) {
        if (-not $eventsByName.ContainsKey($expectedEvent)) {
            throw "Événement attendu absent: $expectedEvent"
        }
    }
}

function Assert-M005Endpoints {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable[]] $EndpointRows
    )

    $endpointsByName = @{}
    foreach ($row in $EndpointRows) {
        $endpointName = $row["Endpoint"]
        if ([string]::IsNullOrWhiteSpace($endpointName)) {
            throw "Endpoint M-005 sans nom."
        }
        if ($endpointsByName.ContainsKey($endpointName)) {
            throw "Endpoint M-005 dupliqué: $endpointName"
        }

        foreach ($requiredColumn in @($successColumn, "Erreurs publiques", "Corps public")) {
            if ([string]::IsNullOrWhiteSpace($row[$requiredColumn])) {
                throw "Colonne $requiredColumn vide pour $endpointName."
            }
        }

        $endpointsByName[$endpointName] = $row
    }

    foreach ($expectedEndpoint in $expectedEndpoints) {
        if (-not $endpointsByName.ContainsKey($expectedEndpoint)) {
            throw "Endpoint attendu absent: $expectedEndpoint"
        }
    }
}

function Assert-M005Metrics {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable[]] $MetricRows
    )

    $metricsByName = @{}
    foreach ($row in $MetricRows) {
        $metricName = $row["Signal"]
        if ([string]::IsNullOrWhiteSpace($metricName)) {
            throw "Signal M-005 sans nom."
        }
        if ($metricsByName.ContainsKey($metricName)) {
            throw "Signal M-005 dupliqué: $metricName"
        }

        foreach ($requiredColumn in @("Type", "Invariant")) {
            if ([string]::IsNullOrWhiteSpace($row[$requiredColumn])) {
                throw "Colonne $requiredColumn vide pour $metricName."
            }
        }

        $metricsByName[$metricName] = $row
    }

    foreach ($expectedMetric in $expectedMetrics) {
        if (-not $metricsByName.ContainsKey($expectedMetric)) {
            throw "Signal attendu absent: $expectedMetric"
        }
    }
}

function Assert-M005Behaviors {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable[]] $BehaviorRows
    )

    $behaviorsByName = @{}
    foreach ($row in $BehaviorRows) {
        $behaviorName = $row["Comportement"]
        if ([string]::IsNullOrWhiteSpace($behaviorName)) {
            throw "Comportement M-005 sans nom."
        }
        if ($behaviorsByName.ContainsKey($behaviorName)) {
            throw "Comportement M-005 dupliqué: $behaviorName"
        }

        foreach ($requiredColumn in @("Invariant", $scenarioColumn, "Test RED", "ADR", "Commande")) {
            if ([string]::IsNullOrWhiteSpace($row[$requiredColumn])) {
                throw "Colonne $requiredColumn vide pour $behaviorName."
            }
        }

        if ($row["Test RED"] -match "(?i)\b(TBD|TODO|à\s+définir|a\s+definir)\b") {
            throw "Test RED non exécutable pour $behaviorName."
        }

        if (-not $row["Commande"].StartsWith("powershell -NoProfile -ExecutionPolicy Bypass -File .\")) {
            throw "Commande PowerShell M-005 absente pour $behaviorName."
        }

        $behaviorsByName[$behaviorName] = $row
    }

    foreach ($expectedBehavior in $expectedBehaviors) {
        if (-not $behaviorsByName.ContainsKey($expectedBehavior.Name)) {
            throw "Comportement attendu absent: $($expectedBehavior.Name)"
        }

        $row = $behaviorsByName[$expectedBehavior.Name]
        if ($row["Test RED"] -ne $expectedBehavior.Test) {
            throw "Test RED invalide pour $($expectedBehavior.Name). Attendu: $($expectedBehavior.Test). Obtenu: $($row["Test RED"])"
        }
        if ($row["Commande"] -ne $expectedBehavior.Command) {
            throw "Commande invalide pour $($expectedBehavior.Name). Attendu: $($expectedBehavior.Command). Obtenu: $($row["Commande"])"
        }

        foreach ($adrId in $expectedBehavior.Adr) {
            Assert-M005AdrToken -Content $row["ADR"] -AdrId $adrId
        }
    }
}

function Assert-M005Spec {
    param(
        [Parameter(Mandatory = $true)]
        [string] $SpecPath
    )

    if (-not (Test-Path -LiteralPath $SpecPath -PathType Leaf)) {
        throw "Spécification M-005 absente: $SpecPath"
    }

    $content = Get-Content -Raw -Encoding UTF8 -LiteralPath $SpecPath
    $lines = @(Get-Content -Encoding UTF8 -LiteralPath $SpecPath)

    Assert-M005ForbiddenPatterns -Content $content

    foreach ($section in $requiredSections) {
        if ($lines -notcontains $section) {
            throw "Section obligatoire absente: $section"
        }
    }

    foreach ($marker in $requiredMarkers) {
        Assert-M005Contains -Content $content -Expected $marker -Message "Marqueur obligatoire absent: $marker"
    }

    foreach ($adrId in $requiredAdrIds) {
        Assert-M005AdrToken -Content $content -AdrId $adrId
    }

    foreach ($term in $requiredTerms) {
        Assert-M005Contains -Content $content -Expected $term -Message "Terme du langage KA absent: $term"
    }

    foreach ($command in $requiredCommands) {
        Assert-M005Contains -Content $content -Expected $command -Message "Commande de validation absente: $command"
    }

    $aggregateRows = Read-M005MarkdownTable -Lines $lines -RequiredHeaders @($aggregateColumn, "$responsibilityColumn M-005", "Invariants", $eventsColumn) -TableName "agrégat M-005"
    $knowledgeProjectionRow = @($aggregateRows | Where-Object { $_[$aggregateColumn] -eq "KnowledgeProjection" })
    if ($knowledgeProjectionRow.Count -ne 1) {
        throw "Agrégat attendu absent: KnowledgeProjection"
    }
    foreach ($expectedEvent in @("KnowledgeProjectionBuilt", "KnowledgeProjectionBecameSearchable", "KnowledgeProjectionFailed", "KnowledgeProjectionBecameStale", "KnowledgeProjectionRetired")) {
        if (-not $knowledgeProjectionRow[0][$eventsColumn].Contains($expectedEvent)) {
            throw "$eventColumn attendu absent: $expectedEvent"
        }
    }

    $valueObjectRows = Read-M005MarkdownTable -Lines $lines -RequiredHeaders @("Objet-valeur", "Sens M-005", "Invariants") -TableName "objets-valeur M-005"
    Assert-M005ValueObjects -ValueObjectRows $valueObjectRows

    $policyRows = Read-M005MarkdownTable -Lines $lines -RequiredHeaders @("Politique", $decisionColumn, "Invariants", "ADR") -TableName "politiques M-005"
    Assert-M005Policies -PolicyRows $policyRows

    $stateRows = Read-M005MarkdownTable -Lines $lines -RequiredHeaders @($stateColumn, $scopeColumn, "Sens M-005", $transitionColumn) -TableName "états M-005"
    Assert-M005States -StateRows $stateRows

    $portRows = Read-M005MarkdownTable -Lines $lines -RequiredHeaders @("Port", $responsibilityColumn, "Interdiction") -TableName "ports M-005"
    Assert-M005Ports -PortRows $portRows

    $eventRows = Read-M005MarkdownTable -Lines $lines -RequiredHeaders @($eventColumn, $triggerColumn, $publishedPayloadColumn) -TableName "événements M-005"
    Assert-M005Events -EventRows $eventRows

    $endpointRows = Read-M005MarkdownTable -Lines $lines -RequiredHeaders @("Endpoint", $successColumn, "Erreurs publiques", "Corps public") -TableName "API M-005"
    Assert-M005Endpoints -EndpointRows $endpointRows

    $metricRows = Read-M005MarkdownTable -Lines $lines -RequiredHeaders @("Signal", "Type", "Invariant") -TableName "métriques M-005"
    Assert-M005Metrics -MetricRows $metricRows

    $behaviorRows = Read-M005MarkdownTable -Lines $lines -RequiredHeaders @("Comportement", "Invariant", $scenarioColumn, "Test RED", "ADR", "Commande") -TableName "comportements M-005"
    Assert-M005Behaviors -BehaviorRows $behaviorRows
}

$resolvedPath = Resolve-M005SpecificationPath -InputPath $Path
Assert-M005Spec -SpecPath $resolvedPath

Write-Host "Sp$($eAcute)cification M-005 valide: $($expectedBehaviors.Count) comportement(s), $($expectedPolicies.Count) politique(s), $($expectedStates.Count) $($eAcute)tat(s) contr$($oCircumflex)l$($eAcute)(s)."
