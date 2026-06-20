# ADR-005 - Recherche hybride

**Statut :** Acceptée  
**Date :** 2026-06-20  
**Décideurs :** Projet chatbot trading  
**Remplace :** Aucun  
**Remplacée par :** Aucune  
**Source :** `docs/specification_pipeline_chatbot_trading_dgx_spark_v3_1.md`, section 3, ADR-005

---

## Contexte

Le chatbot doit répondre à des questions documentaires, retrouver des passages précis, comparer plusieurs sources et citer des pages. Une recherche dense seule peut manquer des termes exacts, tandis qu'une recherche sparse seule peut manquer des reformulations sémantiques.

## Décision

La recherche DOIT combiner :

- recherche dense sémantique ;
- recherche sparse ou BM25 ;
- filtres de métadonnées ;
- reranking ;
- diversification par document et auteur ;
- expansion vers les fragments parents.

Qdrant est retenu comme moteur d'index pour stocker les vecteurs, les métadonnées et permettre les requêtes hybrides.

## Options considérées

| Option | Décision | Raisons |
|---|---|---|
| Recherche dense seule | Rejetée | Risque sur les termes exacts, chiffres, noms propres et expressions techniques. |
| Recherche BM25 seule | Rejetée | Moins robuste aux reformulations et aux requêtes conceptuelles. |
| Recherche hybride avec reranking | Retenue | Meilleur compromis entre rappel, précision et auditabilité. |

## Conséquences

### Positives

- Meilleur rappel sur corpus technique.
- Possibilité de filtrer par auteur, année, type de source ou thème.
- Citations plus robustes grâce au reranking et à l'expansion parent.

### Négatives ou coûts

- Deux familles d'index ou de scores doivent être maintenues.
- L'évaluation retrieval devient obligatoire avant promotion.

### Risques et contrôles

- Risque : pondération dense/sparse mal calibrée.  
  Contrôle : benchmark Recall@k, MRR, nDCG et précision de page.

## Impact d'implémentation

- Modules concernés : `app/chunking/`, `app/indexing/`, `app/retrieval/`, `evaluation/retrieval/`.
- Configuration concernée : `config/models.yaml`, `config/quality_gates.yaml`.
- Tests attendus : recherche dense, recherche sparse, fusion, reranking, filtres et citations.
- Milestones concernées : M4, M5, M8.
