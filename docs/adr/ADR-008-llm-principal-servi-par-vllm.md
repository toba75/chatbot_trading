# ADR-008 - LLM principal servi par vLLM sur le DGX Spark

**Statut :** Acceptée
**Date :** 2026-06-21
**Décideurs :** Propriétaire du projet
**Remplace :** Aucun
**Remplacée par :** Aucune
**Source :** `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 3, 13 et 16

## Contexte

Le chatbot doit générer, extraire, structurer et interpréter avec un LLM local. Le DGX Spark fournit la capacité d'inférence principale et vLLM expose une API compatible OpenAI.

## Décision

Gemma 4 est servi par vLLM sur `spark-inference`. Les bounded contexts et le navigateur NE DOIVENT PAS appeler vLLM directement.

Le seul chemin applicatif autorisé est `LocalLanguageModelGateway` ou `llm-gateway` vers l'API vLLM privée. L'indisponibilité du Spark produit un état explicite `LLM_UNAVAILABLE` sans fallback silencieux.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Appels directs à vLLM depuis les contextes | Rejetée | Couple le domaine au protocole et élargit la surface réseau. |
| Provider distant par fallback | Rejetée | Contredit local-first et absence de fallback silencieux. |
| Gateway local vers vLLM Spark | Retenue | Isole protocole, sécurité et erreurs d'inférence. |

## Conséquences

### Positives

- Les erreurs d'inférence sont centralisées.
- Les contrats de sortie structurée sont testables.

### Négatives ou coûts

- Un service gateway et des tests de contrat sont requis.
- La latence inter-hôtes doit être mesurée.

### Risques et contrôles

- Risque: retry produisant deux transitions métier. Contrôle: idempotence applicative et outbox.

## Impact d'implémentation

- Modules concernés: `platform.llm_gateway`, adaptateurs de modèles.
- Configuration concernée: modèle servi, TLS, clé API, timeouts.
- Tests attendus: contrat compatible OpenAI, TLS, panne Spark, sorties structurées.
- Milestones concernées: M-002, M-012, M-013.

## Liens de traçabilité

- Spécification: sections 3, 13, 16, 20 et 21.
- Plan d'implémentation: M-002.
- Tests d'acceptation: panne Spark explicite et absence de fallback.
- Commits: à renseigner lors de l'implémentation.
