# DDD-ADR-010 - Conservation des versions négatives et supersédées

**Statut :** Acceptée
**Date :** 2026-06-21
**Décideurs :** Propriétaire du projet
**Remplace :** Aucun
**Remplacée par :** Aucune
**Source :** `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 3, 11 et 14

## Contexte

Les résultats défavorables, claims rejetés, réponses supersédées et stratégies invalides font partie de la connaissance. Les supprimer biaiserait l'historique de recherche.

## Décision

Les claims rejetés, réponses supersédées, stratégies invalides, versions remplacées, expériences échouées et résultats défavorables sont conservés selon leur politique de rétention.

Les corrections créent de nouvelles versions et des relations de supersession.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Supprimer les résultats négatifs | Rejetée | Biaise l'audit et la recherche. |
| Écraser les versions corrigées | Rejetée | Détruit la reproductibilité. |
| Conserver versions et résultats | Retenue | Préserve l'historique scientifique et métier. |

## Conséquences

### Positives

- Les échecs restent consultables.
- Les analyses futures peuvent tenir compte des résultats négatifs.

### Négatives ou coûts

- Le stockage et les vues doivent gérer versions et archivage logique.

### Risques et contrôles

- Risque: suppression administrative non maîtrisée. Contrôle: opérations explicites et politiques de rétention.

## Impact d'implémentation

- Modules concernés: SP, EG, RA, SD, EX.
- Configuration concernée: rétention et archivage.
- Tests attendus: résultat négatif conservé, version supersédée résolvable.
- Milestones concernées: M-004, M-006, M-011, M-013.

## Liens de traçabilité

- Spécification: sections 3, 11, 14 et 21.
- Plan d'implémentation: M-011, M-013.
- Tests d'acceptation: résultat négatif conservé.
- Commits: à renseigner lors de l'implémentation.
