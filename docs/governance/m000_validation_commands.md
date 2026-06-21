# Commandes de validation M-000

## Scénario BDD

- Given les artefacts de gouvernance M-000 sont présents.
- When `.\scripts\test.ps1` et `.\scripts\lint.ps1` sont exécutés.
- Then les validateurs requis sont lancés sans omission et la gate retourne GREEN ou RED avec la commande fautive nommée.

## Périmètre

`scripts/test.ps1` exécute les validateurs M-000, puis les tests d'acceptation et unitaires livrés par T-001 à T-005.

Les auto-tests T-006 `tests/governance/validate_m000_validation_commands_acceptance.ps1` et `tests/governance/validate_m000_validation_commands_unit.ps1` sont exécutés explicitement pendant T-006 pour vérifier les gates sans récursion de `scripts/test.ps1` sur lui-même.

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
