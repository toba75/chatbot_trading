# T-001 - Vérifier et rétablir la précondition GREEN M-012

## Milestone
- Nom: M-012 - Évaluation pilote et calibration.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, section `M-012 - Évaluation pilote et calibration`, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 19, 20, 21 et 22.
- Objectif métier: démarrer l'évaluation pilote uniquement depuis M-011 fusionné, avec des expériences reproductibles disponibles et sans masquer un état RED existant.

## Contexte DDD
- Domaine: évaluation scientifique et calibration des seuils.
- Bounded context: transverse, avec SP, KA, EG, RA, CV, SD et EX évalués sans changer leurs responsabilités métier.
- Objectif métier: prouver que M-012 commence depuis un système M-011 présent dans `master`, traçable et prêt à être mesuré sur corpus pilote.
- Langage ubiquitaire: précondition GREEN, corpus pilote, jeu annoté, benchmark, métrique scientifique, seuil calibré, promotion, rapport d'écarts V1, `master`, gate.
- Invariants critiques: M-011 doit être visible dans `master`; la branche M-012 doit contenir `master`; aucun test scientifique RED ne doit être requalifié en succès logiciel; aucun benchmark ne doit s'exécuter sur une base non reproductible.
- Garde-fous: ne pas accepter une branche M-011 locale comme preuve de fusion; ne pas créer de seuil par préférence implicite; ne pas traiter un validateur amont RED comme un bruit de planification.

## Blocages Ou Préconditions
- État GREEN/RED connu: après `git fetch origin --prune` puis `git fetch origin master:master`, `master` et `origin/master` pointent sur `0a166827f921ec769e16462891aa8cebd0f7f299`; avant création de M-012, `uv run --locked gate` est GREEN avec `12 milestone(s), 122 tâche(s) contrôlée(s)` et `uv run --locked gate` est GREEN avec `22 validation(s), 0 test(s)`; `uv run --locked gate` est RED sur `uv run --locked gate` avec `La précondition M-003 doit être GREEN sur la base courante. Code obtenu: 1`, car les validateurs de précondition amont ne reconnaissent pas encore la branche aval M-012.
- Présence des milestones amont dans master: M-011 requis et présent dans `master`, avec 54 entrées observées couvrant `docs/tasks/milestone_011`, `docs/specs/m011_experience_reproductible.md`, `uv run --locked gate`, `uv run --locked gate`, `uv run --locked gate`, `tests/m011`, `app/experimentation` et `app/contracts/strategy_experiments.py`.
- Décisions manquantes: aucune pour planifier M-012; une ADR nouvelle sera requise seulement si la calibration change une décision structurante sur le routage documentaire, le modèle principal, la conservation, la sécurité inter-hôtes ou la frontière d'un bounded context.
- Risques: démarrer M-012 sans élargir explicitement les validateurs de précondition amont à M-012; mélanger tests logiciels et tests scientifiques; calibrer sur un corpus non figé; promouvoir un checkpoint communautaire sans benchmark comparable.

## Tâches
### T-001 - Vérifier et rétablir la précondition GREEN M-012
- But métier: établir une base GREEN vérifiable avant toute mesure de qualité ou décision de calibration.
- Portée DDD: gouvernance de précondition M-012, présence de M-011 dans `master`, branche de travail contenant `master`, rapport de précondition, commandes de validation et absence de contournement des gates amont.
- Scénario BDD:
  - Given M-011 est présent dans `master` avec sa spécification, ses tâches, ses tests, ses contrats EX et ses expériences reproductibles.
  - When les gates de précondition M-012 sont exécutées sur une branche M-012.
  - Then M-012 ne peut commencer que si les validateurs amont acceptent explicitement le jalon aval et si `test`, `lint`, traçabilité, ADR et frontières d'architecture ont un verdict exploitable.
- Tests d'acceptation à écrire: `uv run --locked gate`, qui échoue tant que M-011 n'est pas visible dans `master`, que le rapport de précondition M-012 n'existe pas, qu'un gate requis n'a pas de verdict exploitable ou qu'un validateur amont refuse la branche M-012.
- Tests unitaires à écrire: tests de `uv run --locked gate` pour M-011 absent de `master`, branche ne contenant pas `master`, divergence `origin/master`, test global timeout non qualifié, gate RED, rapport GREEN sans sorties de commande, validateur amont refusant M-012 et validateur amont qui ignore M-012.
- Implémentation attendue: créer `uv run --locked gate`, créer `docs/governance/m012_precondition_green.md`, ajuster seulement les validateurs de précondition amont nécessaires pour reconnaître M-012 sans changer leur sens, enrôler les tests M-012 et obtenir un verdict GREEN sur les commandes ciblées et globales.
- Invariants et garde-fous: aucun fallback de validation; aucune suppression de test amont; aucun statut GREEN sans preuve de commande; aucun délai dépassé traité comme succès; aucun benchmark lancé avant précondition explicite.
- Dépendances: `master`; `origin/master`; `docs/tasks/milestone_011`; `docs/specs/m011_experience_reproductible.md`; `app/experimentation`; `app/contracts/strategy_experiments.py`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commandes de validation: `git fetch origin --prune`; `git ls-tree -r --name-only master -- docs/tasks/milestone_011 docs/specs/m011_experience_reproductible.md uv run --locked gate uv run --locked gate uv run --locked gate tests/m011 app/experimentation app/contracts/strategy_experiments.py`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m012): couvrir la precondition green evaluation pilote`
- Commit GREEN: `test(m012): retablir la precondition green evaluation pilote`
