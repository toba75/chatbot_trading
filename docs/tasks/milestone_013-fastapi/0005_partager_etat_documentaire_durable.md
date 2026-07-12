# T-005 - Partager un état documentaire durable

## Milestone

- Nom: M13-FastAPI - API orchestratrice ASGI raccordée.
- Source: contrats de repository M-003/M-004, topologie M-002 et ADR-018.
- Objectif métier: permettre à l'API et aux workers d'observer le même état documentaire après redémarrage.

## Contexte DDD

- Domaine: traitement des sources et exécution locale.
- Bounded contexts: SP propriétaire des sources, tentatives et conversions; `platform` propriétaire de l'exécution des jobs.
- Objectif métier: conserver l'original immuable et les transitions documentaires sans état privé au processus HTTP.
- Langage ubiquitaire: SourceDocument, DocumentProcessingRun, demande de conversion, job, original immuable.
- Invariants critiques: un `DocumentId` retrouve le même original et le même état depuis l'API et le worker; les transitions sont atomiques.
- Garde-fous: aucun repository en mémoire dans le runtime; aucun fichier JSON parallèle utilisé comme base métier; aucun chemin interne exposé.

## Blocages Ou Préconditions

- T-004 GREEN.
- PostgreSQL et le stockage de corpus configurés par M-002/M13-config doivent être accessibles aux processus concernés.
- Décision de persistance existante à confirmer; créer une ADR dédiée seulement si les contrats actuels ne déterminent pas le partage PostgreSQL/corpus.
- Risque: déclarer la commande raccordée alors que la file de jobs reste privée au processus API.

## Tâches

### T-005 - Partager un état documentaire durable

- But métier: fournir les adaptateurs réels nécessaires aux cas d'usage d'enregistrement, diagnostic et conversion.
- Portée DDD: implémentations des ports SP, stockage immuable du PDF, transaction de soumission de job et migrations locales.
- Scénario BDD:
  - Given un PDF enregistré et une demande de diagnostic acceptée par l'API
  - When un nouveau processus API ou worker relit le même stockage configuré
  - Then il retrouve la source, le manifeste, le statut et le job sans reconstruction ni état en mémoire partagé
- Tests d'acceptation à écrire: `tests/m013_fastapi/validate_document_persistence_restart_acceptance.ps1`, couvrant enregistrement, redémarrage logique, relecture et job visible par un second processus.
- Tests unitaires à écrire: `tests/m013_fastapi/validate_document_persistence_unit.ps1`, couvrant idempotence, doublon binaire, transaction job/processing run, concurrence et original bit à bit.
- Implémentation attendue: implémenter les ports SP sur le PostgreSQL local configuré, conserver les PDF sous `corpus_root`, ajouter les migrations et partager la file de jobs persistante avec `worker-documents`.
- Invariants et garde-fous: pas de fallback vers `InMemoryJobQueue`; échec atomique si état ou job ne peut être persisté; hash vérifié à la restitution; secrets lus uniquement par la configuration autorisée.
- Dépendances: T-004; M-002; M-003; M-004; M13-config.
- Commandes de validation:
  - `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_fastapi\validate_document_persistence_restart_acceptance.ps1`
  - `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_fastapi\validate_document_persistence_unit.ps1`
  - `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_local_compose.ps1`
- Commit RED: `test(sp): couvrir persistance documentaire partagee`.
- Commit GREEN: `feat(sp): persister etat documentaire partage`.
