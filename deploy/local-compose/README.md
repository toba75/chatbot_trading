# Stack locale M-002

## Préconditions

- Exécuter les commandes depuis la racine du dépôt.
- Fournir le secret hors dépôt dans `deploy/local-compose/secrets/`:
  - `postgres_password`
- Le gateway LLM cible uniquement l'endpoint Docker Spark déclaré par `GEMMA_BASE_URL`.
- Le conteneur Gemma sur la machine Spark n'exige pas de clé API: `GEMMA_AUTH_MODE` vaut `none` dans le Compose local.
- Le transport Spark actuel n'exige pas de bundle CA: `GEMMA_TLS_MODE` vaut `disabled` dans le Compose local.

## Variables requises

Le Compose refuse les valeurs par défaut silencieuses. Les variables non secrètes doivent être exportées explicitement avant validation ou démarrage:

- `OST_EDGE_HTTPS_PORT`
- `CADDY_ADMIN` (valeur locale utilisée: `localhost:2019`)
- `UI_API_URL`
- `DATABASE_URL`
- `QDRANT_URL`
- `LLM_GATEWAY_URL`
- `GEMMA_BASE_URL`
- `GEMMA_MODEL`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `QDRANT_GRPC_PORT`
- `GRANITE_MODEL_PATH`
- `EMBEDDING_MODEL_PATH`
- `RERANKER_MODEL_PATH`
- `GRANITE_URL`
- `EMBEDDING_SERVICE_URL`
- `RERANKER_SERVICE_URL`
- `BACKTEST_ENGINE_URL`
- `BACKTEST_WORKDIR`

## Validation statique

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_local_compose.ps1 -Path .\deploy\local-compose\compose.yaml
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_network_boundary.ps1
docker compose -f .\deploy\local-compose\compose.yaml config
```

## Démarrage local

```powershell
docker compose -f .\deploy\local-compose\compose.yaml up --build
```

L'entrée utilisateur est `edge-gateway` liée à `127.0.0.1:${OST_EDGE_HTTPS_PORT}` et accessible via `https://localhost:${OST_EDGE_HTTPS_PORT}`. Aucun service interne ne publie de port hôte; `llm-gateway` est le seul service rattaché au réseau `spark-egress`.
