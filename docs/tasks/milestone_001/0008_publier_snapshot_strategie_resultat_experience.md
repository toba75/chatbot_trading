# T-008 - Publier StrategySnapshot et ExperimentResult

## Milestone
- Nom: M-001 - Frontières DDD et contrats publiés.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, livrables `StrategySnapshot` et `ExperimentResult`, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 4, 10, 11, 14, 20 et 21.
- Objectif métier: permettre à EX de recevoir une stratégie immuable et de retourner un résultat reproductible sans lire l'état mutable de SD.

## Contexte DDD
- Domaine: conception de stratégies et expérimentation reproductible.
- Bounded context: SD producteur de `StrategySnapshot`; EX consommateur et producteur de `ExperimentResult`; RA et CV consommateurs de résultats.
- Objectif métier: figer règles, paramètres, contraintes, preuves et entrées d'expérience pour préserver la reproductibilité.
- Langage ubiquitaire: stratégie candidate, snapshot de stratégie, stratégie compilable, entrée figée, résultat d'expérience, métriques, diagnostics, artefacts.
- Invariants critiques: EX ne lit jamais une stratégie mutable; un snapshot est complet et hashé; un résultat est rattaché à des entrées immuables; les résultats échoués restent consultables.
- Garde-fous: ne pas déclarer une stratégie rentable; ne pas recalculer silencieusement un résultat; ne pas omettre les diagnostics d'échec.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-001 doit être GREEN; T-004 fournit les identifiants communs.
- Présence des milestones amont dans master: M-000 est présent dans `master`.
- Décisions manquantes: aucune ADR nouvelle si DDD-ADR-009 est appliquée sans modification de sens.
- Risques: transmettre une référence mutable de stratégie; confondre résultat expérimental et preuve de rentabilité; perdre le hash de spécification.

## Tâches
### T-008 - Publier StrategySnapshot et ExperimentResult
- But métier: publier le langage immuable entre conception de stratégie et expérimentation.
- Portée DDD: contrats `StrategySnapshot` et `ExperimentResult`, fixtures SD vers EX, EX vers RA et EX vers CV, statut, hash, données figées et diagnostics.
- Scénario BDD:
  - Given SD a produit un snapshot complet et hashé.
  - When EX planifie une expérience.
  - Then EX utilise uniquement le snapshot immuable et retourne un `ExperimentResult` rattaché aux entrées figées.
- Tests d'acceptation à écrire: un test de contrat SD vers EX qui refuse une stratégie sans hash, avec paramètre bloquant non résolu ou référence mutable, puis valide un résultat d'expérience complet.
- Tests unitaires à écrire: tests d'immuabilité de snapshot, hash obligatoire, statut autorisé, rattachement `strategy_version_id`, `data_snapshot_id`, diagnostics et artefacts.
- Implémentation attendue: créer les contrats, fixtures et validateurs stricts pour snapshots et résultats; ne pas implémenter de moteur de backtest.
- Invariants et garde-fous: aucune entrée mutable; aucun statut par défaut; aucun résultat supprimé; aucun accès EX au modèle interne SD.
- Dépendances: T-004; DDD-ADR-009; sections 10 et 11 de la spécification v4.1.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m001\validate_strategy_experiment_contracts_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m001\validate_strategy_experiment_contracts_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`.
- Commit RED: `test(m001): couvrir snapshot strategie et resultat experience`.
- Commit GREEN: `feat(m001): publier les contrats strategie experience`.
