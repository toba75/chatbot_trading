param(
    [Parameter(Mandatory = $false)]
    [string] $Path
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$defaultSpecificationPath = "docs/specs/m008_conversation_produit.md"

$requiredSections = @(
    "# M-008 - Conversation produit",
    "## Statut",
    "## Scénario BDD",
    "## Mission CV",
    "## Contexte DDD",
    "## Langage ubiquitaire CV",
    "## Agrégats CV",
    "## Objets-valeur CV",
    "## Politiques normatives M-008",
    "## Machine d'états M-008",
    "## Ports et adaptateurs CV",
    "## Événements CV",
    "## API publique CV",
    "## Erreurs publiques",
    "## Métriques et traces",
    "## Comportements vérifiables M-008",
    "## Commandes de validation",
    "## Exclusions M-008"
)

$requiredAdrIds = @(
    "ADR-010",
    "DDD-ADR-001",
    "DDD-ADR-002",
    "DDD-ADR-003",
    "DDD-ADR-007",
    "DDD-ADR-008"
)

$requiredMarkers = @(
    "Given la mission M-008 est de permettre une conversation suivie sans preuve historique implicite.",
    "When la spécification de conversation produit est publiée.",
    "Then chaque comportement CV nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.",
    "L'historique conversationnel n'est jamais une preuve autonome.",
    "Une question de suivi est résolue en question autonome avant tout appel à RA, SD ou EX.",
    "Toute assertion historique réutilisée sans VerifiedAnswerVersion est renvoyée à RA pour revalidation avant présentation.",
    'Le DTO public RA de présentation expose answer_text et citations sans modifier `VerifiedResearchOutcome`.',
    '`VerifiedResearchOutcome` ne porte ni answer_text ni citations.',
    "aucun fallback de mode n'est appliqué",
    "l'archivage conversationnel ne supprime pas les connaissances"
)

$requiredTerms = @(
    "Conversation",
    "ConversationTurn",
    "ConversationContextSnapshot",
    "ResolvedQuestion",
    "ConversationMode",
    "ConversationModeSelection",
    "ReferenceResolutionPolicy",
    "ConversationModeRoutingPolicy",
    "ConversationContextCompactionPolicy",
    "VerifiedResultReusePolicy",
    "ConversationRetentionPolicy",
    "PublicAnswerPresentationPolicy",
    "ChatCompatibilityPolicy",
    "VerifiedAnswerVersion",
    "VerifiedResearchOutcome",
    "AnswerQuestionResult",
    "PublicAnswerPresentationDto",
    "CHAT_DOCUMENTAIRE",
    "RECHERCHE_APPROFONDIE",
    "COMPARAISON",
    "CONCEPTION_STRATEGIE",
    "CALCUL",
    "BACKTEST",
    "CLARIFICATION_INTERNE",
    "POST /v1/conversations",
    "GET /v1/conversations/{conversation_id}",
    "GET /v1/conversations/{conversation_id}/turns",
    "POST /v1/conversations/{conversation_id}/messages",
    "DELETE /v1/conversations/{conversation_id}",
    "POST /v1/chat/completions",
    "HTTP_REQUEST_INVALID",
    "ENDPOINT_NOT_FOUND",
    "CONVERSATION_NOT_FOUND",
    "CONVERSATION_ARCHIVED",
    "FOLLOW_UP_AMBIGUOUS",
    "CONVERSATION_MODE_UNSUPPORTED",
    "HISTORICAL_ASSERTION_REVALIDATION_REQUIRED",
    "ANSWER_PUBLIC_PAYLOAD_REQUIRED",
    "CHAT_COMPLETIONS_FIELD_UNSUPPORTED"
)

$requiredCommands = @(
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m008\validate_m008_specification_acceptance.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m008\validate_m008_specification_unit.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m008_specification.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1"
)

$expectedAggregates = @(
    "Conversation",
    "ConversationTurn"
)

$expectedValueObjects = @(
    "ConversationId",
    "ConversationTurnId",
    "ConversationContextSnapshot",
    "ResolvedQuestion",
    "ConversationMode",
    "ConversationModeSelection",
    "HistoricalAssertionRef",
    "VerifiedAnswerVersionRef",
    "PublicAnswerPresentationDto",
    "ConversationRetentionDecision"
)

$expectedPolicies = @(
    @{ Name = "ReferenceResolutionPolicy"; Adr = @("DDD-ADR-007") },
    @{ Name = "ConversationModeRoutingPolicy"; Adr = @("ADR-010", "DDD-ADR-007") },
    @{ Name = "ConversationContextCompactionPolicy"; Adr = @("DDD-ADR-003", "DDD-ADR-007") },
    @{ Name = "VerifiedResultReusePolicy"; Adr = @("DDD-ADR-003", "DDD-ADR-007", "DDD-ADR-008") },
    @{ Name = "PublicAnswerPresentationPolicy"; Adr = @("DDD-ADR-002", "DDD-ADR-003") },
    @{ Name = "ConversationRetentionPolicy"; Adr = @("DDD-ADR-002", "DDD-ADR-008") },
    @{ Name = "ChatCompatibilityPolicy"; Adr = @("ADR-010", "DDD-ADR-001") }
)

$expectedStates = @(
    "ACTIVE",
    "ARCHIVED",
    "USER_TURN_APPENDED",
    "QUESTION_RESOLVED",
    "MODE_SELECTED",
    "DISPATCHED_TO_RA",
    "DISPATCHED_TO_SD",
    "DISPATCHED_TO_EX",
    "VERIFIED_RESULT_ATTACHED",
    "CLARIFICATION_REQUIRED",
    "PRESENTED",
    "REJECTED"
)

$expectedPorts = @(
    "QuestionResolver",
    "ModeClassifier",
    "ConversationRepository",
    "ConversationTurnRepository",
    "ConversationContextStore",
    "ResearchFacade",
    "StrategyFacade",
    "ExperimentFacade",
    "PublicAnswerPresenter",
    "ChatCompletionsAdapter"
)

$expectedEvents = @(
    "ConversationCreated",
    "UserTurnAppended",
    "FollowUpQuestionResolved",
    "ConversationModeSelected",
    "HistoricalAssertionRevalidationRequested",
    "VerifiedAnswerAttachedToTurn",
    "StrategyAttachedToTurn",
    "ExperimentAttachedToTurn",
    "ConversationPreferencesUpdated",
    "ConversationArchived",
    "ConversationPublicResponsePresented"
)

$expectedEndpoints = @(
    "POST /v1/conversations",
    "GET /v1/conversations/{conversation_id}",
    "GET /v1/conversations/{conversation_id}/turns",
    "POST /v1/conversations/{conversation_id}/messages",
    "DELETE /v1/conversations/{conversation_id}",
    "POST /v1/chat/completions"
)

$expectedPublicErrors = @(
    "HTTP_REQUEST_INVALID",
    "ENDPOINT_NOT_FOUND",
    "CONVERSATION_NOT_FOUND",
    "CONVERSATION_TURN_NOT_FOUND",
    "CONVERSATION_ARCHIVED",
    "FOLLOW_UP_AMBIGUOUS",
    "CONVERSATION_MODE_UNSUPPORTED",
    "CONVERSATION_MODE_FORCED_UNSUPPORTED",
    "RESOLVED_QUESTION_REQUIRED",
    "VERIFIED_ANSWER_VERSION_REQUIRED",
    "HISTORICAL_ASSERTION_REVALIDATION_REQUIRED",
    "ANSWER_PUBLIC_PAYLOAD_REQUIRED",
    "CHAT_COMPLETIONS_FIELD_UNSUPPORTED",
    "CV_POLICY_MISSING"
)

$expectedMetrics = @(
    "conversation_created_total",
    "conversation_turn_appended_total",
    "follow_up_question_resolved_total",
    "conversation_mode_selected_total",
    "historical_assertion_revalidated_total",
    "verified_answer_attached_total",
    "conversation_archived_total",
    "conversation_public_error_total",
    "conversation_prompt_payload_rejected_total"
)

$expectedBehaviors = @(
    @{ Name = "CV-001 - Spécification exécutable M-008"; Adr = @("ADR-010", "DDD-ADR-001", "DDD-ADR-002", "DDD-ADR-003", "DDD-ADR-007", "DDD-ADR-008"); Test = "T-002"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m008_specification.ps1" },
    @{ Name = "CV-002 - Conversations et tours append-only"; Adr = @("DDD-ADR-002", "DDD-ADR-008"); Test = "T-003"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m008\validate_conversation_turn_append_only_acceptance.ps1" },
    @{ Name = "CV-003 - Snapshot de contexte sans preuve factuelle"; Adr = @("DDD-ADR-003", "DDD-ADR-007"); Test = "T-004"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m008\validate_conversation_context_snapshot_acceptance.ps1" },
    @{ Name = "CV-004 - Résolution des références de suivi"; Adr = @("DDD-ADR-007"); Test = "T-005"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m008\validate_followup_question_resolution_acceptance.ps1" },
    @{ Name = "CV-005 - Routage de mode justifié"; Adr = @("ADR-010", "DDD-ADR-007"); Test = "T-006"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m008\validate_conversation_mode_routing_acceptance.ps1" },
    @{ Name = "CV-006 - Revalidation RA des assertions historiques"; Adr = @("DDD-ADR-003", "DDD-ADR-007", "DDD-ADR-008"); Test = "T-007"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m008\validate_verified_result_reuse_acceptance.ps1" },
    @{ Name = "CV-007 - Présentation produit depuis DTO public RA"; Adr = @("DDD-ADR-002", "DDD-ADR-003"); Test = "T-008"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m008\validate_chat_answer_presentation_acceptance.ps1" },
    @{ Name = "CV-008 - Endpoints conversation et archivage"; Adr = @("ADR-010", "DDD-ADR-001", "DDD-ADR-002"); Test = "T-009"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m008\validate_conversation_http_contract_acceptance.ps1" },
    @{ Name = "CV-009 - Compatibilité chat contrôlée"; Adr = @("ADR-010", "DDD-ADR-001", "DDD-ADR-007"); Test = "T-010"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m008\validate_chat_completions_contract_acceptance.ps1" },
    @{ Name = "CV-010 - Traçabilité et métriques M-008"; Adr = @("ADR-010", "DDD-ADR-008"); Test = "T-011"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m008\validate_m008_traceability_acceptance.ps1" }
)

function Normalize-M008Cell {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string] $Value
    )

    return ($Value.Trim() -replace "`"", "" -replace "\*\*", "" -replace "``", "" -replace "<br\s*/?>", " ")
}

function Split-M008MarkdownRow {
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

    return @($trimmedLine -split "\|" | ForEach-Object { Normalize-M008Cell -Value $_ })
}

function Test-M008SeparatorRow {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Line
    )

    return ($Line.Trim() -match "^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$")
}

function Read-M008MarkdownTable {
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

        $headers = Split-M008MarkdownRow -Line $Lines[$lineIndex]
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

        if (($lineIndex + 1) -ge $Lines.Count -or -not (Test-M008SeparatorRow -Line $Lines[$lineIndex + 1])) {
            throw "Table $TableName invalide: ligne de séparation absente."
        }

        $rows = @()
        $rowIndex = $lineIndex + 2
        while ($rowIndex -lt $Lines.Count -and $Lines[$rowIndex].Trim().StartsWith("|")) {
            if (Test-M008SeparatorRow -Line $Lines[$rowIndex]) {
                $rowIndex++
                continue
            }

            $cells = Split-M008MarkdownRow -Line $Lines[$rowIndex]
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

function Assert-M008Contains {
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

function Assert-M008AdrToken {
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

function Assert-M008ForbiddenPatterns {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content
    )

    $forbiddenPatterns = @(
        @{ Pattern = "historique\s+conversationnel\s+(est|devient)\s+une\s+preuve"; Message = "Historique conversationnel traité comme preuve autonome interdit" },
        @{ Pattern = "(choisit|s[ée]lectionne|applique).*(mode|CHAT_DOCUMENTAIRE|RECHERCHE_APPROFONDIE).*par\s+d[ée]faut"; Message = "Fallback de mode interdit" },
        @{ Pattern = "fallback\s+silencieux\s+de\s+mode"; Message = "Fallback de mode interdit" },
        @{ Pattern = "VerifiedResearchOutcome\s+(contient|porte|expose|ajoute).*?(answer_text|citations)"; Message = "Confusion VerifiedResearchOutcome/DTO public RA interdite" },
        @{ Pattern = "answer_text\s+.*ajout[ée]\s+.*VerifiedResearchOutcome"; Message = "Confusion VerifiedResearchOutcome/DTO public RA interdite" },
        @{ Pattern = "CV\s+modifie\s+(ResearchCase|Answer|VerifiedResearchOutcome|Claim)"; Message = "Mutation d'agrégat hors CV interdite" },
        @{ Pattern = "CV\s+lit\s+(Qdrant|le\s+registre\s+EG|la\s+table\s+SP)\s+directement"; Message = "Accès direct au stockage documentaire interdit" },
        @{ Pattern = "prompt\s+override\s+accept[ée]\s+silencieusement"; Message = "Prompt override silencieux interdit" }
    )

    foreach ($forbiddenPattern in $forbiddenPatterns) {
        if ($Content -match $forbiddenPattern.Pattern) {
            throw $forbiddenPattern.Message + ": " + $Matches[0]
        }
    }
}

function Resolve-M008SpecificationPath {
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
        throw "Chemin hors dépôt interdit (spécification M-008): $resolvedCandidatePath"
    }

    return $resolvedCandidatePath
}

function Assert-M008NamedRows {
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

function Assert-M008Policies {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable[]] $PolicyRows
    )

    $policiesByName = Assert-M008NamedRows `
        -Rows $PolicyRows `
        -NameColumn "Politique" `
        -RequiredColumns @("Décision", "Invariants", "ADR") `
        -ExpectedNames @($expectedPolicies | ForEach-Object { $_.Name }) `
        -Label "Politique M-008"

    foreach ($expectedPolicy in $expectedPolicies) {
        $row = $policiesByName[$expectedPolicy.Name]
        foreach ($adrId in $expectedPolicy.Adr) {
            Assert-M008AdrToken -Content $row["ADR"] -AdrId $adrId
        }
    }
}

function Assert-M008Behaviors {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable[]] $BehaviorRows
    )

    $behaviorsByName = Assert-M008NamedRows `
        -Rows $BehaviorRows `
        -NameColumn "Comportement" `
        -RequiredColumns @("Invariant", "Scénario BDD", "Test RED", "ADR", "Commande") `
        -ExpectedNames @($expectedBehaviors | ForEach-Object { $_.Name }) `
        -Label "Comportement M-008"

    foreach ($expectedBehavior in $expectedBehaviors) {
        $row = $behaviorsByName[$expectedBehavior.Name]
        if ($row["Test RED"] -ne $expectedBehavior.Test) {
            throw "Test RED invalide pour $($expectedBehavior.Name). Attendu: $($expectedBehavior.Test). Obtenu: $($row["Test RED"])"
        }
        if ($row["Commande"] -ne $expectedBehavior.Command) {
            throw "Commande invalide pour $($expectedBehavior.Name). Attendu: $($expectedBehavior.Command). Obtenu: $($row["Commande"])"
        }
        foreach ($adrId in $expectedBehavior.Adr) {
            Assert-M008AdrToken -Content $row["ADR"] -AdrId $adrId
        }
    }
}

function Assert-M008Spec {
    param(
        [Parameter(Mandatory = $true)]
        [string] $SpecPath
    )

    if (-not (Test-Path -LiteralPath $SpecPath -PathType Leaf)) {
        throw "Spécification M-008 absente: $SpecPath"
    }

    $content = (Get-Content -Raw -Encoding UTF8 -LiteralPath $SpecPath).TrimStart([char] 0xFEFF)
    $lines = @(Get-Content -Encoding UTF8 -LiteralPath $SpecPath)
    if ($lines.Count -gt 0) {
        $lines[0] = $lines[0].TrimStart([char] 0xFEFF)
    }

    Assert-M008ForbiddenPatterns -Content $content

    foreach ($section in $requiredSections) {
        if ($lines -notcontains $section) {
            throw "Section obligatoire absente: $section"
        }
    }

    foreach ($marker in $requiredMarkers) {
        Assert-M008Contains -Content $content -Expected $marker -Message "Marqueur obligatoire absent: $marker"
    }

    foreach ($adrId in $requiredAdrIds) {
        Assert-M008AdrToken -Content $content -AdrId $adrId
    }

    foreach ($term in $requiredTerms) {
        Assert-M008Contains -Content $content -Expected $term -Message "Terme du langage CV absent: $term"
    }

    foreach ($command in $requiredCommands) {
        Assert-M008Contains -Content $content -Expected $command -Message "Commande de validation absente: $command"
    }

    $aggregateRows = Read-M008MarkdownTable -Lines $lines -RequiredHeaders @("Agrégat", "Responsabilité M-008", "Invariants", "Événements") -TableName "agrégats M-008"
    Assert-M008NamedRows -Rows $aggregateRows -NameColumn "Agrégat" -RequiredColumns @("Responsabilité M-008", "Invariants", "Événements") -ExpectedNames $expectedAggregates -Label "Agrégat M-008" | Out-Null

    $valueObjectRows = Read-M008MarkdownTable -Lines $lines -RequiredHeaders @("Objet-valeur", "Sens M-008", "Invariants") -TableName "objets-valeur M-008"
    Assert-M008NamedRows -Rows $valueObjectRows -NameColumn "Objet-valeur" -RequiredColumns @("Sens M-008", "Invariants") -ExpectedNames $expectedValueObjects -Label "Objet-valeur M-008" | Out-Null

    $policyRows = Read-M008MarkdownTable -Lines $lines -RequiredHeaders @("Politique", "Décision", "Invariants", "ADR") -TableName "politiques M-008"
    Assert-M008Policies -PolicyRows $policyRows

    $stateRows = Read-M008MarkdownTable -Lines $lines -RequiredHeaders @("État", "Portée", "Sens M-008", "Transition autorisée") -TableName "états M-008"
    Assert-M008NamedRows -Rows $stateRows -NameColumn "État" -RequiredColumns @("Portée", "Sens M-008", "Transition autorisée") -ExpectedNames $expectedStates -Label "État M-008" | Out-Null

    $portRows = Read-M008MarkdownTable -Lines $lines -RequiredHeaders @("Port", "Responsabilité", "Interdiction") -TableName "ports M-008"
    Assert-M008NamedRows -Rows $portRows -NameColumn "Port" -RequiredColumns @("Responsabilité", "Interdiction") -ExpectedNames $expectedPorts -Label "Port M-008" | Out-Null

    $eventRows = Read-M008MarkdownTable -Lines $lines -RequiredHeaders @("Événement", "Déclencheur", "Payload publié") -TableName "événements M-008"
    Assert-M008NamedRows -Rows $eventRows -NameColumn "Événement" -RequiredColumns @("Déclencheur", "Payload publié") -ExpectedNames $expectedEvents -Label "Événement M-008" | Out-Null

    $endpointRows = Read-M008MarkdownTable -Lines $lines -RequiredHeaders @("Endpoint", "Succès", "Erreurs publiques", "Corps public") -TableName "API M-008"
    Assert-M008NamedRows -Rows $endpointRows -NameColumn "Endpoint" -RequiredColumns @("Succès", "Erreurs publiques", "Corps public") -ExpectedNames $expectedEndpoints -Label "Endpoint M-008" | Out-Null

    $errorRows = Read-M008MarkdownTable -Lines $lines -RequiredHeaders @("Code", "Statut HTTP", "Sens public") -TableName "erreurs publiques M-008"
    Assert-M008NamedRows -Rows $errorRows -NameColumn "Code" -RequiredColumns @("Statut HTTP", "Sens public") -ExpectedNames $expectedPublicErrors -Label "Erreur publique M-008" | Out-Null

    $metricRows = Read-M008MarkdownTable -Lines $lines -RequiredHeaders @("Signal", "Type", "Invariant") -TableName "métriques M-008"
    Assert-M008NamedRows -Rows $metricRows -NameColumn "Signal" -RequiredColumns @("Type", "Invariant") -ExpectedNames $expectedMetrics -Label "Signal M-008" | Out-Null

    $behaviorRows = Read-M008MarkdownTable -Lines $lines -RequiredHeaders @("Comportement", "Invariant", "Scénario BDD", "Test RED", "ADR", "Commande") -TableName "comportements M-008"
    Assert-M008Behaviors -BehaviorRows $behaviorRows
}

$resolvedPath = Resolve-M008SpecificationPath -InputPath $Path
Assert-M008Spec -SpecPath $resolvedPath

Write-Host "Spécification M-008 valide: $($expectedBehaviors.Count) comportement(s), $($expectedPolicies.Count) politique(s), $($expectedStates.Count) état(s) contrôlé(s)."
