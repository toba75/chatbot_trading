# T-001 - Vérifier la précondition GREEN de gouvernance initiale

## Milestone
- Nom: M-000 - Gouvernance exécutable.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, section `M-000 - Gouvernance exécutable`, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 0, 3, 20, 21 et 22.
- Objectif métier: rendre l'implémentation contrôlable avant toute fonctionnalité métier, avec un état GREEN ou RED explicite.

## Contexte DDD
- Domaine: gouvernance d'implémentation et traçabilité transverse.
- Bounded context: transverse, tous les contextes, sans modèle métier applicatif à implémenter dans cette tâche.
- Objectif métier: empêcher qu'un développement démarre sans connaître l'état réel des artefacts de gouvernance.
- Langage ubiquitaire: précondition GREEN, registre ADR, commande de validation, matrice de traçabilité, milestone amont, gate.
- Invariants critiques: un état inconnu n'est jamais assimilé à GREEN; une absence de commande obligatoire est enregistrée comme RED ou comme travail M-000 explicite; aucun milestone aval n'est planifié si une dépendance amont manque dans `master`.
- Garde-fous: vérifier `master`, exécuter les validations existantes, consigner les commandes absentes et refuser les conclusions implicites.

## Blocages Ou Préconditions
- État GREEN/RED connu: `scripts/validate_adr_system.ps1` existe et a été observé GREEN; `scripts/test.ps1` et `scripts/lint.ps1` sont absents et doivent être créés par M-000.
- Présence des milestones amont dans master: M-000 n'a aucune dépendance amont; `git ls-tree -r --name-only master -- docs/tasks docs/adr docs/specs` montre les ADR et specs, mais aucun dossier `docs/tasks/milestone_000` versionné.
- Décisions manquantes: aucune nouvelle décision structurante n'est requise pour cette tâche; toute nouvelle règle de gouvernance structurante doit créer une ADR.
- Risques: confondre un registre ADR valide avec une suite projet complète; masquer l'absence de commandes génériques de test et de lint.

## Tâches
### T-001 - Vérifier la précondition GREEN de gouvernance initiale
- But métier: produire une preuve versionnée de l'état initial du dépôt avant l'exécution de M-000.
- Portée DDD: gouvernance transverse; aucune logique métier SP, KA, EG, RA, CV, SD ou EX.
- Scénario BDD:
  - Given le dépôt `master` contient la spécification v4.1 et le registre ADR.
  - When la précondition de M-000 est vérifiée.
  - Then l'état des validations existantes, des commandes absentes et des tâches versionnées est déclaré sans ambiguïté.
- Tests d'acceptation à écrire: un test automatisé de gouvernance qui échoue tant que le rapport de précondition M-000 ne mentionne pas la révision `master`, la commande ADR exécutée, le résultat GREEN/RED et les commandes de validation absentes.
- Tests unitaires à écrire: tests du parseur ou validateur de rapport pour refuser un champ vide, une valeur d'état inconnue ou une commande non datée.
- Implémentation attendue: créer un rapport de précondition M-000 dans la documentation de gouvernance et un validateur strict de sa structure; le rapport doit citer les commandes utilisées et leur résultat observé.
- Invariants et garde-fous: aucune mention `GREEN` ne peut être produite si une commande obligatoire échoue; une commande absente doit être nommée; aucune valeur par défaut ne remplace un résultat manquant.
- Dépendances: `AGENTS.md`; plan de milestones; spécification v4.1; `scripts/validate_adr_system.ps1`; `master` rafraîchi avec `git fetch origin --prune`.
- Commandes de validation: `git fetch origin --prune`; `git ls-tree -r --name-only master -- docs/tasks docs/adr docs/specs`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_adr_system.ps1`.
- Commit RED: `test(m000): décrire la précondition de gouvernance initiale`.
- Commit GREEN: `feat(m000): publier l'audit de précondition de gouvernance`.
