$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m013_config_environment.ps1"
$temporaryRoot = Join-Path $repoRoot (".tmp/ost_m013_config_environment_acceptance_" + [System.Guid]::NewGuid().ToString("N"))

function Invoke-EnvironmentValidator {
    param(
        [Parameter(Mandatory = $true)]
        [string] $RootPath
    )

    if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
        throw "Validateur environnement M13-config absent: scripts/validate_m013_config_environment.ps1"
    }

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $validatorPath -RootPath $RootPath 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    return [pscustomobject] @{
        ExitCode = $exitCode
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

function New-FixtureFile {
    param(
        [Parameter(Mandatory = $true)]
        [string] $RelativePath,

        [Parameter(Mandatory = $true)]
        [string] $Content
    )

    $path = Join-Path $temporaryRoot $RelativePath
    $directory = Split-Path -Parent $path
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
    Set-Content -Encoding UTF8 -LiteralPath $path -Value $Content
    return $path
}

function Assert-RejectedFixture {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name,

        [Parameter(Mandatory = $true)]
        [string] $RelativePath,

        [Parameter(Mandatory = $true)]
        [string] $Content,

        [Parameter(Mandatory = $true)]
        [string] $ExpectedFragment
    )

    if (Test-Path -LiteralPath $temporaryRoot) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Path $temporaryRoot | Out-Null
    New-FixtureFile -RelativePath $RelativePath -Content $Content | Out-Null

    $result = Invoke-EnvironmentValidator -RootPath $temporaryRoot
    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "La fixture $Name doit être refusée."
    Assert-OutputContains -Output $result.Output -Expected "CONFIG_ENV_INPUT_REJECTED" -Message "La fixture $Name doit produire le code public attendu."
    Assert-OutputContains -Output $result.Output -Expected $ExpectedFragment -Message "La fixture $Name doit nommer la cause."
}

try {
    # Given la base courante a migré vers config/application.yaml.
    # When la gate M13-config inspecte le dépôt.
    # Then aucune entrée environnement applicative réelle n'est acceptée.
    $validResult = Invoke-EnvironmentValidator -RootPath $repoRoot
    Assert-ExitCode -Actual $validResult.ExitCode -Expected 0 -Message "Le dépôt courant doit être GREEN pour la gate environnement M13-config."
    Assert-OutputContains -Output $validResult.Output -Expected "Gate environnement M13-config GREEN" -Message "Le validateur doit annoncer le GREEN."

    $previousDatabaseUrl = $env:DATABASE_URL
    try {
        $env:DATABASE_URL = "postgresql://pollution/interdite"
        $pollutedResult = Invoke-EnvironmentValidator -RootPath $repoRoot
    }
    finally {
        if ($null -eq $previousDatabaseUrl) {
            Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
        }
        else {
            $env:DATABASE_URL = $previousDatabaseUrl
        }
    }
    Assert-ExitCode -Actual $pollutedResult.ExitCode -Expected 1 -Message "Une variable homonyme shell doit être refusée."
    Assert-OutputContains -Output $pollutedResult.Output -Expected "CONFIG_ENV_INPUT_REJECTED" -Message "Le rejet shell doit porter le code public attendu."
    Assert-OutputContains -Output $pollutedResult.Output -Expected "DATABASE_URL" -Message "Le rejet shell doit nommer la clé homonyme."

    Assert-RejectedFixture `
        -Name "os.environ applicatif" `
        -RelativePath "app/platform/bad_runtime.py" `
        -Content "import os`nDATABASE_URL = os.environ['DATABASE_URL']`n" `
        -ExpectedFragment "app/platform/bad_runtime.py:2"

    Assert-RejectedFixture `
        -Name "getenv applicatif" `
        -RelativePath "app/platform/bad_getenv.py" `
        -Content "from os import getenv`nvalue = getenv('QDRANT_URL')`n" `
        -ExpectedFragment "QDRANT_URL"

    Assert-RejectedFixture `
        -Name "process.env applicatif" `
        -RelativePath "app/platform/bad_frontend.js" `
        -Content "const gateway = process.env.LLM_GATEWAY_URL;`n" `
        -ExpectedFragment "process.env"

    Assert-RejectedFixture `
        -Name "env_file Compose" `
        -RelativePath "deploy/local-compose/compose.yaml" `
        -Content "services:`n  worker-research:`n    env_file:`n      - .env`n" `
        -ExpectedFragment "env_file"

    Assert-RejectedFixture `
        -Name "environment applicatif Compose" `
        -RelativePath "deploy/local-compose/compose.yaml" `
        -Content "services:`n  orchestrator-api:`n    environment:`n      DATABASE_URL: postgresql://interdit`n" `
        -ExpectedFragment "DATABASE_URL"

    Assert-RejectedFixture `
        -Name "documentation exploitation polluée" `
        -RelativePath "docs/runbooks/exploitation_locale.md" `
        -Content "# Runbook`nPrécondition: fournir GEMMA_MODEL_REVISION dans le shell.`n" `
        -ExpectedFragment "docs/runbooks/exploitation_locale.md:2"
}
finally {
    if (Test-Path -LiteralPath $temporaryRoot) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}

Write-Host "Test d'acceptation rejet environnement M13-config: OK"
