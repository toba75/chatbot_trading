param(
    [Parameter(Mandatory = $false)]
    [string] $Path
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$definitionPath = $Path

$eAcute = [char] 0x00E9
$eGrave = [char] 0x00E8
$aGrave = [char] 0x00E0
$cCedilla = [char] 0x00E7
$oCircumflex = [char] 0x00F4

$scenarioHeading = "Sc$($eAcute)nario BDD"
$scopeHeading = "Port$($eAcute)e transverse"
$proofHeading = "Crit$($eGrave)res de preuve"
$adrHeading = "ADR et d$($eAcute)cisions structurantes"
$traceabilityHeading = "Tra$($cCedilla)abilit$($eAcute)"
$finalValidationHeading = "Validation finale"
$closureHeading = "Refus de cl$($oCircumflex)ture"
$traceabilityGate = "Tra$($cCedilla)abilit$($eAcute)"

if ($PSBoundParameters.ContainsKey("Path") -and [string]::IsNullOrWhiteSpace($definitionPath)) {
    throw "Chemin de définition d'achèvement vide."
}

if (-not $PSBoundParameters.ContainsKey("Path")) {
    $definitionPath = Join-Path $repoRoot "docs/governance/definition_of_done.md"
}
elseif (-not [System.IO.Path]::IsPathRooted($definitionPath)) {
    $definitionPath = Join-Path $repoRoot $definitionPath
}

$requiredHeadings = @(
    $scenarioHeading,
    $scopeHeading,
    "Gates obligatoires",
    $proofHeading,
    $adrHeading,
    $traceabilityHeading,
    $finalValidationHeading,
    $closureHeading
)

$requiredGateHeaders = @(
    "Gate",
    "Preuve requise",
    "Refus explicite"
)

$requiredGates = @(
    "BDD",
    "ATDD",
    "TDD",
    "Commit RED",
    "Commit GREEN",
    "ADR",
    $traceabilityGate,
    "Tests",
    "Lint",
    "Frontière UI/API"
)

$requiredMarkers = @(
    "docs/traceability/matrix.md",
    "docs/adr/",
    "scripts/test.ps1",
    "scripts/lint.ps1",
    "ADR-018",
    "orchestrator-api",
    "absent ou non câblé au cas d'usage réel",
    "mock",
    "stub",
    "fake",
    "fallback"
)

function Assert-Condition {
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

function Split-MarkdownRow {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Line
    )

    return @($Line.Trim().Trim("|").Split("|") | ForEach-Object { $_.Trim() })
}

function Get-HeadingIndexes {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string[]] $Lines
    )

    $indexes = @{}

    for ($index = 0; $index -lt $Lines.Count; $index++) {
        $match = [regex]::Match($Lines[$index], "^## (?<heading>.+?)\s*$")
        if (-not $match.Success) {
            continue
        }

        $heading = $match.Groups["heading"].Value

        Assert-Condition `
            -Condition (-not $indexes.ContainsKey($heading)) `
            -Message "Section dupliqu$($eAcute)e dans la d$($eAcute)finition d'ach$($eGrave)vement: $heading"

        $indexes[$heading] = $index
    }

    return $indexes
}

function Get-SectionBody {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string[]] $Lines,

        [Parameter(Mandatory = $true)]
        [int] $HeadingIndex
    )

    $body = New-Object System.Collections.Generic.List[string]

    for ($index = $HeadingIndex + 1; $index -lt $Lines.Count; $index++) {
        if ($Lines[$index] -match "^##\s+") {
            break
        }

        $body.Add($Lines[$index])
    }

    return @($body)
}

function Assert-SectionIsNotEmpty {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string[]] $Lines,

        [Parameter(Mandatory = $true)]
        [hashtable] $HeadingIndexes,

        [Parameter(Mandatory = $true)]
        [string] $Heading
    )

    $body = Get-SectionBody -Lines $Lines -HeadingIndex $HeadingIndexes[$Heading]
    $meaningfulLines = @($body | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })

    Assert-Condition `
        -Condition ($meaningfulLines.Count -gt 0) `
        -Message "Section obligatoire vide dans la d$($eAcute)finition d'ach$($eGrave)vement: $Heading"
}

function Assert-Scenario {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string[]] $Lines,

        [Parameter(Mandatory = $true)]
        [hashtable] $HeadingIndexes
    )

    $body = Get-SectionBody -Lines $Lines -HeadingIndex $HeadingIndexes[$scenarioHeading]
    $text = $body -join "`n"

    Assert-Condition `
        -Condition ($text -match "(?m)^\s*-\s+Given\s+\S.*$") `
        -Message "Sc$($eAcute)nario BDD incomplet: Given absent."

    Assert-Condition `
        -Condition ($text -match "(?m)^\s*-\s+When\s+\S.*$") `
        -Message "Sc$($eAcute)nario BDD incomplet: When absent."

    Assert-Condition `
        -Condition ($text -match "(?m)^\s*-\s+Then\s+\S.*$") `
        -Message "Sc$($eAcute)nario BDD incomplet: Then absent."
}

function Assert-GatesTable {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string[]] $Lines,

        [Parameter(Mandatory = $true)]
        [hashtable] $HeadingIndexes
    )

    $body = Get-SectionBody -Lines $Lines -HeadingIndex $HeadingIndexes["Gates obligatoires"]
    $headerIndex = -1

    for ($index = 0; $index -lt $body.Count; $index++) {
        if ($body[$index] -match "^\|\s*Gate\s*\|") {
            $headerIndex = $index
            break
        }
    }

    Assert-Condition `
        -Condition ($headerIndex -ge 0) `
        -Message "Table des gates obligatoire absente."

    $headers = Split-MarkdownRow -Line $body[$headerIndex]

    Assert-Condition `
        -Condition ($headers.Count -eq $requiredGateHeaders.Count) `
        -Message "Nombre de colonnes invalide dans la table des gates."

    for ($index = 0; $index -lt $requiredGateHeaders.Count; $index++) {
        Assert-Condition `
            -Condition ($headers[$index] -eq $requiredGateHeaders[$index]) `
            -Message "Colonne invalide dans la table des gates. Attendu: $($requiredGateHeaders[$index]). Obtenu: $($headers[$index])"
    }

    Assert-Condition `
        -Condition (($headerIndex + 1) -lt $body.Count) `
        -Message "S$($eAcute)parateur de table des gates absent."

    $separatorCells = Split-MarkdownRow -Line $body[$headerIndex + 1]
    Assert-Condition `
        -Condition (($separatorCells.Count -eq $requiredGateHeaders.Count) -and (@($separatorCells | Where-Object { $_ -notmatch "^-{3,}$" }).Count -eq 0)) `
        -Message "S$($eAcute)parateur de table des gates invalide."

    $allowedGates = New-Object System.Collections.Generic.HashSet[string]
    foreach ($gate in $requiredGates) {
        [void] $allowedGates.Add($gate)
    }

    $observedGates = New-Object System.Collections.Generic.HashSet[string]

    for ($index = $headerIndex + 2; $index -lt $body.Count; $index++) {
        $line = $body[$index]

        if ($line -notmatch "^\|") {
            break
        }

        $cells = Split-MarkdownRow -Line $line

        Assert-Condition `
            -Condition ($cells.Count -eq $requiredGateHeaders.Count) `
            -Message "Ligne de gate avec nombre de cellules invalide: $line"

        for ($cellIndex = 0; $cellIndex -lt $cells.Count; $cellIndex++) {
            Assert-Condition `
                -Condition (-not [string]::IsNullOrWhiteSpace($cells[$cellIndex])) `
                -Message "Cellule vide dans la table des gates, colonne $($requiredGateHeaders[$cellIndex])."
        }

        $gate = $cells[0]

        Assert-Condition `
            -Condition ($allowedGates.Contains($gate)) `
            -Message "Gate non autoris$($eAcute)e dans la d$($eAcute)finition d'ach$($eGrave)vement: $gate"

        Assert-Condition `
            -Condition ($observedGates.Add($gate)) `
            -Message "Gate dupliqu$($eAcute)e dans la d$($eAcute)finition d'ach$($eGrave)vement: $gate"
    }

    foreach ($gate in $requiredGates) {
        Assert-Condition `
            -Condition ($observedGates.Contains($gate)) `
            -Message "Gate obligatoire absente dans la d$($eAcute)finition d'ach$($eGrave)vement: $gate"
    }
}

Assert-Condition `
    -Condition (Test-Path -LiteralPath $definitionPath -PathType Leaf) `
    -Message "D$($eAcute)finition d'ach$($eGrave)vement absente: $definitionPath"

$content = Get-Content -Raw -Encoding UTF8 -LiteralPath $definitionPath
$lines = @($content -split "`r?`n")
$headingIndexes = Get-HeadingIndexes -Lines $lines

foreach ($heading in $requiredHeadings) {
    Assert-Condition `
        -Condition ($headingIndexes.ContainsKey($heading)) `
        -Message "Section obligatoire absente dans la d$($eAcute)finition d'ach$($eGrave)vement: ## $heading"

    Assert-SectionIsNotEmpty -Lines $lines -HeadingIndexes $headingIndexes -Heading $heading
}

Assert-Scenario -Lines $lines -HeadingIndexes $headingIndexes
Assert-GatesTable -Lines $lines -HeadingIndexes $headingIndexes

foreach ($marker in $requiredMarkers) {
    Assert-Condition `
        -Condition ($content.Contains($marker)) `
        -Message "Marqueur obligatoire absent dans la d$($eAcute)finition d'ach$($eGrave)vement: $marker"
}

Write-Host "D$($eAcute)finition d'ach$($eGrave)vement transverse valide: $($requiredGates.Count) gates contr$($oCircumflex)l$($eAcute)es."
