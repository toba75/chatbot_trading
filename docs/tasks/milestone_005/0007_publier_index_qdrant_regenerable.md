# T-007 - Publier un index Qdrant régénérable

## Milestone
- Nom: M-005 - Projection de connaissance recherchable.
- Source: livrables M-005 collection Qdrant régénérable, projection reconstruisible, événements KA et absence d'accès direct de RA à Qdrant.
- Objectif métier: matérialiser la projection KA dans un index technique supprimable et reconstruisible.

## Contexte DDD
- Domaine: accès aux connaissances.
- Bounded context: KA.
- Objectif métier: publier une projection `SEARCHABLE` dans un index Qdrant derrière un port stable.
- Langage ubiquitaire: `VectorIndex`, collection, point de projection, schéma d'index, régénération, `KnowledgeProjectionBuilt`, `KnowledgeProjectionBecameSearchable`, `KnowledgeProjectionFailed`, `SEARCHABLE`, `STALE`, `RETIRED`.
- Invariants critiques: Qdrant n'est pas source de vérité; la reconstruction depuis la version canonique et les profils doit reproduire l'identité de build; RA et EG ne lisent jamais Qdrant directement.
- Garde-fous: pas de suppression de source canonique lors d'une suppression d'index; pas de collection publique; pas de statut `SEARCHABLE` tant que tous les points attendus ne sont pas publiés; pas d'événement `KnowledgeProjectionBecameSearchable` avant statut réellement searchable.

## Blocages Ou Préconditions
- État GREEN/RED connu: encodage dense et sparse complet après T-006.
- Présence des milestones amont dans master: M-002 fournit la topologie Qdrant locale; M-004 fournit la source canonique.
- Décisions manquantes: aucune si Qdrant reste un adaptateur KA interne.
- Risques: index partiel marqué searchable; schéma d'index non versionné; accès direct depuis RA contournant `KnowledgeSearchPort`.

## Tâches
### T-007 - Publier un index Qdrant régénérable
- But métier: rendre une projection interrogeable tout en gardant la source de vérité dans SP.
- Portée DDD: port `VectorIndex`, adaptateur Qdrant, schéma d'index versionné, publication atomique de projection, événements KA via outbox et reconstruction idempotente.
- Scénario BDD:
  - Given une projection encodée avec tous ses chunks attendus.
  - When KA publie l'index technique.
  - Then la projection devient `SEARCHABLE` et publie `KnowledgeProjectionBecameSearchable` seulement si l'index contient tous les points versionnés et peut être reconstruit depuis les mêmes entrées.
- Tests d'acceptation à écrire: `tests/m005/validate_qdrant_projection_acceptance.ps1`, couvrant publication complète, reconstruction, suppression sans perte canonique, événement `KnowledgeProjectionBecameSearchable`, événement `KnowledgeProjectionFailed` sur échec et absence d'accès direct RA.
- Tests unitaires à écrire: tests de `VectorIndex`, adaptateur en mémoire, transitions `BUILDING` vers `SEARCHABLE`, `FAILED`, `STALE` et `RETIRED`, détection d'index partiel, payload public des événements KA et idempotence outbox.
- Implémentation attendue: créer l'adaptateur Qdrant derrière `VectorIndex`, un service de publication d'index, le producteur d'événements KA et les règles d'import interdisant RA/EG vers Qdrant.
- Invariants et garde-fous: aucun statut `SEARCHABLE` partiel; aucun événement de succès avant publication complète; aucun client Qdrant dans RA ou EG; aucune donnée de claim dans la collection documentaire; aucun fallback vers une recherche en mémoire non déclarée.
- Dépendances: T-006; ADR-005; DDD-ADR-004; DDD-ADR-008; `scripts/validate_architecture_boundaries.ps1`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m005\validate_qdrant_projection_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m005\validate_qdrant_projection_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m005\validate_knowledge_projection_events_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_architecture_boundaries.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m005): couvrir l index qdrant regenerable`
- Commit GREEN: `feat(m005): publier l index qdrant regenerable`
