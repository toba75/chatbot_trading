# Rapport de précondition GREEN M-000

## Source

- Tâche: `docs/tasks/milestone_000/0001_verifier_precondition_green.md`
- Spécification: `docs/specs/plan_implementation_milestones_workstreams.md`, section `M-000 - Gouvernance exécutable`
- Spécification v4.1: `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 0, 3, 20, 21 et 22
- ADR: non requise pour T-001, car la tâche matérialise une exigence de gouvernance déjà prévue sans créer de nouvelle décision structurante.

## Scénario BDD

- Given le dépôt `master` contient la spécification v4.1 et le registre ADR.
- When la précondition de M-000 est vérifiée.
- Then l'état des validations existantes, des commandes absentes et des tâches versionnées est déclaré sans ambiguïté.

## Révision master

**Révision master observée :** `3ed5b0157128bc03bdaa6e27c3eb85461fbfd3cb`

## Validations exécutées

| Commande | Date UTC | Résultat | Observation |
|---|---|---|---|
| `git fetch origin --prune` | `2026-06-21T15:43:16Z` | `GREEN` | Remote synchronisé sans erreur. |
| `git ls-tree -r --name-only master -- docs/tasks docs/adr docs/specs` | `2026-06-21T15:43:16Z` | `GREEN` | `master` contient le registre ADR et les deux spécifications de référence. |
| `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_adr_system.ps1` | `2026-06-21T15:43:16Z` | `GREEN` | Système ADR valide: 19 ADR contrôlées. |

## Commandes de validation absentes

| Commande | Date UTC | Résultat | Observation |
|---|---|---|---|
| `.\scripts\test.ps1` | `2026-06-21T15:43:16Z` | `RED` | Commande absente; création prévue par M-000. |
| `.\scripts\lint.ps1` | `2026-06-21T15:43:16Z` | `RED` | Commande absente; création prévue par M-000. |

## Tâches versionnées

| Élément | Date UTC | Résultat | Observation |
|---|---|---|---|
| `docs/tasks/milestone_000 dans master` | `2026-06-21T15:43:16Z` | `RED` | Aucun dossier de tâches M-000 n'est versionné dans `master`; les tâches M-000 sont portées par la branche `feature/milestone-m000-gouvernance-executable`. |

## Conclusion

La précondition M-000 est connue: le registre ADR est GREEN, les commandes génériques de test et de lint sont explicitement RED car absentes, et l'état des tâches M-000 dans `master` est explicitement RED. Aucun état inconnu n'est assimilé à GREEN.

## Actualisation T-006

Les tableaux précédents conservent l'état historique observé au démarrage de M-000.

Depuis T-006 sur la branche `feature/milestone-m000-gouvernance-executable`, `scripts/test.ps1` et `scripts/lint.ps1` existent et sont décrits dans `docs/governance/m000_validation_commands.md`.

Cette actualisation ne transforme pas le RED initial en GREEN rétroactif: elle indique seulement que la création des commandes est livrée par T-006 et couverte par `docs/traceability/matrix.md`.
