# DDD-ADR-009 - Snapshots immuables pour l'expérimentation

**Statut :** Acceptée
**Date :** 2026-06-21
**Décideurs :** Propriétaire du projet
**Remplace :** Aucun
**Remplacée par :** Aucune
**Source :** `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 3, 10 et 11

## Contexte

Une expérience doit pouvoir être reproduite. Si EX lit une stratégie mutable ou des paramètres modifiés après démarrage, le résultat devient ambigu.

## Décision

EX reçoit un `StrategySnapshot` complet, hashé et immuable. Il ne lit jamais l'état mutable d'une stratégie candidate pour exécuter une expérience.

Les entrées d'expérience sont figées au démarrage.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| EX lit la stratégie courante | Rejetée | Rend les résultats non reproductibles. |
| Snapshot immuable | Retenue | Assure stabilité et audit. |

## Conséquences

### Positives

- Les expériences peuvent être reproduites.
- Les modifications de stratégie créent de nouvelles versions.

### Négatives ou coûts

- Les snapshots doivent inclure règles, paramètres, contraintes et preuves.

### Risques et contrôles

- Risque: modification d'entrée pendant RUNNING. Contrôle: invariant `EXPERIMENT_INPUT_NOT_FROZEN`.

## Impact d'implémentation

- Modules concernés: SD, EX.
- Configuration concernée: stockage snapshots et résultats.
- Tests attendus: refus de modification des entrées au démarrage.
- Milestones concernées: M-010, M-011.

## Liens de traçabilité

- Spécification: sections 3, 10, 11 et 21.
- Plan d'implémentation: M-010, M-011.
- Tests d'acceptation: entrées figées au démarrage.
- Commits: à renseigner lors de l'implémentation.
