param(
    [Parameter(Mandatory = $false)]
    [string] $PolicyPath,

    [Parameter(Mandatory = $false)]
    [string] $MatrixPath,

    [Parameter(Mandatory = $false)]
    [string] $AdrPath,

    [Parameter(Mandatory = $false)]
    [string] $AdrIndexPath,

    [Parameter(Mandatory = $false)]
    [string] $TestGatePath,

    [Parameter(Mandatory = $false)]
    [string] $LintGatePath
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)

$defaultPolicyPath = "docs/governance/m013_retention_policy.md"
$defaultMatrixPath = "docs/traceability/matrix.md"
$defaultAdrPath = "docs/adr/DDD-ADR-012-politique-retention-purge-administrative-v1.md"
$defaultAdrIndexPath = "docs/adr/index.md"
$defaultTestGatePath = "scripts/test.ps1"
$defaultLintGatePath = "scripts/lint.ps1"

$expectedCategories = @(
    "SP_ORIGINALS",
    "SP_CANONICAL_VERSIONS",
    "KA_REGENERABLE_PROJECTIONS",
    "EG_CLAIMS",
    "RA_VERIFIED_ANSWERS",
    "CV_CONVERSATIONS",
    "SD_STRATEGY_SNAPSHOTS",
    "EX_EXPERIMENT_RESULTS",
    "EV_GOVERNANCE_DECISIONS"
)

$expectedDurations = @{
    SP_ORIGINALS = "120"
    SP_CANONICAL_VERSIONS = "120"
    KA_REGENERABLE_PROJECTIONS = "3"
    EG_CLAIMS = "120"
    RA_VERIFIED_ANSWERS = "120"
    CV_CONVERSATIONS = "18"
    SD_STRATEGY_SNAPSHOTS = "120"
    EX_EXPERIMENT_RESULTS = "120"
    EV_GOVERNANCE_DECISIONS = "120"
}
$eAcute = [char] 0x00E9
$categoryHeader = "Cat$($eAcute)gorie"
$durationHeader = "Dur$($eAcute)e mois"
$operationHeader = "Op$($eAcute)ration autoris$($eAcute)e"

function Assert-M013Condition {
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

function Assert-M013Contains {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content,

        [Parameter(Mandatory = $true)]
        [string] $Expected,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    Assert-M013Condition -Condition ($Content.Contains($Expected)) -Message $Message
}

function Resolve-M013RequiredPath {
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

    Assert-M013Condition `
        -Condition ($resolvedPath.StartsWith($repositoryPrefix, [System.StringComparison]::OrdinalIgnoreCase)) `
        -Message "Chemin hors dépôt interdit ($Label): $resolvedPath"
    Assert-M013Condition `
        -Condition (Test-Path -LiteralPath $resolvedPath -PathType Leaf) `
        -Message "Fichier requis absent ($Label): $resolvedPath"

    return $resolvedPath
}

function Split-M013MarkdownRow {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Line
    )

    $trimmed = $Line.Trim()
    Assert-M013Condition -Condition ($trimmed.StartsWith("|") -and $trimmed.EndsWith("|")) -Message "Ligne de table Markdown invalide: $Line"
    return @($trimmed.Trim("|").Split("|") | ForEach-Object { $_.Trim() })
}

function Read-M013MarkdownTable {
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

        $headers = Split-M013MarkdownRow -Line $Lines[$index]
        if (($headers.Count -eq $RequiredHeaders.Count) -and (@(Compare-Object -ReferenceObject $RequiredHeaders -DifferenceObject $headers -SyncWindow 0).Count -eq 0)) {
            $headerIndex = $index
            break
        }
    }

    Assert-M013Condition -Condition ($headerIndex -ge 0) -Message "Table $TableName absente ou en-têtes invalides."
    Assert-M013Condition -Condition (($headerIndex + 1) -lt $Lines.Count) -Message "Séparateur absent pour la table $TableName."

    $separatorCells = Split-M013MarkdownRow -Line $Lines[$headerIndex + 1]
    Assert-M013Condition `
        -Condition (($separatorCells.Count -eq $RequiredHeaders.Count) -and (@($separatorCells | Where-Object { $_ -notmatch "^-{3,}$" }).Count -eq 0)) `
        -Message "Séparateur invalide pour la table $TableName."

    $rows = New-Object System.Collections.Generic.List[hashtable]
    for ($index = $headerIndex + 2; $index -lt $Lines.Count; $index++) {
        $line = $Lines[$index]
        if ($line -notmatch "^\|") {
            break
        }

        $cells = Split-M013MarkdownRow -Line $line
        Assert-M013Condition -Condition ($cells.Count -eq $RequiredHeaders.Count) -Message "Ligne $TableName invalide: $line"

        $row = @{}
        for ($cellIndex = 0; $cellIndex -lt $RequiredHeaders.Count; $cellIndex++) {
            $row[$RequiredHeaders[$cellIndex]] = $cells[$cellIndex]
        }
        $rows.Add($row)
    }

    Assert-M013Condition -Condition ($rows.Count -gt 0) -Message "Table $TableName sans ligne."
    return $rows.ToArray()
}

function Invoke-M013RetentionDomainCheck {
    . (Join-Path $repoRoot "scripts/require_python.ps1")
    $pythonExecutable = Get-RequiredPythonExecutable
    $pythonCode = @'
import sys

repo_root = sys.argv[1]
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from app.platform.retention import build_m013_retention_policy

policy = build_m013_retention_policy()
print(f"{len(policy.categories)} catégories durables contrôlées")
'@
    $pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_retention_validator_" + [System.Guid]::NewGuid().ToString("N") + ".py")
    Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $env:PYTHONIOENCODING = "utf-8"
        $output = & $pythonExecutable -B $pythonScriptPath $repoRoot 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
        Remove-Item -LiteralPath $pythonScriptPath -Force
    }

    if ($exitCode -ne 0) {
        throw "Politique de rétention M-013 invalide: $($output -join "`n")"
    }
}

function Assert-M013RetentionPolicyDocument {
    param(
        [Parameter(Mandatory = $true)]
        [string] $PolicyContent,

        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string[]] $PolicyLines
    )

    foreach ($marker in @(
        "# Politique V1",
        "purge administrative M-013",
        "M013-RetentionPolicy-1.0",
        "DDD-ADR-010",
        "DDD-ADR-012",
        "justification administrative",
        "audit",
        "Lecture compatible"
    )) {
        Assert-M013Contains -Content $PolicyContent -Expected $marker -Message "Marqueur politique rétention absent: $marker"
    }

    Assert-M013Condition `
        -Condition (-not $PolicyContent.Contains("Purge ordinaire autorisée")) `
        -Message "Purge ordinaire interdite"
    Assert-M013Condition `
        -Condition ($PolicyContent.Contains("Aucune purge ordinaire")) `
        -Message "Purge ordinaire interdite"
    Assert-M013Condition `
        -Condition ($PolicyContent.Contains("cascade interdite vers KA, EG, RA, SD et EX")) `
        -Message "Conversation sans cascade vers connaissances ou expériences"
    Assert-M013Condition `
        -Condition ($PolicyContent.Contains("powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\rebuild_knowledge_projection.ps1 -Source SP")) `
        -Message "Projection régénérable sans reconstruction"

    $categoryRows = Read-M013MarkdownTable `
        -Lines $PolicyLines `
        -RequiredHeaders @($categoryHeader, $durationHeader, "Contexte", "Artefact durable", $operationHeader, "Justification", "Audit", "Lecture compatible", "Garde-fou") `
        -TableName "catégories durables"

    $rowsByCategory = @{}
    foreach ($row in $categoryRows) {
        $category = $row[$categoryHeader]
        Assert-M013Condition -Condition (-not $rowsByCategory.ContainsKey($category)) -Message "Catégorie durable dupliquée: $category"
        $rowsByCategory[$category] = $row
    }

    foreach ($category in $expectedCategories) {
        Assert-M013Condition -Condition ($rowsByCategory.ContainsKey($category)) -Message "Catégorie durable absente: $category"
        $row = $rowsByCategory[$category]
        Assert-M013Condition -Condition (-not [string]::IsNullOrWhiteSpace($row[$durationHeader])) -Message "Durée de rétention absente"
        Assert-M013Condition -Condition ($row[$durationHeader] -eq $expectedDurations[$category]) -Message "Durée de rétention invalide pour ${category}: $($row[$durationHeader])"
        foreach ($column in @("Contexte", "Artefact durable", $operationHeader, "Justification", "Audit", "Lecture compatible", "Garde-fou")) {
            Assert-M013Condition -Condition (-not [string]::IsNullOrWhiteSpace($row[$column])) -Message "Colonne $column absente pour $category"
        }
    }

    Assert-M013Condition `
        -Condition ($rowsByCategory["CV_CONVERSATIONS"]["Garde-fou"].Contains("cascade interdite vers KA, EG, RA, SD et EX")) `
        -Message "Conversation sans cascade vers connaissances ou expériences"
    Assert-M013Condition `
        -Condition ($rowsByCategory["KA_REGENERABLE_PROJECTIONS"]["Garde-fou"].Contains("rebuild_knowledge_projection.ps1")) `
        -Message "Projection régénérable sans reconstruction"
}

function Assert-M013RetentionTraceability {
    param(
        [Parameter(Mandatory = $true)]
        [string] $MatrixContent,

        [Parameter(Mandatory = $true)]
        [string] $AdrContent,

        [Parameter(Mandatory = $true)]
        [string] $AdrIndexContent,

        [Parameter(Mandatory = $true)]
        [string] $TestGateContent,

        [Parameter(Mandatory = $true)]
        [string] $LintGateContent
    )

    foreach ($marker in @(
        "REQ-M013-008",
        "docs/tasks/milestone_013/0008_decider_retention_purge_administrative.md",
        "tests/m013/validate_retention_purge_acceptance.ps1",
        "tests/m013/validate_retention_purge_unit.ps1",
        "scripts/validate_m013_retention.ps1",
        "docs/governance/m013_retention_policy.md",
        "app/platform/retention.py",
        "DDD-ADR-012"
    )) {
        Assert-M013Contains -Content $MatrixContent -Expected $marker -Message "Traçabilité T-008 absente: $marker"
    }

    foreach ($marker in @(
        "# DDD-ADR-012",
        "Politique V1",
        "M013-RetentionPolicy-1.0",
        "120 mois",
        "18 mois",
        "3 mois",
        "sans modifier le sens de DDD-ADR-010"
    )) {
        Assert-M013Contains -Content $AdrContent -Expected $marker -Message "ADR rétention incomplète: $marker"
    }

    Assert-M013Contains -Content $AdrIndexContent -Expected "DDD-ADR-012" -Message "ADR index absente: DDD-ADR-012"
    Assert-M013Contains -Content $AdrIndexContent -Expected "Prochaine DDD-ADR: DDD-ADR-013" -Message "Prochaine DDD-ADR invalide."

    foreach ($marker in @(
        "scripts/validate_m013_retention.ps1",
        "tests/m013/validate_retention_purge_acceptance.ps1",
        "tests/m013/validate_retention_purge_unit.ps1"
    )) {
        Assert-M013Contains -Content $TestGateContent -Expected $marker -Message "Gate test sans rétention purge M-013: $marker"
    }

    Assert-M013Contains `
        -Content $LintGateContent `
        -Expected "scripts/validate_m013_retention.ps1" `
        -Message "Gate lint sans rétention purge M-013."
}

$resolvedPolicyPath = Resolve-M013RequiredPath -Path $PolicyPath -DefaultRelativePath $defaultPolicyPath -Label "politique rétention"
$resolvedMatrixPath = Resolve-M013RequiredPath -Path $MatrixPath -DefaultRelativePath $defaultMatrixPath -Label "matrice"
$resolvedAdrPath = Resolve-M013RequiredPath -Path $AdrPath -DefaultRelativePath $defaultAdrPath -Label "ADR rétention"
$resolvedAdrIndexPath = Resolve-M013RequiredPath -Path $AdrIndexPath -DefaultRelativePath $defaultAdrIndexPath -Label "index ADR"
$resolvedTestGatePath = Resolve-M013RequiredPath -Path $TestGatePath -DefaultRelativePath $defaultTestGatePath -Label "gate test"
$resolvedLintGatePath = Resolve-M013RequiredPath -Path $LintGatePath -DefaultRelativePath $defaultLintGatePath -Label "gate lint"

Invoke-M013RetentionDomainCheck

$policyContent = (Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedPolicyPath).TrimStart([char] 0xFEFF)
$policyLines = @(Get-Content -Encoding UTF8 -LiteralPath $resolvedPolicyPath)
if ($policyLines.Count -gt 0) {
    $policyLines[0] = $policyLines[0].TrimStart([char] 0xFEFF)
}
$matrixContent = (Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedMatrixPath).TrimStart([char] 0xFEFF)
$adrContent = (Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedAdrPath).TrimStart([char] 0xFEFF)
$adrIndexContent = (Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedAdrIndexPath).TrimStart([char] 0xFEFF)
$testGateContent = (Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedTestGatePath).TrimStart([char] 0xFEFF)
$lintGateContent = (Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedLintGatePath).TrimStart([char] 0xFEFF)

Assert-M013RetentionPolicyDocument -PolicyContent $policyContent -PolicyLines $policyLines
Assert-M013RetentionTraceability `
    -MatrixContent $matrixContent `
    -AdrContent $adrContent `
    -AdrIndexContent $adrIndexContent `
    -TestGateContent $testGateContent `
    -LintGateContent $lintGateContent

Write-Host "R$($eAcute)tention purge M-013 valide: $($expectedCategories.Count) cat$($eAcute)gories durables, aucune purge ordinaire, conversation sans cascade, projection r$($eAcute)g$($eAcute)n$($eAcute)rable reconstruite, DDD-ADR-012."
