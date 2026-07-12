# Runbook de l'API orchestratrice M13-FastAPI

## Statut et périmètre

- Tâche: `docs/tasks/milestone_013-fastapi/0011_deployer_auditer_api_orchestratrice.md`.
- ADR applicables: ADR-019 pour le runtime, ADR-020 pour la frontière binaire bornée et ADR-021 pour les migrations PostgreSQL; ADR-018 reste inchangée.
- Runtime public unique: FastAPI servi par Uvicorn sous l'identité `orchestrator-api`.
- Chemin d'exploitation supporté: Compose depuis un commit Git complet, avec la dernière migration livrée par ce commit.
- Configuration unique: fichier conforme à M13-config; aucune variable applicative, valeur par défaut ou solution de repli.

## Scénario BDD

- Given un clone propre placé sur un commit Git précis et les secrets locaux requis.
- When l'exploitant dérive explicitement la révision et le schéma, valide Compose puis construit la stack.
- Then `/health`, `/ready`, `/openapi.json` et les lectures publiques sont servis par l'image identifiée par ce commit, avec un `trace_id` et le `configuration_hash` dans les logs techniques.

## Préconditions strictes

La recette hôte n'est pas un chemin d'exploitation: PostgreSQL est adressé par son nom DNS interne `postgres`, qui n'est volontairement pas joignable depuis l'hôte. Il est interdit de lancer directement l'entrée `api` hors de Compose. La commande historique `python -m app.platform.local_runtime serve-http orchestrator-api 8080` reste interdite et retourne `ORCHESTRATOR_LEGACY_RUNTIME_FORBIDDEN`.

Depuis la racine du dépôt, l'exploitant doit fixer les variables techniques et prouver l'identité du commit et du schéma:

```powershell
$env:OST_EDGE_HTTPS_PORT = "8443"
$env:CADDY_ADMIN = "localhost:2019"
$env:POSTGRES_DB = "ostrading"
$env:POSTGRES_USER = "ostrading"
$env:OSTRADING_IMAGE_REVISION = git rev-parse HEAD
if ($env:OSTRADING_IMAGE_REVISION -notmatch '^[0-9a-f]{40}$') { throw "IMAGE_REVISION_MUTABLE_REJECTED" }
$latestMigration = Get-ChildItem .\deploy\postgres\migrations\*.sql | Sort-Object Name | Select-Object -Last 1
if ($latestMigration.BaseName -notmatch '^(?<version>[0-9]{3})_') { throw "POSTGRES_SCHEMA_VERSION_UNREADABLE" }
$env:OSTRADING_POSTGRES_SCHEMA_VERSION = $Matches.version
docker compose -f .\deploy\local-compose\compose.yaml config
```

Le secret `deploy/local-compose/secrets/postgres_password` doit exister. L'identifiant d'image est alors `ostrading/orchestrator-api:0.1.0-m013-fastapi-schema-<version>-<commit-complet>`; `latest`, une branche, un hash abrégé ou une version de schéma saisie manuellement sont refusés.

## Démarrage Compose

```powershell
docker compose -f .\deploy\local-compose\compose.yaml up --build
```

Compose transmet la révision et le schéma comme arguments de build, exécute directement `api --config /workspace/config/application.yaml` depuis la `.venv` construite avec `uv.lock`, et ne publie pas le port 8080. Le builder copie `uv` depuis une image épinglée par digest; le runtime n'embarque pas `uv` et ne résout aucune dépendance.

Seul `edge-gateway` publie un port, exclusivement sur `127.0.0.1`. Toute tentative de remplacer cette adresse par `0.0.0.0`, une adresse LAN ou une interface publique est un échec d'exploitation nommé `REFUS_BIND_PUBLIC`; elle exige une décision de sécurité distincte, jamais une modification opportuniste du runbook.

## Contrat OpenAPI public

`POST /v1/documents` répond en `201 application/json` avec le DTO documentaire public. `GET /v1/documents/{document_id}/original` répond en `200 application/pdf` uniquement. Le diagnostic documente `202 application/json`; les erreurs publiques utilisent les statuts `400`, `404`, `409`, `422` ou `500` et un DTO typé autour de `error_code`.

`GET /openapi.json` décrit le multipart PDF et les métadonnées obligatoires. Les schémas publics ne contiennent aucune référence de stockage, secret, job interne ni identifiant Qdrant. Une réponse `5xx` n'active aucun runtime alternatif.

## Gates statique et live

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_fastapi.ps1 -Mode Static
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_fastapi.ps1 -Mode Live
```

Les deux modes exécutent d'abord `uv sync --frozen --no-dev --no-install-project`, puis imposent `.venv\Scripts\python.exe` à toutes les preuves. Les dépendances proviennent exclusivement de `uv.lock`; le code testé reste celui du checkout, sans réinstaller les points d'entrée pendant qu'un service local peut les utiliser. Un clone propre ne dépend donc ni du Python global ni d'une `.venv` préexistante. Le mode `Static` n'exige pas Docker; le mode `Live` ajoute PostgreSQL, Uvicorn, PDF et workers réels. L'absence de mode est une erreur explicite.

## Migration d'un volume existant

Le démarrage normal applique toutes les migrations livrées avant readiness. Pour séparer l'opération:

```powershell
docker compose -f .\deploy\local-compose\compose.yaml up -d postgres
docker compose -f .\deploy\local-compose\compose.yaml run --rm --no-deps orchestrator-api python -m app.platform.postgres_migrations --config /workspace/config/application.yaml
```

La sortie attendue est `POSTGRES_SCHEMA_READY:<OSTRADING_POSTGRES_SCHEMA_VERSION>`. La relance est idempotente. `POSTGRES_MIGRATION_DRIFT`, `POSTGRES_SCHEMA_VERSION_UNSUPPORTED` ou un timeout interdisent le démarrage; aucun ledger n'est corrigé automatiquement.

## Contrôles opératoires

```powershell
$edgeAuthority = docker compose -f .\deploy\local-compose\compose.yaml port edge-gateway 8443
curl.exe --fail --insecure "https://$edgeAuthority/api/ready"
curl.exe --fail --insecure "https://$edgeAuthority/api/openapi.json"
docker compose -f .\deploy\local-compose\compose.yaml exec -T orchestrator-api python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=300).read().decode())"
docker compose -f .\deploy\local-compose\compose.yaml exec -T orchestrator-api python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/ready', timeout=300).read().decode())"
```

Le `/ready` doit nommer PostgreSQL `ready`. Chaque réponse porte `X-Trace-ID`; le log JSON contient méthode, chemin, statut, durée, `trace_id` et `configuration_hash`, jamais le PDF ni les métadonnées bibliographiques.

## Limites binaires

- Caddy et l'ASGI refusent les corps `/api/*` supérieurs à 54 Mo, y compris sans `Content-Length`.
- Le PDF métier reste limité à 50 Mio et les métadonnées à leurs bornes documentées.
- Le service reste `read_only: true`; `/tmp` est explicitement borné.
- La restitution vérifie le SHA-256 avant le statut 200 et émet des chunks d'au plus 64 Kio.

## Arrêt et rollback immuable

L'arrêt conserve les volumes:

```powershell
docker compose -f .\deploy\local-compose\compose.yaml down
```

Le rollback redéploie un commit complet compatible avec le ledger. Il ne réutilise jamais le tag de l'image courante:

```powershell
git switch --detach <commit-complet-compatible>
$env:OSTRADING_IMAGE_REVISION = git rev-parse HEAD
if ($env:OSTRADING_IMAGE_REVISION -notmatch '^[0-9a-f]{40}$') { throw "IMAGE_REVISION_MUTABLE_REJECTED" }
$latestMigration = Get-ChildItem .\deploy\postgres\migrations\*.sql | Sort-Object Name | Select-Object -Last 1
if ($latestMigration.BaseName -notmatch '^(?<version>[0-9]{3})_') { throw "POSTGRES_SCHEMA_VERSION_UNREADABLE" }
$env:OSTRADING_POSTGRES_SCHEMA_VERSION = $Matches.version
docker compose -f .\deploy\local-compose\compose.yaml config
docker compose -f .\deploy\local-compose\compose.yaml up --build
$image = "ostrading/orchestrator-api:0.1.0-m013-fastapi-schema-$env:OSTRADING_POSTGRES_SCHEMA_VERSION-$env:OSTRADING_IMAGE_REVISION"
$inspection = (docker image inspect $image | ConvertFrom-Json)[0]
if ($inspection.Config.Labels.'org.opencontainers.image.revision' -ne $env:OSTRADING_IMAGE_REVISION) { throw "IMAGE_REVISION_MISMATCH" }
if ($inspection.Config.Labels.'org.ostrading.postgres-schema-version' -ne $env:OSTRADING_POSTGRES_SCHEMA_VERSION) { throw "IMAGE_SCHEMA_MISMATCH" }
$inspection.Id
```

La révision et le schéma inspectés doivent correspondre exactement aux variables, et l'identifiant local de l'image est consigné dans la preuve de rollback. Une image exigeant une version inférieure au ledger est refusée. Le rollback ne supprime jamais le volume et n'exécute aucune migration descendante; une incompatibilité nécessite une migration corrective ascendante versionnée.

Aucun fallback vers l'ancien routeur, aucun second runtime sur 8080 et aucun bind public implicite ne sont autorisés.
