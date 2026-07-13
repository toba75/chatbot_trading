# T-0005 - Basculer l’autorité de validation atomiquement

## But métier

Fournir un signal GREEN unique, reproductible et non ambigu pour la reprise des développements.

## Scénario BDD

- Given la parité complète, un manifeste strict et une gate Python GREEN.
- When la bascule est appliquée.
- Then `uv run --locked gate` est la seule gate canonique, tous les scripts historiques actifs sont supprimés et les ADR remplacées sont mises à jour ensemble.

## Implémentation attendue

- Mettre à jour ADR-029, ADR-010, ADR-011, ADR-012, l’index, la documentation normative et les skills.
- Supprimer les scripts, tests et gardes de récursion uv run --locked gate
- Ajouter l’allowlist des mentions historiques et les rapports comparatifs/final.

## Validation

- `uv sync --locked`, `uv run --locked gate`, `git diff --check`, inventaire Git et recherche de références actives.

## ADR

- ADR-029.
