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
