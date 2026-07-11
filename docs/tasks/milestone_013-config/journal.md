# Journal M13-config

## Planification

- Sous-milestone: `M13-config`, matérialisé dans `docs/tasks/milestone_013-config`.
- Règle de gouvernance: ce dossier est un sous-milestone de M-013; il ne requiert pas la clôture de `docs/tasks/milestone_013` dans `master` et ne clôture pas M-013 pour les milestones aval.
- Source principale: `docs/specs/plan_implementation_milestones_workstreams.md`, section `M13-config`.
- ADR structurante: ADR-016 - Configuration applicative par fichier unique.
- Précondition amont: M-000 à M-012 doivent être visibles dans `master`.

## Intention

Remplacer les variables d'environnement applicatives par `config/application.yaml`, sans fallback vers `os.environ`, `.env`, `env_file` ou `environment:` Compose. Le sous-milestone doit couvrir la spécification, le chargeur de configuration, le gateway LLM, Compose, les scans anti-régression, les runbooks et la traçabilité.

## Tâches créées

- T-001: vérifier la précondition GREEN de M13-config.
- T-002: publier la spécification de configuration applicative.
- T-003: charger la configuration depuis un fichier unique.
- T-004: migrer le gateway LLM vers la configuration applicative.
- T-005: migrer Compose et le déploiement vers le fichier de configuration.
- T-006: bloquer les entrées d'environnement applicatives.
- T-007: publier les runbooks de migration de configuration.
- T-008: relier M13-config à la traçabilité et aux gates.

## Limite de cette planification

Cette étape crée les tâches de sous-milestone uniquement. Elle ne modifie pas encore `app/...`, `deploy/local-compose/compose.yaml`, les runbooks opérationnels existants ni les scripts de validation M13-config attendus par les tâches.

## T-001 - Précondition GREEN

Date d'exécution: 2026-07-10.

Scénario contrôlé:

- Given le sous-milestone `M13-config` est demandé.
- When la précondition de planification est contrôlée contre `master` et les gates locales.
- Then M-000 à M-012 sont présents, M-013 n'est pas exigé comme clôturé, et les gates de gouvernance restent GREEN.

Références Git observées:

- Branche courante: `codex/m13-config`.
- `HEAD`: `4d411178d`.
- `master`: `4d411178d`.

Commandes exécutées:

- `git fetch origin --prune` - GREEN.
- `git ls-tree -r --name-only master -- docs/tasks/milestone_000 docs/tasks/milestone_001 docs/tasks/milestone_002 docs/tasks/milestone_003 docs/tasks/milestone_004 docs/tasks/milestone_005 docs/tasks/milestone_006 docs/tasks/milestone_007 docs/tasks/milestone_008 docs/tasks/milestone_009 docs/tasks/milestone_010 docs/tasks/milestone_011 docs/tasks/milestone_012` - GREEN; chaque dossier M-000 à M-012 a retourné au moins un fichier.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_task_system.ps1` - GREEN; `15 milestone(s), 165 tâche(s) contrôlée(s)`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1` - GREEN; `35 validation(s), 0 test(s)`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\governance\validate_task_system_unit.ps1` - GREEN; tests unitaires du validateur des tâches OK.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\governance\validate_task_system_acceptance.ps1` - GREEN; test d'acceptation de la convention des tâches OK.
- `git diff --check` - GREEN; avertissement Git de normalisation LF vers CRLF sur `journal.md`, sans erreur whitespace.

Détail de présence dans `master`:

- `docs/tasks/milestone_000`: présent, 7 fichier(s).
- `docs/tasks/milestone_001`: présent, 12 fichier(s).
- `docs/tasks/milestone_002`: présent, 12 fichier(s).
- `docs/tasks/milestone_003`: présent, 10 fichier(s).
- `docs/tasks/milestone_004`: présent, 11 fichier(s).
- `docs/tasks/milestone_005`: présent, 11 fichier(s).
- `docs/tasks/milestone_006`: présent, 11 fichier(s).
- `docs/tasks/milestone_007`: présent, 11 fichier(s).
- `docs/tasks/milestone_008`: présent, 12 fichier(s).
- `docs/tasks/milestone_009`: présent, 12 fichier(s).
- `docs/tasks/milestone_010`: présent, 12 fichier(s).
- `docs/tasks/milestone_011`: présent, 13 fichier(s).
- `docs/tasks/milestone_012`: présent, 13 fichier(s).

Décision de workflow:

- Aucun test RED utile n'a été ajouté: la tâche T-001 est une preuve de précondition et réutilise les validations existantes `tests/governance/validate_task_system_acceptance.ps1`, `tests/governance/validate_task_system_unit.ps1` et `scripts/validate_task_system.ps1`.
- Aucun commit RED n'est créé pour éviter de simuler un échec artificiel.
- Aucune modification de `app/...` n'est effectuée.

Statut: GREEN.

## T-002 - Spécification de configuration applicative

Date d'exécution: 2026-07-10.

Scénario couvert:

- Given l'exploitant prépare un fichier `config/application.yaml`.
- When le contrat de configuration est validé.
- Then chaque valeur nécessaire au démarrage est présente dans le fichier, le schéma refuse les absences et aucun fallback environnement n'est décrit.

ADR consultée:

- ADR-016 - Configuration applicative par fichier unique.

Artefacts publiés:

- `docs/specs/m013_config_configuration_applicative.md`.
- `config/application.schema.json`.
- `config/application.example.yaml`.
- `tests/m013_config/validate_application_config_specification_acceptance.ps1`.
- `tests/m013_config/validate_application_config_specification_unit.ps1`.

Décision de workflow:

- Le commit RED ajoute uniquement les validateurs d'acceptation et unitaires du contrat.
- Le commit GREEN publie la spécification, le schéma strict, l'exemple non secret et cette preuve de journal.
- Aucune modification de `app/...` n'est effectuée.

Preuve RED:

- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_application_config_specification_acceptance.ps1` - RED attendu; `Spécification de configuration absente: docs/specs/m013_config_configuration_applicative.md`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_application_config_specification_unit.ps1` - RED attendu; `Schéma de configuration absent: config/application.schema.json`.

Commandes GREEN exécutées:

- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_application_config_specification_acceptance.ps1` - GREEN; `Test d'acceptation du contrat de configuration applicative: OK`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_application_config_specification_unit.ps1` - GREEN; `Tests unitaires du contrat de configuration applicative: OK`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_adr_system.ps1` - GREEN; `Système ADR valide: 28 ADR contrôlées, 20 décisions section 3 matérialisées`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1` - GREEN; `35 validation(s), 0 test(s)`.

Statut: GREEN après exécution des commandes T-002.

## T-003 - Chargement de configuration depuis un fichier unique

Date d'exécution: 2026-07-10.

Scénario couvert:

- Given un processus applicatif reçoit `--config config/application.yaml`.
- When le fichier est lisible, conforme et qu'aucune variable homonyme n'est présente.
- Then le chargeur retourne une configuration validée et aucun accès à l'environnement ne pilote l'application.

ADR consultée:

- ADR-016 - Configuration applicative par fichier unique.

Artefacts livrés:

- `app/platform/configuration/__init__.py`.
- `tests/m013_config/validate_application_config_loader_acceptance.ps1`.
- `tests/m013_config/validate_application_config_loader_unit.ps1`.

Décision de workflow:

- Le commit RED ajoute uniquement le test d'acceptation du chargeur.
- L'implémentation GREEN expose `load_application_configuration(config_path, environment_snapshot)`, des value objects gelés, des erreurs publiques `CONFIG_*`, la validation du schéma T-002, le rejet des variables historiques ou homonymes et le hash stable de configuration.
- Aucun changement de schéma ou d'exemple n'a été nécessaire.
- Aucun module `local_runtime`, gateway LLM ou Compose n'est migré dans cette tâche.

Preuve RED:

- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_application_config_loader_acceptance.ps1` - RED attendu; `ImportError: cannot import name 'ApplicationConfigurationError' from 'app.platform.configuration'`.
- Commit RED: `953ba59a3` (`test(platform): couvrir chargement configuration fichier unique`).

Commandes GREEN exécutées:

- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_application_config_loader_acceptance.ps1` - GREEN; `Test d'acceptation du chargeur de configuration applicative: OK`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_application_config_loader_unit.ps1` - GREEN; `Tests unitaires du chargeur de configuration applicative: OK`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_architecture_boundaries.ps1 -AppRoot .\app -ContextRegistryPath .\app\context_registry.json -SpecificationPath .\docs\specs\m001_frontieres_ddd_contrats_publies.md` - GREEN; `Frontières d'import M-001 valides: 183 fichier(s), 1128 import(s) contrôlé(s)`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1` - GREEN; `Gate lint GREEN: 35 validation(s), 0 test(s)`.

Note de validation:

- La commande directe `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_architecture_boundaries.ps1` est déjà RED sans modification T-003, car ce validateur exige les paramètres obligatoires `AppRoot`, `ContextRegistryPath` et `SpecificationPath`.
- Le gate `scripts/lint.ps1` appelle ce même validateur avec ses paramètres canoniques et reste GREEN.

Statut: GREEN pour le chargeur applicatif T-003; risque résiduel limité à l'incohérence de commande documentée ci-dessus.

### Correction T-003 - Suppression des dépendances Python implicites

Date d'exécution: 2026-07-10.

Écart détecté:

- Le chargeur T-003 importait `yaml` et `jsonschema`, et les tests loader importaient `yaml`.
- Le dépôt ne publie aucun manifeste de dépendances Python (`requirements`, `pyproject`, `poetry.lock`, `uv.lock`), donc ces imports constituaient une dépendance implicite non traçable.

Preuve RED corrective:

- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_application_config_loader_dependencies_unit.ps1` - RED attendu; `Dépendance Python externe interdite dans T-003: import yaml dans app/platform/configuration/__init__.py`.
- Commit RED correctif: `44d1201f0` (`test(platform): interdire dependances externes configuration`).

Correction livrée:

- Remplacement de `yaml.safe_load` par un parseur YAML standard library limité au sous-ensemble strict utilisé par `config/application.example.yaml`: mappings indentés, listes scalaires et scalaires `string`, `integer`, `number`, `boolean`.
- Remplacement de `Draft202012Validator` par un validateur local couvrant les mots-clés utilisés par `config/application.schema.json`: `$ref`, `type`, `required`, `properties`, `additionalProperties`, `enum`, `const`, `minimum`, `maximum`, `minLength`, `pattern`, `items`, `minItems` et `not`.
- Retrait des imports externes dans les tests loader; les variantes de configuration sont maintenant produites par mutation textuelle contrôlée.
- Aucun changement `local_runtime`, gateway LLM ou Compose.

Commandes GREEN exécutées:

- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_application_config_loader_dependencies_unit.ps1` - GREEN; `Tests unitaires dépendances chargeur de configuration applicative: OK`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_application_config_loader_acceptance.ps1` - GREEN; `Test d'acceptation du chargeur de configuration applicative: OK`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_application_config_loader_unit.ps1` - GREEN; `Tests unitaires du chargeur de configuration applicative: OK`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_architecture_boundaries.ps1 -AppRoot .\app -ContextRegistryPath .\app\context_registry.json -SpecificationPath .\docs\specs\m001_frontieres_ddd_contrats_publies.md` - GREEN; `Frontières d'import M-001 valides: 183 fichier(s), 1127 import(s) contrôlé(s)`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1` - GREEN; `Gate lint GREEN: 35 validation(s), 0 test(s)`.

Statut: GREEN correctif après validation finale.

## T-004 - Migration du gateway LLM vers la configuration applicative

Date d'exécution: 2026-07-10.

Scénario couvert:

- Given `config/application.yaml` déclare le Spark réel, le modèle servi et la provenance LLM.
- When le chat produit ou le benchmark LLM exécute une inférence.
- Then le gateway utilise les valeurs du fichier, rejette les homonymes d'environnement et conserve la provenance complète avec le hash de configuration.

ADR consultées:

- ADR-014 - Endpoint Docker Spark externe sans clé API.
- ADR-015 - Provenance LLM déclarée par le gateway.
- ADR-016 - Configuration applicative par fichier unique.

Artefacts livrés:

- `app/platform/local_runtime.py`.
- `app/platform/llm_gateway/__init__.py`.
- `app/platform/observability/__init__.py`.
- `app/platform/configuration/__init__.py`.
- `config/application.schema.json`.
- `config/application.example.yaml`.
- `docs/specs/m013_config_configuration_applicative.md`.
- `tests/m013_config/validate_llm_gateway_config_file_acceptance.ps1`.
- `tests/m013_config/validate_llm_gateway_config_file_unit.ps1`.
- `tests/m013/validate_llm_gateway_real_spark_acceptance.ps1`.
- `tests/m013/validate_m013_reality_product_acceptance.ps1`.
- `tests/m013/validate_m013_reality_product_unit.ps1`.
- `scripts/validate_m013_reality.ps1`.

Décision de workflow:

- Le commit RED ajoute uniquement les tests T-004 du gateway configuré par fichier.
- L'implémentation GREEN remplace la construction `GatewayConfiguration` depuis `GEMMA_*` par `ApplicationConfiguration`.
- `auth_mode`, `tls_mode` et `retry_before_first_token` deviennent des clés obligatoires du fichier applicatif.
- En mode `auth_mode=none` et `tls_mode=disabled`, le gateway n'injecte aucun header `Authorization` et ne lit pas les chemins de secrets Spark.
- `configuration_hash` est propagé dans `GatewayConfiguration`, les logs et les métriques gateway.
- Compose, `scripts/test.ps1`, `scripts/lint.ps1` et les runbooks ne sont pas migrés dans cette tâche.

Preuve RED:

- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_llm_gateway_config_file_unit.ps1` - RED attendu; `_build_gateway_configuration_from_application_configuration` absent.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_llm_gateway_config_file_acceptance.ps1` - RED attendu; le runtime `serve-http` démarre sans `--config`.
- Commit RED: `65b0853db` (`test(platform): couvrir gateway llm configure par fichier`).

Commandes GREEN exécutées:

- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_llm_gateway_config_file_acceptance.ps1` - GREEN; `Test d'acceptation T-004 gateway LLM configuré par fichier: OK`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_llm_gateway_config_file_unit.ps1` - GREEN; `Tests unitaires T-004 gateway LLM configuré par fichier: OK`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_application_config_loader_acceptance.ps1` - GREEN; `Test d'acceptation du chargeur de configuration applicative: OK`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_application_config_loader_unit.ps1` - GREEN; `Tests unitaires du chargeur de configuration applicative: OK`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_application_config_specification_acceptance.ps1` - GREEN; `Test d'acceptation du contrat de configuration applicative: OK`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_application_config_specification_unit.ps1` - GREEN; `Tests unitaires du contrat de configuration applicative: OK`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_m013_reality_product_unit.ps1` - GREEN; `Tests unitaires M13-reality produit: OK`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m002\validate_llm_gateway_contract_acceptance.ps1` - GREEN; `Test d'acceptation contrat gateway LLM M-002: OK`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m002\validate_llm_gateway_contract_unit.ps1` - GREEN; `Tests unitaires contrat gateway LLM M-002: OK`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m002\validate_llm_gateway_failures_acceptance.ps1` - GREEN; `Test d'acceptation pannes gateway LLM M-002: OK`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m002\validate_llm_gateway_failures_unit.ps1` - GREEN; `Tests unitaires pannes gateway LLM M-002: OK`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m002\validate_gateway_observability_acceptance.ps1` - GREEN; `Test d'acceptation observabilité gateway M-002: OK`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m002\validate_gateway_observability_unit.ps1` - GREEN; `Tests unitaires observabilité gateway M-002: OK`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1` - GREEN; `Gate lint GREEN: 35 validation(s), 0 test(s)`.

Validation live Spark:

- Commande tentée: `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_reality.ps1`.
- Résultat: impossible sans configuration locale réelle; le script échoue explicitement sur `Configuration locale requise pour le test réel M13-reality: C:\Users\maxim\python\chatbot_trading\config\application.yaml`.
- Aucun test live Spark n'a été converti en fixture et aucune provenance n'a été inventée.

Statut: GREEN hors réseau pour T-004; validation live Spark bloquée par l'absence de `config/application.yaml` local réel.

## T-005 - Migration Compose vers le fichier de configuration

Date d'exécution: 2026-07-10.

Scénario couvert:

- Given le fichier `config/application.yaml` est monté en lecture seule dans les services applicatifs.
- When la pile locale est validée et démarrée.
- Then chaque processus reçoit `--config`, aucune valeur applicative n'est transmise par `environment:` ou `env_file`, et la frontière Spark reste contrôlée.

ADR consultées:

- ADR-014 - Endpoint Docker Spark externe sans clé API.
- ADR-016 - Configuration applicative par fichier unique.

Artefacts livrés:

- `deploy/local-compose/compose.yaml`.
- `deploy/local-compose/README.md`.
- `app/platform/local_compose.py`.
- `app/platform/security/network_boundary.py`.
- `tests/m013_config/validate_compose_config_file_acceptance.ps1`.
- `tests/m013_config/validate_compose_config_file_unit.ps1`.
- `tests/m002/validate_local_compose_acceptance.ps1`.
- `tests/m002/validate_local_compose_unit.ps1`.
- `tests/m002/validate_network_boundary_acceptance.ps1`.
- `tests/m002/validate_network_boundary_unit.ps1`.

Décision de workflow:

- Le commit RED ajoute uniquement les tests T-005 du Compose sans environnement applicatif.
- L'implémentation GREEN retire les variables applicatives des services `ostrading/*`, ajoute `--config /workspace/config/application.yaml`, monte `../../config/application.yaml:/workspace/config/application.yaml:ro` et interdit `env_file`.
- Les variables techniques restantes sont explicitement allowlistées: `CADDY_ADMIN` pour Caddy, `POSTGRES_DB`, `POSTGRES_USER` et `POSTGRES_PASSWORD_FILE` pour l'image PostgreSQL.
- Les contrôles M-002 conservent les refus de ports internes, de service Gemma/vLLM local et de `spark-egress` hors `llm-gateway`.
- `scripts/test.ps1`, `scripts/lint.ps1`, les runbooks généraux et la matrice de traçabilité ne sont pas modifiés dans cette tâche.

Preuve RED:

- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_compose_config_file_acceptance.ps1` - RED attendu; `Entrée applicative interdite présente dans le Compose canonique: DATABASE_URL:`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_compose_config_file_unit.ps1` - RED attendu; `Commande Compose invalide pour service ui`.
- Commit RED: `288f5fe18` (`test(platform): couvrir compose sans environnement applicatif`).

Commandes GREEN exécutées:

- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_compose_config_file_acceptance.ps1` - GREEN; `Test d'acceptation Compose M13-config: OK`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_compose_config_file_unit.ps1` - GREEN; `Tests unitaires Compose M13-config: OK`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m002\validate_local_compose_acceptance.ps1` - GREEN; `Test d'acceptation Compose local M-002: OK`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m002\validate_local_compose_unit.ps1` - GREEN; `Tests unitaires Compose local M-002: OK`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m002\validate_network_boundary_acceptance.ps1` - GREEN; `Test d'acceptation frontière réseau M-002: OK`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m002\validate_network_boundary_unit.ps1` - GREEN; `Tests unitaires frontière réseau M-002: OK`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_local_compose.ps1` - GREEN; `Compose local M-002 valide: 13 service(s), 3 réseau(x), 1 secret(s) contrôlé(s).`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_network_boundary.ps1` - GREEN; `Frontière réseau M-002 valide: 13 service(s) Compose, 1 règle(s) Spark, transport Spark et egress contrôlés.`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1` - GREEN; `Gate lint GREEN: 35 validation(s), 0 test(s)`.

Statut: GREEN pour T-005; la validation Compose contrôle le montage `config/application.yaml` mais ne requiert pas le fichier local réel, qui reste propre à l'installation.

## T-006 - Blocage des entrées d'environnement applicatives

Date d'exécution: 2026-07-10.

Scénario couvert:

- Given une modification réintroduit une lecture de variable d'environnement applicative.
- When la gate M13-config inspecte le code, Compose, les scripts et la documentation d'exploitation.
- Then la validation échoue avec `CONFIG_ENV_INPUT_REJECTED` et un diagnostic `chemin:ligne` avant tout démarrage.

ADR consultée:

- ADR-016 - Configuration applicative par fichier unique.

Artefacts livrés:

- `tests/m013_config/validate_environment_input_rejection_acceptance.ps1`.
- `tests/m013_config/validate_environment_input_rejection_unit.ps1`.
- `scripts/validate_m013_config_environment.ps1`.
- `scripts/validate_m013_config_environment.py`.
- `scripts/lint.ps1`.
- `scripts/test.ps1`.
- Ajustements minimaux de mentions opérationnelles dans `docs/runbooks/exploitation_locale.md`, `docs/runbooks/spark_reseau_incidents.md`, `docs/runbooks/certificats_spark.md` et `deploy/local-compose/README.md`.

Décision de workflow:

- Le commit RED ajoute uniquement les tests d'acceptation et unitaires qui exigent la gate anti-environnement.
- L'implémentation GREEN crée une gate statique bornée aux racines `app`, `scripts`, `deploy` et `docs/runbooks`, avec refus de `os.environ`, `getenv`, `process.env`, `.env`, `env_file`, `environment:` applicatif, clés historiques et variables homonymes shell.
- Les exceptions sont nommées et testées: l'instantané `dict(os.environ)` de `app/platform/local_runtime.py` sert uniquement au rejet explicite, les registres de rejet `platform.configuration`, `local_compose` et `network_boundary` conservent les marqueurs interdits, les validateurs M13 existants peuvent chercher les patterns de secrets `GEMMA_API_KEY`/`VLLM_API_KEY`, et les gardes de récursion PowerShell restent techniques.
- Les runbooks ne sont pas migrés complètement dans cette tâche; seules les lignes qui prescrivaient encore des variables de shell applicatives ont été remplacées par des références à `config/application.yaml`.

Preuve RED:

- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_environment_input_rejection_acceptance.ps1` - RED attendu; `Validateur environnement M13-config absent: scripts/validate_m013_config_environment.ps1`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_environment_input_rejection_unit.ps1` - RED attendu; `Validateur environnement M13-config absent: scripts/validate_m013_config_environment.ps1`.
- Commit RED: `c9c4118c` (`test(governance): couvrir rejet environnement applicatif`).

Commandes GREEN exécutées:

- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_environment_input_rejection_acceptance.ps1` - GREEN; `Test d'acceptation rejet environnement M13-config: OK`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_environment_input_rejection_unit.ps1` - GREEN; `Tests unitaires rejet environnement M13-config: OK`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_config_environment.ps1` - GREEN; `Gate environnement M13-config GREEN: 257 fichier(s), 46 exception(s) technique(s) contrôlée(s).`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1` - GREEN; `Gate lint GREEN: 36 validation(s), 0 test(s)`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1` - T-006 appelée et GREEN, puis arrêt indépendant sur `scripts/validate_m013_reality.ps1` faute de fichier local réel `config/application.yaml`.

Statut: GREEN pour T-006; `scripts/test.ps1` reste non conclusif au-delà de T-006 tant que `config/application.yaml` local réel n'est pas fourni pour M13-reality.

## T-007 - Runbooks de migration de configuration

Date d'exécution: 2026-07-10.

Scénario couvert:

- Given un exploitant local lit les runbooks après M13-config.
- When il prépare et démarre la pile V1.
- Then chaque commande utilise `--config`, les anciennes variables sont présentées comme entrées rejetées, et la preuve d'audit cite le fichier chargé.

ADR consultée:

- ADR-016 - Configuration applicative par fichier unique.

Artefacts livrés:

- `docs/runbooks/configuration_applicative.md`.
- `tests/m013_config/validate_config_runbooks_acceptance.ps1`.
- `tests/m013_config/validate_config_runbooks_unit.ps1`.
- `docs/runbooks/exploitation_locale.md`.
- `docs/runbooks/spark_reseau_incidents.md`.
- `docs/runbooks/certificats_spark.md`.
- `deploy/local-compose/README.md`.
- `scripts/validate_m013_config_environment.py`.

Décision de workflow:

- Le commit RED ajoute uniquement les tests d'acceptation et unitaires des runbooks de migration.
- L'implémentation GREEN publie le runbook `configuration_applicative`, met à jour les runbooks existants avec `config/application.yaml`, `--config`, les chemins de secrets hors Git et la preuve `configuration_hash`.
- La gate T-006 reste stricte: elle autorise les anciennes clés dans le nouveau runbook uniquement sur les lignes qui documentent explicitement migration, rejet ou interdiction; toute mention opérationnelle reste rejetée par `CONFIG_ENV_INPUT_REJECTED`.
- `scripts/test.ps1` et `scripts/lint.ps1` ne sont pas modifiés dans cette tâche; l'enrôlement global reste réservé à T-008.

Preuve RED:

- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_config_runbooks_acceptance.ps1` - RED attendu; `Document attendu absent: C:\Users\maxim\python\chatbot_trading\docs\runbooks\configuration_applicative.md`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_config_runbooks_unit.ps1` - RED attendu; `Document requis absent: docs/runbooks/configuration_applicative.md`.
- Commit RED: `2166e787a` (`test(docs): couvrir runbooks configuration sans environnement`).

Commandes GREEN exécutées:

- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_config_runbooks_acceptance.ps1` - GREEN; `Test d'acceptation runbooks configuration M13-config: OK`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_config_runbooks_unit.ps1` - GREEN; `Tests unitaires runbooks configuration M13-config: OK`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_runbooks.ps1` - GREEN; `Runbooks documentation utilisateur M-013 valides: 11 runbook(s), documentation utilisateur V1, commandes vérifiées, écarts V1 non acceptés visibles, aucun secret, aucun service interne publié, aucune promesse financière.`
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_config_environment.ps1` - GREEN; `Gate environnement M13-config GREEN: 258 fichier(s), 63 exception(s) technique(s) contrôlée(s).`
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_environment_input_rejection_acceptance.ps1` - GREEN; `Test d'acceptation rejet environnement M13-config: OK`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_environment_input_rejection_unit.ps1` - GREEN; `Tests unitaires rejet environnement M13-config: OK`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1` - GREEN; `Gate lint GREEN: 36 validation(s), 0 test(s)`.

Statut: GREEN pour T-007; le runbook documente les anciennes clés uniquement comme migration ou rejet, et aucun enrôlement global `scripts/test.ps1` / `scripts/lint.ps1` n'a été ajouté hors T-008.

## T-008 - Traçabilité, audit et gates M13-config

Date d'exécution: 2026-07-10.

Scénario couvert:

- Given les tâches M13-config ont migré configuration, gateway, Compose, scans et runbooks.
- When les gates de traçabilité et de lint sont exécutées.
- Then chaque exigence ADR-016 est reliée à une preuve et toute régression d'environnement bloque la validation.

ADR consultée:

- ADR-016 - Configuration applicative par fichier unique.

Artefacts livrés:

- `docs/governance/m013_config_audit.md`.
- `scripts/validate_m013_config_traceability.ps1`.
- `tests/m013_config/validate_m013_config_traceability_acceptance.ps1`.
- `tests/m013_config/validate_m013_config_traceability_unit.ps1`.
- `docs/traceability/matrix.md`.
- `scripts/test.ps1`.
- `scripts/lint.ps1`.

Décision de workflow:

- Le commit RED ajoute uniquement les tests d'acceptation et unitaires de traçabilité M13-config.
- L'implémentation GREEN ajoute les exigences `REQ-M013-CONFIG-001` à `REQ-M013-CONFIG-008`, le rapport d'audit, le validateur dédié et l'enrôlement dans les gates.
- Aucune ADR nouvelle n'est créée: ADR-016 couvre déjà la décision structurante.
- Ce sous-milestone ne clôt pas M-013 entier et ne déclare pas la V1 acceptée.

Preuve RED:

- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_m013_config_traceability_acceptance.ps1` - RED attendu; `Validateur de traçabilité M13-config absent: scripts/validate_m013_config_traceability.ps1`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_m013_config_traceability_unit.ps1` - RED attendu; `Validateur de traçabilité M13-config absent: scripts/validate_m013_config_traceability.ps1`.
- Commit RED: `42ef2be63` (`test(governance): couvrir tracabilite m13 config`).

Commandes GREEN exécutées:

- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_m013_config_traceability_acceptance.ps1` - GREEN; `Test d'acceptation T-008 traçabilité M13-config: OK`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_m013_config_traceability_unit.ps1` - GREEN; `Tests unitaires T-008 traçabilité M13-config: OK`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_config_traceability.ps1` - GREEN; `Traçabilité M13-config valide: 8 exigence(s), 8 tâche(s), V1 non acceptée.`
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability.ps1` - GREEN; `Matrice de traçabilité valide: 161 exigence(s) contrôlée(s).`
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1` - GREEN; `Gate lint GREEN: 37 validation(s), 0 test(s).`
- `git diff --check` - GREEN; avertissements Git de normalisation LF vers CRLF uniquement, sans erreur whitespace.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1` - GREEN jusqu'à `scripts/validate_m013_config_traceability.ps1`, puis RED indépendant sur `scripts/validate_m013_reality.ps1`: `Configuration locale requise pour le test réel M13-reality: C:\Users\maxim\python\chatbot_trading\config\application.yaml`.

Limites conservées:

- `config/application.yaml` réel requis pour les démarrages locaux et la preuve live.
- Spark live requis pour valider les chemins réels M13-reality.
- Les preuves synthétiques et statiques ne remplacent pas l'exécution réelle Spark.

Statut: GREEN pour T-008; la suite complète `scripts/test.ps1` reste bloquée uniquement par l'absence de `config/application.yaml` réel requis par M13-reality.
