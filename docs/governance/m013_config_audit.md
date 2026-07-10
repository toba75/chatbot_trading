# Audit M13-config - Configuration applicative sans environnement

## Statut

- Sous-milestone: `M13-config`.
- Décision appliquée: ADR-016 - Configuration applicative par fichier unique.
- Statut M13-config: clôture technique et documentaire prête après validation T-008.
- Statut M-013: M-013 entier non clôturé.
- Statut V1: V1 non acceptée.
- Limites opérationnelles: `config/application.yaml` réel requis pour les démarrages locaux et Spark live requis pour les chemins réels M13-reality.

## Scénario BDD audité

- Given les tâches M13-config ont migré configuration, gateway, Compose, scans et runbooks.
- When les gates de traçabilité et de lint sont exécutées.
- Then chaque exigence ADR-016 est reliée à une preuve et toute régression d'entrée par environnement bloque la validation.

## Décision ADR-016 appliquée

ADR-016 impose que les processus applicatifs lisent leur configuration depuis `config/application.yaml` via `--config`, sans fallback vers le shell, `.env`, `env_file` ou `environment:` Compose. La preuve M13-config vérifie aussi que les erreurs publiques restent explicites: `CONFIG_FILE_REQUIRED`, `CONFIG_SCHEMA_INVALID`, `CONFIG_ENV_INPUT_REJECTED` et les erreurs de clé ou secret invalides.

La configuration valide produit `configuration_hash`, qui doit être conservé dans les logs, métriques et rapports d'exploitation. Un hash absent reste une non-conformité de traçabilité pour M13-config.

## Exigences et preuves

| Exigence | Tâche | Preuve RED | Preuve GREEN | Artefacts |
|---|---|---|---|---|
| REQ-M013-CONFIG-001 | T-001 précondition | RED non créé: précondition documentaire sans échec artificiel | `4d8cbb7a1` `docs(m13-config): publier preuve precondition green` | `docs/tasks/milestone_013-config/journal.md`; `scripts/validate_task_system.ps1` |
| REQ-M013-CONFIG-002 | T-002 contrat de configuration | `38cd1b46e` `test(m13-config): couvrir specification configuration applicative` | `b3327c5a8` `docs(m13-config): publier contrat configuration applicative` | `docs/specs/m013_config_configuration_applicative.md`; `config/application.schema.json`; `config/application.example.yaml` |
| REQ-M013-CONFIG-003 | T-003 chargeur sans environnement | `953ba59a3` `test(platform): couvrir chargement configuration fichier unique`; `44d1201f0` `test(platform): interdire dependances externes configuration` | `543804a2c` `feat(platform): charger configuration applicative sans environnement`; `97ae808aa` `fix(platform): supprimer dependances externes configuration` | `app/platform/configuration/__init__.py`; tests loader M13-config |
| REQ-M013-CONFIG-004 | T-004 gateway LLM par fichier | `65b0853db` `test(platform): couvrir gateway llm configure par fichier` | `38fa1010d` `feat(platform): migrer gateway llm vers application yaml` | `app/platform/local_runtime.py`; `app/platform/llm_gateway/__init__.py`; `app/platform/observability/__init__.py` |
| REQ-M013-CONFIG-005 | T-005 Compose par fichier | `288f5fe18` `test(platform): couvrir compose sans environnement applicatif` | `55886cdd7` `feat(platform): piloter compose par application yaml` | `deploy/local-compose/compose.yaml`; `app/platform/local_compose.py`; `app/platform/security/network_boundary.py` |
| REQ-M013-CONFIG-006 | T-006 gate environnement | `c9c4118c0` `test(governance): couvrir rejet environnement applicatif` | `ea544dc2d` `feat(governance): bloquer entrees environnement applicatives` | `scripts/validate_m013_config_environment.ps1`; `scripts/validate_m013_config_environment.py` |
| REQ-M013-CONFIG-007 | T-007 runbooks migration | `2166e787a` `test(docs): couvrir runbooks configuration sans environnement` | `8db59074f` `docs(runbooks): publier migration application yaml` | `docs/runbooks/configuration_applicative.md`; runbooks exploitation, Spark et certificats |
| REQ-M013-CONFIG-008 | T-008 traçabilité et gates | `42ef2be63` `test(governance): couvrir tracabilite m13 config` | Commit attendu par cette livraison: `docs(governance): relier m13 config aux gates` | `docs/traceability/matrix.md`; `scripts/validate_m013_config_traceability.ps1`; `docs/governance/m013_config_audit.md`; `scripts/test.ps1`; `scripts/lint.ps1` |

## Validations attendues

- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_m013_config_traceability_acceptance.ps1`
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_config\validate_m013_config_traceability_unit.ps1`
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_config_traceability.ps1`
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_config_environment.ps1`
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability.ps1`
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`

## Gates enrôlées

- `scripts/test.ps1` contient les validations M13-config et les tests d'acceptation/unitaires M13-config.
- `scripts/lint.ps1` contient `scripts/validate_m013_config_environment.ps1` et `scripts/validate_m013_config_traceability.ps1`.
- La matrice `docs/traceability/matrix.md` expose les lignes `REQ-M013-CONFIG-001` à `REQ-M013-CONFIG-008`.

## Limites et risques résiduels

- `config/application.yaml` réel requis: le dépôt versionne `config/application.example.yaml` et le schéma, mais l'installation locale doit créer son fichier réel hors secret en clair.
- Spark live requis: les chemins réels M13-reality restent bloqués tant que le Spark local et le fichier réel ne sont pas disponibles.
- Ce rapport ne clôt pas M-013 entier et ne transforme pas les écarts V1 restants en acceptation produit.
- Les tests synthétiques prouvent les contrats et gates; ils ne remplacent pas une exécution live Spark avec configuration locale réelle.
