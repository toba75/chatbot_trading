# Matrice d'étanchéité M13-environments

## Statut

- Décision : ADR-045.
- Source machine : `docs/governance/m013_environments_isolation_matrix.json`.
- Statut : `SUBMILESTONE_GREEN_M013_OPEN`.

## Accès 3 × 3

La ligne représente l'identité du processus et la colonne la ressource visée.

| Processus \ ressource | development | test | production |
|---|---|---|---|
| development | `OWNED` | `FORBIDDEN` | `FORBIDDEN` |
| test | `FORBIDDEN` | `OWNED` | `FORBIDDEN` |
| production | `FORBIDDEN` | `FORBIDDEN` | `OWNED` |

Chaque cellule `FORBIDDEN` est prouvée avant lecture, écriture, migration,
claim, sauvegarde, restauration ou suppression. Une simple différence de
préfixe dans un stockage partagé n'est pas une preuve recevable.

## Ressources mutables couvertes

La source machine inventorie exhaustivement :

- les 27 coordonnées de configuration : identifiant de déploiement,
  PostgreSQL, Qdrant, files, outbox, progression, neuf racines de fichiers et
  cinq chemins de secrets ;
- le nom de projet Compose de chaque profil ;
- les cinq réseaux nommés de chaque profil ;
- les sept volumes nommés de chaque profil ;
- les deux montages de secrets Compose de chaque profil.

Les identifiants sont distincts entre les trois profils. Les racines résolues
ne se chevauchent pas. Les chemins de secrets sont des références ; leur
contenu n'est ni lu par cette matrice, ni versionné.

## Workers couverts

| Service | Réplicas attendus par profil | Identité obligatoire |
|---|---:|---|
| `worker-documents` | 2 | environnement, déploiement, hash de configuration |
| `worker-projection` | 2 | environnement, déploiement, hash de configuration |

Les quatre réplicas sont présents dans chacun des rapports réels. Un service
`worker-*` ajouté au Compose sans ajout simultané à la source machine rend la
gate statique RED.

`DEEP_RESEARCH`, `VERIFY_RESPONSE` et `BACKTEST` ne sont pas annoncés comme
actions asynchrones dans ces piles : aucune chaîne publique complète et
supervisée n'est encore câblée pour ces traitements. Les anciens conteneurs
d'attente sont absents plutôt que déclarés prêts sans consommation réelle.
