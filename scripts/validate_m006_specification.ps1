param(
    [Parameter(Mandatory = $false)]
    [string] $Path
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$defaultSpecificationPath = "docs/specs/m006_claims_verifiables.md"

$requiredSections = @(
    "# M-006 - Claims vérifiables",
    "## Statut",
    "## Scénario BDD",
    "## Mission EG",
    "## Contexte DDD",
    "## Langage ubiquitaire EG",
    "## Agrégats EG",
    "## Objets-valeur EG",
    "## Politiques normatives M-006",
    "## Machine d'états M-006",
    "## Ports et adaptateurs EG",
    "## Événements EG",
    "## API publique EG",
    "## Erreurs publiques",
    "## Métriques et traces",
    "## Comportements vérifiables M-006",
    "## Commandes de validation",
    "## Exclusions M-006"
)

$requiredAdrIds = @(
    "ADR-006",
    "ADR-010",
    "DDD-ADR-003",
    "DDD-ADR-005",
    "DDD-ADR-007",
    "DDD-ADR-010"
)

$requiredMarkers = @(
    "Given des preuves candidates KA avec SourceLocator résolvable.",
    "When la spécification M-006 est publiée.",
    "Then chaque comportement de claim nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.",
    "Une affirmation VERIFIED DOIT posséder au moins une preuve directe admissible.",
    "La portée de l'affirmation ne peut dépasser la portée commune de ses preuves sans qualification explicite.",
    "Le LLM propose et la politique décide.",
    "aucun claim EG stocké dans l'index documentaire",
    "EG consomme KnowledgeSearchPort sans accès direct à Qdrant",
    "un score n'est pas un verdict métier"
)

$requiredTerms = @(
    "Claim",
    "VerificationCase",
    "DependencyGroup",
    "CanonicalProposition",
    "SourceLocator",
    "EvidenceRef",
    "EvidenceAdmissibilityPolicy",
    "ClaimVerificationPolicy",
    "ScopePreservationPolicy",
    "SourceIndependencePolicy",
    "POST /v1/claims/extract",
    "POST /v1/claims/{claim_id}/verify",
    "GET /v1/claims/{claim_id}",
    "GET /v1/claims/{claim_id}/evidence",
    "INSUFFICIENT_DIRECT_EVIDENCE",
    "CLAIM_SCOPE_EXCEEDS_EVIDENCE",
    "CLAIM_EVIDENCE_SOURCE_UNRESOLVABLE"
)

$requiredCommands = @(
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m006\validate_m006_specification_acceptance.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m006\validate_m006_specification_unit.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m006_specification.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1"
)

$expectedValueObjects = @(
    "ClaimId",
    "ClaimVersion",
    "CanonicalProposition",
    "ClaimScope",
    "ClaimCondition",
    "Limitation",
    "EvidenceRef",
    "SourceLocator",
    "VerificationVerdict",
    "ReasonCode",
    "CalibratedScore"
)

$expectedPolicies = @(
    @{ Name = "ClaimAtomicityPolicy"; Adr = @("DDD-ADR-005") },
    @{ Name = "EvidenceAdmissibilityPolicy"; Adr = @("ADR-006", "DDD-ADR-003") },
    @{ Name = "ClaimVerificationPolicy"; Adr = @("DDD-ADR-005", "DDD-ADR-007") },
    @{ Name = "ScopePreservationPolicy"; Adr = @("DDD-ADR-005") },
    @{ Name = "SourceIndependencePolicy"; Adr = @("ADR-006") },
    @{ Name = "ClaimCanonicalizationPolicy"; Adr = @("DDD-ADR-005", "DDD-ADR-007") },
    @{ Name = "ClaimRelationPolicy"; Adr = @("DDD-ADR-005", "DDD-ADR-010") },
    @{ Name = "HumanReviewEscalationPolicy"; Adr = @("DDD-ADR-007") }
)

$expectedStates = @(
    "DRAFT",
    "EVIDENCE_ATTACHED",
    "UNDER_VERIFICATION",
    "VERIFIED",
    "REJECTED",
    "SUPERSEDED",
    "ABANDONED"
)

$expectedPorts = @(
    "CanonicalEvidenceReader",
    "KnowledgeSearchPort",
    "ClaimExtractor",
    "IndependentClaimVerifier",
    "DependencyResolver",
    "ClaimRepository",
    "VerificationCaseRepository",
    "DependencyGroupRepository",
    "ClaimRelationRepository",
    "HumanReviewQueue"
)

$expectedEvents = @(
    "ClaimDrafted",
    "EvidenceAttachedToClaim",
    "ClaimSubmittedForVerification",
    "VerificationDecisionRecorded",
    "ClaimVerified",
    "ClaimRejected",
    "ClaimDependencyAssigned",
    "ClaimRelationRecorded",
    "ClaimSuperseded",
    "ClaimApprovedByHuman",
    "ClaimRejectedByHuman"
)

$expectedEndpoints = @(
    "POST /v1/claims/extract",
    "POST /v1/claims/{claim_id}/verify",
    "GET /v1/claims/{claim_id}",
    "GET /v1/claims/{claim_id}/evidence"
)

$expectedPublicErrors = @(
    "HTTP_REQUEST_INVALID",
    "CLAIM_CONTEXT_FORBIDDEN",
    "CLAIM_NOT_FOUND",
    "CLAIM_STATE_INVALID",
    "CLAIM_EVIDENCE_REQUIRED",
    "CLAIM_EVIDENCE_SOURCE_UNRESOLVABLE",
    "CLAIM_SCOPE_EXCEEDS_EVIDENCE",
    "INSUFFICIENT_DIRECT_EVIDENCE",
    "CLAIM_VERIFICATION_POLICY_MISSING",
    "CLAIM_PUBLICATION_FORBIDDEN"
)

$expectedMetrics = @(
    "claims_drafted_total",
    "claims_verified_total",
    "claims_rejected_total",
    "claim_verification_latency_seconds",
    "claim_scope_refusal_total",
    "claim_independent_support_groups",
    "claim_superseded_total",
    "claim_model_proposal_total",
    "claim_public_evidence_resolution_failed_total"
)

$expectedBehaviors = @(
    @{ Name = "EG-001 - Spécification exécutable M-006"; Adr = @("ADR-006", "ADR-010", "DDD-ADR-003", "DDD-ADR-005", "DDD-ADR-007", "DDD-ADR-010"); Test = "T-002"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m006_specification.ps1" },
    @{ Name = "EG-002 - Extraction atomique structurée"; Adr = @("ADR-006", "DDD-ADR-005", "DDD-ADR-007"); Test = "T-003"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m006\validate_claim_extraction_acceptance.ps1" },
    @{ Name = "EG-003 - Preuves admissibles avec SourceLocator"; Adr = @("DDD-ADR-003", "DDD-ADR-005"); Test = "T-004"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m006\validate_claim_evidence_attachment_acceptance.ps1" },
    @{ Name = "EG-004 - Vérification par preuve directe et portée"; Adr = @("ADR-006", "DDD-ADR-005", "DDD-ADR-007"); Test = "T-005"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m006\validate_claim_verification_acceptance.ps1" },
    @{ Name = "EG-005 - Confirmations indépendantes par DependencyGroup"; Adr = @("ADR-006", "DDD-ADR-005", "DDD-ADR-010"); Test = "T-006"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m006\validate_dependency_group_acceptance.ps1" },
    @{ Name = "EG-006 - Relations après comparaison de portée"; Adr = @("DDD-ADR-005", "DDD-ADR-010"); Test = "T-007"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m006\validate_claim_relation_acceptance.ps1" },
    @{ Name = "EG-007 - Conservation des claims rejetés et supersédés"; Adr = @("ADR-006", "DDD-ADR-005", "DDD-ADR-010"); Test = "T-008"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m006\validate_claim_retention_acceptance.ps1" },
    @{ Name = "EG-008 - API claims et preuves publiques"; Adr = @("ADR-006", "ADR-010", "DDD-ADR-003", "DDD-ADR-005"); Test = "T-009"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m006\validate_claim_http_contract_acceptance.ps1" },
    @{ Name = "EG-009 - Traçabilité et métriques M-006"; Adr = @("ADR-006", "ADR-010", "DDD-ADR-005", "DDD-ADR-010"); Test = "T-010"; Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m006\validate_m006_traceability_acceptance.ps1" }
)

function Normalize-M006Cell {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string] $Value
    )

    return ($Value.Trim() -replace "`"", "" -replace "\*\*", "" -replace "``", "" -replace "<br\s*/?>", " ")
}

function Split-M006MarkdownRow {
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

    return @($trimmedLine -split "\|" | ForEach-Object { Normalize-M006Cell -Value $_ })
}

function Test-M006SeparatorRow {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Line
    )

    return ($Line.Trim() -match "^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$")
}

function Read-M006MarkdownTable {
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

        $headers = Split-M006MarkdownRow -Line $Lines[$lineIndex]
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

        if (($lineIndex + 1) -ge $Lines.Count -or -not (Test-M006SeparatorRow -Line $Lines[$lineIndex + 1])) {
            throw "Table $TableName invalide: ligne de séparation absente."
        }

        $rows = @()
        $rowIndex = $lineIndex + 2
        while ($rowIndex -lt $Lines.Count -and $Lines[$rowIndex].Trim().StartsWith("|")) {
            if (Test-M006SeparatorRow -Line $Lines[$rowIndex]) {
                $rowIndex++
                continue
            }

            $cells = Split-M006MarkdownRow -Line $Lines[$rowIndex]
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

function Assert-M006Contains {
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

function Assert-M006AdrToken {
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

function Assert-M006ForbiddenPatterns {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content
    )

    $forbiddenPatterns = @(
        @{ Pattern = "EG\s+lit\s+Qdrant\s+directement"; Message = "Accès EG direct à Qdrant interdit" },
        @{ Pattern = "EG\s+acc[èe]de\s+directement\s+[àa]\s+Qdrant"; Message = "Accès EG direct à Qdrant interdit" },
        @{ Pattern = "(?:index\s+documentaire|Qdrant)\s+stocke\s+(?:les\s+)?claims"; Message = "Claim EG dans l'index documentaire interdit" },
        @{ Pattern = "score\s+.*(?:devient|est|constitue)\s+le\s+verdict"; Message = "Score traité comme verdict métier interdit" },
        @{ Pattern = "score\s+.*trait.*comme\s+verdict"; Message = "Score traité comme verdict métier interdit" },
        @{ Pattern = "LLM\s+.*auto-?approuve"; Message = "Auto-approbation LLM interdite" },
        @{ Pattern = "fallback\s+.*(?:mod[èe]le|v[ée]rificateur).*silencieux"; Message = "Fallback silencieux interdit" }
    )

    foreach ($forbiddenPattern in $forbiddenPatterns) {
        if ($Content -match $forbiddenPattern.Pattern) {
            throw $forbiddenPattern.Message + ": " + $Matches[0]
        }
    }
}

function Resolve-M006SpecificationPath {
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
        throw "Chemin hors dépôt interdit (spécification M-006): $resolvedCandidatePath"
    }

    return $resolvedCandidatePath
}

function Assert-M006NamedRows {
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

function Assert-M006Policies {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable[]] $PolicyRows
    )

    $policiesByName = Assert-M006NamedRows `
        -Rows $PolicyRows `
        -NameColumn "Politique" `
        -RequiredColumns @("Décision", "Invariants", "ADR") `
        -ExpectedNames @($expectedPolicies | ForEach-Object { $_.Name }) `
        -Label "Politique M-006"

    foreach ($expectedPolicy in $expectedPolicies) {
        $row = $policiesByName[$expectedPolicy.Name]
        foreach ($adrId in $expectedPolicy.Adr) {
            Assert-M006AdrToken -Content $row["ADR"] -AdrId $adrId
        }
    }
}

function Assert-M006Behaviors {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable[]] $BehaviorRows
    )

    $behaviorsByName = Assert-M006NamedRows `
        -Rows $BehaviorRows `
        -NameColumn "Comportement" `
        -RequiredColumns @("Invariant", "Scénario BDD", "Test RED", "ADR", "Commande") `
        -ExpectedNames @($expectedBehaviors | ForEach-Object { $_.Name }) `
        -Label "Comportement M-006"

    foreach ($expectedBehavior in $expectedBehaviors) {
        $row = $behaviorsByName[$expectedBehavior.Name]
        if ($row["Test RED"] -ne $expectedBehavior.Test) {
            throw "Test RED invalide pour $($expectedBehavior.Name). Attendu: $($expectedBehavior.Test). Obtenu: $($row["Test RED"])"
        }
        if ($row["Commande"] -ne $expectedBehavior.Command) {
            throw "Commande invalide pour $($expectedBehavior.Name). Attendu: $($expectedBehavior.Command). Obtenu: $($row["Commande"])"
        }
        foreach ($adrId in $expectedBehavior.Adr) {
            Assert-M006AdrToken -Content $row["ADR"] -AdrId $adrId
        }
    }
}

function Assert-M006Spec {
    param(
        [Parameter(Mandatory = $true)]
        [string] $SpecPath
    )

    if (-not (Test-Path -LiteralPath $SpecPath -PathType Leaf)) {
        throw "Spécification M-006 absente: $SpecPath"
    }

    $content = (Get-Content -Raw -Encoding UTF8 -LiteralPath $SpecPath).TrimStart([char] 0xFEFF)
    $lines = @(Get-Content -Encoding UTF8 -LiteralPath $SpecPath)
    if ($lines.Count -gt 0) {
        $lines[0] = $lines[0].TrimStart([char] 0xFEFF)
    }

    Assert-M006ForbiddenPatterns -Content $content

    foreach ($section in $requiredSections) {
        if ($lines -notcontains $section) {
            throw "Section obligatoire absente: $section"
        }
    }

    foreach ($marker in $requiredMarkers) {
        Assert-M006Contains -Content $content -Expected $marker -Message "Marqueur obligatoire absent: $marker"
    }

    foreach ($adrId in $requiredAdrIds) {
        Assert-M006AdrToken -Content $content -AdrId $adrId
    }

    foreach ($term in $requiredTerms) {
        Assert-M006Contains -Content $content -Expected $term -Message "Terme du langage EG absent: $term"
    }

    foreach ($command in $requiredCommands) {
        Assert-M006Contains -Content $content -Expected $command -Message "Commande de validation absente: $command"
    }

    $aggregateRows = Read-M006MarkdownTable -Lines $lines -RequiredHeaders @("Agrégat", "Responsabilité M-006", "Invariants", "Événements") -TableName "agrégats M-006"
    $aggregateNames = @("Claim", "VerificationCase", "DependencyGroup")
    $aggregatesByName = Assert-M006NamedRows -Rows $aggregateRows -NameColumn "Agrégat" -RequiredColumns @("Responsabilité M-006", "Invariants", "Événements") -ExpectedNames $aggregateNames -Label "Agrégat M-006"
    foreach ($expectedEvent in @("ClaimVerified", "ClaimRejected", "ClaimSuperseded")) {
        if (-not $aggregatesByName["Claim"]["Événements"].Contains($expectedEvent)) {
            throw "Événement Claim attendu absent: $expectedEvent"
        }
    }

    $valueObjectRows = Read-M006MarkdownTable -Lines $lines -RequiredHeaders @("Objet-valeur", "Sens M-006", "Invariants") -TableName "objets-valeur M-006"
    Assert-M006NamedRows -Rows $valueObjectRows -NameColumn "Objet-valeur" -RequiredColumns @("Sens M-006", "Invariants") -ExpectedNames $expectedValueObjects -Label "Objet-valeur M-006" | Out-Null

    $policyRows = Read-M006MarkdownTable -Lines $lines -RequiredHeaders @("Politique", "Décision", "Invariants", "ADR") -TableName "politiques M-006"
    Assert-M006Policies -PolicyRows $policyRows

    $stateRows = Read-M006MarkdownTable -Lines $lines -RequiredHeaders @("État", "Portée", "Sens M-006", "Transition autorisée") -TableName "états M-006"
    Assert-M006NamedRows -Rows $stateRows -NameColumn "État" -RequiredColumns @("Portée", "Sens M-006", "Transition autorisée") -ExpectedNames $expectedStates -Label "État M-006" | Out-Null

    $portRows = Read-M006MarkdownTable -Lines $lines -RequiredHeaders @("Port", "Responsabilité", "Interdiction") -TableName "ports M-006"
    Assert-M006NamedRows -Rows $portRows -NameColumn "Port" -RequiredColumns @("Responsabilité", "Interdiction") -ExpectedNames $expectedPorts -Label "Port M-006" | Out-Null

    $eventRows = Read-M006MarkdownTable -Lines $lines -RequiredHeaders @("Événement", "Déclencheur", "Payload publié") -TableName "événements M-006"
    Assert-M006NamedRows -Rows $eventRows -NameColumn "Événement" -RequiredColumns @("Déclencheur", "Payload publié") -ExpectedNames $expectedEvents -Label "Événement M-006" | Out-Null

    $endpointRows = Read-M006MarkdownTable -Lines $lines -RequiredHeaders @("Endpoint", "Succès", "Erreurs publiques", "Corps public") -TableName "API M-006"
    Assert-M006NamedRows -Rows $endpointRows -NameColumn "Endpoint" -RequiredColumns @("Succès", "Erreurs publiques", "Corps public") -ExpectedNames $expectedEndpoints -Label "Endpoint M-006" | Out-Null

    $errorRows = Read-M006MarkdownTable -Lines $lines -RequiredHeaders @("Code", "Statut HTTP", "Sens public") -TableName "erreurs publiques M-006"
    Assert-M006NamedRows -Rows $errorRows -NameColumn "Code" -RequiredColumns @("Statut HTTP", "Sens public") -ExpectedNames $expectedPublicErrors -Label "Erreur publique M-006" | Out-Null

    $metricRows = Read-M006MarkdownTable -Lines $lines -RequiredHeaders @("Signal", "Type", "Invariant") -TableName "métriques M-006"
    Assert-M006NamedRows -Rows $metricRows -NameColumn "Signal" -RequiredColumns @("Type", "Invariant") -ExpectedNames $expectedMetrics -Label "Signal M-006" | Out-Null

    $behaviorRows = Read-M006MarkdownTable -Lines $lines -RequiredHeaders @("Comportement", "Invariant", "Scénario BDD", "Test RED", "ADR", "Commande") -TableName "comportements M-006"
    Assert-M006Behaviors -BehaviorRows $behaviorRows
}

$resolvedPath = Resolve-M006SpecificationPath -InputPath $Path
Assert-M006Spec -SpecPath $resolvedPath

Write-Host "Spécification M-006 valide: $($expectedBehaviors.Count) comportement(s), $($expectedPolicies.Count) politique(s), $($expectedStates.Count) état(s) contrôlé(s)."
