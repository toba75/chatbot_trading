# Rapport T-010 - Benchmark stratégies et backtests pilotes

## Scénario BDD

- Given des stratégies candidates snapshotées et des expériences reproductibles M-011.
- When les backtests pilotes sont mesurés selon `StrategyExperimentBenchmarkPolicy-1.0`.
- Then les métriques SD, les métriques EX, limites, coûts, périodes, univers et résultats négatifs sont publiés sans promotion implicite de rentabilité.

## Portée

Le benchmark T-010 agrège uniquement des observations SD et EX déjà produites par les politiques de stratégie et d'expérimentation. Il ne lit pas le LLM, ne lit pas de donnée de marché courante et ne lance pas d'optimisation implicite.

## Métriques SD publiées

| Signal | Source | Invariant |
|---|---|---|
| `strategy_compilable_rate` | Politique SD | Les stratégies non compilables restent dans le dénominateur. |
| `strategy_rejection_reason_distribution` | Diagnostics SD | Chaque raison de rejet est conservée et agrégée. |
| `strategy_rule_origin_ratio` | Origines de règles SD | Les proportions d'origines sont calculées sans payload de preuve complet. |
| `strategy_parameter_without_calibration_plan_total` | Diagnostics SD | Les paramètres sans plan restent visibles. |
| `strategy_compatibility_conflict_total` | Compatibilité SD | Les conflits sont catégorisés. |
| `strategy_version_count` | Versions SD | Les versions invalides, rejetées ou supersédées restent comptées. |

## Métriques EX publiées

| Signal | Source | Invariant |
|---|---|---|
| `experiment_reproducible_rate` | Répétitions EX | Toutes les expériences mesurées restent dans le dénominateur. |
| `experiment_failure_rate_by_cause` | Résultats EX | Les échecs restent conservés par cause. |
| `negative_experiment_retention_ratio` | Rétention EX | Les résultats négatifs et échoués restent consultables. |
| `experiment_without_complete_cost_model_total` | Entrées figées EX | Les coûts incomplets restent visibles. |
| `coherent_repeat_count` | Comparaisons EX | Les répétitions cohérentes sont comptées sans mutation du résultat initial. |
| `invalidated_result_ratio` | Audit EX | Les résultats invalidés après audit restent dans le benchmark. |
| `backtest_assumption_count` | Protocole M-012 | Les hypothèses comparables sont explicites. |

## Garde-fous

- Aucun paramètre optimisé sans domaine, protocole de calibration et période hors échantillon.
- Aucun résultat comparable sans période, univers, coûts et hypothèses.
- Aucun résultat négatif ou échoué retiré du benchmark.
- Aucune métrique dérivée du LLM.
- Aucun verdict de rentabilité publié sans qualification explicite de mesure pilote descriptive.
- Aucune promesse de rentabilité.

## Validations

```console
uv run --locked gate
uv run --locked gate
uv run --locked gate
uv run --locked gate
```
