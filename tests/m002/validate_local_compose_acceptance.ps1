$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_local_compose.ps1"
$composePath = Join-Path $repoRoot "deploy/local-compose/compose.yaml"
$caddyfilePath = Join-Path $repoRoot "deploy/local-compose/Caddyfile"
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

function Get-ComposeLineEnding {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content
    )

    if ($Content.Contains("`r`n")) {
        return "`r`n"
    }

    if ($Content.Contains("`n")) {
        return "`n"
    }

    throw "Fin de ligne fixture Compose absente."
}

function Find-ServiceInsertionIndex {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content,

        [Parameter(Mandatory = $true)]
        [string] $ServiceId,

        [Parameter(Mandatory = $true)]
        [string] $Section
    )

    $serviceMatch = [regex]::Match($Content, "(?m)^  $([regex]::Escape($ServiceId)):\r?\n")
    if (-not $serviceMatch.Success) {
        throw "Service fixture absent: $ServiceId"
    }

    $serviceTail = $Content.Substring($serviceMatch.Index + $serviceMatch.Length)
    $sectionMatch = [regex]::Match($serviceTail, "(?m)^    $([regex]::Escape($Section)):\r?\n")
    if (-not $sectionMatch.Success) {
        throw "Section fixture absente pour service ${ServiceId}: $Section"
    }

    return $serviceMatch.Index + $serviceMatch.Length + $sectionMatch.Index
}

function Add-PublishedPortToService {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content,

        [Parameter(Mandatory = $true)]
        [string] $ServiceId
    )

    $lineEnding = Get-ComposeLineEnding -Content $Content
    $serviceMatch = [regex]::Match($Content, "(?m)^  $([regex]::Escape($ServiceId)):\r?\n")
    if (-not $serviceMatch.Success) {
        throw "Service fixture absent: $ServiceId"
    }

    $publishedPort = "${lineEnding}    ports:${lineEnding}      - `"127.0.0.1:9191:9191`"${lineEnding}"
    return $Content.Insert($serviceMatch.Index + $serviceMatch.Length, $publishedPort)
}

function Add-SparkEgressToService {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content,

        [Parameter(Mandatory = $true)]
        [string] $ServiceId
    )

    $lineEnding = Get-ComposeLineEnding -Content $Content
    $networkIndex = Find-ServiceInsertionIndex -Content $Content -ServiceId $ServiceId -Section "networks"
    $networkBlockMatch = [regex]::Match($Content.Substring($networkIndex), "(?m)^    networks:\r?\n      - core\r?\n")
    if (-not $networkBlockMatch.Success) {
        throw "Bloc networks fixture absent pour service: $ServiceId"
    }

    $mutatedNetworkBlock = "    networks:${lineEnding}      - core${lineEnding}      - spark-egress${lineEnding}"
    return $Content.Remove($networkIndex, $networkBlockMatch.Length).Insert($networkIndex, $mutatedNetworkBlock)
}

function Add-ApplicationEnvironmentVariable {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content,

        [Parameter(Mandatory = $true)]
        [string] $ServiceId,

        [Parameter(Mandatory = $true)]
        [string] $Name
    )

    $lineEnding = Get-ComposeLineEnding -Content $Content
    $networkIndex = Find-ServiceInsertionIndex -Content $Content -ServiceId $ServiceId -Section "networks"
    $environmentBlock = "    environment:${lineEnding}      ${Name}: `"http://valeur-applicative.local`"${lineEnding}"
    return $Content.Insert($networkIndex, $environmentBlock)
}

function Add-EnvFileToService {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content,

        [Parameter(Mandatory = $true)]
        [string] $ServiceId
    )

    $lineEnding = Get-ComposeLineEnding -Content $Content
    $networkIndex = Find-ServiceInsertionIndex -Content $Content -ServiceId $ServiceId -Section "networks"
    $envFileBlock = "    env_file:${lineEnding}      - .env${lineEnding}"
    return $Content.Insert($networkIndex, $envFileBlock)
}

function Add-VllmPrincipalService {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content
    )

    $lineEnding = Get-ComposeLineEnding -Content $Content
    $injectedServiceLines = @(
        "  vllm-main:",
        "    image: vllm/vllm-openai:0.8.5",
        "    expose:",
        "      - `"8443`"",
        "    networks:",
        "      - core",
        "    healthcheck:",
        "      test:",
        "        - CMD-SHELL",
        "        - `"test -f /tmp/health`"",
        "      interval: 30s",
        "      timeout: 5s",
        "      retries: 3",
        "      start_period: 10s",
        ""
    )
    $injectedService = $injectedServiceLines -join $lineEnding

    $rootNetworksMarker = "networks:${lineEnding}  edge:"
    if (-not $Content.Contains($rootNetworksMarker)) {
        throw "Bloc networks racine absent du fixture."
    }

    return $Content.Replace($rootNetworksMarker, "$injectedService${lineEnding}$rootNetworksMarker")
}

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
    throw "Validateur Compose local M-002 absent: scripts/validate_local_compose.ps1"
}

if (-not (Test-Path -LiteralPath $composePath -PathType Leaf)) {
    throw "Compose local M-002 absent: deploy/local-compose/compose.yaml"
}

if (-not (Test-Path -LiteralPath $caddyfilePath -PathType Leaf)) {
    throw "Caddyfile local M-002 absent: deploy/local-compose/Caddyfile"
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
    $validCaddyfile = Get-Content -Raw -Encoding UTF8 -LiteralPath $caddyfilePath

    Assert-OutputContains -Output $validCaddyfile -Expected "localhost:8443" -Message "Le Caddyfile doit nommer localhost pour le TLS interne."
    Assert-OutputContains -Output $validCaddyfile -Expected "skip_install_trust" -Message "Le Caddyfile ne doit pas tenter d'installer la CA locale dans le conteneur."
    Assert-OutputContains -Output $validCaddyfile -Expected "handle /health" -Message "La santé edge-gateway doit rester traitée par Caddy."
    if ($validCaddyfile -match "(?m)^:8443\s*\{") {
        throw "Le Caddyfile ne doit pas déclarer le site TLS sans hostname."
    }

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

    $applicationEnvironmentPath = New-TemporaryCompose -Name "gateway-application-environment" -Content (
        Add-ApplicationEnvironmentVariable -Content $validCompose -ServiceId "llm-gateway" -Name "GEMMA_MODEL_REVISION"
    )
    $applicationEnvironmentResult = Invoke-LocalComposeValidator -ComposePath $applicationEnvironmentPath
    Assert-ExitCode -Actual $applicationEnvironmentResult.ExitCode -Expected 1 -Message "Le gateway ne doit pas recevoir de configuration applicative par environment."
    Assert-OutputContains -Output $applicationEnvironmentResult.Output -Expected "Variable applicative interdite pour service llm-gateway: GEMMA_MODEL_REVISION" -Message "La clé applicative interdite doit être nommée."

    $envFilePath = New-TemporaryCompose -Name "worker-env-file" -Content (
        Add-EnvFileToService -Content $validCompose -ServiceId "worker-research"
    )
    $envFileResult = Invoke-LocalComposeValidator -ComposePath $envFilePath
    Assert-ExitCode -Actual $envFileResult.ExitCode -Expected 1 -Message "Un env_file ne doit pas être accepté."
    Assert-OutputContains -Output $envFileResult.Output -Expected "env_file interdit pour service worker-research" -Message "Le service avec env_file doit être nommé."

    $workerEgressPath = New-TemporaryCompose -Name "worker-spark-egress" -Content (Add-SparkEgressToService -Content $validCompose -ServiceId "worker-documents")
    $workerEgressResult = Invoke-LocalComposeValidator -ComposePath $workerEgressPath
    Assert-ExitCode -Actual $workerEgressResult.ExitCode -Expected 1 -Message "Un worker ne doit pas joindre spark-egress."
    Assert-OutputContains -Output $workerEgressResult.Output -Expected "spark-egress interdit pour service: worker-documents" -Message "Le réseau interdit doit nommer le service."
}
finally {
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
}

Write-Host "Test d'acceptation Compose local M-002: OK"
