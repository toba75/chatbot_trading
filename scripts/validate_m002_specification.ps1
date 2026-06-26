param(
    [Parameter(Mandatory = $false)]
    [string] $Path
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$eAcute = [char] 0x00E9
$eGrave = [char] 0x00E8
$aGrave = [char] 0x00E0
$cCedilla = [char] 0x00E7
$eCircumflex = [char] 0x00EA
$uCircumflex = [char] 0x00FB
$oCircumflex = [char] 0x00F4

$defaultSpecificationPath = "docs/specs/m002_plateforme_locale_sure.md"

$requiredSections = @(
    "# M-002 - Plateforme locale s$($uCircumflex)re",
    "## Statut",
    "## Sc$($eAcute)nario BDD",
    "## Contexte DDD",
    "## Langage ubiquitaire M-002",
    "## Relations avec M-001",
    "## Placement des capacit$($eAcute)s",
    "## R$($eGrave)gles de plateforme M-002",
    "## Commandes de validation",
    "## Hors p$($eAcute)rim$($eGrave)tre M-002"
)

$requiredAdrIds = @(
    "ADR-007",
    "ADR-008",
    "ADR-009",
    "DDD-ADR-006",
    "DDD-ADR-008"
)

$requiredMarkers = @(
    "Given la sp$($eAcute)cification v4.1 impose deux plans physiques et une coh$($eAcute)rence $($eAcute)ventuelle par outbox.",
    "When la sp$($eAcute)cification M-002 est publi$($eAcute)e.",
    "Then chaque r$($eGrave)gle de plateforme nomme le comportement attendu, les invariants, les tests et les ADR qui la gouvernent."
)

$requiredTerms = @(
    "docker-local",
    "spark-inference",
    "llm-gateway",
    "gateway LLM",
    "outbox transactionnelle",
    "job prioris$($eAcute)",
    "appel d'inf$($eAcute)rence",
    "panne explicite",
    "observabilit$($eAcute) technique"
)

$requiredCommands = @(
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m002_specification.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1"
)

$expectedPlacements = @(
    @{ Capability = "Gemma 4 et vLLM principal"; Host = "spark-inference" },
    @{ Capability = "Application m$($eAcute)tier, API, UI et workers"; Host = "docker-local" },
    @{ Capability = "PostgreSQL, Qdrant, corpus et exp$($eAcute)riences"; Host = "docker-local" },
    @{ Capability = "llm-gateway"; Host = "docker-local" },
    @{ Capability = "Outbox et file de jobs"; Host = "docker-local" },
    @{ Capability = "Granite-Docling, embeddings et reranker"; Host = "docker-local" }
)

$expectedRules = @(
    @{ Name = "PLAT-001 - Placement docker-local"; Adr = @("ADR-007", "ADR-009") },
    @{ Name = "PLAT-002 - Spark d'inf$($eAcute)rence sans $($eAcute)tat m$($eAcute)tier"; Adr = @("ADR-007", "ADR-008", "ADR-009") },
    @{ Name = "PLAT-003 - Gateway LLM unique"; Adr = @("ADR-008", "ADR-009") },
    @{ Name = "PLAT-004 - Outbox transactionnelle"; Adr = @("DDD-ADR-006", "DDD-ADR-008") },
    @{ Name = "PLAT-005 - Jobs techniques prioris$($eAcute)s"; Adr = @("DDD-ADR-006") },
    @{ Name = "PLAT-006 - Pannes explicites d'inf$($eAcute)rence"; Adr = @("ADR-008", "ADR-009") },
    @{ Name = "PLAT-007 - Observabilit$($eAcute) technique"; Adr = @("ADR-008", "ADR-009") },
    @{ Name = "PLAT-008 - Commandes de validation"; Adr = @("ADR-010") }
)

$requiredObservabilityDimensions = @(
    "disponibilit$($eAcute) Spark",
    "DNS",
    "TCP",
    "TLS",
    "authentification",
    "latence",
    "TTFT",
    "retries",
    "circuit breaker"
)

function Normalize-M002Cell {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string] $Value
    )

    return ($Value.Trim() -replace "`"", "" -replace "\*\*", "" -replace "<br\s*/?>", " ")
}

function Split-M002MarkdownRow {
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

    return @($trimmedLine -split "\|" | ForEach-Object { Normalize-M002Cell -Value $_ })
}

function Test-M002SeparatorRow {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Line
    )

    return ($Line.Trim() -match "^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$")
}

function Read-M002MarkdownTable {
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

        $headers = Split-M002MarkdownRow -Line $Lines[$lineIndex]
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

        if (($lineIndex + 1) -ge $Lines.Count -or -not (Test-M002SeparatorRow -Line $Lines[$lineIndex + 1])) {
            throw "Table $TableName invalide: ligne de s$($eAcute)paration absente."
        }

        $rows = @()
        $rowIndex = $lineIndex + 2
        while ($rowIndex -lt $Lines.Count -and $Lines[$rowIndex].Trim().StartsWith("|")) {
            if (Test-M002SeparatorRow -Line $Lines[$rowIndex]) {
                $rowIndex++
                continue
            }

            $cells = Split-M002MarkdownRow -Line $Lines[$rowIndex]
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

function Assert-M002Contains {
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

function Assert-M002AdrToken {
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

function Assert-M002ForbiddenPatterns {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content
    )

    $forbiddenFallbackPatterns = @(
        "silent_fallback\s*:\s*true",
        "fallback\s+silencieux\s+(?:autoris[e$($eAcute)]|activ[e$($eAcute)]|possible|permis)",
        "fournisseur\s+distant\s+de\s+secours",
        "provider\s+distant\s+de\s+(?:secours|fallback)",
        "secours\s+automatique"
    )

    foreach ($pattern in $forbiddenFallbackPatterns) {
        if ($Content -match $pattern) {
            throw "Fallback silencieux interdit: $($Matches[0])"
        }
    }

    $forbiddenEndpointPatterns = @(
        "https?://spark-inference[^\s``<]*",
        "https?://(?:127\.0\.0\.1|localhost)(?::\d+)?(?:/[^\s``<]*)?",
        "\b\d{1,3}(?:\.\d{1,3}){3}:8443\b"
    )

    foreach ($pattern in $forbiddenEndpointPatterns) {
        if ($Content -match $pattern) {
            throw "Endpoint Spark cod$($eAcute) en dur interdit: $($Matches[0])"
        }
    }

    if ($Content -match "mTLS\s+obligatoire|require_mtls\s*:\s*true") {
        throw "mTLS obligatoire interdit sans nouvelle ADR."
    }
}

function Resolve-M002RepositoryPath {
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
        throw "Chemin hors d$($eAcute)p$($oCircumflex)t interdit (sp$($eAcute)cification M-002): $resolvedCandidatePath"
    }

    return $resolvedCandidatePath
}

function Assert-M002Placements {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable[]] $PlacementRows
    )

    $placementsByCapability = @{}
    foreach ($row in $PlacementRows) {
        $capability = $row["Capacit$($eAcute)"]
        if ([string]::IsNullOrWhiteSpace($capability)) {
            throw "Placement sans capacit$($eAcute)."
        }
        if ($placementsByCapability.ContainsKey($capability)) {
            throw "Placement dupliqu$($eAcute): $capability"
        }

        $placementHost = $row["H$($oCircumflex)te obligatoire"]
        if ([string]::IsNullOrWhiteSpace($placementHost)) {
            throw "H$($oCircumflex)te obligatoire vide pour $capability."
        }
        if ($placementHost -notin @("docker-local", "spark-inference")) {
            throw "H$($oCircumflex)te obligatoire inconnu pour ${capability}: $placementHost"
        }
        if ([string]::IsNullOrWhiteSpace($row["R$($eGrave)gle"])) {
            throw "R$($eGrave)gle de placement vide pour $capability."
        }

        $placementsByCapability[$capability] = $row
    }

    foreach ($expectedPlacement in $expectedPlacements) {
        if (-not $placementsByCapability.ContainsKey($expectedPlacement.Capability)) {
            throw "Placement attendu absent: $($expectedPlacement.Capability)"
        }

        $row = $placementsByCapability[$expectedPlacement.Capability]
        if ($row["H$($oCircumflex)te obligatoire"] -ne $expectedPlacement.Host) {
            throw "Placement invalide pour $($expectedPlacement.Capability). Attendu: $($expectedPlacement.Host). Obtenu: $($row["H$($oCircumflex)te obligatoire"])"
        }
    }

    foreach ($capability in $placementsByCapability.Keys) {
        if (@($expectedPlacements | Where-Object { $_.Capability -eq $capability }).Count -eq 0) {
            throw "Placement non pr$($eAcute)vu par M-002: $capability"
        }
    }
}

function Assert-M002Rules {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable[]] $RuleRows
    )

    $rulesByName = @{}
    foreach ($row in $RuleRows) {
        $ruleName = $row["R$($eGrave)gle"]
        if ([string]::IsNullOrWhiteSpace($ruleName)) {
            throw "R$($eGrave)gle de plateforme sans nom."
        }
        if ($rulesByName.ContainsKey($ruleName)) {
            throw "R$($eGrave)gle de plateforme dupliqu$($eAcute)e: $ruleName"
        }

        foreach ($requiredColumn in @("Comportement attendu", "Invariants", "Tests", "ADR")) {
            if ([string]::IsNullOrWhiteSpace($row[$requiredColumn])) {
                throw "Colonne $requiredColumn vide pour $ruleName."
            }
        }

        if ($row["Tests"] -match "(?i)\b(TBD|TODO|$($aGrave)\s+d$($eAcute)finir|a\s+definir)\b") {
            throw "Tests non ex$($eAcute)cutables pour $ruleName."
        }

        $rulesByName[$ruleName] = $row
    }

    foreach ($expectedRule in $expectedRules) {
        if (-not $rulesByName.ContainsKey($expectedRule.Name)) {
            throw "R$($eGrave)gle de plateforme attendue absente: $($expectedRule.Name)"
        }

        $row = $rulesByName[$expectedRule.Name]
        foreach ($adrId in $expectedRule.Adr) {
            Assert-M002AdrToken -Content $row["ADR"] -AdrId $adrId
        }

        if ($expectedRule.Name -eq "PLAT-007 - Observabilit$($eAcute) technique") {
            $observabilityRuleContent = "$($row["Comportement attendu"]) $($row["Invariants"])"
            foreach ($dimension in $requiredObservabilityDimensions) {
                if (-not $observabilityRuleContent.Contains($dimension)) {
                    throw "Dimension d'observabilit$($eAcute) absente: $dimension"
                }
            }
        }
    }

    foreach ($ruleName in $rulesByName.Keys) {
        if (@($expectedRules | Where-Object { $_.Name -eq $ruleName }).Count -eq 0) {
            throw "R$($eGrave)gle de plateforme non pr$($eAcute)vue par M-002: $ruleName"
        }
    }
}

function Assert-M002Spec {
    param(
        [Parameter(Mandatory = $true)]
        [string] $SpecPath
    )

    if (-not (Test-Path -LiteralPath $SpecPath -PathType Leaf)) {
        throw "Sp$($eAcute)cification M-002 absente: $SpecPath"
    }

    $content = Get-Content -Raw -Encoding UTF8 -LiteralPath $SpecPath
    $lines = @(Get-Content -Encoding UTF8 -LiteralPath $SpecPath)

    Assert-M002ForbiddenPatterns -Content $content

    foreach ($section in $requiredSections) {
        if ($lines -notcontains $section) {
            throw "Section obligatoire absente: $section"
        }
    }

    foreach ($marker in $requiredMarkers) {
        Assert-M002Contains `
            -Content $content `
            -Expected $marker `
            -Message "Marqueur BDD obligatoire absent: $marker"
    }

    foreach ($term in $requiredTerms) {
        Assert-M002Contains `
            -Content $content `
            -Expected $term `
            -Message "Terme du langage de plateforme absent: $term"
    }

    foreach ($command in $requiredCommands) {
        Assert-M002Contains `
            -Content $content `
            -Expected $command `
            -Message "Commande de validation absente: $command"
    }

    foreach ($adrId in $requiredAdrIds) {
        Assert-M002AdrToken -Content $content -AdrId $adrId
    }

    $placementRows = Read-M002MarkdownTable `
        -Lines $lines `
        -RequiredHeaders @("Capacit$($eAcute)", "H$($oCircumflex)te obligatoire", "R$($eGrave)gle") `
        -TableName "placements M-002"
    Assert-M002Placements -PlacementRows $placementRows

    $ruleRows = Read-M002MarkdownTable `
        -Lines $lines `
        -RequiredHeaders @("R$($eGrave)gle", "Comportement attendu", "Invariants", "Tests", "ADR") `
        -TableName "r$($eGrave)gles M-002"
    Assert-M002Rules -RuleRows $ruleRows
}

$resolvedPath = Resolve-M002RepositoryPath -InputPath $Path
Assert-M002Spec -SpecPath $resolvedPath

Write-Host "Sp$($eAcute)cification M-002 valide: $($expectedRules.Count) r$($eGrave)gle(s), $($expectedPlacements.Count) placement(s) contr$($oCircumflex)l$($eAcute)(s)."
