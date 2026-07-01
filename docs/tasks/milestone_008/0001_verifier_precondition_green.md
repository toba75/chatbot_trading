# T-001 - Vérifier et rétablir la précondition GREEN M-008

## Milestone
- Nom: M-008 - Conversation produit.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, section `M-008 - Conversation produit`, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 9, 12, 17, 18, 19, 20 et 21.
- Objectif métier: démarrer la conversation produit uniquement depuis M-007 fusionné, avec une base de validation qui accepte explicitement le jalon aval M-008.

## Contexte DDD
- Domaine: conversation produit fondée sur preuves.
- Bounded context: CV, avec RA comme fournisseur de réponses vérifiées.
- Objectif métier: prouver que M-008 commence depuis une réponse documentaire vérifiée déjà livrée, sans masquer un RED de gouvernance.
- Langage ubiquitaire: précondition GREEN, `Conversation`, `ConversationTurn`, `ConversationContextSnapshot`, question résolue, mode conversationnel, `VerifiedResearchOutcome`, `master`, gate.
- Invariants critiques: M-007 doit être visible dans `master`; la branche de travail M-008 doit contenir `master`; aucune gate RED existante ne doit être ignorée; les préconditions amont ne doivent pas être réécrites pour changer leur sens.
- Garde-fous: ne pas accepter une branche locale M-007 comme preuve de M-007 fusionné; ne pas contourner les validateurs de précondition historiques; ne pas déclarer GREEN si `scripts/test.ps1` reste RED.

## Blocages Ou Préconditions
- État GREEN/RED connu: avant création de M-008, `scripts/test.ps1` est RED sur `tests/m003/validate_m003_precondition_acceptance.ps1`, car `scripts/validate_m003_precondition.ps1` refuse la branche `codex/plan-milestone-m008-conversation-produit`; `scripts/lint.ps1` est GREEN avec `16 validation(s), 0 test(s)`; `scripts/validate_task_system.ps1` est GREEN avec `8 milestone(s), 77 tâche(s) contrôlée(s)`; `git diff --check` est GREEN.
- Présence des milestones amont dans master: M-007 requis et présent dans `master` au commit `e211a7ea27050a1226203cec2529c217f9f7cfc4`, après `git fetch origin --prune` puis `git fetch origin master:master`.
- Décisions manquantes: aucune si la correction formalise seulement l'autorisation explicite de M-008 par les validateurs de précondition; ADR requise si la politique durable de validation des branches ou des préconditions est remplacée.
- Risques: ajouter M-008 sans branche contenant `master`; corriger seulement M-003 et laisser M-004 à M-007 incohérents; traiter un RED de gouvernance comme un bruit de planification.

## Tâches
### T-001 - Rétablir la précondition GREEN M-008
- But métier: établir une base GREEN vérifiable avant toute fonctionnalité CV.
- Portée DDD: gouvernance de précondition M-008, présence de M-007 dans `master`, branche de travail contenant `master`, rapport de précondition et remise au vert des gates existantes.
- Scénario BDD:
  - Given M-007 est présent dans `master`.
  - When les gates de précondition M-008 sont exécutées sur une branche M-008.
  - Then M-008 ne peut commencer que si les validateurs amont acceptent explicitement la branche aval et si `test`, `lint`, traçabilité, ADR et frontières d'architecture sont GREEN.
- Tests d'acceptation à écrire: `tests/m008/validate_m008_precondition_acceptance.ps1`, qui échoue tant que la branche M-008 n'est pas acceptée, que M-007 n'est pas visible dans `master` et que le rapport de précondition M-008 n'existe pas.
- Tests unitaires à écrire: tests de `scripts/validate_m008_precondition.ps1` pour M-007 absent de `master`, branche ne contenant pas `master`, `origin/master` divergent, validateur amont rejetant M-008, gate RED, timeout non concluant et rapport GREEN sans sorties de commande.
- Implémentation attendue: créer `scripts/validate_m008_precondition.ps1`, créer `docs/governance/m008_precondition_green.md`, corriger les listes ou règles de branches des validateurs de précondition amont sans changer leur sens, enrôler les tests M-008 et obtenir `scripts/test.ps1` et `scripts/lint.ps1` GREEN.
- Invariants et garde-fous: aucun contournement de gate; aucune suppression de test amont; aucune acceptation implicite de branche; aucun statut GREEN sans preuve de commande.
- Dépendances: `master`; `origin/master`; `docs/tasks/milestone_007`; `docs/specs/m007_reponse_documentaire_verifiee.md`; `scripts/test.ps1`; `scripts/lint.ps1`; `scripts/validate_task_system.ps1`.
- Commandes de validation: `git fetch origin --prune`; `git ls-tree -r --name-only master -- docs/tasks/milestone_007 docs/specs/m007_reponse_documentaire_verifiee.md scripts tests/m007`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m008\validate_m008_precondition_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m008): couvrir la precondition green conversation`
- Commit GREEN: `test(m008): retablir la precondition green conversation`
