# T-007 - Lire le diagnostic et la conversion

## Milestone

- Nom: M13-FastAPI - API orchestratrice ASGI raccordée.
- Source: `docs/specs/ui.md`, M-003, M-004 et ADR-018.
- Objectif métier: rendre inspectables les sorties SP sans reconstruire l'état dans l'UI.

## Contexte DDD

- Domaine: traitement des sources.
- Bounded context: SP.
- Objectif métier: publier l'état courant et les sorties page par page du diagnostic et de la conversion canonique.
- Langage ubiquitaire: manifeste, diagnostic de page, route, QA, version canonique, rejet.
- Invariants critiques: chaque page du manifeste reste visible; une sortie absente est nommée sans être inventée.
- Garde-fous: aucun accès direct aux tables, logs ou artefacts internes depuis le routeur ou l'UI.

## Blocages Ou Préconditions

- T-006 GREEN.
- Les sorties SP doivent être persistées par leurs cas d'usage avant d'être exposées.
- Risque: agréger le diagnostic au point de masquer une page absente ou un rejet QA.

## Tâches

### T-007 - Lire le diagnostic et la conversion

- But métier: publier `GET /v1/documents`, `GET /v1/documents/{id}/diagnostic` et `GET /v1/documents/{id}/conversion`.
- Portée DDD: query services et read-models SP, sérialisation publique et routeur de lecture.
- Scénario BDD:
  - Given des documents sont à des étapes différentes du traitement SP
  - When le client liste le corpus ou ouvre les sorties d'un document
  - Then chaque statut, manifeste, diagnostic de page, route, QA et version canonique disponibles sont rendus sans champ interne ni état synthétique
- Tests d'acceptation à écrire: `uv run --locked gate`, couvrant source seule, diagnostic demandé, routage, conversion acceptée et rejetée.
- Tests unitaires à écrire: `uv run --locked gate`, couvrant projection des états, ordre des pages, nullabilité explicite et erreurs `SOURCE_NOT_FOUND`.
- Implémentation attendue: créer des ports de lecture SP et un query service propriétaire; le routeur ne reçoit que des DTO publics immuables.
- Invariants et garde-fous: `original_storage_ref`, job id, table et artefact interne interdits; `DIAGNOSTIC_NOT_REQUESTED` et `CONVERSION_NOT_REQUESTED` ne sont produits que par absence constatée dans le repository réel.
- Dépendances: T-006; spécifications M-003/M-004; UI-003/UI-004/UI-005.
- Commandes de validation:
  - `uv run --locked gate`
  - `uv run --locked gate`
  - `uv run --locked gate`
- Commit RED: `test(sp): couvrir lectures diagnostic conversion`.
- Commit GREEN: `feat(sp): publier lectures diagnostic conversion`.
