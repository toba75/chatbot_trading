# T-002 - Publier la spécification d'expérience reproductible

## Milestone
- Nom: M-011 - Expérience reproductible.
- Source: plan M-011 et spécification v4.1, sections EX, contrats publiés, commandes, API, observabilité, tests et définition de terminé.
- Objectif métier: publier le contrat exécutable du bounded context EX avant d'implémenter un backtest.

## Contexte DDD
- Domaine: expérimentation quantitative reproductible.
- Bounded context: EX, avec SD en amont, RA et CV en aval, et plateforme locale comme support d'exécution.
- Objectif métier: définir comment EX transforme un `StrategySnapshot` en expérience planifiée, exécutée, terminée ou échouée, avec entrées figées et résultat conservé.
- Langage ubiquitaire: expérience, résultat d'expérience, snapshot de données, modèle de coûts, environnement d'exécution, graine, backtest, registre append-only, répétition, comparaison, invalidation.
- Invariants critiques: une expérience ne démarre pas avec des entrées mutables; les métriques viennent du moteur déterministe; les résultats négatifs et échoués restent consultables; une correction crée une nouvelle expérience.
- Garde-fous: aucun calcul financier par LLM; aucune lecture d'une stratégie mutable; aucune donnée de marché actuelle inventée; aucune suppression de résultat défavorable.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-001; la spécification détaillée M-011 n'existe pas encore sous `docs/specs`.
- Présence des milestones amont dans master: M-010 présent dans `master`.
- Décisions manquantes: aucune si M-011 applique DDD-ADR-009 et DDD-ADR-010 sans en changer le sens.
- Risques: spécification centrée sur l'adaptateur de backtest au lieu de l'agrégat EX; oubli des résultats échoués; absence de modèle de coûts complet; confusion entre backtest reproductible et validation scientifique M-012.

## Tâches
### T-002 - Publier la spécification d'expérience reproductible
- But métier: rendre M-011 implémentable par comportements EX vérifiables.
- Portée DDD: mission EX, agrégat `Experiment`, artefact `ExperimentResult`, objets-valeur `DataSnapshotRef`, `CostModelSnapshot`, `ExecutionEnvironment`, politiques de reproductibilité, point-in-time, coûts, rétention, répétition, comparaison, invalidation, commandes, événements, ports, API publiques, erreurs publiques, métriques et exclusions M-012.
- Scénario BDD:
  - Given la mission M-011 est de transformer une stratégie snapshotée en expérience auditable.
  - When la spécification d'expérience reproductible est publiée.
  - Then chaque comportement M-011 nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.
- Tests d'acceptation à écrire: `tests/m011/validate_m011_specification_acceptance.ps1`, qui échoue tant que `docs/specs/m011_experience_reproductible.md` et son validateur n'existent pas.
- Tests unitaires à écrire: tests de `scripts/validate_m011_specification.ps1` pour mission absente, agrégat absent, entrées figées absentes, modèle de coûts absent, moteur déterministe absent, registre append-only absent, commande `CompareExperiments` absente, résultats négatifs absents, endpoints absents, erreurs publiques absentes, métriques absentes, exclusion de calibration M-012 absente et ADR manquantes.
- Implémentation attendue: créer `docs/specs/m011_experience_reproductible.md`, créer `scripts/validate_m011_specification.ps1`, enrôler la validation dans `scripts/test.ps1` et `scripts/lint.ps1`, puis relier les exigences M-011 à `docs/traceability/matrix.md`.
- Invariants et garde-fous: aucune décision structurante implicite; aucune validation scientifique présentée comme livrée; aucune métrique issue d'un LLM; aucun champ de stockage interne dans le contrat public.
- Dépendances: T-001; DDD-ADR-009; DDD-ADR-010; `docs/tasks/README.md`; `docs/specs/plan_implementation_milestones_workstreams.md`; `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m011\validate_m011_specification_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m011_specification.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m011): couvrir la specification experience reproductible`
- Commit GREEN: `docs(m011): publier la specification experience reproductible`
