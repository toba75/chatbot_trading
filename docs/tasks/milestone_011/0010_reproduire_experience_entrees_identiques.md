# T-010 - Reproduire une expérience avec les mêmes entrées

## Milestone
- Nom: M-011 - Expérience reproductible.
- Source: M-011, invariants de reproduction depuis `spec_hash`, snapshot de données, paramètres, modèle de coûts et version de code.
- Objectif métier: permettre une répétition auditable et une comparaison EX autonome sans relancer une expérience sous le même identifiant.

## Contexte DDD
- Domaine: expérimentation quantitative reproductible.
- Bounded context: EX.
- Objectif métier: créer une nouvelle expérience liée à l'expérience d'origine pour vérifier la cohérence d'une reproduction, puis permettre la comparaison explicite de deux expériences existantes.
- Langage ubiquitaire: répétition, relation `REPEATS`, cohérence de reproduction, `CompareExperiments`, `ExperimentComparisonCompleted`, entrées identiques, paramètres de stratégie, résultat comparé, divulgation de tests multiples.
- Invariants critiques: une expérience terminée n'est jamais relancée sous le même identifiant; une répétition crée une nouvelle expérience; les entrées de reproduction doivent correspondre aux hash d'origine, y compris les paramètres du `StrategySnapshot`; les comparaisons ne sont valides que si les protocoles sont comparables; `CompareExperiments` ne modifie aucune expérience ni aucun résultat.
- Garde-fous: pas de réutilisation d'`ExperimentId`; pas de comparaison entre protocoles incompatibles; pas de modification de paramètre classée comme répétition; pas d'optimisation déguisée en répétition; pas de nouveau résultat écrasant l'ancien; pas de comparaison implicite sans commande EX.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-009.
- Présence des milestones amont dans master: M-010 présent dans `master`.
- Décisions manquantes: aucune si la comparaison reste descriptive et ne livre pas la calibration M-012.
- Risques: traiter une reproduction divergente comme succès; masquer une modification de coût, de données ou de paramètre; compter une optimisation comme répétition; oublier le contrat `CompareExperiments` prévu par EX.

## Tâches
### T-010 - Reproduire une expérience avec les mêmes entrées
- But métier: rendre la reproductibilité vérifiable par nouvelle expérience liée et par comparaison EX explicite.
- Portée DDD: commande `RepeatExperiment`, commande/query `CompareExperiments`, relation `REPEATS`, politique `ExperimentComparisonPolicy`, politique `MultipleTestingDisclosurePolicy`, comparaison de hash d'entrées, empreinte des paramètres du `StrategySnapshot`, événements `ExperimentRepeated` et `ExperimentComparisonCompleted`, résultat de comparaison et consultation des expériences comparées.
- Scénario BDD:
  - Given une expérience `COMPLETED` possède `spec_hash`, `strategy_parameter_hash`, `data_snapshot_hash`, `cost_model_hash`, `execution_environment_hash` et version de code.
  - When une répétition est demandée avec les mêmes entrées figées.
  - Then EX crée une nouvelle expérience liée par `REPEATS`, conserve les deux résultats et signale toute divergence de métriques ou de hash.
- Tests d'acceptation à écrire: `tests/m011/validate_experiment_reproducibility_acceptance.ps1`, qui échoue tant qu'une répétition peut réutiliser le même `ExperimentId`, changer une entrée ou un paramètre sans diagnostic, écraser le résultat initial, comparer deux expériences non comparables, ou tant que `CompareExperiments` ne produit pas de résultat explicite sans mutation.
- Tests unitaires à écrire: tests de `RepeatExperimentHandler`, `CompareExperimentsHandler`, `ExperimentComparisonPolicy`, `MultipleTestingDisclosurePolicy`, relation `REPEATS`, `ExperimentComparisonCompleted`, comparaison de hash, empreinte des paramètres, divergence de métriques, protocole incompatible, absence de mutation par comparaison et conservation des deux résultats.
- Implémentation attendue: créer la commande de répétition, dupliquer seulement les références figées autorisées dans une nouvelle expérience, publier la relation `REPEATS`, créer `CompareExperiments`, comparer les entrées, les paramètres et les résultats, publier `ExperimentComparisonCompleted`, puis signaler les divergences sans supprimer ni corriger l'original.
- Invariants et garde-fous: aucune relance sous le même identifiant; aucune entrée ou paramètre changé sans diagnostic; aucune comparaison sans protocole comparable; aucune comparaison qui mute un résultat ou une expérience; aucune conclusion d'optimisation; aucune suppression du résultat d'origine.
- Dépendances: T-009; DDD-ADR-009; DDD-ADR-010.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_experiment_reproducibility_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_experiment_reproducibility_unit.ps1`; `python -m compileall app\experimentation`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m011): couvrir repetition experience reproductible`
- Commit GREEN: `feat(m011): reproduire experience entrees identiques`
