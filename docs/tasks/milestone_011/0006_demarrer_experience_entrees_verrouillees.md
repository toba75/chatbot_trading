# T-006 - Planifier, annuler ou démarrer une expérience avec entrées verrouillées

## Milestone
- Nom: M-011 - Expérience reproductible.
- Source: scénario directeur M-011 et DDD-ADR-009.
- Objectif métier: planifier l'exécution, autoriser l'annulation explicite avant démarrage et empêcher toute modification d'entrée dès qu'une expérience est `RUNNING`.

## Contexte DDD
- Domaine: expérimentation quantitative reproductible.
- Bounded context: EX.
- Objectif métier: passer de `PLANNED` à `SCHEDULED`, de `SCHEDULED` à `RUNNING` ou `CANCELLED`, uniquement selon une commande explicite et avec des entrées figées avant démarrage.
- Langage ubiquitaire: `SCHEDULED`, `RUNNING`, `CANCELLED`, scheduler d'expérience, annulation, entrées figées, `frozen_inputs`, verrouillage, idempotence, registre de transitions, `EXPERIMENT_INPUT_NOT_FROZEN`.
- Invariants critiques: une expérience `RUNNING` ne peut plus modifier ses entrées; une expérience ne démarre pas sans snapshot de stratégie, données, coûts et environnement; une expérience `SCHEDULED` peut être annulée explicitement avant démarrage; le démarrage est idempotent pour la même commande; les transitions `SCHEDULED`, `RUNNING` et `CANCELLED` sont enregistrées sans réécriture.
- Garde-fous: pas de démarrage partiel; pas de modification du modèle de coûts pendant `RUNNING`; pas d'annulation après démarrage sans échec explicite; pas de création d'une nouvelle expérience implicite; pas de catch générique qui masque le refus métier.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-005.
- Présence des milestones amont dans master: M-010 présent dans `master`.
- Décisions manquantes: aucune.
- Risques: accepter une modification d'entrée pendant l'exécution; confondre retry technique et nouvelle expérience métier; enregistrer un statut RUNNING sans hash d'entrées; ignorer la transition `SCHEDULED -> CANCELLED` prévue par EX.

## Tâches
### T-006 - Planifier, annuler ou démarrer une expérience avec entrées verrouillées
- But métier: matérialiser le scheduling et le verrou métier qui rendent l'expérience reproductible.
- Portée DDD: commandes `ScheduleExperiment`, `CancelExperiment` et `StartExperiment`, port `ExperimentScheduler`, port `ExperimentRepository`, transitions `PLANNED -> SCHEDULED`, `SCHEDULED -> CANCELLED` et `SCHEDULED -> RUNNING`, registre append-only des transitions, `frozen_inputs`, événements `ExperimentScheduled`, `ExperimentCancelled` et `ExperimentStarted`, refus public `EXPERIMENT_INPUT_NOT_FROZEN` et idempotence de démarrage.
- Scénario BDD:
  - Given une expérience `RUNNING`.
  - When la modification du modèle de coûts est demandée.
  - Then la commande est refusée avec `EXPERIMENT_INPUT_NOT_FROZEN` et une nouvelle expérience doit être planifiée.
- Tests d'acceptation à écrire: `tests/m011/validate_experiment_start_lock_acceptance.ps1`, qui échoue tant qu'une expérience peut démarrer sans entrée complète, modifier son modèle de coûts en `RUNNING`, modifier son snapshot de données en `RUNNING`, relancer un démarrage en doublon, annuler une expérience déjà `RUNNING`, ignorer `ExperimentScheduled` et `ExperimentCancelled`, ou réécrire une transition déjà enregistrée.
- Tests unitaires à écrire: tests de transitions `Experiment`, `ScheduleExperimentHandler`, `CancelExperimentHandler`, `StartExperimentHandler`, `ExperimentScheduled`, `ExperimentCancelled`, `ExperimentStarted`, `ExperimentScheduler`, `ExperimentRepository`, verrouillage de `frozen_inputs`, idempotence, statuts interdits, suppression de transition, réécriture de transition et erreurs publiques.
- Implémentation attendue: implémenter les transitions de scheduling, annulation et démarrage, calculer `frozen_inputs`, persister chaque transition dans le registre append-only, publier `ExperimentScheduled`, `ExperimentCancelled` et `ExperimentStarted`, puis refuser toute mutation d'entrée après démarrage.
- Invariants et garde-fous: aucun statut `RUNNING` sans entrées complètes; aucune modification d'entrée après démarrage; aucune valeur par défaut pour `frozen_at`; aucun démarrage depuis `COMPLETED`, `FAILED` ou `CANCELLED`; aucune annulation depuis `RUNNING`, `COMPLETED` ou `FAILED`; aucune suppression ou réécriture de transition.
- Dépendances: T-005; DDD-ADR-009.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_experiment_start_lock_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_experiment_start_lock_unit.ps1`; `python -m compileall app\experimentation`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m011): couvrir verrouillage entrees experience`
- Commit GREEN: `feat(m011): demarrer experience entrees verrouillees`
