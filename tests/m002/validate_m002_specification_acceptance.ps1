$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m002_specification.ps1"
$specPath = Join-Path $repoRoot "docs/specs/m002_plateforme_locale_sure.md"

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
    throw "Validateur de spécification M-002 absent: scripts/validate_m002_specification.ps1"
}

# Given la spécification v4.1 impose deux plans physiques et une cohérence éventuelle par outbox.
# When la spécification M-002 est publiée.
# Then chaque règle de plateforme nomme le comportement attendu, les invariants, les tests et les ADR qui la gouvernent.
$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $validatorPath -Path $specPath 2>&1
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
}

if ($LASTEXITCODE -ne 0) {
    throw ($output -join "`n")
}

Write-Host "Test d'acceptation de la spécification M-002: OK"
