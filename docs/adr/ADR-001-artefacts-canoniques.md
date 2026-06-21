# ADR-001 - Artefacts canoniques

**Statut :** Acceptée
**Date :** 2026-06-21
**Décideurs :** Propriétaire du projet
**Remplace :** Aucun
**Remplacée par :** Aucune
**Source :** `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, section 3, ADR-001

## Contexte

Le système manipule des PDF financiers hétérogènes. Les usages aval ont besoin d'une représentation structurée pour chunker, indexer, citer et vérifier, mais la référence visuelle et éditoriale reste le PDF original.

## Décision

Pour chaque document, les artefacts faisant autorité sont le PDF original immuable et le `DoclingDocument` sérialisé en JSON.

Les exports Markdown, HTML, texte ou images sont des artefacts dérivés et régénérables. Ils NE DOIVENT PAS être traités comme source de vérité.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| PDF original seul | Rejetée | Insuffisant pour la recherche structurée et la provenance fine. |
| Markdown exporté comme canonique | Rejetée | Perd trop d'information de structure, de coordonnées et de provenance. |
| PDF original et Docling JSON | Retenue | Préserve la référence visuelle et fournit une structure exploitable. |

## Conséquences

### Positives

- Les citations peuvent rester reliées au PDF original.
- Les projections de recherche peuvent être régénérées.
- Les versions canoniques deviennent auditables.

### Négatives ou coûts

- Le stockage doit conserver au moins deux artefacts par version canonique.
- Les contrôles qualité doivent vérifier la cohérence PDF vers JSON.

### Risques et contrôles

- Risque: une exportation dérivée devient utilisée comme vérité. Contrôle: tests et documentation interdisant cette dépendance.

## Impact d'implémentation

- Modules concernés: `source_processing`, `knowledge_access`.
- Configuration concernée: stockage du corpus et des artefacts canoniques.
- Tests attendus: acceptation de version canonique, absence d'omission de page, résolvabilité des localisateurs.
- Milestones concernées: M-004, M-005.

## Liens de traçabilité

- Spécification: sections 3, 5, 6 et 21.
- Plan d'implémentation: M-004, M-005.
- Tests d'acceptation: publication de version canonique et recherche traçable.
- Commits: à renseigner lors de l'implémentation.
