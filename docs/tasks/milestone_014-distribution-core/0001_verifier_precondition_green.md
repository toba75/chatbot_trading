# T-001 - Vérifier la précondition GREEN et figer le baseline local

## Milestone

- Nom : M14-distribution-core - Socle de distribution locale durable.
- Source : `docs/specs/plan_distribution.md`, T-001 ; section
  `M14-distribution-core` du plan d'implémentation.
- Objectif métier : établir sur une base M-013 GREEN une preuve reproductible du
  comportement actuel à un puis deux workers, avant de modifier le protocole de
  conversion documentaire.

## Contexte DDD

- Domaine : plateforme d'exécution locale et traitement des sources.
- Bounded contexts : `platform` et Source Processing (SP), sans transfert de
  propriété entre eux.
- Objectif métier : distinguer les capacités déjà livrées des écarts que
  M14-distribution-core doit fermer.
- Langage ubiquitaire : précondition GREEN, baseline, worker documentaire,
  replica, claim, lease, fencing, progression persistée, capacité Granite,
  artefact local, environnement étanche.
- Invariants critiques : M-013 et les milestones strictement antérieurs sont
  présents dans `master` ; la même page, les mêmes actifs, la même image et la
  même configuration sont utilisés à un puis deux workers ; Granite reste sur
  `cuda:0` ; chaque worker reste limité à 2 Gio ; aucun hôte distant ne
  participe à la preuve.
- Garde-fous : aucun service indisponible n'est remplacé par un mock ; aucun
  résultat historique n'est présenté comme une nouvelle mesure ; aucune
  configuration, donnée ou file ne traverse `development`, `test` et
  `production`.

## Blocages Ou Préconditions

- État GREEN/RED connu : au prévol de planification du 2026-07-23,
  `uv run --locked gate` sur `master` exécute 451 nœuds exactement une fois et
  termine `PARTIAL GREEN: offline` après mise à disposition du fichier local
  ignoré `config/application.yaml` ; la gate doit être rejouée avant le premier
  commit RED d'implémentation.
- Présence des milestones amont dans master : M-000 à M-013 sont visibles dans
  `master` ; les têtes contrôlées de M-013, M13-environments et M13-FastAPI sont
  ancêtres de `master`.
- Décisions manquantes : ADR-052 reste à créer en T-002 ; T-001 inventorie les
  choix existants sans décider le quota durable.
- Risques : mesures non comparables, preuve CUDA seulement déclarative,
  consommation mémoire non observée, ou présence implicite d'un chemin SSH,
  Kamal, Colima, `arm64` ou d'un hôte distant.

## Tâches

### T-001 - Vérifier la précondition GREEN et figer le baseline local

- But métier : publier une preuve initiale qui sépare les régressions M14 des
  comportements déjà présents et fixe le point de comparaison de la
  distribution locale.
- Portée DDD : gouvernance du milestone, runtime Granite M-004, workers M13,
  file PostgreSQL, progression publique et volumes locaux des trois profils.
- Scénario BDD :
  - Given `master` contient M-013 GREEN et la branche de travail contient la
    capacité Granite CUDA stricte ainsi que deux workers limités à 2 Gio.
  - When la gate canonique, l'inventaire des claims, leases, progressions,
    limiteurs et volumes, puis la même page Granite réelle à un et deux workers
    sont contrôlés.
  - Then la preuve publie les références Git, identités d'environnement,
    digests, versions, mesures de durée, RAM, VRAM et GPU, démontre que les
    sorties sont contractuellement identiques et confirme l'absence de toute
    capacité distante.
- Tests d'acceptation à écrire : créer le scope
  `m014_distribution_core` et un test qui refuse une preuve de baseline absente,
  synthétique ou incomplète ; exiger les références Git, le profil `test`, la
  page et la route mesurées, l'identité de l'image et des actifs, les mesures un
  et deux workers, les empreintes des sorties, l'inventaire des mécanismes
  existants et la liste fermée des exclusions réseau.
- Tests unitaires à écrire : couvrir le validateur de preuve avec commit absent,
  métrique manquante, durée non positive, hash invalide, sorties divergentes,
  limite mémoire différente de 2 Gio, absence de preuve CUDA et apparition de
  `ssh`, Kamal, Colima, `arm64` ou d'un worker distant.
- Implémentation attendue : publier une preuve structurée sous
  `docs/evaluation/m014/`, son compte rendu sous
  `docs/governance/m014_distribution_core_baseline.md`, enregistrer les tests
  dans la gate Python et compléter `journal.md` avec l'inventaire précis des
  modules, tables, migrations, configurations et validations observés.
- Invariants et garde-fous : conserver les résultats négatifs ; identifier
  explicitement toute mesure reprise du plan ; ne jamais déduire la progression
  depuis les logs ; ne pas démarrer, arrêter ou modifier un profil autre que
  `test` pour la preuve fonctionnelle.
- Dépendances : `AGENTS.md` ; `docs/tasks/README.md` ; M-013 dans `master` ;
  ADR-025, ADR-040, ADR-042, ADR-046 et ADR-051 ; commits de prérequis Granite
  CUDA et limite 2 Gio présents sur la branche.
- Commandes de validation : `git fetch origin --prune` ;
  `git ls-tree -r --name-only master -- docs/tasks/milestone_013 docs/adr app gate_tests` ;
  `uv run --locked gate --scope governance` ;
  `uv run --locked gate --scope m004` ;
  `uv run --locked gate --scope m013_environments` ;
  tests ciblés du scope `m014_distribution_core` ;
  `uv run --locked gate`.
- Commit RED : `test(m014-core): exiger baseline locale reproductible`.
- Commit GREEN : `docs(m014-core): publier baseline et précondition green`.
