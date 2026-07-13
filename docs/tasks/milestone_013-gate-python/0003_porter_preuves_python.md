# T-0003 - Porter les preuves sans processus PowerShell

## But métier

Conserver la couverture réellement observée des milestones tout en supprimant le coût de processus et de récursion.

## Scénario BDD

- Given un ancien validateur ou test PowerShell déclaré par la gate.
- When son comportement est porté en Python.
- Then la table de parité relie le chemin historique, le node ID et le comportement couvert sans appeler PowerShell.

## Implémentation attendue

- Porter les tests par vagues M-000/M-002, M-003/M-005, M-006/M-008, M-009/M-011, puis M-012/M-013, configuration, FastAPI, UI et réalité produit.
- Classer les preuves en `unit`, `integration`, `process`, `git` ou `live` selon leurs effets réels.

## Validation

- Rapport de parité et collecte pytest stricte.

## ADR

- ADR-029.
