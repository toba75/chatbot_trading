# ADR-047 - Archive chiffrée vérifiée avant preuve de restauration

**Statut :** Acceptée
**Date :** 2026-07-22
**Décideurs :** Propriétaire du projet
**Remplace :** ADR-013
**Remplacée par :** Aucune
**Source :** Revue de clôture `M13-environments`

## Contexte

ADR-013 imposait un manifeste, un chiffrement et des hashes, mais son contrat
`M013-BackupManifest-1.0` permettait à l'outil d'exploitation de valider les
déclarations d'un manifeste sans lire l'archive correspondante. La
restauration matérialisait alors des fichiers de preuve à partir des seules
valeurs déclarées. Une archive absente, altérée ou chiffrée avec une autre clé
pouvait donc ne jamais être confrontée aux preuves publiées.

La correction doit rester compatible avec ADR-009, ADR-014, ADR-021,
ADR-046, DDD-ADR-004 et DDD-ADR-010. Elle ne transforme pas `backup-v1` en
outil d'export des autorités : cette commande vérifie une archive déjà produite.

## Décision

Le contrat d'exploitation DOIT être `M013-BackupManifest-1.1`.

`backup-v1` et `restore-v1` DOIVENT recevoir explicitement un manifeste, une
archive AES-256-GCM et un fichier de clé brute de 32 octets. L'archive et la clé
DOIVENT exister et respecter les limites de taille avant tout appel Compose.
Aucune valeur de clé NE DOIT apparaître dans les arguments, variables
d'environnement, logs ou fichiers versionnés.

Le wrapper hôte DOIT transmettre manifeste, archive et clé à un conteneur
administratif du profil via un flux binaire cadré, versionné et borné. Il DOIT
injecter exactement les variables techniques calculées par le lanceur Compose,
dont la révision Git et la version courante du schéma PostgreSQL.

Avant de déclarer une archive vérifiée, l'outil DOIT contrôler successivement :

1. l'identité native PostgreSQL, l'identité native Qdrant et les racines
   fichiers réellement montées dans `application-data` ;
2. le SHA-256 exact du ciphertext ;
3. l'authenticité AES-256-GCM et la capacité à déchiffrer avec la clé fournie ;
4. la sûreté et l'exhaustivité des membres de l'archive ;
5. le SHA-256 extrait de chaque entrée ;
6. l'identifiant stable, le contexte, la catégorie, l'immutabilité et la
   conservation négative ou supersédée portés par chaque entrée.

`restore-v1` DOIT restaurer dans un staging isolé. Il NE DOIT publier
`restore_test_result=GREEN` et déplacer le staging vers la cible finale
qu'après tous les contrôles. Une archive absente ou altérée, une clé incorrecte,
un membre supplémentaire, manquant ou divergent rend l'opération terminalement
RED. Qdrant reste une projection régénérable non autoritaire.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Continuer à vérifier le manifeste seul | Rejetée | Une déclaration cohérente ne prouve ni l'existence ni la restaurabilité des octets. |
| Accepter un chiffrement optionnel ou plusieurs formats | Rejetée | Introduit un fallback et une ambiguïté d'exploitation. |
| Vérifier une archive AES-256-GCM réelle avec un contrat 1.1 | Retenue | Authentifie les octets et relie chaque preuve au contenu effectivement extrait. |

## Conséquences

### Positives

- Aucun GREEN n'est possible sans archive réelle et clé correcte.
- L'intégrité du ciphertext et de chaque entrée extraite est vérifiable.
- Les preuves de conservation et d'identifiants stables proviennent des octets restaurés.

### Négatives ou coûts

- Une dépendance cryptographique explicite et verrouillée est requise.
- L'export initial des autorités reste une opération distincte à fournir par l'exploitant.
- Le transport Compose impose des limites maximales documentées.

### Risques et contrôles

- Risque : exposition de la clé. Contrôle : fichier hors dépôt, permissions
  temporaires restrictives, transport par entrée standard et suppression garantie.
- Risque : traversée de chemins TAR. Contrôle : membres réguliers, noms exacts
  déclarés et extraction contrôlée sans `extractall`.
- Risque : preuve partielle. Contrôle : égalité exacte entre membres déclarés et extraits.

## Impact d'implémentation

- Modules concernés : `ost_gate/operations/backup.py`,
  `ost_gate/operations/restore.py`, `ost_gate/operations/backup_manifest.py`,
  `ost_gate/operations/encrypted_archive.py`, `app/platform/configured_datastore_identity.py`.
- Configuration concernée : aucune clé dans YAML ou variable d'environnement.
- Tests attendus : tests unitaires du runtime d'archive et smoke Compose borné.
- Milestones concernées : M-013, `M13-environments`.

## Liens de traçabilité

- Spécification : `docs/specs/m013_environments_environnements_explicites.md`.
- Plan d'implémentation : `docs/tasks/milestone_013-environments/0012_cloturer_gouvernance_runbooks_gates.md`.
- Tests d'acceptation : `gate_tests/ported/tests/m013_environments/validate_backup_restore_runtime_unit.py` et `validate_backup_restore_compose_live.py`.
- Commits : `test(m13-environments): couvrir archive chiffrée réelle`; `fix(m13-environments): vérifier archive avant restauration`.

## Notes

ADR-047 remplace explicitement ADR-013 sans modifier ADR-014 ni ADR-046.
