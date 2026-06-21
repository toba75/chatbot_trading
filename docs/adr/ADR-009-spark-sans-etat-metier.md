# ADR-009 - Le Spark est sans état métier

**Statut :** Acceptée
**Date :** 2026-06-21
**Décideurs :** Propriétaire du projet
**Remplace :** Aucun
**Remplacée par :** Aucune
**Source :** `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, section 3, ADR-009

## Contexte

Le Spark sert le modèle principal mais ne doit pas devenir un second plan applicatif. Les conversations, claims, stratégies, corpus et expériences sont des données métier durables.

## Décision

Le Spark conserve uniquement le cache de poids et tokenizers, la configuration runtime, les secrets nécessaires au serving et des métriques techniques à rétention courte.

Il NE DOIT PAS conserver corpus, prompts complets persistants, réponses complètes persistantes, conversations, claims, stratégies, jeux de données, résultats expérimentaux ou secrets des autres services.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Spark comme noeud applicatif durable | Rejetée | Contredit la propriété des données par `docker-local`. |
| Spark stateless métier | Retenue | Limite sauvegarde, sécurité et couplage. |

## Conséquences

### Positives

- Les sauvegardes métier restent concentrées sur `docker-local`.
- Une réinstallation du Spark ne détruit pas l'historique métier.

### Négatives ou coûts

- Les payloads envoyés au Spark doivent être minimisés.
- Les journaux Spark doivent être configurés strictement.

### Risques et contrôles

- Risque: logging persistant de prompts complets. Contrôle: configuration de logs et audit M-013.

## Impact d'implémentation

- Modules concernés: `platform.llm_gateway`, exploitation Spark.
- Configuration concernée: logs, volumes, secrets, rétention.
- Tests attendus: absence de stockage métier sur Spark et payload minimal.
- Milestones concernées: M-002, M-013.

## Liens de traçabilité

- Spécification: sections 3, 13, 18 et 21.
- Plan d'implémentation: M-002, M-013.
- Tests d'acceptation: local-first et sécurité Spark.
- Commits: à renseigner lors de l'implémentation.
