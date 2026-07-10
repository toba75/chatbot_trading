$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_local_compose.ps1"
$composePath = Join-Path $repoRoot "deploy/local-compose/compose.yaml"
$temporaryRoot = Join-Path $repoRoot (".tmp/ost_m013_config_compose_acceptance_" + [System.Guid]::NewGuid().ToString("N"))

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

function Add-ApplicationEnvironmentVariable {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content,

        [Parameter(Mandatory = $true)]
        [string] $ServiceId,

        [Parameter(Mandatory = $true)]
        [string] $VariableName
    )

    $lineEnding = Get-ComposeLineEnding -Content $Content
    $serviceMatch = [regex]::Match($Content, "(?m)^  $([regex]::Escape($ServiceId)):\r?\n")
    if (-not $serviceMatch.Success) {
        throw "Service fixture absent: $ServiceId"
    }

    $serviceTail = $Content.Substring($serviceMatch.Index + $serviceMatch.Length)
    $networkMatch = [regex]::Match($serviceTail, "(?m)^    networks:\r?\n")
    if (-not $networkMatch.Success) {
        throw "Point d'insertion fixture absent pour service: $ServiceId"
    }

    $networkIndex = $serviceMatch.Index + $serviceMatch.Length + $networkMatch.Index
    $environmentBlock = "    environment:${lineEnding}      ${VariableName}: `"http://valeur-applicative.local`"${lineEnding}"
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
    $serviceMatch = [regex]::Match($Content, "(?m)^  $([regex]::Escape($ServiceId)):\r?\n")
    if (-not $serviceMatch.Success) {
        throw "Service fixture absent: $ServiceId"
    }

    $serviceTail = $Content.Substring($serviceMatch.Index + $serviceMatch.Length)
    $networkMatch = [regex]::Match($serviceTail, "(?m)^    networks:\r?\n")
    if (-not $networkMatch.Success) {
        throw "Point d'insertion fixture absent pour service: $ServiceId"
    }

    $networkIndex = $serviceMatch.Index + $serviceMatch.Length + $networkMatch.Index
    $envFileBlock = "    env_file:${lineEnding}      - .env${lineEnding}"
    return $Content.Insert($networkIndex, $envFileBlock)
}

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
    throw "Validateur Compose local absent: scripts/validate_local_compose.ps1"
}

if (-not (Test-Path -LiteralPath $composePath -PathType Leaf)) {
    throw "Compose local absent: deploy/local-compose/compose.yaml"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    # Given le fichier config/application.yaml est monté en lecture seule.
    # When la pile locale est validée.
    # Then chaque processus applicatif reçoit --config et aucune valeur applicative
    # n'est transmise par environment ou env_file.
    $validResult = Invoke-LocalComposeValidator -ComposePath $composePath
    Assert-ExitCode -Actual $validResult.ExitCode -Expected 0 -Message "Le Compose M13-config canonique doit être GREEN."
    Assert-OutputContains -Output $validResult.Output -Expected "Compose local M-002 valide" -Message "Le validateur doit annoncer le GREEN Compose."

    $validCompose = Get-Content -Raw -Encoding UTF8 -LiteralPath $composePath

    foreach ($forbiddenText in @(
        "env_file:",
        "DATABASE_URL:",
        "QDRANT_URL:",
        "LLM_GATEWAY_URL:",
        "GEMMA_BASE_URL:",
        "GEMMA_MODEL:",
        "GEMMA_MODEL_REVISION:",
        "GEMMA_RUNTIME_VERSION:"
    )) {
        if ($validCompose.Contains($forbiddenText)) {
            throw "Entrée applicative interdite présente dans le Compose canonique: $forbiddenText"
        }
    }

    $composeServiceIds = @(
        "edge-gateway",
        "ui",
        "orchestrator-api",
        "llm-gateway",
        "postgres",
        "qdrant",
        "granite-docling",
        "embedding-service",
        "reranker-service",
        "worker-documents",
        "worker-research",
        "worker-backtest",
        "backtest-engine"
    )

    foreach ($serviceId in @(
        "ui",
        "orchestrator-api",
        "llm-gateway",
        "granite-docling",
        "embedding-service",
        "reranker-service",
        "worker-documents",
        "worker-research",
        "worker-backtest",
        "backtest-engine"
    )) {
        $lineEnding = Get-ComposeLineEnding -Content $validCompose
        $serviceHeader = "${lineEnding}  ${serviceId}:${lineEnding}"
        $serviceIndex = $validCompose.IndexOf($serviceHeader)
        if ($serviceIndex -lt 0) {
            throw "Service applicatif absent du Compose canonique: $serviceId"
        }

        $nextServiceIndex = $validCompose.Length
        foreach ($candidateServiceId in $composeServiceIds) {
            $candidateHeader = "${lineEnding}  ${candidateServiceId}:${lineEnding}"
            $candidateIndex = $validCompose.IndexOf($candidateHeader, $serviceIndex + $serviceHeader.Length)
            if ($candidateIndex -ge 0 -and $candidateIndex -lt $nextServiceIndex) {
                $nextServiceIndex = $candidateIndex
            }
        }
        $serviceBlock = if ($nextServiceIndex -lt 0) {
            $validCompose.Substring($serviceIndex)
        }
        else {
            $validCompose.Substring($serviceIndex, $nextServiceIndex - $serviceIndex)
        }

        if (-not $serviceBlock.Contains("- --config") -or -not $serviceBlock.Contains("- /workspace/config/application.yaml")) {
            throw "Argument --config absent pour service applicatif: $serviceId"
        }
        if (-not $serviceBlock.Contains("../../config/application.yaml:/workspace/config/application.yaml:ro")) {
            throw "Montage config/application.yaml read-only absent pour service applicatif: $serviceId"
        }
        if (-not $serviceBlock.Contains("../../config/application.schema.json:/workspace/config/application.schema.json:ro")) {
            throw "Montage config/application.schema.json read-only absent pour service applicatif: $serviceId"
        }
        if ($serviceId -eq "llm-gateway" -and -not $serviceBlock.Contains("../../config/secrets/local:/workspace/config/secrets/local:ro")) {
            throw "Montage config/secrets/local read-only absent pour service llm-gateway"
        }
    }

    $environmentPath = New-TemporaryCompose -Name "orchestrator-api-application-environment" -Content (
        Add-ApplicationEnvironmentVariable -Content $validCompose -ServiceId "orchestrator-api" -VariableName "DATABASE_URL"
    )
    $environmentResult = Invoke-LocalComposeValidator -ComposePath $environmentPath
    Assert-ExitCode -Actual $environmentResult.ExitCode -Expected 1 -Message "Une valeur applicative via environment doit être refusée."
    Assert-OutputContains -Output $environmentResult.Output -Expected "Variable applicative interdite pour service orchestrator-api: DATABASE_URL" -Message "Le refus environment doit nommer la clé applicative."

    $envFilePath = New-TemporaryCompose -Name "worker-research-env-file" -Content (
        Add-EnvFileToService -Content $validCompose -ServiceId "worker-research"
    )
    $envFileResult = Invoke-LocalComposeValidator -ComposePath $envFilePath
    Assert-ExitCode -Actual $envFileResult.ExitCode -Expected 1 -Message "Un env_file Compose doit être refusé."
    Assert-OutputContains -Output $envFileResult.Output -Expected "env_file interdit pour service worker-research" -Message "Le refus env_file doit nommer le service."
}
finally {
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
}

Write-Host "Test d'acceptation Compose M13-config: OK"
