# Preuve de sauvegarde/restauration M13-environments

- Contrat opérationnel : `M013-BackupManifest-1.1`.
- Décision : ADR-047, qui remplace ADR-013.
- Gate unitaire : `test.m013-environments.validate-backup-restore-runtime-unit`.
- Smoke Compose : `test.m013-environments.validate-backup-restore-compose-live`.

Le smoke utilise une archive AES-256-GCM réelle contenant les dix catégories
d'artefacts V1, restaure ses octets dans une cible isolée du volume
`ostrading-test-application-data`, puis exige deux échecs terminaux : archive
altérée et clé erronée. Le projet `ostrading-test` doit être absent avant le
smoke; ses conteneurs et volumes sont supprimés et leur absence est vérifiée
après l'exécution.

La preuve n'affirme pas exporter les bases réelles. `backup-v1` reste le
vérificateur d'une archive déjà produite et refuse un manifeste seul.
