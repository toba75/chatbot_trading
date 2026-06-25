# Commandes de validation M-000, M-001 et M-002

## Scénario BDD

- Given les artefacts de gouvernance M-000, les contrats M-001 et la spécification M-002 sont présents.
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

## Préconditions d'outillage

M-001 ajoute un validateur d'architecture qui inspecte l'AST Python avec la bibliothèque standard. Cette dépendance d'outillage est documentée par `docs/adr/ADR-011-python-outille-pour-validateurs-architecture.md`.

Avant d'exécuter `scripts/test.ps1`, `scripts/lint.ps1`, `scripts/validate_architecture_boundaries.ps1` ou un test PowerShell M-001 qui lance `python -B`, l'appelant DOIT disposer de `python` dans `PATH` avec une version `3.10` ou supérieure.

Le wrapper `scripts/validate_architecture_boundaries.ps1` refuse explicitement un interpréteur absent, trop ancien ou non résolu.

## Périmètre des tests

`scripts/test.ps1` exécute les validateurs M-000, les validateurs M-001 et le validateur de spécification M-002, les tests d'acceptation et unitaires de gouvernance livrés par M-000, puis les tests d'acceptation et unitaires M-001 et M-002.

Le self-test d'acceptation `tests/governance/validate_m000_validation_commands_acceptance.ps1` reste exécuté explicitement hors `scripts/test.ps1` pour vérifier les gates sans récursion de `scripts/test.ps1` sur lui-même.

`scripts/lint.ps1` exécute les validateurs M-000, M-001 et M-002 sans lancer de suite de tests.

## Validateurs requis

- `scripts/validate_m000_precondition_report.ps1`
- `scripts/validate_adr_system.ps1`
- `scripts/validate_task_system.ps1`
- `scripts/validate_traceability.ps1`
- `scripts/validate_definition_of_done.ps1`
- `scripts/validate_m001_specification.ps1`
- `scripts/validate_m002_specification.ps1`
- `scripts/validate_architecture_boundaries.ps1`

## Refus explicites

Une validation ou un test requis absent produit un code de sortie non nul et nomme le script absent.

Une validation ou un test requis échoué produit un code de sortie non nul et nomme le script en échec.

Aucune suite vide n'est acceptée comme GREEN.

## Hors périmètre M-000

M-000 ne livre pas de code métier applicatif. L'absence de suite applicative reste tracée dans `docs/traceability/matrix.md` comme hors périmètre du milestone de gouvernance.

## Extension M-001

M-001 ajoute les contrats publiés, le registre de contextes et les frontières d'import aux gates existantes sans changer les points d'entrée PowerShell ADR-010. Le validateur d'architecture utilise Python comme outillage interne selon ADR-011.

Les tests M-001 restent non récursifs: ils valident les contrats, fixtures, règles d'architecture et lignes de traçabilité sans relancer `scripts/test.ps1`.

## Extension M-002

M-002 ajoute la spécification de plateforme locale sûre aux gates existantes sans changer les points d'entrée PowerShell ADR-010.

Les tests M-002 restent non récursifs: ils valident la présence des sections, scénarios, placements physiques, règles `docker-local` et `spark-inference`, gateway unique, outbox, commandes de validation et garde-fous sans lancer `scripts/test.ps1`.
