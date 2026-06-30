# Journal M-007

## Planification initiale

- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, milestone `M-007 - Réponse documentaire vérifiée`.
- Dépendance amont: M-006, présent dans `master` au commit `236c2420a84c0439e8d1c101eb2251ba44069fa9`, identique à `origin/master` après `git fetch origin --prune`.
- Précondition observée pendant la planification: `scripts/test.ps1` a expiré une première fois à 904 secondes puis a conclu GREEN après relance large avec `15 validation(s), 134 test(s)`; `scripts/lint.ps1` GREEN avec `15 validation(s), 0 test(s)`; `scripts/validate_task_system.ps1` GREEN avec `7 milestone(s), 67 tâche(s) contrôlée(s)` avant création de M-007; `git diff --check` GREEN.
- Découpage retenu: précondition, spécification RA, cas de recherche avec mandat, jeu de preuves scellé, contradictions et lacunes, extraction d'assertions, support et citations, abstention pour données actuelles, commande `POST /v1/answer`, puis traçabilité et métriques.
- ADR: aucune nouvelle ADR planifiée à ce stade; les tâches appliquent les ADR existantes et exigent une nouvelle ADR si une décision structurante change le contrat public RA, la politique durable de fraîcheur ou le stockage des preuves.

