param(
    [Parameter(Mandatory = $false)]
    [string] $Path
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$defaultReportPath = "docs/governance/m011_precondition_green.md"
$m011Branch = "codex/milestone-m011-experience-reproductible"
$m012Branch = "codex/milestone-m012-evaluation-pilote-calibration"
$m013Branch = "codex/milestone-m013-durcissement-acceptation-v1"
$allowedBranches = @("master", $m011Branch, $m012Branch, $m013Branch)
$requiredMasterArtifacts = @(
    "docs/tasks/milestone_010",
    "docs/specs/m010_strategie_candidate_attribuee.md",
    "scripts/validate_m010_specification.ps1",
    "scripts/validate_m010_traceability.ps1",
    "tests/m010",
    "app/strategy_design",
    "app/contracts/strategy_experiments.py"
)
$requiredUpstreamValidators = @(
    "scripts/validate_m003_precondition.ps1",
    "scripts/validate_m004_precondition.ps1",
    "scripts/validate_m005_precondition.ps1",
    "scripts/validate_m006_precondition.ps1",
    "scripts/validate_m007_precondition.ps1",
    "scripts/validate_m008_precondition.ps1",
    "scripts/validate_m009_precondition.ps1",
    "scripts/validate_m010_precondition.ps1"
)
$requiredReportMarkers = @(
    "M-011",
    "codex/milestone-m011-experience-reproductible",
    "docs/tasks/milestone_010",
    "scripts/validate_m010_traceability.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1",
    "M-003"
)

function Resolve-M011ReportPath {
    param([string] $InputPath)
    if ([string]::IsNullOrWhiteSpace($InputPath)) {
        $candidatePath = Join-Path $repoRoot $defaultReportPath
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
        throw "Chemin hors depot interdit (precondition M-011): $resolvedCandidatePath"
    }
    return $resolvedCandidatePath
}

function Invoke-GitText {
    param([string[]] $Arguments)
    $output = & git @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Commande git invalide: git $($Arguments -join ' '). Sortie: $($output -join "`n")"
    }
    return ($output -join "`n")
}

$resolvedReportPath = Resolve-M011ReportPath -InputPath $Path
if (-not (Test-Path -LiteralPath $resolvedReportPath -PathType Leaf)) {
    throw "Rapport de precondition M-011 absent: $resolvedReportPath"
}
$reportContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedReportPath
foreach ($marker in $requiredReportMarkers) {
    if (-not $reportContent.Contains($marker)) {
        throw "Marqueur de precondition M-011 absent: $marker"
    }
}

$currentBranch = Invoke-GitText -Arguments @("branch", "--show-current")
if ($allowedBranches -notcontains $currentBranch.Trim()) {
    throw "Branche M-011 non autorisee: $currentBranch"
}

& git merge-base --is-ancestor master HEAD 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "La branche courante ne contient pas master"
}

foreach ($artifactPath in $requiredMasterArtifacts) {
    $treeOutput = & git ls-tree -r --name-only master -- $artifactPath 2>&1
    if (($LASTEXITCODE -ne 0) -or ([string]::IsNullOrWhiteSpace(($treeOutput -join "`n")))) {
        throw "Artefact M-010 absent de master: $artifactPath"
    }
}

foreach ($validatorPath in $requiredUpstreamValidators) {
    $absoluteValidatorPath = Join-Path $repoRoot $validatorPath
    if (-not (Test-Path -LiteralPath $absoluteValidatorPath -PathType Leaf)) {
        throw "Validateur amont absent: $validatorPath"
    }
    $validatorContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $absoluteValidatorPath
    if (-not $validatorContent.Contains($m011Branch)) {
        throw "Validateur amont sans branche M-011: $validatorPath"
    }
}

Write-Host "Precondition M-011 valide: master contient M-010 et les validateurs amont acceptent M-011."
