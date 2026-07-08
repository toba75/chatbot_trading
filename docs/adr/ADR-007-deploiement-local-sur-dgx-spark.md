# ADR-007 - Topologie physique locale à deux plans

**Statut :** Remplacée
**Date :** 2026-06-21
**Décideurs :** Propriétaire du projet
**Remplace :** Aucun
**Remplacée par :** ADR-014
**Source :** `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 3 et 13

## Contexte

Le système doit rester local-first tout en utilisant un DGX Spark pour l'inférence principale. Les données métier et les stockages doivent rester sur la machine applicative locale.

## Décision

La plateforme cible utilise deux plans physiques:

- `spark-inference`: DGX Spark servant Gemma 4 via vLLM;
- `docker-local`: application métier, interface, workers, Docling, PostgreSQL, Qdrant, corpus et expériences.

Le Spark NE DOIT PAS héberger de stockage métier, worker documentaire, Qdrant, PostgreSQL ou moteur de backtest.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Tout exécuter sur `docker-local` | Rejetée pour V1 cible | Ne correspond pas à la topologie d'acceptation avec Spark. |
| Déporter données et traitements sur Spark | Rejetée | Introduit état métier et surface d'accès non souhaités. |
| Deux plans physiques | Retenue | Sépare inférence et données métier. |

## Conséquences

### Positives

- Les données durables restent sur `docker-local`.
- La frontière d'inférence est auditable.

### Négatives ou coûts

- La configuration réseau et TLS devient obligatoire.
- Les tests doivent simuler ou vérifier les pannes Spark.

### Risques et contrôles

- Risque: accès direct au Spark depuis navigateur ou worker. Contrôle: pare-feu, gateway unique, tests M-002 et M-013.

## Impact d'implémentation

- Modules concernés: `platform.llm_gateway`, déploiement.
- Configuration concernée: Docker Compose local, DNS, TLS, pare-feu Spark.
- Tests attendus: ports non exposés, Spark inaccessible hors gateway.
- Milestones concernées: M-002, M-013.

## Liens de traçabilité

- Spécification: sections 3, 13, 18 et 21.
- Plan d'implémentation: M-002, M-013.
- Tests d'acceptation: sécurité locale et frontière Spark.
- Commits: à renseigner lors de l'implémentation.
