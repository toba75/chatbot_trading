# T-0001 - Inventorier le contrat de gate uv

## But métier

Permettre au projet de connaître précisément le coût et la couverture de sa validation avant de modifier son autorité de gouvernance.

## Portée DDD

- Domaine : gouvernance transverse.
- Bounded context : plateforme technique, hors bounded contexts métier.
- Invariant : aucune mesure historique n’est présentée comme mesure courante sans réexécution.

## Scénario BDD

- Given le dépôt courant et sa gate uv run --locked gate
- When l’inventaire des commandes et fichiers est calculé.
- Then les écarts sont documentés et les 15 tests M13-config sont nommés.

## Implémentation attendue

- Consigner l’inventaire dans `docs/specs/m013_gate_python.md`.
- Préserver la modification utilisateur de santé M-013 lors de son port Python.

## Validation

- Inventaire Git des scripts historiques et analyse statique de `uv run --locked gate`.

## ADR

- ADR-029.
