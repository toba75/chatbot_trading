# T-009 - Lire la projection de connaissance

## Milestone

- Nom: M13-FastAPI - API orchestratrice ASGI raccordée.
- Source: spécification M-005, DDD-ADR-004, ADR-018 et `docs/specs/ui.md`.
- Objectif métier: rendre inspectable l'état KA d'un document sans exposer Qdrant ni transformer une recherche en preuve.

## Contexte DDD

- Domaine: accès aux connaissances.
- Bounded context: KA.
- Objectif métier: publier l'identité, l'état, le profil et les sorties bornées de la projection courante.
- Langage ubiquitaire: KnowledgeProjection, projection_id, version canonique, profil, chunk_count, fraîcheur.
- Invariants critiques: Qdrant reste une projection régénérable; seul KA interprète ses états.
- Garde-fous: aucun accès direct du routeur ou de l'UI à une collection, un point ou une recherche libre.

## Blocages Ou Préconditions

- T-007 GREEN; T-008 peut être exécutée indépendamment avant cette tâche.
- Le read-model KA doit lire la source de vérité de projection, pas déduire l'état de la présence d'une collection Qdrant.
- Risque: retourner `SEARCHABLE` sur la seule présence de chunks.

## Tâches

### T-009 - Lire la projection de connaissance

- But métier: publier `GET /v1/documents/{document_id}/projection` avec les sorties publiques KA nécessaires au jugement utilisateur.
- Portée DDD: query service KA, port de lecture de projection et DTO public consommé par l'API orchestratrice.
- Scénario BDD:
  - Given un document possède ou non une KnowledgeProjection publiée par KA
  - When le client lit la projection par le DocumentId
  - Then KA retourne son état réel, son profil, sa fraîcheur et ses sorties bornées sans exposer son stockage technique
- Tests d'acceptation à écrire: `tests/m013_fastapi/validate_projection_read_model_acceptance.ps1`, couvrant absence, build, searchable, stale et failed.
- Tests unitaires à écrire: `tests/m013_fastapi/validate_projection_queries_unit.ps1`, couvrant mapping d'état, version canonique, `chunk_count`, échantillons bornés et SourceLocator.
- Implémentation attendue: ajouter un query service KA et injecter son port dans le routeur documentaire de l'API orchestratrice.
- Invariants et garde-fous: `PROJECTION_NOT_REQUESTED` vient de l'absence réelle; `SEARCHABLE` vient de l'agrégat KA; `qdrant_collection` et identifiants de points sont interdits.
- Dépendances: T-007; M-005; DDD-ADR-004; ADR-018.
- Commandes de validation:
  - `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_fastapi\validate_projection_read_model_acceptance.ps1`
  - `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_fastapi\validate_projection_queries_unit.ps1`
  - `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_architecture_boundaries.ps1`
- Commit RED: `test(ka): couvrir lecture projection documentaire`.
- Commit GREEN: `feat(ka): publier read model projection`.
