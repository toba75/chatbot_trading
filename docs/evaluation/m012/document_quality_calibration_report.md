# Rapport de calibration documentaire M-012

## Scénario BDD

- Given les routes documentaires ont été mesurées sur le corpus pilote M-012.
- When les seuils de conversion canonique sont calibrés par `DocumentQualityCalibrationPolicy`.
- Then chaque seuil SP publié référence son benchmark source, son corpus, sa version de politique et une justification par strate; toute route sous seuil reste refusée avec un écart V1 documentaire explicite.

## Politique appliquée

- Politique: `DocumentQualityCalibrationPolicy-1.0`.
- Source benchmark: `RouteBenchmarkResult` produit par T-005.
- Corpus: corpus pilote M-012 référencé par le `RouteBenchmarkRun`.
- ADR appliquées: ADR-002, ADR-004 et ADR-010.
- ADR nouvelle: non requise; T-006 applique le routage explicite, l'autorité textuelle unique par page et les gates PowerShell sans changer leur sens.

## Seuils SP calibrés

| Seuil | Métrique | Opérateur | Benchmark source | Corpus | Version de politique | Justification par strate |
|---|---|---|---|---|---|---|
| Qualité texte documentaire | `document_cer` | maximum | `RouteBenchmarkResult.result_id` | `RouteBenchmarkRun.corpus_id` | `DocumentQualityCalibrationPolicy-1.0` | Chaque strate mesurée doit rester sous le CER calibré; le seuil global ne peut pas masquer une strate critique. |
| Cellules financières | `document_cell_accuracy` | minimum | `RouteBenchmarkResult.result_id` | `RouteBenchmarkRun.corpus_id` | `DocumentQualityCalibrationPolicy-1.0` | Les strates de tableaux financiers doivent justifier séparément l'acceptation; une cellule insuffisante produit un écart V1. |
| Formules et équations | `document_formula_fidelity` | minimum | `RouteBenchmarkResult.result_id` | `RouteBenchmarkRun.corpus_id` | `DocumentQualityCalibrationPolicy-1.0` | Les strates d'équations gardent leur justification propre; aucune moyenne globale ne les efface. |

## Décision documentaire

`CalibrationDecision` ne promeut aucune valeur de développement. Une route est acceptée uniquement si tous les seuils explicitement versionnés de son `DocumentQualityThresholdReport` sont satisfaits pour chaque strate du `RouteBenchmarkResult` source.

Une métrique manquante, une strate sans justification ou une valeur sous seuil produit:

- un `DocumentRouteCalibrationDiagnostic` au statut `REJECTED`;
- un `DocumentV1Gap` au statut `BLOCKING`;
- le lien vers le seuil, le benchmark source, le corpus et la version de politique.

## Écarts V1 documentaires

Les écarts V1 documentaires restent append-only dans la décision de calibration. Ils ne modifient pas rétroactivement les benchmarks T-005 et ne remplacent pas une mesure scientifique RED par un succès logiciel.
