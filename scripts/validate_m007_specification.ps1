param(
    [Parameter(Mandatory = $false)]
    [string] $Path
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$defaultSpecificationPath = "docs/specs/m007_reponse_documentaire_verifiee.md"

$requiredSections = @(
    "# M-007 - Réponse documentaire vérifiée",
    "## Statut",
    "## Scénario BDD",
    "## Mission RA",
    "## Contexte DDD",
    "## Langage ubiquitaire RA",
    "## Agrégats RA",
    "## Objets-valeur RA",
    "## Politiques normatives M-007",
    "## Machine d'états M-007",
    "## Ports et adaptateurs RA",
    "## Événements RA",
    "## API publique RA",
    "## Erreurs publiques",
    "## Métriques et traces",
    "## Comportements vérifiables M-007",
    "## Commandes de validation",
    "## Exclusions M-007"
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
    "Given un brouillon contenant une assertion factuelle importante.",
    "When la spécification M-007 est publiée.",
    "Then chaque comportement de réponse nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.",
    "Une réponse SUPPORTED exige que chaque assertion importante conservée soit supportée.",
    "Le jeu de preuves publié est figé.",
    "Toute Citation reste ouvrable jusqu'au SourceLocator.",
    "RA consomme KnowledgeSearch sans accès direct à Qdrant",
    "RA consomme VerifiedClaimCatalog sans lecture du registre EG interne",
    "Le LLM propose un brouillon; la politique RA décide le SupportStatus.",
    "Aucune valeur de marché n'est inventée."
)

$requiredTerms = @(
    "ResearchCase",
    "Answer",
    "ResearchMandate",
    "EvidenceSet",
    "AnswerAssertion",
    "Citation",
    "ContradictionAssessment",
    "KnowledgeGap",
    "SupportStatus",
    "AbstentionReason",
    "SourceLocator",
    "VerifiedClaimRef",
    "VerifiedResearchOutcome",
    "AnswerSupportPolicy",
    "CitationIntegrityPolicy",
    "AbstentionPolicy",
    "POST /v1/answer",
    "SUPPORTED",
    "PARTIALLY_SUPPORTED",
    "INSUFFICIENT_EVIDENCE",
    "CONFLICTING_EVIDENCE",
    "REQUIRES_CURRENT_DATA",
    "ANSWER_ASSERTION_UNSUPPORTED",
    "ANSWER_CITATION_UNRESOLVABLE",
    "CURRENT_DATA_REQUIRED"
)

$requiredCommands = @(
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m007\validate_m007_specification_acceptance.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m007\validate_m007_specification_unit.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m007_specification.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1"
)

$expectedValueObjects = @(
    "ResolvedQuestion",
    "ResearchMandate",
    "ResearchMode",
    "EvidenceSet",
    "EvidenceSetVersion",
    "AnswerAssertion",
    "AssertionOrigin",
    "Citation",
    "ContradictionAssessment",
    "KnowledgeGap",
    "SupportStatus",
    "AbstentionReason"
)

$expectedPolicies = @(
    @{ Name = "ResearchMandatePolicy"; Adr = @("ADR-010") },
    @{ Name = "EvidenceSetSealingPolicy"; Adr = @("DDD-ADR-003", "DDD-ADR-008") },
    @{ Name = "AnswerAssertionExtractionPolicy"; Adr = @("DDD-ADR-005", "DDD-ADR-007") },
    @{ Name = "AnswerSupportPolicy"; Adr = @("ADR-006", "DDD-ADR-005", "DDD-ADR-007") },
    @{ Name = "CitationIntegrityPolicy"; Adr = @("DDD-ADR-003") },
    @{ Name = "ContradictionAssessmentPolicy"; Adr = @("DDD-ADR-005") },
    @{ Name = "KnowledgeGapPolicy"; Adr = @("ADR-006", "DDD-ADR-005") },
    @{ Name = "AbstentionPolicy"; Adr = @("DDD-ADR-007") },
    @{ Name = "CurrentDataRequirementPolicy"; Adr = @("DDD-ADR-007") }
)

$expectedStates = @(
    "CREATED",
    "PLANNED",
    "COLLECTING_EVIDENCE",
    "EVIDENCE_ASSEMBLED",
    "SYNTHESIZING",
    "VERIFYING",
    "COMPLETED",
    "INSUFFICIENT_EVIDENCE",
    "CONFLICTING_EVIDENCE",
    "DRAFT",
    "ASSERTIONS_EXTRACTED",
    "SUPPORT_EVALUATED",
    "VERIFIED",
    "PARTIALLY_SUPPORTED",
    "ABSTAINED",
    "REJECTED"
)

$expectedPorts = @(
    "KnowledgeSearch",
    "VerifiedClaimCatalog",
    "EvidenceAssembler",
    "ContradictionAnalyzer",
    "AnswerGenerator",
    "AnswerAssertionExtractor",
    "AnswerVerifier",
    "CitationResolver",
    "CurrentDataAuthorization",
    "ResearchCaseRepository",
    "AnswerRepository"
)

$expectedEvents = @(
    "ResearchCaseOpened",
    "ResearchPlanCreated",
    "EvidenceCollectionCompleted",
    "EvidenceSetSealed",
    "ContradictionDetected",
    "KnowledgeGapRecorded",
    "AnswerDrafted",
    "AnswerAssertionsExtracted",
    "AnswerSupportEvaluated",
    "AnswerVerified",
    "AnswerPartiallySupported",
    "AnswerPublicationBlocked",
    "ResearchEvidenceFoundInsufficient",
    "ResearchEvidenceFoundConflicting",
    "AnswerAbstained",
    "AnswerSuperseded"
)

$expectedEndpoints = @(
    "POST /v1/answer"
)

$expectedPublicErrors = @(
    "HTTP_REQUEST_INVALID",
    "ENDPOINT_NOT_FOUND",
    "ANSWER_CONTEXT_FORBIDDEN",
    "RESEARCH_MANDATE_REQUIRED",
    "RESEARCH_CASE_NOT_FOUND",
    "EVIDENCE_SET_NOT_SEALED",
    "ANSWER_ASSERTION_UNSUPPORTED",
    "ANSWER_CITATION_UNRESOLVABLE",
    "ANSWER_CONFLICT_UNRESOLVED",
    "INSUFFICIENT_EVIDENCE",
    "CURRENT_DATA_REQUIRED",
    "ANSWER_PUBLICATION_FORBIDDEN",
    "RA_POLICY_MISSING"
)

$expectedMetrics = @(
    "answer_support_status_total",
    "answer_unsupported_assertions_removed_total",
    "answer_citation_resolution_failed_total",
    "answer_abstention_total",
    "research_coverage_obligation_met_total",
    "answer_conflict_detected_total",
    "answer_knowledge_gap_total",
    "answer_evidence_set_sealed_total",
    "answer_model_draft_total"
)

$expectedBehaviors = @(
    @{ Name = "RA-001 - Spécification exécutable M-007"; Adr = @("ADR-006", "ADR-010", "DDD-ADR-003", "DDD-ADR-005", "DDD-ADR-007", "DDD-ADR-008"); Test = "T-002"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m007_specification.ps1" },
    @{ Name = "RA-002 - Cas de recherche avec mandat explicite"; Adr = @("ADR-010"); Test = "T-003"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m007\validate_research_case_mandate_acceptance.ps1" },
    @{ Name = "RA-003 - Jeu de preuves scellé"; Adr = @("DDD-ADR-003", "DDD-ADR-008"); Test = "T-004"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m007\validate_evidence_set_sealing_acceptance.ps1" },
    @{ Name = "RA-004 - Contradictions et lacunes classées"; Adr = @("DDD-ADR-005"); Test = "T-005"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m007\validate_contradiction_gap_acceptance.ps1" },
    @{ Name = "RA-005 - Assertions de réponse extraites"; Adr = @("DDD-ADR-005", "DDD-ADR-007"); Test = "T-006"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m007\validate_answer_assertion_extraction_acceptance.ps1" },
    @{ Name = "RA-006 - Support et citations évalués"; Adr = @("ADR-006", "DDD-ADR-003", "DDD-ADR-005", "DDD-ADR-007"); Test = "T-007"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m007\validate_answer_support_acceptance.ps1" },
    @{ Name = "RA-007 - Abstention données actuelles"; Adr = @("DDD-ADR-007"); Test = "T-008"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m007\validate_current_data_abstention_acceptance.ps1" },
    @{ Name = "RA-008 - Commande publique de réponse documentaire"; Adr = @("ADR-010", "DDD-ADR-003", "DDD-ADR-005"); Test = "T-009"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m007\validate_answer_http_contract_acceptance.ps1" },
    @{ Name = "RA-009 - Traçabilité et métriques M-007"; Adr = @("ADR-006", "ADR-010", "DDD-ADR-005", "DDD-ADR-008"); Test = "T-010"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m007\validate_m007_traceability_acceptance.ps1" }
)

function Normalize-M007Cell {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string] $Value
    )

    return ($Value.Trim() -replace "`"", "" -replace "\*\*", "" -replace "``", "" -replace "<br\s*/?>", " ")
}

function Split-M007MarkdownRow {
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

    return @($trimmedLine -split "\|" | ForEach-Object { Normalize-M007Cell -Value $_ })
}

function Test-M007SeparatorRow {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Line
    )

    return ($Line.Trim() -match "^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$")
}

function Read-M007MarkdownTable {
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

        $headers = Split-M007MarkdownRow -Line $Lines[$lineIndex]
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

        if (($lineIndex + 1) -ge $Lines.Count -or -not (Test-M007SeparatorRow -Line $Lines[$lineIndex + 1])) {
            throw "Table $TableName invalide: ligne de séparation absente."
        }

        $rows = @()
        $rowIndex = $lineIndex + 2
        while ($rowIndex -lt $Lines.Count -and $Lines[$rowIndex].Trim().StartsWith("|")) {
            if (Test-M007SeparatorRow -Line $Lines[$rowIndex]) {
                $rowIndex++
                continue
            }

            $cells = Split-M007MarkdownRow -Line $Lines[$rowIndex]
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

function Assert-M007Contains {
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

function Assert-M007AdrToken {
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

function Assert-M007ForbiddenPatterns {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content
    )

    $forbiddenPatterns = @(
        @{ Pattern = "RA\s+lit\s+Qdrant\s+directement"; Message = "Accès RA direct à Qdrant interdit" },
        @{ Pattern = "RA\s+acc[èe]de\s+directement\s+[àa]\s+Qdrant"; Message = "Accès RA direct à Qdrant interdit" },
        @{ Pattern = "RA\s+lit\s+le\s+registre\s+EG\s+interne\s+directement"; Message = "Accès RA direct au registre EG interne interdit" },
        @{ Pattern = "RA\s+acc[èe]de\s+directement\s+au\s+registre\s+EG\s+interne"; Message = "Accès RA direct au registre EG interne interdit" },
        @{ Pattern = "brouillon\s+de\s+r[ée]ponse\s+est\s+publi[ée]\s+comme\s+r[ée]ponse\s+finale"; Message = "Confusion brouillon/réponse publiée interdite" },
        @{ Pattern = "SupportStatus\s+par\s+d[ée]faut"; Message = "Statut de support par défaut interdit" },
        @{ Pattern = "score\s+.*devient\s+.*SupportStatus"; Message = "SupportStatus dérivé d'un score interdit" },
        @{ Pattern = "valeur\s+de\s+march[ée]\s+invent[ée]e"; Message = "Valeur de marché inventée interdite" }
    )

    foreach ($forbiddenPattern in $forbiddenPatterns) {
        if ($Content -match $forbiddenPattern.Pattern) {
            throw $forbiddenPattern.Message + ": " + $Matches[0]
        }
    }
}

function Resolve-M007SpecificationPath {
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
        throw "Chemin hors dépôt interdit (spécification M-007): $resolvedCandidatePath"
    }

    return $resolvedCandidatePath
}

function Assert-M007NamedRows {
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

function Assert-M007Policies {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable[]] $PolicyRows
    )

    $policiesByName = Assert-M007NamedRows `
        -Rows $PolicyRows `
        -NameColumn "Politique" `
        -RequiredColumns @("Décision", "Invariants", "ADR") `
        -ExpectedNames @($expectedPolicies | ForEach-Object { $_.Name }) `
        -Label "Politique M-007"

    foreach ($expectedPolicy in $expectedPolicies) {
        $row = $policiesByName[$expectedPolicy.Name]
        foreach ($adrId in $expectedPolicy.Adr) {
            Assert-M007AdrToken -Content $row["ADR"] -AdrId $adrId
        }
    }
}

function Assert-M007CommandPathExists {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Command,

        [Parameter(Mandatory = $true)]
        [string] $BehaviorName
    )

    if ($Command -notmatch "-File\s+(\S+)") {
        throw "Commande sans chemin -File pour $BehaviorName."
    }

    $relativePath = $Matches[1].Trim()
    $normalizedPath = $relativePath -replace "^\.[\\/]", ""
    $candidatePath = Join-Path $repoRoot $normalizedPath
    if (-not (Test-Path -LiteralPath $candidatePath -PathType Leaf)) {
        throw "Commande de validation introuvable pour ${BehaviorName}: $relativePath"
    }
}

function Assert-M007Behaviors {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable[]] $BehaviorRows
    )

    $behaviorsByName = Assert-M007NamedRows `
        -Rows $BehaviorRows `
        -NameColumn "Comportement" `
        -RequiredColumns @("Invariant", "Scénario BDD", "Test RED", "ADR", "Commande") `
        -ExpectedNames @($expectedBehaviors | ForEach-Object { $_.Name }) `
        -Label "Comportement M-007"

    foreach ($expectedBehavior in $expectedBehaviors) {
        $row = $behaviorsByName[$expectedBehavior.Name]
        if ($row["Test RED"] -ne $expectedBehavior.Test) {
            throw "Test RED invalide pour $($expectedBehavior.Name). Attendu: $($expectedBehavior.Test). Obtenu: $($row["Test RED"])"
        }
        if ($row["Commande"] -ne $expectedBehavior.Command) {
            throw "Commande invalide pour $($expectedBehavior.Name). Attendu: $($expectedBehavior.Command). Obtenu: $($row["Commande"])"
        }
        Assert-M007CommandPathExists -Command $row["Commande"] -BehaviorName $expectedBehavior.Name
        foreach ($adrId in $expectedBehavior.Adr) {
            Assert-M007AdrToken -Content $row["ADR"] -AdrId $adrId
        }
    }
}

function Assert-M007Spec {
    param(
        [Parameter(Mandatory = $true)]
        [string] $SpecPath
    )

    if (-not (Test-Path -LiteralPath $SpecPath -PathType Leaf)) {
        throw "Spécification M-007 absente: $SpecPath"
    }

    $content = (Get-Content -Raw -Encoding UTF8 -LiteralPath $SpecPath).TrimStart([char] 0xFEFF)
    $lines = @(Get-Content -Encoding UTF8 -LiteralPath $SpecPath)
    if ($lines.Count -gt 0) {
        $lines[0] = $lines[0].TrimStart([char] 0xFEFF)
    }

    Assert-M007ForbiddenPatterns -Content $content

    foreach ($section in $requiredSections) {
        if ($lines -notcontains $section) {
            throw "Section obligatoire absente: $section"
        }
    }

    foreach ($marker in $requiredMarkers) {
        Assert-M007Contains -Content $content -Expected $marker -Message "Marqueur obligatoire absent: $marker"
    }

    foreach ($adrId in $requiredAdrIds) {
        Assert-M007AdrToken -Content $content -AdrId $adrId
    }

    foreach ($term in $requiredTerms) {
        Assert-M007Contains -Content $content -Expected $term -Message "Terme du langage RA absent: $term"
    }

    foreach ($command in $requiredCommands) {
        Assert-M007Contains -Content $content -Expected $command -Message "Commande de validation absente: $command"
    }

    $aggregateRows = Read-M007MarkdownTable -Lines $lines -RequiredHeaders @("Agrégat", "Responsabilité M-007", "Invariants", "Événements") -TableName "agrégats M-007"
    $aggregateNames = @("ResearchCase", "Answer")
    $aggregatesByName = Assert-M007NamedRows -Rows $aggregateRows -NameColumn "Agrégat" -RequiredColumns @("Responsabilité M-007", "Invariants", "Événements") -ExpectedNames $aggregateNames -Label "Agrégat M-007"
    foreach ($expectedEvent in @("AnswerVerified", "AnswerPartiallySupported", "AnswerPublicationBlocked", "AnswerAbstained")) {
        if (-not $aggregatesByName["Answer"]["Événements"].Contains($expectedEvent)) {
            throw "Événement Answer attendu absent: $expectedEvent"
        }
    }

    $valueObjectRows = Read-M007MarkdownTable -Lines $lines -RequiredHeaders @("Objet-valeur", "Sens M-007", "Invariants") -TableName "objets-valeur M-007"
    Assert-M007NamedRows -Rows $valueObjectRows -NameColumn "Objet-valeur" -RequiredColumns @("Sens M-007", "Invariants") -ExpectedNames $expectedValueObjects -Label "Objet-valeur M-007" | Out-Null

    $policyRows = Read-M007MarkdownTable -Lines $lines -RequiredHeaders @("Politique", "Décision", "Invariants", "ADR") -TableName "politiques M-007"
    Assert-M007Policies -PolicyRows $policyRows

    $stateRows = Read-M007MarkdownTable -Lines $lines -RequiredHeaders @("État", "Portée", "Sens M-007", "Transition autorisée") -TableName "états M-007"
    Assert-M007NamedRows -Rows $stateRows -NameColumn "État" -RequiredColumns @("Portée", "Sens M-007", "Transition autorisée") -ExpectedNames $expectedStates -Label "État M-007" | Out-Null

    $portRows = Read-M007MarkdownTable -Lines $lines -RequiredHeaders @("Port", "Responsabilité", "Interdiction") -TableName "ports M-007"
    Assert-M007NamedRows -Rows $portRows -NameColumn "Port" -RequiredColumns @("Responsabilité", "Interdiction") -ExpectedNames $expectedPorts -Label "Port M-007" | Out-Null

    $eventRows = Read-M007MarkdownTable -Lines $lines -RequiredHeaders @("Événement", "Déclencheur", "Payload publié") -TableName "événements M-007"
    Assert-M007NamedRows -Rows $eventRows -NameColumn "Événement" -RequiredColumns @("Déclencheur", "Payload publié") -ExpectedNames $expectedEvents -Label "Événement M-007" | Out-Null

    $endpointRows = Read-M007MarkdownTable -Lines $lines -RequiredHeaders @("Endpoint", "Succès", "Erreurs publiques", "Corps public") -TableName "API M-007"
    Assert-M007NamedRows -Rows $endpointRows -NameColumn "Endpoint" -RequiredColumns @("Succès", "Erreurs publiques", "Corps public") -ExpectedNames $expectedEndpoints -Label "Endpoint M-007" | Out-Null

    $errorRows = Read-M007MarkdownTable -Lines $lines -RequiredHeaders @("Code", "Statut HTTP", "Sens public") -TableName "erreurs publiques M-007"
    Assert-M007NamedRows -Rows $errorRows -NameColumn "Code" -RequiredColumns @("Statut HTTP", "Sens public") -ExpectedNames $expectedPublicErrors -Label "Erreur publique M-007" | Out-Null

    $metricRows = Read-M007MarkdownTable -Lines $lines -RequiredHeaders @("Signal", "Type", "Invariant") -TableName "métriques M-007"
    Assert-M007NamedRows -Rows $metricRows -NameColumn "Signal" -RequiredColumns @("Type", "Invariant") -ExpectedNames $expectedMetrics -Label "Signal M-007" | Out-Null

    $behaviorRows = Read-M007MarkdownTable -Lines $lines -RequiredHeaders @("Comportement", "Invariant", "Scénario BDD", "Test RED", "ADR", "Commande") -TableName "comportements M-007"
    Assert-M007Behaviors -BehaviorRows $behaviorRows
}

$resolvedPath = Resolve-M007SpecificationPath -InputPath $Path
Assert-M007Spec -SpecPath $resolvedPath

Write-Host "Spécification M-007 valide: $($expectedBehaviors.Count) comportement(s), $($expectedPolicies.Count) politique(s), $($expectedStates.Count) état(s) contrôlé(s)."
