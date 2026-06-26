# T-009 - Exposer la commande de conversion documentaire

## Milestone
- Nom: M-004 - Version canonique publiée.
- Source: livrables M-004 du plan v4.1, endpoint `POST /v1/documents/{id}/convert`.
- Objectif métier: permettre à un client ou un worker de demander la conversion canonique d'une source routée sans contourner le domaine SP.

## Contexte DDD
- Domaine: interface applicative du traitement des sources.
- Bounded context: `SP`.
- Objectif métier: exposer la commande métier de conversion et publication avec statuts explicites, erreurs stables et intégration job idempotente.
- Langage ubiquitaire: `POST /v1/documents/{id}/convert`, commande de conversion, job de conversion, statut canonique, source non publiable, conversion acceptée.
- Invariants critiques: seul un document routé et publiable peut être converti; l'adaptateur HTTP ne décide ni route ni autorité; une erreur métier n'est pas transformée en succès partiel.
- Garde-fous: pas de conversion déclenchée depuis `diagnose`; pas de fallback vers une route alternative; pas d'identifiant technique exposé comme identité métier.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-001 à T-008 doivent être GREEN.
- Présence des milestones amont dans master: M-000 à M-003 sont présents dans `master`.
- Décisions manquantes: une ADR est requise seulement si une nouvelle frontière de service ou un protocole public structurant est introduit au-delà de l'endpoint prévu.
- Risques: coupler le domaine à FastAPI; lancer deux conversions pour la même version; masquer une erreur de QA sous un statut accepté.

## Tâches
### T-009 - Exposer la commande de conversion documentaire
- But métier: rendre la publication canonique déclenchable par une interface contrôlée, auditable et idempotente.
- Portée DDD: handler applicatif SP, intégration au runtime de jobs M-002, adaptateur HTTP mince pour `POST /v1/documents/{id}/convert`, mapping d'erreurs métier et statut public.
- Scénario BDD:
  - Given un document enregistré, diagnostiqué et routé.
  - When un client appelle `POST /v1/documents/{id}/convert`.
  - Then la conversion canonique est acceptée comme job idempotent ou refusée avec une erreur explicite sans exposer les structures internes SP.
- Tests d'acceptation à écrire: un test `tests/m004/validate_document_conversion_command_acceptance.ps1` couvrant conversion acceptée, source inconnue, source en quarantaine, route absente, conversion déjà demandée et QA refusée.
- Tests unitaires à écrire: tests du service applicatif, mapping HTTP, idempotence de job, absence d'import framework dans le domaine et absence de conversion depuis l'endpoint de diagnostic M-003.
- Implémentation attendue: créer la commande applicative de conversion, connecter le job runtime, exposer l'adaptateur HTTP et documenter les statuts publics sans fuite d'identifiants internes.
- Invariants et garde-fous: route préalable obligatoire; idempotency key explicite; aucune publication partielle; aucune erreur avalée; aucun import transport dans `app/source_processing/domain`.
- Dépendances: T-008; M-002 job runtime; M-003 commandes documentaires; `app/source_processing/adapters/document_http.py`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m004\validate_document_conversion_command_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m004\validate_document_conversion_command_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m003\validate_document_http_contract_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_architecture_boundaries.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m004): couvrir la commande de conversion documentaire`.
- Commit GREEN: `feat(m004): exposer la commande de conversion documentaire`.
