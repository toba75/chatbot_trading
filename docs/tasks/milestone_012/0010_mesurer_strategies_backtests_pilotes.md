# T-010 - Mesurer les stratégies et backtests pilotes

## Milestone
- Nom: M-012 - Évaluation pilote et calibration.
- Source: M-012, livrable `benchmark backtests`, et sections SD/EX de la spécification v4.1.
- Objectif métier: mesurer si les stratégies candidates et expériences reproductibles produisent des résultats auditables sans prétendre prouver une rentabilité générale.

## Contexte DDD
- Domaine: évaluation scientifique et calibration des seuils.
- Bounded context: SD et EX évalués par M-012.
- Objectif métier: benchmarker les stratégies et backtests pilotes avec paramètres cadrés, entrées figées, métriques SD explicites, métriques EX calculées par code déterministe et résultats négatifs conservés.
- Langage ubiquitaire: stratégie candidate, règle déterministe, origine de règle, paramètre à calibrer, snapshot de stratégie, expérience, résultat d'expérience, métrique de backtest, hors échantillon, résultat négatif, taux de stratégies compilables, raison de rejet, conflit de compatibilité.
- Invariants critiques: un paramètre à calibrer garde domaine et protocole; une expérience ne démarre pas sans entrées figées; les métriques viennent du moteur ou des politiques SD, jamais du LLM; un résultat négatif ou échoué reste dans le benchmark; le LLM n'interprète pas une stratégie comme rentable; une stratégie non compilable reste comptée avec sa raison de rejet.
- Garde-fous: aucune optimisation implicite de paramètres; aucune lecture de données de marché courante; aucun résultat défavorable retiré; aucune comparaison sans période, univers, coûts et hypothèses.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-009.
- Présence des milestones amont dans master: M-011 présent dans `master`.
- Décisions manquantes: ADR requise si le moteur de backtest ou le modèle de données de marché change une décision structurante.
- Risques: confondre reproductibilité M-011 et validation scientifique M-012; optimiser sur le corpus pilote; oublier les résultats échoués dans les métriques; publier des backtests sans les métriques SD de compilabilité, origines, paramètres à calibrer, conflits et versions.

## Tâches
### T-010 - Mesurer les stratégies et backtests pilotes
- But métier: publier un benchmark de stratégies et expériences qui conserve limites, coûts et résultats défavorables.
- Portée DDD: `StrategyEvaluationCase`, `StrategyDesignBenchmark`, `BacktestBenchmarkRun`, `BacktestBenchmarkResult`, protocole de calibration de paramètres, séparation hors échantillon, taux de stratégies compilables, raisons principales de rejet, proportion de règles par origine, paramètres sans plan de calibration, conflits de compatibilité par catégorie, nombre de versions par stratégie, métriques calculées, diagnostics de biais et conservation des échecs.
- Scénario BDD:
  - Given des stratégies candidates snapshotées et des expériences reproductibles M-011.
  - When les backtests pilotes sont mesurés selon un protocole M-012.
  - Then les métriques SD, les métriques EX, limites, coûts, périodes, univers et résultats négatifs sont publiés sans promotion implicite de rentabilité.
- Tests d'acceptation à écrire: `tests/m012/validate_strategy_backtest_benchmark_acceptance.ps1`, qui échoue si un paramètre est optimisé sans protocole, si un résultat négatif est retiré, si une métrique provient du LLM, si la période ou les coûts manquent, si un verdict de rentabilité est publié sans qualification, si le taux de stratégies compilables manque, si une raison de rejet manque, si les origines de règles ne sont pas agrégées, si les paramètres sans plan de calibration ne sont pas comptés ou si les conflits de compatibilité ne sont pas catégorisés.
- Tests unitaires à écrire: tests de benchmark pour paramètre sans domaine, protocole absent, entrée mutable, métrique LLM interdite, résultat négatif conservé, échec conservé, séparation hors échantillon manquante, hypothèse absente, comparaison de backtests non comparable, stratégie non compilable comptée, raison de rejet agrégée, origine de règle comptabilisée, paramètre sans plan de calibration, conflit par catégorie et nombre de versions par stratégie.
- Implémentation attendue: créer les cas d'évaluation SD/EX, le benchmark SD, le runner de backtests pilotes, le format de résultat de benchmark, les contrôles de protocole de calibration et le rapport de résultats incluant métriques SD, échecs et limites.
- Invariants et garde-fous: aucune optimisation cachée; aucun backtest lancé sans snapshot; aucun résultat supprimé; aucune métrique hors contexte; aucune promesse de rentabilité; aucune stratégie non compilable retirée du dénominateur.
- Dépendances: T-009; `app/strategy_design`; `app/experimentation`; `docs/specs/m010_strategie_candidate_attribuee.md`; `docs/specs/m011_experience_reproductible.md`; DDD-ADR-009; DDD-ADR-010.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_strategy_backtest_benchmark_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_strategy_backtest_benchmark_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m012_specification.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m012): couvrir le benchmark backtests`
- Commit GREEN: `feat(m012): mesurer strategies et backtests pilotes`
