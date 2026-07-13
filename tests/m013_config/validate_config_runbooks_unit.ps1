$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")

$documents = @(
    @{
        Label = "configuration applicative"
        Path = "docs/runbooks/configuration_applicative.md"
        RequiredMarkers = @(
            "config/application.example.yaml",
            "config/application.yaml",
            "config/application.schema.json",
            "scripts\validate_m013_config_environment.ps1",
            "scripts\validate_local_compose.ps1",
            "scripts\validate_network_boundary.ps1",
            "-ApplicationConfigPath .\config\application.yaml",
            "configuration_hash",
            "CONFIG_ENV_INPUT_REJECTED",
            "CONFIG_SECRET_INLINE_REJECTED"
        )
    },
    @{
        Label = "exploitation locale"
        Path = "docs/runbooks/exploitation_locale.md"
        RequiredMarkers = @(
            "config/application.yaml",
            "--config",
            "scripts\validate_local_compose.ps1",
            "scripts\validate_network_boundary.ps1",
            "-ApplicationConfigPath .\config\application.yaml",
            "hash de configuration"
        )
    },
    @{
        Label = "incidents Spark"
        Path = "docs/runbooks/spark_reseau_incidents.md"
        RequiredMarkers = @(
            "config/application.yaml",
            "services.llm_gateway.spark_endpoint_url",
            "-ApplicationConfigPath .\config\application.yaml",
            "models.llm.model_revision",
            "configuration_hash",
            "LLM_UNAVAILABLE"
        )
    },
    @{
        Label = "certificats Spark"
        Path = "docs/runbooks/certificats_spark.md"
        RequiredMarkers = @(
            "config/application.yaml",
            "services.llm_gateway.tls_mode",
            "security.secrets.tls_ca_certificate_path",
            "-ApplicationConfigPath .\config\application.yaml",
            "secret hors Git",
            "LLM_TLS_CERTIFICATE_INVALID"
        )
    },
    @{
        Label = "README Compose"
        Path = "deploy/local-compose/README.md"
        RequiredMarkers = @(
            "config/application.yaml",
            "deploy/local-compose/application.compose.yaml",
            "--config /workspace/config/application.yaml",
            "./application.compose.yaml:/workspace/config/application.yaml:ro",
            "deploy/local-compose/secrets/",
            "docker compose -f .\deploy\local-compose\compose.yaml up --build"
        )
    }
)

function Get-RepositoryDocument {
    param(
        [Parameter(Mandatory = $true)]
        [string] $RelativePath
    )

    $path = Join-Path $repoRoot $RelativePath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Document requis absent: $RelativePath"
    }

    return (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).TrimStart([char] 0xFEFF)
}

function Assert-Contains {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content,

        [Parameter(Mandatory = $true)]
        [string] $Expected,

        [Parameter(Mandatory = $true)]
        [string] $Label
    )

    if (-not $Content.Contains($Expected)) {
        throw "Marqueur absent ($Label): $Expected"
    }
}

function Assert-NoOperationalEnvironmentInput {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content,

        [Parameter(Mandatory = $true)]
        [string] $Label
    )

    $forbiddenOperationalPatterns = @(
        "export GEMMA_",
        '$env:GEMMA_',
        "set GEMMA_",
        "export DATABASE_URL",
        '$env:DATABASE_URL',
        "set DATABASE_URL",
        "export QDRANT_URL",
        '$env:QDRANT_URL',
        "set QDRANT_URL",
        "export LLM_GATEWAY_URL",
        '$env:LLM_GATEWAY_URL',
        "set LLM_GATEWAY_URL",
        "--env-file",
        "env_file:",
        "environment:`n      DATABASE_URL",
        ".env requis",
        ".env obligatoire"
    )

    foreach ($pattern in $forbiddenOperationalPatterns) {
        if ($Content.Contains($pattern)) {
            throw "Entrée environnement opérationnelle interdite ($Label): $pattern"
        }
    }
}

function Assert-CommandsReferenceExistingFiles {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content,

        [Parameter(Mandatory = $true)]
        [string] $Label
    )

    $matches = [regex]::Matches(
        $Content,
        "-File\s+\.\\(?<path>(?:scripts|tests)\\[A-Za-z0-9_.\\-]+(?:\\[A-Za-z0-9_.\\-]+)*\.ps1)",
        [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
    )

    foreach ($match in $matches) {
        $relativePath = $match.Groups["path"].Value.Replace("\", "/")
        $candidatePath = Join-Path $repoRoot $relativePath
        if (-not (Test-Path -LiteralPath $candidatePath -PathType Leaf)) {
            throw "Commande PowerShell absente ($Label): $relativePath"
        }
    }
}

foreach ($document in $documents) {
    $content = Get-RepositoryDocument -RelativePath $document.Path
    foreach ($marker in $document.RequiredMarkers) {
        Assert-Contains -Content $content -Expected $marker -Label $document.Label
    }
    Assert-NoOperationalEnvironmentInput -Content $content -Label $document.Label
    Assert-CommandsReferenceExistingFiles -Content $content -Label $document.Label
}

$configurationRunbook = Get-RepositoryDocument -RelativePath "docs/runbooks/configuration_applicative.md"
foreach ($requiredPath in @(
    "config/application.example.yaml",
    "config/application.schema.json",
    "deploy/local-compose/compose.yaml",
    "deploy/local-compose/secrets/.gitignore"
)) {
    $absolutePath = Join-Path $repoRoot $requiredPath
    if (-not (Test-Path -LiteralPath $absolutePath)) {
        throw "Chemin référencé absent: $requiredPath"
    }
    Assert-Contains -Content $configurationRunbook -Expected $requiredPath -Label "configuration applicative"
}

Write-Host "Tests unitaires runbooks configuration M13-config: OK"
