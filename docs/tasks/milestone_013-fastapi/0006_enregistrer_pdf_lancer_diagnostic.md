# T-006 - Enregistrer un PDF et lancer son diagnostic

## Milestone

- Nom: M13-FastAPI - API orchestratrice ASGI raccordée.
- Source: contrats HTTP M-003, ADR-018 et test RED `8ec5231e4`.
- Objectif métier: rendre opérationnelles les commandes documentaires publiques depuis tout client autorisé, notamment l'UI.

## Contexte DDD

- Domaine: traitement des sources.
- Bounded context: SP; l'API orchestratrice traduit HTTP et délègue.
- Objectif métier: enregistrer l'original immuable puis soumettre un diagnostic réel et idempotent.
- Langage ubiquitaire: PDF original, métadonnées bibliographiques, SourceDocument, diagnostic demandé.
- Invariants critiques: métadonnées obligatoires, original PDF valide, doublon explicite, job `DIAGNOSE` persistant.
- Garde-fous: aucun nom de fichier transformé en métadonnée; aucun diagnostic simulé; aucun corps binaire journalisé.

## Blocages Ou Préconditions

- T-005 GREEN.
- Le test RED `uv run --locked gate` doit être repris et adapté au client ASGI au lieu d'être dupliqué.
- Risque: charger sans limite un PDF en mémoire ou accepter simultanément JSON et multipart avec des règles divergentes.

## Tâches

### T-006 - Enregistrer un PDF et lancer son diagnostic

- But métier: publier `POST /v1/documents` et `POST /v1/documents/{document_id}/diagnose` sur l'application orchestratrice.
- Portée DDD: routeur documentaire, modèles d'entrée, adaptateurs SP existants et composition des cas d'usage réels.
- Scénario BDD:
  - Given un PDF et des métadonnées bibliographiques explicites sont transmis à l'API
  - When le client enregistre la source puis demande son diagnostic
  - Then SP conserve l'original, retourne le `DocumentId` public et soumet un job `DIAGNOSE` persistant sans exposer d'identifiant interne
- Tests d'acceptation à écrire: adapter `uv run --locked gate` et créer `uv run --locked gate` pour multipart, doublon et erreurs publiques.
- Tests unitaires à écrire: `uv run --locked gate`, couvrant taille, type MIME, champs bibliographiques, `DocumentId` et mapping des erreurs M-003.
- Implémentation attendue: utiliser `UploadFile`/formulaire multipart strict, déléguer à `SourceProcessingHttpAdapter` et `DocumentCommandService`, injectés par le composition root.
- Invariants et garde-fous: limite explicite de taille; type PDF et structure validés par SP; aucune route de secours; les champs internes restent absents de la réponse.
- Dépendances: T-005; spécification M-003; ADR-018; ADR-019.
- Commandes de validation:
  - `uv run --locked gate`
  - `uv run --locked gate`
  - `uv run --locked gate`
  - `uv run --locked gate`
- Commit RED: `test(api): couvrir commandes documentaires asgi`.
- Commit GREEN: `feat(api): raccorder enregistrement et diagnostic sp`.
