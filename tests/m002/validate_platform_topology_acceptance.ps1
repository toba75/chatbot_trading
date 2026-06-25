$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_platform_topology.ps1"
$registryPath = Join-Path $repoRoot "app/platform/topology_registry.json"
$temporaryRoot = Join-Path $repoRoot (".tmp/ost_m002_platform_topology_acceptance_" + [System.Guid]::NewGuid().ToString("N"))

function Invoke-PlatformTopologyValidator {
    param(
        [Parameter(Mandatory = $true)]
        [string] $TopologyPath
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $validatorPath -Path $TopologyPath 2>&1
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    return [pscustomobject] @{
        ExitCode = $LASTEXITCODE
        Output = ($output -join "`n")
    }
}

function Assert-ExitCode {
    param(
        [Parameter(Mandatory = $true)]
        [int] $Actual,

        [Parameter(Mandatory = $true)]
        [int] $Expected,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if ($Actual -ne $Expected) {
        throw "$Message Code obtenu: $Actual"
    }
}

function Assert-OutputContains {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Output,

        [Parameter(Mandatory = $true)]
        [string] $Expected,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if (-not $Output.Contains($Expected)) {
        throw "$Message Sortie obtenue: $Output"
    }
}

function Copy-RegistryObject {
    param(
        [Parameter(Mandatory = $true)]
        [object] $Registry
    )

    return ($Registry | ConvertTo-Json -Depth 32 | ConvertFrom-Json)
}

function Get-TopologyService {
    param(
        [Parameter(Mandatory = $true)]
        [object] $Registry,

        [Parameter(Mandatory = $true)]
        [string] $ServiceId
    )

    $matches = @($Registry.services | Where-Object { $_.id -eq $ServiceId })
    if ($matches.Count -ne 1) {
        throw "Service attendu absent ou dupliqué dans le fixture: $ServiceId"
    }

    return $matches[0]
}

function New-TemporaryTopology {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name,

        [Parameter(Mandatory = $true)]
        [object] $Registry
    )

    $path = Join-Path $temporaryRoot "$Name.json"
    $Registry | ConvertTo-Json -Depth 32 | Set-Content -Encoding UTF8 -LiteralPath $path
    return $path
}

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
    throw "Validateur de topologie M-002 absent: scripts/validate_platform_topology.ps1"
}

if (-not (Test-Path -LiteralPath $registryPath -PathType Leaf)) {
    throw "Registre de topologie M-002 absent: app/platform/topology_registry.json"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    # Given la plateforme contient des services applicatifs, des stockages et un service Gemma.
    # When la topologie M-002 est validée.
    # Then chaque service est placé sur l'hôte autorisé et aucun stockage métier n'est déclaré sur spark-inference.
    $validResult = Invoke-PlatformTopologyValidator -TopologyPath $registryPath
    Assert-ExitCode -Actual $validResult.ExitCode -Expected 0 -Message "La topologie M-002 canonique doit être GREEN."
    Assert-OutputContains -Output $validResult.Output -Expected "Topologie M-002 valide" -Message "Le validateur doit annoncer le GREEN de topologie."

    $validRegistry = Get-Content -Raw -Encoding UTF8 -LiteralPath $registryPath | ConvertFrom-Json

    $composeGemmaRegistry = Copy-RegistryObject -Registry $validRegistry
    $gemmaService = Get-TopologyService -Registry $composeGemmaRegistry -ServiceId "gemma-vllm"
    $gemmaService.host = "docker-local"
    $gemmaService.compose_local = $true
    $composeGemmaPath = New-TemporaryTopology -Name "gemma-compose-local" -Registry $composeGemmaRegistry
    $composeGemmaResult = Invoke-PlatformTopologyValidator -TopologyPath $composeGemmaPath
    Assert-ExitCode -Actual $composeGemmaResult.ExitCode -Expected 1 -Message "Gemma/vLLM dans le Compose local doit être refusé."
    Assert-OutputContains -Output $composeGemmaResult.Output -Expected "Gemma/vLLM principal interdit dans Compose local" -Message "Le refus Gemma/vLLM local doit être explicite."

    $postgresSparkRegistry = Copy-RegistryObject -Registry $validRegistry
    (Get-TopologyService -Registry $postgresSparkRegistry -ServiceId "postgres").host = "spark-inference"
    $postgresSparkPath = New-TemporaryTopology -Name "postgres-spark" -Registry $postgresSparkRegistry
    $postgresSparkResult = Invoke-PlatformTopologyValidator -TopologyPath $postgresSparkPath
    Assert-ExitCode -Actual $postgresSparkResult.ExitCode -Expected 1 -Message "PostgreSQL sur Spark doit être refusé."
    Assert-OutputContains -Output $postgresSparkResult.Output -Expected "Stockage métier interdit sur spark-inference: postgres" -Message "Le stockage Spark interdit doit être nommé."

    $qdrantSparkRegistry = Copy-RegistryObject -Registry $validRegistry
    (Get-TopologyService -Registry $qdrantSparkRegistry -ServiceId "qdrant").host = "spark-inference"
    $qdrantSparkPath = New-TemporaryTopology -Name "qdrant-spark" -Registry $qdrantSparkRegistry
    $qdrantSparkResult = Invoke-PlatformTopologyValidator -TopologyPath $qdrantSparkPath
    Assert-ExitCode -Actual $qdrantSparkResult.ExitCode -Expected 1 -Message "Qdrant sur Spark doit être refusé."
    Assert-OutputContains -Output $qdrantSparkResult.Output -Expected "Stockage métier interdit sur spark-inference: qdrant" -Message "Le stockage Spark interdit doit être nommé."

    $workerSparkRegistry = Copy-RegistryObject -Registry $validRegistry
    (Get-TopologyService -Registry $workerSparkRegistry -ServiceId "worker-documents").host = "spark-inference"
    $workerSparkPath = New-TemporaryTopology -Name "worker-spark" -Registry $workerSparkRegistry
    $workerSparkResult = Invoke-PlatformTopologyValidator -TopologyPath $workerSparkPath
    Assert-ExitCode -Actual $workerSparkResult.ExitCode -Expected 1 -Message "Un worker sur Spark doit être refusé."
    Assert-OutputContains -Output $workerSparkResult.Output -Expected "Traitement local interdit sur spark-inference: worker-documents" -Message "Le worker Spark interdit doit être nommé."

    $missingHostRegistry = Copy-RegistryObject -Registry $validRegistry
    (Get-TopologyService -Registry $missingHostRegistry -ServiceId "llm-gateway").host = ""
    $missingHostPath = New-TemporaryTopology -Name "service-without-host" -Registry $missingHostRegistry
    $missingHostResult = Invoke-PlatformTopologyValidator -TopologyPath $missingHostPath
    Assert-ExitCode -Actual $missingHostResult.ExitCode -Expected 1 -Message "Un service sans hôte explicite doit être refusé."
    Assert-OutputContains -Output $missingHostResult.Output -Expected "Hôte explicite absent pour service: llm-gateway" -Message "Le service sans hôte doit être nommé."
}
finally {
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
}

Write-Host "Test d'acceptation de topologie M-002: OK"
