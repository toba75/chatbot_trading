# Journal M-004 - Version canonique publiée

## Statut initial

- Planification créée depuis `docs/specs/plan_implementation_milestones_workstreams.md`.
- Dépendance directe: M-003.
- Milestones amont vérifiés dans `master`: M-000, M-001, M-002 et M-003.
- État initial des gates: `lint` GREEN; `test` RED sur `tests/m003/validate_m003_precondition_acceptance.ps1`.
- Cause RED conservée: `scripts/validate_m003_precondition.ps1` attendait `codex/milestone-m003-source-routee` alors que la base courante est `master` ou la branche M-004.

## Ordre d'exécution prévu

1. T-001 - Vérifier et rétablir la précondition GREEN M-004.
2. T-002 - Publier la spécification de version canonique.
3. T-003 - Convertir les pages selon la route explicite.
4. T-004 - Adjuger l'autorité textuelle par page.
5. T-005 - Contrôler la qualité de la version canonique.
6. T-006 - Publier une version canonique immuable.
7. T-007 - Rendre les SourceLocator résolvables.
8. T-008 - Publier l'événement CanonicalSourcePublished.
9. T-009 - Exposer la commande de conversion documentaire.
10. T-010 - Relier M-004 à la traçabilité et aux gates.

## Suivi d'exécution

| Tâche | Commit RED | Commit GREEN | ADR consultées | ADR créée ou modifiée | Validations GREEN déclarées |
|---|---|---|---|---|---|
| T-001 - Vérifier et rétablir la précondition GREEN M-004 | `b5036c60d07de6b8bdd4e8d27661fa4f78dab976` | `test(m004): retablir la precondition green avant version canonique` | ADR-010 | Aucune | `tests/m003/validate_m003_precondition_unit.ps1`; `tests/m003/validate_m003_precondition_acceptance.ps1`; `tests/m004/validate_m004_precondition_unit.ps1`; `tests/m004/validate_m004_precondition_acceptance.ps1`; `scripts/validate_m004_precondition.ps1 -Path .\docs\governance\m004_precondition_green.md`; `scripts/test.ps1`; `scripts/lint.ps1` |

## Clôture T-001

- Scénario BDD: Given M-000, M-001, M-002 et M-003 sont présents dans `master`; When les gates de précondition M-004 sont exécutées depuis la base courante; Then M-004 ne commence que si `test`, `lint`, la traçabilité, les ADR, les frontières d'architecture et la preuve M-003 post-merge sont GREEN.
- RED T-001 confirmé: `tests/m004/validate_m004_precondition_acceptance.ps1` échouait sur l'absence de `scripts/validate_m004_precondition.ps1`; `tests/m003/validate_m003_precondition_unit.ps1` échouait tant que la branche M-004 post-merge n'était pas explicitement autorisée.
- Implémentation: `scripts/validate_m004_precondition.ps1` vérifie les branches autorisées `master` et `codex/milestone-m004-version-canonique-publiee`, la présence de M-000 à M-003 dans `master`, la relation `master` contient `origin/master`, la présence de `master` dans la branche courante, les gates `test` et `lint`, et écrit `docs/governance/m004_precondition_green.md`.
- Correction M-003: `scripts/validate_m003_precondition.ps1` autorise explicitement le post-merge sur `master` et la branche M-004 sans dépendre silencieusement de l'ancienne branche `codex/milestone-m003-source-routee`.
- ADR: non requise; T-001 applique ADR-010 et rend la précondition post-merge explicite sans changer la politique durable des gates PowerShell.
- Risques traités: l'ancien RED M-003 n'est pas supprimé ni masqué; un milestone amont absent, une branche non autorisée, une référence `master` qui ne contient pas `origin/master`, une gate RED ou un rapport hors dépôt restent refusés explicitement.
