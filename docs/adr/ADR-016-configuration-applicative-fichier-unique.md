# ADR-016 - Configuration applicative par fichier unique

**Statut :** Acceptée
**Date :** 2026-07-10
**Décideurs :** Propriétaire du projet
**Remplace :** Aucun
**Remplacée par :** Aucune
**Source :** Demande utilisateur du 2026-07-10; `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`; `docs/specs/plan_implementation_milestones_workstreams.md`

## Contexte

La configuration actuelle du plan et de certaines décisions mentionne des variables de type `GEMMA_*`, `DATABASE_URL`, `QDRANT_URL`, `LLM_GATEWAY_URL` ou des blocs Compose `environment:`. Ce mode d'entrée rend possible une dérive silencieuse entre l'environnement du shell, les conteneurs, les scripts et la documentation.

Le projet interdit les valeurs par défaut implicites et les fallbacks silencieux. Cette interdiction doit aussi s'appliquer à la source de configuration: une variable système ne doit pas pouvoir remplacer, compléter ou contredire le fichier déclaré par l'exploitant.

## Décision

Tout processus applicatif DOIT charger sa configuration depuis un fichier unique `config/application.yaml`, dont le chemin est fourni explicitement au lancement par un argument `--config <chemin>`.

Les valeurs qui pilotent l'application DOIVENT être présentes dans ce fichier: URLs internes, endpoint Spark, modèle servi, provenance modèle, modes d'authentification et TLS, timeouts, ports applicatifs, chemins de données, profils de charge, seuils, chemins de secrets et paramètres de sécurité.

Un processus applicatif NE DOIT PAS accepter de variable d'environnement comme entrée de configuration. Il NE DOIT PAS lire `os.environ`, `getenv`, `process.env`, `.env`, `env_file` ou `environment:` Compose pour piloter l'application.

La présence d'une variable d'environnement homonyme d'une clé applicative connue DOIT faire échouer le démarrage avec `CONFIG_ENV_INPUT_REJECTED`. Elle ne doit pas être ignorée silencieusement.

Le fichier de configuration DOIT être validé avant tout accès à une ressource externe. Un fichier absent, illisible, invalide, incomplet, vide ou contenant une valeur placeholder DOIT produire une erreur explicite: `CONFIG_FILE_REQUIRED`, `CONFIG_FILE_UNREADABLE`, `CONFIG_SCHEMA_INVALID`, `CONFIG_KEY_MISSING` ou `CONFIG_KEY_EMPTY`.

Les secrets NE DOIVENT PAS être transmis par variable d'environnement. Le fichier de configuration peut référencer des chemins de fichiers secrets montés en lecture seule hors Git ou un store secret explicitement approuvé par ADR.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Continuer avec variables d'environnement explicites | Rejetée | Deux processus lancés depuis des shells différents peuvent diverger sans trace dans le fichier de configuration. |
| Fichier de configuration avec fallback environnement | Rejetée | Contredit l'interdiction de fallback et rend les audits de configuration incomplets. |
| Fichier de configuration unique sans fallback environnement | Retenue | Rend la configuration auditable, versionnable et testable au démarrage. |

## Conséquences

### Positives

- Le démarrage local devient reproductible à partir d'un artefact de configuration unique.
- Les audits peuvent comparer la configuration chargée, les rapports de benchmark et la provenance d'exécution.
- Les erreurs de configuration deviennent explicites avant tout appel réseau, lecture de base ou inférence Spark.

### Négatives ou coûts

- Les scripts de lancement, Compose et validateurs doivent cesser d'injecter des valeurs applicatives par environnement.
- Les anciens noms `GEMMA_*`, `DATABASE_URL`, `QDRANT_URL` et `LLM_GATEWAY_URL` doivent être migrés vers des clés de `config/application.yaml`.
- Les tests doivent couvrir les cas d'environnement pollué au lieu de seulement vérifier l'absence de clé manquante.

### Risques et contrôles

- Risque: un adaptateur lit encore une variable d'environnement par commodité. Contrôle: scan statique et test de démarrage avec variables homonymes.
- Risque: le chemin `--config` devient implicite dans un wrapper. Contrôle: démarrage sans `--config` refusé.
- Risque: un secret est copié dans le fichier versionné. Contrôle: schéma interdisant les contenus secrets directs et acceptant seulement des chemins ou références de store.

## Impact d'implémentation

- Modules concernés: `app/platform/configuration`, `app/platform/llm_gateway`, API, workers, scripts de lancement Compose et Spark.
- Configuration concernée: `config/application.yaml`, `config/application.schema.json`, `deploy/local-compose/compose.yaml`, scripts `deploy/spark-inference`.
- Tests attendus: chargement strict du fichier, refus de `--config` absent, refus des variables d'environnement homonymes, refus des clés manquantes ou vides, scan statique des accès environnement applicatifs.
- Milestones concernées: M-002, M-013, M13-config.

## Liens de traçabilité

- Spécification: sections 0, 3, 13, 16, 18, 20 et 22 de `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`.
- Plan d'implémentation: `docs/specs/plan_implementation_milestones_workstreams.md`, milestone `M13-config`.
- Tests d'acceptation: à créer dans `docs/tasks/milestone_013-config`.
- Commits: RED et GREEN à renseigner après livraison.

## Notes

Les identifiants historiques tels que `GEMMA_BASE_URL` ou `GEMMA_MODEL_REVISION` restent utiles pour reconnaître les anciennes entrées à refuser, mais ils ne sont plus des entrées de processus acceptées.
