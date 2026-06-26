param(
    [Parameter(Mandatory = $false)]
    [string] $Path
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$eAcute = [char] 0x00E9
$eGrave = [char] 0x00E8
$aGrave = [char] 0x00E0
$eCircumflex = [char] 0x00EA
$cCedilla = [char] 0x00E7
$oCircumflex = [char] 0x00F4

$defaultSpecificationPath = "docs/specs/m004_version_canonique_publiee.md"

$requiredSections = @(
    "# M-004 - Version canonique publi$($eAcute)e",
    "## Statut",
    "## Sc$($eAcute)nario BDD",
    "## Mission",
    "## Contexte DDD",
    "## Langage ubiquitaire M-004",
    "## Agr$($eAcute)gats et objets-valeur",
    "## Politiques normatives M-004",
    "## Machine d'$($eAcute)tats M-004",
    "## Fusion pagewise vers DoclingDocument unique",
    "## QA pr$($eAcute)-conversion",
    "## QA post-conversion",
    "## $($eAcute)v$($eAcute)nements M-004",
    "## Comportements v$($eAcute)rifiables M-004",
    "## Contrat HTTP M-004",
    "## Commandes de validation",
    "## Exclusions M-005"
)

$requiredAdrIds = @(
    "ADR-001",
    "ADR-002",
    "ADR-003",
    "ADR-004",
    "DDD-ADR-003"
)

$requiredMarkers = @(
    "Given une source M-003 enregistr$($eAcute)e, diagnostiqu$($eAcute)e et rout$($eAcute)e.",
    "When la sp$($eAcute)cification M-004 est publi$($eAcute)e.",
    "Then chaque comportement de version canonique nomme son invariant, son sc$($eAcute)nario BDD, son test RED, ses ADR applicables et sa commande de validation.",
    "Chaque page poss$($eGrave)de exactement une autorit$($eAcute) textuelle unique.",
    "Aucune page ne peut $($eCircumflex)tre omise"
)

$requiredTerms = @(
    "CanonicalSource",
    "CanonicalVersionId",
    "DoclingDocument unique",
    "Docling JSON canonique",
    "TextAuthoritySelectionPolicy",
    "CanonicalAcceptancePolicy",
    "CriticalPageSamplingPolicy",
    "CanonicalSourcePublished",
    "SourceLocator",
    "POST /v1/documents/{id}/convert",
    "M-005"
)

$requiredCommands = @(
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m004\validate_m004_specification_acceptance.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m004_specification.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1"
)

$requiredHttpMarkers = @(
    "POST /v1/documents/{id}/convert",
    "202",
    "400",
    "404",
    "409",
    "422",
    "CONVERSION_REQUESTED",
    "HTTP_REQUEST_INVALID",
    "SOURCE_NOT_FOUND",
    "SOURCE_NOT_ROUTED",
    "SOURCE_QUARANTINED",
    "PAGE_AUTHORITY_MISSING",
    "SOURCE_NOT_CANONICAL"
)

$expectedAggregates = @(
    @{
        Name = "CanonicalSource"
        Events = @("CanonicalSourceAccepted", "CanonicalSourcePublished", "CanonicalSourceSuperseded", "CanonicalSourceQuarantined")
    }
)

$expectedValueObjects = @(
    "CanonicalVersionId",
    "CanonicalArtifactRef",
    "TextAuthorityManifest",
    "QualityDecision",
    "CanonicalArtifactHash"
)

$expectedPolicies = @(
    @{ Name = "TextAuthoritySelectionPolicy"; Adr = @("ADR-004") },
    @{ Name = "CanonicalAcceptancePolicy"; Adr = @("ADR-001", "ADR-002", "ADR-003", "ADR-004", "DDD-ADR-003") },
    @{ Name = "CriticalPageSamplingPolicy"; Adr = @("ADR-002", "ADR-003", "ADR-004") }
)

$expectedStates = @(
    "ROUTED",
    "PRE_QA_PASSED",
    "CONVERTED",
    "POST_QA_PASSED",
    "ACCEPTED",
    "PUBLISHED",
    "SUPERSEDED",
    "QUARANTINED",
    "REJECTED"
)

$expectedEvents = @(
    "PageTextAuthoritySelected",
    "DocumentConversionCompleted",
    "CanonicalSourceAccepted",
    "CanonicalSourcePublished",
    "CanonicalSourceSuperseded"
)

$expectedBehaviors = @(
    @{ Name = "SP-009 - Sp$($eAcute)cification ex$($eAcute)cutable M-004"; Adr = @("ADR-001", "ADR-002", "ADR-003", "ADR-004", "DDD-ADR-003"); Test = "T-002" },
    @{ Name = "SP-010 - Fusion pagewise vers DoclingDocument unique"; Adr = @("ADR-001", "ADR-002", "ADR-003", "ADR-004"); Test = "T-003" },
    @{ Name = "SP-011 - Autorit$($eAcute) textuelle unique par page"; Adr = @("ADR-004"); Test = "T-004" },
    @{ Name = "SP-012 - QA pr$($eAcute) et post-conversion"; Adr = @("ADR-001", "ADR-002", "ADR-003", "ADR-004"); Test = "T-005" },
    @{ Name = "SP-013 - Publication immuable"; Adr = @("ADR-001", "DDD-ADR-003"); Test = "T-006" },
    @{ Name = "SP-014 - SourceLocator r$($eAcute)solvable"; Adr = @("DDD-ADR-003"); Test = "T-007" },
    @{ Name = "SP-015 - $($eAcute)v$($eAcute)nement CanonicalSourcePublished"; Adr = @("ADR-001", "DDD-ADR-003"); Test = "T-008" },
    @{ Name = "SP-016 - Contrat HTTP de conversion"; Adr = @("ADR-010", "DDD-ADR-003"); Test = "T-009" },
    @{ Name = "SP-017 - Tra$($cCedilla)abilit$($eAcute) et gates M-004"; Adr = @("ADR-010"); Test = "T-010" }
)

function Normalize-M004Cell {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string] $Value
    )

    return ($Value.Trim() -replace "`"", "" -replace "\*\*", "" -replace "``", "" -replace "<br\s*/?>", " ")
}

function Split-M004MarkdownRow {
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

    return @($trimmedLine -split "\|" | ForEach-Object { Normalize-M004Cell -Value $_ })
}

function Test-M004SeparatorRow {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Line
    )

    return ($Line.Trim() -match "^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$")
}

function Read-M004MarkdownTable {
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

        $headers = Split-M004MarkdownRow -Line $Lines[$lineIndex]
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

        if (($lineIndex + 1) -ge $Lines.Count -or -not (Test-M004SeparatorRow -Line $Lines[$lineIndex + 1])) {
            throw "Table $TableName invalide: ligne de s$($eAcute)paration absente."
        }

        $rows = @()
        $rowIndex = $lineIndex + 2
        while ($rowIndex -lt $Lines.Count -and $Lines[$rowIndex].Trim().StartsWith("|")) {
            if (Test-M004SeparatorRow -Line $Lines[$rowIndex]) {
                $rowIndex++
                continue
            }

            $cells = Split-M004MarkdownRow -Line $Lines[$rowIndex]
            if ($cells.Count -ne $headers.Count) {
                throw "Table $TableName invalide: nombre de cellules incoh$($eAcute)rent ligne $($rowIndex + 1)."
            }

            $row = @{}
            for ($cellIndex = 0; $cellIndex -lt $headers.Count; $cellIndex++) {
                $key = [string] $headers[$cellIndex]
                $value = [string] $cells[$cellIndex]
                $row[$key] = $value
            }
            $rows += ,$row
            $rowIndex++
        }

        if (@($rows).Count -eq 0) {
            throw "Table $TableName invalide: aucune ligne de donn$($eAcute)es."
        }

        return @($rows)
    }

    throw "Table $TableName absente."
}

function Assert-M004Contains {
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

function Assert-M004AdrToken {
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

function Assert-M004ForbiddenPatterns {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content
    )

    $forbiddenFallbackPatterns = @(
        "fallback\s+silencieux\s+(?:autoris[e$($eAcute)]|activ[e$($eAcute)]|possible|permis|configur[e$($eAcute)])",
        "fallback\s+Docling\s+vers\s+Granite\s+(?:silencieux|automatique|autoris[e$($eAcute)]|activ[e$($eAcute)]|possible|configur[e$($eAcute)])",
        "bascule\s+silencieuse\s+(?:autoris[e$($eAcute)]|activ[e$($eAcute)]|possible|permise|configur[e$($eAcute)])",
        "fusion\s+silencieuse\s+de\s+(?:transcriptions|sorties)"
    )

    foreach ($pattern in $forbiddenFallbackPatterns) {
        if ($Content -match $pattern) {
            throw "Fallback silencieux interdit: $($Matches[0])"
        }
    }

    $forbiddenPagePatterns = @(
        "page\s+peut\s+(?:$($eCircumflex)tre|etre)\s+omise\s+silencieusement",
        "PAGE_OMISSION_ALLOWED"
    )

    foreach ($pattern in $forbiddenPagePatterns) {
        if ($Content -match $pattern) {
            throw "Page omise interdite: $($Matches[0])"
        }
    }

    $forbiddenMutationPatterns = @(
        "correction\s+modifie\s+la\s+version\s+publi[e$($eAcute)]e\s+en\s+place",
        "mutation\s+en\s+place\s+(?:autoris[e$($eAcute)]e|possible|configur[e$($eAcute)]e)"
    )

    foreach ($pattern in $forbiddenMutationPatterns) {
        if ($Content -match $pattern) {
            throw "Mutation en place interdite: $($Matches[0])"
        }
    }

    $forbiddenProjectionPatterns = @(
        "M-004\s+cr[e$($eAcute)]e\s+une\s+projection\s+KA",
        "M-004\s+construit\s+.*KnowledgeProjection",
        "M-004\s+indexe\s+.*Qdrant"
    )

    foreach ($pattern in $forbiddenProjectionPatterns) {
        if ($Content -match $pattern) {
            throw "Projection KA interdite: $($Matches[0])"
        }
    }

    $forbiddenArtifactPatterns = @(
        "Markdown\s+(?:est|devient)\s+.*(?:canonique|source\s+de\s+v[e$($eAcute)]rit[e$($eAcute)])",
        "HTML\s+(?:est|devient)\s+.*(?:canonique|source\s+de\s+v[e$($eAcute)]rit[e$($eAcute)])"
    )

    foreach ($pattern in $forbiddenArtifactPatterns) {
        if ($Content -match $pattern) {
            throw "Artefact d$($eAcute)riv$($eAcute) trait$($eAcute) comme source canonique: $($Matches[0])"
        }
    }
}

function Resolve-M004SpecificationPath {
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
        throw "Chemin hors d$($eAcute)p$($oCircumflex)t interdit (sp$($eAcute)cification M-004): $resolvedCandidatePath"
    }

    return $resolvedCandidatePath
}

function Assert-M004Aggregates {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable[]] $AggregateRows
    )

    $aggregatesByName = @{}
    foreach ($row in $AggregateRows) {
        $aggregateName = $row["Agr$($eAcute)gat"]
        if ([string]::IsNullOrWhiteSpace($aggregateName)) {
            throw "Agr$($eAcute)gat M-004 sans nom."
        }
        if ($aggregatesByName.ContainsKey($aggregateName)) {
            throw "Agr$($eAcute)gat M-004 dupliqu$($eAcute): $aggregateName"
        }

        foreach ($requiredColumn in @("Responsabilit$($eAcute) M-004", "Invariants", "$($eAcute)v$($eAcute)nements")) {
            if ([string]::IsNullOrWhiteSpace($row[$requiredColumn])) {
                throw "Colonne $requiredColumn vide pour $aggregateName."
            }
        }

        $aggregatesByName[$aggregateName] = $row
    }

    foreach ($expectedAggregate in $expectedAggregates) {
        if (-not $aggregatesByName.ContainsKey($expectedAggregate.Name)) {
            throw "Agr$($eAcute)gat attendu absent: $($expectedAggregate.Name)"
        }

        $row = $aggregatesByName[$expectedAggregate.Name]
        foreach ($eventName in $expectedAggregate.Events) {
            if (-not $row["$($eAcute)v$($eAcute)nements"].Contains($eventName)) {
                throw "$($eAcute)v$($eAcute)nement attendu absent pour $($expectedAggregate.Name): $eventName"
            }
        }
    }
}

function Assert-M004ValueObjects {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable[]] $ValueObjectRows
    )

    $valueObjectsByName = @{}
    foreach ($row in $ValueObjectRows) {
        $valueObjectName = $row["Objet-valeur"]
        if ([string]::IsNullOrWhiteSpace($valueObjectName)) {
            throw "Objet-valeur M-004 sans nom."
        }
        if ($valueObjectsByName.ContainsKey($valueObjectName)) {
            throw "Objet-valeur M-004 dupliqu$($eAcute): $valueObjectName"
        }

        foreach ($requiredColumn in @("Sens M-004", "Invariants")) {
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

function Assert-M004Policies {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable[]] $PolicyRows
    )

    $policiesByName = @{}
    foreach ($row in $PolicyRows) {
        $policyName = $row["Politique"]
        if ([string]::IsNullOrWhiteSpace($policyName)) {
            throw "Politique M-004 sans nom."
        }
        if ($policiesByName.ContainsKey($policyName)) {
            throw "Politique M-004 dupliqu$($eAcute)e: $policyName"
        }

        foreach ($requiredColumn in @("D$($eAcute)cision", "Invariants", "ADR")) {
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
            Assert-M004AdrToken -Content $row["ADR"] -AdrId $adrId
        }
    }
}

function Assert-M004States {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable[]] $StateRows
    )

    $statesByName = @{}
    foreach ($row in $StateRows) {
        $stateName = $row["$($eAcute)tat"]
        if ([string]::IsNullOrWhiteSpace($stateName)) {
            throw "$($eAcute)tat M-004 sans nom."
        }
        if ($statesByName.ContainsKey($stateName)) {
            throw "$($eAcute)tat M-004 dupliqu$($eAcute): $stateName"
        }

        foreach ($requiredColumn in @("Port$($eAcute)e", "Sens M-004", "Transition autoris$($eAcute)e")) {
            if ([string]::IsNullOrWhiteSpace($row[$requiredColumn])) {
                throw "Colonne $requiredColumn vide pour $stateName."
            }
        }

        $statesByName[$stateName] = $row
    }

    foreach ($expectedState in $expectedStates) {
        if (-not $statesByName.ContainsKey($expectedState)) {
            throw "$($eAcute)tat attendu absent: $expectedState"
        }
    }
}

function Assert-M004Events {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable[]] $EventRows
    )

    $eventsByName = @{}
    foreach ($row in $EventRows) {
        $eventName = $row["$($eAcute)v$($eAcute)nement"]
        if ([string]::IsNullOrWhiteSpace($eventName)) {
            throw "$($eAcute)v$($eAcute)nement M-004 sans nom."
        }
        if ($eventsByName.ContainsKey($eventName)) {
            throw "$($eAcute)v$($eAcute)nement M-004 dupliqu$($eAcute): $eventName"
        }

        foreach ($requiredColumn in @("D$($eAcute)clencheur", "Payload publi$($eAcute)")) {
            if ([string]::IsNullOrWhiteSpace($row[$requiredColumn])) {
                throw "Colonne $requiredColumn vide pour $eventName."
            }
        }

        $eventsByName[$eventName] = $row
    }

    foreach ($expectedEvent in $expectedEvents) {
        if (-not $eventsByName.ContainsKey($expectedEvent)) {
            throw "$($eAcute)v$($eAcute)nement attendu absent: $expectedEvent"
        }
    }
}

function Assert-M004Behaviors {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable[]] $BehaviorRows
    )

    $behaviorsByName = @{}
    foreach ($row in $BehaviorRows) {
        $behaviorName = $row["Comportement"]
        if ([string]::IsNullOrWhiteSpace($behaviorName)) {
            throw "Comportement M-004 sans nom."
        }
        if ($behaviorsByName.ContainsKey($behaviorName)) {
            throw "Comportement M-004 dupliqu$($eAcute): $behaviorName"
        }

        foreach ($requiredColumn in @("Invariant", "Sc$($eAcute)nario BDD", "Test RED", "ADR", "Commande")) {
            if ([string]::IsNullOrWhiteSpace($row[$requiredColumn])) {
                throw "Colonne $requiredColumn vide pour $behaviorName."
            }
        }

        if ($row["Test RED"] -match "(?i)\b(TBD|TODO|$($aGrave)\s+d$($eAcute)finir|a\s+definir)\b") {
            throw "Test RED non ex$($eAcute)cutable pour $behaviorName."
        }

        if (-not $row["Commande"].Contains("powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m004_specification.ps1")) {
            throw "Commande de validation M-004 absente pour $behaviorName."
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

        foreach ($adrId in $expectedBehavior.Adr) {
            Assert-M004AdrToken -Content $row["ADR"] -AdrId $adrId
        }
    }
}

function Assert-M004Spec {
    param(
        [Parameter(Mandatory = $true)]
        [string] $SpecPath
    )

    if (-not (Test-Path -LiteralPath $SpecPath -PathType Leaf)) {
        throw "Sp$($eAcute)cification M-004 absente: $SpecPath"
    }

    $content = Get-Content -Raw -Encoding UTF8 -LiteralPath $SpecPath
    $lines = @(Get-Content -Encoding UTF8 -LiteralPath $SpecPath)

    Assert-M004ForbiddenPatterns -Content $content

    foreach ($section in $requiredSections) {
        if ($lines -notcontains $section) {
            throw "Section obligatoire absente: $section"
        }
    }

    foreach ($marker in $requiredMarkers) {
        Assert-M004Contains `
            -Content $content `
            -Expected $marker `
            -Message "Marqueur obligatoire absent: $marker"
    }

    foreach ($adrId in $requiredAdrIds) {
        Assert-M004AdrToken -Content $content -AdrId $adrId
    }

    foreach ($term in $requiredTerms) {
        Assert-M004Contains `
            -Content $content `
            -Expected $term `
            -Message "Terme du langage M-004 absent: $term"
    }

    foreach ($command in $requiredCommands) {
        Assert-M004Contains `
            -Content $content `
            -Expected $command `
            -Message "Commande de validation absente: $command"
    }

    foreach ($marker in $requiredHttpMarkers) {
        Assert-M004Contains `
            -Content $content `
            -Expected $marker `
            -Message "Marqueur HTTP M-004 absent: $marker"
    }

    $aggregateRows = Read-M004MarkdownTable `
        -Lines $lines `
        -RequiredHeaders @("Agr$($eAcute)gat", "Responsabilit$($eAcute) M-004", "Invariants", "$($eAcute)v$($eAcute)nements") `
        -TableName "agr$($eAcute)gats M-004"
    Assert-M004Aggregates -AggregateRows $aggregateRows

    $valueObjectRows = Read-M004MarkdownTable `
        -Lines $lines `
        -RequiredHeaders @("Objet-valeur", "Sens M-004", "Invariants") `
        -TableName "objets-valeur M-004"
    Assert-M004ValueObjects -ValueObjectRows $valueObjectRows

    $policyRows = Read-M004MarkdownTable `
        -Lines $lines `
        -RequiredHeaders @("Politique", "D$($eAcute)cision", "Invariants", "ADR") `
        -TableName "politiques M-004"
    Assert-M004Policies -PolicyRows $policyRows

    $stateRows = Read-M004MarkdownTable `
        -Lines $lines `
        -RequiredHeaders @("$($eAcute)tat", "Port$($eAcute)e", "Sens M-004", "Transition autoris$($eAcute)e") `
        -TableName "$($eAcute)tats M-004"
    Assert-M004States -StateRows $stateRows

    $eventRows = Read-M004MarkdownTable `
        -Lines $lines `
        -RequiredHeaders @("$($eAcute)v$($eAcute)nement", "D$($eAcute)clencheur", "Payload publi$($eAcute)") `
        -TableName "$($eAcute)v$($eAcute)nements M-004"
    Assert-M004Events -EventRows $eventRows

    $behaviorRows = Read-M004MarkdownTable `
        -Lines $lines `
        -RequiredHeaders @("Comportement", "Invariant", "Sc$($eAcute)nario BDD", "Test RED", "ADR", "Commande") `
        -TableName "comportements M-004"
    Assert-M004Behaviors -BehaviorRows $behaviorRows
}

$resolvedPath = Resolve-M004SpecificationPath -InputPath $Path
Assert-M004Spec -SpecPath $resolvedPath

Write-Host "Sp$($eAcute)cification M-004 valide: $($expectedBehaviors.Count) comportement(s), $($expectedPolicies.Count) politique(s), $($expectedStates.Count) $($eAcute)tat(s) contr$($oCircumflex)l$($eAcute)(s)."
