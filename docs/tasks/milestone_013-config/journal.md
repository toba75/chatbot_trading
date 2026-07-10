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
