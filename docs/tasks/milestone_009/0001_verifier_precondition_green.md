# T-001 - Vérifier la précondition GREEN M-009

## Milestone
- Nom: M-009 - Recherche approfondie multi-sources.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, section `M-009 - Recherche approfondie multi-sources`, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 7, 8, 12, 17, 19, 20 et 21.
- Objectif métier: démarrer la recherche approfondie uniquement depuis M-008 fusionné, avec une base de validation GREEN et traçable.

## Contexte DDD
- Domaine: recherche et réponse vérifiée approfondie.
- Bounded context: RA, avec EG comme fournisseur de claims vérifiés et CV comme déclencheur conversationnel.
- Objectif métier: prouver que M-009 commence après la conversation produit livrée, sans masquer un RED existant.
- Langage ubiquitaire: précondition GREEN, recherche approfondie, `ResearchCase`, `ResearchPlan`, obligations de couverture, `master`, gate.
- Invariants critiques: M-008 doit être visible dans `master`; la branche M-009 doit contenir `master`; aucune gate RED existante ne doit être ignorée.
- Garde-fous: ne pas accepter une branche M-008 non fusionnée comme preuve; ne pas créer de plan de contournement; ne pas déclarer GREEN si `scripts/test.ps1` reste RED.

## Blocages Ou Préconditions
- État GREEN/RED connu: après fusion PR #9, `scripts/test.ps1` est GREEN avec 17 validation(s), 176 test(s), et `scripts/lint.ps1` est GREEN avec 17 validation(s), 0 test(s).
- Présence des milestones amont dans master: M-008 requis et présent dans `master` au commit `2adca74e467a4bb5173247aec55a25168be65101`.
- Décisions manquantes: aucune si la tâche formalise seulement la précondition M-009; ADR requise si la politique de validation des prérequis change de sens.
- Risques: planifier M-009 depuis une branche M-008 non fusionnée; traiter un timeout de gate comme GREEN; ignorer les validateurs de tâches aval.

## Tâches
### T-001 - Vérifier la précondition GREEN M-009
- But métier: établir une base GREEN vérifiable avant toute capacité RA approfondie.
- Portée DDD: gouvernance de précondition M-009, présence de M-008 dans `master`, rapport de précondition et preuve de gates existantes.
- Scénario BDD:
  - Given M-008 est présent dans `master`.
  - When les gates de précondition M-009 sont exécutées sur une branche M-009.
  - Then M-009 ne peut commencer que si les validations existantes restent GREEN et si les artefacts M-008 sont visibles depuis `master`.
- Tests d'acceptation à écrire: `tests/m009/validate_m009_precondition_acceptance.ps1`, qui échoue tant que le rapport de précondition M-009 et la preuve de M-008 dans `master` n'existent pas.
- Tests unitaires à écrire: tests de `scripts/validate_m009_precondition.ps1` pour M-008 absent de `master`, branche ne contenant pas `master`, `origin/master` divergent, gate RED, timeout non concluant et rapport GREEN sans commandes.
- Implémentation attendue: créer `scripts/validate_m009_precondition.ps1`, créer `docs/governance/m009_precondition_green.md`, enrôler les tests M-009 dans les gates et obtenir `scripts/test.ps1` et `scripts/lint.ps1` GREEN.
- Invariants et garde-fous: aucune acceptation implicite de branche; aucune suppression de test amont; aucune preuve GREEN sans sortie de commande; aucun fallback silencieux en cas de validation absente.
- Dépendances: `master`; `origin/master`; `docs/tasks/milestone_008`; `docs/specs/m008_conversation_produit.md`; `scripts/test.ps1`; `scripts/lint.ps1`.
- Commandes de validation: `git fetch origin --prune`; `git ls-tree -r --name-only master -- docs/tasks/milestone_008 docs/specs/m008_conversation_produit.md scripts tests/m008`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_m009_precondition_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m009): couvrir la precondition green recherche approfondie`
- Commit GREEN: `test(m009): retablir la precondition green recherche approfondie`

