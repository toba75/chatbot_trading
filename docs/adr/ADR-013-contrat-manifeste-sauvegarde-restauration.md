# ADR-013 - Contrat de manifeste de sauvegarde et restauration

**Statut :** Remplacée
**Date :** 2026-07-08
**Décideurs :** Propriétaire du projet
**Remplace :** Aucun
**Remplacée par :** ADR-047
**Source :** `docs/tasks/milestone_013/0007_valider_sauvegardes_chiffrees_restauration.md`

## Contexte

M-013 doit prouver qu'une instance V1 personnelle reste exploitable après un incident local. Cette preuve traverse les contextes SP, KA, EG, RA, CV, SD, EX, EV et `platform`, mais le drill ne doit pas devenir propriétaire de leurs données métier.

Les décisions existantes imposent déjà que le Spark ne conserve pas d'état métier durable (ADR-009), que Qdrant reste une projection régénérable (DDD-ADR-004) et que les versions négatives ou supersédées restent consultables (DDD-ADR-010). T-007 introduit un contrat de manifeste durable pour rendre ces obligations vérifiables pendant la restauration.

## Décision

Le projet DOIT utiliser un manifeste de sauvegarde versionné `M013-BackupManifest-1.0` pour tout drill d'acceptation V1.

Le manifeste DOIT lister chaque catégorie durable restaurable avec son contexte propriétaire, son identifiant stable, son hôte de stockage, son statut d'autorité ou de projection régénérable, son hash sauvegardé et son hash restauré.

La sauvegarde DOIT être chiffrée avant d'être déclarée complète. Le manifeste DOIT fournir une preuve de chiffrement sans publier de clé, passphrase, secret, certificat privé ou valeur complète de token.

La clé de restauration DOIT rester hors dépôt. Aucun chemin, fichier ou champ versionné NE DOIT contenir de matériel de clé en clair.

La restauration DOIT s'exécuter dans une cible locale isolée et produire `restore_test_result` avant toute acceptation V1. Ce résultat DOIT prouver l'égalité des hashes restaurés, la préservation des identifiants stables, la conservation des artefacts immuables et la consultation des résultats négatifs ou supersédés.

Le Spark NE DOIT PAS contenir de donnée métier restaurable. Les projections régénérables, dont Qdrant, NE DOIVENT PAS être traitées comme autorité métier et DOIVENT pouvoir être reconstruites depuis les artefacts d'autorité restaurés.

Une restauration destructive, partielle déclarée complète ou silencieuse est interdite.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Sauvegarde chiffrée sans manifeste versionné | Rejetée | Ne prouve pas le périmètre restauré, les hashes ni les exclusions Spark. |
| Manifeste versionné et drill local isolé | Retenue | Rend le périmètre, l'intégrité, la restauration et les garde-fous auditables par gate. |
| Snapshot Spark inclus dans la sauvegarde métier | Rejetée | Contredit ADR-009 et introduit un second plan de données durable. |

## Conséquences

### Positives

- Le périmètre restaurable V1 devient testable sans ambiguïté.
- Les preuves d'intégrité sont liées aux identifiants stables et aux contextes propriétaires.
- Les projections peuvent être reconstruites sans devenir sources de vérité.

### Négatives ou coûts

- Chaque nouvelle catégorie durable V1 doit être ajoutée explicitement au manifeste.
- Les procédures d'exploitation doivent conserver une preuve de restauration, pas seulement une preuve d'archive.

### Risques et contrôles

- Risque: clé ou secret exposé dans le dépôt. Contrôle: validateur T-007 et motifs interdits.
- Risque: sauvegarde partielle déclarée complète. Contrôle: couverture obligatoire des contextes V1.
- Risque: restauration qui écrase l'historique défavorable. Contrôle: conservation vérifiée des résultats négatifs et supersédés.
- Risque: projection Qdrant traitée comme autorité. Contrôle: statut `regenerable_projection` obligatoire et source d'autorité séparée.

## Impact d'implémentation

- Modules concernés: `app/platform/backup_restore.py`.
- Configuration concernée: aucune valeur de secret versionnée; clé de restauration hors dépôt.
- Tests attendus: `tests/m013/validate_backup_restore_acceptance.ps1`, `tests/m013/validate_backup_restore_unit.ps1`, `scripts/validate_m013_backup_restore.ps1`.
- Milestones concernées: M-013.

## Liens de traçabilité

- Spécification: `docs/specs/m013_durcissement_acceptation_v1.md`, comportement V1-006.
- Plan d'implémentation: `docs/tasks/milestone_013/0007_valider_sauvegardes_chiffrees_restauration.md`.
- Tests d'acceptation: `tests/m013/validate_backup_restore_acceptance.ps1`.
- Commits: `test(m013): couvrir restauration sauvegardes`; `feat(m013): valider sauvegardes restauration`.

## Notes

ADR-013 précise le contrat de preuve de sauvegarde et restauration sans remplacer ADR-009, DDD-ADR-004 ni DDD-ADR-010.
