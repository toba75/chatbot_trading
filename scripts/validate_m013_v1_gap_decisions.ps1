param(
    [Parameter(Mandatory = $false)]
    [string] $DecisionsPath,

    [Parameter(Mandatory = $false)]
    [string] $SourceGapReportPath,

    [Parameter(Mandatory = $false)]
    [string] $MatrixPath
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

$expectedSourceGaps = @{
    SP = @{ Status = "différé"; Benchmark = "RBRUN-M012-DOCUMENT-ROUTES-0001"; Calibration = "DEC-M012-SP-DEFERRED" }
    KA = @{ Status = "différé"; Benchmark = "KSRUN-M012-KNOWLEDGE-0001"; Calibration = "DEC-M012-KA-REJECTED" }
    EG = @{ Status = "satisfait"; Benchmark = "EGRUN-M012-0001"; Calibration = "DEC-M012-EG-ACCEPTED" }
    RA = @{ Status = "différé"; Benchmark = "VARUN-M012-VERIFIED-ANSWERS-0001"; Calibration = "DEC-M012-RA-DEFERRED" }
    CV = @{ Status = "satisfait"; Benchmark = "CVRUN-M012-CRITERIA-0001"; Calibration = "DEC-M012-CV-ACCEPTED" }
    SD = @{ Status = "bloquant"; Benchmark = "SBRUN-M012-STRATEGY-BACKTEST-0001"; Calibration = "DEC-M012-SD-REJECTED" }
    LLM = @{ Status = "bloquant"; Benchmark = "LLMRUN-M012-REAL-PATH-0001"; Calibration = "DEC-M012-LLM-REJECTED" }
    EX = @{ Status = "satisfait"; Benchmark = "SBRUN-M012-EXPERIMENTS-0001"; Calibration = "DEC-M012-EX-ACCEPTED" }
}

$expectedContexts = @("SP", "KA", "EG", "RA", "CV", "SD", "LLM", "EX")
$allowedSourceStatuses = @("satisfait", "bloquant", "accepté", "différé")
$allowedDecisionStatuses = @("corrigé", "accepté", "différé", "bloquant")
$commandPrefix = "powershell -NoProfile -ExecutionPolicy Bypass -File .\"

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

function Resolve-RequiredPath {
    param(
        [Parameter(Mandatory = $false)]
        [AllowEmptyString()]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [string] $DefaultRelativePath,

        [Parameter(Mandatory = $true)]
        [string] $Label
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        $candidatePath = Join-Path $repoRoot $DefaultRelativePath
    }
    elseif ([System.IO.Path]::IsPathRooted($Path)) {
        $candidatePath = $Path
    }
    else {
        $candidatePath = Join-Path $repoRoot $Path
    }

    $resolvedRepositoryRoot = [System.IO.Path]::GetFullPath($repoRoot)
    $resolvedPath = [System.IO.Path]::GetFullPath($candidatePath)
    $repositoryPrefix = $resolvedRepositoryRoot.TrimEnd("\", "/") + [System.IO.Path]::DirectorySeparatorChar
    Assert-Condition `
        -Condition ($resolvedPath.StartsWith($repositoryPrefix, [System.StringComparison]::OrdinalIgnoreCase)) `
        -Message "Chemin hors dépôt interdit ($Label): $resolvedPath"
    Assert-Condition `
        -Condition (Test-Path -LiteralPath $resolvedPath -PathType Leaf) `
        -Message "Fichier requis absent ($Label): $resolvedPath"
    return $resolvedPath
}

function Split-MarkdownRow {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Line
    )

    $trimmed = $Line.Trim()
    Assert-Condition -Condition ($trimmed.StartsWith("|") -and $trimmed.EndsWith("|")) -Message "Ligne de table Markdown invalide: $Line"
    return @($trimmed.Trim("|").Split("|") | ForEach-Object { $_.Trim() })
}

function Read-MarkdownTable {
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
        $headers = Split-MarkdownRow -Line $Lines[$index]
        if (($headers.Count -eq $RequiredHeaders.Count) -and (@(Compare-Object -ReferenceObject $RequiredHeaders -DifferenceObject $headers -SyncWindow 0).Count -eq 0)) {
            $headerIndex = $index
            break
        }
    }

    Assert-Condition -Condition ($headerIndex -ge 0) -Message "Table $TableName absente ou en-têtes invalides."
    Assert-Condition -Condition (($headerIndex + 1) -lt $Lines.Count) -Message "Séparateur absent pour la table $TableName."

    $separatorCells = Split-MarkdownRow -Line $Lines[$headerIndex + 1]
    Assert-Condition `
        -Condition (($separatorCells.Count -eq $RequiredHeaders.Count) -and (@($separatorCells | Where-Object { $_ -notmatch "^-{3,}$" }).Count -eq 0)) `
        -Message "Séparateur invalide pour la table $TableName."

    $rows = New-Object System.Collections.Generic.List[hashtable]
    for ($index = $headerIndex + 2; $index -lt $Lines.Count; $index++) {
        $line = $Lines[$index]
        if ($line -notmatch "^\|") {
            break
        }

        $cells = Split-MarkdownRow -Line $line
        Assert-Condition -Condition ($cells.Count -eq $RequiredHeaders.Count) -Message "Ligne $TableName invalide: $line"

        $row = @{}
        for ($cellIndex = 0; $cellIndex -lt $RequiredHeaders.Count; $cellIndex++) {
            $row[$RequiredHeaders[$cellIndex]] = $cells[$cellIndex]
        }
        $rows.Add($row)
    }

    Assert-Condition -Condition ($rows.Count -gt 0) -Message "Table $TableName sans ligne."
    return $rows.ToArray()
}

function ConvertTo-SourceGapMap {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string[]] $Lines
    )

    $headers = @("Contexte", "Statut", "Critère V1", "Benchmark source", "Corpus", "Décision liée", "Commande de preuve", "Justification")
    $rows = Read-MarkdownTable -Lines $Lines -RequiredHeaders $headers -TableName "écarts source M-012"
    $sourceByContext = @{}
    foreach ($row in $rows) {
        $context = $row["Contexte"]
        if ($expectedContexts -contains $context) {
            $sourceByContext[$context] = $row
        }
    }
    return $sourceByContext
}

function Assert-Command {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Command,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    Assert-Condition -Condition (-not [string]::IsNullOrWhiteSpace($Command)) -Message $Message
    Assert-Condition -Condition ($Command.StartsWith($commandPrefix)) -Message $Message
}

function Normalize-CodeCell {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Value
    )

    return $Value.Trim().Trim([char] 0x0060)
}

function Assert-MatrixTraceability {
    param(
        [Parameter(Mandatory = $true)]
        [string] $MatrixContent
    )

    foreach ($marker in @(
        "REQ-M013-003",
        "tests/m013/validate_v1_gap_decisions_acceptance.ps1",
        "tests/m013/validate_v1_gap_decisions_unit.ps1",
        "scripts/validate_m013_v1_gap_decisions.ps1",
        "docs/governance/m013_v1_gap_decisions.md",
        "app/evaluation/domain/v1_gap_decisions.py"
    )) {
        Assert-Condition -Condition ($MatrixContent.Contains($marker)) -Message "Traçabilité T-003 absente: $marker"
    }
}

$resolvedDecisionsPath = Resolve-RequiredPath -Path $DecisionsPath -DefaultRelativePath "docs/governance/m013_v1_gap_decisions.md" -Label "decisions"
$resolvedSourceGapReportPath = Resolve-RequiredPath -Path $SourceGapReportPath -DefaultRelativePath "docs/governance/m012_v1_gap_report.md" -Label "source gap report"
$resolvedMatrixPath = Resolve-RequiredPath -Path $MatrixPath -DefaultRelativePath "docs/traceability/matrix.md" -Label "matrix"

$decisionsContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedDecisionsPath
$decisionsLines = @(Get-Content -Encoding UTF8 -LiteralPath $resolvedDecisionsPath)
$sourceGapLines = @(Get-Content -Encoding UTF8 -LiteralPath $resolvedSourceGapReportPath)
$matrixContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedMatrixPath

foreach ($marker in @(
    "# Décisions d'écarts V1 M-013",
    "V1GapDecisionPolicy",
    "V1GapDecision",
    "docs/governance/m012_v1_gap_report.md",
    "M-013 ne réécrit pas les benchmarks M-012",
    "V1AcceptanceReport"
)) {
    Assert-Condition -Condition ($decisionsContent.Contains($marker)) -Message "Marqueur T-003 absent: $marker"
}

$sourceByContext = ConvertTo-SourceGapMap -Lines $sourceGapLines
$decisionHeaders = @(
    "Contexte",
    "Statut M-012",
    "Décision M-013",
    "Critère V1",
    "Benchmark source",
    "Décision calibration",
    "Commande de preuve",
    "Commande de correction",
    "Justification de non-acceptation",
    "Impact acceptation V1"
)
$decisionRows = Read-MarkdownTable -Lines $decisionsLines -RequiredHeaders $decisionHeaders -TableName "décisions V1"
$nonAcceptedRows = Read-MarkdownTable `
    -Lines $decisionsLines `
    -RequiredHeaders @("Contexte", "Décision M-013", "Justification", "Transmission V1AcceptanceReport") `
    -TableName "écarts non acceptés"

$contextCounts = @{}
foreach ($row in $decisionRows) {
    $context = $row["Contexte"]
    if (-not $contextCounts.ContainsKey($context)) {
        $contextCounts[$context] = 0
    }
    $contextCounts[$context] += 1
    if ($contextCounts[$context] -gt 1) {
        throw "écart V1 dupliqué"
    }
}

$decisionsByContext = @{}
foreach ($row in $decisionRows) {
    $context = $row["Contexte"]
    Assert-Condition -Condition ($expectedContexts -contains $context) -Message "Contexte V1 inconnu: $context"
    Assert-Condition -Condition (-not $decisionsByContext.ContainsKey($context)) -Message "écart V1 dupliqué"
    $decisionsByContext[$context] = $row

    $sourceStatus = $row["Statut M-012"]
    $decisionStatus = $row["Décision M-013"]
    Assert-Condition -Condition ($allowedSourceStatuses -contains $sourceStatus) -Message "statut M-012 inconnu"
    Assert-Condition -Condition ($allowedDecisionStatuses -contains $decisionStatus) -Message "décision V1 inconnue"
    Assert-Condition -Condition (-not [string]::IsNullOrWhiteSpace($row["Critère V1"])) -Message "critère V1 absent"
    Assert-Condition -Condition (-not [string]::IsNullOrWhiteSpace($row["Benchmark source"])) -Message "benchmark source manque"
    Assert-Command -Command $row["Commande de preuve"] -Message "décision sans preuve"

    if ($decisionStatus -eq "corrigé") {
        Assert-Command -Command $row["Commande de correction"] -Message "correction sans commande"
    }
    if (($sourceStatus -eq "bloquant") -and ($decisionStatus -eq "accepté")) {
        throw "écart bloquant accepté"
    }
    if (($decisionStatus -eq "différé") -and [string]::IsNullOrWhiteSpace($row["Justification de non-acceptation"])) {
        throw "écart différé sans justification"
    }
    if (($decisionStatus -eq "bloquant") -and [string]::IsNullOrWhiteSpace($row["Justification de non-acceptation"])) {
        throw "écart bloquant sans justification"
    }

    Assert-Condition -Condition ($sourceByContext.ContainsKey($context)) -Message "écart M-012 absent: $context"
    $source = $sourceByContext[$context]
    if (
        ($source["Statut"] -ne $sourceStatus) -or
        ((Normalize-CodeCell -Value $source["Benchmark source"]) -ne $row["Benchmark source"]) -or
        ((Normalize-CodeCell -Value $source["Décision liée"]) -ne $row["Décision calibration"])
    ) {
        throw "décision contredit M-012"
    }
}

foreach ($context in $expectedContexts) {
    Assert-Condition -Condition ($decisionsByContext.ContainsKey($context)) -Message "écart M-012 absent: $context"
    $expected = $expectedSourceGaps[$context]
    $actual = $decisionsByContext[$context]
    Assert-Condition -Condition ($actual["Statut M-012"] -eq $expected.Status) -Message "décision contredit M-012"
    Assert-Condition -Condition ($actual["Benchmark source"] -eq $expected.Benchmark) -Message "décision contredit M-012"
    Assert-Condition -Condition ($actual["Décision calibration"] -eq $expected.Calibration) -Message "décision contredit M-012"
}

$nonAcceptedContexts = @(
    $decisionRows |
        Where-Object { @("différé", "bloquant") -contains $_["Décision M-013"] } |
        ForEach-Object { $_["Contexte"] }
)
$listedNonAcceptedContexts = @($nonAcceptedRows | ForEach-Object { $_["Contexte"] })
foreach ($context in $nonAcceptedContexts) {
    Assert-Condition `
        -Condition ($listedNonAcceptedContexts -contains $context) `
        -Message "rapport d'acceptation ignore un écart non accepté: $context"
}

$hasBlockingGap = @($decisionRows | Where-Object { $_["Décision M-013"] -eq "bloquant" }).Count -gt 0
Assert-Condition -Condition $hasBlockingGap -Message "écart bloquant absent"
Assert-Condition -Condition ($decisionsContent.Contains("Acceptation V1 refusée")) -Message "acceptation V1 refusée absente"
Assert-MatrixTraceability -MatrixContent $matrixContent

Write-Host "Décisions d'écarts V1 M-013 valides: $($decisionRows.Count) écart(s), $($nonAcceptedContexts.Count) écart(s) non accepté(s), acceptation V1 refusée."
