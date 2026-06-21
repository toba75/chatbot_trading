# Commandes de validation M-000

## Scénario BDD

- Given les artefacts de gouvernance M-000 sont présents.
- When `.\scripts\test.ps1` et `.\scripts\lint.ps1` sont exécutés.
- Then les validateurs requis sont lancés sans omission et la gate retourne GREEN ou RED avec la commande fautive nommée.

## Périmètre

La politique d'exécution durable de ces gates est documentée par `docs/adr/ADR-010-gates-gouvernance-powershell.md`.

## Préconditions Git

Les gates utilisent la référence locale `master` pour contrôler les ADR acceptées et les dépendances de milestones.

Avant d'exécuter `scripts/test.ps1` ou `scripts/lint.ps1`, l'appelant DOIT synchroniser les références avec:

```powershell
git fetch origin --prune
```

La branche locale `master` DOIT exister et représenter la base de comparaison attendue du dépôt.

## Périmètre des tests

`scripts/test.ps1` exécute les validateurs M-000, puis les tests d'acceptation et unitaires livrés par T-001 à T-005, ainsi que le self-test unitaire non récursif T-006 `tests/governance/validate_m000_validation_commands_unit.ps1`.

Le self-test d'acceptation T-006 `tests/governance/validate_m000_validation_commands_acceptance.ps1` reste exécuté explicitement pendant T-006 pour vérifier les gates sans récursion de `scripts/test.ps1` sur lui-même.

`scripts/lint.ps1` exécute les validateurs M-000 sans lancer de suite de tests.

## Validateurs requis

- `scripts/validate_m000_precondition_report.ps1`
- `scripts/validate_adr_system.ps1`
- `scripts/validate_task_system.ps1`
- `scripts/validate_traceability.ps1`
- `scripts/validate_definition_of_done.ps1`

## Refus explicites

Une validation ou un test requis absent produit un code de sortie non nul et nomme le script absent.

Une validation ou un test requis échoué produit un code de sortie non nul et nomme le script en échec.

Aucune suite vide n'est acceptée comme GREEN.

## Hors périmètre M-000

M-000 ne livre pas de code métier applicatif. L'absence de suite applicative reste tracée dans `docs/traceability/matrix.md` comme hors périmètre du milestone de gouvernance.
