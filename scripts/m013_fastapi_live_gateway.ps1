function Test-M013FastApiTcpPortOpen {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateRange(1, 65535)]
        [int] $Port
    )

    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $connection = $client.ConnectAsync([System.Net.IPAddress]::Loopback, $Port)
        if (-not $connection.Wait(250)) {
            return $false
        }
        return $client.Connected
    }
    catch [System.AggregateException] {
        return $false
    }
    catch [System.Net.Sockets.SocketException] {
        return $false
    }
    finally {
        $client.Dispose()
    }
}


function Test-M013FastApiGatewayReady {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateRange(1, 65535)]
        [int] $Port
    )

    try {
        $response = Invoke-RestMethod `
            -Method Get `
            -Uri "http://127.0.0.1:$Port/health" `
            -TimeoutSec 1
    }
    catch {
        return $false
    }
    return (
        $response.service -eq "llm-gateway" -and
        $response.status -eq "ready" -and
        $response.configuration_hash -is [string] -and
        $response.configuration_hash -match '^[0-9a-f]{64}$'
    )
}


function Start-M013FastApiLiveGateway {
    param(
        [Parameter(Mandatory = $true)]
        [string] $PythonPath,

        [Parameter(Mandatory = $true)]
        [string] $RepoRoot,

        [Parameter(Mandatory = $true)]
        [string] $TemporaryRoot,

        [Parameter(Mandatory = $true)]
        [string] $ConfigPath,

        [Parameter(Mandatory = $true)]
        [ValidateRange(1, 65535)]
        [int] $Port
    )

    foreach ($file in @($PythonPath, $ConfigPath)) {
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
            throw "M013_FASTAPI_LLM_GATEWAY_FILE_REQUIRED:$file"
        }
    }
    foreach ($directory in @($RepoRoot, $TemporaryRoot)) {
        if (-not (Test-Path -LiteralPath $directory -PathType Container)) {
            throw "M013_FASTAPI_LLM_GATEWAY_DIRECTORY_REQUIRED:$directory"
        }
    }

    if (Test-M013FastApiTcpPortOpen -Port $Port) {
        if (Test-M013FastApiGatewayReady -Port $Port) {
            return [pscustomobject]@{
                Owned = $false
                Process = $null
                Port = $Port
            }
        }
        throw "M013_FASTAPI_GATEWAY_LISTENER_OCCUPIED_UNEXPECTED:$Port"
    }

    $stdoutPath = Join-Path $TemporaryRoot "llm-gateway.stdout.log"
    $stderrPath = Join-Path $TemporaryRoot "llm-gateway.stderr.log"
    $gatewayProcess = $null
    try {
        $gatewayProcess = Start-Process `
            -FilePath $PythonPath `
            -ArgumentList @(
                "-B",
                "-m",
                "app.platform.local_runtime",
                "serve-http",
                "llm-gateway",
                "$Port",
                "--config",
                $ConfigPath
            ) `
            -WorkingDirectory $RepoRoot `
            -RedirectStandardOutput $stdoutPath `
            -RedirectStandardError $stderrPath `
            -WindowStyle Hidden `
            -PassThru
        for ($attempt = 0; $attempt -lt 120; $attempt++) {
            if ($gatewayProcess.HasExited) {
                throw "M013_FASTAPI_LLM_GATEWAY_START_FAILED:$($gatewayProcess.ExitCode)"
            }
            if (Test-M013FastApiGatewayReady -Port $Port) {
                return [pscustomobject]@{
                    Owned = $true
                    Process = $gatewayProcess
                    Port = $Port
                }
            }
            Start-Sleep -Milliseconds 100
        }
        throw "M013_FASTAPI_LLM_GATEWAY_NOT_READY:$Port"
    }
    catch {
        if ($null -ne $gatewayProcess -and -not $gatewayProcess.HasExited) {
            Stop-Process -Id $gatewayProcess.Id
            if (-not $gatewayProcess.WaitForExit(10000)) {
                throw "M013_FASTAPI_LLM_GATEWAY_CLEANUP_FAILED:$($gatewayProcess.Id)"
            }
        }
        throw
    }
}


function Stop-M013FastApiLiveGateway {
    param(
        [Parameter(Mandatory = $true)]
        [psobject] $Gateway
    )

    if (
        $Gateway.Owned -isnot [bool] -or
        $Gateway.Port -isnot [int] -or
        $Gateway.Port -lt 1 -or
        $Gateway.Port -gt 65535
    ) {
        throw "M013_FASTAPI_LLM_GATEWAY_OWNERSHIP_INVALID"
    }
    if (-not $Gateway.Owned) {
        if ($null -ne $Gateway.Process) {
            throw "M013_FASTAPI_LLM_GATEWAY_REUSED_PROCESS_FORBIDDEN"
        }
        return
    }
    if ($Gateway.Process -isnot [System.Diagnostics.Process]) {
        throw "M013_FASTAPI_LLM_GATEWAY_OWNED_PROCESS_REQUIRED"
    }
    if (-not $Gateway.Process.HasExited) {
        Stop-Process -Id $Gateway.Process.Id
        if (-not $Gateway.Process.WaitForExit(10000)) {
            throw "M013_FASTAPI_LLM_GATEWAY_CLEANUP_FAILED:$($Gateway.Process.Id)"
        }
    }
}
