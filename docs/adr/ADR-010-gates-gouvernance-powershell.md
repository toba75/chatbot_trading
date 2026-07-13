# ADR-010 - Gates de gouvernance PowerShell

**Statut :** Remplacée
**Date :** 2026-06-21
**Décideurs :** Propriétaire du projet
**Remplace :** Aucun
**Remplacée par :** ADR-029-gate-python-uv-manifeste-unique
**Source :** `docs/specs/plan_implementation_milestones_workstreams.md`, M-000

## Contexte

M-000 doit rendre le projet capable de déclarer un état GREEN ou RED sans ambiguïté avant toute implémentation métier. Les milestones suivants doivent disposer de commandes standard, locales et traçables pour exécuter les validations de gouvernance.

La définition d'achèvement transverse rend obligatoire une preuve de tests, de lint, de traçabilité et d'ADR. La politique d'exécution de ces preuves devient donc une décision durable de gouvernance.

## Décision

Le dépôt DOIT exposer deux gates PowerShell canoniques:

- `scripts/test.ps1`;
- `scripts/lint.ps1`.

Ces gates DOIVENT exécuter les validateurs M-000 requis via `scripts/m000_validation_gate.ps1`.

`scripts/test.ps1` DOIT exécuter les validateurs de gouvernance, les tests d'acceptation et unitaires de gouvernance livrés par T-001 à T-005, ainsi que le self-test unitaire non récursif T-006.

Le self-test d'acceptation T-006 DOIT rester exécuté explicitement hors `scripts/test.ps1` pour éviter une récursion.

`scripts/lint.ps1` DOIT exécuter les validateurs de gouvernance sans lancer les tests.

Une gate NE DOIT PAS retourner GREEN si une validation ou un test requis est absent, échoue, sort du dépôt, est dupliqué, n'appartient pas à la liste attendue ou si le nombre de commandes déclarées ne correspond pas au nombre attendu.

Les gates DOIVENT contrôler l'identité et l'unicité des chemins attendus, et pas seulement le nombre total de validations ou de tests.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Gates PowerShell versionnées dans `scripts/` | Retenue | Cohérent avec le dépôt Windows actuel et exécutable sans dépendance applicative. |
| Commandes ad hoc par tâche | Rejetée | Ne donne pas de signal GREEN/RED standard aux milestones suivants. |
| Gate unique sans séparation test/lint | Rejetée | Ne distingue pas la validation statique de l'exécution des tests. |

## Conséquences

### Positives

- Les agents et développeurs disposent d'un point d'entrée stable pour vérifier M-000.
- Les validations échouées nomment explicitement le script fautif.
- Les milestones suivants peuvent référencer `scripts/test.ps1` et `scripts/lint.ps1` dans leur précondition GREEN.

### Négatives ou coûts

- Les scripts PowerShell deviennent une surface de maintenance transverse.
- Chaque nouveau validateur de gouvernance devra être ajouté explicitement aux gates et aux tests de comptage.

### Risques et contrôles

- Risque: gate amputée qui reste GREEN. Contrôle: comptage attendu, identité et unicité des validations et tests.
- Risque: preuve hors dépôt ou commande suffixée. Contrôle: validation stricte des chemins et commandes dans la matrice de traçabilité.
- Risque: récursion des auto-tests de la gate. Contrôle: le self-test d'acceptation T-006 reste exécuté explicitement hors `scripts/test.ps1`, tandis que le self-test unitaire T-006 est inclus dans la gate canonique.

## Impact d'implémentation

- Modules concernés: `scripts/test.ps1`, `scripts/lint.ps1`, `scripts/m000_validation_gate.ps1`.
- Configuration concernée: aucune variable d'environnement.
- Tests attendus: `tests/governance/validate_m000_validation_commands_acceptance.ps1`, `tests/governance/validate_m000_validation_commands_unit.ps1`.
- Milestones concernées: M-000, puis préconditions GREEN des milestones suivants.

## Liens de traçabilité

- Spécification: `docs/specs/plan_implementation_milestones_workstreams.md`, M-000 et règles d'exécution.
- Plan d'implémentation: M-000, T-006.
- Tests d'acceptation: `tests/governance/validate_m000_validation_commands_acceptance.ps1`.
- Commits: implémentation initiale `6d71280bbed826fa102330ef369128886b93ca69`, création ADR `87517ab`, complément identité/unicité `b90e8fb`, corrections de revue documentées dans `docs/tasks/milestone_000/journal.md`.
