# T-001 - Vérifier la précondition GREEN de M13-FastAPI

## Milestone

- Nom: M13-FastAPI - API orchestratrice ASGI raccordée.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, ADR-018 et demande utilisateur du 2026-07-12.
- Objectif métier: établir une base vérifiable avant de remplacer la frontière HTTP publique et de raccorder les contrats documentaires.

## Contexte DDD

- Domaine: plateforme locale et accès au pipeline documentaire.
- Bounded contexts: `platform`, SP, KA et UI comme client.
- Objectif métier: distinguer une régression existante d'un RED attendu du sous-milestone.
- Langage ubiquitaire: API orchestratrice, contrat public, cas d'usage réel, read-model, erreur explicite.
- Invariants critiques: aucune suite initialement RED indépendante ne peut être masquée; aucun changement utilisateur n'est réinitialisé.
- Garde-fous: pas d'exclusion silencieuse, pas d'affaiblissement de gate, pas de preuve issue d'un mock.

## Blocages Ou Préconditions

- État connu: M-001 à M-012 sont présents dans `master` au commit observé `8670e88f9` lors de la planification.
- Le test `uv run --locked gate`, commit `8ec5231e4`, est un RED intentionnel non enrôlé à reprendre par T-006 et non une preuve de précondition GREEN.
- La modification utilisateur de `uv run --locked gate` reste hors périmètre.
- Risque: confondre une indisponibilité locale de configuration ou Spark avec une régression du runtime HTTP.

## Tâches

### T-001 - Vérifier la précondition GREEN de M13-FastAPI

- But métier: publier un état initial reproductible des contrats HTTP et des frontières d'architecture concernés.
- Portée DDD: tests existants de `platform`, M-003, M-004, M-005 et UI; aucun code de production.
- Scénario BDD:
  - Given les milestones M-001 à M-012 sont présents dans `master` et le worktree peut contenir des changements utilisateur
  - When les validations existantes pertinentes sont exécutées avant toute implémentation M13-FastAPI
  - Then chaque résultat GREEN, RED attendu ou blocage externe est classé explicitement sans modifier ni contourner l'existant
- Tests d'acceptation à écrire: `uv run --locked gate`, vérifiant les contrats HTTP M-003, la frontière UI/API et la présence des sources canoniques.
- Tests unitaires à écrire: `uv run --locked gate`, vérifiant la classification stricte `GREEN`, `EXPECTED_RED` ou `BLOCKED_EXTERNAL`.
- Implémentation attendue: créer `docs/governance/m013_fastapi_precondition.md` avec commandes, sorties, commit de référence et écarts; ne modifier aucun comportement applicatif.
- Invariants et garde-fous: un RED indépendant bloque la suite; le RED `8ec5231e4` reste attribué à T-006; aucun fichier utilisateur n'est inclus dans les commits.
- Dépendances: M-001 à M-012 dans `master`; ADR-018; tests M-003 à M-005 et M-013 UI.
- Commandes de validation:
  - `uv run --locked gate`
  - `uv run --locked gate`
  - `uv run --locked gate`
- Commit RED: `test(platform): couvrir precondition m13 fastapi`.
- Commit GREEN: `docs(platform): publier precondition m13 fastapi`.
