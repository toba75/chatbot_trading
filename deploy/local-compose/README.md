# Stack locale M13-FastAPI

## Préconditions

- Exécuter les commandes depuis la racine du dépôt.
- La configuration conteneur versionnée est `deploy/local-compose/application.compose.yaml`; elle respecte `config/application.schema.json` et les DNS Compose.
- Fournir le secret hors dépôt dans `deploy/local-compose/secrets/`:
  - `postgres_password`
  - `local_api_token` d'au moins 32 octets aléatoires, partagé uniquement par `ui` et `orchestrator-api`
- Le gateway LLM cible uniquement l'endpoint Docker Spark déclaré dans `services.llm_gateway.spark_endpoint_url`.
- La provenance LLM est déclarée explicitement dans `models.llm.served_model_name`, `models.llm.model_revision` et `models.llm.runtime_version`.
- Les processus applicatifs reçoivent tous `--config /workspace/config/application.yaml`.
- Le fichier `deploy/local-compose/application.compose.yaml` est monté en lecture seule dans les services applicatifs.
- Montage attendu dans chaque service applicatif: `./application.compose.yaml:/workspace/config/application.yaml:ro`.
- Le schéma `config/application.schema.json` est monté en lecture seule dans les services applicatifs.
- Montage schéma attendu: `../../config/application.schema.json:/workspace/config/application.schema.json:ro`.
- Le répertoire `config/secrets/local/` est monté en lecture seule dans `llm-gateway` pour les modes futurs `api_key_file` et `ca_bundle`.
- Montage secrets gateway attendu: `../../config/secrets/local:/workspace/config/secrets/local:ro`.

## Variables techniques requises

Le Compose refuse les valeurs par défaut silencieuses. Les variables techniques restantes doivent être exportées explicitement avant validation ou démarrage:

- `OST_EDGE_HTTPS_PORT`
- `CADDY_ADMIN` (valeur locale utilisée: `localhost:2019`)
- `OSTRADING_IMAGE_REVISION` (commit Git complet)
- `OSTRADING_POSTGRES_SCHEMA_VERSION` (préfixe de la dernière migration du commit)

Aucune valeur applicative OSTrading ne doit être transmise par `environment:` ou `env_file`. La base et le rôle PostgreSQL valent exactement `ostrading` afin de correspondre à l'URL de la configuration montée.

## Validation statique

```console
uv run --locked gate --scope m002
uv run --locked gate --scope m013
docker compose -f .\deploy\local-compose\compose.yaml config
```

## Démarrage local

```console
docker compose -f .\deploy\local-compose\compose.yaml up --build
```

L'entrée utilisateur est `edge-gateway` liée à `127.0.0.1:${OST_EDGE_HTTPS_PORT}` et accessible via `https://localhost:${OST_EDGE_HTTPS_PORT}`. Aucun service interne ne publie de port hôte; `llm-gateway` est le seul service rattaché au réseau `spark-egress`. Le token local n'est jamais transmis au navigateur : le serveur UI le lit depuis `/run/secrets/local_api_token` pour authentifier uniquement ses mutations backend.
