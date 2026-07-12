# Runbook de l'API orchestratrice M13-FastAPI

## Statut

- Tâche: `docs/tasks/milestone_013-fastapi/0011_deployer_auditer_api_orchestratrice.md`.
- ADR applicables: ADR-019 pour le runtime et ADR-020 pour la frontière binaire bornée; ADR-018 reste inchangée.
- Runtime public unique: FastAPI servi par Uvicorn sous l'identité `orchestrator-api`.
- Configuration unique: fichier explicite conforme à M13-config; aucune variable applicative, valeur par défaut ou solution de repli.

## Scénario BDD

- Given l'application ASGI, PostgreSQL et les contrats documentaires sont prêts.
- When l'exploitant démarre `orchestrator-api` puis enregistre un PDF.
- Then `/health`, `/ready`, `/openapi.json` et les lectures publiques sont servis par Uvicorn, avec un `trace_id` et le `configuration_hash` dans les logs techniques.

## Démarrage local borné

Depuis la racine du dépôt, avec le fichier et le secret PostgreSQL effectivement présents:

```powershell
uv run api --config .\config\application.yaml
```

Le processus s'arrête explicitement si `--config`, PostgreSQL, le secret PostgreSQL ou une migration obligatoire manque. Il ne démarre aucun ancien routeur et n'essaie aucun backend alternatif.

## Démarrage Compose

```powershell
docker compose -f .\deploy\local-compose\compose.yaml up --build
```

Les quatre variables techniques `OST_EDGE_HTTPS_PORT`, `CADDY_ADMIN`, `POSTGRES_DB` et `POSTGRES_USER` doivent avoir été exportées explicitement selon `deploy/local-compose/README.md`; aucune variable applicative n'est admise.

Le service `orchestrator-api` exécute directement l'entrée verrouillée `api --config /workspace/config/application.yaml` depuis la `.venv` copiée par le builder. L'image runtime n'installe pas `uv` et ne résout aucune dépendance. Le service conserve le port interne 8080 et attend PostgreSQL. L'UI et `llm-gateway` gardent leur runtime propre; ils ne sont pas migrés vers FastAPI.

## Limites binaires et spool temporaire

- Caddy refuse les corps `/api/*` supérieurs à 54 Mo avant le proxy.
- L'ASGI applique la même limite agrégée, y compris sans `Content-Length` ou en transfert chunked, avant le parseur multipart.
- Le PDF métier reste limité à 50 Mio. Le titre est limité à 512 caractères, chaque auteur à 256 caractères, la liste à 16 auteurs, l'édition à 64 caractères et l'année à l'intervalle 1 à 9999.
- `orchestrator-api` conserve `read_only: true` et dispose uniquement de `/tmp:size=128m,mode=1777` pour couvrir simultanément le spool ASGI et le spool multipart. Une saturation ou un dépassement reste une erreur visible; aucun stockage alternatif n'est utilisé.
- La restitution d'un original vérifie son SHA-256 avant le statut 200, puis émet des chunks d'au plus 64 Kio. Le descripteur est fermé à la fin, sur interruption ou par la tâche de fermeture de la réponse.

## Contrôles opératoires

```powershell
Invoke-RestMethod http://127.0.0.1:8080/health
Invoke-RestMethod http://127.0.0.1:8080/ready
Invoke-RestMethod http://127.0.0.1:8080/openapi.json
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_fastapi.ps1
```

- `/health` prouve que le processus répond.
- `/ready` doit répondre 200 et nommer PostgreSQL `ready`; un 503 interdit l'exploitation.
- `/openapi.json` est la seule description OpenAPI exposée; `/docs` et `/redoc` sont désactivés.
- Chaque réponse porte `X-Trace-ID`; le log JSON correspondant contient seulement méthode, chemin, statut, durée, `trace_id` et `configuration_hash`, jamais le PDF ni les métadonnées bibliographiques.

## Arrêt et rollback

L'arrêt Compose conserve les volumes:

```powershell
docker compose -f .\deploy\local-compose\compose.yaml down
```

Le rollback applicatif consiste à redéployer le commit GREEN M13-FastAPI précédent avec son `uv.lock`, son image et son schéma PostgreSQL compatibles. Il est interdit de réactiver `app.platform.local_runtime serve-http orchestrator-api`, de servir deux runtimes sur le port 8080 ou de supprimer les volumes. Une migration corrective doit être explicite et gouvernée; aucun fallback vers l'ancien routeur n'est autorisé.

Le rollback du présent durcissement doit restaurer ensemble `pyproject.toml`, `uv.lock`, l'image multi-stage, les limites Caddy/ASGI et le `tmpfs`. Il est interdit de retirer seulement une limite ou de réintroduire `Path.read_bytes()` sur la restitution publique.
