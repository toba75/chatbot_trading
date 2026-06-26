# T-005 - Diagnostiquer chaque page de la source

## Milestone
- Nom: M-003 - Source enregistrée, diagnostiquée et routée.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, scénario directeur M-003, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, phase 1 de diagnostic page par page.
- Objectif métier: classer chaque page pour préparer une route explicite et auditable.

## Contexte DDD
- Domaine: diagnostic documentaire.
- Bounded context: `SP`.
- Objectif métier: transformer des signaux techniques inspectés en états de page métier utilisés par la politique de routage.
- Langage ubiquitaire: diagnostic de page, `PageDecision`, `NATIVE_OK`, `NATIVE_SUSPECT`, `SCAN_CLEAN`, `SCAN_DEGRADED`, `OCR_BAD`, `MIXED_CONTENT`, `COMPLEX_VISUAL`, `UNSUPPORTED_OR_CORRUPT`.
- Invariants critiques: chaque page reçoit un état ou le document passe en revue explicite; les signaux techniques sont conservés avec la version de diagnostic; une page corrompue n'est pas routée implicitement.
- Garde-fous: pas de classification par défaut; pas de seuil implicite; pas d'appel direct à Docling ou Granite depuis le domaine.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-001 à T-004 doivent être GREEN.
- Présence des milestones amont dans master: M-000, M-001 et M-002 sont présents dans `master`.
- Décisions manquantes: aucune si les états de page restent ceux de la spécification M-003; une ADR est requise si de nouveaux états changent la politique de routage acceptée.
- Risques: perdre les signaux qui justifient une décision; classer une page inconnue comme native fiable; diagnostiquer un manifeste incomplet.

## Tâches
### T-005 - Diagnostiquer chaque page de la source
- But métier: rendre chaque décision de routage justifiable par un état de page explicite.
- Portée DDD: commande `RecordPageDiagnostics`, entité `PageDecision`, objets-valeur de signaux diagnostiques et transition de tentative vers `DIAGNOSED`.
- Scénario BDD:
  - Given un manifeste complet contient des pages natives, scannées et corrompues.
  - When les diagnostics de pages sont enregistrés.
  - Then chaque page reçoit un état diagnostique explicite avec justification, ou la tentative est marquée pour revue sans route implicite.
- Tests d'acceptation à écrire: un test `tests/m003/validate_page_diagnostics_acceptance.ps1` couvrant les états principaux, la page corrompue, la page non diagnostiquée et la conservation de la version de diagnostic.
- Tests unitaires à écrire: tests de classification des signaux, validation d'exhaustivité du diagnostic, refus d'état inconnu et transition interdite depuis un run non créé.
- Implémentation attendue: implémenter l'enregistrement de diagnostics page par page, les types de signaux nécessaires et les erreurs explicites de diagnostic incomplet.
- Invariants et garde-fous: un diagnostic absent bloque le routage; un état inconnu est refusé; la version de politique est obligatoire; aucun état par défaut n'est appliqué.
- Dépendances: T-004; `DocumentInspector`; `DocumentProcessingRun`; `PageDecision`; `ModelVersion` ou version de diagnostic équivalente.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m003\validate_page_diagnostics_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m003\validate_page_diagnostics_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m003): couvrir le diagnostic des pages source`.
- Commit GREEN: `feat(m003): diagnostiquer les pages source`.
