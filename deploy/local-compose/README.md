# Stack locale M-002

## Préconditions

- Exécuter les commandes depuis la racine du dépôt.
- Créer le fichier local `config/application.yaml` à partir de `config/application.example.yaml` et renseigner les valeurs propres à l'installation.
- Fournir le secret hors dépôt dans `deploy/local-compose/secrets/`:
  - `postgres_password`
- Le gateway LLM cible uniquement l'endpoint Docker Spark déclaré dans `services.llm_gateway.spark_endpoint_url`.
- La provenance LLM est déclarée explicitement dans `models.llm.served_model_name`, `models.llm.model_revision` et `models.llm.runtime_version`.
- Les processus applicatifs reçoivent tous `--config /workspace/config/application.yaml`.
- Le fichier `config/application.yaml` est monté en lecture seule dans les services applicatifs.

## Variables requises

Le Compose refuse les valeurs par défaut silencieuses. Les variables techniques restantes doivent être exportées explicitement avant validation ou démarrage:

- `OST_EDGE_HTTPS_PORT`
- `CADDY_ADMIN` (valeur locale utilisée: `localhost:2019`)
- `POSTGRES_DB`
- `POSTGRES_USER`

Aucune valeur applicative OSTrading ne doit être transmise par `environment:` ou `env_file`. Les anciennes entrées `DATABASE_URL`, `QDRANT_URL`, `LLM_GATEWAY_URL`, `GEMMA_*`, `UI_API_URL`, `GRANITE_*`, `EMBEDDING_*`, `RERANKER_*` et `BACKTEST_*` sont à renseigner dans `config/application.yaml` selon le schéma applicatif.

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
