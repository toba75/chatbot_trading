# T-008 - Exposer les commandes documentaires SP

## Milestone
- Nom: M-003 - Source enregistrée, diagnostiquée et routée.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, endpoints M-003, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, section 17.
- Objectif métier: permettre à un utilisateur ou à un worker de demander l'enregistrement et le diagnostic d'une source sans contourner le domaine SP.

## Contexte DDD
- Domaine: interface applicative du traitement des sources.
- Bounded context: `SP`.
- Objectif métier: exposer les commandes métier `RegisterSourceDocument` et `StartDocumentProcessing` avec erreurs explicites et contrat stable.
- Langage ubiquitaire: `POST /v1/documents`, `POST /v1/documents/{id}/diagnose`, commande applicative, réponse d'acceptation, statut de document, diagnostic demandé.
- Invariants critiques: l'adaptateur HTTP ne décide pas la route; le domaine ne dépend pas du framework; une erreur métier n'est pas transformée en succès partiel.
- Garde-fous: pas de fallback vers conversion; pas d'identifiant technique exposé comme identité métier; pas de catch générique qui masque une erreur SP.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-001 à T-007 doivent être GREEN.
- Présence des milestones amont dans master: M-000, M-001 et M-002 sont présents dans `master`.
- Décisions manquantes: une ADR est requise seulement si une nouvelle frontière de service ou un protocole public structurant est introduit au-delà des endpoints indicatifs déjà spécifiés.
- Risques: coupler SP à FastAPI avant le contrat applicatif; remplacer les endpoints requis par une CLI; lancer un traitement asynchrone sans job idempotent M-002; retourner une réponse acceptée alors que la source est en revue.

## Tâches
### T-008 - Exposer les commandes documentaires SP
- But métier: rendre l'ajout et le diagnostic de source déclenchables par une interface contrôlée et auditable.
- Portée DDD: handlers applicatifs SP, ports de stockage, intégration au runtime de jobs M-002 si nécessaire, adaptateur HTTP mince pour `POST /v1/documents` et `POST /v1/documents/{id}/diagnose`.
- Scénario BDD:
  - Given un client soumet un PDF original puis demande son diagnostic.
  - When les commandes documentaires SP sont appelées.
  - Then l'enregistrement retourne une identité de document stable et le diagnostic retourne un statut explicite sans exposer de structure interne ni lancer de conversion.
- Tests d'acceptation à écrire: un test `tests/m003/validate_document_commands_acceptance.ps1` couvrant les deux endpoints HTTP requis, les erreurs de source inconnue, source illisible, diagnostic déjà demandé et absence de conversion.
- Tests unitaires à écrire: tests des handlers applicatifs, mapping d'erreurs métier, idempotence contrôlée de demande de diagnostic et absence d'import de framework dans `app/source_processing/domain`.
- Implémentation attendue: créer la surface HTTP SP, connecter les handlers au runtime local existant et garder l'adaptateur de transport hors du domaine; une CLI ne peut être ajoutée qu'en complément, jamais comme substitut aux endpoints M-003.
- Invariants et garde-fous: aucune décision de routage dans l'adaptateur; aucune conversion M-004 déclenchée; aucune erreur métier avalée; aucun import framework dans le domaine.
- Dépendances: T-007; M-002 job runtime; `app/platform/job_runtime`; `app/source_processing/application`; `scripts/validate_architecture_boundaries.ps1`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m003\validate_document_commands_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m003\validate_document_commands_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m003\validate_document_http_contract_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_architecture_boundaries.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m003): couvrir les commandes documentaires sp`.
- Commit GREEN: `feat(m003): exposer les commandes documentaires sp`.
