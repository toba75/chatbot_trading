$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$gatePath = Join-Path $repoRoot "scripts\validate_m013_fastapi.ps1"
$gateSource = Get-Content -Raw -Encoding UTF8 $gatePath

function Assert-Contains([string] $Content, [string] $Expected, [string] $Message) {
    if (-not $Content.Contains($Expected)) {
        throw $Message
    }
}

function Assert-NotContains([string] $Content, [string] $Forbidden, [string] $Message) {
    if ($Content.Contains($Forbidden)) {
        throw $Message
    }
}

# Given une gate exécutée alors que la .venv du dépôt est indisponible,
# When la préparation verrouillée puis une preuve RED sont exécutées,
# Then l'environnement uv est isolé, explicitement propagé et supprimé en finally.
Assert-Contains $gateSource 'M013_FASTAPI_TEMP_ENVIRONMENT:' "La gate doit rendre observable son environnement temporaire."
Assert-Contains $gateSource 'UV_PROJECT_ENVIRONMENT' "La cible uv isolée doit être explicite."
Assert-Contains $gateSource 'M013_FASTAPI_PYTHON' "Le Python verrouillé doit être propagé aux preuves."
Assert-Contains $gateSource 'finally' "Le nettoyage de l'environnement temporaire doit être garanti."
Assert-NotContains $gateSource 'Join-Path $repoRoot ".venv\Scripts"' "La gate ne doit jamais cibler la .venv partagée."

$pythonConsumers = @(
    "validate_document_worker_runtime_acceptance.ps1",
    "validate_ka_projection_persistence_live.ps1",
    "validate_document_http_live_acceptance.ps1",
    "validate_job_outbox_boundary_acceptance.ps1",
    "validate_document_worker_live.ps1",
    "validate_review3_safety_acceptance.ps1",
    "validate_worker_data_resilience_acceptance.ps1"
)
foreach ($consumer in $pythonConsumers) {
    $content = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "tests\m013_fastapi\$consumer")
    Assert-Contains $content 'Resolve-M013FastApiPython' "$consumer doit préférer M013_FASTAPI_PYTHON avec un mode standalone strict."
    Assert-NotContains $content 'Join-Path $repoRoot ".venv\Scripts\python.exe"' "$consumer ne doit plus coder la .venv en dur."
}

$sandbox = Join-Path ([System.IO.Path]::GetTempPath()) ("m013-fastapi-gate-contract-" + [guid]::NewGuid().ToString("N"))
$lockedSentinel = $null
try {
    New-Item -ItemType Directory -Path (Join-Path $sandbox "scripts") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $sandbox "tests\m013_fastapi") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $sandbox ".venv") -Force | Out-Null
    Copy-Item -LiteralPath $gatePath -Destination (Join-Path $sandbox "scripts\validate_m013_fastapi.ps1")
    Copy-Item -LiteralPath (Join-Path $repoRoot "pyproject.toml") -Destination $sandbox
    Copy-Item -LiteralPath (Join-Path $repoRoot "uv.lock") -Destination $sandbox

    $declared = [regex]::Matches($gateSource, 'tests/m013_fastapi/(validate_[a-z0-9_]+\.ps1)') |
        ForEach-Object { $_.Groups[1].Value } |
        Sort-Object -Unique
    if ($declared.Count -lt 1) {
        throw "Le catalogue de preuves M13-FastAPI est vide."
    }
    foreach ($name in $declared) {
        Set-Content -LiteralPath (Join-Path $sandbox "tests\m013_fastapi\$name") -Encoding UTF8 -Value 'exit 0'
    }
    Set-Content -LiteralPath (Join-Path $sandbox "tests\m013_fastapi\validate_precondition_acceptance.ps1") -Encoding UTF8 -Value 'exit 19'

    $sentinelPath = Join-Path $sandbox ".venv\occupied-and-intact.txt"
    [System.IO.File]::WriteAllText($sentinelPath, "intact", [System.Text.UTF8Encoding]::new($false))
    $sentinelHashBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $sentinelPath).Hash
    $lockedSentinel = [System.IO.File]::Open(
        $sentinelPath,
        [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read,
        [System.IO.FileShare]::None
    )

    $output = @(& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $sandbox "scripts\validate_m013_fastapi.ps1") -Mode Static 2>&1)
    $exitCode = $LASTEXITCODE
    $lockedSentinel.Dispose()
    $lockedSentinel = $null
    if ($exitCode -eq 0) {
        throw "La preuve synthétique devait rester RED après préparation isolée."
    }
    $sentinelHashAfter = (Get-FileHash -Algorithm SHA256 -LiteralPath $sentinelPath).Hash
    if ($sentinelHashAfter -ne $sentinelHashBefore) {
        throw "La .venv occupée du dépôt synthétique a été modifiée."
    }
    $renderedOutput = $output | Out-String
    $temporaryMatch = [regex]::Match($renderedOutput, 'M013_FASTAPI_TEMP_ENVIRONMENT:\s*(?<path>[^\r\n]+)')
    if (-not $temporaryMatch.Success) {
        throw "La gate n'a pas exposé le chemin de son environnement temporaire."
    }
    $temporaryPath = $temporaryMatch.Groups["path"].Value.Trim()
    if (Test-Path -LiteralPath $temporaryPath) {
        throw "L'environnement uv temporaire subsiste après une preuve RED: $temporaryPath"
    }
}
finally {
    if ($null -ne $lockedSentinel) {
        $lockedSentinel.Dispose()
    }
    if (Test-Path -LiteralPath $sandbox) {
        Remove-Item -LiteralPath $sandbox -Recurse -Force
    }
}

$resolver = Join-Path $repoRoot "tests\m013_fastapi\resolve_m013_fastapi_python.ps1"
. $resolver
$python = Resolve-M013FastApiPython -RepoRoot $repoRoot
$env:PYTHONPATH = $repoRoot
$pythonCode = @'
from app.platform.job_runtime.postgres import _ClaimedJobRow, _JobRow
from app.source_processing.adapters.postgres_document_persistence import (
    _ManifestEntryRow,
    _ProcessingRunRow,
)


def require_shape_error(factory, row):
    try:
        factory(row)
    except RuntimeError as exc:
        assert "SQL_ROW_SHAPE_INVALID" in str(exc), exc
    else:
        raise AssertionError("Une forme SQL divergente doit être refusée.")


require_shape_error(_JobRow.from_database, tuple(range(11)))
require_shape_error(_ClaimedJobRow.from_database, tuple(range(17)))
require_shape_error(_ProcessingRunRow.from_database, tuple(range(7)))
require_shape_error(_ManifestEntryRow.from_grouped, (1,))
print("DTO SQL nommés et formes strictes: OK")
'@
$pythonCode | & $python -
if ($LASTEXITCODE -ne 0) {
    throw "M013_REVIEW3_SQL_ROWS_RED"
}

Write-Host "Maintenance gate isolée et DTO SQL nommés: OK"
