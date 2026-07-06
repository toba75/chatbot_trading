# DDD-ADR-011 - Contexte transverse d'évaluation pilote

**Statut :** Acceptée
**Date :** 2026-07-06
**Décideurs :** Propriétaire du projet
**Remplace :** Aucun
**Remplacée par :** Aucune
**Source :** `docs/specs/m012_evaluation_pilote_calibration.md`

## Contexte

M-012 mesure les comportements livrés par SP, KA, EG, RA, CV, SD, LLM et EX sur un corpus pilote. Ces mesures publient des rapports, des écarts V1 et des décisions de calibration sans prendre possession des données métier des contextes mesurés.

Sans contexte déclaré, le module `app/evaluation` échappe aux règles d'import, de contrats publics et de propriété du monolithe modulaire.

## Décision

Le module `app/evaluation` est un contexte transverse EV dédié à l'évaluation pilote et à la calibration.

EV DOIT consommer les contrats publics des contextes mesurés. EV NE DOIT PAS importer les modèles internes des contextes mesurés. EV DOIT publier ses rapports et décisions comme artefacts propres.

EV NE DOIT PAS devenir propriétaire des données SP, KA, EG, RA, CV, SD ou EX. Il conserve seulement les artefacts d'évaluation, les métriques, les écarts V1 et les décisions de calibration.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Laisser `evaluation` hors registre | Rejetée | Crée un trou de gouvernance et de validation d'architecture. |
| Répartir les benchmarks dans chaque contexte | Rejetée | Duplique les règles de calibration et rend les comparaisons transverses difficiles. |
| Déclarer EV comme contexte transverse | Retenue | Garde une propriété claire des artefacts d'évaluation sans casser les frontières métier. |

## Conséquences

### Positives

- Les imports EV sont contrôlés par le validateur d'architecture.
- Les rapports M-012 ont un propriétaire explicite.
- Les décisions de calibration restent séparées des données métier évaluées.

### Négatives ou coûts

- Les contrats publics consommés par EV doivent être maintenus explicitement.
- Les futures métriques transverses doivent éviter de devenir des dépendances internes masquées.

### Risques et contrôles

- Risque: EV importe des modèles internes pour aller plus vite. Contrôle: `scripts/validate_architecture_boundaries.ps1` refuse les imports intercontextes non publiés.
- Risque: EV devient une couche de production cachée. Contrôle: EV est limité aux artefacts d'évaluation, rapports, écarts et décisions de calibration.

## Impact d'implémentation

- Modules concernés: `app/evaluation`, `app/context_registry.json`, `scripts/validate_architecture_boundaries.py`.
- Configuration concernée: aucune.
- Tests attendus: validation des frontières d'architecture avec EV enregistré.
- Milestones concernées: M-012.

## Liens de traçabilité

- Spécification: `docs/specs/m012_evaluation_pilote_calibration.md`.
- Plan d'implémentation: `docs/tasks/milestone_012/`.
- Tests d'acceptation: `scripts/validate_architecture_boundaries.ps1`, `scripts/validate_m012_traceability.ps1`.
- Commits: à renseigner lors de l'implémentation.
