# M-011 - Expérience reproductible

## Statut

Cette spécification rend le bounded context EX exécutable pour transformer un `StrategySnapshot` immuable en expérience de backtest reproductible, sans validation scientifique M-012 et sans promesse de rentabilité.

## Scénario BDD

- Given la mission M-011 est de transformer une stratégie snapshotée en expérience auditable.
- When la spécification d'expérience reproductible est publiée.
- Then chaque comportement M-011 nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.

## Mission EX

EX planifie, verrouille, exécute et conserve les expériences quantitatives. EX consomme le `StrategySnapshot` publié par SD, produit un `ExperimentResult` publié vers RA et CV, et interdit toute lecture de stratégie mutable, de donnée courante ou de stockage interne.

## Contexte DDD

Le bounded context EX appartient au domaine d'expérimentation quantitative reproductible. SD fournit `StrategySnapshot`; RA et CV consomment les statuts et résultats publics. DDD-ADR-009 gouverne le snapshot immuable et DDD-ADR-010 gouverne la conservation append-only des versions et résultats défavorables.

## Langage ubiquitaire EX

`Experiment`, `ExperimentId`, `StrategySnapshotRef`, `DataSnapshotRef`, `CostModelSnapshot`, `ExecutionEnvironment`, `FrozenInputs`, `ExperimentRepository`, `ExperimentResultRepository`, `ExperimentArtifactStore`, `DeterministicBacktestEngineAdapter`, `RepeatExperiment`, `CompareExperiments`, `ExperimentComparisonCompleted`, `ExperimentScheduled`, `ExperimentCancelled`, `strategy_parameter_hash`, résultat négatif, résultat invalidé et correction par nouvelle expérience liée sont les termes normatifs M-011.

## Agrégat et objets-valeur EX

| Élément | Responsabilité M-011 | Invariants |
|---|---|---|
| Experiment | Agrégat propriétaire du cycle `PLANNED -> SCHEDULED -> RUNNING -> COMPLETED/FAILED/CANCELLED` | Identifiant stable, transitions explicites, événement par transition, aucun redémarrage d'un résultat terminé |
| DataSnapshotRef | Référence point-in-time des données | `data_snapshot_id`, période, univers, fréquence et hash obligatoires; aucune référence `/latest` |
| CostModelSnapshot | Coûts de transaction et hypothèses d'exécution | Hash obligatoire, commissions et slippage explicites, aucune valeur implicite |
| ExecutionEnvironment | Version de code, moteur et graine | Hash obligatoire, seed explicite, version moteur et code versionnés |
| FrozenInputs | Empreinte des entrées verrouillées | `strategy_snapshot_hash`, `strategy_parameter_hash`, `data_snapshot_hash`, `cost_model_hash`, `execution_environment_hash` et `frozen_at` obligatoires |

## Machine d'états M-011

| État | Sens | Transition autorisée |
|---|---|---|
| PLANNED | Expérience ouverte depuis un snapshot SD compilable | Attacher les données, les coûts et l'environnement |
| SCHEDULED | Entrées figées, exécution planifiée | `SCHEDULED -> RUNNING` ou `SCHEDULED -> CANCELLED` |
| RUNNING | Backtest déterministe en cours avec entrées verrouillées | `RUNNING -> COMPLETED` ou `RUNNING -> FAILED` |
| COMPLETED | Résultat publié et immuable | Reproduire, comparer, invalider par nouvelle expérience liée |
| FAILED | Échec conservé avec diagnostic | Reproduire interdit, correction par nouvelle expérience liée |
| CANCELLED | Annulation explicite avant exécution | Aucune relance sous le même `ExperimentId` |

## Ports et adaptateurs EX

| Port ou adaptateur | Responsabilité | Interdiction |
|---|---|---|
| StrategySnapshotReader | Lire le `StrategySnapshot` public SD | Lire `StrategyCandidate` courant |
| ExperimentRepository | Registre append-only des expériences | Supprimer ou réécrire une transition |
| ExperimentResultRepository | Registre append-only des `ExperimentResult` | Supprimer un résultat négatif ou échoué |
| ExperimentArtifactStore | Stocker artefacts hashés d'équity curve, positions, transactions, warnings et logs | Exposer un payload moteur brut |
| DeterministicBacktestEngineAdapter | Produire métriques et contrôles minimaux à partir des entrées figées | Utiliser `ExperimentId` comme facteur de performance |
| ExperimentHttpAdapter | Exposer `POST /v1/strategies/{id}/backtest` et `GET /v1/experiments/{id}` | Exposer `experiment_registry_table`, prompt, stockage interne ou donnée de marché complète |

## Événements EX

| Événement | Déclencheur | Payload publié |
|---|---|---|
| ExperimentPlanned | Planification depuis `StrategySnapshot` | Références SD, `spec_hash`, `strategy_parameter_hash` |
| ExperimentDataSnapshotFrozen | Attachement de `DataSnapshotRef` | Identifiant, période, univers, fréquence et hash |
| ExperimentInputsFrozen | Gel coûts et environnement | Hashs de coûts, environnement et entrées |
| ExperimentScheduled | Planification d'exécution | Transition `PLANNED -> SCHEDULED` |
| ExperimentCancelled | Annulation explicite | Transition `SCHEDULED -> CANCELLED` et raison |
| ExperimentStarted | Démarrage | Transition `SCHEDULED -> RUNNING` |
| ExperimentResultRecorded | Résultat terminal | `result_hash`, statut et artefacts hashés |
| ExperimentFailedResultRecorded | Échec terminal | `failure_reason` et conservation du résultat |
| ExperimentRepeated | Reproduction | Relation `REPEATS` et mêmes hash d'entrées |
| ExperimentComparisonCompleted | `CompareExperiments` | Comparaison des entrées, paramètres et métriques |

## API publique EX

| Endpoint | Succès | Erreurs publiques | Corps public |
|---|---|---|---|
| POST /v1/strategies/{id}/backtest | `202` avec `ExperimentId` et statut `SCHEDULED` | `HTTP_REQUEST_INVALID`, `STRATEGY_SNAPSHOT_NOT_FOUND`, `PUBLIC_STORAGE_FIELD_FORBIDDEN`, `STRATEGY_SNAPSHOT_MISMATCH` | Snapshot, données, coûts, environnement et dates explicites |
| GET /v1/experiments/{id} | `200` avec statut, diagnostics publics, entrées figées et résultat public si disponible | `EXPERIMENT_NOT_FOUND`, `PUBLIC_STORAGE_FIELD_FORBIDDEN`, `ENDPOINT_NOT_FOUND` | Aucun stockage interne, aucun prompt, aucun payload moteur brut |

### Champs publics interdits

`experiment_registry_table`, `raw_engine_payload`, `prompt`, `prompt_text`, `current_strategy_ref`, `latest_data_ref`, `market_data_payload` et `strategy_internal_payload` sont interdits dans les requêtes et réponses publiques.

## Métriques et traces

| Signal | Type | Invariant |
|---|---|---|
| experiment_reproducible_rate | Ratio | Répétitions cohérentes sur observations EX |
| experiment_failure_rate_by_cause | Distribution | Échecs conservés par cause explicite |
| negative_experiment_retention_ratio | Ratio | Résultats négatifs et échoués toujours consultables |
| experiment_without_complete_cost_model_total | Compteur | Expériences refusées ou signalées sans coûts complets |
| coherent_repeat_count | Compteur | Répétitions qui gardent les mêmes hash d'entrées |
| invalidated_result_ratio | Ratio | Résultats invalidés après audit et conservés |

Les métriques EX ne contiennent ni secret, ni prompt, ni donnée de marché complète, ni payload moteur brut.

## Comportements vérifiables M-011

| Comportement | Invariant | Scénario BDD | Test RED | ADR | Commande |
|---|---|---|---|---|---|
| EX-001 - Précondition GREEN | M-010 est visible dans `master` et les validateurs amont acceptent M-011 | Given M-010 fusionné, When la précondition M-011 est validée, Then les gates ont une preuve exploitable | T-001 | ADR-010 | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m011_precondition.ps1 |
| EX-002 - Spécification exécutable | Les termes EX sont publiés avant le code | Given la mission EX, When la spec est lue, Then les invariants et tests sont nommés | T-002 | ADR-010; DDD-ADR-009; DDD-ADR-010 | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m011_specification.ps1 |
| EX-003 - Planification depuis snapshot | `Experiment` ne lit jamais une stratégie mutable | Given un `StrategySnapshot`, When EX planifie, Then `PLANNED` est append-only | T-003 | DDD-ADR-009; DDD-ADR-010 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_experiment_planning_acceptance.ps1 |
| EX-004 - Données point-in-time | `DataSnapshotRef` refuse `/latest` | Given une expérience `PLANNED`, When les données sont attachées, Then le snapshot est figé | T-004 | DDD-ADR-009 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_data_snapshot_freeze_acceptance.ps1 |
| EX-005 - Coûts et environnement figés | Aucun coût ou environnement implicite | Given données figées, When coûts et environnement sont attachés, Then `FrozenInputs` est complet | T-005 | DDD-ADR-009 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_cost_environment_freeze_acceptance.ps1 |
| EX-006 - Démarrage verrouillé | `PLANNED -> SCHEDULED -> RUNNING` et `SCHEDULED -> CANCELLED` sont explicites | Given entrées verrouillées, When l'expérience démarre ou s'annule, Then chaque transition est événementée | T-006 | DDD-ADR-010 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_experiment_start_lock_acceptance.ps1 |
| EX-007 - Backtest déterministe | Les mêmes entrées produisent les mêmes métriques | Given `RUNNING`, When le moteur s'exécute deux fois, Then métriques et contrôles minimaux sont stables | T-007 | DDD-ADR-009 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_deterministic_backtest_acceptance.ps1 |
| EX-008 - Résultat immuable | `ExperimentResultRepository` est append-only | Given un résultat, When il est enregistré, Then sa réécriture est refusée | T-008 | DDD-ADR-010 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_experiment_result_acceptance.ps1 |
| EX-009 - Conservation négative | Les échecs et résultats défavorables restent consultables | Given un échec, When EX le conserve, Then la suppression est interdite | T-009 | DDD-ADR-010 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_experiment_retention_acceptance.ps1 |
| EX-010 - Répétition et comparaison | `RepeatExperiment` crée une nouvelle expérience et `CompareExperiments` ne mute rien | Given un résultat `COMPLETED`, When une répétition est demandée, Then `ExperimentComparisonCompleted` compare sans écraser | T-010 | DDD-ADR-009; DDD-ADR-010 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_experiment_reproducibility_acceptance.ps1 |
| EX-011 - Contrat HTTP | Les endpoints publics ne fuient aucun stockage interne | Given une requête publique, When EX répond, Then le statut et les erreurs sont stables | T-011 | ADR-010; DDD-ADR-001 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_experiment_http_contract_acceptance.ps1 |
| EX-012 - Traçabilité et métriques | Toutes les exigences, métriques et gates M-011 sont reliées | Given M-011 livré, When les gates tournent, Then la matrice couvre tests, code et métriques | T-012 | ADR-010; DDD-ADR-008 | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m011_traceability.ps1 |

## Commandes de validation

- powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_m011_precondition_acceptance.ps1
- powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_m011_specification_acceptance.ps1
- powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_experiment_planning_acceptance.ps1
- powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_data_snapshot_freeze_acceptance.ps1
- powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_cost_environment_freeze_acceptance.ps1
- powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_experiment_start_lock_acceptance.ps1
- powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_deterministic_backtest_acceptance.ps1
- powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_experiment_result_acceptance.ps1
- powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_experiment_retention_acceptance.ps1
- powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_experiment_reproducibility_acceptance.ps1
- powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_experiment_http_contract_acceptance.ps1
- powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_m011_traceability_acceptance.ps1
- powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m011_specification.ps1
- powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m011_traceability.ps1
- powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1
- powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1

## Exclusions M-011

M-011 ne livre pas la calibration scientifique M-012, ne conclut pas qu'une stratégie est rentable, ne lance aucune optimisation de paramètres, ne lit aucune donnée de marché courante et ne corrige jamais un résultat invalidé par réécriture du même `ExperimentId`.
