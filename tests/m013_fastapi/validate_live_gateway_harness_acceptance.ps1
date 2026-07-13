$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$gatePath = Join-Path $repoRoot "scripts\validate_m013_fastapi.ps1"
$harnessPath = Join-Path $repoRoot "scripts\m013_fastapi_live_gateway.ps1"
if (-not (Test-Path -LiteralPath $harnessPath -PathType Leaf)) {
    throw "M013_FASTAPI_LIVE_GATEWAY_HARNESS_REQUIRED"
}

$gateSource = Get-Content -Raw -Encoding UTF8 $gatePath
foreach ($marker in @(
    'Start-M013FastApiLiveGateway',
    'Stop-M013FastApiLiveGateway',
    'M013_FASTAPI_LLM_GATEWAY_REUSED',
    'M013_FASTAPI_LLM_GATEWAY_STARTED',
    'M013_FASTAPI_GATEWAY_ENDPOINT'
)) {
    if (-not $gateSource.Contains($marker)) {
        throw "Cycle de vie llm-gateway absent de la gate Live: $marker"
    }
}

. (Join-Path $PSScriptRoot "resolve_m013_fastapi_python.ps1")
. (Join-Path $PSScriptRoot "resolve_m013_fastapi_live_gateway.ps1")
. $harnessPath
$python = Resolve-M013FastApiPython -RepoRoot $repoRoot

$previousGatewayUrl = [System.Environment]::GetEnvironmentVariable(
    "M013_FASTAPI_GATEWAY_ENDPOINT",
    "Process"
)
$env:M013_FASTAPI_GATEWAY_ENDPOINT = "http://127.0.0.1:8090"
if ((Resolve-M013FastApiLiveGatewayUrl) -ne "http://127.0.0.1:8090") {
    throw "La résolution explicite de l'URL gateway Live a dérivé."
}
$env:M013_FASTAPI_GATEWAY_ENDPOINT = "http://service-inattendu:8090"
try {
    Resolve-M013FastApiLiveGatewayUrl | Out-Null
    throw "Une URL gateway non loopback aurait dû être refusée."
}
catch {
        if (-not $_.Exception.Message.Contains("M013_FASTAPI_GATEWAY_ENDPOINT_INVALID")) {
        throw
    }
}
if ($null -eq $previousGatewayUrl) {
    Remove-Item Env:M013_FASTAPI_GATEWAY_ENDPOINT
}
else {
    $env:M013_FASTAPI_GATEWAY_ENDPOINT = $previousGatewayUrl
}

function Get-FreeTcpPort {
    $listener = [System.Net.Sockets.TcpListener]::new(
        [System.Net.IPAddress]::Loopback,
        0
    )
    $listener.Start()
    try {
        return ([System.Net.IPEndPoint] $listener.LocalEndpoint).Port
    }
    finally {
        $listener.Stop()
    }
}

function New-GatewayConfig([string] $Root, [int] $Port) {
    $source = Get-Content -Raw -Encoding UTF8 (Join-Path $repoRoot "config\application.example.yaml")
    $content = $source.Replace("http://llm-gateway:8090", "http://127.0.0.1:$Port")
    $content = $content.Replace("    port: 8090", "    port: $Port")
    $path = Join-Path $Root "application-$Port.yaml"
    [System.IO.File]::WriteAllText($path, $content, [System.Text.UTF8Encoding]::new($false))
    return $path
}

function Wait-PortClosed([int] $Port) {
    for ($attempt = 0; $attempt -lt 100; $attempt++) {
        if (-not (Test-M013FastApiTcpPortOpen -Port $Port)) {
            return
        }
        Start-Sleep -Milliseconds 50
    }
    throw "Le port $Port reste ouvert après nettoyage du gateway possédé."
}

$temporaryRoot = Join-Path (
    [System.IO.Path]::GetTempPath()
) ("m013-fastapi-live-gateway-contract-" + [guid]::NewGuid().ToString("N"))
$ownedGateway = $null
$externalGateway = $null
$unexpectedListener = $null
New-Item -ItemType Directory -Path $temporaryRoot -Force | Out-Null
try {
    # Given un port libre, When la harness démarre le gateway réel,
    # Then elle en possède le processus et le ferme explicitement.
    $ownedPort = Get-FreeTcpPort
    $ownedConfig = New-GatewayConfig -Root $temporaryRoot -Port $ownedPort
    $ownedGateway = Start-M013FastApiLiveGateway `
        -PythonPath $python `
        -RepoRoot $repoRoot `
        -TemporaryRoot $temporaryRoot `
        -ConfigPath $ownedConfig `
        -Port $ownedPort
    if (-not $ownedGateway.Owned -or $null -eq $ownedGateway.Process) {
        throw "La harness doit posséder le gateway qu'elle a démarré."
    }
    Stop-M013FastApiLiveGateway -Gateway $ownedGateway
    Wait-PortClosed -Port $ownedPort
    $ownedGateway = $null

    # Given un vrai gateway déjà prêt, When la harness inspecte son port,
    # Then elle le réutilise explicitement sans jamais arrêter son processus.
    $reusedPort = Get-FreeTcpPort
    $reusedConfig = New-GatewayConfig -Root $temporaryRoot -Port $reusedPort
    $externalStdout = Join-Path $temporaryRoot "external.stdout.log"
    $externalStderr = Join-Path $temporaryRoot "external.stderr.log"
    $externalGateway = Start-Process -FilePath $python `
        -ArgumentList @(
            "-B", "-m", "app.platform.local_runtime", "serve-http",
            "llm-gateway", "$reusedPort", "--config", $reusedConfig
        ) `
        -WorkingDirectory $repoRoot `
        -RedirectStandardOutput $externalStdout `
        -RedirectStandardError $externalStderr `
        -WindowStyle Hidden `
        -PassThru
    for ($attempt = 0; $attempt -lt 100; $attempt++) {
        if ($externalGateway.HasExited) {
            throw "Le gateway externe conforme a quitté prématurément."
        }
        if (Test-M013FastApiGatewayReady -Port $reusedPort) {
            break
        }
        Start-Sleep -Milliseconds 50
    }
    if (-not (Test-M013FastApiGatewayReady -Port $reusedPort)) {
        throw "Le gateway externe conforme n'est pas prêt."
    }
    $reusedGateway = Start-M013FastApiLiveGateway `
        -PythonPath $python `
        -RepoRoot $repoRoot `
        -TemporaryRoot $temporaryRoot `
        -ConfigPath $reusedConfig `
        -Port $reusedPort
    if ($reusedGateway.Owned -or $null -ne $reusedGateway.Process) {
        throw "Un gateway préexistant conforme ne doit jamais devenir possédé."
    }
    Stop-M013FastApiLiveGateway -Gateway $reusedGateway
    if ($externalGateway.HasExited -or -not (Test-M013FastApiGatewayReady -Port $reusedPort)) {
        throw "La réutilisation a arrêté ou altéré le gateway préexistant."
    }

    # Given un service inattendu sur le port, When la harness l'inspecte,
    # Then elle refuse le port sans toucher au listener étranger.
    $unexpectedPort = Get-FreeTcpPort
    $unexpectedListener = [System.Net.Sockets.TcpListener]::new(
        [System.Net.IPAddress]::Loopback,
        $unexpectedPort
    )
    $unexpectedListener.Start()
    try {
        Start-M013FastApiLiveGateway `
            -PythonPath $python `
            -RepoRoot $repoRoot `
            -TemporaryRoot $temporaryRoot `
            -ConfigPath (New-GatewayConfig -Root $temporaryRoot -Port $unexpectedPort) `
            -Port $unexpectedPort | Out-Null
        throw "Le service inattendu aurait dû être refusé."
    }
    catch {
        if (-not $_.Exception.Message.Contains("M013_FASTAPI_GATEWAY_LISTENER_OCCUPIED_UNEXPECTED")) {
            throw
        }
    }
    if (-not $unexpectedListener.Server.IsBound) {
        throw "La harness a touché au listener inattendu."
    }
}
finally {
    if ($null -ne $ownedGateway) {
        Stop-M013FastApiLiveGateway -Gateway $ownedGateway
    }
    if ($null -ne $externalGateway -and -not $externalGateway.HasExited) {
        Stop-Process -Id $externalGateway.Id
        $externalGateway.WaitForExit(10000) | Out-Null
    }
    if ($null -ne $unexpectedListener) {
        $unexpectedListener.Stop()
    }
    if (Test-Path -LiteralPath $temporaryRoot) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}

Write-Host "Harness Live llm-gateway: ownership, réutilisation et nettoyage OK"
