# ADR-006 - Registre d'affirmations séparé de l'index documentaire

**Statut :** Acceptée
**Date :** 2026-06-21
**Décideurs :** Propriétaire du projet
**Remplace :** Aucun
**Remplacée par :** Aucune
**Source :** `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 3 et 7

## Contexte

L'index documentaire contient des fragments retrouvables. Il ne représente pas les affirmations, leurs conditions, leurs relations de dépendance ni leurs verdicts de vérification.

## Décision

Le registre d'affirmations DOIT être séparé de l'index documentaire.

L'index vectoriel stocke des fragments et localisateurs. Le registre EG stocke les claims, preuves, portées, relations, vérifications, dépendances et supersessions.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Stocker les claims dans Qdrant | Rejetée | Confond projection de recherche et état métier vérifié. |
| Ne pas matérialiser les claims | Rejetée | Empêche audit, contradictions et réutilisation contrôlée. |
| Registre EG séparé | Retenue | Protège les invariants du core domain. |

## Conséquences

### Positives

- Une affirmation sans preuve directe peut être refusée de façon explicite.
- Les dépendances et contradictions deviennent auditables.

### Négatives ou coûts

- Un bounded context EG complet est nécessaire.
- Des synchronisations SP vers EG sont requises.

### Risques et contrôles

- Risque: duplication apparente entre passages et claims. Contrôle: contrats `EvidenceRef` et `VerifiedClaimRef`.

## Impact d'implémentation

- Modules concernés: `evidence_governance`, `knowledge_access`.
- Configuration concernée: stockage claims et événements intercontextes.
- Tests attendus: claim sans preuve directe refusé, dépendances comptées.
- Milestones concernées: M-006, M-007, M-009.

## Liens de traçabilité

- Spécification: sections 3, 7 et 21.
- Plan d'implémentation: M-006.
- Tests d'acceptation: affirmation sans preuve directe.
- Commits: à renseigner lors de l'implémentation.
