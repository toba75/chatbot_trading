# T-005 - Contrôler les paramètres à calibrer

## Milestone
- Nom: M-010 - Stratégie candidate attribuée.
- Source: M-010, entité `StrategyParameter`, origine `PARAMETER_TO_CALIBRATE` et politique `ParameterCalibrationPolicy`.
- Objectif métier: refuser les paramètres inventés ou laissés ambigus avant compilation.

## Contexte DDD
- Domaine: conception de stratégies candidates attribuées.
- Bounded context: SD.
- Objectif métier: expliciter la valeur, le domaine ou le protocole de calibration de chaque paramètre qui influence la stratégie.
- Langage ubiquitaire: paramètre de stratégie, domaine de calibration, protocole anti-surajustement, sensibilité attendue, statut bloquant, résolution.
- Invariants critiques: un paramètre possède une valeur, un domaine ou une raison explicite d'être non résolu; `PARAMETER_TO_CALIBRATE` exige un domaine et un protocole; un paramètre bloquant non résolu interdit la compilation.
- Garde-fous: aucune valeur par défaut; aucune plage implicite; aucune calibration sans protocole anti-surajustement; aucun paramètre non résolu présenté comme choix validé.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-004.
- Présence des milestones amont dans master: M-009 présent dans `master`.
- Décisions manquantes: aucune si la calibration reste un contrat SD et que l'exécution expérimentale reste en M-011.
- Risques: inventer un lookback, un seuil ou une fenêtre de volatilité; confondre domaine de recherche et résultat calibré; lancer un backtest avant snapshot.

## Tâches
### T-005 - Contrôler les paramètres à calibrer
- But métier: rendre explicite tout paramètre qui doit être calibré et bloquer la stratégie tant que son protocole manque.
- Portée DDD: entité `StrategyParameter`, objet-valeur `ParameterDomain`, `ValidationPlan`, politique `ParameterCalibrationPolicy`, commande `DefineCalibrationPlan` et événement `CalibrationPlanDefined`.
- Scénario BDD:
  - Given un lookback est déclaré `PARAMETER_TO_CALIBRATE`.
  - When aucun domaine ni protocole de calibration n'est fourni.
  - Then la compilation est refusée avec un diagnostic bloquant sur le paramètre.
- Tests d'acceptation à écrire: `tests/m010/validate_strategy_parameter_calibration_acceptance.ps1`, qui échoue tant qu'un paramètre à calibrer peut être compilé sans domaine et protocole.
- Tests unitaires à écrire: tests de `StrategyParameter` et `ParameterCalibrationPolicy` pour valeur fixe valide, domaine vide, protocole absent, sensibilité absente, statut bloquant non résolu, paramètre non bloquant justifié et normalisation de l'unité.
- Implémentation attendue: créer le modèle de paramètre SD, les politiques de calibration, la commande de définition de plan et l'intégration des diagnostics dans `StrategyCandidate`.
- Invariants et garde-fous: aucune valeur par défaut; aucun domaine ouvert sans justification; aucun protocole vide; aucune mutation silencieuse d'un paramètre bloquant en non bloquant.
- Dépendances: T-004; DDD-ADR-010; contrats `StrategySnapshot` existants.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m010\validate_strategy_parameter_calibration_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m010\validate_strategy_parameter_calibration_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m010): couvrir parametres calibration strategie`
- Commit GREEN: `feat(m010): controler parametres calibration strategie`
