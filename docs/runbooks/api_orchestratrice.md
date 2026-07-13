# Runbook de l'API orchestratrice M13-FastAPI

## Statut et périmètre

- Tâche : `docs/tasks/milestone_013-fastapi/0011_deployer_auditer_api_orchestratrice.md`.
- ADR applicables : ADR-018, ADR-019, ADR-020, ADR-021, ADR-023, ADR-024, ADR-025 et ADR-026.
- Runtime public unique : FastAPI servi par Uvicorn sous l'identité `orchestrator-api`.
- Chemin d'exploitation supporté : Compose construit depuis une archive d'un commit Git complet.
- Configuration conteneur versionnée : `deploy/local-compose/application.compose.yaml` ; aucun fallback environnement.

## Scénario BDD

- Given un clone propre positionné sur un commit Git complet et un secret PostgreSQL local hors Git.
- When l'exploitant exporte ce commit, dérive le schéma, construit et inspecte les images, puis démarre Compose.
- Then PostgreSQL, Qdrant, `llm-gateway`, l'API, deux workers, l'UI et Caddy exécutent exactement les artefacts identifiés par ce commit et ce schéma.

## Préconditions strictes

La recette hôte n'est pas un chemin d'exploitation : PostgreSQL est adressé par le DNS interne `postgres` et le gateway par `llm-gateway`. Il est interdit de lancer directement l'entrée `api` hors de Compose. La commande historique `python -m app.platform.local_runtime serve-http orchestrator-api 8080` reste interdite et retourne `ORCHESTRATOR_LEGACY_RUNTIME_FORBIDDEN`.

Les outils requis sont Git, Docker Engine avec Compose v2, PowerShell et `tar.exe`. Le secret PostgreSQL existe hors Git dans un fichier lisible par l'opérateur. L'identité technique est fixe : base `ostrading`, rôle `ostrading`, URL `postgresql+psycopg://ostrading@postgres/ostrading`. Aucune variable `POSTGRES_DB` ou `POSTGRES_USER` ne peut la redéfinir.

## Export immuable et préparation

Exécuter depuis la racine du dépôt :

```powershell
$edgePort = "8443"
$caddyAdmin = "localhost:2019"
$sourceCommit = (git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $sourceCommit -notmatch '^[0-9a-f]{40}$') { throw "IMAGE_REVISION_MUTABLE_REJECTED" }

$migrationNames = @(git ls-tree -r --name-only $sourceCommit -- deploy/postgres/migrations)
if ($LASTEXITCODE -ne 0 -or $migrationNames.Count -eq 0) { throw "POSTGRES_SCHEMA_VERSION_UNREADABLE" }
$latestMigration = $migrationNames | Sort-Object | Select-Object -Last 1
if ([IO.Path]::GetFileNameWithoutExtension($latestMigration) -notmatch '^(?<version>[0-9]{3})_') { throw "POSTGRES_SCHEMA_VERSION_UNREADABLE" }
$schemaVersion = $Matches.version

function Invoke-ComposeWithTechnicalInterpolation {
    param(
        [Parameter(Mandatory = $true)][scriptblock] $Operation,
        [Parameter(Mandatory = $true)][string] $Revision,
        [Parameter(Mandatory = $true)][string] $PostgresSchemaVersion
    )
    $technicalValues = [ordered] @{
        OST_EDGE_HTTPS_PORT = $edgePort
        CADDY_ADMIN = $caddyAdmin
        OSTRADING_IMAGE_REVISION = $Revision
        OSTRADING_POSTGRES_SCHEMA_VERSION = $PostgresSchemaVersion
    }
    $previousValues = @{}
    foreach ($entry in $technicalValues.GetEnumerator()) {
        $previousValues[$entry.Key] = [System.Environment]::GetEnvironmentVariable($entry.Key, "Process") # Fichier .env interdit; lecture technique bornée.
        [System.Environment]::SetEnvironmentVariable($entry.Key, $entry.Value, "Process") # Fichier .env interdit; interpolation technique bornée.
    }
    try {
        & $Operation
    }
    finally {
        foreach ($entry in $technicalValues.GetEnumerator()) {
            [System.Environment]::SetEnvironmentVariable($entry.Key, $previousValues[$entry.Key], "Process") # Fichier .env interdit; restauration obligatoire.
        }
    }
}

$exportRoot = Join-Path ([System.IO.Path]::GetTempPath()) "ostrading-$sourceCommit"
$archive = "$exportRoot.tar"
if (Test-Path -LiteralPath $exportRoot) { throw "GIT_EXPORT_ALREADY_EXISTS" }
git archive --format=tar --output=$archive $sourceCommit
if ($LASTEXITCODE -ne 0) { throw "GIT_EXPORT_FAILED" }
New-Item -ItemType Directory -Path $exportRoot | Out-Null
tar.exe -xf $archive -C $exportRoot
if ($LASTEXITCODE -ne 0) { throw "GIT_EXPORT_EXTRACTION_FAILED" }
New-Item -ItemType Directory -Force -Path "$exportRoot\deploy\local-compose\secrets" | Out-Null
Copy-Item -LiteralPath <chemin-secret-postgres-hors-git> -Destination "$exportRoot\deploy\local-compose\secrets\postgres_password"
Set-Location $exportRoot
Invoke-ComposeWithTechnicalInterpolation -Revision $sourceCommit -PostgresSchemaVersion $schemaVersion -Operation {
    docker compose -f .\deploy\local-compose\compose.yaml config
    if ($LASTEXITCODE -ne 0) { throw "COMPOSE_CONFIGURATION_INVALID" }
}
```

Le contexte Docker est l'archive du commit, jamais le worktree. Le `.dockerignore` racine exclut Git, environnements Python, données, secrets et temporaires. Le fichier de configuration Compose monte `./application.compose.yaml:/workspace/config/application.yaml:ro` et utilise `/run/secrets/postgres_password`.

## Construction et inspection avant démarrage

```powershell
Invoke-ComposeWithTechnicalInterpolation -Revision $sourceCommit -PostgresSchemaVersion $schemaVersion -Operation {
    docker compose -f .\deploy\local-compose\compose.yaml build orchestrator-api worker-documents llm-gateway ui
    if ($LASTEXITCODE -ne 0) { throw "COMPOSE_BUILD_FAILED" }
}

$apiImage = "ostrading/orchestrator-api:0.1.0-m013-fastapi-schema-$schemaVersion-$sourceCommit"
$workerImage = "ostrading/worker-documents:0.1.0-m013-fastapi-schema-$schemaVersion-$sourceCommit"
foreach ($candidate in @(
    @{ Image = $apiImage; Entrypoint = 'api' },
    @{ Image = $workerImage; Entrypoint = 'python' }
)) {
    $inspection = (docker image inspect $candidate.Image | ConvertFrom-Json)[0]
    if ($inspection.Config.Labels.'org.opencontainers.image.revision' -ne $sourceCommit) { throw "IMAGE_REVISION_MISMATCH" }
    if ($inspection.Config.Labels.'org.ostrading.postgres-schema-version' -ne $schemaVersion) { throw "IMAGE_SCHEMA_MISMATCH" }
    if ($inspection.Config.User -ne 'ostrading') { throw "IMAGE_NON_ROOT_USER_MISMATCH" }
    if ($inspection.Config.Entrypoint[0] -ne $candidate.Entrypoint) { throw "IMAGE_ENTRYPOINT_MISMATCH" }
    $inspection.Id
}

Invoke-ComposeWithTechnicalInterpolation -Revision $sourceCommit -PostgresSchemaVersion $schemaVersion -Operation {
    docker compose -f .\deploy\local-compose\compose.yaml up -d --no-build
    if ($LASTEXITCODE -ne 0) { throw "COMPOSE_START_FAILED" }
}
```

L'API exécute `api --config /workspace/config/application.yaml`. Le worker exécute son module dédié, avec un tag immuable contenant schéma et commit. Compose matérialise `services.worker-documents.deploy.replicas: 2` ; ADR-025 impose une identité d'instance et un fencing distincts par replica.

Le raccourci historique `docker compose -f .\deploy\local-compose\compose.yaml up --build` n'est pas la procédure de livraison : il ne permet pas l'inspection préalable obligatoire. Seul `edge-gateway` publie un port, exclusivement sur `127.0.0.1`. Tout bind `0.0.0.0`, LAN ou public est refusé par `REFUS_BIND_PUBLIC`.

## Contrôles opératoires

```powershell
Invoke-ComposeWithTechnicalInterpolation -Revision $sourceCommit -PostgresSchemaVersion $schemaVersion -Operation {
    $edgeAuthority = docker compose -f .\deploy\local-compose\compose.yaml port edge-gateway 8443
    curl.exe --fail --insecure "https://$edgeAuthority/api/health"
    curl.exe --fail --insecure "https://$edgeAuthority/api/ready"
    curl.exe --fail --insecure "https://$edgeAuthority/api/openapi.json"
    docker compose -f .\deploy\local-compose\compose.yaml exec -T orchestrator-api python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=300).read().decode())"
    docker compose -f .\deploy\local-compose\compose.yaml exec -T orchestrator-api python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/ready', timeout=300).read().decode())"
}
```

`/ready` doit nommer `postgres` et `llm-gateway` avec le statut `ready`. Une dépendance indisponible rend l'API non prête avec un code technique sûr, sans URL ni secret. Chaque réponse porte `X-Trace-ID`; les logs incluent méthode, chemin, statut, durée, `trace_id` et `configuration_hash`, jamais le PDF ni les métadonnées.

## Contrat OpenAPI et erreurs opératoires

`POST /v1/documents` répond en `201 application/json`. `GET /v1/documents/{document_id}/original` répond en `200 application/pdf` uniquement. Le diagnostic répond en `202 application/json`. Les erreurs publiques utilisent un DTO typé autour de `error_code` ; une réponse `5xx` n'active aucun runtime alternatif.

| Statut | Signification opératoire | Action sans fallback |
|---|---|---|
| `413` | Corps Caddy/ASGI ou PDF supérieur à la borne autorisée. | Réduire l'entrée ; ne pas réessayer le même corps. |
| `503` | Readiness échouée, notamment PostgreSQL ou `llm-gateway` indisponible. | Restaurer la dépendance, vérifier `/ready`, puis seulement réessayer. |
| `504` | Délai explicite de traitement ou de dépendance dépassé. | Diagnostiquer la latence et la capacité ; aucun retry ou backend alternatif implicite. |

Caddy et l'ASGI refusent les corps `/api/*` supérieurs à 54 Mo, y compris sans `Content-Length`. Le PDF métier reste limité à 50 Mio. La restitution vérifie le SHA-256 avant le statut 200 et émet des chunks d'au plus 64 Kio.

## Gates statique et live

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_fastapi.ps1 -Mode Static
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_fastapi.ps1 -Mode Live
```

Les deux modes matérialisent l'environnement verrouillé par `uv sync --frozen --no-dev`. Cette synchronisation installe aussi le paquet `chatbot-trading` en version `0.1.0` et la gate refuse toute métadonnée absente ou différente. Le mode `Live` exporte `HEAD`, construit et démarre la stack finale : PostgreSQL, Qdrant, `llm-gateway`, `orchestrator-api`, deux workers, UI et Caddy. Il vérifie les labels, l'utilisateur, les entrypoints, la migration 008, la readiness PostgreSQL + LLM et un PDF réel. Il redémarre ensuite PostgreSQL et l'API dans de nouveaux processus, puis relit le diagnostic et le SHA-256 original : c'est la preuve réelle T-005. Le test historique `validate_document_persistence_restart_acceptance.ps1` reste une preuve de contrat isolée et ne remplace pas ce parcours Compose.

## Migration ascendante d'un volume existant

```powershell
Invoke-ComposeWithTechnicalInterpolation -Revision $sourceCommit -PostgresSchemaVersion $schemaVersion -Operation {
    docker compose -f .\deploy\local-compose\compose.yaml up -d postgres
    docker compose -f .\deploy\local-compose\compose.yaml run --rm --no-deps orchestrator-api python -m app.platform.postgres_migrations --config /workspace/config/application.yaml
}
```

La sortie attendue est `POSTGRES_SCHEMA_READY:<OSTRADING_POSTGRES_SCHEMA_VERSION>`. La relance est idempotente. `POSTGRES_MIGRATION_DRIFT`, `POSTGRES_SCHEMA_VERSION_UNSUPPORTED` ou un timeout interdisent le démarrage ; aucun ledger n'est corrigé automatiquement.

## Arrêt et rollback immuable

L'arrêt conserve les volumes :

```powershell
Invoke-ComposeWithTechnicalInterpolation -Revision $sourceCommit -PostgresSchemaVersion $schemaVersion -Operation {
    docker compose -f .\deploy\local-compose\compose.yaml down
}
```

Le rollback prévalide le ledger **avant** export, build et remplacement :

```powershell
$target = git rev-parse <commit-complet-compatible>
if ($LASTEXITCODE -ne 0 -or $target -notmatch '^[0-9a-f]{40}$') { throw "IMAGE_REVISION_MUTABLE_REJECTED" }

$ledgerRaw = Invoke-ComposeWithTechnicalInterpolation -Revision $sourceCommit -PostgresSchemaVersion $schemaVersion -Operation {
    docker compose -f .\deploy\local-compose\compose.yaml exec -T postgres psql -At -U ostrading -d ostrading -c "SELECT COALESCE(MAX(version), 0) FROM platform.schema_migrations;"
}
if ($LASTEXITCODE -ne 0 -or $ledgerRaw -notmatch '^\s*(?<ledger>[0-9]+)\s*$') { throw "POSTGRES_LEDGER_UNREADABLE" }
$ledgerVersion = [int]$Matches.ledger

$targetMigrations = @(git ls-tree -r --name-only $target -- deploy/postgres/migrations)
if ($LASTEXITCODE -ne 0 -or $targetMigrations.Count -eq 0) { throw "POSTGRES_SCHEMA_VERSION_UNREADABLE" }
$targetLatest = $targetMigrations | Sort-Object | Select-Object -Last 1
if ([IO.Path]::GetFileNameWithoutExtension($targetLatest) -notmatch '^(?<version>[0-9]{3})_') { throw "POSTGRES_SCHEMA_VERSION_UNREADABLE" }
$targetSchemaVersion = [int]$Matches.version
if ($targetSchemaVersion -lt $ledgerVersion) { throw "POSTGRES_SCHEMA_VERSION_UNSUPPORTED" }
$sourceCommit = $target
$schemaVersion = '{0:D3}' -f $targetSchemaVersion
```

Après cette prévalidation, reprendre la procédure « Export immuable et préparation » avec `$target`, puis « Construction et inspection avant démarrage ». Les labels et entrypoints API **et** worker sont inspectés avant `up -d --no-build`. Une cible plus ancienne que le ledger est refusée avant toute construction et avant tout remplacement. Le rollback ne supprime jamais le volume et n'exécute aucune migration descendante ; une incompatibilité exige une migration corrective ascendante versionnée.

Après arrêt, supprimer explicitement l'archive et le répertoire temporaires. Aucun fallback vers l'ancien routeur, aucun second runtime sur 8080 et aucun bind public implicite ne sont autorisés.
