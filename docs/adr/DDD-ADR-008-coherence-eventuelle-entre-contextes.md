# DDD-ADR-008 - Cohérence éventuelle entre contextes

**Statut :** Acceptée
**Date :** 2026-06-21
**Décideurs :** Propriétaire du projet
**Remplace :** Aucun
**Remplacée par :** Aucune
**Source :** `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 3, 14 et 15

## Contexte

Les contextes ont des propriétaires de données distincts. Imposer des transactions fortes entre contextes couplerait les modèles et fragiliserait les traitements longs.

## Décision

Les événements synchronisent les contextes en cohérence éventuelle. Les invariants forts restent locaux à un agrégat propriétaire.

Les événements intercontextes DOIVENT être publiés via outbox et consommés de manière idempotente.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Transaction forte intercontextes | Rejetée | Couplage excessif et faible résilience. |
| Partage direct de tables | Rejetée | Viole la propriété des contextes. |
| Outbox et cohérence éventuelle | Retenue | Protège les frontières et la reprise. |

## Conséquences

### Positives

- Les contextes restent autonomes.
- Les duplications d'événements peuvent être tolérées.

### Négatives ou coûts

- Les vues de lecture peuvent être temporairement stale.

### Risques et contrôles

- Risque: consommateur non idempotent. Contrôle: stockage des `event_id` traités et tests de répétition.

## Impact d'implémentation

- Modules concernés: tous les contextes, `platform.event_bus`.
- Configuration concernée: outbox, jobs de livraison.
- Tests attendus: événement dupliqué sans altération d'état.
- Milestones concernées: M-002, M-005, M-006.

## Liens de traçabilité

- Spécification: sections 3, 14, 15 et 20.
- Plan d'implémentation: M-002.
- Tests d'acceptation: publication source vers projection.
- Commits: à renseigner lors de l'implémentation.
