$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$gitignorePath = Join-Path $repoRoot ".gitignore"

$expectedCorpusPdfPaths = @(
    "data/corpus/A Century of Profitable Industry Trends Carlo Zarattini Gary Antonacci.pdf",
    "data/corpus/Optimal Trend Following Rules in Two State Switching Regime Models.pdf",
    "data/corpus/Quantitative_Momentum_-_Wesley_R_Gray.pdf",
    "data/corpus/_OceanofPDF.com_Markets_and_Momentum_-_James_F_Dalton.pdf",
    "data/corpus/_OceanofPDF.com_the_second_leg_down_-_hari_p_krishnan.pdf",
    "data/corpus/buy-the-fear-sell-the-greed-pdf-free.pdf",
    "data/corpus/dual-momentum-investing-an-innovative-strategy-for-higher-returns-with-lower-risk.pdf",
    "data/corpus/the-original-turtle-trading-rules.pdf",
    "data/corpus/trading-on-momentum-advanced-techniques-for-high-percentage-day-trading.pdf",
    "data/corpus/trading-on-momentum.pdf",
    "data/corpus/trading-regime-analysis-the-probability-of-volatility-wiley-trading.pdf"
)

function Get-IgnoreExitCode {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path
    )

    & git -C $repoRoot check-ignore --no-index --quiet -- $Path
    return $LASTEXITCODE
}

function Assert-Ignored {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path
    )

    $exitCode = Get-IgnoreExitCode -Path $Path
    if ($exitCode -ne 0) {
        throw "Chemin local non ignoré: $Path"
    }
}

function Assert-NotIgnored {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path
    )

    $exitCode = Get-IgnoreExitCode -Path $Path
    if ($exitCode -ne 1) {
        throw "Chemin versionnable ignoré ou contrôle Git invalide: $Path (code $exitCode)"
    }
}

if (-not (Test-Path -LiteralPath $gitignorePath -PathType Leaf)) {
    throw "Politique d'exclusion absente: .gitignore"
}

$trackedCorpusPdfPaths = @(& git -C $repoRoot ls-files -- "data/corpus/*.pdf") | Sort-Object
if ($LASTEXITCODE -ne 0) {
    throw "Lecture des PDF suivis impossible."
}

$expectedSortedPaths = @($expectedCorpusPdfPaths | Sort-Object)
$corpusDifferences = @(Compare-Object -ReferenceObject $expectedSortedPaths -DifferenceObject $trackedCorpusPdfPaths)
if ($corpusDifferences.Count -ne 0) {
    throw "La liste des PDF suivis ne correspond pas aux onze exceptions déclarées."
}

foreach ($pdfPath in $expectedCorpusPdfPaths) {
    Assert-NotIgnored -Path $pdfPath
}

$ignoredPaths = @(
    "data/corpus/unlisted.pdf",
    "data/canonical_sources/document.json",
    "data/qdrant/segments/index.bin",
    "data/postgres/base/record.bin",
    "data/experiments/run.json",
    "logs/application.log",
    ".tmp/work/file.txt",
    "app/__pycache__/module.pyc",
    ".pytest_cache/state",
    ".mypy_cache/state",
    ".ruff_cache/state",
    ".coverage",
    "htmlcov/index.html",
    ".venv/pyvenv.cfg",
    "venv/pyvenv.cfg",
    ".env",
    ".env.local",
    "config/application.yaml",
    "config/secrets/local/postgres_password"
)

foreach ($ignoredPath in $ignoredPaths) {
    Assert-Ignored -Path $ignoredPath
}

Assert-NotIgnored -Path "config/application.example.yaml"
Assert-NotIgnored -Path "config/secrets/local/.gitignore"

Write-Host "Politique .gitignore valide: data ignoré sauf onze PDF, sorties locales exclues."
