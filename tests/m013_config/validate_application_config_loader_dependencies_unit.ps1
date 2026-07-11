$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")

$scannedFiles = @(
    "app/platform/configuration/__init__.py",
    "tests/m013_config/validate_application_config_loader_acceptance.ps1",
    "tests/m013_config/validate_application_config_loader_unit.ps1"
)

$forbiddenFragments = @(
    "import yaml",
    "from yaml",
    "import jsonschema",
    "from jsonschema",
    "Draft202012Validator"
)

foreach ($relativePath in $scannedFiles) {
    $absolutePath = Join-Path $repoRoot $relativePath
    if (-not (Test-Path -LiteralPath $absolutePath -PathType Leaf)) {
        throw "Fichier T-003 absent pour contrôle de dépendances: $relativePath"
    }

    $content = (Get-Content -Raw -Encoding UTF8 -LiteralPath $absolutePath).TrimStart([char] 0xFEFF)
    foreach ($forbiddenFragment in $forbiddenFragments) {
        if ($content.Contains($forbiddenFragment)) {
            throw "Dépendance Python externe interdite dans T-003: $forbiddenFragment dans $relativePath"
        }
    }
}

Write-Host "Tests unitaires dépendances chargeur de configuration applicative: OK"
