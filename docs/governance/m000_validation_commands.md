# Commande canonique de validation

## Scénario BDD

- Given le manifeste racine `gate.toml` et l’environnement verrouillé par `uv.lock`.
- When `uv run --locked gate` est exécuté.
- Then chaque nœud est collecté et exécuté une seule fois, le pipeline réel M-013 est inclus et le rapport JSON nomme précisément toute erreur.

## Commandes

```console
uv sync --locked
uv run --locked gate
```

`uv run gate --scope <milestone>` est ciblé et affiche seulement `SCOPE GREEN`.
`uv run gate --offline` est explicitement partiel et n’affiche jamais `Gate GREEN`.
`uv run gate --list` produit l’inventaire déterministe sans exécution.

## Contrat

`gate.toml` est l’unique manifeste. Les dépendances entre milestones forment un DAG ; un nœud vert déjà exécuté est réutilisé en mémoire et n’est jamais relancé. Les skips, xfails, collectes incomplètes, fichiers absents, cycles et chemins hors dépôt rendent la gate RED.

La décision est gouvernée par [ADR-029](../adr/ADR-029-gate-python-uv-manifeste-unique.md). Les anciennes commandes sont historiques et ne constituent plus des points d’entrée actifs.
