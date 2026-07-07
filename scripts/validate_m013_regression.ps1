param(
    [Parameter(Mandatory = $false)]
    [string] $SuitePath,

    [Parameter(Mandatory = $false)]
    [string] $DecisionsPath,

    [Parameter(Mandatory = $false)]
    [string] $SourceGapReportPath,

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
    "V1-SP-QUALITE-DOCUMENTAIRE" = @{ Context = "SP"; Verdict = "NON_ACCEPTED_GAP" }
    "V1-KA-RECHERCHE-PAGES" = @{ Context = "KA"; Verdict = "NON_ACCEPTED_GAP" }
    "V1-EG-GOUVERNANCE-PREUVES" = @{ Context = "EG"; Verdict = "GREEN" }
    "V1-RA-REPONSES-VERIFIEES" = @{ Context = "RA"; Verdict = "NON_ACCEPTED_GAP" }
    "V1-CV-CONVERSATION-PRODUIT" = @{ Context = "CV"; Verdict = "GREEN" }
    "V1-SD-PARAMETRES-CALIBRABLES" = @{ Context = "SD"; Verdict = "NON_ACCEPTED_GAP" }
    "V1-LLM-CHECKPOINT-PRINCIPAL" = @{ Context = "LLM"; Verdict = "NON_ACCEPTED_GAP" }
    "V1-EX-BACKTESTS-REPRODUCTIBLES" = @{ Context = "EX"; Verdict = "GREEN" }
}

$expectedContexts = @("SP", "KA", "EG", "RA", "CV", "SD", "LLM", "EX")
$allowedVerdicts = @("GREEN", "NON_ACCEPTED_GAP")
$defaultForbiddenSensitiveMarkers = @(
    "PROMPT_COMPLET_INTERDIT_M013",
    "DOCUMENT_COMPLET_INTERDIT_M013",
    "PREUVE_COMPLETE_INTERDITE_M013",
    "REPONSE_COMPLETE_INTERDITE_M013",
    "SECRET_INTERDIT_M013",
    "MARKET_DATA_COMPLETE_FORBIDDEN_M013"
)
$forbiddenInternalPatterns = @(
    "in_memory",
    "internal",
    "repository",
    "qdrant",
    "collection",
    "database",
    "registry_table",
    "raw_.*payload",
    "storage"
)
$forbiddenCommandPatterns = @(
    "Set-Content",
    "Add-Content",
    "Out-File",
    "Remove-Item",
    "Move-Item",
    "New-Item",
    ">>",
    ">"
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

function Resolve-ArtifactPath {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [string] $Label
    )

    Assert-Condition -Condition (-not [string]::IsNullOrWhiteSpace($Path)) -Message "Chemin de preuve absent ($Label)"
    return Resolve-RequiredPath -Path $Path -DefaultRelativePath $Path -Label $Label
}

function Assert-NoSensitivePayload {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content,

        [Parameter(Mandatory = $true)]
        [string[]] $ForbiddenMarkers
    )

    foreach ($marker in $ForbiddenMarkers) {
        if ($Content.Contains($marker)) {
            throw "Payload sensible M-013 exposé: $marker"
        }
    }
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
        $headersMatch = $headers.Count -eq $RequiredHeaders.Count
        if ($headersMatch) {
            for ($headerCellIndex = 0; $headerCellIndex -lt $RequiredHeaders.Count; $headerCellIndex++) {
                if ($headers[$headerCellIndex] -ne $RequiredHeaders[$headerCellIndex]) {
                    $headersMatch = $false
                    break
                }
            }
        }
        if ($headersMatch) {
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

function Assert-Command {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string] $Command,

        [Parameter(Mandatory = $true)]
        [string] $Label
    )

    Assert-Condition -Condition (-not [string]::IsNullOrWhiteSpace($Command)) -Message "commande manquante: $Label"
    Assert-Condition -Condition ($Command.StartsWith($commandPrefix)) -Message "commande invalide: $Label"
    foreach ($pattern in $forbiddenCommandPatterns) {
        if ($Command -match $pattern) {
            throw "commande mutante interdite: $Label"
        }
    }
}

function Assert-ArtifactMarker {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [string] $Marker,

        [Parameter(Mandatory = $true)]
        [string] $FailureMessage
    )

    $resolvedPath = Resolve-ArtifactPath -Path $Path -Label $FailureMessage
    $content = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedPath
    Assert-Condition -Condition ($content.Contains($Marker)) -Message $FailureMessage
    return $content
}

function Assert-PublicContractRef {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Reference
    )

    Assert-Condition -Condition (-not [string]::IsNullOrWhiteSpace($Reference)) -Message "contrat public vide"
    foreach ($pattern in $forbiddenInternalPatterns) {
        if ($Reference -match $pattern) {
            throw "dépendance directe à un stockage interne: $Reference"
        }
    }
}

$resolvedSuitePath = Resolve-RequiredPath -Path $SuitePath -DefaultRelativePath "docs/evaluation/m013/v1_regression_suite.json" -Label "suite regression"
$resolvedDecisionsPath = Resolve-RequiredPath -Path $DecisionsPath -DefaultRelativePath "docs/governance/m013_v1_gap_decisions.md" -Label "decisions"
$resolvedSourceGapReportPath = Resolve-RequiredPath -Path $SourceGapReportPath -DefaultRelativePath "docs/governance/m012_v1_gap_report.md" -Label "source gap report"
$resolvedMatrixPath = Resolve-RequiredPath -Path $MatrixPath -DefaultRelativePath "docs/traceability/matrix.md" -Label "matrix"
$resolvedTestGatePath = Resolve-RequiredPath -Path $TestGatePath -DefaultRelativePath "scripts/test.ps1" -Label "test gate"
$resolvedLintGatePath = Resolve-RequiredPath -Path $LintGatePath -DefaultRelativePath "scripts/lint.ps1" -Label "lint gate"

$suiteContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedSuitePath
Assert-NoSensitivePayload -Content $suiteContent -ForbiddenMarkers $defaultForbiddenSensitiveMarkers

try {
    $suite = $suiteContent | ConvertFrom-Json
}
catch {
    throw "Fixture de suite de régression V1 invalide: $($_.Exception.Message)"
}

$suiteForbiddenMarkers = @($defaultForbiddenSensitiveMarkers)
if ($suite.sensitive_payload_forbidden_markers) {
    $suiteForbiddenMarkers = @($suite.sensitive_payload_forbidden_markers | ForEach-Object { [string] $_ })
}
Assert-NoSensitivePayload -Content $suiteContent -ForbiddenMarkers $suiteForbiddenMarkers

foreach ($requiredMarker in @(
    "M013-V1-REGRESSION-SUITE-0001",
    "M013-RegressionSuitePolicy-1.0",
    "CORPUS-M012-PILOTE-0001"
)) {
    Assert-Condition -Condition ($suiteContent.Contains($requiredMarker)) -Message "Marqueur de suite absent: $requiredMarker"
}

$decisionsContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedDecisionsPath
$sourceGapReportContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedSourceGapReportPath
$matrixContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedMatrixPath
$testGateContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedTestGatePath
$lintGateContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedLintGatePath

foreach ($contentToScan in @($decisionsContent, $sourceGapReportContent, $matrixContent, $testGateContent, $lintGateContent)) {
    Assert-NoSensitivePayload -Content $contentToScan -ForbiddenMarkers $suiteForbiddenMarkers
}

$decisionRows = Read-MarkdownTable `
    -Lines @(Get-Content -Encoding UTF8 -LiteralPath $resolvedDecisionsPath) `
    -RequiredHeaders @(
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
    ) `
    -TableName "décisions V1"

$decisionsByContext = @{}
$nonAcceptedContexts = New-Object System.Collections.Generic.List[string]
foreach ($row in $decisionRows) {
    $context = $row["Contexte"]
    Assert-Condition -Condition ($expectedContexts -contains $context) -Message "décision V1 inconnue: $context"
    Assert-Condition -Condition (-not $decisionsByContext.ContainsKey($context)) -Message "décision V1 dupliquée: $context"
    $decisionsByContext[$context] = $row
    if (@("différé", "bloquant") -contains $row["Décision M-013"]) {
        $nonAcceptedContexts.Add($context)
    }
}

$fixturesById = @{}
foreach ($fixture in @($suite.fixtures)) {
    $fixtureId = [string] $fixture.fixture_id
    Assert-Condition -Condition (-not [string]::IsNullOrWhiteSpace($fixtureId)) -Message "fixture sans identifiant"
    Assert-Condition -Condition (-not $fixturesById.ContainsKey($fixtureId)) -Message "fixture dupliquée: $fixtureId"
    $fixturesById[$fixtureId] = $fixture
    $fixtureContent = Assert-ArtifactMarker `
        -Path ([string] $fixture.artifact_path) `
        -Marker ([string] $fixture.marker) `
        -FailureMessage "fixture sans preuve: $fixtureId"
    Assert-NoSensitivePayload -Content $fixtureContent -ForbiddenMarkers $suiteForbiddenMarkers
}

$criteriaById = @{}
foreach ($criterion in @($suite.criteria)) {
    $criterionId = [string] $criterion.criterion_id
    Assert-Condition -Condition (-not [string]::IsNullOrWhiteSpace($criterionId)) -Message "critère sans identifiant"
    Assert-Condition -Condition (-not $criteriaById.ContainsKey($criterionId)) -Message "critère dupliqué: $criterionId"
    $criteriaById[$criterionId] = $criterion
}

foreach ($criterionId in $expectedCriteria.Keys) {
    Assert-Condition -Condition ($criteriaById.ContainsKey($criterionId)) -Message "critère non couvert: $criterionId"
}
Assert-Condition -Condition ($criteriaById.Count -eq $expectedCriteria.Keys.Count) -Message "critère V1 inattendu dans la régression"

foreach ($criterionId in $expectedCriteria.Keys) {
    $criterion = $criteriaById[$criterionId]
    $expected = $expectedCriteria[$criterionId]
    $context = [string] $criterion.context
    $verdict = [string] $criterion.verdict
    Assert-Condition -Condition ($context -eq $expected.Context) -Message "contexte invalide pour critère: $criterionId"
    Assert-Condition -Condition ($allowedVerdicts -contains $verdict) -Message "verdict invalide pour critère: $criterionId"
    Assert-Condition -Condition ($verdict -eq $expected.Verdict) -Message "verdict contredit les décisions M-013: $criterionId"
    Assert-Command -Command ([string] $criterion.regression_command) -Label $criterionId
    $criterionEvidence = Assert-ArtifactMarker `
        -Path ([string] $criterion.evidence_artifact_path) `
        -Marker ([string] $criterion.evidence_marker) `
        -FailureMessage "résultat sans preuve: $criterionId"
    Assert-NoSensitivePayload -Content $criterionEvidence -ForbiddenMarkers $suiteForbiddenMarkers

    Assert-Condition -Condition ($decisionsByContext.ContainsKey($context)) -Message "décision V1 non reliée à la régression: $context"
    Assert-Condition -Condition ($decisionsByContext[$context]["Critère V1"] -eq $criterionId) -Message "décision V1 non reliée à la régression: $context"
    Assert-Condition `
        -Condition ($sourceGapReportContent.Contains($decisionsByContext[$context]["Benchmark source"])) `
        -Message "écart source M-012 non relié: $criterionId"

    if ($verdict -eq "NON_ACCEPTED_GAP") {
        $gapDecisionContext = [string] $criterion.gap_decision_context
        Assert-Condition `
            -Condition (($gapDecisionContext -eq $context) -and ($nonAcceptedContexts -contains $gapDecisionContext)) `
            -Message "écart non relié: $criterionId"
    }
}

$coveredCriteriaFromJourneys = New-Object System.Collections.Generic.HashSet[string]
$decisionContextsFromJourneys = New-Object System.Collections.Generic.HashSet[string]
$negativeResultPreserved = $false

$journeys = @($suite.journeys)
Assert-Condition -Condition ($journeys.Count -eq 10) -Message "nombre de parcours V1 invalide"
foreach ($journey in $journeys) {
    $journeyId = [string] $journey.journey_id
    Assert-Condition -Condition (-not [string]::IsNullOrWhiteSpace($journeyId)) -Message "parcours sans identifiant"

    $fixtureId = [string] $journey.fixture_id
    Assert-Condition -Condition ($fixturesById.ContainsKey($fixtureId)) -Message "fixture non déclarée: $fixtureId"
    Assert-Command -Command ([string] $journey.command) -Label $journeyId

    Assert-Condition -Condition ([bool] $journey.uses_internal_contract -eq $false) -Message "dépendance directe à un stockage interne: $journeyId"
    Assert-Condition -Condition ([bool] $journey.mutates_immutable_artifacts -eq $false) -Message "artefact immuable muté: $journeyId"

    foreach ($reference in @($journey.public_contract_refs)) {
        Assert-PublicContractRef -Reference ([string] $reference)
    }

    foreach ($coveredCriterion in @($journey.covered_criteria)) {
        $coveredCriterionId = [string] $coveredCriterion
        Assert-Condition -Condition ($criteriaById.ContainsKey($coveredCriterionId)) -Message "critère non couvert par la matrice de suite: $coveredCriterionId"
        $coveredCriteriaFromJourneys.Add($coveredCriterionId) | Out-Null
    }

    $firstCoveredCriterion = [string] @($journey.covered_criteria)[0]
    $journeyEvidence = Assert-ArtifactMarker `
        -Path ([string] $journey.evidence_artifact_path) `
        -Marker ([string] $journey.evidence_marker) `
        -FailureMessage "résultat sans preuve: $firstCoveredCriterion"
    Assert-NoSensitivePayload -Content $journeyEvidence -ForbiddenMarkers $suiteForbiddenMarkers

    if ([bool] $journey.requires_openable_citation) {
        Assert-ArtifactMarker `
            -Path ([string] $journey.citation_artifact_path) `
            -Marker ([string] $journey.citation_marker) `
            -FailureMessage "citation non ouvrable: $journeyId" | Out-Null
    }

    if ([bool] $journey.preserves_negative_result) {
        Assert-ArtifactMarker `
            -Path ([string] $journey.negative_result_artifact_path) `
            -Marker ([string] $journey.negative_result_marker) `
            -FailureMessage "résultat négatif disparu: $journeyId" | Out-Null
        $negativeResultPreserved = $true
    }

    foreach ($decisionContext in @($journey.decision_contexts)) {
        $context = [string] $decisionContext
        Assert-Condition -Condition ($decisionsByContext.ContainsKey($context)) -Message "décision V1 non reliée à la régression: $context"
        $decisionContextsFromJourneys.Add($context) | Out-Null
    }
}

foreach ($criterionId in $expectedCriteria.Keys) {
    Assert-Condition -Condition ($coveredCriteriaFromJourneys.Contains($criterionId)) -Message "critère non couvert par un parcours V1: $criterionId"
}

foreach ($context in $expectedContexts) {
    Assert-Condition -Condition ($decisionContextsFromJourneys.Contains($context)) -Message "décision V1 non reliée à la régression: $context"
}

Assert-Condition -Condition $negativeResultPreserved -Message "résultat négatif disparu"

foreach ($marker in @(
    "REQ-M013-004",
    "tests/m013/validate_v1_regression_suite_acceptance.ps1",
    "tests/m013/validate_v1_regression_suite_unit.ps1",
    "scripts/validate_m013_regression.ps1",
    "docs/evaluation/m013/v1_regression_suite.json"
)) {
    Assert-Condition -Condition ($matrixContent.Contains($marker)) -Message "Traçabilité T-004 absente: $marker"
}

foreach ($marker in @(
    "scripts/validate_m013_regression.ps1",
    "tests/m013/validate_v1_regression_suite_acceptance.ps1",
    "tests/m013/validate_v1_regression_suite_unit.ps1"
)) {
    Assert-Condition -Condition ($testGateContent.Contains($marker)) -Message "Gate test sans régression V1: $marker"
}

Assert-Condition -Condition ($lintGateContent.Contains("scripts/validate_m013_regression.ps1")) -Message "Gate lint sans validateur régression V1"

Write-Host "Suite de régression V1 M-013 valide: $($expectedCriteria.Keys.Count) critère(s), $($journeys.Count) parcours V1, $($nonAcceptedContexts.Count) écart(s) non accepté(s)."

