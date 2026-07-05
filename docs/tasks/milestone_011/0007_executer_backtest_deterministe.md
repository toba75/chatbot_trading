# T-007 - Exécuter un backtest déterministe

## Milestone
- Nom: M-011 - Expérience reproductible.
- Source: M-011, port `BacktestEngine` et adaptateur `DeterministicBacktestEngineAdapter`.
- Objectif métier: produire les métriques d'expérience par calcul déterministe, jamais par estimation du LLM.

## Contexte DDD
- Domaine: expérimentation quantitative reproductible.
- Bounded context: EX, avec moteur de backtest comme adaptateur de plateforme local.
- Objectif métier: exécuter une expérience `RUNNING` avec les entrées figées et obtenir une sortie moteur traçable.
- Langage ubiquitaire: backtest déterministe, moteur de backtest, métriques, séries temporelles, positions, transactions, diagnostics de biais, contrôles minimaux de backtest, progression.
- Invariants critiques: le LLM ne produit pas les métriques; le moteur reçoit uniquement les entrées figées; une sortie moteur non déterministe ou incomplète est refusée; les diagnostics de biais restent rattachés au résultat; chaque sortie de backtest expose le statut des contrôles minimaux M-011.
- Garde-fous: pas d'appel Spark pour calcul financier; pas de métrique inventée; pas de retry qui duplique une expérience; pas de lecture de données hors snapshot.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-006.
- Présence des milestones amont dans master: M-010 présent dans `master`.
- Décisions manquantes: aucune si l'adaptateur reste derrière le port EX.
- Risques: coupler le domaine EX au framework de backtest; accepter une sortie sans provenance; laisser le moteur lire des données vivantes.

## Tâches
### T-007 - Exécuter un backtest déterministe
- But métier: transformer les entrées figées en mesures calculées auditables.
- Portée DDD: port `BacktestEngine`, adaptateur `DeterministicBacktestEngineAdapter`, commande `RecordExperimentProgress`, sortie moteur, diagnostics de biais, checklist des contrôles minimaux, absence d'appel LLM et journal de progression.
- Scénario BDD:
  - Given une expérience `RUNNING` avec stratégie, données, coûts, environnement et graine figés.
  - When le backtest déterministe est exécuté.
  - Then les métriques, positions, transactions et diagnostics proviennent du moteur de backtest, sans appel LLM, sans lecture hors snapshot, et avec le statut explicite des contrôles minimaux.
- Tests d'acceptation à écrire: `tests/m011/validate_deterministic_backtest_acceptance.ps1`, qui échoue tant que le moteur peut recevoir une référence mutable, que les métriques peuvent venir d'un LLM, qu'une sortie sans hash est acceptée, qu'une lecture hors `DataSnapshotId` est possible ou qu'un contrôle minimal requis n'a pas de statut explicite.
- Tests unitaires à écrire: tests de `BacktestEngine`, `DeterministicBacktestEngineAdapter`, `BacktestEngineResult`, `RecordExperimentProgress` et garde anti-LLM pour entrée mutable, sortie non déterministe, métrique non finie, diagnostic absent, contrôle minimal absent, progression incohérente et doublon de run.
- Implémentation attendue: créer le port moteur, un adaptateur déterministe de test, les DTO de sortie, l'enregistrement de progression, la checklist des contrôles minimaux et les contrôles interdisant les métriques externes au moteur. La checklist M-011 doit couvrir présence ou diagnostic explicite pour biais de survivance, look-ahead bias, délais de publication, data snooping, commissions, spreads, slippage, financement, borrow, liquidité, capacité, stabilité inter-périodes, stabilité inter-actifs, sensibilité aux paramètres, tests hors échantillon, walk-forward, stress des coûts, stress des corrélations, drawdown, benchmarks simples et analyse des queues.
- Invariants et garde-fous: aucune métrique par LLM; aucune donnée vivante; aucun nombre non fini; aucun résultat sans hash; aucun contrôle minimal masqué ou reporté implicitement vers M-012; aucun import du moteur dans le domaine.
- Dépendances: T-006; `app/platform/local_compose.py`; `app/platform/topology.py`; DDD-ADR-009.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_deterministic_backtest_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_deterministic_backtest_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_architecture_boundaries.ps1 -AppRoot .\app -ContextRegistryPath .\app\context_registry.json -SpecificationPath .\docs\specs\m001_frontieres_ddd_contrats_publies.md`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m011): couvrir backtest deterministe`
- Commit GREEN: `feat(m011): executer backtest deterministe`
