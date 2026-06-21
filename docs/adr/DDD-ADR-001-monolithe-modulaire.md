# DDD-ADR-001 - Monolithe modulaire

**Statut :** Acceptée
**Date :** 2026-06-21
**Décideurs :** Propriétaire du projet
**Remplace :** Aucun
**Remplacée par :** Aucune
**Source :** `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, section 3, DDD-ADR-001

## Contexte

Le système contient sept bounded contexts métier mais cible une exploitation personnelle locale. Les frontières de modèle sont nécessaires sans imposer de microservices artificiels.

## Décision

La V1 utilise un monolithe modulaire. Les bounded contexts sont des frontières de modèle, de dépendance et de propriété de données, pas des services réseau imposés.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Microservices par contexte | Rejetée | Complexité opérationnelle inutile pour une V1 personnelle locale. |
| Monolithe sans frontières | Rejetée | Mélange les modèles et fragilise les invariants. |
| Monolithe modulaire | Retenue | Protège les frontières tout en gardant une exploitation simple. |

## Conséquences

### Positives

- Les contextes peuvent évoluer avec des contrats internes clairs.
- L'exploitation locale reste simple.

### Négatives ou coûts

- Des tests d'architecture sont nécessaires pour empêcher l'érosion des frontières.

### Risques et contrôles

- Risque: imports transverses non autorisés. Contrôle: tests de dépendances et revue.

## Impact d'implémentation

- Modules concernés: tous les bounded contexts.
- Configuration concernée: packaging applicatif.
- Tests attendus: absence d'import d'adaptateur dans le domaine et absence d'import intercontexte interdit.
- Milestones concernées: M-001, M-013.

## Liens de traçabilité

- Spécification: sections 3, 4, 13 et 21.
- Plan d'implémentation: M-001.
- Tests d'acceptation: tests d'architecture.
- Commits: à renseigner lors de l'implémentation.
