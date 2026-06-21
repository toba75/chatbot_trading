# DDD-ADR-004 - Qdrant est une projection

**Statut :** Acceptée
**Date :** 2026-06-21
**Décideurs :** Propriétaire du projet
**Remplace :** Aucun
**Remplacée par :** Aucune
**Source :** `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, section 3, DDD-ADR-004

## Contexte

Qdrant permet la recherche vectorielle et hybride, mais ses collections sont dérivées de versions canoniques. Les confondre avec la source de vérité casserait la gouvernance des preuves.

## Décision

Qdrant est une projection régénérable détenue par KA. Les versions canoniques et les claims restent les sources métier dans leurs contextes propriétaires.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Qdrant comme source documentaire | Rejetée | Perte de provenance et de version canonique. |
| Qdrant comme registre de claims | Rejetée | Ne protège pas les invariants EG. |
| Qdrant comme projection KA | Retenue | Aligne recherche et régénération. |

## Conséquences

### Positives

- Les index peuvent être reconstruits.
- Les consommateurs passent par un port KA stable.

### Négatives ou coûts

- Les traitements d'indexation doivent être idempotents.

### Risques et contrôles

- Risque: RA lit Qdrant directement. Contrôle: tests d'architecture et port `SearchKnowledge`.

## Impact d'implémentation

- Modules concernés: KA, RA.
- Configuration concernée: collections Qdrant et versions de projection.
- Tests attendus: reconstruction de projection, source en quarantaine non indexée.
- Milestones concernées: M-005.

## Liens de traçabilité

- Spécification: sections 3, 6, 13, 14 et 21.
- Plan d'implémentation: M-005.
- Tests d'acceptation: source en quarantaine non indexée.
- Commits: à renseigner lors de l'implémentation.
