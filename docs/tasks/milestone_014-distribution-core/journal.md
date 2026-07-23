# Journal M14-distribution-core - Socle de distribution locale durable

## Prévol de planification

- Date : 2026-07-23.
- Branche de planification : `codex/m14-distribution-core`.
- Base contrôlée : `master` et `origin/master` à
  `c67e8aebb` après `git fetch origin --prune`.
- État initial du worktree principal : propre avant création des tâches.
- Présence amont : les têtes contrôlées de M-013 principal,
  M13-environments et M13-FastAPI sont ancêtres de `master`; les dossiers de
  tâches M-000 à M-013 et leurs artefacts canoniques sont visibles depuis
  `master`.
- Premier prévol détaché : `uv run --locked gate` a terminé `PARTIAL RED` sur
  `test.m004.validate-granite-gemma-recovery-unit` avec
  `CONFIG_FILE_UNREADABLE` parce que le worktree propre ne contenait pas le
  fichier local ignoré `config/application.yaml`.
- Qualification du prévol : le fichier local existant a été relié temporairement
  au worktree sans être versionné ni affiché; la même commande a ensuite exécuté
  451 nœuds exactement une fois et terminé avec le code 0,
  `PARTIAL GREEN: offline`.
- Conclusion : M-013 est présent et la baseline logicielle de `master` est
  GREEN pour planifier M14-distribution-core. Le fichier local qualifié reste
  requis pour reproduire la gate complète dans un worktree détaché.

## Commits techniques déjà présents sur la branche

- `436c682e9` : test RED exigeant Granite sur CUDA selon ADR-051.
- `89a73a075` : implémentation GREEN de Granite sur `cuda:0` selon ADR-051.
- `975a12c27` : limite des workers documentaires à 2 Gio.
- `dad3ec98e` : recadrage documentaire de M-014 sur deux workers locaux.
- Ces commits ne servent pas à déclarer M-013 présent dans `master`. Ils forment
  les prérequis techniques et documentaires propres à la branche de
  planification M14.

## Sources canoniques consultées

- `AGENTS.md` et `docs/tasks/README.md`.
- `docs/specs/plan_implementation_milestones_workstreams.md`, sections M-014 et
  M14-distribution-core.
- `docs/specs/plan_distribution.md`, notamment les invariants, le modèle
  d'exécution, DIST-001 à DIST-003, T-001 à T-004, les tests, migrations et
  risques.
- `docs/specs/m004_version_canonique_publiee.md` et
  `docs/specs/m013_environments_environnements_explicites.md`.
- ADR-021, ADR-024, ADR-025, ADR-040, ADR-042, ADR-046 et ADR-051.
- Contrats et runtime existants : `app/contracts/technical_jobs.py`,
  `app/platform/job_runtime`, domaine pagewise M-004, limiteurs Docling/Granite,
  persistance SP, configuration stricte et composition des environnements.
- Migrations PostgreSQL 001 à 021 et tests portés M-004/M13-environments.

## Synthèse DDD

- Source Processing reste propriétaire de `DocumentProcessingRun`, des routes,
  résultats de pages, artefacts et de la publication canonique.
- `platform` reste propriétaire de la file technique, des claims fenced et de
  la capacité d'exécution locale.
- Les deux workers documentaires sont des replicas généralistes identiques ; un
  job déclare une capacité requise mais ne cible jamais une instance.
- L'effet persistant doit être exactement une fois malgré une exécution au
  moins une fois ; toutes les écritures post-claim transportent génération et
  token.
- PostgreSQL est l'autorité du quota Granite. Les sémaphores M-004 existants
  restent des limites de processus, pas la preuve du plafond global.
- L'environnement `test` porte les preuves fonctionnelles ; `development` et
  `production` reçoivent uniquement des contrôles structurels pour cette
  tranche.

## Découpage initial

- T-001 vérifie la précondition GREEN, inventorie l'existant et publie un
  baseline comparable à un puis deux workers.
- T-002 crée ADR-052 et décide le fan-out local, le quota PostgreSQL, le cycle de
  vie des slots et le fencing.
- T-003 publie les contrats versionnés de jobs, résultats, artefacts, erreurs et
  configuration locale stricte.
- T-004 ajoute les migrations ascendantes et implémente les deux slots Granite
  fenced avec preuve PostgreSQL réelle.
- Les jobs de pages, leur exécution métier, l'assemblage canonique et la
  projection restent réservés à M14-local-pipeline.

## Règles d'exécution

- Chaque tâche commence par la vérification GREEN pertinente.
- Le scénario BDD et le test d'acceptation échouant pour la bonne raison sont
  commités avant le code applicatif.
- Le commit RED ne contient aucune implémentation ; le commit GREEN contient
  uniquement le comportement strict nécessaire.
- Aucune valeur par défaut, aucun fallback silencieux, aucune conversion
  ambiguë et aucun état synthétique ne sont admis.
- Toute évolution de la décision structurante ADR-052 crée une ADR remplaçante
  et met à jour `docs/adr/index.md`.

## Risques ouverts avant implémentation

- Le mécanisme PostgreSQL exact des deux slots doit être choisi par ADR-052.
- Les noms et propriétaires des tables de résultats de pages doivent respecter
  les frontières ADR-024 et ADR-025.
- La capacité Granite actuelle est bornée en mémoire dans chaque processus ;
  elle ne prouve pas encore le plafond global entre replicas.
- Les mesures réelles doivent conserver la même page, les mêmes actifs, la même
  image et les mêmes limites pour éviter un faux gain de débit.
- Les mentions historiques de flotte CPU multiarchitecture dans ADR-051 ne
  doivent pas être modifiées silencieusement ; ADR-052 doit les superséder de
  façon bornée pour M-014 tout en conservant la décision CUDA stricte.

## 2026-07-23 - T-001 baseline locale reproductible

- Précondition GREEN : `uv run --locked gate` a exécuté 452 nœuds exactement
  une fois et terminé avec le code 0, `PARTIAL GREEN: offline`, avant toute
  modification T-001.
- Scénario BDD et portée de gate ajoutés sous
  `gate_tests/ported/tests/m014_distribution_core/`, avec la précondition
  `gate_tests/preconditions/test_m014_distribution_core.py` et le scope
  `m014_distribution_core` enregistré dans `gate.toml`.
- RED utile : le scope a terminé `PARTIAL RED` et Pytest a refusé la collecte
  avec `ModuleNotFoundError: ost_gate.m014_distribution_core`. Commit RED
  `c0a136bcfb5c5f51c0d9b31f627e0a96ff13ee35`.
- Validateur strict : `ost_gate/m014_distribution_core.py` refuse preuve
  synthétique, champ ou commit absent, durée non positive, hash invalide,
  sorties divergentes, limite autre que 2 Gio, preuve CUDA absente et capacité
  `ssh`, Kamal, Colima, `arm64` ou worker distant active.
- Preuve structurée :
  `docs/evaluation/m014/distribution_core_baseline.json` ; compte rendu :
  `docs/governance/m014_distribution_core_baseline.md`.
- Charge mesurée : page 2 de la fixture M-013, route `MIXED_PAGEWISE`, image
  scellée `sha256:2af4bfdfd1b7c6f4c43896fb2767cfe2e87646dcab84b5569f5fd4e3c84f7bfd`,
  actifs Granite au manifeste
  `575eb811c47bb48a6401006bdde1084605ab4f6e158901651f9dbfcbc659e368`.
- Un worker : 24,955 s, pic RAM 1 872 605 741 octets, pic VRAM 1 396 Mio,
  pic GPU 34 %, deux items `granite_docling`.
- Deux workers : 25,539 s pour deux pages concurrentes, pics RAM
  1 871 531 999 et 1 464 583 848 octets, pic VRAM total 2 719 Mio, pic GPU
  8 %, deux items par réponse.
- Les trois sorties possèdent le même SHA-256
  `21eb4e0b719b644bca4e193546cfc53b6be7666f732200ec9da0e44d921a2977`.
  Le débit dérivé du lot atteint `1,954x` par rapport à deux durées unitaires.
- Résultats négatifs conservés : deux courses du collecteur `docker stats`
  sans preuve retenue ; une conversion réussie en 24,601 s rejetée parce que
  son SHA-256 de réponse était absent.
- Inventaire observé : contrats `app/contracts/technical_jobs.py`, runtime
  `app/platform/job_runtime`, worker SP, tables de jobs, outbox, runs,
  progression et routes, migrations `003`, `008`, `012`, `014`, `020`, `021`,
  configurations et volumes du profil `test`.
- ADR consultées : ADR-025, ADR-040, ADR-042, ADR-046 et ADR-051. ADR nouvelle :
  non requise ; ADR-052 demeure réservée à T-002.
- Validations GREEN : Pytest ciblé 2/2 ; scope `m014_distribution_core` 26
  nœuds ; `governance` 25 nœuds ; `m004` 45 nœuds ; `m013_environments` 49
  nœuds ; aucune absence, surprise ou duplication.
- Gate canonique finale : 455 nœuds exécutés exactement une fois, code 0,
  aucune absence, surprise ou duplication, `PARTIAL GREEN: offline`.
- Lint ciblée : Ruff GREEN sur le validateur, les tests et la précondition.
- Commit GREEN : `fd30fcdebd2f8c554615fed2d91535d1c630c343`.

## 2026-07-23 - T-002 décision locale et quota Granite fenced

- Précondition GREEN : `uv run --locked gate` a exécuté 455 nœuds exactement
  une fois avant toute modification T-002 et terminé avec le code 0, aucune
  absence, surprise ou duplication, `PARTIAL GREEN: offline`.
- Scénario BDD : deux workers généralistes du même environnement détiennent les
  deux slots ; un troisième job Granite reste `pending` sans claim, modèle,
  changement de route ni CPU ; après expiration, une nouvelle attribution
  renouvelle générations et tokens et refuse l’ancien détenteur.
- RED utile : les tests d’acceptation et unitaires ont refusé la collecte parce
  que `validate_distribution_decision` et `DistributionDecisionError` étaient
  absents. Commit RED
  `2d65f687a264b44317584eb6b2e66bd7314b05fb`.
- ADR-052 proposée : `platform` possède deux lignes
  `platform.granite_slots` par identité explicite d’environnement et de
  déploiement, avec `slot_ordinal IN (1, 2)`, un détenteur unique par worker,
  une génération monotone et un UUID v4 neuf par attribution.
- Acquisition : le claim de job compatible et le slot sont sélectionnés avec
  `FOR UPDATE SKIP LOCKED` puis attribués dans une seule transaction
  PostgreSQL ; les deux leases partagent la même échéance explicite.
- Cycle de vie : heartbeat claim-slot atomique, expiration sur l’horloge
  PostgreSQL, drainage sans nouvelle acquisition, libération sous double
  fencing et reprise uniquement après libération ou expiration.
- Frontières DDD : Source Processing conserve manifeste, résultats,
  progression et publication canonique ; `platform` conserve jobs, claims,
  slots et enveloppes de complétion. Les résultats passent par des relais
  idempotents et des transactions locales, sans transaction forte
  intercontextes.
- Topologie : exactement deux replicas généralistes sur la station locale,
  aucune file ou route spécialisée, aucun Redis, Taskiq, Celery, broker, SSH,
  Kamal, Colima, `arm64`, worker distant, stockage réseau, détection matérielle
  implicite ou fallback CPU.
- ADR-051 n’a pas été modifiée ; son SHA-256 reste
  `a3043a8710536c25277e6b555237fced538b17e2595ea08494bac409b241e87e`.
  ADR-052 remplace seulement, pour M-014, ses mentions contextuelles devenues
  obsolètes de flotte CPU multiarchitecture ou distante et conserve son
  autorité `cuda:0` stricte.
- Fichiers principaux :
  `docs/adr/ADR-052-distribution-locale-pages-quota-granite-fenced.md`,
  `docs/adr/index.md`, `ost_gate/m014_distribution_core.py`, `gate.toml`, les
  deux tests `validate_distribution_decision_*`, l’allowlist historique et les
  attentes M13-environments sur le prochain numéro ADR.
- Validations GREEN : Pytest ciblé 2/2 ; Ruff ciblé ; scope
  `m014_distribution_core` 28 nœuds ; scope `governance` 25 nœuds ; toutes les
  exécutions sont uniques et sans absence ni surprise.
- Gate canonique finale : 457 nœuds exécutés exactement une fois, code 0,
  aucune absence, surprise ou duplication, `PARTIAL GREEN: offline`.
- Commit GREEN : `356972ec1593c0fb4590aeb8168224524753d222`.
- Risques résiduels : ADR-052 reste proposée jusqu’aux preuves PostgreSQL
  réelles de T-004 et aux preuves live de M14-local-qualification ; T-002 ne
  crée encore ni migration, ni contrat runtime, ni slot actif.

## 2026-07-23 - T-003 contrats stricts de distribution locale

- Précondition GREEN : le scope `m014_distribution_core` a exécuté 28 nœuds
  exactement une fois avant toute modification T-003, sans absence, surprise
  ni duplication.
- Scénarios BDD et tests ATDD/TDD ajoutés pour les contrats versionnés
  `CONVERT_PAGE`, résultat de page et `ASSEMBLE_CANONICAL_DOCUMENT`, leur
  sérialisation JSON fermée, leurs clés d’idempotence et leur transport dans
  l’enveloppe technique générique `JobRequest`.
- RED utile : les quatre tests ciblés initiaux ont échoué parce que le module
  de contrats Source Processing et la configuration locale explicite
  n’existaient pas. Commit RED
  `f7549941548438cd2239806a4cf72de1ee9edd74`.
- Contrats publiés dans
  `app/source_processing/domain/distribution_contracts.py` : identités
  d’artefacts locaux bornées au profil et à l’environnement, empreinte et
  taille obligatoires, versions d’actifs et de modèle verrouillées, exigences
  de capacité explicites, fencing des claims et des slots Granite, répétition
  strictement compatible et erreurs stables sans fallback.
- `SKIP_EMPTY` est un résultat explicite sans convertisseur, exécution ni slot.
  Les routes document standard interdisent un slot Granite ; les routes
  Granite exigent `cuda:0`, un slot fenced et les actifs verrouillés.
- Configuration publiée sous `services.workers.local_distribution` dans le
  schéma, les profils `development`, `test`, `production`, l’exemple et le
  profil Compose : deux replicas, 2 Gio et 4 CPU par worker, `cuda:0`, deux
  slots globaux et un slot par worker. Le rendu Compose vérifie ces valeurs
  sans détection implicite ni valeur de repli.
- Le contrat de capacité utilise les noms explicites `granite_slots_global` et
  `granite_slots_per_worker`, distincts du paramètre historique de concurrence
  intra-processus M-004.
- Fichiers de validation : les deux tests
  `validate_local_distribution_contracts_*` et leurs nœuds dans `gate.toml`.
  Les tests couvrent notamment champs inconnus ou absents, versions, chemins,
  empreintes, enveloppes divergentes, répétitions incompatibles, fencing,
  limites de ressources et rendu des trois profils.
- ADR consultées : ADR-025, ADR-040, ADR-042, ADR-046, ADR-051 et ADR-052.
  ADR nouvelle : non requise, car T-003 matérialise la décision structurante
  déjà portée par ADR-052 sans en changer le sens.
- Validations GREEN : tests ciblés 2/2 ; Ruff ciblé ; scopes `m004` 45 nœuds,
  `m013_config` 4 nœuds, `m013_environments` 49 nœuds et
  `m014_distribution_core` 30 nœuds ; aucune absence, surprise ou
  duplication.
- Gate canonique finale : 459 nœuds exécutés exactement une fois, code 0,
  aucune absence, surprise ou duplication, `PARTIAL GREEN: offline`.
- Commit GREEN : `f5c4bdaade2a211c9f1c9ef368bb8e40dfd8a0f7`.
- Périmètre respecté : aucune migration, table, boucle d’exécution, fan-out
  ou activation runtime n’est ajoutée. Le quota PostgreSQL réel et la
  saturation restent à prouver en T-004 ; le branchement runtime demeure la
  responsabilité de T-005.

## 2026-07-23 - T-004 quota Granite PostgreSQL double-fenced

- Précondition GREEN : `uv run --locked gate --scope
  m014_distribution_core` a exécuté 30 nœuds exactement une fois avant toute
  modification T-004 et terminé avec le code 0, sans absence, surprise ni
  duplication.
- Scénario BDD : deux workers généralistes `READY` du même environnement
  réclament concurremment les deux slots Granite ; le troisième job reste
  `pending` sans appel modèle ; après expiration PostgreSQL, il récupère le
  slot avec une génération et un UUID v4 nouveaux, tandis que l’ancien
  heartbeat, l’ancienne libération et l’ancien succès sont refusés avec
  `JOB_LEASE_LOST`.
- RED utile : les tests d’acceptation, unitaires et PostgreSQL live exigeaient
  le module `app.platform.job_runtime.granite_capacity` et la migration
  `022_granite_quota_and_page_results.sql`, tous deux absents. Commit RED
  `25ce8893cd2af91df61547cbf4023fbd044f2b3c`.
- Migration ascendante :
  `deploy/postgres/migrations/022_granite_quota_and_page_results.sql` crée
  `platform.granite_slots`, initialise exactement les ordinaux 1 et 2 depuis
  l’unique `platform.datastore_identity`, interdit un troisième ordinal et
  impose un détenteur unique par worker. Elle prépare séparément
  `platform.page_completion_outbox` et
  `source_processing.page_execution_results`, sans clé étrangère ni
  transaction forte intercontextes, sans suppression et sans activer le
  fan-out, les jobs de pages ou l’assemblage.
- Adaptateur platform : `PostgresGraniteSlotRepository` sélectionne le job puis
  le slot avec deux `FOR UPDATE SKIP LOCKED`, dans cet ordre documenté, et les
  attribue dans une transaction unique. Il vérifie environnement, déploiement,
  hash de configuration, identité de stockage, capacité `GRANITE_CUDA`,
  `cuda:0`, état non drainant et généralité du worker.
- Cycle de vie : la lease du claim et celle du slot partagent l’échéance
  PostgreSQL ; heartbeat et libération comparent worker, job, environnement,
  les deux générations, les deux tokens et une échéance future. Le contrôleur
  unique renouvelle pendant l’appel modèle et libère sous le même fencing sur
  succès ou erreur explicite, sans fallback.
- Correctif d’intégration T-003 : `PostgresJobQueue` sérialise désormais
  récursivement les mappings immutables des contrats ; la preuve live avait
  détecté le refus JSON d’un `mappingproxy` imbriqué avant tout claim.
- Preuve PostgreSQL réelle : départ d’un ledger 001 à 021, migration vers 022,
  second passage du runner sans drift, ledger final de 22 lignes, exactement
  deux slots, deux acquisitions concurrentes, troisième attente sans appel
  modèle, un slot maximum par worker, heartbeat, drainage sans claim,
  expiration forcée sur l’horloge PostgreSQL, reprise monotone, refus de
  l’ancien détenteur, libération répétée refusée, profil `production` incapable
  de voir les slots `test` et index du chemin chaud observé par `EXPLAIN`.
- Tests ajoutés :
  `validate_granite_quota_acceptance.py`,
  `validate_granite_quota_unit.py` et
  `validate_granite_quota_live.py`, enrôlés dans `gate.toml` ; le test live
  démarre un PostgreSQL 16 éphémère avec un port local aléatoire et le supprime
  systématiquement.
- Validations GREEN avant commit : Pytest ciblé 3/3 ; Ruff ciblé ; scope
  `m014_distribution_core --live` 33 nœuds ; scope `m004` 45 nœuds ; scope
  `m013_environments` 49 nœuds. Toutes les exécutions sont uniques, sans
  absence ni surprise ; aucun conteneur `ostrading-m014-quota-*` ne subsiste.
- Gate canonique finale : 461 nœuds exécutés exactement une fois, tous GREEN,
  aucune absence, surprise ou duplication, `PARTIAL GREEN: offline` ; rapport
  local `.tmp/m014-t004-global-gate.json` ignoré par Git.
- Commit GREEN : `fa878d5241139aba024757e9808743aea0ad626d`.
- ADR consultées : ADR-021, ADR-024, ADR-025 et ADR-052. ADR nouvelle : non
  requise, car T-004 matérialise sans la modifier la décision structurante
  d’ADR-052. ADR-052 reste proposée jusqu’à la qualification live du pipeline
  local prévue dans le sous-milestone ultérieur.
- Périmètre respecté : aucun worker spécialisé, aucune nouvelle route ou file,
  aucun CPU de repli, aucun résultat de page écrit et aucune activation de
  M14-local-pipeline.

### Stabilisation de la readiness PostgreSQL publiée

- RED reproduit lors de la revalidation : `pg_isready` réussissait sur le
  socket interne du conteneur pendant que la première connexion des migrations
  au port TCP publié échouait encore avec `psycopg.OperationalError: server
  closed the connection unexpectedly`.
- Test de harnais ajouté avant le correctif : une rupture réseau de démarrage
  sans SQLSTATE est attendue dans une fenêtre bornée ; un conteneur arrêté
  échoue immédiatement ; une erreur PostgreSQL structurée avec SQLSTATE reste
  terminale. Commit RED : `f9b0b0c66`.
- Correctif : `_wait_postgres` sonde désormais `SELECT 1` avec la même
  `PsycopgConnectionFactory`, le même secret et le même port TCP publié que les
  migrations. L’état Docker est contrôlé à chaque tentative ; aucune panne
  serveur, erreur d’authentification ou indisponibilité persistante n’est
  masquée. Commit GREEN : `f3713ad69`.
- Validations GREEN : test de harnais 1/1 ; harnais et preuve live 2/2 ; preuve
  PostgreSQL live ciblée réussie dix fois consécutivement ; scope
  `m014_distribution_core --live` à 34 nœuds, tous exécutés exactement une fois,
  sans absence, surprise ni duplication.
- Les assertions de quota global, concurrence, attente sans appel modèle,
  reprise monotone et double fencing restent inchangées. Aucun élément de T-005
  n’est introduit et aucune ADR supplémentaire n’est requise.

## 2026-07-23 - Corrections contrats, Compose et exploitation locale

- Précondition GREEN : la gate canonique a exécuté 462 nœuds exactement une
  fois avant les corrections, sans absence, surprise ni duplication, et a
  terminé `PARTIAL GREEN: offline`.
- Scénarios BDD : un résultat Granite publié porte durée, pic RAM, pic VRAM,
  utilisation et puissance GPU mesurés ; une route standard interdit les
  mesures GPU ; `SKIP_EMPTY` interdit toute mesure d’exécution. Deux workers
  rendus par Compose reçoivent chacun 2 Gio, 4 CPU et uniquement le
  périphérique NVIDIA 0.
- RED utile : les trois tests ciblés ont échoué pour les raisons attendues :
  value objects de métriques absents, réservation GPU 0 absente et
  `gpus: all` encore actif. Commit RED :
  `b51c6e11bf01bc5a79ab0efd15b5c6a9b94024c2`.
- `PageResultContract` v1 exige désormais `PageTechnicalMetrics` pour toute
  exécution réelle et sérialise `PageGpuMetrics` seulement pour une route
  Granite. Durée non positive ou non finie, RAM non positive, VRAM négative,
  utilisation hors `0..100`, puissance négative, champ absent ou inconnu sont
  refusés par des erreurs stables. La validation terminale est décomposée par
  variante et satisfait Ruff C901.
- Les Compose local et multi-profils publient deux replicas, 2 Gio, 4 CPU et
  une réservation NVIDIA fermée `device_ids: ["0"]`. Le validateur de rendu
  multi-profils et le test du rendu local `docker compose config` refusent
  toute autre réservation. Le parseur YAML statique accepte désormais les
  mappings de réservation dans une séquence sans relâcher ses contrôles.
- La validation Python morte du produit des constantes
  `granite_slots_global`, `replicas` et `granite_slots_per_worker` est retirée ;
  le schéma JSON fermé reste l’unique autorité de ces valeurs fixes.
- Le runbook `docs/runbooks/distribution_locale.md` publie la sonde NVIDIA,
  l’obligation `cuda:0`, l’absence de fallback et l’upgrade bloquant : arrêt
  des admissions, drainage sous l’ancien `configuration_hash`, contrôle de
  zéro job `pending` ou `running`, puis seulement bascule du profil. Il
  documente les prérequis de la gate PostgreSQL T-004 `--live`.
- La spécification M13 aligne ses deux limites historiques de 8 Gio sur les
  2 Gio de M14-distribution-core. La matrice publie exactement quatre exigences
  `REQ-M014-CORE-001` à `004`, les preuves, le runbook et le lien cohérent
  ADR-051/ADR-052.
- La preuve live T-004 réutilise `LOCAL_POSTGRES_IMAGE`, référence digérée
  centrale existante. L’étage `worker-documents` remplace les index Debian
  mutables par les snapshots du 2025-02-03 et épingle
  `gcc=4:12.2.0-3` ainsi que `libc6-dev=2.36-9+deb12u9`.
- Preuve de construction : l’étage Docker `worker-documents` a été construit
  avec succès, puis `dpkg-query` a retourné exactement les deux versions
  épinglées.
- Validations GREEN : tests ciblés 5/5 puis 3/3 ; Ruff ciblé ; `m004` 45
  nœuds ; `m013_config` 36 nœuds ; `m013_environments` 49 nœuds ;
  `governance` 25 nœuds ; `m014_distribution_core` offline 35 nœuds et live
  36 nœuds. Chaque exécution est unique, sans absence ni surprise.
- Gate canonique finale : 464 nœuds exécutés exactement une fois, code 0,
  aucune absence, surprise ou duplication, `PARTIAL GREEN: offline`.
- Commit GREEN : `7a873ebbd541e8492f258d3efa7347d13bf203a8`.
- ADR consultées : ADR-025, ADR-040, ADR-042, ADR-046, ADR-051 et ADR-052.
  ADR nouvelle : non requise ; les corrections précisent leurs conséquences
  sans modifier une décision structurante.
- Périmètre respecté : aucun raccordement worker au job de page, aucune
  acquisition supplémentaire, aucune requête SQL de quota et aucune migration
  ne sont ajoutés. Le runtime et le quota PostgreSQL de T-004 restent inchangés.
