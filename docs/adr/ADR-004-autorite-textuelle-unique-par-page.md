# ADR-004 - Autorité textuelle unique par page

**Statut :** Acceptée  
**Date :** 2026-06-20  
**Décideurs :** Projet chatbot trading  
**Remplace :** Aucun  
**Remplacée par :** Aucune  
**Source :** `docs/specification_pipeline_chatbot_trading_dgx_spark_v3_1.md`, section 3, ADR-004

---

## Contexte

Une même page peut disposer de plusieurs transcriptions possibles : texte natif du PDF, sortie VLM, sortie OCR amont ou ancienne couche OCR. Mélanger ces transcriptions sans protocole explicite rendrait les citations et les vérifications non auditables.

## Décision

Chaque page DOIT avoir une seule autorité textuelle :

- texte natif du PDF ;
- sortie Granite-Docling ;
- sortie d'un OCR amont explicitement retenu.

Le système NE DOIT PAS fusionner silencieusement plusieurs transcriptions concurrentes.

## Options considérées

| Option | Décision | Raisons |
|---|---|---|
| Fusion silencieuse des transcriptions | Rejetée | Rend la provenance non fiable. |
| Choix d'une autorité unique par document | Rejetée | Trop grossier pour les documents mixtes. |
| Autorité unique par page | Retenue | Compatible avec les documents mixtes et l'audit page par page. |

## Conséquences

### Positives

- La provenance textuelle reste claire.
- Les erreurs peuvent être isolées par page.
- Les citations restent vérifiables.

### Négatives ou coûts

- La fusion pagewise doit conserver l'autorité retenue.
- Les cas ambigus doivent passer en revue ou adjudication explicite.

### Risques et contrôles

- Risque : perte d'information utile dans une autre transcription.  
  Contrôle : enrichissement ciblé ou adjudication explicite, jamais fusion silencieuse.

## Impact d'implémentation

- Modules concernés : `app/routing/`, `app/conversion/`, `app/quality/`, `app/retrieval/`.
- Configuration concernée : `config/routing.yaml`, `config/quality_gates.yaml`.
- Tests attendus : une seule autorité par page, absence de doublons silencieux, traçabilité `text_authority`.
- Milestones concernées : M2, M3, M5.
