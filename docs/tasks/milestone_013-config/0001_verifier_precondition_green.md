# T-001 - Vérifier la précondition GREEN de M13-config

## Milestone

- Nom: M13-config - Configuration applicative sans environnement.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, section `M13-config`; ADR-016.
- Objectif métier: sécuriser le sous-milestone avant toute migration de configuration en prouvant que les gates existantes sont GREEN et que les milestones strictement antérieurs à M-013 sont présents dans `master`.

## Contexte DDD

- Domaine: gouvernance d'implémentation et plateforme locale.
- Bounded context: transverse, `platform`.
- Objectif métier: éviter de démarrer la migration de configuration sur une base de gouvernance ambiguë.
- Langage ubiquitaire: sous-milestone, précondition GREEN, configuration applicative, absence de fallback, `master`, ADR-016.
- Invariants critiques: `M13-config` est un sous-milestone de M-013; il ne requiert pas la clôture de M-013; il requiert M-000 à M-012 visibles dans `master`.
- Garde-fous: aucun dossier de tâche aval n'est créé si une précondition amont stricte manque; aucune erreur existante n'est masquée.

## Blocages Ou Préconditions

- État GREEN/RED connu: à vérifier avant le commit RED de la première tâche.
- Présence des milestones amont dans master: M-000 à M-012 doivent être visibles dans `master`; M-013 n'est pas requis pour ce sous-milestone.
- Décisions manquantes: aucune; ADR-016 est créée pour la décision structurante de configuration.
- Risques: confondre sous-milestone `milestone_013-config` et clôture complète de `milestone_013`.

## Tâches

### T-001 - Vérifier la précondition GREEN de M13-config

- But métier: établir une preuve initiale que la migration vers `config/application.yaml` peut être planifiée sans dette de gouvernance cachée.
- Portée DDD: gouvernance transverse, règle de sous-milestone, précondition de plateforme.
- Scénario BDD:
  - Given le sous-milestone `M13-config` est demandé.
  - When la précondition de planification est contrôlée contre `master` et les gates locales.
  - Then M-000 à M-012 sont présents, M-013 n'est pas exigé comme clôturé, et les gates de gouvernance restent GREEN.
- Tests d'acceptation à écrire: aucun nouveau test d'acceptation fonctionnel; réutiliser `uv run --locked gate` pour la règle de sous-milestone.
- Tests unitaires à écrire: aucun nouveau test unitaire applicatif; réutiliser `uv run --locked gate`.
- Implémentation attendue: produire le rapport de précondition dans `docs/tasks/milestone_013-config/journal.md` avec les commandes exécutées, les références Git observées et le statut GREEN/RED.
- Invariants et garde-fous: ne pas modifier `app/...`; ne pas traiter `milestone_013-config` comme une clôture de `milestone_013`; ne pas ignorer un RED préexistant.
- Dépendances: `AGENTS.md`; `docs/tasks/README.md`; `uv run --locked gate`; `docs/specs/plan_implementation_milestones_workstreams.md`.
- Commandes de validation: `git fetch origin --prune`; `git ls-tree -r --name-only master -- docs/tasks/milestone_000 docs/tasks/milestone_001 docs/tasks/milestone_002 docs/tasks/milestone_003 docs/tasks/milestone_004 docs/tasks/milestone_005 docs/tasks/milestone_006 docs/tasks/milestone_007 docs/tasks/milestone_008 docs/tasks/milestone_009 docs/tasks/milestone_010 docs/tasks/milestone_011 docs/tasks/milestone_012`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m13-config): verifier precondition configuration sans environnement`.
- Commit GREEN: `docs(m13-config): publier preuve precondition green`.
