# T-003 - Planifier une expérience depuis un snapshot de stratégie

## Milestone
- Nom: M-011 - Expérience reproductible.
- Source: M-011, DDD-ADR-009, contrat `StrategySnapshot` et relation SD -> EX.
- Objectif métier: créer une expérience uniquement depuis une stratégie snapshotée, jamais depuis une stratégie mutable.

## Contexte DDD
- Domaine: expérimentation quantitative reproductible.
- Bounded context: EX consommant le langage publié SD.
- Objectif métier: ouvrir un agrégat `Experiment` planifié avec référence stable au `StrategySnapshot` et l'inscrire dans le registre append-only EX.
- Langage ubiquitaire: `Experiment`, `ExperimentId`, `StrategySnapshotRef`, `spec_hash`, statut `PLANNED`, mandat expérimental, diagnostic d'entrée, `ExperimentRepository`, registre append-only.
- Invariants critiques: EX ne lit jamais l'état mutable de `StrategyCandidate`; le snapshot doit être complet, hashé, versionné et résolvable; une expérience possède un identifiant stable dès la planification; une expérience planifiée ne peut pas être supprimée ou réécrite dans le registre.
- Garde-fous: pas de référence `/current`; pas de payload SD interne; pas de planification si le snapshot est absent ou non `COMPILABLE`; pas de backtest au moment de planifier.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-002.
- Présence des milestones amont dans master: M-010 présent dans `master`; le contrat `StrategySnapshot` existe depuis M-001 et son store SD depuis M-010.
- Décisions manquantes: aucune si EX consomme le contrat publié sans nouvelle frontière.
- Risques: reconstruire une stratégie à partir d'une réponse RA; accepter une référence mutable; lancer un backtest avant que données, coûts et environnement soient figés.

## Tâches
### T-003 - Planifier une expérience depuis un snapshot de stratégie
- But métier: établir l'intention expérimentale EX sans modifier la stratégie source.
- Portée DDD: commande `PlanExperiment`, agrégat `Experiment`, port `StrategySnapshotReader`, port `ExperimentRepository`, registre append-only des expériences, politique `ExperimentReproducibilityPolicy`, événement `ExperimentPlanned`, statut `PLANNED` et diagnostics publics d'entrée.
- Scénario BDD:
  - Given un `StrategySnapshot` SD complet, hashé et immuable existe pour une stratégie compilable.
  - When EX planifie une expérience pour ce snapshot.
  - Then l'expérience passe à `PLANNED` avec `ExperimentId`, `StrategySnapshotRef`, `spec_hash` et diagnostic public, sans lire ni modifier la stratégie mutable.
- Tests d'acceptation à écrire: `tests/m011/validate_experiment_planning_acceptance.ps1`, qui échoue tant qu'une expérience peut être planifiée depuis une référence mutable, un snapshot absent, un snapshot non compilable ou un payload SD interne, ou tant qu'une expérience `PLANNED` peut être supprimée ou écrasée dans le registre.
- Tests unitaires à écrire: tests de `Experiment`, `PlanExperimentHandler`, `StrategySnapshotReader`, `ExperimentRepository`, `ExperimentReproducibilityPolicy` et `ExperimentPlanned` pour snapshot absent, hash absent, statut interdit, identifiant invalide, doublon d'idempotence, payload mutable, suppression du registre, réécriture de transition et absence d'événement.
- Implémentation attendue: créer le modèle de domaine EX minimal, le cas d'usage de planification, le port `ExperimentRepository`, un registre append-only en mémoire pour les tests, un lecteur de snapshot en mémoire, les diagnostics publics et l'événement `ExperimentPlanned` sans démarrer le moteur de backtest.
- Invariants et garde-fous: aucune lecture SD interne; aucune mutation du snapshot; aucun démarrage implicite; aucun identifiant généré depuis un chemin de fichier; aucun fallback vers la dernière stratégie connue; aucune suppression ou réécriture d'expérience planifiée.
- Dépendances: T-002; `app/contracts/strategy_experiments.py`; `app/strategy_design/adapters/in_memory_strategy_snapshot_store.py`; DDD-ADR-009.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_experiment_planning_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_experiment_planning_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m001\validate_strategy_experiment_contracts_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m011): couvrir planification experience snapshot`
- Commit GREEN: `feat(m011): planifier experience depuis snapshot`
