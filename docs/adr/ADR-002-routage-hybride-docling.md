# ADR-002 - Routage hybride Docling

**Statut :** Acceptée  
**Date :** 2026-06-20  
**Décideurs :** Projet chatbot trading  
**Remplace :** Aucun  
**Remplacée par :** Aucune  
**Source :** `docs/specification_pipeline_chatbot_trading_dgx_spark_v3_1.md`, section 3, ADR-002

---

## Contexte

Le corpus contient des PDF numériques propres, des scans, des documents mixtes, des pages avec tableaux, graphiques et structures complexes. Un unique pipeline appliqué à tous les documents produirait des erreurs ou des coûts inutiles.

## Décision

Le pipeline documentaire DOIT employer deux modes principaux :

```text
PDF numérique avec texte natif fiable
-> pipeline Docling standard

Page image, scan ou structure visuelle nécessitant une conversion end-to-end
-> pipeline VLM Docling avec Granite-Docling
```

Le routage peut être effectué page par page lorsque le document est mixte.

## Options considérées

| Option | Décision | Raisons |
|---|---|---|
| Docling standard pour tout le corpus | Rejetée | Insuffisant pour les scans et certaines pages visuelles. |
| Granite-Docling pour tout le corpus | Rejetée | Coût inutile et risque de dégrader du texte natif fiable. |
| Routage hybride | Retenue | Adapte le traitement à l'état réel de chaque page. |

## Conséquences

### Positives

- Meilleure qualité sur documents hétérogènes.
- Coût VLM limité aux pages qui en ont besoin.
- Possibilité de traiter correctement les documents mixtes.

### Négatives ou coûts

- Le diagnostic page par page devient obligatoire.
- La fusion pagewise doit préserver la pagination et la provenance.

### Risques et contrôles

- Risque : route incorrecte.  
  Contrôle : seuils calibrés, statut de revue explicite si confiance insuffisante.

## Impact d'implémentation

- Modules concernés : `app/diagnostics/`, `app/routing/`, `app/conversion/`, `app/quality/`.
- Configuration concernée : `config/routing.yaml`, `config/docling_profiles.yaml`.
- Tests attendus : routage par page, documents mixtes, absence de fallback silencieux.
- Milestones concernées : M2, M3, M8.
