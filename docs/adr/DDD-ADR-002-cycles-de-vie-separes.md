# DDD-ADR-002 - Cycles de vie séparés

**Statut :** Acceptée
**Date :** 2026-06-21
**Décideurs :** Propriétaire du projet
**Remplace :** Aucun
**Remplacée par :** Aucune
**Source :** `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, section 3, DDD-ADR-002

## Contexte

Une machine d'états globale ne permet pas de représenter correctement les responsabilités distinctes entre source, projection, claim, recherche, stratégie et expérience.

## Décision

Les cycles de vie sont séparés pour le traitement de source, la projection de connaissance, l'affirmation, la recherche, la stratégie et l'expérience.

Une projection opérationnelle PEUT agréger ces états pour l'affichage, mais elle NE DOIT PAS devenir l'agrégat métier unique.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Machine globale unique | Rejetée | Mélange responsabilités et transactions. |
| Cycles de vie locaux par contexte | Retenue | Aligne les invariants sur les agrégats propriétaires. |

## Conséquences

### Positives

- Chaque contexte protège ses transitions métier.
- Les reprises et corrections sont plus explicites.

### Négatives ou coûts

- Les vues de statut global doivent être construites comme projections.

### Risques et contrôles

- Risque: confusion entre statut de projection et état métier. Contrôle: langage publié et tests de processus.

## Impact d'implémentation

- Modules concernés: SP, KA, EG, RA, SD, EX.
- Configuration concernée: aucune spécifique.
- Tests attendus: transitions locales refusant les commandes invalides.
- Milestones concernées: M-001 à M-011.

## Liens de traçabilité

- Spécification: sections 3, 5 à 12 et 21.
- Plan d'implémentation: M-001.
- Tests d'acceptation: transitions des agrégats propriétaires.
- Commits: à renseigner lors de l'implémentation.
