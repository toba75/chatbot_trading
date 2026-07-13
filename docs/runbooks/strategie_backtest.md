# Runbook stratégie et backtest V1 M-013

## Statut

- Identifiant: `M013-Runbook-StrategyBacktest-1.0`
- Contextes: SD, EX, RA, EG et EV.
- Sources: `docs/specs/m010_strategie_candidate_attribuee.md`, `docs/specs/m011_experience_reproductible.md`, `docs/evaluation/m012/strategy_backtest_benchmark_report.md` et `docs/governance/m013_v1_gap_decisions.md`
- ADR applicables: ADR-010, DDD-ADR-009, DDD-ADR-010
- ADR: non requise; ce runbook publie les limites utilisateur V1 sans nouvelle politique de stratégie.

## Scénario BDD

- Given une stratégie candidate est attribuée et un backtest pilote est reproductible.
- When l'utilisateur consulte stratégie, expérience et benchmark.
- Then règles, origines, paramètres, coûts, hypothèses, résultats négatifs et écarts SD/EX restent visibles sans promesse financière.

## Procédure

- Précondition: la stratégie candidate possède des origines de règles et un snapshot immuable; aucun paramètre inventé ou optimisé silencieusement n'est accepté.
- Commande vérifiée:

```console
uv run --locked gate
uv run --locked gate
uv run --locked gate
```

- Résultat attendu: les contrats stratégie, expérience reproductible et benchmark pilote restent conformes; SD reste visible tant que l'écart est bloquant.
- Erreur explicite: paramètre sans plan de calibration, coût incomplet, période manquante, résultat non reproductible ou écart SD bloquant interdit le verdict V1.
- Preuve à conserver: sortie des validateurs, StrategySnapshotId, ExperimentId, hypothèses, coûts et statut d'écart.

## Métriques SD et EX visibles

| Famille | Métriques utilisateur |
|---|---|
| SD | `strategy_compilable_rate`, `strategy_rejection_reason_distribution`, `strategy_rule_origin_ratio`, `strategy_parameter_without_calibration_plan_total`, `strategy_compatibility_conflict_total`, `strategy_version_count` |
| EX | `experiment_reproducible_rate`, `experiment_failure_rate_by_cause`, `negative_experiment_retention_ratio`, `experiment_without_complete_cost_model_total`, `coherent_repeat_count`, `invalidated_result_ratio`, `backtest_assumption_count` |

## Limites V1

| Contexte | Statut |
|---|---|
| SD | bloquant |
| EX | satisfait |

## Garde-fous

- Aucune promesse financière.
- Aucun conseil d'investissement.
- Aucun résultat négatif retiré.
- Aucun paramètre sans plan de calibration.
- Fallback silencieux: interdit.
- Les mesures de backtest restent descriptives et reproductibles, sans garantie de rendement futur.
