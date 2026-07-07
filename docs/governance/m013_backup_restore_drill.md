# Exercice sauvegardes chiffrées et restauration M-013

## Statut

- Identifiant: `M013-BACKUP-RESTORE-DRILL-0001`
- Politique: `M013-BackupRestoreDrill-1.0` / `BackupRestorePolicy`
- Contrat de manifeste: `M013-BackupManifest-1.0`
- Tâche: `docs/tasks/milestone_013/0007_valider_sauvegardes_chiffrees_restauration.md`
- ADR applicables: ADR-009, ADR-013, DDD-ADR-004, DDD-ADR-010
- ADR: ADR-013 créée; T-007 introduit un contrat durable de manifeste de sauvegarde et restauration sans remplacer le Spark sans état métier, Qdrant projection régénérable ni la conservation des versions négatives et supersédées.

## Scénario BDD

- Given une instance V1 contient corpus, versions canoniques, claims, réponses, conversations, stratégies, expériences, décisions et écarts V1.
- When une sauvegarde chiffrée est restaurée dans une cible locale isolée.
- Then les identifiants stables, artefacts immuables, résultats négatifs et décisions restent vérifiables sans secret en clair ni stockage métier sur Spark.

## Contrat de manifeste

Le manifeste `M013-BackupManifest-1.0` est la preuve versionnée de périmètre et d'intégrité. Il déclare pour chaque entrée: contexte propriétaire, catégorie d'artefact, identifiant stable, hôte de stockage, statut d'autorité, statut de projection régénérable, hash sauvegardé, hash restauré et preuve de conservation.

- Commande de sauvegarde: `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\backup_v1.ps1 -Manifest .\restore\manifest.json`
- Commande de restauration: `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\restore_v1.ps1 -Manifest .\restore\manifest.json -Target C:\restore\m013-isolated`
- Cible: cible locale isolée.
- Chiffrement: archive chiffrée requise avec preuve `ciphertext_sha256`.
- Clé: clé hors dépôt, jamais versionnée, sans valeur de secret publiée.
- Résultat requis: `restore_test_result`.

## Périmètre restaurable V1

| Contexte | Catégorie | Autorité | Projection régénérable | Hôte restauré | Preuve |
|---|---|---|---|---|---|
| `SP` | corpus original et versions canoniques | oui | non | `docker-local` | identifiants `SRC-M013-BACKUP-001` et `CANON-M013-BACKUP-001`, hash sauvegardé égal au hash restauré |
| `KA` | projection Qdrant | non | oui | `docker-local` | projections régénérables non autorité, reconstruction depuis version canonique |
| `EG` | registre de claims | oui | non | `docker-local` | claims rejetés et relations conservés |
| `RA` | réponses vérifiées | oui | non | `docker-local` | réponses supersédées consultables |
| `CV` | conversations | oui | non | `docker-local` | tours append-only restaurés avec identifiants stables |
| `SD` | snapshots de stratégie | oui | non | `docker-local` | stratégies invalides conservées |
| `EX` | résultats d'expériences | oui | non | `docker-local` | expériences échouées et résultats défavorables conservés |
| `EV` | rapports d'évaluation et écarts V1 | oui | non | `docker-local` | décisions d'écarts V1 conservées |
| `platform` | gouvernance, ADR et manifeste | oui | non | `docker-local` | preuves M-013 et commandes restaurées |

## Résultat de restauration

- `restore_test_result`: GREEN.
- Hashes: chaque hash restauré est égal au hash sauvegardé.
- Identifiants stables: chaque identifiant stable listé par le manifeste reste présent après restauration.
- Artefacts immuables: corpus, versions canoniques, claims, réponses, snapshots, expériences, rapports et ADR ne sont pas modifiés en place.
- Historique défavorable: résultats négatifs et supersédés conservés.
- Projections: projections régénérables non autorité et reconstruisibles depuis les artefacts restaurés.
- Spark: aucune donnée métier sur Spark; le Spark n'est pas requis pour restaurer corpus, bases, index, expériences, décisions ou rapports.
- Secrets: aucun secret en Git, aucune clé versionnée, aucun certificat privé publié.
- Sécurité opérationnelle: restauration destructive interdite et sauvegarde partielle déclarée complète interdite.

## Contrôles T-007

| Contrôle | Invariant | Preuve |
|---|---|---|
| CTRL-M013-BACKUP-001 | manifeste complet obligatoire | Tous les contextes SP, KA, EG, RA, CV, SD, EX, EV et `platform` sont listés. |
| CTRL-M013-BACKUP-002 | archive chiffrée requise | Le manifeste porte une preuve `ciphertext_sha256` sans clé publiée. |
| CTRL-M013-BACKUP-003 | clé hors dépôt | Le champ de clé référence `hors_depot://cle-restauration/m013` sans secret versionné. |
| CTRL-M013-BACKUP-004 | aucun secret en Git | Le drill ne contient aucun mot de passe, clé API, token bearer ou clé privée. |
| CTRL-M013-BACKUP-005 | hashes restaurés vérifiés | Chaque entrée porte un hash sauvegardé et un hash restauré identiques. |
| CTRL-M013-BACKUP-006 | identifiants stables préservés | Les identifiants restaurés restent ceux du manifeste. |
| CTRL-M013-BACKUP-007 | résultats négatifs et supersédés conservés | EG, RA, SD, EX et EV restent consultables après restauration. |
| CTRL-M013-BACKUP-008 | projections régénérables non autorité | KA/Qdrant est restaurable ou reconstruisible, sans devenir source métier. |
| CTRL-M013-BACKUP-009 | aucune donnée métier sur Spark | `spark-inference` ne contient aucun corpus, base, claim, conversation, stratégie, expérience ou rapport. |
| CTRL-M013-BACKUP-010 | restauration destructive interdite | La restauration isolée ne remplace pas silencieusement un état local existant. |
| CTRL-M013-BACKUP-011 | commande et traçabilité requises | `restore_test_result` référence la commande de restauration et les preuves M-013. |

## Commandes de preuve

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_backup_restore_acceptance.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_backup_restore_unit.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_backup_restore.ps1
```
