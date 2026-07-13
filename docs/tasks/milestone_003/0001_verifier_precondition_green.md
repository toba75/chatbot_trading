# T-001 - Vérifier et rétablir la précondition GREEN de M-003

## Milestone
- Nom: M-003 - Source enregistrée, diagnostiquée et routée.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, section `M-003 - Source enregistrée, diagnostiquée et routée`, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 5, 12, 17, 19, 20 et 21.
- Objectif métier: prouver que la gouvernance, les frontières DDD, les contrats publiés et la plateforme locale sont GREEN avant d'enregistrer et diagnostiquer des sources PDF.

## Contexte DDD
- Domaine: gouvernance d'implémentation et traitement des sources documentaires.
- Bounded context: `SP`, avec dépendance préalable vers `platform` pour les jobs, l'outbox et les gates.
- Objectif métier: empêcher que le traitement des sources démarre sur une base de tests déjà RED.
- Langage ubiquitaire: précondition GREEN, source documentaire, PDF original, diagnostic de page, route explicite, gate, RED, GREEN.
- Invariants critiques: M-000, M-001 et M-002 sont présents dans `master`; un RED existant bloque l'implémentation M-003; aucune correction ne doit masquer une gate en échec.
- Garde-fous: exécuter les gates standard; consigner le RED exact; corriger uniquement la cause vérifiée; ne pas basculer vers une branche ou une fixture alternative.

## Blocages Ou Préconditions
- État GREEN/RED connu: au 2026-06-26, `uv run --locked gate` est GREEN avec 11 validations et `uv run --locked gate` est RED sur `uv run --locked gate` avec `Service fixture absent: postgres`.
- Présence des milestones amont dans master: `git fetch origin --prune` a confirmé `master` et `origin/master` à `b7941bdc69c7aae85066878e303d5a9e05d433cf`; `docs/tasks/milestone_000`, `docs/tasks/milestone_001` et `docs/tasks/milestone_002` sont visibles dans `master`.
- Décisions manquantes: aucune décision structurante nouvelle pour la précondition; ADR-010 gouverne déjà les gates uv run --locked gate
- Risques: ignorer le RED M-002; commencer M-003 sur une suite partielle; corriger la fixture Compose sans prouver que les gates complètes repassent GREEN.

## Tâches
### T-001 - Vérifier et rétablir la précondition GREEN de M-003
- But métier: établir une preuve de départ fiable avant tout comportement de traitement des sources.
- Portée DDD: gouvernance transverse; aucune règle métier SP n'est ajoutée avant la remise au vert.
- Scénario BDD:
  - Given M-000, M-001 et M-002 sont présents dans `master`.
  - When les gates de validation sont exécutées avant la première tâche métier M-003.
  - Then M-003 peut commencer uniquement si `test`, `lint`, la traçabilité, les ADR et les frontières d'architecture sont GREEN.
- Tests d'acceptation à écrire: un test de précondition M-003 qui exécute `uv run --locked gate` et `uv run --locked gate`, vérifie la présence de `docs/tasks/milestone_002` dans `master` et échoue explicitement si une gate est RED.
- Tests unitaires à écrire: tests du validateur de précondition avec gate RED, milestone amont absent de `master`, référence `master` divergente et sortie de test vide.
- Implémentation attendue: corriger le blocage `uv run --locked gate` ou sa fixture réelle, créer le validateur de précondition M-003 et enregistrer les commandes exécutées.
- Invariants et garde-fous: aucun passage GREEN sans exécuter les commandes; aucun fallback vers une fixture absente ignorée; aucun `try/catch` qui transforme un RED en avertissement.
- Dépendances: M-000; M-001; M-002; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `git ls-tree -r --name-only master -- docs/tasks/milestone_000 docs/tasks/milestone_001 docs/tasks/milestone_002`.
- Commit RED: `test(m003): couvrir la precondition green des sources`.
- Commit GREEN: `test(m003): retablir la precondition green des sources`.
