# T-010 - Brancher l'UI sur l'API orchestratrice

## Milestone

- Nom: M13-FastAPI - API orchestratrice ASGI raccordée.
- Source: ADR-018, `docs/specs/ui.md` et contrats livrés par T-006 à T-009.
- Objectif métier: permettre à l'utilisateur de gérer et inspecter le corpus sans chemin d'exécution parallèle.

## Contexte DDD

- Domaine: interface utilisateur locale fondée sur preuves.
- Bounded contexts propriétaires: SP et KA; UI reste un client sans stockage métier.
- Objectif métier: lister, enregistrer, diagnostiquer et inspecter un PDF par les mêmes contrats que tout client public.
- Langage ubiquitaire: corpus PDF, diagnostic, conversion, projection, PDF original.
- Invariants critiques: toute donnée affichée provient de `orchestrator-api`; l'UI ne décide aucun état métier.
- Garde-fous: aucun mock, stub, fixture, état local documentaire ou lecture de fichier dans le runtime UI.

## Blocages Ou Préconditions

- T-006 à T-009 GREEN.
- Les erreurs publiques doivent être stabilisées avant le branchement UI.
- Risque: conserver l'ancien écran bloqué tout en ajoutant un second chemin client non gouverné.

## Tâches

### T-010 - Brancher l'UI sur l'API orchestratrice

- But métier: rendre opérationnels l'écran corpus, le bouton Diagnostiquer, les lectures d'étapes et le visualiseur PDF.
- Portée DDD: client HTTP UI, mapping des DTO publics et états d'affichage; aucune logique SP/KA.
- Scénario BDD:
  - Given l'API orchestratrice est prête et expose les contrats documentaires raccordés
  - When l'utilisateur ouvre le corpus, ajoute un PDF, lance le diagnostic ou inspecte une étape
  - Then l'UI appelle exclusivement ces contrats et affiche leurs sorties ou leur erreur publique sans comportement alternatif
- Tests d'acceptation à écrire: `tests/m013_fastapi/validate_ui_orchestrator_document_flow_acceptance.ps1`, couvrant le trajet HTTP réel UI/API et les états succès/erreur.
- Tests unitaires à écrire: `tests/m013_fastapi/validate_ui_document_api_client_unit.ps1`, couvrant URL relative publique, parsing strict, absence de données internes et affichage des indisponibilités.
- Implémentation attendue: remplacer `build_unconnected_corpus_pdf_state` et les réponses 503 codées en dur par un client des routes `/v1/documents`; conserver le blocage explicite seulement pour une erreur réellement retournée.
- Invariants et garde-fous: aucune importation de repository/cas d'usage dans l'UI; aucun cache métier; aucun fallback vers `data/corpus`; bouton Diagnostiquer visible seulement pour `DIAGNOSTIC_NOT_REQUESTED`.
- Dépendances: T-006, T-007, T-008, T-009; ADR-018; UI-015.
- Commandes de validation:
  - `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_fastapi\validate_ui_orchestrator_document_flow_acceptance.ps1`
  - `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_fastapi\validate_ui_document_api_client_unit.ps1`
  - `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_ui_corpus_backend_connection_acceptance.ps1`
  - `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_ui_pdf_viewer_layout_acceptance.ps1`
- Commit RED: `test(ui): couvrir parcours documentaire via orchestrateur`.
- Commit GREEN: `feat(ui): brancher corpus sur api orchestratrice`.
