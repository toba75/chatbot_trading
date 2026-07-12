# Rapport d'audit M13-FastAPI

## Périmètre

- Tâche: T-011, déployer et auditer l'API orchestratrice.
- Date: 2026-07-12.
- Décision: ADR-019, FastAPI et Uvicorn uniquement pour `orchestrator-api`.
- Configuration: M13-config, fichier unique et `configuration_hash` obligatoire.

## Scénario audité

- Given l'application ASGI et les contrats documentaires sont GREEN.
- When PostgreSQL réel démarre dans Docker, Uvicorn démarre puis reçoit un PDF réel par HTTP multipart.
- Then les routes de santé, readiness, OpenAPI, enregistrement, diagnostic, corpus, original et projection publique répondent par un seul runtime traçable.

## Contrôles

| Contrôle | Preuve attendue | Verdict |
|---|---|---|
| Runtime public unique | Compose exécute `uv run --no-sync api`; aucune commande `local_runtime` pour `orchestrator-api` | Couvert par la gate |
| PostgreSQL réel | Conteneur PostgreSQL épinglé, migrations SQL exécutées, readiness `SELECT 1` | Couvert par la gate live |
| PDF réel | PDF valide produit avec `pypdf`, transmis multipart, hash identique à la restitution | Couvert par la gate live |
| Traçabilité | `X-Trace-ID`, log `trace_id`, `configuration_hash`, statut et durée sans payload | Couvert par la gate live |
| OpenAPI borné | `/openapi.json` sans référence de stockage, job, secret ni identifiant Qdrant | Couvert par la gate live |
| Configuration obligatoire | `--config` requis; secret et dépendance manquants arrêtent le démarrage | Couvert par tests et runtime |
| Aucun fallback | aucune route de secours, aucun backend alternatif, aucune réactivation de l'ancien serveur | Couvert par tests statiques |

## Commandes d'audit

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_fastapi\validate_orchestrator_deployment_acceptance.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_fastapi\validate_document_http_live_acceptance.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_fastapi\validate_orchestrator_deployment_unit.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_fastapi\validate_m013_fastapi_traceability_unit.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_fastapi.ps1
```

La preuve live utilise Docker Engine, PostgreSQL, Uvicorn et HTTP réels. Aucun mock, stub, fake, serveur de test ASGI ni fallback n'est admis dans cette preuve. Les tests unitaires isolés ne remplacent pas cette preuve live.

## Limites et rollback

- L'UI reste cliente HTTP de `orchestrator-api`; elle n'est pas migrée vers FastAPI.
- `llm-gateway` reste le seul adaptateur réseau vers Spark et n'est pas migré.
- Qdrant ne devient pas une source de vérité de projection; l'état public KA est lu depuis PostgreSQL.
- Le rollback suit `docs/runbooks/api_orchestratrice.md` et ne réactive jamais deux runtimes concurrents.

## Résultats observés

- Docker Engine: serveur `29.1.5` disponible.
- Image Compose: `ostrading/orchestrator-api:0.0.0-m002` construite avec `uv sync --frozen --no-dev`; manifeste local `sha256:51de59597a927e0cb59030a630ae3af81fd2a599ef0835697f1791fdb076ae84`.
- Preuve HTTP: document `DOC-BC6CFA26B1753E74`, PDF SHA-256 `bc6cfa26b1753e740c2749f8a854828770965f5862134ec304cb11a25e98d02a`, PostgreSQL Docker et transport `uvicorn-http`.
- Gate M13-FastAPI: quatre preuves GREEN, dont la preuve live sans double.
- Gate lint: GREEN, 38 validations.
- Gate de traçabilité: GREEN, 163 exigences.
- Gate globale `scripts/test.ps1`: tentative bornée à 10 minutes, expirée sans sortie ni code de sortie applicatif; résultat non concluant et jamais présenté comme GREEN.
