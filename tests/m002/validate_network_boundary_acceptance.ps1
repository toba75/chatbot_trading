$ErrorActionPreference = "Stop"
$eAcute = [char] 0x00E9
$eGrave = [char] 0x00E8

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_network_boundary.ps1"
$composePath = Join-Path $repoRoot "deploy/local-compose/compose.yaml"
$topologyPath = Join-Path $repoRoot "app/platform/topology_registry.json"
$sparkFirewallPath = Join-Path $repoRoot "deploy/spark-firewall/network-boundary.json"
$temporaryRoot = Join-Path $repoRoot (".tmp/ost_m002_network_boundary_acceptance_" + [System.Guid]::NewGuid().ToString("N"))

function Invoke-NetworkBoundaryValidator {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ComposePath,

        [Parameter(Mandatory = $true)]
        [string] $TopologyPath,

        [Parameter(Mandatory = $true)]
        [string] $SparkFirewallPath
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & powershell `
            -NoProfile `
            -ExecutionPolicy Bypass `
            -File $validatorPath `
            -ComposePath $ComposePath `
            -TopologyPath $TopologyPath `
            -SparkFirewallPath $SparkFirewallPath `
            2>&1
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

function New-TemporaryFile {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name,

        [Parameter(Mandatory = $true)]
        [string] $Content
    )

    $path = Join-Path $temporaryRoot $Name
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

    $publishedPort = "${lineEnding}    ports:${lineEnding}      - `"0.0.0.0:9191:9191`"${lineEnding}"
    return $Content.Insert($serviceMatch.Index + $serviceMatch.Length, $publishedPort)
}

function Add-ProfilePublishedPortToService {
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

    $publishedPort = "${lineEnding}    profiles:${lineEnding}      - debug${lineEnding}    ports:${lineEnding}      - `"127.0.0.1:6333:6333`"${lineEnding}"
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
    $environmentBlock = "    environment:${lineEnding}      ${Name}: `"false`"${lineEnding}"
    return $Content.Insert($networkIndex, $environmentBlock)
}

function Replace-FirewallText {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content,

        [Parameter(Mandatory = $true)]
        [string] $ExpectedText,

        [Parameter(Mandatory = $true)]
        [string] $ReplacementText
    )

    if (-not $Content.Contains($ExpectedText)) {
        throw "Texte fixture pare-feu absent: $ExpectedText"
    }

    return $Content.Replace($ExpectedText, $ReplacementText)
}

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
    throw "Validateur frontière réseau M-002 absent: scripts/validate_network_boundary.ps1"
}

if (-not (Test-Path -LiteralPath $composePath -PathType Leaf)) {
    throw "Compose local M-002 absent: deploy/local-compose/compose.yaml"
}

if (-not (Test-Path -LiteralPath $topologyPath -PathType Leaf)) {
    throw "Registre de topologie M-002 absent: app/platform/topology_registry.json"
}

if (-not (Test-Path -LiteralPath $sparkFirewallPath -PathType Leaf)) {
    throw "Artefact pare-feu Spark M-002 absent: deploy/spark-firewall/network-boundary.json"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    # Given la stack locale et le service vLLM Spark sont configurés.
    # When les règles réseau M-002 sont validées.
    # Then seul llm-gateway peut joindre spark-inference et aucun stockage
    # local n'est accessible hors réseau Docker privé.
    $validResult = Invoke-NetworkBoundaryValidator `
        -ComposePath $composePath `
        -TopologyPath $topologyPath `
        -SparkFirewallPath $sparkFirewallPath
    Assert-ExitCode -Actual $validResult.ExitCode -Expected 0 -Message "La frontière réseau canonique doit être GREEN."
    Assert-OutputContains -Output $validResult.Output -Expected "M-002 valide" -Message "Le validateur doit annoncer le GREEN réseau."

    $validCompose = Get-Content -Raw -Encoding UTF8 -LiteralPath $composePath
    $validFirewall = Get-Content -Raw -Encoding UTF8 -LiteralPath $sparkFirewallPath

    $postgresPublicPath = New-TemporaryFile `
        -Name "postgres-public.yaml" `
        -Content (Add-PublishedPortToService -Content $validCompose -ServiceId "postgres")
    $postgresPublicResult = Invoke-NetworkBoundaryValidator `
        -ComposePath $postgresPublicPath `
        -TopologyPath $topologyPath `
        -SparkFirewallPath $sparkFirewallPath
    Assert-ExitCode -Actual $postgresPublicResult.ExitCode -Expected 1 -Message "PostgreSQL ne doit pas publier de port."
    Assert-OutputContains -Output $postgresPublicResult.Output -Expected "Port public interdit pour stockage local: postgres" -Message "Le stockage exposé doit être nommé."

    $qdrantDebugProfilePath = New-TemporaryFile `
        -Name "qdrant-debug-profile.yaml" `
        -Content (Add-ProfilePublishedPortToService -Content $validCompose -ServiceId "qdrant")
    $qdrantDebugProfileResult = Invoke-NetworkBoundaryValidator `
        -ComposePath $qdrantDebugProfilePath `
        -TopologyPath $topologyPath `
        -SparkFirewallPath $sparkFirewallPath
    Assert-ExitCode -Actual $qdrantDebugProfileResult.ExitCode -Expected 1 -Message "Un profil Compose ne doit pas publier Qdrant."
    Assert-OutputContains -Output $qdrantDebugProfileResult.Output -Expected "Profil Compose avec port public interdit pour service interne: qdrant" -Message "Le profil exposant Qdrant doit être refusé."

    $workerEgressPath = New-TemporaryFile `
        -Name "worker-spark-egress.yaml" `
        -Content (Add-SparkEgressToService -Content $validCompose -ServiceId "worker-research")
    $workerEgressResult = Invoke-NetworkBoundaryValidator `
        -ComposePath $workerEgressPath `
        -TopologyPath $topologyPath `
        -SparkFirewallPath $sparkFirewallPath
    Assert-ExitCode -Actual $workerEgressResult.ExitCode -Expected 1 -Message "Un worker ne doit pas joindre spark-egress."
    Assert-OutputContains -Output $workerEgressResult.Output -Expected "Egress Spark interdit hors llm-gateway: worker-research" -Message "Le service avec egress Spark doit être nommé."

    $gatewayEnvironmentPath = New-TemporaryFile `
        -Name "gateway-application-environment.yaml" `
        -Content (Add-ApplicationEnvironmentVariable -Content $validCompose -ServiceId "llm-gateway" -Name "GEMMA_TLS_VERIFY")
    $gatewayEnvironmentResult = Invoke-NetworkBoundaryValidator `
        -ComposePath $gatewayEnvironmentPath `
        -TopologyPath $topologyPath `
        -SparkFirewallPath $sparkFirewallPath
    Assert-ExitCode -Actual $gatewayEnvironmentResult.ExitCode -Expected 1 -Message "Le gateway ne doit pas recevoir de configuration Spark par environment."
    Assert-OutputContains -Output $gatewayEnvironmentResult.Output -Expected "Variable applicative interdite pour service llm-gateway: GEMMA_TLS_VERIFY" -Message "La variable Spark interdite doit être nommée."

    $extraSparkSourcePath = New-TemporaryFile `
        -Name "spark-extra-source.json" `
        -Content (Replace-FirewallText `
            -Content $validFirewall `
            -ExpectedText '"source_service": "llm-gateway"' `
            -ReplacementText '"source_service": "worker-research"')
    $extraSparkSourceResult = Invoke-NetworkBoundaryValidator `
        -ComposePath $composePath `
        -TopologyPath $topologyPath `
        -SparkFirewallPath $extraSparkSourcePath
    Assert-ExitCode -Actual $extraSparkSourceResult.ExitCode -Expected 1 -Message "Le pare-feu Spark ne doit autoriser que llm-gateway."
    Assert-OutputContains -Output $extraSparkSourceResult.Output -Expected "Source Spark non autoris" -Message "La source Spark non autorisée doit être nommée."

    $tlsIncoherentPath = New-TemporaryFile `
        -Name "spark-tls-incoherent.json" `
        -Content (Replace-FirewallText `
            -Content $validFirewall `
            -ExpectedText '"tls_mode": "disabled"' `
            -ReplacementText '"tls_mode": "ca_bundle"')
    $tlsIncoherentResult = Invoke-NetworkBoundaryValidator `
        -ComposePath $composePath `
        -TopologyPath $topologyPath `
        -SparkFirewallPath $tlsIncoherentPath
    Assert-ExitCode -Actual $tlsIncoherentResult.ExitCode -Expected 1 -Message "Le mode TLS Spark doit rester cohérent."
    Assert-OutputContains -Output $tlsIncoherentResult.Output -Expected "Mode TLS Spark" -Message "L'incohérence TLS doit être explicite."

    $callbackEnabledPath = New-TemporaryFile `
        -Name "spark-callback-enabled.json" `
        -Content (Replace-FirewallText `
            -Content $validFirewall `
            -ExpectedText '"callbacks_from_spark_allowed": false' `
            -ReplacementText '"callbacks_from_spark_allowed": true')
    $callbackEnabledResult = Invoke-NetworkBoundaryValidator `
        -ComposePath $composePath `
        -TopologyPath $topologyPath `
        -SparkFirewallPath $callbackEnabledPath
    Assert-ExitCode -Actual $callbackEnabledResult.ExitCode -Expected 1 -Message "Le Spark ne doit pas rappeler docker-local."
    Assert-OutputContains -Output $callbackEnabledResult.Output -Expected "Callback Spark interdit" -Message "Le callback Spark doit être refusé."

    $browserDirectPath = New-TemporaryFile `
        -Name "spark-browser-direct.json" `
        -Content (Replace-FirewallText `
            -Content $validFirewall `
            -ExpectedText '"browser_direct_access_allowed": false' `
            -ReplacementText '"browser_direct_access_allowed": true')
    $browserDirectResult = Invoke-NetworkBoundaryValidator `
        -ComposePath $composePath `
        -TopologyPath $topologyPath `
        -SparkFirewallPath $browserDirectPath
    Assert-ExitCode -Actual $browserDirectResult.ExitCode -Expected 1 -Message "Le navigateur ne doit pas appeler Spark."
    Assert-OutputContains -Output $browserDirectResult.Output -Expected "navigateur direct au Spark interdit" -Message "L'accès navigateur direct doit être refusé."
}
finally {
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
}

Write-Host "Test d'acceptation fronti$($eGrave)re r$($eAcute)seau M-002: OK"
