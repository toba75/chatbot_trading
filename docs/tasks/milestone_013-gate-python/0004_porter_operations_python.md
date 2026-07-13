# T-0004 - Exposer les opérations sûres via uv

## But métier

Préserver les contrats de sauvegarde, restauration et reconstruction sans dépendre de PowerShell.

## Scénario BDD

- Given un manifeste de sauvegarde valide ou une source SP admissible.
- When une commande uv opérationnelle est exécutée.
- Then elle conserve les validations, preuves et refus de sécurité du contrat historique.

## Implémentation attendue

- Créer les entrées `backup-v1`, `restore-v1` et `rebuild-knowledge-projection`.
- Porter la bibliothèque de manifeste de sauvegarde et les tests associés.

## Validation

- Tests Python des cas nominaux et des cibles interdites ou non vides.

## ADR

- ADR-029.
