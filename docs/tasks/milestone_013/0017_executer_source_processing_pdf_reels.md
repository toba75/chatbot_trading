# T-017 - Exécuter réellement Source Processing sur les PDF

## Milestone

- Nom: M-013 - Durcissement et acceptation V1, tranche `M13-remediation`.
- Source: `docs/specs/plan_remediation_m13.md`, bounded context `source_processing`, ADR de routes documentaires et exigences de qualité documentaire V1.
- Objectif métier: prouver que des PDF originaux réels deviennent des versions canoniques traçables, contrôlées page par page.

## Contexte DDD

- Domaine: assistant personnel de trading et d'investissement fondé sur preuves.
- Bounded context: `source_processing`.
- Objectif métier: transformer des PDF réels en artefacts canoniques utilisables par la recherche, sans omission silencieuse de page ni conversion fixture.
- Langage ubiquitaire: `SourceDocument`, PDF original immuable, diagnostic page par page, route documentaire, Docling, Granite-Docling, OCRmyPDF, version canonique, quarantaine.
- Invariants critiques: chaque page reçoit une route explicite; chaque artefact canonique remonte à l'original; une page non traitable part en quarantaine explicite; la pagination d'origine reste traçable.
- Garde-fous: pas de route par défaut; pas d'OCR global; pas de page ignorée; pas de conversion fixture; pas de succès si l'outil réel requis est absent.

## Blocages Ou Préconditions

- État GREEN/RED connu: T-015 et T-016 doivent déclarer le corpus et les questions réelles; les validations M-013 existantes ne prouvent pas le traitement de PDF réels.
- Présence des milestones amont dans master: M-003 à M-013 sont présents dans `master`; les contrats SP antérieurs doivent être consommés sans contournement.
- Décisions manquantes: créer une ADR seulement si une nouvelle route documentaire ou un nouveau mode de quarantaine durable est introduit.
- Risques: outils Docling, Granite-Docling ou OCRmyPDF indisponibles; temps de conversion long; pages omises; artefacts canoniques non hashés; confusion entre diagnostic et acceptation qualité.

## Tâches

### T-017 - Exécuter réellement Source Processing sur les PDF

- But métier: prouver que les PDF réels deviennent des versions canoniques traçables.
- Portée DDD: SP, `SourceDocument`, diagnostic, route de page, artefacts Docling, contrôle qualité et quarantaine explicite.
- Scénario BDD:
  - Given un PDF réel du manifeste.
  - When le pipeline SP le traite.
  - Then chaque page reçoit une route explicite, un artefact canonique ou une quarantaine, et la pagination d'origine reste traçable.
- Tests d'acceptation à écrire: `tests/m013/validate_real_source_processing_acceptance.ps1`.
- Tests unitaires à écrire: original modifié, page omise, route absente, Docling JSON absent, OCRmyPDF appliqué sans condition, quarantaine non explicite, hash canonique absent, outil requis indisponible masqué.
- Implémentation attendue: brancher le runtime local sur les vrais adaptateurs Docling, Granite-Docling et OCRmyPDF conditionnel, ou échouer explicitement si l'outil requis par la route déclarée est absent.
- Invariants et garde-fous: pas de conversion fixture; pas de page ignorée; pas de route par défaut; pas d'OCR global; aucun statut GREEN sans PDF local résolvable.
- Dépendances: T-015, T-016, ADR de routes documentaires, contrats SP existants.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_real_source_processing_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_task_system.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m013): couvrir traitement pdf reel`
- Commit GREEN: `feat(m013): traiter corpus pdf reel`
