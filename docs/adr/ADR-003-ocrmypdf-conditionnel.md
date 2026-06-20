# ADR-003 - OCRmyPDF conditionnel

**Statut :** Acceptée  
**Date :** 2026-06-20  
**Décideurs :** Projet chatbot trading  
**Remplace :** Aucun  
**Remplacée par :** Aucune  
**Source :** `docs/specification_pipeline_chatbot_trading_dgx_spark_v3_1.md`, section 3, ADR-003

---

## Contexte

Certains PDF scannés peuvent nécessiter une correction physique avant conversion : rotation, redressement, nettoyage prudent ou réparation exceptionnelle d'une couche OCR. Appliquer OCRmyPDF à tout le corpus introduirait des transcriptions concurrentes et des transformations inutiles.

## Décision

OCRmyPDF NE DOIT PAS être appliqué à tous les PDF.

Il intervient uniquement comme outil de correction physique des scans lorsque nécessaire :

- rotation ;
- redressement ;
- préparation d'une image très dégradée ;
- nettoyage prudent ;
- réparation exceptionnelle d'une couche OCR.

Sa sortie n'est pas le format final du système. Le format final reste le `DoclingDocument`.

## Options considérées

| Option | Décision | Raisons |
|---|---|---|
| OCRmyPDF systématique | Rejetée | Contredit le principe d'autorité textuelle unique et peut dégrader des PDF natifs. |
| Aucun OCR amont | Rejetée | Ne permet pas de corriger certains scans dégradés. |
| OCRmyPDF conditionnel | Retenue | Limite l'usage aux cas où il améliore la conversion physique. |

## Conséquences

### Positives

- Réduction du risque de double OCR.
- Préservation des PDF numériques fiables.
- Meilleure qualité possible sur scans dégradés.

### Négatives ou coûts

- Le diagnostic doit identifier les cas qui justifient le prétraitement.
- Les artefacts préparés doivent être hashés et tracés.

### Risques et contrôles

- Risque : nettoyage destructif.  
  Contrôle : configuration prudente et interdiction des transformations non justifiées.

## Impact d'implémentation

- Modules concernés : `app/diagnostics/`, `app/routing/`, `app/conversion/`, `app/quality/`.
- Configuration concernée : `config/routing.yaml`, `config/docling_profiles.yaml`.
- Tests attendus : scans inclinés, scans bruités, PDF natifs non modifiés.
- Milestones concernées : M2, M3, M8.
