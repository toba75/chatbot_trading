# T-003 - Publier la convention des tâches de milestone

## Milestone
- Nom: M-000 - Gouvernance exécutable.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, sections `M-000 - Gouvernance exécutable` et `Règles de création des tâches détaillées`.
- Objectif métier: rendre les tâches d'implémentation retrouvables, ordonnées et exécutables selon le workflow BDD/TDD du projet.

## Contexte DDD
- Domaine: gouvernance d'implémentation.
- Bounded context: transverse.
- Objectif métier: éviter qu'un milestone soit implémenté à partir d'intentions dispersées ou de tâches non vérifiables.
- Langage ubiquitaire: milestone, tâche verticale, scénario BDD, test RED, commit RED, commit GREEN, commande de validation.
- Invariants critiques: un dossier de milestone suit `docs/tasks/milestone_NNN`; une tâche suit `NNNN_slug.md`; la première tâche est la précondition GREEN; chaque tâche possède un scénario Given-When-Then et des commandes de validation.
- Garde-fous: validation stricte de nommage et de structure; refus d'une tâche sans comportement observable.

## Blocages Ou Préconditions
- État GREEN/RED connu: `docs/tasks` existe localement mais aucun dossier de tâches n'est versionné dans `master`.
- Présence des milestones amont dans master: M-000 n'a aucune dépendance amont.
- Décisions manquantes: aucune ADR requise, sauf si la convention introduit une décision structurante non prévue par le plan.
- Risques: créer des tâches horizontales ou techniques qui ne portent pas de scénario métier observable.

## Tâches
### T-003 - Publier la convention des tâches de milestone
- But métier: fournir une convention exécutable pour créer, relire et exécuter les tâches de milestone.
- Portée DDD: gouvernance transverse des tâches; langage métier français obligatoire dans les titres et scénarios.
- Scénario BDD:
  - Given un milestone prêt à être détaillé.
  - When une tâche est créée dans `docs/tasks/milestone_NNN`.
  - Then son nom, son ordre, son scénario BDD, ses tests RED/GREEN et ses commandes de validation sont contrôlables automatiquement.
- Tests d'acceptation à écrire: un test qui échoue si une tâche de milestone ne respecte pas le format de chemin, omet le scénario BDD, omet un commit RED/GREEN ou place une tâche avant la précondition GREEN.
- Tests unitaires à écrire: tests de validation du numéro de milestone, du numéro séquentiel, du slug sans accents, des sections obligatoires et de la présence des champs TDD.
- Implémentation attendue: créer la documentation de convention des tâches et un validateur strict du dossier `docs/tasks`; intégrer cette validation à la future commande de test M-000.
- Invariants et garde-fous: pas de dossier de milestone aval si ses dépendances amont manquent dans `master`; pas de tâche sans validation; pas de correction silencieuse des slugs ou numéros.
- Dépendances: T-001; plan de milestones; règles AGENTS BDD/TDD; structure `docs/tasks`.
- Commandes de validation: future commande `uv run --locked gate`; puis `uv run --locked gate` après T-006.
- Commit RED: `test(m000): couvrir la convention des tâches de milestone`.
- Commit GREEN: `feat(m000): publier la convention contrôlée des tâches`.
