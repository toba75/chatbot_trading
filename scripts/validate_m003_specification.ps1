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
$oCircumflex = [char] 0x00F4

$defaultSpecificationPath = "docs/specs/m003_source_enregistree_diagnostiquee_routee.md"

$requiredSections = @(
    "# M-003 - Source enregistr$($eAcute)e, diagnostiqu$($eAcute)e et rout$($eAcute)e",
    "## Statut",
    "## Sc$($eAcute)nario BDD",
    "## Mission",
    "## Contexte DDD",
    "## Langage ubiquitaire M-003",
    "## Agr$($eAcute)gats et objets-valeur",
    "## Politiques de domaine M-003",
    "## Machine d'$($eAcute)tats M-003",
    "## Comportements v$($eAcute)rifiables M-003",
    "## Contrat HTTP M-003",
    "## Commandes de validation",
    "## Exclusions M-004"
)

$requiredAdrIds = @(
    "ADR-002",
    "ADR-003",
    "ADR-010",
    "DDD-ADR-003"
)

$requiredMarkers = @(
    "Given la sp$($eAcute)cification v4.1 d$($eAcute)finit SP comme propri$($eAcute)taire du diagnostic et du routage documentaire.",
    "When la sp$($eAcute)cification M-003 est publi$($eAcute)e.",
    "Then chaque comportement M-003 nomme son invariant, son sc$($eAcute)nario BDD, son test RED, ses ADR applicables et sa commande de validation."
)

$requiredTerms = @(
    "SourceDocument",
    "DocumentProcessingRun",
    "PDF original",
    "empreinte stable",
    "manifeste de pages",
    "diagnostic de page",
    "route de page",
    "revue manuelle",
    "quarantaine"
)

$requiredCommands = @(
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m003\validate_m003_specification_acceptance.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m003_specification.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1"
)

$requiredHttpMarkers = @(
    "POST /v1/documents",
    "POST /v1/documents/{id}/diagnose",
    "201",
    "200",
    "202",
    "400",
    "404",
    "409",
    "422",
    "DUPLICATE_SOURCE",
    "HTTP_REQUEST_INVALID"
)

$expectedAggregates = @(
    @{ Name = "SourceDocument"; Events = @("SourceDocumentRegistered", "SourceDocumentQuarantined") },
    @{ Name = "DocumentProcessingRun"; Events = @("PageManifestCreated", "PageDiagnosticRecorded", "PageRoutePlanned", "ManualReviewRequested") }
)

$expectedValueObjects = @(
    "OriginalFingerprint",
    "PageManifest",
    "PageDiagnostic",
    "PageRoute"
)

$expectedPolicies = @(
    @{ Name = "SourceRegistrationPolicy"; Adr = @("DDD-ADR-003") },
    @{ Name = "PageManifestCompletenessPolicy"; Adr = @("DDD-ADR-003") },
    @{ Name = "PageDiagnosticPolicy"; Adr = @("ADR-002", "ADR-003") },
    @{ Name = "PageRoutingPolicy"; Adr = @("ADR-002") },
    @{ Name = "QuarantinePublicationPolicy"; Adr = @("DDD-ADR-003") }
)

$expectedStates = @(
    "REGISTERED",
    "MANIFEST_CREATED",
    "DIAGNOSED",
    "ROUTE_PLANNED",
    "MANUAL_REVIEW",
    "QUARANTINED"
)

$expectedBehaviors = @(
    @{ Name = "SP-001 - Enregistrement immuable"; Adr = @("DDD-ADR-003"); Test = "T-003" },
    @{ Name = "SP-002 - Manifeste complet"; Adr = @("DDD-ADR-003"); Test = "T-004" },
    @{ Name = "SP-003 - Diagnostic page par page"; Adr = @("ADR-002", "ADR-003"); Test = "T-005" },
    @{ Name = "SP-004 - Routage explicite"; Adr = @("ADR-002"); Test = "T-006" },
    @{ Name = "SP-005 - Revue manuelle d'incertitude"; Adr = @("ADR-002", "ADR-003"); Test = "T-006" },
    @{ Name = "SP-006 - Quarantaine non publiable"; Adr = @("DDD-ADR-003"); Test = "T-007" },
    @{ Name = "SP-007 - Commandes de validation"; Adr = @("ADR-002", "ADR-003", "DDD-ADR-003"); Test = "T-002" },
    @{ Name = "SP-008 - Contrat HTTP documentaire"; Adr = @("DDD-ADR-003", "ADR-010"); Test = "T-008" }
)

function Normalize-M003Cell {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string] $Value
    )

    return ($Value.Trim() -replace "`"", "" -replace "\*\*", "" -replace "``", "" -replace "<br\s*/?>", " ")
}

function Split-M003MarkdownRow {
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

    return @($trimmedLine -split "\|" | ForEach-Object { Normalize-M003Cell -Value $_ })
}

function Test-M003SeparatorRow {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Line
    )

    return ($Line.Trim() -match "^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$")
}

function Read-M003MarkdownTable {
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

        $headers = Split-M003MarkdownRow -Line $Lines[$lineIndex]
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

        if (($lineIndex + 1) -ge $Lines.Count -or -not (Test-M003SeparatorRow -Line $Lines[$lineIndex + 1])) {
            throw "Table $TableName invalide: ligne de s$($eAcute)paration absente."
        }

        $rows = @()
        $rowIndex = $lineIndex + 2
        while ($rowIndex -lt $Lines.Count -and $Lines[$rowIndex].Trim().StartsWith("|")) {
            if (Test-M003SeparatorRow -Line $Lines[$rowIndex]) {
                $rowIndex++
                continue
            }

            $cells = Split-M003MarkdownRow -Line $Lines[$rowIndex]
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

function Assert-M003Contains {
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

function Assert-M003AdrToken {
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

function Assert-M003ForbiddenPatterns {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content
    )

    $forbiddenFallbackPatterns = @(
        "silent_fallback\s*:\s*true",
        "fallback\s+silencieux\s+(?:autoris[e$($eAcute)]|activ[e$($eAcute)]|possible|permis|configur[e$($eAcute)])",
        "bascule\s+silencieuse\s+(?:autoris[e$($eAcute)]|activ[e$($eAcute)]|possible|permise|configur[e$($eAcute)])",
        "route\s+de\s+secours\s+automatique"
    )

    foreach ($pattern in $forbiddenFallbackPatterns) {
        if ($Content -match $pattern) {
            throw "Fallback silencieux interdit: $($Matches[0])"
        }
    }

    $forbiddenRoutePatterns = @(
        "route\s+par\s+d[e$($eAcute)]faut\s+(?:autoris[e$($eAcute)]e|accept[e$($eAcute)]e|appliqu[e$($eAcute)]e|utilis[e$($eAcute)]e|configur[e$($eAcute)]e)",
        "default_route\s*:\s*[A-Za-z0-9_]+",
        "\bDEFAULT_ROUTE\b",
        "sinon\s+(?:NATIVE_STANDARD|SCAN_GRANITE|PREPROCESS_GRANITE|BAD_OCR_TO_GRANITE|MIXED_PAGEWISE|TARGETED_ENRICHMENT)"
    )

    foreach ($pattern in $forbiddenRoutePatterns) {
        if ($Content -match $pattern) {
            throw "Route par d$($eAcute)faut interdite: $($Matches[0])"
        }
    }

    $forbiddenM004Patterns = @(
        "M-004\s+est\s+(?:impl[e$($eAcute)]ment[e$($eAcute)]|livr[e$($eAcute)]|planifi[e$($eAcute)]|r[e$($eAcute)]alis[e$($eAcute)])\s+par\s+M-003",
        "conversion\s+canonique\s+publi[e$($eAcute)]e\s+par\s+M-003",
        "version\s+canonique\s+publi[e$($eAcute)]e\s+par\s+M-003",
        "CanonicalSourcePublished\s+vers\s+KA\s+ou\s+EG\s+est\s+publi[e$($eAcute)]\s+par\s+M-003"
    )

    foreach ($pattern in $forbiddenM004Patterns) {
        if ($Content -match $pattern) {
            throw "Exigence M-004 interdite dans M-003: $($Matches[0])"
        }
    }
}

function Resolve-M003SpecificationPath {
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
        throw "Chemin hors d$($eAcute)p$($oCircumflex)t interdit (sp$($eAcute)cification M-003): $resolvedCandidatePath"
    }

    return $resolvedCandidatePath
}

function Assert-M003Aggregates {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable[]] $AggregateRows
    )

    $aggregatesByName = @{}
    foreach ($row in $AggregateRows) {
        $aggregateName = $row["Agr$($eAcute)gat"]
        if ([string]::IsNullOrWhiteSpace($aggregateName)) {
            throw "Agr$($eAcute)gat M-003 sans nom."
        }
        if ($aggregatesByName.ContainsKey($aggregateName)) {
            throw "Agr$($eAcute)gat M-003 dupliqu$($eAcute): $aggregateName"
        }

        foreach ($requiredColumn in @("Responsabilit$($eAcute) M-003", "Invariants", "$($eAcute)v$($eAcute)nements")) {
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

    foreach ($aggregateName in $aggregatesByName.Keys) {
        if (@($expectedAggregates | Where-Object { $_.Name -eq $aggregateName }).Count -eq 0) {
            throw "Agr$($eAcute)gat non pr$($eAcute)vu par M-003: $aggregateName"
        }
    }
}

function Assert-M003ValueObjects {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable[]] $ValueObjectRows
    )

    $valueObjectsByName = @{}
    foreach ($row in $ValueObjectRows) {
        $valueObjectName = $row["Objet-valeur"]
        if ([string]::IsNullOrWhiteSpace($valueObjectName)) {
            throw "Objet-valeur M-003 sans nom."
        }
        if ($valueObjectsByName.ContainsKey($valueObjectName)) {
            throw "Objet-valeur M-003 dupliqu$($eAcute): $valueObjectName"
        }
        foreach ($requiredColumn in @("Sens M-003", "Invariants")) {
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

function Assert-M003Policies {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable[]] $PolicyRows
    )

    $policiesByName = @{}
    foreach ($row in $PolicyRows) {
        $policyName = $row["Politique"]
        if ([string]::IsNullOrWhiteSpace($policyName)) {
            throw "Politique M-003 sans nom."
        }
        if ($policiesByName.ContainsKey($policyName)) {
            throw "Politique M-003 dupliqu$($eAcute)e: $policyName"
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
            Assert-M003AdrToken -Content $row["ADR"] -AdrId $adrId
        }
    }
}

function Assert-M003States {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable[]] $StateRows
    )

    $statesByName = @{}
    foreach ($row in $StateRows) {
        $stateName = $row["$($eAcute)tat"]
        if ([string]::IsNullOrWhiteSpace($stateName)) {
            throw "$($eAcute)tat M-003 sans nom."
        }
        if ($statesByName.ContainsKey($stateName)) {
            throw "$($eAcute)tat M-003 dupliqu$($eAcute): $stateName"
        }

        foreach ($requiredColumn in @("Port$($eAcute)e", "Sens M-003", "Transition autoris$($eAcute)e")) {
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

function Assert-M003Behaviors {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable[]] $BehaviorRows
    )

    $behaviorsByName = @{}
    foreach ($row in $BehaviorRows) {
        $behaviorName = $row["Comportement"]
        if ([string]::IsNullOrWhiteSpace($behaviorName)) {
            throw "Comportement M-003 sans nom."
        }
        if ($behaviorsByName.ContainsKey($behaviorName)) {
            throw "Comportement M-003 dupliqu$($eAcute): $behaviorName"
        }

        foreach ($requiredColumn in @("Invariant", "Sc$($eAcute)nario BDD", "Test RED", "ADR", "Commande")) {
            if ([string]::IsNullOrWhiteSpace($row[$requiredColumn])) {
                throw "Colonne $requiredColumn vide pour $behaviorName."
            }
        }

        if ($row["Test RED"] -match "(?i)\b(TBD|TODO|$($aGrave)\s+d$($eAcute)finir|a\s+definir)\b") {
            throw "Test RED non ex$($eAcute)cutable pour $behaviorName."
        }

        if (-not $row["Commande"].Contains("powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m003_specification.ps1")) {
            throw "Commande de validation M-003 absente pour $behaviorName."
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
            Assert-M003AdrToken -Content $row["ADR"] -AdrId $adrId
        }
    }
}

function Assert-M003Spec {
    param(
        [Parameter(Mandatory = $true)]
        [string] $SpecPath
    )

    if (-not (Test-Path -LiteralPath $SpecPath -PathType Leaf)) {
        throw "Sp$($eAcute)cification M-003 absente: $SpecPath"
    }

    $content = Get-Content -Raw -Encoding UTF8 -LiteralPath $SpecPath
    $lines = @(Get-Content -Encoding UTF8 -LiteralPath $SpecPath)

    Assert-M003ForbiddenPatterns -Content $content

    foreach ($section in $requiredSections) {
        if ($lines -notcontains $section) {
            throw "Section obligatoire absente: $section"
        }
    }

    foreach ($marker in $requiredMarkers) {
        Assert-M003Contains `
            -Content $content `
            -Expected $marker `
            -Message "Marqueur BDD obligatoire absent: $marker"
    }

    foreach ($term in $requiredTerms) {
        Assert-M003Contains `
            -Content $content `
            -Expected $term `
            -Message "Terme du langage M-003 absent: $term"
    }

    foreach ($command in $requiredCommands) {
        Assert-M003Contains `
            -Content $content `
            -Expected $command `
            -Message "Commande de validation absente: $command"
    }

    foreach ($marker in $requiredHttpMarkers) {
        Assert-M003Contains `
            -Content $content `
            -Expected $marker `
            -Message "Marqueur HTTP M-003 absent: $marker"
    }

    foreach ($adrId in $requiredAdrIds) {
        Assert-M003AdrToken -Content $content -AdrId $adrId
    }

    $aggregateRows = Read-M003MarkdownTable `
        -Lines $lines `
        -RequiredHeaders @("Agr$($eAcute)gat", "Responsabilit$($eAcute) M-003", "Invariants", "$($eAcute)v$($eAcute)nements") `
        -TableName "agr$($eAcute)gats M-003"
    Assert-M003Aggregates -AggregateRows $aggregateRows

    $valueObjectRows = Read-M003MarkdownTable `
        -Lines $lines `
        -RequiredHeaders @("Objet-valeur", "Sens M-003", "Invariants") `
        -TableName "objets-valeur M-003"
    Assert-M003ValueObjects -ValueObjectRows $valueObjectRows

    $policyRows = Read-M003MarkdownTable `
        -Lines $lines `
        -RequiredHeaders @("Politique", "D$($eAcute)cision", "Invariants", "ADR") `
        -TableName "politiques M-003"
    Assert-M003Policies -PolicyRows $policyRows

    $stateRows = Read-M003MarkdownTable `
        -Lines $lines `
        -RequiredHeaders @("$($eAcute)tat", "Port$($eAcute)e", "Sens M-003", "Transition autoris$($eAcute)e") `
        -TableName "$($eAcute)tats M-003"
    Assert-M003States -StateRows $stateRows

    $behaviorRows = Read-M003MarkdownTable `
        -Lines $lines `
        -RequiredHeaders @("Comportement", "Invariant", "Sc$($eAcute)nario BDD", "Test RED", "ADR", "Commande") `
        -TableName "comportements M-003"
    Assert-M003Behaviors -BehaviorRows $behaviorRows
}

$resolvedPath = Resolve-M003SpecificationPath -InputPath $Path
Assert-M003Spec -SpecPath $resolvedPath

Write-Host "Sp$($eAcute)cification M-003 valide: $($expectedBehaviors.Count) comportement(s), $($expectedPolicies.Count) politique(s), $($expectedStates.Count) $($eAcute)tat(s) contr$($oCircumflex)l$($eAcute)(s)."
