$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$validatorPath = Join-Path $repoRoot "scripts/validate_architecture_boundaries.ps1"
$realAppRoot = Join-Path $repoRoot "app"
$realRegistryPath = Join-Path $realAppRoot "context_registry.json"
$specificationPath = Join-Path $repoRoot "docs/specs/m001_frontieres_ddd_contrats_publies.md"

$eAcute = [char] 0x00E9
$eGrave = [char] 0x00E8

function Assert-ValidatorExists {
    if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
        throw "Validateur T-010 absent: scripts/validate_architecture_boundaries.ps1"
    }
}

function Invoke-ArchitectureBoundaryValidator {
    param(
        [Parameter(Mandatory = $true)]
        [string] $AppRoot,

        [Parameter(Mandatory = $true)]
        [string] $ContextRegistryPath,

        [Parameter(Mandatory = $true)]
        [string] $SpecificationPath
    )

    Assert-ValidatorExists

    $output = & powershell `
        -NoProfile `
        -ExecutionPolicy Bypass `
        -File $validatorPath `
        -AppRoot $AppRoot `
        -ContextRegistryPath $ContextRegistryPath `
        -SpecificationPath $SpecificationPath `
        2>&1

    return @{
        ExitCode = $LASTEXITCODE
        Output = ($output -join "`n")
    }
}

function Assert-OutputContains {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Output,

        [Parameter(Mandatory = $true)]
        [string] $Expected
    )

    if (-not $Output.Contains($Expected)) {
        throw "Sortie attendue absente: $Expected`nSortie obtenue:`n$Output"
    }
}

function New-PythonPackageFile {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string] $Content
    )

    $directory = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force -Path $directory | Out-Null
    Set-Content -Encoding UTF8 -LiteralPath $Path -Value $Content
}

function Initialize-ControlledApp {
    param(
        [Parameter(Mandatory = $true)]
        [string] $TargetRoot
    )

    $sampleAppRoot = Join-Path $TargetRoot "app"
    $registry = Get-Content -Raw -Encoding UTF8 -LiteralPath $realRegistryPath | ConvertFrom-Json

    New-PythonPackageFile -Path (Join-Path $sampleAppRoot "__init__.py") -Content ""
    foreach ($context in @($registry.contexts)) {
        $contextRoot = Join-Path $sampleAppRoot $context.module
        New-PythonPackageFile -Path (Join-Path $contextRoot "__init__.py") -Content ""
        foreach ($layer in @($context.layers)) {
            New-PythonPackageFile -Path (Join-Path $contextRoot "$layer/__init__.py") -Content ""
        }
    }

    New-PythonPackageFile -Path (Join-Path $sampleAppRoot "contracts/__init__.py") -Content @"
class CanonicalSourceRef:
    pass
"@
    New-PythonPackageFile -Path (Join-Path $sampleAppRoot "source_processing/domain/canonical_source.py") -Content @"
class CanonicalSource:
    pass
"@

    $registry | ConvertTo-Json -Depth 20 | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $sampleAppRoot "context_registry.json")

    return $sampleAppRoot
}

# Given les contextes M-001 existants communiquent par contrats publies.
# When les frontieres d'import sont controlees.
# Then l'application courante ne contient pas de couplage intercontexte interdit.
$realResult = Invoke-ArchitectureBoundaryValidator `
    -AppRoot $realAppRoot `
    -ContextRegistryPath $realRegistryPath `
    -SpecificationPath $specificationPath

if ($realResult.ExitCode -ne 0) {
    throw $realResult.Output
}
Assert-OutputContains -Output $realResult.Output -Expected "Fronti$($eGrave)res d'import M-001 valides"

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m001_arch_acceptance_" + [System.Guid]::NewGuid().ToString("N"))
try {
    $sampleAppRoot = Initialize-ControlledApp -TargetRoot $tempRoot
    New-PythonPackageFile -Path (Join-Path $sampleAppRoot "knowledge_access/domain/direct_source_model.py") -Content @"
from app.source_processing.domain.canonical_source import CanonicalSource

def read_source_model():
    return CanonicalSource()
"@

    # Given KA tente d'utiliser le modele interne SP.
    # When le validateur d'architecture est execute sur l'echantillon controle.
    # Then l'import est refuse avec le producteur, le consommateur et le contrat publie attendu.
    $invalidResult = Invoke-ArchitectureBoundaryValidator `
        -AppRoot $sampleAppRoot `
        -ContextRegistryPath (Join-Path $sampleAppRoot "context_registry.json") `
        -SpecificationPath $specificationPath

    if ($invalidResult.ExitCode -eq 0) {
        throw "Le validateur devait refuser l'import intercontexte interdit KA vers SP."
    }

    Assert-OutputContains -Output $invalidResult.Output -Expected "Import intercontexte interdit"
    Assert-OutputContains -Output $invalidResult.Output -Expected "consommateur KA"
    Assert-OutputContains -Output $invalidResult.Output -Expected "producteur SP"
    Assert-OutputContains -Output $invalidResult.Output -Expected "app.knowledge_access.domain.direct_source_model"
    Assert-OutputContains -Output $invalidResult.Output -Expected "app.source_processing.domain.canonical_source"
    Assert-OutputContains -Output $invalidResult.Output -Expected "contrat publi$($eAcute) attendu: CanonicalSourcePublished"
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}

Write-Host "Test d'acceptation des fronti$($eGrave)res d'import M-001: OK"
