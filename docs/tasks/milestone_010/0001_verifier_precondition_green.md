# T-001 - Vérifier et rétablir la précondition GREEN M-010

## Milestone
- Nom: M-010 - Stratégie candidate attribuée.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, section `M-010 - Stratégie candidate attribuée`, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 10, 12, 17, 18, 19, 20 et 21.
- Objectif métier: démarrer la conception de stratégie uniquement depuis M-009 fusionné, avec un socle RA/EG capable de fournir des résultats vérifiés et sans masquer un état RED existant.

## Contexte DDD
- Domaine: conception de stratégies candidates attribuées.
- Bounded context: SD, avec RA et EG comme fournisseurs de résultats et claims vérifiés, et EX comme consommateur futur de snapshots.
- Objectif métier: prouver que M-010 commence depuis une recherche approfondie M-009 livrée, capable de transmettre un `VerifiedResearchOutcome` traduisible en langage SD.
- Langage ubiquitaire: précondition GREEN, `StrategyCandidate`, résultat de recherche vérifié, règle de stratégie, origine de règle, diagnostic bloquant, `master`, gate.
- Invariants critiques: M-009 doit être visible dans `master`; la branche M-010 doit contenir `master`; aucune gate RED existante ne doit être ignorée; un test global sans verdict exploitable ne vaut pas GREEN.
- Garde-fous: ne pas accepter une branche M-009 locale comme preuve de fusion; ne pas créer un validateur qui contourne les milestones amont; ne pas déclarer M-010 prêt tant que les commandes ciblées et globales n'ont pas un verdict exploitable.

## Blocages Ou Préconditions
- État GREEN/RED connu: après `git fetch origin --prune` puis `git fetch origin master:master`, `master` et `origin/master` pointent sur `ef419b4c068e958d328262cdf7c5d0f84b9adb92`; avant création de M-010, `scripts/validate_task_system.ps1` est GREEN avec `10 milestone(s), 99 tâche(s) contrôlée(s)` et `scripts/lint.ps1` est GREEN avec `18 validation(s), 0 test(s)`; après création des tâches M-010, `scripts/validate_task_system.ps1` est GREEN avec `11 milestone(s), 110 tâche(s) contrôlée(s)` et `scripts/test.ps1` est RED sur `tests/m003/validate_m003_precondition_acceptance.ps1`, car `scripts/validate_m003_precondition.ps1` refuse la branche `codex/milestone-m010-strategie-candidate-attribuee`.
- Présence des milestones amont dans master: M-009 requis et présent dans `master`, avec `60` entrées observées couvrant `docs/tasks/milestone_009`, `docs/specs/m009_recherche_approfondie_multi_sources.md`, `scripts/validate_m009_specification.ps1`, `tests/m009`, `app/research_answering` et l'adaptateur SD de traduction RA.
- Décisions manquantes: aucune pour appliquer DDD-ADR-009; ADR requise seulement si M-010 change le sens des snapshots immuables, du langage publié SD -> EX ou de la conservation des versions négatives.
- Risques: démarrer M-010 avant d'élargir explicitement les validateurs de précondition amont à la branche M-010; confondre synthèse RA et règle SD; introduire une persistance ou un backtest avant le contrat de domaine.

## Tâches
### T-001 - Vérifier et rétablir la précondition GREEN M-010
- But métier: établir une base GREEN vérifiable avant tout comportement de conception de stratégie.
- Portée DDD: gouvernance de précondition M-010, présence de M-009 dans `master`, branche de travail contenant `master`, rapport de précondition, commandes de validation et absence de contournement des gates amont.
- Scénario BDD:
  - Given M-009 est présent dans `master` avec sa spécification, ses tests, ses tâches et son langage RA vers SD.
  - When les gates de précondition M-010 sont exécutées sur une branche M-010.
  - Then M-010 ne peut commencer que si les validateurs amont acceptent explicitement le jalon aval et si `test`, `lint`, traçabilité, ADR et frontières d'architecture ont un verdict GREEN exploitable.
- Tests d'acceptation à écrire: `tests/m010/validate_m010_precondition_acceptance.ps1`, qui échoue tant que M-009 n'est pas visible dans `master`, que le rapport de précondition M-010 n'existe pas, qu'un gate requis n'a pas de verdict GREEN exploitable ou qu'un validateur amont refuse la branche M-010.
- Tests unitaires à écrire: tests de `scripts/validate_m010_precondition.ps1` pour M-009 absent de `master`, branche ne contenant pas `master`, divergence `origin/master`, test global timeout non qualifié, gate RED, rapport GREEN sans sorties de commande, `validate_m003_precondition.ps1` refusant la branche M-010 et validateur amont qui ignore M-010.
- Implémentation attendue: créer `scripts/validate_m010_precondition.ps1`, créer `docs/governance/m010_precondition_green.md`, ajuster seulement les validateurs de précondition amont nécessaires pour reconnaître M-010 sans changer leur sens, enrôler les tests M-010 et obtenir un verdict GREEN sur les commandes ciblées et globales.
- Invariants et garde-fous: aucun fallback de validation; aucune suppression de test amont; aucun statut GREEN sans preuve de commande; aucun délai dépassé traité comme succès.
- Dépendances: `master`; `origin/master`; `docs/tasks/milestone_009`; `docs/specs/m009_recherche_approfondie_multi_sources.md`; `scripts/test.ps1`; `scripts/lint.ps1`; `scripts/validate_task_system.ps1`.
- Commandes de validation: `git fetch origin --prune`; `git ls-tree -r --name-only master -- docs/tasks/milestone_009 docs/specs/m009_recherche_approfondie_multi_sources.md scripts/validate_m009_specification.ps1 tests/m009`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m010\validate_m010_precondition_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m010): couvrir la precondition green strategie candidate`
- Commit GREEN: `test(m010): retablir la precondition green strategie candidate`
