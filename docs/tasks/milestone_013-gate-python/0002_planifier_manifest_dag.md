# T-0002 - Planifier chaque preuve par manifeste DAG

## But métier

Garantir qu’une preuve de qualité n’est ni oubliée ni réexécutée inutilement.

## Scénario BDD

- Given un manifeste de nœuds et leurs dépendances.
- When le planificateur ordonne l’exécution.
- Then un cycle, un doublon ou un chemin invalide est refusé et chaque nœud n’apparaît qu’une fois.

## Implémentation attendue

- Créer `ost_gate.manifest`, `ost_gate.planner`, `ost_gate.executor`, `ost_gate.report` et `gate.toml`.
- Définir les scopes, phases, timeouts et groupes séries.

## Validation

- Tests Python du manifeste, du DAG, de l’unicité et du rapport.

## ADR

- ADR-029.
