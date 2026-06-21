# DDD-ADR-006 - Pas d'event sourcing généralisé

**Statut :** Acceptée
**Date :** 2026-06-21
**Décideurs :** Propriétaire du projet
**Remplace :** Aucun
**Remplacée par :** Aucune
**Source :** `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 3 et 13

## Contexte

Le système doit être auditable et reproductible, mais une reconstruction intégrale des agrégats depuis des événements ajouterait une complexité forte pour la V1.

## Décision

La V1 n'utilise pas d'event sourcing généralisé. Elle utilise état courant transactionnel, journal d'audit, outbox et artefacts immuables pour les versions importantes.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Event sourcing complet | Rejetée | Complexité excessive pour la V1. |
| État courant sans audit | Rejetée | Insuffisant pour preuves et reproductibilité. |
| État courant, audit, outbox et immutabilité | Retenue | Équilibre traçabilité et simplicité. |

## Conséquences

### Positives

- Les agrégats restent simples à charger.
- Les événements intercontextes restent explicites.

### Négatives ou coûts

- Les audits doivent lire état, journal et artefacts.

### Risques et contrôles

- Risque: événements interprétés comme source unique de vérité. Contrôle: documentation et repositories propriétaires.

## Impact d'implémentation

- Modules concernés: tous les contextes, `platform.event_bus`.
- Configuration concernée: outbox et audit.
- Tests attendus: événement publié dans la même transaction que l'état producteur.
- Milestones concernées: M-002, M-013.

## Liens de traçabilité

- Spécification: sections 3, 13, 14 et 15.
- Plan d'implémentation: M-002.
- Tests d'acceptation: idempotence et livraison outbox.
- Commits: à renseigner lors de l'implémentation.
