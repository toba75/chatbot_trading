# T-008 - Récupérer le PDF original de manière contrôlée

## Milestone

- Nom: M13-FastAPI - API orchestratrice ASGI raccordée.
- Source: ADR-018, DDD-ADR-003 et spécification UI de visualisation.
- Objectif métier: permettre l'ouverture d'une source citée sans révéler son emplacement interne.

## Contexte DDD

- Domaine: traitement des sources et résolution des preuves.
- Bounded context: SP.
- Objectif métier: restituer l'original immuable identifié par son `DocumentId` public.
- Langage ubiquitaire: PDF original, DocumentId, hash source, contenu contrôlé.
- Invariants critiques: contenu bit à bit, type MIME PDF, hash conforme, aucun chemin public.
- Garde-fous: pas de path traversal, pas de téléchargement arbitraire, pas de substitution d'un PDF voisin.

## Blocages Ou Préconditions

- T-007 GREEN.
- L'adaptateur de stockage original de T-005 doit résoudre uniquement une référence interne issue du repository SP.
- Risque: utiliser directement le paramètre d'URL comme chemin de fichier.

## Tâches

### T-008 - Récupérer le PDF original de manière contrôlée

- But métier: publier `GET /v1/documents/{document_id}/original` pour la visualisation et les citations ouvrables.
- Portée DDD: query service SP, port de lecture binaire et réponse HTTP streaming.
- Scénario BDD:
  - Given un SourceDocument enregistré avec un original immuable
  - When le client demande son contenu par le `DocumentId` public
  - Then l'API restitue exactement le PDF enregistré avec son type public sans exposer ni accepter de référence de stockage
- Tests d'acceptation à écrire: `uv run --locked gate`, couvrant contenu, hash, document absent et identifiant invalide.
- Tests unitaires à écrire: `uv run --locked gate`, couvrant résolution interne, taille, en-têtes, streaming et refus de chemins.
- Implémentation attendue: ajouter le port SP de lecture de l'original et une réponse streaming `application/pdf` avec nom public neutralisé.
- Invariants et garde-fous: `Content-Disposition` ne reprend aucun chemin; pas de lecture hors `corpus_root`; échec explicite si le hash stocké ne correspond pas.
- Dépendances: T-005; T-007; ADR-018; DDD-ADR-003.
- Commandes de validation:
  - `uv run --locked gate`
  - `uv run --locked gate`
  - `uv run --locked gate`
- Commit RED: `test(sp): couvrir recuperation pdf original`.
- Commit GREEN: `feat(sp): servir pdf original controle`.
