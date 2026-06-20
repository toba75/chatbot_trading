# ADR-008 - LLM principal servi par vLLM

**Statut :** Acceptée  
**Date :** 2026-06-20  
**Décideurs :** Projet chatbot trading  
**Remplace :** Aucun  
**Remplacée par :** Aucune  
**Source :** `docs/specification_pipeline_chatbot_trading_dgx_spark_v3_1.md`, section 3, ADR-008

---

## Contexte

Le chatbot doit générer des réponses structurées, appeler des outils contraints par schéma JSON, participer à l'extraction d'affirmations et produire des synthèses citées. Le moteur d'inférence doit être local et compatible avec l'architecture DGX Spark.

## Décision

Le moteur d'inférence principal est **vLLM**, avec API locale compatible OpenAI.

Le modèle de référence recommandé au démarrage est :

```text
nvidia/Gemma-4-31B-IT-NVFP4
```

Les modèles candidats à benchmarker sont :

| Statut | Modèle | Rôle |
|---|---|---|
| Référence recommandée | `nvidia/Gemma-4-31B-IT-NVFP4` | Modèle principal officiellement listé pour vLLM sur DGX Spark. |
| Candidat comparatif | `YCWTG/gemma-4-31B-it-NVFP4A16-GPTQ` | Checkpoint communautaire à accepter seulement après benchmark métier. |
| Référence qualitative supplémentaire | `google/gemma-4-31B-it-qat-w4a16-ct` | Quantification QAT W4A16 officielle Google. |

Le checkpoint communautaire NE DOIT PAS être promu sans benchmark métier sur le corpus réel.

## Options considérées

| Option | Décision | Raisons |
|---|---|---|
| Service LLM distant par défaut | Rejetée | Contredit le local-first. |
| vLLM local avec modèle de référence NVIDIA | Retenue | Compatible DGX Spark, API locale compatible OpenAI, sorties structurées et tool calling. |
| Checkpoint communautaire promu immédiatement | Rejetée | Nécessite une validation métier préalable. |

## Conséquences

### Positives

- API locale compatible avec des clients existants.
- Support des sorties structurées et appels d'outils.
- Cohérence avec le déploiement DGX Spark.

### Négatives ou coûts

- Les benchmarks métier sont obligatoires avant tout changement de modèle principal.
- Les paramètres de contexte doivent être mesurés plutôt que maximisés par défaut.

### Risques et contrôles

- Risque : dégradation sur nombres, négations, citations ou tool calling.  
  Contrôle : benchmark LLM sur tâches métier avant promotion.

## Impact d'implémentation

- Modules concernés : `app/chat/`, `app/claims/`, `app/synthesis/`, `app/research/`, `app/strategies/`.
- Configuration concernée : `config/models.yaml`.
- Tests attendus : JSON valide, tool calling, citations, entailment, négations, exactitude numérique.
- Milestones concernées : M5, M6, M8.
