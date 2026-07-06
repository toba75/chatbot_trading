# T-001 - Vérifier et rétablir la précondition GREEN M-013

## Milestone
- Nom: M-013 - Durcissement et acceptation V1.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, section `M-013 - Durcissement et acceptation V1`, `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 18 à 24, et `docs/governance/m012_v1_gap_report.md`.
- Objectif métier: démarrer le durcissement V1 uniquement depuis M-012 fusionné, avec les écarts V1 visibles et des gates de gouvernance exploitables.

## Contexte DDD
- Domaine: durcissement opérationnel et acceptation V1.
- Bounded context: transverse de gouvernance V1, avec dépendances vers tous les bounded contexts et la plateforme locale.
- Objectif métier: prouver que la branche M-013 part d'un `master` contenant M-012, que les écarts V1 M-012 sont consommables et qu'aucun état RED existant n'est masqué.
- Langage ubiquitaire: précondition GREEN, rapport d'écarts V1, gate, acceptation V1, écart bloquant, écart différé, `master`, preuve de commande.
- Invariants critiques: M-012 doit être visible dans `master`; la branche M-013 doit contenir `master`; tout RED préexistant reste explicite; aucun écart V1 n'est requalifié sans décision.
- Garde-fous: ne pas accepter une branche M-012 locale comme preuve de fusion; ne pas traiter un test RED comme bruit; ne pas créer de contournement pour la gate V1; ne pas changer le sens d'une ADR acceptée.

## Blocages Ou Préconditions
- État GREEN/RED connu: après `git fetch origin --prune` puis `git fetch origin master:master`, `master` et `origin/master` pointent sur `5ef94d942bda6ad0f3ceb29de4973fe6ac05d9c1`; `scripts/validate_task_system.ps1` est GREEN avec `13 milestone(s), 134 tâche(s) contrôlée(s)`; `scripts/lint.ps1` est GREEN avec `24 validation(s), 0 test(s)`; `scripts/test.ps1` est RED sur `tests/m003/validate_m003_precondition_acceptance.ps1` avec `La précondition M-003 doit être GREEN sur la base courante. Code obtenu: 1`.
- Présence des milestones amont dans master: M-012 requis et présent dans `master`, avec `docs/tasks/milestone_012`, `docs/specs/m012_evaluation_pilote_calibration.md`, `scripts/validate_m012_precondition.ps1`, `scripts/validate_m012_specification.ps1`, `scripts/validate_m012_traceability.ps1`, `tests/m012`, `app/evaluation`, `docs/governance/m012_v1_gap_report.md` et `docs/traceability/matrix.md`.
- Décisions manquantes: aucune pour planifier M-013; une ADR nouvelle sera requise seulement si M-013 change la politique de rétention, la sécurité inter-hôtes, la topologie Spark ou un critère d'acceptation V1.
- Risques: démarrer M-013 sans élargir explicitement les validateurs de précondition amont; considérer un écart bloquant M-012 comme accepté; confondre gate logicielle GREEN et acceptation scientifique V1.

## Tâches
### T-001 - Vérifier et rétablir la précondition GREEN M-013
- But métier: établir une base de durcissement V1 vérifiable avant toute décision d'acceptation.
- Portée DDD: gouvernance de précondition M-013, présence de M-012 dans `master`, rapport d'écarts V1 consommable, branche contenant `master`, rapport de précondition et absence de contournement des gates amont.
- Scénario BDD:
  - Given M-012 est présent dans `master` avec ses tâches, sa spécification, ses validateurs, ses tests, son contexte EV et son rapport d'écarts V1.
  - When les gates de précondition M-013 sont exécutées sur une branche M-013 créée depuis `master`.
  - Then M-013 ne peut commencer que si la présence M-012, les écarts V1, la branche de travail et les gates amont ont un verdict explicite.
- Tests d'acceptation à écrire: `tests/m013/validate_m013_precondition_acceptance.ps1`, qui échoue tant que M-012 n'est pas visible dans `master`, que `docs/governance/m012_v1_gap_report.md` est absent, qu'un écart V1 n'a pas de statut, que la branche ne contient pas `master`, qu'un gate requis n'a pas de sortie exploitable ou qu'un validateur amont refuse M-013.
- Tests unitaires à écrire: tests de `scripts/validate_m013_precondition.ps1` pour M-012 absent, rapport V1 absent, écart V1 sans statut, divergence `origin/master`, branche ne contenant pas `master`, gate RED non documentée, sortie de commande manquante, validateur amont ignorant M-013 et statut GREEN sans preuve.
- Implémentation attendue: créer `scripts/validate_m013_precondition.ps1`, créer `docs/governance/m013_precondition_green.md`, ajuster seulement les validateurs de précondition amont nécessaires pour reconnaître M-013 sans changer leur sens, enrôler les tests M-013 et obtenir un verdict GREEN ciblé sur la précondition.
- Invariants et garde-fous: aucun fallback de validation; aucune suppression de test amont; aucun statut GREEN sans preuve de commande; aucun écart V1 supprimé; aucune modification silencieuse des ADR acceptées.
- Dépendances: `master`; M-012; `docs/governance/m012_v1_gap_report.md`; `scripts/test.ps1`; `scripts/lint.ps1`; `scripts/validate_task_system.ps1`; ADR-010.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_m013_precondition_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_m013_precondition_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_precondition.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m013): couvrir precondition durcissement v1`
- Commit GREEN: `chore(m013): retablir precondition durcissement v1`
