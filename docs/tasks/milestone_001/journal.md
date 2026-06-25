# Journal M-001 - Frontières DDD et contrats publiés

## Branche
- Branche: à renseigner lors de l'exécution.
- Base: `master`.
- Remote: `origin`.

## Précondition observée lors de la planification
- Date: 2026-06-25.
- `git fetch origin --prune`: GREEN.
- Présence de M-000 dans `master`: GREEN, `docs/tasks/milestone_000`, les scripts M-000, les ADR et les specs sont visibles.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`: RED sur `scripts/validate_task_system.ps1`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`: RED sur `scripts/validate_task_system.ps1`.
- Cause RED observée: `Titre de tâche invalide ou absent: 0001_verifier_precondition_green.md`.

## Tâches planifiées
- T-001 - Vérifier la précondition GREEN de M-001.
- T-002 - Publier la spécification des frontières DDD.
- T-003 - Déclarer les contextes et propriétaires de données.
- T-004 - Publier les identifiants opaques et versions de contrats.
- T-005 - Publier CanonicalSourceRef et SourceLocator.
- T-006 - Publier EvidenceRef et VerifiedClaimRef.
- T-007 - Publier VerifiedResearchOutcome vers la stratégie.
- T-008 - Publier StrategySnapshot et ExperimentResult.
- T-009 - Publier l'enveloppe d'événement versionnée.
- T-010 - Interdire les couplages intercontextes.
- T-011 - Relier M-001 à la traçabilité et aux gates.

## Suivi d'exécution
- Statut initial: non démarré.
