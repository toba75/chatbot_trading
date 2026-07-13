# T-011 - Relier M-008 aux métriques, à la traçabilité et aux gates

## Milestone
- Nom: M-008 - Conversation produit.
- Source: plan M-008, spécification v4.1 sections observabilité, tests, critères V1 et définition d'achèvement transverse.
- Objectif métier: clôturer M-008 avec des preuves de conformité auditables.

## Contexte DDD
- Domaine: conversation produit fondée sur preuves.
- Bounded context: CV.
- Objectif métier: rendre mesurables les conversations, questions résolues, modes sélectionnés, réponses attachées et archivages sans journaliser le contenu complet des messages.
- Langage ubiquitaire: métriques CV, trace conversationnelle, question résolue, mode sélectionné, statut documentaire, archive, matrice de traçabilité, gate.
- Invariants critiques: chaque exigence M-008 possède test, commande, ADR ou justification; les métriques ne contiennent pas de message complet, prompt ni texte documentaire complet; tous les tests M-008 sont enrôlés dans les gates.
- Garde-fous: aucune métrique basée sur payload sensible; aucun compteur de tours utilisé comme preuve documentaire; aucune gate ignorée après ajout des endpoints.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-001 à T-010 terminés.
- Présence des milestones amont dans master: M-007 présent.
- Décisions manquantes: aucune pour métriques locales; ADR requise si une solution d'observabilité durable ou une rétention de logs persistante est introduite.
- Risques: traçabilité incomplète; fuite de messages utilisateur dans les signaux; tests M-008 non enrôlés dans `uv run --locked gate` ou `uv run --locked gate`.

## Tâches
### T-011 - Relier M-008 aux métriques, à la traçabilité et aux gates
- But métier: prouver que la conversation produit est terminée, vérifiable et observable sans exposer de contenu sensible.
- Portée DDD: signaux d'audit CV, métriques de résolution et routage, matrice `docs/traceability/matrix.md`, enrôlement des tests M-008, snapshot de métriques et journal de milestone.
- Scénario BDD:
  - Given les comportements M-008 sont implémentés et testés.
  - When la matrice de traçabilité et les gates sont exécutées.
  - Then chaque exigence M-008 est rattachée à un test GREEN, une commande de validation et une ADR ou justification explicite.
- Tests d'acceptation à écrire: `uv run --locked gate`, qui échoue tant que M-008 n'est pas relié à la matrice et aux gates.
- Tests unitaires à écrire: tests des métriques CV pour conversations créées, tours ajoutés, questions résolues, ambiguïtés, modes sélectionnés, réponses attachées, archives, absence de message complet, absence de prompt et absence de texte documentaire.
- Implémentation attendue: créer `app/conversation/application/traceability_metrics.py`, produire `docs/governance/m008_conversation_metrics.json`, compléter `docs/traceability/matrix.md`, enrôler toutes les validations M-008 et documenter la clôture dans `docs/tasks/milestone_008/journal.md`.
- Invariants et garde-fous: aucun payload complet dans les métriques; aucune preuve complète ni prompt persistant; aucun comportement M-008 absent de la traçabilité; aucune gate ignorée.
- Dépendances: T-001 à T-010; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `git diff --check`.
- Commit RED: `test(m008): couvrir tracabilite metriques gates`
- Commit GREEN: `chore(m008): relier metriques tracabilite gates`

