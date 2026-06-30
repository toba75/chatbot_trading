# T-001 - Vérifier et rétablir la précondition GREEN M-007

## Milestone
- Nom: M-007 - Réponse documentaire vérifiée.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, section `M-007 - Réponse documentaire vérifiée`, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 8, 12, 16, 17, 19, 20 et 21.
- Objectif métier: démarrer la réponse documentaire RA uniquement depuis un registre EG de claims vérifiables déjà livré, avec des gates concluantes et des contrats publiés stables.

## Contexte DDD
- Domaine: recherche et réponse vérifiée.
- Bounded context: RA, avec EG comme fournisseur de claims vérifiés et KA comme fournisseur de preuves candidates.
- Objectif métier: prouver que M-007 peut produire une réponse citée, qualifiée ou abstinente sans masquer un défaut de preuve.
- Langage ubiquitaire: précondition GREEN, `ResearchCase`, `Answer`, `ResearchMandate`, `VerifiedClaimRef`, `VerifiedResearchOutcome`, jeu de preuves, `master`, gate.
- Invariants critiques: M-006 doit être visible dans `master`; une réponse ne peut pas être `SUPPORTED` si une assertion importante reste non supportée; aucune gate RED existante ne doit être masquée.
- Garde-fous: ne pas accepter une branche locale comme preuve de M-006; ne pas ignorer un timeout; ne pas commencer RA si EG n'expose pas les claims vérifiables attendus.

## Blocages Ou Préconditions
- État GREEN/RED connu: `scripts/test.ps1` a expiré une première fois à 904 secondes puis a conclu GREEN après relance large avec `15 validation(s), 134 test(s)`; `scripts/lint.ps1` GREEN avec `15 validation(s), 0 test(s)`; `scripts/validate_task_system.ps1` GREEN avec `7 milestone(s), 67 tâche(s) contrôlée(s)`; `git diff --check` GREEN.
- Présence des milestones amont dans master: M-006 requis et présent dans `master` au commit `236c2420a84c0439e8d1c101eb2251ba44069fa9`, identique à `origin/master` après `git fetch origin --prune`.
- Décisions manquantes: aucune pour la précondition; ADR requise seulement si la politique durable des gates ou des contrats RA publiés change.
- Risques: démarrer RA avec un registre EG absent; traiter une réponse plausible comme vérifiée; publier une précondition GREEN sans preuve de commande concluante.

## Tâches
### T-001 - Vérifier et rétablir la précondition GREEN M-007
- But métier: prouver que M-007 commence depuis les claims vérifiables M-006 fusionnés, avec une base de validation explicite.
- Portée DDD: gouvernance de précondition M-007, présence de M-006 dans `master`, rapport de précondition et contrôle des gates existantes.
- Scénario BDD:
  - Given M-006 est présent dans `master`.
  - When les gates de précondition M-007 sont exécutées.
  - Then M-007 ne peut commencer que si les validations, la traçabilité, les ADR, les frontières d'architecture et les preuves M-006 sont GREEN ou si le blocage exact est isolé.
- Tests d'acceptation à écrire: `tests/m007/validate_m007_precondition_acceptance.ps1`, qui échoue tant que le validateur M-007, le rapport de précondition et la présence M-006 dans `master` ne sont pas vérifiés.
- Tests unitaires à écrire: tests du validateur pour M-006 absent de `master`, `origin/master` divergent, `scripts/test.ps1` non concluant, gate RED, rapport hors dépôt et statut GREEN déclaré sans sortie de commande.
- Implémentation attendue: créer `scripts/validate_m007_precondition.ps1`, produire `docs/governance/m007_precondition_green.md`, enrôler la précondition dans les gates si nécessaire, puis obtenir `scripts/test.ps1` et `scripts/lint.ps1` GREEN.
- Invariants et garde-fous: aucun contournement de gate; aucun statut GREEN sans preuve de commande; aucun fallback silencieux en cas de timeout; aucune dépendance à une branche M-006 non fusionnée.
- Dépendances: `master`; `origin/master`; `docs/tasks/milestone_006`; `docs/specs/m006_claims_verifiables.md`; `scripts/test.ps1`; `scripts/lint.ps1`.
- Commandes de validation: `git fetch origin --prune`; `git ls-tree -r --name-only master -- docs/tasks/milestone_006 docs/specs/m006_claims_verifiables.md scripts tests/m006`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m007\validate_m007_precondition_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m007): couvrir la precondition green reponse documentaire`
- Commit GREEN: `test(m007): etablir la precondition green reponse documentaire`

