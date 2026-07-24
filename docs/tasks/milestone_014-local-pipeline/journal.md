# Journal M14-local-pipeline - Pipeline documentaire local distribué

## Statut de planification

- Date : 2026-07-24.
- Statut : P-001 et P-002 GREEN ; T-005 peut commencer, sans comportement
  T-005 à T-008 encore implémenté.
- Branche d'implémentation : `codex/m14-local-pipeline` ; le cycle RED/GREEN de
  P-002 est documenté ci-dessous.
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

## 2026-07-24 - P-001 précondition GREEN du pipeline local

- Références Git avant correction : branche `codex/m14-local-pipeline` au commit
  `5b41e160c1c3441b2b623cb5dfa165606e23b1d4` ; `master` et `origin/master`
  alignés sur `665e2ae8f3b8158833891f3e2602d37b2ae5a1a7` ;
  `git rev-list --left-right --count master...origin/master` retourne `0 0`.
- Les arbres de `master` confirment la présence de M-013,
  `docs/tasks/milestone_014-distribution-core`, des ADR, du code applicatif et
  des tests de gate requis.
- RED amont reproduit avant correction : `uv run --locked gate --scope m004`
  planifie 45 nœuds et termine `PARTIAL RED` sur
  `test.m004.validate-granite-gemma-recovery-unit`, avec
  `CONFIG_SCHEMA_INVALID` à
  `application.services.workers.granite_concurrency` car la valeur locale `2`
  diffère de la constante `1`.
- RED M14-core reproduit avant correction :
  `uv run --locked gate --scope m014_distribution_core` planifie 36 nœuds et
  termine `PARTIAL RED` sur
  `test.m014-distribution-core.validate-distribution-decision-unit`, erreur
  `M014_DISTRIBUTION_ADR_051_CHANGED`.
- Le fichier local `config/application.yaml` a été explicitement réaligné sur
  le profil `development` avec `granite_concurrency: 1`. Le quota versionné
  reste `granite_slots_global: 2` et `granite_slots_per_worker: 1`.
  `git check-ignore -v config/application.yaml` confirme la règle
  `.gitignore:19:/config/application.yaml` et la commande
  `git ls-files config/application.yaml` ne retourne aucun chemin : le fichier
  reste local et absent du commit.
- Le validateur M14-core accepte désormais l'empreinte actuelle
  `2e81990a61b956f63f903b671dcf64acd494e90ad856f4130d67a8d07003d6e1`
  d'ADR-051. Il exige en plus les métadonnées et la note qui bornent le
  remplacement partiel par ADR-052 à M-014, avant de contrôler l'intégrité du
  document complet.
- Le test unitaire refuse séparément la suppression des métadonnées, la
  suppression de la note de réciprocité et toute autre mutation du document.
  Le test ciblé RED est celui déjà présent au prévol ; aucun commit RED
  artificiel n'a été créé.
- Validations finales : tests ADR ciblés 2/2 GREEN ; Ruff ciblé GREEN ;
  `git diff --check` GREEN ; scope `governance` 25/25 GREEN ; scope `m004`
  45/45 GREEN ; scope `m014_distribution_core` 36/36 GREEN ; gate canonique
  465/465 GREEN, aucune absence, surprise ou duplication, sortie terminale
  `PARTIAL GREEN: offline` avec code 0.
- ADR consultées : ADR-051 et ADR-052. ADR créée ou modifiée : aucune ; la
  correction valide leur lien réciproque sans en changer le sens.
- Commit GREEN prévu : `fix(m014-core): realigner preuve reciproque ADR-051`.

## 2026-07-24 - P-002 spécification du pipeline local distribué

- Sous-agent : `/root/m14_p002_specification`, chargé exclusivement de P-002
  par l'orchestrateur du milestone.
- Baseline initiale : arbre propre sur `5433a1ab1`, résultat P-001 465/465,
  code 0, sortie terminale `PARTIAL GREEN: offline`. Une invocation courte a
  expiré sans verdict ; elle n'a pas été interprétée comme un RED. L'invocation
  déjà active a ensuite été attendue jusqu'au même verdict terminal 465/465.
- Scénario BDD : un manifeste SP figé est distribué entre deux workers locaux,
  les complétions fenced sont persistées chez leur propriétaire, une seule
  version canonique complète est publiée puis KA projette cette publication
  dans l'environnement concordant.
- RED utile : les tests d'acceptation et unitaires échouaient à la collecte sur
  `ModuleNotFoundError: No module named 'ost_gate.m014_local_pipeline'`.
  Commit RED : `303eed36a` —
  `test(m014-pipeline): exiger specification pipeline local distribue`.
- GREEN documentaire : `docs/specs/m014_local_pipeline_documentaire_distribue.md`
  fixe mission, langage, propriétaires, invariants, machines d'états, ports,
  enveloppes, erreurs, scénarios DIST-003 à DIST-005, ordre des transactions
  ADR-024, activation et rollback. Le validateur
  `ost_gate/m014_local_pipeline.py` refuse huit dérives sémantiques :
  propriétaire absent, total mutable, transaction intercontexte, progression
  synthétique, assemblage ou projection prématurés, fallback de route et
  environnement ambigu.
- Scope : `gate.toml` enregistre uniquement la précondition
  `precondition.m014_local_pipeline` et les deux tests de spécification. Aucun
  test d'implémentation T-005 à T-008 n'est encore enregistré.
- Fichiers ajoutés : spécification, validateur, précondition et deux tests sous
  `gate_tests/ported/tests/m014_local_pipeline/`. Fichiers modifiés :
  `gate.toml` et le présent journal.
- ADR consultées : ADR-024, ADR-025, ADR-052 et DDD-ADR-008. ADR créée ou
  modifiée : aucune ; P-002 applique leurs décisions sans en changer le sens.
- Validations avant commit GREEN : tests ciblés 2/2 GREEN ; Ruff ciblé GREEN ;
  `git diff --check` GREEN ; scope `governance` 25/25 GREEN ; scope
  `m014_local_pipeline` 27/27 GREEN, sans nœud absent, inattendu ou dupliqué.
- Commit GREEN : `docs(m014-pipeline): publier specification pipeline local distribue`
  (commit portant cette entrée). La gate globale finale doit être exécutée une
  seule fois après ce commit et son verdict terminal transmis à l'orchestrateur.

## 2026-07-24 - T-005 fan-out transactionnel des pages

- Sous-agent : `/root/m14_t005_fanout`, chargé exclusivement de T-005 par
  l'orchestrateur du milestone.
- Baseline initiale : commit `f90cfe505`, gate canonique 468/468 GREEN, code 0.
  Cette preuve transmise par l'orchestrateur n'a pas été rejouée au démarrage.
- Scénario BDD : un traitement SP de quatre pages, dont une `SKIP_EMPTY`,
  active explicitement `m014-page-fanout-v1` ; le premier fan-out persiste un
  résultat vide et trois enveloppes `CONVERT_PAGE`, puis le rejeu exact ne crée
  aucun doublon et n'exécute aucun convertisseur.
- RED utile : les tests unitaires, d'acceptation et PostgreSQL échouaient à la
  collecte sur l'absence du cas d'usage
  `app.source_processing.application.fan_out_document_pages`. Commit RED :
  `2a4cce8b4` —
  `test(m014-pipeline): couvrir fan-out transactionnel des pages`.
- GREEN applicatif : `PageFanOutPlan` fige le manifeste, les actifs et les
  contrats de page ; `FanOutDocumentPagesHandler` exige l'activation explicite,
  conserve l'ordre PDF, matérialise `SKIP_EMPTY` sans artefact ni métrique et
  produit les jobs réclamables sans appeler de convertisseur.
- Persistance : la migration 023 classe explicitement l'existant sous
  `m004-inline-v1`, ferme le discriminateur de parcours et ajoute le registre
  immuable du fan-out. Une transaction locale SP verrouille la demande, écrit
  le plan, les résultats vides, l'outbox et la progression publique. Le relais
  reconstruit les exigences d'exécution de `CONVERT_PAGE` avant l'insertion
  idempotente dans la file propriétaire `platform` ; aucune transaction
  intercontextes n'est créée.
- Preuve PostgreSQL réelle : migration 022 vers 023, refus de bascule d'une
  demande historique, crash injecté sur la deuxième enveloppe puis rollback
  total, rejeu exact, trois jobs relayés sans doublon, divergence d'actif et
  environnement étranger refusés. Résultat ciblé : 1/1 GREEN.
- Compatibilité : les preuves M14-core propres à la migration 022 bornent
  désormais explicitement leur corpus aux migrations 001 à 022. Les tests
  ciblés du fan-out sont 3/3 GREEN et Ruff ciblé est GREEN.
- Scopes avant commit GREEN : `m004` 45/45 GREEN ; `m013_environments` 49/49
  GREEN ; `m014_distribution_core` 36/36 GREEN ; `m014_local_pipeline` 29/29
  GREEN en mode partiel hors live, complété par la preuve PostgreSQL réelle.
  Les nœuds attendus sont présents une seule fois et aucune surprise n'est
  signalée.
- Fichiers ajoutés : cas d'usage du fan-out, migration 023 et trois preuves
  T-005. Fichiers modifiés : contrats de distribution, commande documentaire,
  persistance et relais PostgreSQL, manifeste de gate, spécification M14,
  validateur sémantique, deux preuves de compatibilité M14-core et le présent
  journal.
- ADR consultées : ADR-024, ADR-025 et ADR-052. ADR créée ou modifiée : aucune ;
  T-005 applique leur ordre de transactions et leur déploiement local sans en
  changer le sens.
- Commit GREEN prévu :
  `feat(m014-pipeline): eclater conversion en jobs de pages`. La gate globale
  finale sera exécutée une seule fois après ce commit avec un délai d'une heure ;
  toute sortie différée sera attendue sur la même exécution, sans relance.

## 2026-07-24 - T-006 exécution et résultat de page sous fencing

- Sous-agent : `/root/m14_t006_page_fenced`, chargé exclusivement de T-006 par
  l’orchestrateur du milestone.
- Baseline initiale réutilisée sans relance : commit T-005 `8336dd92e`, arbre
  propre, gate canonique 470/470 GREEN, code 0. Cette preuve constitue la
  précondition T-006 ; aucune gate globale n’a été démarrée avant le commit
  GREEN.
- Scénario BDD : deux workers réclament une page standard et une page Granite ;
  après expiration du premier claim Granite, le second reprend la page, produit
  l’unique enveloppe admissible et les redélivrances n’incrémentent jamais deux
  fois la progression SP.
- RED utile : les preuves unitaires et d’acceptation échouaient à la collecte
  sur l’absence de `execute_document_page` et du relais de complétion.
  Commit RED : `73b99c530` —
  `test(m014-pipeline): couvrir resultat de page fenced`.
- Exécution : `CONVERT_PAGE` est une capacité explicite des deux replicas
  généralistes `worker-documents`. La boucle réclame séparément le contrat
  standard sans slot et le contrat Granite avec acquisition atomique du claim
  et du slot. Les convertisseurs M-004 existants restent l’unique autorité des
  routes ; Granite est supervisé sous le couple claim-slot actif et aucun
  changement de route ou fallback CPU n’est introduit.
- Artefacts et contrats : la source locale est résolue sous la racine du profil,
  lue immuablement et vérifiée par SHA-256 avant tout convertisseur. Le résultat
  porte le claim, le worker, le slot seulement pour Granite, l’outil, les
  métriques et soit un artefact immutable, soit une erreur terminale fermée.
- Frontières transactionnelles : `platform` crée d’abord l’enveloppe immutable
  et terminalise le job sous fencing. Le relais claim cette enveloppe dans une
  transaction `platform`, appelle ensuite SP, où résultat et progression sont
  persistés dans une seule transaction, puis acquitte l’enveloppe dans une
  transaction `platform` séparée. Il ne marque jamais `relayed` avant le commit
  SP.
- Preuve PostgreSQL réelle : deux claims concurrents standard/Granite, ancienne
  lease et ancien slot expirés, reprise avec génération 2, ancien détenteur
  refusé avec `JOB_LEASE_LOST`, route standard sans slot, résultat Granite avec
  slot, échec stable `ARTIFACT_HASH_MISMATCH`, crash après commit SP avant ACK,
  redélivrance idempotente et progression finale 4/4 sans double comptage.
- Compatibilité M-013 : les deux preuves qui fermaient historiquement les jobs
  de `worker-documents` à `DIAGNOSE` et `CONVERT_DOCUMENT` attendent désormais
  aussi `CONVERT_PAGE`, puisque la chaîne réelle est composée et supervisée.
- Validations avant commit GREEN : tests ciblés T-006 3/3 GREEN, dont PostgreSQL
  réel ; preuve de métriques M14-core GREEN ; Ruff ciblé GREEN ;
  `git diff --check` GREEN ; scope `m004` 45/45 GREEN ; scope
  `m013_environments` 49/49 GREEN ; scope `m014_distribution_core --live`
  38/38 GREEN ; scope `m014_local_pipeline --live` 33/33 GREEN. Chaque scope
  est sans nœud absent, inattendu ou dupliqué.
- ADR consultées : ADR-024, ADR-025, ADR-040, ADR-042, ADR-051 et ADR-052. ADR
  créée ou modifiée : aucune ; T-006 applique les frontières, le double fencing
  et la CUDA stricte déjà décidés sans nouvelle décision structurante.
- Commit GREEN : `a57c8d5a6` —
  `feat(m014-pipeline): persister resultats de pages sous fencing`.
- Gate globale finale : un seul lancement, exécution différée `91` attendue
  jusqu’à son terme sans redémarrage, délai configuré à 3 600 secondes. Verdict
  après 80,2 secondes : 472 nœuds, code 1, `PARTIAL RED`. L’échec n’était pas
  un timeout : `test.m013-fastapi.validate-review3-api-architecture-acceptance`
  refusait la dépendance de `source_processing/application` vers `platform`.
- Correction ciblée : les contrats techniques de lease, enveloppe terminale et
  message de complétion sont désormais neutres dans `app/contracts`. Les
  modules d’application SP ne dépendent plus de `app.platform`. Après
  correction : tests directs 5/5 GREEN, Ruff ciblé GREEN, scope `m013_fastapi`
  70/70 GREEN, scope `m014_distribution_core --live` 38/38 GREEN et scope
  `m014_local_pipeline --live` 33/33 GREEN. Conformément au contrat
  d’exécution T-006, aucune seconde gate globale n’a été lancée.
- Commit correctif prévu :
  `fix(m014-pipeline): neutraliser contrat de completion de page`.

## 2026-07-24 - T-007 assemblage et publication canoniques

- Sous-agent : `/root/m14_t007_canonical`, chargé exclusivement de T-007 par
  l'orchestrateur du milestone.
- Baseline initiale réutilisée sans relance : commit T-006 correctif
  `9683d3b0e`, arbre propre, gate canonique 472/472 GREEN, code 0, sortie
  terminale `PARTIAL GREEN: offline`. Aucune gate globale n'a été démarrée
  pendant le cycle RED/GREEN.
- Scénario BDD : la dernière complétion de page crée une unique commande
  `ASSEMBLE_CANONICAL_DOCUMENT`; deux workers concurrents ne publient qu'une
  version complète et le rejeu exact conserve la même identité sans second
  événement ni progression additionnelle.
- RED utile : les preuves unitaires, d'acceptation et PostgreSQL échouaient à
  la collecte sur l'absence du cas d'usage
  `app.source_processing.application.assemble_canonical_document`. Commit RED :
  `fa4d9e6ff` —
  `test(m014-pipeline): couvrir assemblage canonique atomique`.
- Complétude transactionnelle : la transaction SP qui persiste le dernier
  résultat crée au plus une commande d'assemblage. Elle refuse tout résultat
  manquant, échoué ou divergent et conserve le manifeste, l'environnement et
  le contrat de résultat comme identité immutable.
- Assemblage : le handler relit uniquement les faits SP, vérifie les octets et
  empreintes des artefacts de pages, restaure l'ordre PDF puis réutilise les
  politiques M-004 d'autorité textuelle, de fusion Docling et d'acceptation
  canonique. Aucun port de modèle n'est appelé et aucun contenu alternatif
  n'est inventé.
- Publication : l'artefact immutable est préparé avant la transaction SP ; une
  transaction unique rend ensuite visibles la version canonique, le succès
  public et l'outbox `CanonicalSourcePublished`. Un crash avant ce commit peut
  laisser un fichier non référencé, jamais une version partielle.
- Chaîne réelle : `ASSEMBLE_CANONICAL_DOCUMENT` appartient au catalogue et aux
  deux replicas `worker-documents`; le runtime construit son repository, son
  stockage local et son worker. L'environnement étranger est refusé avant
  insertion dans la file technique.
- Preuve PostgreSQL réelle : absence de commande avant complétude, rejeu exact
  idempotent, doublon divergent refusé, unique commande après la dernière page,
  concurrence de claims, crash après écriture d'artefact avant commit, puis
  reprise atomique avec une version et un événement uniques.
- Validations avant commit GREEN : tests ciblés T-007 et compatibilité M-013
  5/5 GREEN ; Ruff ciblé GREEN ; `git diff --check` GREEN ; preuves PostgreSQL
  T-005/T-006 2/2 GREEN ; scope `m004` 45/45 GREEN ; scope
  `m014_local_pipeline --live` 36/36 GREEN. Chaque scope est sans nœud absent,
  inattendu ou dupliqué.
- ADR consultées : ADR-001, ADR-002, ADR-003, ADR-004, ADR-024 et ADR-052. ADR
  créée ou modifiée : aucune ; T-007 applique les autorités, frontières et
  transactions déjà décidées sans nouvelle décision structurante.
- Commit GREEN prévu :
  `feat(m014-pipeline): publier document canonique complet`. Après ce commit et
  un arbre propre, la gate globale finale sera lancée exactement une fois avec
  un délai de 3 600 secondes ; toute exécution différée sera attendue jusqu'à
  son verdict terminal sans relance.
