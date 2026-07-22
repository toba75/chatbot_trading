# Runbook des environnements explicites

## Contrat d'exploitation

- Identifiant : `M13-Environments-Runbook-1.0`.
- Décision : ADR-045.
- Profils fermés : `development`, `test`, `production`.
- Statut de livraison : `SUBMILESTONE_GREEN_M013_OPEN` ; ce runbook ne clôt
  pas le milestone M-013 global.
- Répertoire de travail : racine du dépôt.
- Prérequis : Docker opérationnel, dépendances UV verrouillées, Spark réel
  joignable et fichiers de secrets locaux du seul profil présent. Une valeur
  absente arrête la commande ; aucun secret ni profil n'est déduit.
- Les commandes ne créent ni répertoire ni valeur secrète. L'opérateur fournit
  avant le lancement les cinq fichiers du profil, tous valides et hors Git.
- Une preuve réelle exige un worktree Git propre. Le commit annoncé dans le
  rapport est celui injecté dans les images et contient le runner qualifié.

## Commandes principales

| Profil | Commande unique | Port public | Persistance à la sortie |
|---|---|---:|---|
| development | `uv run development` | `https://localhost:18443` | volumes conservés |
| test | `uv run test` | `https://localhost:19443` pendant chaque cycle | seuls les volumes test sont supprimés après préflight |
| production | `uv run production` | `https://localhost:20443` pendant la qualification | volumes conservés |

`uv run development` démarre les 17 conteneurs, vérifie la readiness de tous
les participants, puis reste actif. L'arrêt normal est `Ctrl+C`; le contexte
exécute `down --remove-orphans`, sans `--volumes`.

`uv run test` exécute exactement deux parcours réels sur une pile vide. Chaque
parcours écrit sa preuve avant l'arrêt. La seule occurrence autorisée de
`down --volumes` appartient à ce cycle et suit le préflight PostgreSQL, Qdrant
et fichiers avec l'identité `test` / `ostrading-test-ci`. Une identité
divergente produit `DATASTORE_ENVIRONMENT_MISMATCH`, arrête les conteneurs et
conserve les volumes.
Un verrou interprocessus couvre les deux cycles. Chaque installation inscrit
son identifiant de cycle dans le volume applicatif ; le teardown compare ce
propriétaire persistant avant `down --volumes`. Un verrou orphelin ou une pile
test préexistante est terminal et n'est jamais réinitialisé automatiquement.

`uv run production` exécute une qualification réelle finie, redémarre la même
installation pour relire ses données et sort par `down --remove-orphans`. La
commande n'exécute jamais `down --volumes`, purge ou restauration.

## Migration bornée

Les migrations PostgreSQL font partie du démarrage de la pile sélectionnée.
Elles utilisent le fichier `config/environments/<profil>.yaml`, le rôle et la
base de ce profil, puis vérifient l'identité observée avant mutation. Il
n'existe pas de commande de migration générique avec profil implicite : lancer
la commande principale du profil concerné et conserver la sortie de readiness.

Une migration qui observe un autre `environment` ou `deployment_id` est RED
avant la première écriture. Il est interdit de contourner le refus, de modifier
une URL à la main ou de réutiliser les credentials d'un autre profil.

## Sauvegarde bornée

Le manifeste doit porter le même `environment` et le même `deployment_id` que
la configuration et les trois familles de stockage observées.

```console
uv run --locked backup-v1 --manifest <manifest.json> --config config/environments/<profil>.yaml
```

Conserver la sortie d'audit et le manifeste hors des données d'un autre
profil. Une preuve incomplète, un hash invalide ou une identité divergente est
terminale. Les clés de chiffrement et valeurs de secrets restent hors Git.

## Restauration bornée

La cible doit être neuve, vide et strictement sous le répertoire de drill du
profil sélectionné.

```console
uv run --locked restore-v1 --manifest <manifest.json> --target data/environments/<profil>/reports/restore-drills/<drill> --config config/environments/<profil>.yaml
```

Le manifeste, la configuration, PostgreSQL, Qdrant et les fichiers doivent
publier la même identité avant matérialisation. Il n'existe ni option `force`,
ni restauration croisée, ni cible par défaut.

## Gates statique et live

La gate statique contrôle les artefacts versionnés, la matrice 3 × 3, les
coordonnées mutables, les six réplicas workers et la copie normalisée des
rapports réels :

```console
uv run --locked gate --scope m013_environments
```

La gate live rejoue les trois vraies piles, sans mock, puis consolide leurs
nouveaux rapports. Elle est volontairement explicite et coûteuse :

```console
uv run --locked gate --scope m013_environments --live
```

Sans `--live`, même une gate sans `--scope` exclut les nœuds live. Le parcours
live repart d'un Docker propre : aucun volume étranger n'est un prérequis. Les
sondes croisées relisent uniquement les artefacts versionnés du profil qualifié
et ne lisent aucun secret, stockage ou autorité d'un autre profil.

Une preuve `development`, `test` ou `production` absente, une collision
d'identifiant, un worker manquant ou une donnée sensible rend la gate RED. Une
gate structurelle GREEN ne remplace jamais la gate live.

## Incident et arrêt

- Conserver le code d'erreur terminal et le rapport produit avant toute autre
  action.
- Ne jamais copier une configuration ou un secret d'un autre profil pour faire
  repartir une pile.
- Pour development, interrompre la commande au premier plan et vérifier que
  les conteneurs sont arrêtés sans suppression de volume.
- Test et production sont des qualifications finies : un échec est propagé et
  leur superviseur applique respectivement le teardown test contrôlé ou
  l'arrêt production non destructif.
- Ne jamais déclarer un écart accepté implicitement. Le statut reste
  `SUBMILESTONE_GREEN_M013_OPEN` tant que la décision globale M-013 n'a pas été
  prise par sa propre gouvernance.
