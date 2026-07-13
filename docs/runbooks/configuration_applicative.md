# Runbook configuration applicative M13-config

## Statut

- Identifiant: `M13Config-Runbook-ApplicationConfiguration-1.0`
- Tâche: `docs/tasks/milestone_013-config/0007_publier_runbooks_migration_configuration.md`
- ADR applicable: ADR-016 - Configuration applicative par fichier unique.
- Fichier applicatif: `config/application.yaml`.
- Schéma applicatif: `config/application.schema.json`.
- Fallback silencieux: interdit.
- Secret en clair: interdit.

## Scénario BDD

- Given un exploitant local lit les runbooks après M13-config.
- When il prépare et démarre la pile V1.
- Then chaque commande utilise `--config`, les anciennes variables sont présentées comme entrées rejetées, et la preuve d'audit cite le fichier chargé.

## Préparer le fichier applicatif

- Prérequis: exécuter depuis la racine du dépôt, sur une branche contenant ADR-016 et les validations M13-config.
- Copier `config/application.example.yaml` vers `config/application.yaml`.
- Relire chaque section obligatoire: `deployment`, `services`, `models`, `paths`, `security`, `quality_gates`, `observability` et `runtime`.
- Renseigner les valeurs propres à l'installation dans `config/application.yaml` sans valeur implicite et sans comportement alternatif.
- Placer chaque secret hors Git sous `config/secrets/local/` ou sous un chemin absolu approuvé localement; le fichier applicatif référence seulement ces chemins.
- Conserver le secret Compose local sous `deploy/local-compose/secrets/`, avec `deploy/local-compose/secrets/.gitignore` comme garde-fou de versionnement.

Commande vérifiée:

```console
Copy-Item -LiteralPath .\config\application.example.yaml -Destination .\config\application.yaml
uv run --locked gate
uv run --locked gate
```

Résultat attendu: le chargeur `load_application_configuration` valide le fichier avec `config/application.schema.json`, refuse les clés absentes, les valeurs vides, les placeholders et les secrets en clair.

Erreur explicite: `CONFIG_FILE_REQUIRED`, `CONFIG_FILE_UNREADABLE`, `CONFIG_SCHEMA_INVALID`, `CONFIG_KEY_MISSING`, `CONFIG_KEY_EMPTY` ou `CONFIG_SECRET_INLINE_REJECTED`.

Preuve à conserver: chemin du fichier chargé, hash SHA-256 `configuration_hash`, sortie des validateurs et horodatage local.

## Valider les garde-fous

Commande vérifiée:

```console
uv run --locked gate
uv run --locked gate
uv run --locked gate
```

Résultat attendu: la gate environnement reste GREEN, Compose monte le fichier applicatif en lecture seule, et le seul chemin Spark autorisé reste `llm-gateway -> spark-inference`.

Erreur explicite: `CONFIG_ENV_INPUT_REJECTED` si une entrée de processus tente de piloter l'application, ou erreur du validateur réseau si un service interne devient public.

Preuve à conserver: sorties des trois validateurs et hash du fichier `deploy/local-compose/compose.yaml`.

## Démarrer la pile locale

Commande vérifiée:

```console
docker compose -f .\deploy\local-compose\compose.yaml up --build
```

Résultat attendu: Compose applique déjà `--config /workspace/config/application.yaml` à chaque processus applicatif et monte la variante conteneur versionnée `./application.compose.yaml:/workspace/config/application.yaml:ro`. Cette variante respecte le même schéma strict et utilise les DNS Compose; elle ne remplace pas le fichier local préparé pour les processus exécutés hors conteneur.

Erreur explicite: si `config/application.yaml` est absent, illisible, incomplet ou contredit par une entrée de processus, le démarrage échoue avant l'accès à PostgreSQL, Qdrant ou Spark.

Preuve à conserver: sortie Compose, identifiant d'image, horodatage du démarrage, `configuration_hash` observé dans les logs ou métriques gateway, et alias de preuve `config_hash` si un rapport historique le nomme encore.

## Démarrage direct de diagnostic

Cette commande démarre un service applicatif hors Compose uniquement pour reproduire un diagnostic local; l'arrêt manuel est attendu après capture de la preuve.

```console
python -m app.platform.local_runtime serve-http llm-gateway 8090 --config .\config\application.yaml
```

Résultat attendu: le processus charge le même fichier applicatif que Compose et expose la provenance LLM gouvernée par ADR-016.

Erreur explicite: l'absence de `--config` produit `CONFIG_FILE_REQUIRED`; une pollution de processus produit `CONFIG_ENV_INPUT_REJECTED`.

Preuve à conserver: commande complète, chemin du fichier, `configuration_hash` et message d'erreur public le cas échéant.

## Auditer la configuration chargée

- Comparer le hash `configuration_hash` avec le contenu réel de `config/application.yaml` au moment du démarrage.
- Vérifier que la provenance LLM cite `models.llm.served_model_name`, `models.llm.model_revision` et `models.llm.runtime_version`.
- Vérifier que les chemins de secrets déclarés dans `security.secrets` pointent vers des fichiers locaux non versionnés.
- Vérifier que le mode actuel ADR-014 conserve `services.llm_gateway.auth_mode=none` et `services.llm_gateway.tls_mode=disabled` tant qu'aucune ADR ne remplace ce choix.

Preuve à conserver: extrait de log sans payload sensible, hash `configuration_hash`, commit applicatif, et ticket d'incident si une divergence apparaît.

## Mapping de migration

| Ancienne entrée | Nouvelle clé dans `config/application.yaml` | Règle |
|---|---|---|
| `DATABASE_URL` | `services.postgres.url` | Migrée dans le fichier; ancienne entrée refusée au démarrage. |
| `QDRANT_URL` | `services.qdrant.url` | Migrée dans le fichier; ancienne entrée refusée au démarrage. |
| `LLM_GATEWAY_URL` | `services.llm_gateway.url` | Migrée dans le fichier; ancienne entrée refusée au démarrage. |
| `GEMMA_BASE_URL` | `services.llm_gateway.spark_endpoint_url` | Migrée dans le fichier; ancienne entrée refusée au démarrage. |
| `GEMMA_AUTH_MODE` | `services.llm_gateway.auth_mode` | Migrée dans le fichier; ancienne entrée refusée au démarrage. |
| `GEMMA_TLS_MODE` | `services.llm_gateway.tls_mode` | Migrée dans le fichier; ancienne entrée refusée au démarrage. |
| `GEMMA_MODEL` | `models.llm.served_model_name` | Migrée dans le fichier; ancienne entrée refusée au démarrage. |
| `GEMMA_MODEL_REVISION` | `models.llm.model_revision` | Migrée dans le fichier; ancienne entrée refusée au démarrage. |
| `GEMMA_RUNTIME_VERSION` | `models.llm.runtime_version` | Migrée dans le fichier; ancienne entrée refusée au démarrage. |
| `GEMMA_TIMEOUT_SECONDS` | `services.llm_gateway.timeout_seconds` | Migrée dans le fichier; ancienne entrée refusée au démarrage. |
| `GEMMA_RETRY_BEFORE_FIRST_TOKEN` | `services.llm_gateway.retry_before_first_token` | Migrée dans le fichier; ancienne entrée refusée au démarrage. |
| `GEMMA_CIRCUIT_BREAKER_FAILURE_THRESHOLD` | `services.llm_gateway.circuit_breaker_failure_threshold` | Migrée dans le fichier; ancienne entrée refusée au démarrage. |
| `GEMMA_CIRCUIT_BREAKER_OPEN_SECONDS` | `services.llm_gateway.circuit_breaker_reset_seconds` | Migrée dans le fichier; ancienne entrée refusée au démarrage. |
| `GEMMA_API_KEY_FILE` | `security.secrets.llm_gateway_api_key_path` | Migrée comme chemin de secret hors Git; ancienne entrée refusée au démarrage. |
| `GEMMA_CA_BUNDLE` | `security.secrets.tls_ca_certificate_path` | Migrée comme chemin de certificat hors Git; ancienne entrée refusée au démarrage. |

## Entrées rejetées

- `GEMMA_*`: interdit comme entrée de processus; migrer chaque valeur vers le mapping ci-dessus.
- `DATABASE_URL`, `QDRANT_URL` et `LLM_GATEWAY_URL`: interdits comme entrées de processus; migrer les URLs vers `services`.
- `.env`: interdit pour la configuration applicative.
- `env_file`: interdit pour la configuration applicative Compose.
- `environment:` Compose: interdit pour toute valeur applicative; seules les variables techniques allowlistées par T-005 restent acceptées.

## Garde-fous

- Aucun secret n'est copié dans Git.
- Aucun démarrage applicatif ne se fait sans `--config`.
- Aucun fallback vers le shell, un fichier local implicite ou une valeur par défaut n'est documenté.
- Les anciennes clés restent visibles uniquement pour migrer ou expliquer le rejet `CONFIG_ENV_INPUT_REJECTED`.
