# Runbook déprécié : configuration applicative unique

## Statut

Ce document est déprécié depuis ADR-046. Il reste versionné pour conserver le
lien de traçabilité avec M13-config, mais il ne décrit plus une procédure
opératoire active.

Le runbook actif est
`docs/runbooks/environnements_explicites.md`. Les seules commandes de sélection
sont :

```console
uv run development
uv run test
uv run production
```

Chaque commande choisit exactement le fichier complet
`config/environments/<profil>.yaml` et les secrets hors Git sous
`config/secrets/<profil>/`. Il n'existe ni fusion, ni héritage, ni fichier
implicite. Un profil, un fichier ou un secret manquant provoque une erreur
terminale avant tout accès externe.

## Scénario BDD

- Given un opérateur choisit l'un des trois profils fermés.
- When il exécute la commande UV correspondante.
- Then la configuration complète, les secrets et toutes les autorités de
  données appartiennent au même profil, sans quatrième chemin ni fallback.

## Validation

```console
uv run --locked gate --scope m013_environments --offline
uv run --locked gate --scope m013_environments --live
```

La première commande vérifie le contrat statique. La seconde exige les preuves
réelles à la révision courante. Les anciennes preuves restent historiques et ne
peuvent pas rendre la gate live GREEN.
