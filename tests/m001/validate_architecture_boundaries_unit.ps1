$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$validatorPath = Join-Path $repoRoot "scripts/validate_architecture_boundaries.ps1"
$realRegistryPath = Join-Path $repoRoot "app/context_registry.json"
$specificationPath = Join-Path $repoRoot "docs/specs/m001_frontieres_ddd_contrats_publies.md"

$eAcute = [char] 0x00E9

function Assert-ValidatorExists {
    if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
        throw "Validateur T-010 absent: scripts/validate_architecture_boundaries.ps1"
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

function New-ControlledApp {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ScenarioName
    )

    $targetRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m001_arch_unit_" + $ScenarioName + "_" + [System.Guid]::NewGuid().ToString("N"))
    $sampleAppRoot = Join-Path $targetRoot "app"
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

class StrategyRequest:
    pass
"@
    New-PythonPackageFile -Path (Join-Path $sampleAppRoot "conversation/application/strategy_request_facade.py") -Content @"
class StrategyRequestFacade:
    pass
"@
    New-PythonPackageFile -Path (Join-Path $sampleAppRoot "strategy_design/application/strategy_design_facade.py") -Content @"
class StrategyDesignFacade:
    pass
"@
    New-PythonPackageFile -Path (Join-Path $sampleAppRoot "source_processing/domain/canonical_source.py") -Content @"
class CanonicalSource:
    pass
"@
    New-PythonPackageFile -Path (Join-Path $sampleAppRoot "source_processing/adapters/persistence.py") -Content @"
class SourceRepository:
    pass
"@

    $registry | ConvertTo-Json -Depth 20 | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $sampleAppRoot "context_registry.json")

    return @{
        Root = $targetRoot
        AppRoot = $sampleAppRoot
        RegistryPath = (Join-Path $sampleAppRoot "context_registry.json")
    }
}

function Invoke-ArchitectureBoundaryValidator {
    param(
        [Parameter(Mandatory = $true)]
        [string] $AppRoot,

        [Parameter(Mandatory = $true)]
        [string] $ContextRegistryPath
    )

    Assert-ValidatorExists

    $output = & powershell `
        -NoProfile `
        -ExecutionPolicy Bypass `
        -File $validatorPath `
        -AppRoot $AppRoot `
        -ContextRegistryPath $ContextRegistryPath `
        -SpecificationPath $specificationPath `
        2>&1

    return @{
        ExitCode = $LASTEXITCODE
        Output = ($output -join "`n")
    }
}

function Assert-Passes {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable] $Scenario
    )

    $result = Invoke-ArchitectureBoundaryValidator -AppRoot $Scenario.AppRoot -ContextRegistryPath $Scenario.RegistryPath
    if ($result.ExitCode -ne 0) {
        throw $result.Output
    }
}

function Assert-FailsWith {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable] $Scenario,

        [Parameter(Mandatory = $true)]
        [string[]] $ExpectedFragments
    )

    $result = Invoke-ArchitectureBoundaryValidator -AppRoot $Scenario.AppRoot -ContextRegistryPath $Scenario.RegistryPath
    if ($result.ExitCode -eq 0) {
        throw "Une violation d'architecture etait attendue."
    }

    foreach ($expectedFragment in $ExpectedFragments) {
        if (-not $result.Output.Contains($expectedFragment)) {
            throw "Fragment attendu absent: $expectedFragment`nSortie obtenue:`n$($result.Output)"
        }
    }
}

$createdRoots = @()
try {
    $allowedContractsAndFacade = New-ControlledApp -ScenarioName "allowed"
    $createdRoots += $allowedContractsAndFacade.Root
    New-PythonPackageFile -Path (Join-Path $allowedContractsAndFacade.AppRoot "knowledge_access/domain/uses_contract.py") -Content @"
from app.contracts import CanonicalSourceRef

def project_source(reference: CanonicalSourceRef):
    return reference
"@
    New-PythonPackageFile -Path (Join-Path $allowedContractsAndFacade.AppRoot "conversation/adapters/strategy_client.py") -Content @"
from app.strategy_design.application.strategy_design_facade import StrategyDesignFacade

def load_facade():
    return StrategyDesignFacade()
"@
    Assert-Passes -Scenario $allowedContractsAndFacade

    $domainAdapterImport = New-ControlledApp -ScenarioName "domain_adapter"
    $createdRoots += $domainAdapterImport.Root
    New-PythonPackageFile -Path (Join-Path $domainAdapterImport.AppRoot "source_processing/domain/uses_adapter.py") -Content @"
from app.source_processing.adapters.persistence import SourceRepository

def build_repository():
    return SourceRepository()
"@
    Assert-FailsWith `
        -Scenario $domainAdapterImport `
        -ExpectedFragments @("Import d'adapter interdit dans domain", "contexte SP", "app.source_processing.adapters.persistence")

    $domainFrameworkImport = New-ControlledApp -ScenarioName "domain_framework"
    $createdRoots += $domainFrameworkImport.Root
    New-PythonPackageFile -Path (Join-Path $domainFrameworkImport.AppRoot "research_answering/domain/api_query.py") -Content @"
from pydantic import BaseModel

class ResearchQuery(BaseModel):
    pass
"@
    Assert-FailsWith `
        -Scenario $domainFrameworkImport `
        -ExpectedFragments @("Import de framework externe interdit dans domain", "framework pydantic", "Mod$($eAcute)le d'API interdit dans domain", "ResearchQuery")

    $interContextInternalModel = New-ControlledApp -ScenarioName "intercontext_internal"
    $createdRoots += $interContextInternalModel.Root
    New-PythonPackageFile -Path (Join-Path $interContextInternalModel.AppRoot "knowledge_access/application/read_source.py") -Content @"
from app.source_processing.domain.canonical_source import CanonicalSource

def read_source():
    return CanonicalSource()
"@
    Assert-FailsWith `
        -Scenario $interContextInternalModel `
        -ExpectedFragments @("Import intercontexte interdit", "consommateur KA", "producteur SP", "contrat publi$($eAcute) attendu: CanonicalSourcePublished")

    $cycleBetweenFacades = New-ControlledApp -ScenarioName "cycle"
    $createdRoots += $cycleBetweenFacades.Root
    New-PythonPackageFile -Path (Join-Path $cycleBetweenFacades.AppRoot "conversation/application/strategy_request_facade.py") -Content @"
from app.strategy_design.application.strategy_design_facade import StrategyDesignFacade

class StrategyRequestFacade:
    pass
"@
    New-PythonPackageFile -Path (Join-Path $cycleBetweenFacades.AppRoot "strategy_design/application/strategy_design_facade.py") -Content @"
from app.conversation.application.strategy_request_facade import StrategyRequestFacade

class StrategyDesignFacade:
    pass
"@
    Assert-FailsWith `
        -Scenario $cycleBetweenFacades `
        -ExpectedFragments @("Cycle intercontexte interdit", "CV", "SD")
}
finally {
    foreach ($createdRoot in $createdRoots) {
        if (Test-Path -LiteralPath $createdRoot) {
            Remove-Item -LiteralPath $createdRoot -Recurse -Force
        }
    }
}

Write-Host "Tests unitaires des frontieres d'import M-001: OK"
