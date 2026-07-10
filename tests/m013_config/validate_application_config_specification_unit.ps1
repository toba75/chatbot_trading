$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$schemaPath = Join-Path $repoRoot "config/application.schema.json"
$examplePath = Join-Path $repoRoot "config/application.example.yaml"

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

function Assert-RequiredField {
    param(
        [Parameter(Mandatory = $true)]
        [object] $SchemaNode,

        [Parameter(Mandatory = $true)]
        [string] $Field,

        [Parameter(Mandatory = $true)]
        [string] $Path
    )

    if ($SchemaNode.required -notcontains $Field) {
        throw "Clé obligatoire absente du schéma: $Path.$Field"
    }
    if (-not $SchemaNode.properties.PSObject.Properties.Name.Contains($Field)) {
        throw "Propriété obligatoire non déclarée dans le schéma: $Path.$Field"
    }
}

function Assert-ObjectNodeStrict {
    param(
        [Parameter(Mandatory = $true)]
        [object] $SchemaNode,

        [Parameter(Mandatory = $true)]
        [string] $Path
    )

    if ($SchemaNode.type -ne "object") {
        throw "Noeud de schéma non objet: $Path"
    }
    if ($SchemaNode.additionalProperties -ne $false) {
        throw "Noeud de schéma permissif interdit: $Path"
    }
}

function Assert-Ref {
    param(
        [Parameter(Mandatory = $true)]
        [object] $SchemaNode,

        [Parameter(Mandatory = $true)]
        [string] $ExpectedRef,

        [Parameter(Mandatory = $true)]
        [string] $Path
    )

    $actualRef = $SchemaNode.'$ref'
    if ($actualRef -ne $ExpectedRef) {
        throw "Référence de schéma invalide pour $Path. Attendu: $ExpectedRef. Obtenu: $actualRef"
    }
}

function Assert-NoHistoricalEnvironmentKey {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content
    )

    foreach ($historicalKey in @("GEMMA_BASE_URL", "GEMMA_MODEL", "GEMMA_MODEL_REVISION", "GEMMA_RUNTIME_VERSION", "DATABASE_URL", "QDRANT_URL", "LLM_GATEWAY_URL")) {
        if ($Content.Contains($historicalKey)) {
            throw "Clé d'environnement historique non migrée dans un artefact applicatif: $historicalKey"
        }
    }
}

Assert-FileExists -Path $schemaPath -Message "Schéma de configuration absent: config/application.schema.json"
Assert-FileExists -Path $examplePath -Message "Exemple de configuration absent: config/application.example.yaml"

$schemaContent = (Get-Content -Raw -Encoding UTF8 -LiteralPath $schemaPath).TrimStart([char] 0xFEFF)
$schema = $schemaContent | ConvertFrom-Json
$exampleContent = (Get-Content -Raw -Encoding UTF8 -LiteralPath $examplePath).TrimStart([char] 0xFEFF)

# Section manquante: chaque section racine attendue est obligatoire et les objets sont stricts.
Assert-ObjectNodeStrict -SchemaNode $schema -Path "application"
foreach ($section in @("deployment", "services", "models", "paths", "security", "quality_gates", "observability", "runtime")) {
    Assert-RequiredField -SchemaNode $schema -Field $section -Path "application"
    Assert-ObjectNodeStrict -SchemaNode $schema.properties.$section -Path "application.$section"
}
Assert-RequiredField -SchemaNode $schema.properties.models -Field "llm" -Path "application.models"
Assert-ObjectNodeStrict -SchemaNode $schema.properties.models.properties.llm -Path "application.models.llm"

# Clé obligatoire absente: les valeurs qui pilotent le démarrage doivent être requises explicitement.
$requiredKeyPaths = @(
    @{ Node = $schema.properties.deployment; Field = "topology"; Path = "application.deployment" },
    @{ Node = $schema.properties.deployment; Field = "hosts"; Path = "application.deployment" },
    @{ Node = $schema.properties.services; Field = "postgres"; Path = "application.services" },
    @{ Node = $schema.properties.services; Field = "qdrant"; Path = "application.services" },
    @{ Node = $schema.properties.services; Field = "llm_gateway"; Path = "application.services" },
    @{ Node = $schema.properties.models.properties.llm; Field = "served_model_name"; Path = "application.models.llm" },
    @{ Node = $schema.properties.models.properties.llm; Field = "model_revision"; Path = "application.models.llm" },
    @{ Node = $schema.properties.models.properties.llm; Field = "runtime_version"; Path = "application.models.llm" },
    @{ Node = $schema.properties.security; Field = "secrets"; Path = "application.security" },
    @{ Node = $schema.properties.runtime; Field = "timeouts"; Path = "application.runtime" }
)

foreach ($requiredKeyPath in $requiredKeyPaths) {
    Assert-RequiredField -SchemaNode $requiredKeyPath.Node -Field $requiredKeyPath.Field -Path $requiredKeyPath.Path
}

# Placeholder: les chaînes libres obligatoires partagent une définition qui refuse vide et TO_BE_FILLED.
$stringDefinition = $schema.'$defs'.nonEmptyNonPlaceholderString
if ($stringDefinition.type -ne "string") {
    throw "Définition stricte des chaînes absente."
}
if ($stringDefinition.minLength -ne 1) {
    throw "Les chaînes obligatoires doivent refuser la valeur vide."
}
if ($stringDefinition.not.enum -notcontains "") {
    throw "La valeur vide doit être explicitement interdite."
}
if ($stringDefinition.not.enum -notcontains "TO_BE_FILLED") {
    throw "Le placeholder TO_BE_FILLED doit être explicitement interdit."
}

Assert-Ref -SchemaNode $schema.properties.models.properties.llm.properties.served_model_name -ExpectedRef "#/$defs/nonEmptyNonPlaceholderString" -Path "application.models.llm.served_model_name"
Assert-Ref -SchemaNode $schema.properties.models.properties.llm.properties.model_revision -ExpectedRef "#/$defs/nonEmptyNonPlaceholderString" -Path "application.models.llm.model_revision"
Assert-Ref -SchemaNode $schema.properties.models.properties.llm.properties.runtime_version -ExpectedRef "#/$defs/nonEmptyNonPlaceholderString" -Path "application.models.llm.runtime_version"

if ($exampleContent.Contains("TO_BE_FILLED")) {
    throw "L'exemple de configuration contient un placeholder interdit."
}

# Secret en clair: seuls des chemins de secrets sont acceptés.
$secretsNode = $schema.properties.security.properties.secrets
Assert-ObjectNodeStrict -SchemaNode $secretsNode -Path "application.security.secrets"
foreach ($secretPath in @("postgres_password_path", "llm_gateway_api_key_path", "tls_ca_certificate_path")) {
    Assert-RequiredField -SchemaNode $secretsNode -Field $secretPath -Path "application.security.secrets"
    Assert-Ref -SchemaNode $secretsNode.properties.$secretPath -ExpectedRef "#/$defs/secretPath" -Path "application.security.secrets.$secretPath"
}

foreach ($forbiddenSecretProperty in @("password", "token", "api_key", "secret", "secret_value")) {
    if ($schemaContent -match ('"' + [regex]::Escape($forbiddenSecretProperty) + '"')) {
        throw "Propriété de secret en clair interdite dans le schéma: $forbiddenSecretProperty"
    }
}

foreach ($forbiddenExampleToken in @("password:", "token:", "api_key:", "secret_value:")) {
    if ($exampleContent.Contains($forbiddenExampleToken)) {
        throw "Secret en clair interdit dans l'exemple: $forbiddenExampleToken"
    }
}

# Clé environnement historique non migrée: le schéma et l'exemple ne publient aucune ancienne entrée.
Assert-NoHistoricalEnvironmentKey -Content $schemaContent
Assert-NoHistoricalEnvironmentKey -Content $exampleContent

# Chemin secret absent: la définition impose un chemin relatif ou absolu non vide vers un fichier monté hors Git.
if ($schema.'$defs'.secretPath.type -ne "string") {
    throw "Définition secretPath absente."
}
if ($schema.'$defs'.secretPath.minLength -ne 1) {
    throw "Un chemin de secret vide doit être refusé."
}
if ($schema.'$defs'.secretPath.not.enum -notcontains "TO_BE_FILLED") {
    throw "Un chemin de secret placeholder doit être refusé."
}
foreach ($exampleSecretPath in @("config/secrets/local/postgres_password", "config/secrets/local/llm_gateway_api_key", "config/secrets/local/tls_ca_certificate.pem")) {
    if (-not $exampleContent.Contains($exampleSecretPath)) {
        throw "Chemin de secret attendu absent de l'exemple: $exampleSecretPath"
    }
}

Write-Host "Tests unitaires du contrat de configuration applicative: OK"
