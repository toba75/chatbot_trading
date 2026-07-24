# Journal M14-local-pipeline - Pipeline documentaire local distribué

## Statut de planification

- Date : 2026-07-24.
- Statut : planifié, implémentation bloquée par la précondition P-001.
- Branche de planification : `master` au moment du prévol ; aucune branche
  d'implémentation ni aucun commit RED n'a été créé.
- Source canonique : `docs/specs/plan_distribution.md`, T-005 à T-008, et
  `docs/specs/plan_implementation_milestones_workstreams.md`, section
  `M14-local-pipeline`.
- Dossier : `docs/tasks/milestone_014-local-pipeline`.

## Prévol Git et dépendances

- `git fetch origin --prune` exécuté.
- `master` et `origin/master` sont alignés sur `665e2ae8f`, merge de la PR de
  M14-distribution-core.
- M-013, les sous-milestones M13 applicables et
  `docs/tasks/milestone_014-distribution-core` sont présents dans `master`.
- Le sous-milestone dépend de M14-distribution-core ; il ne clôt pas M-014 et ne
  débloque pas M14-local-qualification avant sa propre gate de sortie GREEN.

## Baseline observée

### Gate globale

- Commande : `uv run --locked gate`.
- Résultat : `PARTIAL RED`, 465 nœuds planifiés.
- Premier RED : `test.m004.validate-granite-gemma-recovery-unit`.
- Cause : `config/application.yaml`, fichier local ignoré par
  `.gitignore`, conserve `services.workers.granite_concurrency: 2`, alors que le
  schéma versionné exige `const: 1` depuis M14-distribution-core.
- Règle : le fichier local doit être réaligné explicitement et rester non
  versionné ; aucune exclusion de test ou configuration alternative ne vaut GREEN.

### Scope M14-distribution-core

- Commande : `uv run --locked gate --scope m014_distribution_core`.
- Résultat : `PARTIAL RED`, 36 nœuds planifiés.
- RED :
  `test.m014-distribution-core.validate-distribution-decision-unit`.
- Erreur : `M014_DISTRIBUTION_ADR_051_CHANGED`.
- Empreinte ADR-051 observée :
  `2e81990a61b956f63f903b671dcf64acd494e90ad856f4130d67a8d07003d6e1`.
- Empreinte encore attendue par le validateur :
  `70d219179c703b36b44b877cace124e6aa671364e857a06f411c05c89d18183d`.
- Cause versionnée : ADR-051 acceptée porte désormais le lien réciproque
  explicite vers ADR-052, mais le validateur M14-core n'a pas été réaligné.
- Règle : corriger le validateur et ses tests sans réécrire le sens d'ADR-051 ou
  d'ADR-052 ; obtenir le scope M14-core puis la gate globale GREEN avant P-002.

## Cadrage DDD retenu

- SP reste propriétaire de `DocumentProcessingRun`, du manifeste, des routes,
  des résultats de pages, de la progression et de la publication canonique.
- `platform` reste propriétaire de la file technique, des claims, des slots
  Granite, des enveloppes de complétion et de leur acquittement.
- KA reste propriétaire de `KnowledgeProjection`, de son outbox et de la
  génération Qdrant régénérable.
- Les transactions fortes ne traversent jamais ces propriétaires ; outbox,
  relais et consommateurs idempotents réalisent les échanges.
- Le pipeline conserve l'action publique `CONVERT_DOCUMENT`, un total persistant
  figé, une version canonique unique et la progression publique issue
  exclusivement des stockages propriétaires.

## Découpage exécutable

| Fichier | Source | Comportement |
|---|---|---|
| `0001_verifier_precondition_green.md` | Précondition de tranche | Fermer les RED local et versionné, puis prouver la baseline GREEN. |
| `0002_publier_specification_pipeline_local_distribue.md` | Spécification DDD | Publier contrats de comportement, propriétaires, états, erreurs et gate dédiée. |
| `0003_eclater_conversion_en_jobs_pages.md` | T-005 | Figer le manifeste, persister `SKIP_EMPTY` et fan-out transactionnel. |
| `0004_executer_persister_page_fenced.md` | T-006 | Réclamer, convertir, compléter et persister une page sous fencing. |
| `0005_assembler_publier_document_canonique.md` | T-007 | Assembler, contrôler et publier une version canonique unique. |
| `0006_projeter_document_publie_localement.md` | T-008 | Consommer la publication et rendre une projection locale unique recherchable. |

## Séquence obligatoire

```text
P-001 précondition GREEN
  -> P-002 spécification et scope RED/GREEN
  -> T-005 fan-out pages RED/GREEN
  -> T-006 résultats fenced RED/GREEN
  -> T-007 assemblage canonique RED/GREEN
  -> T-008 projection locale RED/GREEN
```

- Chaque tâche fonctionnelle commence par une baseline GREEN.
- Chaque commit RED contient uniquement le scénario, la spécification utile et
  les tests qui échouent pour la raison attendue.
- Chaque commit GREEN contient l'implémentation stricte minimale et les
  ajustements de tests requis.
- Une tâche ne commence pas tant que les gates de sa dépendance ne sont pas GREEN.

## Gate de sortie attendue

- Deux workers locaux peuvent réclamer des pages distinctes du même traitement.
- Un crash et une redélivrance ne créent ni doublon, ni progression additionnelle.
- Une page manquante, échouée ou divergente interdit toute publication.
- Une version canonique complète et un événement de publication existent une
  seule fois.
- Une seule projection locale de cette version devient `SEARCHABLE` dans le
  Qdrant du même environnement.
- Les scopes `m004`, `m005`, `m013_environments`,
  `m014_distribution_core`, `m014_local_pipeline` et la gate globale sont GREEN.
- La qualification GPU, les opérations, l'observabilité de capacité et la
  campagne de cent PDF restent hors périmètre, réservées à
  M14-local-qualification T-009 à T-011.
