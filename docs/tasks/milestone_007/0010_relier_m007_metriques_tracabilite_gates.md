# T-010 - Relier M-007 aux métriques, à la traçabilité et aux gates

## Milestone
- Nom: M-007 - Réponse documentaire vérifiée.
- Source: plan M-007, spécification v4.1 sections observabilité, tests, critères V1 et définition d'achèvement transverse.
- Objectif métier: clôturer M-007 avec des preuves de conformité auditables.

## Contexte DDD
- Domaine: recherche et réponse vérifiée.
- Bounded context: RA.
- Objectif métier: rendre mesurables les réponses supportées, partielles, conflictuelles, insuffisantes et abstinentes sans journaliser le contenu complet des réponses.
- Langage ubiquitaire: métriques RA, trace de réponse, `SupportStatus`, `KnowledgeGap`, `Citation`, `VerifiedResearchOutcome`, matrice de traçabilité, gate.
- Invariants critiques: chaque exigence M-007 possède test, commande, ADR ou justification; les métriques ne contiennent pas de prompt ni texte complet de réponse; les gates restent GREEN.
- Garde-fous: aucune métrique basée sur payload sensible; aucun compteur de citations utilisé comme preuve de consensus; aucun test M-007 non enrôlé dans la gate globale.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-001 à T-009 terminés.
- Présence des milestones amont dans master: M-006 présent.
- Décisions manquantes: aucune pour métriques locales; ADR requise si une nouvelle solution d'observabilité durable est introduite.
- Risques: traçabilité incomplète; fuite de contenu documentaire dans les signaux; gates non alignées après ajout des tests M-007.

## Tâches
### T-010 - Relier M-007 aux métriques, à la traçabilité et aux gates
- But métier: prouver que M-007 est terminé, vérifiable et observable sans exposer de contenu sensible.
- Portée DDD: signaux d'audit RA, métriques de support documentaire, matrice `docs/traceability/matrix.md`, enrôlement des tests M-007, documentation de clôture et journal de milestone.
- Scénario BDD:
  - Given les comportements M-007 sont implémentés et testés.
  - When la matrice de traçabilité et les gates sont exécutés.
  - Then chaque exigence M-007 est rattachée à un test GREEN, une commande de validation et une ADR ou justification explicite.
- Tests d'acceptation à écrire: `uv run --locked gate`, qui échoue tant que M-007 n'est pas relié à la matrice et aux gates.
- Tests unitaires à écrire: tests des métriques RA pour statuts, citations, lacunes, contradictions, abstentions, latence, absence de texte complet, absence de prompt et refus de signal non anonymisé.
- Implémentation attendue: créer `app/research_answering/application/traceability_metrics.py`, produire le snapshot de métriques M-007, compléter `docs/traceability/matrix.md`, enrôler les validations M-007 et documenter la clôture dans le journal.
- Invariants et garde-fous: aucun payload de réponse complet dans les métriques; aucune preuve complète ni prompt persistant; aucun statut M-007 absent de la traçabilité; aucune gate ignorée.
- Dépendances: T-001 à T-009; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `git diff --check`.
- Commit RED: `test(m007): couvrir tracabilite metriques gates`
- Commit GREEN: `chore(m007): relier metriques tracabilite gates`

