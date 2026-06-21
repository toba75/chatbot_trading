# DDD-ADR-005 - Claim est un agrégat central

**Statut :** Acceptée
**Date :** 2026-06-21
**Décideurs :** Propriétaire du projet
**Remplace :** Aucun
**Remplacée par :** Aucune
**Source :** `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 3 et 7

## Contexte

La différenciation principale du produit est la gouvernance des preuves. Une affirmation ne doit pas devenir connaissance vérifiée par simple génération ou répétition documentaire.

## Décision

`Claim` est un agrégat central du core domain. La transition vers `VERIFIED` est protégée par une décision de vérification indépendante, une preuve admissible et une portée compatible.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Claim comme simple DTO extrait | Rejetée | Ne protège aucun invariant. |
| Réponse directe sans registre de claims | Rejetée | Empêche audit, contradiction et réutilisation. |
| Claim comme agrégat central | Retenue | Protège preuve, portée et statut. |

## Conséquences

### Positives

- Les affirmations sans preuve directe sont refusées.
- Les conditions et limites restent explicites.

### Négatives ou coûts

- La vérification devient une étape métier dédiée.

### Risques et contrôles

- Risque: claim trop large par rapport à la preuve. Contrôle: invariant `CLAIM_SCOPE_EXCEEDS_EVIDENCE`.

## Impact d'implémentation

- Modules concernés: EG, RA, SD.
- Configuration concernée: modèles de vérification.
- Tests attendus: refus sans preuve directe, conservation de portée, dépendances.
- Milestones concernées: M-006, M-007, M-009.

## Liens de traçabilité

- Spécification: sections 3, 7 et 21.
- Plan d'implémentation: M-006.
- Tests d'acceptation: affirmation sans preuve directe.
- Commits: à renseigner lors de l'implémentation.
