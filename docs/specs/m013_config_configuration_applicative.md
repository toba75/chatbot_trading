# M13-config - Spécification de configuration applicative

## Statut

- Statut: publié pour T-002.
- Milestone: `M13-config - Configuration applicative sans environnement`.
- Bounded context: `platform.configuration`.
- ADR applicables: ADR-016 - Configuration applicative par fichier unique; ADR-026 - Déploiement Compose reproductible depuis un commit complet.
- Artefacts normatifs: `config/application.schema.json`, `config/application.example.yaml` et `deploy/local-compose/application.compose.yaml` pour le réseau conteneur versionné.

## Scénario BDD

- Given l'exploitant prépare un fichier `config/application.yaml`.
- When le contrat de configuration est validé.
- Then chaque valeur nécessaire au démarrage est présente dans le fichier, le schéma refuse les absences et aucun fallback environnement n'est décrit.

## Objectif métier

Le contrat rend auditable et reproductible le démarrage local. Toute valeur qui pilote l'application est déclarée dans `config/application.yaml`, validée avant le premier accès externe, puis associée à un hash de configuration dans les preuves d'exécution.

Cette spécification remplace les entrées de processus historiques par un fichier unique. Elle ne modifie pas les modules applicatifs; les tâches aval chargeront et appliqueront ce contrat.

## Contexte DDD

| Élément | Décision |
|---|---|
| Domaine | Plateforme locale et gouvernance d'exécution |
| Bounded context | `platform.configuration` |
| Langage ubiquitaire | configuration applicative, schéma strict, clé obligatoire, valeur placeholder, chemin de secret, configuration hashée, erreur explicite |
| Responsabilité | Publier le contrat de démarrage utilisé par API, workers, `llm-gateway`, Compose et scripts Spark |
| Intégrations | `platform.llm_gateway`, `platform.observability`, sécurité réseau, stockage local |

## Invariants

- Aucune valeur par défaut implicite n'est définie par le contrat.
- Aucun fallback environnement n'est autorisé.
- Aucun fallback vers `os.environ`, `.env`, `env_file`, `environment:` Compose ou variable système homonyme n'est autorisé.
- Aucun fallback vers os.environ, .env, env_file, environment: Compose ou variable système homonyme n'est autorisé.
- Aucune clé inconnue n'est acceptée par le schéma.
- Aucune clé obligatoire n'est absente, vide ou renseignée avec `TO_BE_FILLED`.
- Les secrets sont référencés par chemin; leur contenu n'est pas copié dans le fichier versionné.
- Les clés historiques `GEMMA_*`, `DATABASE_URL`, `QDRANT_URL` et `LLM_GATEWAY_URL` servent uniquement au mapping de migration et au rejet explicite.

## Sections obligatoires

| Section | Responsabilité | Exemples de clés obligatoires |
|---|---|---|
| `deployment` | Décrit la topologie locale, le binding hôte, l'écoute conteneur, les hôtes Spark autorisés et le placement des services | `topology`, `hosts.docker_local.bind_host`, `hosts.docker_local.container_listen_host`, `hosts.spark_inference.endpoint_hosts`, `network`, `placement` |
| `services` | Déclare les URLs, ports et paramètres de démarrage des services locaux | `postgres`, `qdrant`, `api`, `workers`, `llm_gateway` |
| `models.llm` | Déclare le modèle principal, sa provenance et son runtime | `provider`, `transport`, `served_model_name`, `model_revision`, `runtime_version` |
| `paths` | Déclare les répertoires applicatifs pilotants | `data_root`, `corpus_root`, `canonical_sources_root`, `reports_root`, `logs_root` |
| `security` | Déclare exposition réseau, chemins de secrets et audit de configuration | `network_exposure`, `allow_public_bind`, `secrets`, `audit` |
| `quality_gates` | Déclare les seuils et politiques de validation applicatives | `post_conversion`, `retrieval`, `answering`, `llm` |
| `observability` | Déclare uniquement les contrôles effectivement consommés par les runtimes | `tracing.enabled`, `logs.include_payloads` |
| `runtime` | Déclare profil local, workers, timeouts et ressources | `profile`, `workers`, `timeouts`, `resource_limits` |

## Erreurs publiques de configuration

| Code | Condition |
|---|---|
| `CONFIG_FILE_REQUIRED` | Le processus applicatif démarre sans argument explicite `--config <chemin>`. |
| `CONFIG_FILE_UNREADABLE` | Le fichier déclaré est absent, illisible ou non ouvrable. |
| `CONFIG_SCHEMA_INVALID` | Le fichier ne respecte pas `config/application.schema.json` ou contient une clé inconnue. |
| `CONFIG_KEY_MISSING` | Une section ou une clé obligatoire est absente. |
| `CONFIG_KEY_EMPTY` | Une valeur obligatoire est vide ou égale à `TO_BE_FILLED`. |
| `CONFIG_ENV_INPUT_REJECTED` | Une variable d'environnement historique ou homonyme tente de piloter l'application. |
| `CONFIG_SECRET_INLINE_REJECTED` | Un secret est fourni en clair au lieu d'un chemin de fichier secret. |

## Mapping de migration

| Ancienne entrée | Nouvelle clé dans `config/application.yaml` | Règle |
|---|---|---|
| `DATABASE_URL` | `services.postgres.url` | Migrée dans le fichier; variable refusée au démarrage. |
| `QDRANT_URL` | `services.qdrant.url` | Migrée dans le fichier; variable refusée au démarrage. |
| `LLM_GATEWAY_URL` | `services.llm_gateway.url` | Migrée dans le fichier; variable refusée au démarrage. |
| `GEMMA_BASE_URL` | `services.llm_gateway.spark_endpoint_url` | Migrée dans le fichier; variable refusée au démarrage. |
| `GEMMA_AUTH_MODE` | `services.llm_gateway.auth_mode` | Migrée dans le fichier; `none` et `api_key_file` sont les seuls modes acceptés; variable refusée au démarrage. |
| `GEMMA_TLS_MODE` | `services.llm_gateway.tls_mode` | Migrée dans le fichier; `disabled` et `ca_bundle` sont les seuls modes acceptés; variable refusée au démarrage. |
| `GEMMA_MODEL` | `models.llm.served_model_name` | Migrée dans le fichier; variable refusée au démarrage. |
| `GEMMA_MODEL_REVISION` | `models.llm.model_revision` | Migrée dans le fichier; variable refusée au démarrage. |
| `GEMMA_RUNTIME_VERSION` | `models.llm.runtime_version` | Migrée dans le fichier; variable refusée au démarrage. |
| `GEMMA_TIMEOUT_SECONDS` | `services.llm_gateway.timeout_seconds` | Migrée dans le fichier; variable refusée au démarrage. |
| `GEMMA_RETRY_BEFORE_FIRST_TOKEN` | `services.llm_gateway.retry_before_first_token` | Migrée dans le fichier; entier positif ou nul; variable refusée au démarrage. |
| `GEMMA_CIRCUIT_BREAKER_FAILURE_THRESHOLD` | `services.llm_gateway.circuit_breaker_failure_threshold` | Migrée dans le fichier; variable refusée au démarrage. |
| `GEMMA_CIRCUIT_BREAKER_OPEN_SECONDS` | `services.llm_gateway.circuit_breaker_reset_seconds` | Migrée dans le fichier; variable refusée au démarrage. |
| `GEMMA_API_KEY_FILE` | `security.secrets.llm_gateway_api_key_path` | Référencée par chemin seulement quand `auth_mode=api_key_file`; variable refusée au démarrage. |
| `GEMMA_CA_BUNDLE` | `security.secrets.tls_ca_certificate_path` | Référencé par chemin seulement quand `tls_mode=ca_bundle`; variable refusée au démarrage. |
| `API_PORT` | `services.api.port` | Migrée dans le fichier; variable refusée au démarrage. |
| `LLM_GATEWAY_PORT` | `services.llm_gateway.port` | Migrée dans le fichier; variable refusée au démarrage. |
| `SPARK_ALLOWED_CLIENT_CIDRS` | `deployment.hosts.spark_inference.allowed_client_cidrs` | Migrée dans le fichier; variable refusée au démarrage. |

## Contrat de sécurité

Les chemins de secrets sont obligatoires dans `security.secrets`. Ils pointent vers des fichiers montés en lecture seule hors Git, par exemple `config/secrets/local/postgres_password`. Le schéma refuse les propriétés génériques `password`, `token`, `api_key`, `secret` ou `secret_value` afin d'empêcher un secret en clair dans l'artefact versionné.

La configuration peut exiger TLS ou une clé d'API, mais l'exigence est déclarée dans `deployment.network` et les chemins de matériaux secrets restent dans `security.secrets`. Aucune valeur système du shell ne complète ces champs.

Pour le Spark Docker actuel gouverné par ADR-014, `services.llm_gateway.auth_mode` vaut `none` et `services.llm_gateway.tls_mode` vaut `disabled`. Dans ce mode, le gateway ne lit pas `security.secrets.llm_gateway_api_key_path`, n'injecte aucun header `Authorization`, ne lit pas `security.secrets.tls_ca_certificate_path` et conserve les pannes Spark sous forme d'erreurs explicites comme `LLM_UNAVAILABLE`.

## Contrat de traçabilité

Chaque chargement valide produit une configuration hashée. Les rapports d'évaluation, de démarrage et d'exploitation référencent ce hash avec les versions de code, modèle et runtime. Un hash manquant est une non-conformité de traçabilité pour M13-config.

ADR-026 retire du schéma les clés d'observabilité sans consommateur applicatif réel : `metrics`, chemin de traces, niveau et rétention applicative. Comme `additionalProperties` vaut `false`, leur présence produit `CONFIG_SCHEMA_INVALID`. La rotation des logs relève de la configuration explicite du moteur de conteneurs et ne constitue pas une clé applicative implicite.

Dans Compose, `deploy/local-compose/application.compose.yaml` est une variante versionnée du même contrat strict : elle utilise les DNS `postgres`, `qdrant`, `llm-gateway` et `orchestrator-api`, ainsi que les chemins de secrets montés dans les conteneurs. Elle ne constitue ni un second schéma ni un fallback vers l'environnement.

## Commandes de validation

- `uv run --locked gate`
- `uv run --locked gate`
- `uv run --locked gate`
- `uv run --locked gate`

## Exclusions historiques T-002

- Aucun chargeur applicatif n'est implémenté dans cette tâche.
- Aucun fichier `app/...` n'est modifié.
- Aucun changement Compose ou runbook opératoire n'est livré ici.
- Aucun fallback temporaire n'est introduit pour faciliter la migration.

Ces exclusions décrivent la publication initiale T-002. Les tâches aval ont depuis livré le chargeur, Compose et les runbooks sans modifier l'interdiction de fallback.
