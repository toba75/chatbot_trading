# Runbook sauvegarde et restauration M-013

## Statut

- Identifiant : `M013-Runbook-BackupRestore-1.1`
- Politique : `M013-BackupRestoreDrill-1.1`
- Contrat : `M013-BackupManifest-1.1`
- ADR applicables : ADR-009, ADR-014, ADR-021, ADR-046, ADR-047,
  DDD-ADR-004, DDD-ADR-010.

ADR-047 remplace ADR-013 pour le contrat opérationnel. Le document historique
`docs/governance/m013_backup_restore_drill.md` décrit encore le drill 1.0 et ne
constitue pas une preuve d'archive restaurable 1.1.

## Scénario BDD

- Given une archive AES-256-GCM a déjà été produite avec son manifeste 1.1 et
  une clé brute de 32 octets conservée hors dépôt.
- When l'opérateur exécute `backup-v1`, puis `restore-v1` dans le profil
  propriétaire.
- Then les octets chiffrés, chaque entrée extraite, les identifiants stables et
  les propriétés de conservation sont contrôlés avant le premier GREEN.

## Préconditions obligatoires

- La pile du profil cible n'est pas requise au complet, mais ses autorités
  PostgreSQL et Qdrant doivent être démarrées, identifiées et accessibles par
  le réseau Compose du profil.
- Toutes les racines fichiers réellement montées dans `application-data`
  (`data`, corpus, sources canoniques, rapports, logs, expériences et cache)
  doivent porter l'identité du profil. Les volumes natifs PostgreSQL et Qdrant
  ne sont jamais contrôlés comme des répertoires de ce volume.
- Le manifeste, l'archive et le fichier de clé doivent exister. La clé est un
  fichier binaire de 32 octets situé hors du dépôt.
- L'archive ne dépasse pas 256 Mio, le manifeste 2 Mio et aucune entrée 64 Mio.
  Ces limites sont terminales; aucun format de secours n'est tenté.

## Vérifier la sauvegarde existante

`backup-v1` ne fabrique pas l'export : il vérifie une archive déjà produite.

```console
uv run --locked backup-v1 --manifest <manifest.json> --archive <backup.m013.aesgcm> --key-file <chemin-hors-depot-vers-cle-binaire> --config config/environments/<profil>.yaml
```

Le wrapper calcule la révision Git et la version courante du schéma PostgreSQL
avec le même code que le lanceur d'environnement. Il démarre un conteneur
administratif éphémère `orchestrator-api` dans le projet Compose du profil et
transmet les trois documents par un flux binaire cadré sur l'entrée standard.
La valeur de la clé n'apparaît ni dans les arguments, ni dans les variables
d'environnement, ni dans les logs.

L'ordre de vérification est strict :

1. identités natives PostgreSQL et Qdrant, puis identités des racines fichiers ;
2. `ciphertext_sha256` sur l'archive complète ;
3. tag et déchiffrement AES-256-GCM ;
4. ensemble exact des membres TAR ;
5. SHA-256 de chaque entrée extraite ;
6. contexte, catégorie, `stable_identifier`, autorité, immutabilité,
   projection régénérable et conservation négative ou supersédée.

Une sortie `Archive chiffrée V1 vérifiée` n'est publiée qu'après ces contrôles.

## Restaurer dans une cible isolée

```console
uv run --locked restore-v1 --manifest <manifest.json> --archive <backup.m013.aesgcm> --key-file <chemin-hors-depot-vers-cle-binaire> --target data/environments/<profil>/reports/restore-drills/<drill> --config config/environments/<profil>.yaml
```

La cible doit être absente ou vide et rester sous `reports/restore-drills` du
profil. La restauration écrit d'abord un staging. Chaque fichier est relu et
rehashé après écriture. `restore-proof.json` est écrit en dernier, puis le
staging est déplacé atomiquement vers la cible. En cas d'échec, le staging est
supprimé; un échec de compensation produit `RESTORE_COMPENSATION_FAILED`.

La preuve GREEN contient le hash du ciphertext, les hashes restaurés et la
liste des identifiants stables. Elle confirme la conservation des artefacts
immuables et des résultats négatifs ou supersédés à partir des octets extraits,
pas de booléens fournis par l'opérateur.

## Refus attendus

- archive absente : `ARCHIVE_REQUIRED` ;
- clé absente ou de taille différente de 32 octets :
  `ARCHIVE_KEY_REQUIRED` ou `ARCHIVE_KEY_SIZE_INVALID` ;
- clé située dans le dépôt : `ARCHIVE_KEY_INSIDE_REPOSITORY` ;
- archive altérée : `ARCHIVE_CIPHERTEXT_HASH_MISMATCH` ;
- mauvaise clé ou tag invalide : `ARCHIVE_DECRYPTION_FAILED` ;
- entrée manquante ou supplémentaire : `ARCHIVE_MEMBER_SET_INVALID` ;
- hash ou identifiant divergent : `ARCHIVE_ENTRY_HASH_MISMATCH` ou
  `ARCHIVE_STABLE_IDENTIFIER_MISMATCH`.

## Garde-fous

- Aucune restauration destructive.
- Aucune clé versionnée ou valeur de clé dans les sorties.
- Aucune donnée métier durable sur Spark.
- Qdrant reste une projection régénérable, pas une autorité métier.
- Aucun fallback de format, chiffrement ou cible.
- Le smoke Compose `validate-backup-restore-compose-live` utilise uniquement le
  profil `test`, exige qu'il soit initialement absent et supprime conteneurs et
  volumes en fin d'exécution.
