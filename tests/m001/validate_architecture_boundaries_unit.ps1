$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$validatorPath = Join-Path $repoRoot "scripts/validate_architecture_boundaries.ps1"
$realRegistryPath = Join-Path $repoRoot "app/context_registry.json"
$specificationPath = Join-Path $repoRoot "docs/specs/m001_frontieres_ddd_contrats_publies.md"

$eAcute = [char] 0x00E9
$eGrave = [char] 0x00E8

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

    $targetRoot = Join-Path $repoRoot (".tmp/ost_m001_arch_unit_" + $ScenarioName + "_" + [System.Guid]::NewGuid().ToString("N"))
    $sampleAppRoot = Join-Path $targetRoot "app"
    $registry = Get-Content -Raw -Encoding UTF8 -LiteralPath $realRegistryPath | ConvertFrom-Json

    New-PythonPackageFile -Path (Join-Path $sampleAppRoot "__init__.py") -Content ""
    New-PythonPackageFile -Path (Join-Path $sampleAppRoot "platform/__init__.py") -Content ""
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
        -ExpectedFragments @("Import de framework externe interdit dans domain", "framework pydantic", "Mod$($eGrave)le d'API interdit dans domain", "ResearchQuery")

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

    $inverseFacadeImport = New-ControlledApp -ScenarioName "inverse_facade"
    $createdRoots += $inverseFacadeImport.Root
    New-PythonPackageFile -Path (Join-Path $inverseFacadeImport.AppRoot "experimentation/application/conversation_client.py") -Content @"
from app.conversation.application.strategy_request_facade import StrategyRequestFacade

def load_facade():
    return StrategyRequestFacade()
"@
    Assert-FailsWith `
        -Scenario $inverseFacadeImport `
        -ExpectedFragments @("Import intercontexte interdit", "consommateur EX", "producteur CV", "app.conversation.application.strategy_request_facade")

    $forbiddenContractImport = New-ControlledApp -ScenarioName "forbidden_contract"
    $createdRoots += $forbiddenContractImport.Root
    New-PythonPackageFile -Path (Join-Path $forbiddenContractImport.AppRoot "experimentation/domain/uses_research_outcome.py") -Content @"
from app.contracts.research_outcomes import VerifiedResearchOutcome

def project_outcome(outcome: VerifiedResearchOutcome):
    return outcome
"@
    Assert-FailsWith `
        -Scenario $forbiddenContractImport `
        -ExpectedFragments @("Import de contrat publie interdit", "contexte EX", "app.contracts.research_outcomes")

    $platformBusinessImport = New-ControlledApp -ScenarioName "platform_business_import"
    $createdRoots += $platformBusinessImport.Root
    New-PythonPackageFile -Path (Join-Path $platformBusinessImport.AppRoot "platform/job_runtime.py") -Content @"
from app.source_processing.domain.canonical_source import CanonicalSource

def load_source():
    return CanonicalSource()
"@
    Assert-FailsWith `
        -Scenario $platformBusinessImport `
        -ExpectedFragments @("Import de contexte metier interdit dans platform", "app.source_processing.domain.canonical_source")

    $emptyAppRoot = Join-Path $repoRoot (".tmp/ost_m001_arch_unit_empty_" + [System.Guid]::NewGuid().ToString("N"))
    $createdRoots += $emptyAppRoot
    New-PythonPackageFile -Path (Join-Path $emptyAppRoot "__init__.py") -Content ""
    New-PythonPackageFile -Path (Join-Path $emptyAppRoot "contracts/__init__.py") -Content ""
    New-PythonPackageFile -Path (Join-Path $emptyAppRoot "platform/__init__.py") -Content ""
    $emptyResult = Invoke-ArchitectureBoundaryValidator -AppRoot $emptyAppRoot -ContextRegistryPath $realRegistryPath
    if ($emptyResult.ExitCode -eq 0) {
        throw "Un AppRoot vide doit etre refuse."
    }
    foreach ($expectedFragment in @("Module de contexte absent", "source_processing")) {
        if (-not $emptyResult.Output.Contains($expectedFragment)) {
            throw "Fragment attendu absent: $expectedFragment`nSortie obtenue:`n$($emptyResult.Output)"
        }
    }

    $missingPython = New-ControlledApp -ScenarioName "missing_python"
    $createdRoots += $missingPython.Root
    $powershellExecutable = (Get-Command powershell -ErrorAction Stop).Source
    $previousPath = $env:PATH
    $previousMissingPythonErrorActionPreference = $ErrorActionPreference
    $env:PATH = $PSHOME
    $ErrorActionPreference = "Continue"
    try {
        $missingPythonOutput = & $powershellExecutable `
            -NoProfile `
            -ExecutionPolicy Bypass `
            -File $validatorPath `
            -AppRoot $missingPython.AppRoot `
            -ContextRegistryPath $missingPython.RegistryPath `
            -SpecificationPath $specificationPath `
            2>&1
        $missingPythonExitCode = $LASTEXITCODE
    }
    finally {
        $env:PATH = $previousPath
        $ErrorActionPreference = $previousMissingPythonErrorActionPreference
    }
    $missingPythonText = $missingPythonOutput -join "`n"
    if ($missingPythonExitCode -eq 0) {
        throw "Le wrapper doit echouer quand python est absent du PATH."
    }
    if (-not $missingPythonText.Contains("Python 3.10+ requis")) {
        throw "Message Python absent. Sortie obtenue:`n$missingPythonText"
    }

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

Write-Host "Tests unitaires des fronti$($eGrave)res d'import M-001: OK"
