$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$specificationPath = Join-Path $repoRoot "docs/specs/m013_config_configuration_applicative.md"
$schemaPath = Join-Path $repoRoot "config/application.schema.json"
$examplePath = Join-Path $repoRoot "config/application.example.yaml"
$eAcute = [char] 0x00E9
$eGrave = [char] 0x00E8

function Assert-FileExists {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw $Message
    }
}

function Read-Utf8Content {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path
    )

    return (Get-Content -Raw -Encoding UTF8 -LiteralPath $Path).TrimStart([char] 0xFEFF)
}

function Assert-Contains {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content,

        [Parameter(Mandatory = $true)]
        [string] $Expected,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if (-not $Content.Contains($Expected)) {
        throw $Message
    }
}

function Assert-NotContains {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content,

        [Parameter(Mandatory = $true)]
        [string] $Forbidden,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if ($Content.Contains($Forbidden)) {
        throw $Message
    }
}

function Assert-JsonSchemaRoot {
    param(
        [Parameter(Mandatory = $true)]
        [string] $SchemaContent
    )

    $schema = $SchemaContent | ConvertFrom-Json
    if ($schema.type -ne "object") {
        throw "Le schéma de configuration doit être un objet JSON Schema racine."
    }
    if ($schema.additionalProperties -ne $false) {
        throw "Le schéma racine doit refuser les clés inconnues."
    }

    $requiredSections = @(
        "deployment",
        "services",
        "models",
        "paths",
        "security",
        "quality_gates",
        "observability",
        "runtime"
    )

    foreach ($section in $requiredSections) {
        if ($schema.required -notcontains $section) {
            throw "Section obligatoire absente du schéma: $section"
        }
        if (-not $schema.properties.PSObject.Properties.Name.Contains($section)) {
            throw "Section non déclarée dans les propriétés du schéma: $section"
        }
    }

    if ($schema.properties.models.required -notcontains "llm") {
        throw "La section models.llm doit être obligatoire."
    }
}

# Given l'exploitant prépare un fichier config/application.yaml.
# When le contrat de configuration est validé.
# Then chaque valeur nécessaire au démarrage est présente dans le fichier, le schéma refuse les absences et aucun fallback environnement n'est décrit.
Assert-FileExists -Path $specificationPath -Message "Spécification de configuration absente: docs/specs/m013_config_configuration_applicative.md"
Assert-FileExists -Path $schemaPath -Message "Schéma de configuration absent: config/application.schema.json"
Assert-FileExists -Path $examplePath -Message "Exemple de configuration absent: config/application.example.yaml"

$specificationContent = Read-Utf8Content -Path $specificationPath
$schemaContent = Read-Utf8Content -Path $schemaPath
$exampleContent = Read-Utf8Content -Path $examplePath

Assert-JsonSchemaRoot -SchemaContent $schemaContent

foreach ($section in @("deployment", "services", "models.llm", "paths", "security", "quality_gates", "observability", "runtime")) {
    Assert-Contains -Content $specificationContent -Expected $section -Message "Section obligatoire absente de la spécification: $section"
}

foreach ($errorCode in @("CONFIG_FILE_REQUIRED", "CONFIG_SCHEMA_INVALID", "CONFIG_KEY_MISSING", "CONFIG_KEY_EMPTY", "CONFIG_ENV_INPUT_REJECTED", "CONFIG_SECRET_INLINE_REJECTED")) {
    Assert-Contains -Content $specificationContent -Expected $errorCode -Message "Erreur publique de configuration absente: $errorCode"
}

foreach ($historicalKey in @("GEMMA_BASE_URL", "GEMMA_MODEL", "GEMMA_MODEL_REVISION", "GEMMA_RUNTIME_VERSION", "DATABASE_URL", "QDRANT_URL", "LLM_GATEWAY_URL")) {
    Assert-Contains -Content $specificationContent -Expected $historicalKey -Message "Mapping historique absent de la spécification: $historicalKey"
    Assert-NotContains -Content $schemaContent -Forbidden $historicalKey -Message "Clé historique interdite dans le schéma: $historicalKey"
    Assert-NotContains -Content $exampleContent -Forbidden $historicalKey -Message "Clé historique interdite dans l'exemple: $historicalKey"
}

foreach ($guardrail in @(
    "Aucune valeur par d$($eAcute)faut implicite",
    "Aucun fallback environnement",
    "Aucun fallback vers `os.environ`, `.env`, `env_file`, `environment:` Compose ou variable syst$($eGrave)me homonyme",
    "Les secrets sont r$($eAcute)f$($eAcute)renc$($eAcute)s par chemin"
)) {
    Assert-Contains -Content $specificationContent -Expected $guardrail -Message "Garde-fou absent de la spécification: $guardrail"
}

foreach ($forbiddenExampleToken in @("TO_BE_FILLED", "change-me", "password:", "token:", "api_key_value:", "secret_value:")) {
    Assert-NotContains -Content $exampleContent -Forbidden $forbiddenExampleToken -Message "L'exemple contient une valeur secrète ou placeholder interdite: $forbiddenExampleToken"
}

Write-Host "Test d'acceptation du contrat de configuration applicative: OK"
