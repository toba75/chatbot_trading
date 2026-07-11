# ADR-017 - PDF sources suivis par Git LFS

**Statut :** Acceptée
**Date :** 2026-07-11
**Décideurs :** Propriétaire du projet
**Remplace :** Aucun
**Remplacée par :** Aucune
**Source :** Demande utilisateur du 2026-07-11; ADR-001; `docs/specs/plan_remediation_m13.md`

## Contexte

Le corpus réel contient des livres PDF dont la taille rend leur stockage direct dans les objets Git coûteux. ADR-001 impose néanmoins de conserver le PDF original immuable comme artefact faisant autorité. Le dépôt doit donc versionner les originaux sans incorporer leur contenu binaire complet dans chaque objet Git ordinaire.

## Scénario BDD

- Given un PDF original est ajouté au corpus du dépôt.
- When Git prépare ce fichier pour un commit.
- Then le chemin est versionné dans Git et le contenu binaire est stocké par Git LFS au moyen d'un pointeur explicite, sans traitement texte ni fallback vers Git ordinaire.

## Décision

- Le dépôt **DOIT** suivre tous les fichiers `*.pdf` avec Git LFS au moyen de la règle `*.pdf filter=lfs diff=lfs merge=lfs -text` dans `.gitattributes`.
- Les PDF originaux **DOIVENT** conserver leur chemin versionné dans Git; leur contenu binaire **DOIT** être stocké dans le magasin Git LFS.
- Les manifestes, métadonnées, configurations et artefacts textuels **DOIVENT** rester dans Git ordinaire.
- Une installation Git LFS absente ou une erreur de transfert **NE DOIT PAS** déclencher un stockage ou un téléchargement alternatif silencieux.
- Cette décision **NE MODIFIE PAS** l'historique Git antérieur; une migration d'historique nécessiterait une décision et une opération explicites distinctes.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Ne pas versionner les PDF | Rejetée | Empêche le dépôt de référencer un corpus réel reproductible par chemin et révision. |
| Stocker les PDF directement dans Git | Rejetée | Gonfle durablement les objets et les clones Git. |
| Stocker les PDF avec Git LFS | Retenue | Préserve le versionnement des chemins et délègue les binaires volumineux au stockage prévu à cet effet. |

## Conséquences

### Positives

- Le corpus PDF peut être versionné sans alourdir chaque clone avec tout l'historique binaire Git ordinaire.
- Les pointeurs LFS identifient explicitement le contenu par empreinte.
- Les originaux restent associés à une révision du dépôt.

### Négatives ou coûts

- Chaque poste et la CI doivent disposer de Git LFS.
- Le serveur Git distant doit accepter et conserver les objets LFS.
- Le clone du dépôt ne suffit pas si les objets LFS distants sont indisponibles.

### Risques et contrôles

- Risque: commit d'un PDF hors LFS. Contrôle: test d'acceptation de `.gitattributes` et contrôle `git lfs ls-files` avant publication.
- Risque: quota LFS distant insuffisant. Contrôle: échec explicite du push; aucun fallback vers Git ordinaire.
- Risque: réécriture accidentelle de l'historique. Contrôle: aucune commande `git lfs migrate` dans cette décision.

## Impact d'implémentation

- Modules concernés: gouvernance du dépôt et corpus SP.
- Configuration concernée: `.gitattributes` et configuration Git LFS locale.
- Tests attendus: `tests/governance/validate_git_lfs_acceptance.ps1`.
- Milestones concernées: M13-reality, traitement du corpus PDF réel.

## Liens de traçabilité

- Spécification: `docs/specs/plan_remediation_m13.md`, corpus réel et PDF original immuable.
- Plan d'implémentation: M13-reality, déclaration et traitement du corpus réel.
- Tests d'acceptation: `tests/governance/validate_git_lfs_acceptance.ps1`.
- Commits: commit RED du test d'acceptation; commit GREEN de la configuration Git LFS.

## Notes

ADR-001 reste la décision canonique sur l'autorité du PDF original et du `DoclingDocument`; ADR-017 définit uniquement le mécanisme de versionnement des binaires PDF dans ce dépôt.
