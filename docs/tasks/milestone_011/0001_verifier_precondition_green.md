# T-001 - Vérifier et rétablir la précondition GREEN M-011

## Milestone
- Nom: M-011 - Expérience reproductible.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, section `M-011 - Expérience reproductible`, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 11, 12, 14, 17, 19, 20 et 21.
- Objectif métier: démarrer l'expérimentation uniquement depuis M-010 fusionné, avec un `StrategySnapshot` immuable disponible et sans masquer un état RED existant.

## Contexte DDD
- Domaine: expérimentation quantitative reproductible.
- Bounded context: EX, avec SD comme fournisseur de `StrategySnapshot` et RA/CV comme consommateurs de `ExperimentResult`.
- Objectif métier: prouver que M-011 commence depuis une stratégie snapshotée, hashée et consultable dans `master`.
- Langage ubiquitaire: précondition GREEN, `Experiment`, `StrategySnapshot`, `ExperimentResult`, snapshot de données, modèle de coûts, backtest déterministe, `master`, gate.
- Invariants critiques: M-010 doit être visible dans `master`; la branche M-011 doit contenir `master`; aucune gate RED existante ne doit être ignorée; un résultat de test global sans verdict exploitable ne vaut pas GREEN.
- Garde-fous: ne pas accepter une branche M-010 locale comme preuve de fusion; ne pas créer de backtest avant le contrat EX; ne pas traiter un validateur amont RED comme un bruit de planification.

## Blocages Ou Préconditions
- État GREEN/RED connu: après `git fetch origin --prune` puis `git fetch origin master:master`, `master` et `origin/master` pointent sur `3606b54e65dea73d10bd2af3039c981a9ab37335`; avant création de M-011, `uv run --locked gate` est GREEN avec `11 milestone(s), 110 tâche(s) contrôlée(s)` et `uv run --locked gate` est GREEN avec `20 validation(s), 0 test(s)`; après création de M-011, `uv run --locked gate` est GREEN avec `12 milestone(s), 122 tâche(s) contrôlée(s)`, `uv run --locked gate` est GREEN avec `20 validation(s), 0 test(s)` et `uv run --locked gate` reste RED sur `uv run --locked gate`, car les validateurs de précondition amont autorisent les branches aval jusqu'à M-010 mais pas encore une branche M-011.
- Présence des milestones amont dans master: M-010 requis et présent dans `master`, avec `59` entrées observées couvrant `docs/tasks/milestone_010`, `docs/specs/m010_strategie_candidate_attribuee.md`, `uv run --locked gate`, `uv run --locked gate`, `tests/m010`, `app/strategy_design`, `app/experimentation` et `app/contracts/strategy_experiments.py`.
- Décisions manquantes: aucune pour appliquer DDD-ADR-009 et DDD-ADR-010; ADR nouvelle requise seulement si M-011 change le sens du snapshot immuable, de la conservation des résultats défavorables ou de la frontière SD -> EX.
- Risques: démarrer M-011 avant d'élargir explicitement les validateurs de précondition amont à M-011; confondre résultat de backtest et validation scientifique; introduire un moteur ou une persistance avant les invariants EX.

## Tâches
### T-001 - Vérifier et rétablir la précondition GREEN M-011
- But métier: établir une base GREEN vérifiable avant tout comportement d'expérimentation.
- Portée DDD: gouvernance de précondition M-011, présence de M-010 dans `master`, branche de travail contenant `master`, rapport de précondition, commandes de validation et absence de contournement des gates amont.
- Scénario BDD:
  - Given M-010 est présent dans `master` avec sa spécification, ses tests, ses tâches, ses snapshots SD et son langage publié vers EX.
  - When les gates de précondition M-011 sont exécutées sur une branche M-011.
  - Then M-011 ne peut commencer que si les validateurs amont acceptent explicitement le jalon aval et si `test`, `lint`, traçabilité, ADR et frontières d'architecture ont un verdict GREEN exploitable.
- Tests d'acceptation à écrire: `uv run --locked gate`, qui échoue tant que M-010 n'est pas visible dans `master`, que le rapport de précondition M-011 n'existe pas, qu'un gate requis n'a pas de verdict GREEN exploitable ou qu'un validateur amont refuse la branche M-011.
- Tests unitaires à écrire: tests de `uv run --locked gate` pour M-010 absent de `master`, branche ne contenant pas `master`, divergence `origin/master`, test global timeout non qualifié, gate RED, rapport GREEN sans sorties de commande, validateur amont refusant M-011 et validateur amont qui ignore M-011.
- Implémentation attendue: créer `uv run --locked gate`, créer `docs/governance/m011_precondition_green.md`, ajuster seulement les validateurs de précondition amont nécessaires pour reconnaître M-011 sans changer leur sens, enrôler les tests M-011 et obtenir un verdict GREEN sur les commandes ciblées et globales.
- Invariants et garde-fous: aucun fallback de validation; aucune suppression de test amont; aucun statut GREEN sans preuve de commande; aucun délai dépassé traité comme succès; aucune modification des décisions DDD-ADR-009 et DDD-ADR-010.
- Dépendances: `master`; `origin/master`; `docs/tasks/milestone_010`; `docs/specs/m010_strategie_candidate_attribuee.md`; `app/contracts/strategy_experiments.py`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commandes de validation: `git fetch origin --prune`; `git ls-tree -r --name-only master -- docs/tasks/milestone_010 docs/specs/m010_strategie_candidate_attribuee.md uv run --locked gate uv run --locked gate tests/m010 app/strategy_design app/experimentation app/contracts/strategy_experiments.py`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m011): couvrir la precondition green experience reproductible`
- Commit GREEN: `test(m011): retablir la precondition green experience reproductible`
