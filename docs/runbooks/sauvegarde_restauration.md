# Runbook sauvegarde et restauration M-013

## Statut

- Identifiant: `M013-Runbook-BackupRestore-1.0`
- Politique: `M013-BackupRestoreDrill-1.0`
- Contrat: `M013-BackupManifest-1.0`
- Tâche: `docs/tasks/milestone_013/0010_publier_runbooks_documentation_utilisateur.md`
- Preuve source: `docs/governance/m013_backup_restore_drill.md`
- ADR applicables: ADR-009, ADR-013, DDD-ADR-004, DDD-ADR-010
- ADR: non requise; ce runbook documente le drill T-007 sans créer une nouvelle politique de sauvegarde.

## Scénario BDD

- Given la V1 possède un drill de sauvegarde chiffrée et restauration testée.
- When l'utilisateur prépare une sauvegarde ou vérifie une restauration locale.
- Then le manifeste, la clé hors dépôt, la cible isolée et `restore_test_result` restent vérifiables avant toute décision d'acceptation.

## Sauvegarde

- Précondition: disposer d'un manifeste `M013-BackupManifest-1.0` produit avec l'archive chiffrée; une sauvegarde partielle ne peut pas être déclarée complète.
- Commande vérifiée:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\backup_v1.ps1 -Manifest .\restore\manifest.json
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_backup_restore.ps1
```

- Résultat attendu: `backup_v1.ps1` vérifie le manifeste de sauvegarde, la preuve `ciphertext_sha256`, les paires contexte/catégorie, les hashes non placeholders et l'absence de secret.
- Erreur explicite: si `scripts\backup_v1.ps1` ou `scripts\validate_m013_backup_restore.ps1` échoue, conserver la sortie RED et ne pas déclarer la sauvegarde exploitable.
- Preuve à conserver: sortie du contrôle de manifeste, sortie du validateur, `docs/governance/m013_backup_restore_drill.md`, identifiant `restore_test_result` et preuve `ciphertext_sha256` sans clé versionnée.

## Restauration

- Précondition: utiliser une cible de restauration isolée; aucune restauration destructive n'est autorisée sur l'instance locale courante.
- Commande vérifiée:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\restore_v1.ps1 -Manifest .\restore\manifest.json -Target C:\restore\m013-isolated
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_backup_restore.ps1
```

- Résultat attendu: `restore_v1.ps1` matérialise `restore-proof.json`, `restore_test_result` reste GREEN, les identifiants stables sont préservés, les artefacts immuables ne sont pas réécrits et les résultats négatifs ou supersédés restent consultables.
- Erreur explicite: si un hash restauré diverge, si une clé est suivie par Git ou si Spark devient requis pour restaurer les données métier, la restauration V1 est refusée.
- Preuve à conserver: sortie GREEN du validateur, liste des identifiants stables restaurés et mention de la cible isolée.

## Garde-fous

- Clé hors dépôt obligatoire.
- Aucune restauration destructive.
- Aucune donnée métier durable sur `spark-inference`.
- Qdrant reste une projection régénérable, pas une autorité métier.
- Fallback silencieux: interdit.
- Aucune commande de purge ou de suppression physique n'appartient à ce runbook.
