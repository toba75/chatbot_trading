# ADR-002 - Routage hybride Docling

**Statut :** Acceptée
**Date :** 2026-06-21
**Décideurs :** Propriétaire du projet
**Remplace :** Aucun
**Remplacée par :** Aucune
**Source :** `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, section 3, ADR-002

## Contexte

Le corpus contient des PDF numériques, des scans, des pages mixtes et des documents visuellement complexes. Une chaîne unique de conversion produirait soit trop d'erreurs, soit trop de coût.

## Décision

Le pipeline documentaire DOIT router explicitement chaque document ou page entre Docling standard, Granite-Docling et les routes mixtes prévues par la politique de traitement.

Une route incertaine NE DOIT PAS déclencher une autre route silencieuse. Elle doit produire un statut explicite de revue ou de quarantaine.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Docling standard pour tous les PDF | Rejetée | Ne couvre pas correctement scans et pages visuellement difficiles. |
| Granite-Docling pour tous les PDF | Rejetée | Coûteux et inutile pour les PDF natifs fiables. |
| Routage hybride explicite | Retenue | Adapte le traitement au diagnostic tout en conservant l'audit. |

## Conséquences

### Positives

- La qualité documentaire devient mesurable route par route.
- Les pages difficiles peuvent être traitées sans pénaliser les pages simples.

### Négatives ou coûts

- Le diagnostic et la politique de routage deviennent obligatoires.
- Les tests doivent couvrir les routes et les refus.

### Risques et contrôles

- Risque: mauvais routage produisant une mauvaise preuve. Contrôle: seuils calibrés, revue explicite, métriques M-012.

## Impact d'implémentation

- Modules concernés: `source_processing`.
- Configuration concernée: `routing.yaml`, politiques de qualité.
- Tests attendus: route explicite, refus des routes incertaines, absence de fallback.
- Milestones concernées: M-003, M-004, M-012.

## Liens de traçabilité

- Spécification: sections 3, 5, 20 et 21.
- Plan d'implémentation: M-003, M-004.
- Tests d'acceptation: diagnostic et routage d'un document source.
- Commits: à renseigner lors de l'implémentation.
