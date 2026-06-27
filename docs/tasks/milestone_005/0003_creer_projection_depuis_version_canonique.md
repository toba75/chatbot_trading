# T-003 - Créer une projection depuis une version canonique publiée

## Milestone
- Nom: M-005 - Projection de connaissance recherchable.
- Source: livrables M-005 `KnowledgeProjection`, projection reconstruisible, source en quarantaine non indexable et endpoint KA `POST /v1/documents/{document_id}/index`.
- Objectif métier: transformer une version canonique publiée en demande de projection KA sans modifier la source documentaire.

## Contexte DDD
- Domaine: accès aux connaissances.
- Bounded context: KA.
- Objectif métier: établir le cycle de vie `KnowledgeProjection` pour une version canonique, un profil de chunking, un modèle d'embedding, un profil sparse et un schéma d'index.
- Langage ubiquitaire: `ProjectionId`, `CanonicalVersionId`, `BuildFingerprint`, `ProjectionStatus`, `RequestKnowledgeProjection`, `POST /v1/documents/{document_id}/index`, `REQUESTED`, `BUILDING`, `SEARCHABLE`, `STALE`, `FAILED`, `RETIRED`.
- Invariants critiques: une projection ne peut être construite que depuis une version canonique publiée; une source en quarantaine ou refusée est non indexable; supprimer une projection ne supprime jamais la source canonique.
- Garde-fous: aucun accès aux tables internes SP; aucune mutation de `CanonicalSource`; aucune reconstruction implicite sans empreinte de build explicite; aucune indexation déclenchée depuis un endpoint SP.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-001 et T-002 doivent être GREEN.
- Présence des milestones amont dans master: M-004 fournit `CanonicalSourcePublished` et `CanonicalSourceRef`.
- Décisions manquantes: aucune si les événements M-004 sont consommés en cohérence éventuelle via outbox idempotente.
- Risques: dupliquer des projections identiques; indexer une version supersédée sans statut explicite; démarrer une projection sur une source non publiée.

## Tâches
### T-003 - Créer une projection depuis une version canonique publiée
- But métier: permettre à KA de déclarer une projection reconstruisible pour une version canonique précise.
- Portée DDD: agrégat `KnowledgeProjection`, politique d'éligibilité, repository KA, commande applicative `RequestKnowledgeProjection`, contrat HTTP KA `POST /v1/documents/{document_id}/index`, consommation idempotente de `CanonicalSourcePublished` et transitions d'état initiales.
- Scénario BDD:
  - Given une `CanonicalSource` publiée et non mise en quarantaine.
  - When KA reçoit `POST /v1/documents/{document_id}/index` avec un profil d'indexation explicite.
  - Then une `KnowledgeProjection` `REQUESTED` est créée avec une empreinte de build unique et aucune donnée canonique n'est modifiée.
- Tests d'acceptation à écrire: `tests/m005/validate_knowledge_projection_acceptance.ps1`, couvrant création depuis version publiée, refus source en quarantaine, idempotence, absence de mutation SP et contrat HTTP `POST /v1/documents/{document_id}/index`.
- Tests unitaires à écrire: tests de `KnowledgeProjection`, `ProjectionEligibilityPolicy`, calcul de `BuildFingerprint`, transitions autorisées, repository en mémoire, mapping des erreurs publiques d'indexation et refus de corps ambigu.
- Implémentation attendue: créer `app/knowledge_access/domain/knowledge_projection.py`, `app/knowledge_access/application/request_projection.py`, l'adaptateur HTTP d'indexation KA, les ports de lecture canonique et un repository KA minimal.
- Invariants et garde-fous: pas de projection sans `CanonicalVersionId`; pas de valeurs par défaut pour profils; pas de transition directe vers `SEARCHABLE`; pas de `202` si la source n'est pas canonique; pas de try/catch masquant un refus métier.
- Dépendances: T-002; `app/contracts/source_references.py`; événements M-004; outbox M-002; DDD-ADR-004; DDD-ADR-008.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m005\validate_knowledge_projection_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m005\validate_knowledge_projection_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m005\validate_index_command_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_architecture_boundaries.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m005): couvrir la creation de projection`
- Commit GREEN: `feat(m005): creer la projection depuis source canonique`
