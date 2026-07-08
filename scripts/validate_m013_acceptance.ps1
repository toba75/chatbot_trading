param(
    [Parameter(Mandatory = $false)]
    [string] $ReportPath,

    [Parameter(Mandatory = $false)]
    [string] $MatrixPath,

    [Parameter(Mandatory = $false)]
    [string] $TestGatePath,

    [Parameter(Mandatory = $false)]
    [string] $LintGatePath
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$commandPrefix = "powershell -NoProfile -ExecutionPolicy Bypass -File .\"

$expectedCriteria = @{
    "V1-SP-QUALITE-DOCUMENTAIRE" = @{ Context = "SP"; Verdict = "différé" }
    "V1-KA-RECHERCHE-PAGES" = @{ Context = "KA"; Verdict = "différé" }
    "V1-EG-GOUVERNANCE-PREUVES" = @{ Context = "EG"; Verdict = "accepté" }
    "V1-RA-REPONSES-VERIFIEES" = @{ Context = "RA"; Verdict = "différé" }
    "V1-CV-CONVERSATION-PRODUIT" = @{ Context = "CV"; Verdict = "accepté" }
    "V1-SD-PARAMETRES-CALIBRABLES" = @{ Context = "SD"; Verdict = "bloquant" }
    "V1-LLM-CHECKPOINT-PRINCIPAL" = @{ Context = "LLM"; Verdict = "bloquant" }
    "V1-EX-BACKTESTS-REPRODUCTIBLES" = @{ Context = "EX"; Verdict = "accepté" }
}

$requiredEvidenceTopics = @(
    "décisions d'écarts",
    "régression",
    "sécurité réseau",
    "panne Spark",
    "sauvegarde/restauration",
    "rétention",
    "monitoring",
    "runbooks",
    "anti-patterns",
    "traceabilité",
    "gates finales"
)

$requiredFinalCommands = @(
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_v1_acceptance_report_acceptance.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_v1_acceptance_report_unit.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_acceptance.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_specification.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1"
)

$forbiddenSecretPatterns = @(
    "BEGIN PRIVATE KEY",
    "END PRIVATE KEY",
    "POSTGRES_PASSWORD\s*=",
    "QDRANT_API_KEY\s*=",
    "GEMMA_API_KEY\s*=",
    "VLLM_API_KEY\s*=",
    "Authorization:\s*Bearer",
    "SECRET_INTERDIT_M013"
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

function Assert-Contains {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content,

        [Parameter(Mandatory = $true)]
        [string] $Expected,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    Assert-Condition -Condition ($Content.Contains($Expected)) -Message $Message
}

function Assert-Command {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string] $Command,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    Assert-Condition -Condition (-not [string]::IsNullOrWhiteSpace($Command)) -Message $Message
    Assert-Condition -Condition ($Command.StartsWith($commandPrefix)) -Message $Message
}

function Assert-NoSecret {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content
    )

    foreach ($pattern in $forbiddenSecretPatterns) {
        if ([regex]::IsMatch($Content, $pattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)) {
            throw "Secret interdit dans le rapport d'acceptation V1 M-013: $pattern"
        }
    }
}

$resolvedReportPath = Resolve-RequiredPath -Path $ReportPath -DefaultRelativePath "docs/governance/m013_v1_acceptance_report.md" -Label "rapport acceptation"
$resolvedMatrixPath = Resolve-RequiredPath -Path $MatrixPath -DefaultRelativePath "docs/traceability/matrix.md" -Label "matrice"
$resolvedTestGatePath = Resolve-RequiredPath -Path $TestGatePath -DefaultRelativePath "scripts/test.ps1" -Label "gate test"
$resolvedLintGatePath = Resolve-RequiredPath -Path $LintGatePath -DefaultRelativePath "scripts/lint.ps1" -Label "gate lint"

$reportContent = (Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedReportPath).TrimStart([char] 0xFEFF)
$reportLines = @(Get-Content -Encoding UTF8 -LiteralPath $resolvedReportPath)
$matrixContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedMatrixPath
$testGateContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedTestGatePath
$lintGateContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedLintGatePath

Assert-NoSecret -Content $reportContent

foreach ($marker in @(
    "# Rapport d'acceptation V1 M-013",
    "M013-V1AcceptanceReport-1.0",
    "V1AcceptanceReportPolicy",
    "Given M-013 a livré décisions d'écarts",
    "When la gate finale V1 agrège les preuves",
    "Then le rapport d'acceptation publie un verdict par critère",
    "Verdict V1: non acceptée",
    "Acceptation V1 refusée",
    "acceptation",
    "non-acceptation",
    "différé",
    "Définition de terminé",
    "Gates finales",
    "ADR-010",
    "DDD-ADR-010",
    "DDD-ADR-011",
    "ADR: non requise"
)) {
    Assert-Contains -Content $reportContent -Expected $marker -Message "Marqueur rapport T-012 absent: $marker"
}

foreach ($topic in $requiredEvidenceTopics) {
    Assert-Contains -Content $reportContent -Expected $topic -Message "Preuve agrégée absente: $topic"
}

$criterionRows = Read-MarkdownTable `
    -Lines $reportLines `
    -RequiredHeaders @("Critère V1", "Contexte", "Verdict", "Preuve", "Commande de preuve", "ADR", "Impact final") `
    -TableName "verdicts par critère"

$criteriaById = @{}
$nonAcceptedRows = @()
$blockingRows = @()
$unknownCriteria = @()
$missingProofCriteria = @()
foreach ($row in $criterionRows) {
    $criterionId = $row["Critère V1"]
    Assert-Condition -Condition (-not $criteriaById.ContainsKey($criterionId)) -Message "critère V1 dupliqué: $criterionId"
    $criteriaById[$criterionId] = $row

    if (-not $expectedCriteria.ContainsKey($criterionId)) {
        $unknownCriteria += $criterionId
        continue
    }

    $expected = $expectedCriteria[$criterionId]
    Assert-Condition -Condition ($row["Contexte"] -eq $expected.Context) -Message "contexte invalide: $criterionId"
    if (($expected.Verdict -eq "bloquant") -and ($row["Verdict"] -eq "accepté")) {
        throw "écart bloquant accepté: $criterionId"
    }
    Assert-Condition -Condition ($row["Verdict"] -eq $expected.Verdict) -Message "verdict V1 invalide: $criterionId"
    Assert-Condition -Condition (-not [string]::IsNullOrWhiteSpace($row["Preuve"])) -Message "preuve par verdict absente: $criterionId"
    if (-not $row["Preuve"].Contains("docs/governance/m013_v1_gap_decisions.md")) {
        $missingProofCriteria += $criterionId
    }
    Assert-Command -Command $row["Commande de preuve"] -Message "commande finale absente: $criterionId"
    foreach ($adr in @("ADR-010", "DDD-ADR-010", "DDD-ADR-011")) {
        Assert-Contains -Content $row["ADR"] -Expected $adr -Message "ADR reliée absente: $criterionId"
    }

    if ($row["Verdict"] -in @("différé", "bloquant")) {
        $nonAcceptedRows += $row
    }
    if ($row["Verdict"] -eq "bloquant") {
        $blockingRows += $row
    }
}

foreach ($criterionId in $expectedCriteria.Keys) {
    Assert-Condition -Condition ($criteriaById.ContainsKey($criterionId)) -Message "critère V1 absent: $criterionId"
}
if ($unknownCriteria.Count -gt 0) {
    throw "critère V1 inconnu: $($unknownCriteria[0])"
}
if ($missingProofCriteria.Count -gt 0) {
    if ($missingProofCriteria -contains "V1-EG-GOUVERNANCE-PREUVES") {
        throw "preuve par verdict absente: V1-EG-GOUVERNANCE-PREUVES"
    }
    throw "preuve par verdict absente: $($missingProofCriteria[0])"
}

$nonAcceptedTableRows = Read-MarkdownTable `
    -Lines $reportLines `
    -RequiredHeaders @("Contexte", "Critère V1", "Statut", "Justification", "Action requise") `
    -TableName "écarts non acceptés"
$listedNonAcceptedCriteria = @($nonAcceptedTableRows | ForEach-Object { $_["Critère V1"] })
foreach ($row in $nonAcceptedRows) {
    Assert-Condition -Condition ($listedNonAcceptedCriteria -contains $row["Critère V1"]) -Message "écart non accepté absent: $($row["Contexte"])"
}

Assert-Condition -Condition ($nonAcceptedRows.Count -eq 5) -Message "nombre d'écarts non acceptés invalide"
Assert-Condition -Condition ($blockingRows.Count -eq 2) -Message "nombre d'écarts bloquants invalide"
Assert-Condition -Condition (-not $reportContent.Contains("Verdict V1: acceptée")) -Message "écart bloquant accepté dans le verdict final"

$gateRows = Read-MarkdownTable `
    -Lines $reportLines `
    -RequiredHeaders @("Gate", "Commande", "Verdict", "Preuve") `
    -TableName "gates finales"
foreach ($command in $requiredFinalCommands) {
    $commandLabel = $command.Substring($commandPrefix.Length).Replace("\", "/")
    Assert-Contains -Content $reportContent -Expected $command -Message "commande finale absente: $commandLabel"
}
foreach ($row in $gateRows) {
    Assert-Command -Command $row["Commande"] -Message "commande finale absente: $($row["Gate"])"
}

foreach ($marker in @(
    "REQ-M013-012",
    "tests/m013/validate_v1_acceptance_report_acceptance.ps1",
    "tests/m013/validate_v1_acceptance_report_unit.ps1",
    "scripts/validate_m013_acceptance.ps1",
    "docs/governance/m013_v1_acceptance_report.md",
    "app/evaluation/domain/v1_acceptance_report.py"
)) {
    Assert-Contains -Content $matrixContent -Expected $marker -Message "Traçabilité T-012 absente: $marker"
}

foreach ($marker in @(
    "scripts/validate_m013_acceptance.ps1",
    "tests/m013/validate_v1_acceptance_report_acceptance.ps1",
    "tests/m013/validate_v1_acceptance_report_unit.ps1"
)) {
    Assert-Contains -Content $testGateContent -Expected $marker -Message "Gate test sans rapport d'acceptation V1: $marker"
}
Assert-Contains -Content $lintGateContent -Expected "scripts/validate_m013_acceptance.ps1" -Message "Gate lint sans rapport d'acceptation V1."

Write-Host "Rapport d'acceptation V1 M-013 valide: $($criterionRows.Count) critère(s), $($nonAcceptedRows.Count) écart(s) non accepté(s), $($blockingRows.Count) écart(s) bloquant(s), verdict V1 non acceptée."
