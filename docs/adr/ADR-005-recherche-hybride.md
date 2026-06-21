# ADR-005 - Recherche hybride

**Statut :** Acceptée
**Date :** 2026-06-21
**Décideurs :** Propriétaire du projet
**Remplace :** Aucun
**Remplacée par :** Aucune
**Source :** `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 3 et 6

## Contexte

Les questions de recherche financière nécessitent de retrouver concepts, termes exacts, chiffres, auteurs, périodes et passages multilingues. Une seule méthode de recherche ne couvre pas ces besoins.

## Décision

La recherche DOIT combiner recherche dense, recherche sparse ou BM25, filtres de métadonnées, fusion, reranking, diversification et expansion vers fragments parents.

Les détails Qdrant restent derrière le port `SearchKnowledge`. Les consommateurs NE DOIVENT PAS dépendre directement des collections Qdrant.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Recherche dense seule | Rejetée | Moins fiable sur termes exacts, chiffres et auteurs. |
| Recherche lexicale seule | Rejetée | Moins robuste aux reformulations et questions FR vers sources EN. |
| Recherche hybride | Retenue | Combine rappel sémantique et précision lexicale. |

## Conséquences

### Positives

- Le rappel et la précision peuvent être mesurés séparément.
- Les résultats restent filtrables et diversifiables.

### Négatives ou coûts

- Le pipeline d'évaluation est plus exigeant.
- Les projections doivent être versionnées et régénérables.

### Risques et contrôles

- Risque: score hybride interprété comme vérité. Contrôle: KA retourne des preuves candidates, EG/RA décident.

## Impact d'implémentation

- Modules concernés: `knowledge_access`.
- Configuration concernée: embeddings, sparse index, reranker, Qdrant.
- Tests attendus: recherche traçable, filtres, absence de source en quarantaine.
- Milestones concernées: M-005, M-012.

## Liens de traçabilité

- Spécification: sections 3, 6, 20 et 21.
- Plan d'implémentation: M-005.
- Tests d'acceptation: résultat de recherche traçable.
- Commits: à renseigner lors de l'implémentation.
