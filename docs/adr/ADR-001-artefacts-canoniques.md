# ADR-001 - Artefacts canoniques

**Statut :** Acceptée  
**Date :** 2026-06-20  
**Décideurs :** Projet chatbot trading  
**Remplace :** Aucun  
**Remplacée par :** Aucune  
**Source :** `docs/specification_pipeline_chatbot_trading_dgx_spark_v3_1.md`, section 3, ADR-001

---

## Contexte

Le système doit traiter une bibliothèque de PDF consacrés au trading, à l'investissement, à la finance quantitative et à la gestion du risque. Les traitements ultérieurs doivent rester traçables jusqu'au document original.

Le système a besoin d'une source visuelle immuable et d'une représentation structurée exploitable par le chunking, l'indexation, la recherche, les citations et les vérifications.

## Décision

Pour chaque document, les artefacts faisant autorité sont :

```text
PDF original immuable
+
DoclingDocument sérialisé en JSON
```

Le PDF original reste la référence éditoriale et visuelle.

Le `DoclingDocument` constitue la représentation structurée utilisée pour le chunking, l'indexation et la provenance.

Les exports Markdown, HTML, texte ou images sont des artefacts dérivés et régénérables.

## Options considérées

| Option | Décision | Raisons |
|---|---|---|
| PDF original seul | Rejetée | Ne suffit pas pour l'indexation structurée ni pour la provenance fine. |
| Markdown comme format canonique | Rejetée | Perd trop d'information structurelle, visuelle et de provenance. |
| PDF original + DoclingDocument JSON | Retenue | Préserve l'autorité visuelle et fournit une représentation structurée traçable. |

## Conséquences

### Positives

- Les traitements peuvent être audités jusqu'au PDF original.
- Les exports peuvent être régénérés.
- Les citations peuvent s'appuyer sur des éléments structurés.

### Négatives ou coûts

- Le stockage doit conserver à la fois le PDF et le JSON canonique.
- Les migrations de format Docling doivent être versionnées.

### Risques et contrôles

- Risque : divergence entre exports et artefact canonique.  
  Contrôle : ne jamais traiter les exports comme source d'autorité.

## Impact d'implémentation

- Modules concernés : `app/inventory/`, `app/conversion/`, `app/quality/`, `app/chunking/`, `app/indexing/`.
- Configuration concernée : chemins `corpus/raw/`, `corpus/docling/`, `corpus/exports/`.
- Tests attendus : immutabilité des originaux, validité JSON, présence de provenance.
- Milestones concernées : M2, M3, M4, M5.
