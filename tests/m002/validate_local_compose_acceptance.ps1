$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_local_compose.ps1"
$composePath = Join-Path $repoRoot "deploy/local-compose/compose.yaml"
$temporaryRoot = Join-Path $repoRoot (".tmp/ost_m002_local_compose_acceptance_" + [System.Guid]::NewGuid().ToString("N"))

function Invoke-LocalComposeValidator {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ComposePath
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $validatorPath -Path $ComposePath 2>&1
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

function New-TemporaryCompose {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name,

        [Parameter(Mandatory = $true)]
        [string] $Content
    )

    $path = Join-Path $temporaryRoot "$Name.yaml"
    Set-Content -Encoding UTF8 -LiteralPath $path -Value $Content
    return $path
}

function Add-PublishedPortToService {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content,

        [Parameter(Mandatory = $true)]
        [string] $ServiceId
    )

    $serviceHeader = "  ${ServiceId}:`n"
    if (-not $Content.Contains($serviceHeader)) {
        throw "Service fixture absent: $ServiceId"
    }

    $publishedPort = "  ${ServiceId}:`n    ports:`n      - `"127.0.0.1:9191:9191`"`n"
    return $Content.Replace($serviceHeader, $publishedPort)
}

function Add-SparkEgressToService {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content,

        [Parameter(Mandatory = $true)]
        [string] $ServiceId
    )

    $serviceHeader = "  ${ServiceId}:`n"
    $serviceIndex = $Content.IndexOf($serviceHeader)
    if ($serviceIndex -lt 0) {
        throw "Service fixture absent: $ServiceId"
    }

    $networkBlock = "    networks:`n      - core`n"
    $networkIndex = $Content.IndexOf($networkBlock, $serviceIndex)
    if ($networkIndex -lt 0) {
        throw "Bloc networks fixture absent pour service: $ServiceId"
    }

    $mutatedNetworkBlock = "    networks:`n      - core`n      - spark-egress`n"
    return $Content.Remove($networkIndex, $networkBlock.Length).Insert($networkIndex, $mutatedNetworkBlock)
}

function Remove-GatewaySparkSecret {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content
    )

    $secretLine = "      - gemma_api_key`n"
    if (-not $Content.Contains($secretLine)) {
        throw "Secret Spark fixture absent: gemma_api_key"
    }

    return $Content.Replace($secretLine, "")
}

function Add-VllmPrincipalService {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content
    )

    $injectedService = @'
  vllm-main:
    image: vllm/vllm-openai:0.8.5
    expose:
      - "8443"
    networks:
      - core
    healthcheck:
      test:
        - CMD-SHELL
        - "test -f /tmp/health"
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s

'@

    $rootNetworksMarker = "networks:`n  edge:"
    if (-not $Content.Contains($rootNetworksMarker)) {
        throw "Bloc networks racine absent du fixture."
    }

    return $Content.Replace($rootNetworksMarker, "$injectedService`n$rootNetworksMarker")
}

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
    throw "Validateur Compose local M-002 absent: scripts/validate_local_compose.ps1"
}

if (-not (Test-Path -LiteralPath $composePath -PathType Leaf)) {
    throw "Compose local M-002 absent: deploy/local-compose/compose.yaml"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    # Given l'utilisateur lance la stack docker-local.
    # When la configuration Compose est validée.
    # Then les stockages et workers restent internes, llm-gateway est présent,
    # et aucun service Gemma ou vLLM principal n'est déclaré localement.
    $validResult = Invoke-LocalComposeValidator -ComposePath $composePath
    Assert-ExitCode -Actual $validResult.ExitCode -Expected 0 -Message "Le Compose local canonique doit être GREEN."
    Assert-OutputContains -Output $validResult.Output -Expected "Compose local M-002 valide" -Message "Le validateur doit annoncer le GREEN Compose local."

    $validCompose = Get-Content -Raw -Encoding UTF8 -LiteralPath $composePath

    foreach ($serviceId in @(
        "postgres",
        "qdrant",
        "granite-docling",
        "embedding-service",
        "reranker-service",
        "worker-documents",
        "worker-research",
        "worker-backtest"
    )) {
        $portsPath = New-TemporaryCompose -Name "$serviceId-ports" -Content (Add-PublishedPortToService -Content $validCompose -ServiceId $serviceId)
        $portsResult = Invoke-LocalComposeValidator -ComposePath $portsPath
        Assert-ExitCode -Actual $portsResult.ExitCode -Expected 1 -Message "Le service $serviceId ne doit pas publier de port."
        Assert-OutputContains -Output $portsResult.Output -Expected "interdit pour service interne: $serviceId" -Message "Le port interdit doit nommer le service."
    }

    $vllmPath = New-TemporaryCompose -Name "vllm-main-local" -Content (Add-VllmPrincipalService -Content $validCompose)
    $vllmResult = Invoke-LocalComposeValidator -ComposePath $vllmPath
    Assert-ExitCode -Actual $vllmResult.ExitCode -Expected 1 -Message "Un vLLM principal local doit être refusé."
    Assert-OutputContains -Output $vllmResult.Output -Expected "Service Gemma/vLLM principal interdit dans Compose local: vllm-main" -Message "Le refus vLLM local doit être explicite."

    $missingSecretPath = New-TemporaryCompose -Name "gateway-without-gemma-secret" -Content (Remove-GatewaySparkSecret -Content $validCompose)
    $missingSecretResult = Invoke-LocalComposeValidator -ComposePath $missingSecretPath
    Assert-ExitCode -Actual $missingSecretResult.ExitCode -Expected 1 -Message "Le secret Spark du gateway doit être requis."
    Assert-OutputContains -Output $missingSecretResult.Output -Expected "Secret Spark absent pour llm-gateway: gemma_api_key" -Message "Le secret Spark absent doit être nommé."

    $workerEgressPath = New-TemporaryCompose -Name "worker-spark-egress" -Content (Add-SparkEgressToService -Content $validCompose -ServiceId "worker-documents")
    $workerEgressResult = Invoke-LocalComposeValidator -ComposePath $workerEgressPath
    Assert-ExitCode -Actual $workerEgressResult.ExitCode -Expected 1 -Message "Un worker ne doit pas joindre spark-egress."
    Assert-OutputContains -Output $workerEgressResult.Output -Expected "spark-egress interdit pour service: worker-documents" -Message "Le réseau interdit doit nommer le service."
}
finally {
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
}

Write-Host "Test d'acceptation Compose local M-002: OK"
