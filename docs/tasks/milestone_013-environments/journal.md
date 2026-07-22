# Journal M13-environments

> **Note de requalification du 2026-07-22.** Les mentions antérieures de six
> workers ou dix-sept conteneurs décrivent le runtime historique désormais
> `STALE`. Le contrat courant exact est de quatre instances workers et quatorze
> conteneurs. Seuls de nouveaux rapports à la révision courante peuvent servir
> de preuve live GREEN ; les entrées historiques ci-dessous ne sont pas réécrites.

## T-007 - Scénario BDD et preuve RED

Scénario contrôlé:

- Given un worker `development` est raccordé à ses stockages et reçoit un
  message explicitement produit par `test`;
- When le relais ou le worker compare le couple `environment` / `deployment_id`
  avant tout claim ou callback métier;
- Then le travail n'est jamais exécuté, l'erreur terminale stable
  `WORKER_ENVIRONMENT_MISMATCH` est persistable dans la progression publique du
  producteur, et l'état de santé du worker publie son identité et son
  `configuration_hash`.

Précondition GREEN avant modification:

- `uv run --locked gate --scope m013_environments` - GREEN; 30 nœuds, aucune
  exécution manquante, inattendue ou dupliquée.

Preuve RED attendue:

- le test unitaire exige le value object immutable d'identité, le registre
  fermé des quatre workers, leur nom d'instance lié au profil et le refus d'un
  job dont seul le hash coïncide;
- le test d'acceptation exige la propagation job-outbox-relais, l'absence de
  callback métier sur divergence, la progression terminale persistable, la
  migration ascendante des trois tables et les healthchecks liés au profil;
- le RED doit provenir de l'absence des contrats et du module de liaison, sans
  affaiblir les invariants existants.

ADR consultées: ADR-045 et ADR-024. Aucune nouvelle ADR n'est requise: T-007
matérialise l'identité et le refus déjà décidés sans modifier les frontières
transactionnelles locales du relais.

Commit RED prévu: `test(platform): couvrir appartenance environnement des jobs`.

Preuve RED obtenue:

- `uv run --locked pytest -q gate_tests/ported/tests/m013_environments/validate_worker_environment_identity_acceptance.py gate_tests/ported/tests/m013_environments/validate_worker_environment_identity_unit.py` - RED utile; 2 tests échouent uniquement parce que `JobEnvironmentIdentity` n'existe pas encore.

## T-007 - Implémentation et preuve GREEN

Date d'exécution: 2026-07-21.

Implémentation:

- `JobRequest`, les outbox SP/KA, le relais et `platform.technical_jobs`
  portent obligatoirement `environment` et `deployment_id` en plus du
  `configuration_hash`;
- la migration additive `020_job_environment_identity.sql` complète les
  lignes existantes depuis `platform.datastore_identity`, rend les deux
  colonnes obligatoires et ajoute le refus terminal
  `WORKER_ENVIRONMENT_MISMATCH`;
- les workers documents, projection, recherche et backtest construisent une
  identité depuis la configuration validée, contrôlent PostgreSQL avant usage
  et publient `environment`, `deployment_id` et `configuration_hash` dans leur
  healthcheck;
- la file refuse les demandes étrangères avant insertion ou claim; le relais
  laisse l'outbox productrice persister atomiquement son échec et celui de la
  progression publique réelle.

Preuves automatisées ciblées:

- les tests unitaires et d'acceptation T-007 sont GREEN: identité immutable,
  registre fermé des quatre workers, propagation du message, refus sans
  callback métier, absence d'ACK et transition terminale confiée à l'outbox;
- les régressions jobs/outbox/commandes/workers M-002, M-003, M-004 et
  M13-fastapi sont GREEN après adaptation explicite des fixtures, sans valeur
  par défaut ni fallback.
- `uv run --locked gate --scope m002`, `--scope m013_config`,
  `--scope m013_environments` et `--scope m013_fastapi` sont GREEN;
- `uv run --locked gate` est GREEN: 447 nœuds, phases live incluses,
  `missing=[]`, `unexpected=[]`, `non_unique=[]`;
- `compileall`, le contrôle Ruff des erreurs de syntaxe et de noms, et
  `git diff --check` sont GREEN.

Preuve live sur les volumes T-006 conservés:

- les piles ont été démarrées puis arrêtées séquentiellement avec Compose,
  sans `down -v` et sans suppression de secret;
- dans `development`, `test` et `production`, la ledger contient
  `019_sparse_native_visual_authority.sql` puis
  `020_job_environment_identity.sql`;
- les trois tables jobs/outbox ont zéro ligne sans `environment` ou
  `deployment_id` après migration;
- chaque pile a atteint 17 conteneurs sains; les quatre catégories de workers
  publient l'identité exacte du profil et un hash commun au profil, distinct
  de ceux des deux autres profils.

Preuve live du refus public terminal:

- les workers documentaires `production` ont été arrêtés avant de produire,
  via l'API réelle, un diagnostic dont l'enveloppe a ensuite été étiquetée
  `test / ostrading-test-ci`;
- après redémarrage d'un worker `production`, l'outbox est passée à `failed`
  avec `WORKER_ENVIRONMENT_MISMATCH`, aucune ligne n'a été créée dans
  `platform.technical_jobs` et aucun callback métier n'a été exécuté;
- `GET /v1/documents/{id}/diagnostic/progress` a renvoyé HTTP 200 avec
  `phase=FAILED`, `completed_units=0`, `total_units=1` et
  `failure_error_code=WORKER_ENVIRONMENT_MISMATCH`;
- le document, le run, l'outbox et le PDF créés uniquement pour cette preuve
  ont ensuite été supprimés exactement; les trois comptes de contrôle sont
  revenus à zéro, puis `production` a de nouveau atteint 17/17 conteneurs
  sains avant l'arrêt propre sans suppression de volume.

ADR consultées: ADR-045 et ADR-024. Aucune nouvelle ADR: la mise en œuvre ne
change ni la décision d'identité d'installation ni la frontière
transactionnelle locale des outbox.

Commit GREEN prévu: `feat(platform): lier workers et jobs au profil courant`.

## Planification

- Sous-milestone: `M13-environments`, matérialisé dans `docs/tasks/milestone_013-environments`.
- Source principale: demande utilisateur du 2026-07-21 et section `M13-environments` du plan d'implémentation.
- Règle de gouvernance: ce dossier est un sous-milestone de M-013; il requiert M-000 à M-012 dans `master`, ne requiert pas la clôture de M-013 et ne clôture pas M-013 pour les milestones aval.
- Dépendance fonctionnelle: M13-config, dont le chargeur strict, les points d'entrée `--config` et l'interdiction des variables d'environnement sont présents sur la branche.
- Décision à créer pendant T-002: ADR-045, remplaçant explicitement ADR-016 pour la règle du chemin unique, sans modifier ADR-016 silencieusement.

## Intention

Fournir trois commandes opérateur simples, `uv run development`, `uv run test` et `uv run production`. Chacune sélectionne un fichier complet et immuable, supervise la chaîne réelle et utilise exclusivement ses bases, volumes, fichiers, artefacts, queues, outbox et secrets. Les workers portent la même identité que l'API et refusent tout travail d'un autre environnement avant claim ou effet métier.

## Tâches créées

- T-001: vérifier la précondition GREEN.
- T-002: décider le contrat des environnements explicites.
- T-003: lancer l'environnement choisi par une commande UV.
- T-004: vérifier l'identité des stockages avant usage.
- T-005: isoler toutes les ressources mutables.
- T-006: orchestrer trois piles et secrets distincts.
- T-007: lier workers et jobs à l'environnement courant.
- T-008: borner les opérations administratives à un environnement.
- T-009: prouver le parcours réel en development.
- T-010: prouver le parcours réel en test.
- T-011: prouver le parcours réel en production.
- T-012: relier environnements, runbooks et gates.

## Limite de cette planification

Cette étape crée uniquement le plan et les fichiers de tâches. Elle ne crée pas ADR-045, ne publie pas la spécification détaillée, ne modifie ni code, ni test, ni configuration, ni déploiement, et ne démarre ou n'arrête aucun service.

## T-001 - Précondition documentaire

Date d'exécution: 2026-07-21.

Scénario contrôlé:

- Given le sous-milestone M13-environments est demandé.
- When les prérequis Git et la gate documentaire sont vérifiés.
- Then M-000 à M-012 sont présents dans `master`, la branche descend de `master` et la gouvernance est GREEN avant planification.

Références Git observées avant le commit de planification:

- Branche courante: `codex/m13-environments`.
- `HEAD`: `781469359`.
- `master`: `9edeab957`.
- `origin/master`: `35fb5a4f8`.
- `master` et `origin/master` sont ancêtres de `HEAD`.

Présence dans `master`:

- M-000: 7 fichiers; M-001: 12; M-002: 12; M-003: 10; M-004: 11; M-005: 11.
- M-006: 11 fichiers; M-007: 11; M-008: 12; M-009: 12; M-010: 12; M-011: 13; M-012: 13.

Commandes exécutées:

- `git fetch origin --prune` - GREEN.
- contrôle `git cat-file -e master:docs/tasks/milestone_NNN/journal.md` pour M-000 à M-012 - GREEN.
- `uv run --locked gate --scope governance` - GREEN; 25 nœuds exécutés, aucune exécution manquante, inattendue ou dupliquée.

État connu de l'implémentation avant M13-environments:

- `pyproject.toml` ne publie pas encore `development`, `test` ou `production`.
- `config/application.schema.json` et le chargeur ne portent pas encore `environment` ou `deployment_id`.
- Compose utilise encore un unique jeu de volumes et un unique fichier monté pour tous les services.
- Les workers consomment `configuration_hash`, mais aucun contrat d'environnement ne bloque encore un job cross-environment.

Statut de T-001 pour la planification: GREEN documentaire.

## T-001 - Précondition GREEN d'implémentation

Date d'exécution: 2026-07-21.

Scénario contrôlé:

- Given M13-environments est demandé sur `codex/m13-environments`, issue de `master`.
- When les prérequis Git, la gate canonique et les parcours live disponibles sont contrôlés sans mock ni fallback.
- Then chaque RED de disponibilité est conservé, puis la baseline n'est qualifiée GREEN qu'après réussite du scope live M-013 et de la gate complète.

Références Git vérifiées avant la modification documentaire:

- `HEAD`: `64d9caa09`, commit de planification M13-environments.
- `master`: `9edeab957`; `origin/master`: `35fb5a4f8` après `git fetch origin --prune`.
- `master` et `origin/master` sont ancêtres de `HEAD`.
- Le commit utilisateur `781469359`, qui ajoute le rapport DOCX, est resté intact.
- `git ls-tree -r --name-only master -- docs/tasks/milestone_000 ... docs/tasks/milestone_012` confirme la présence de M-000 à M-012 dans `master`.

RED de disponibilité réellement observés, sans modification du code:

- La première tentative de gate complète a signalé Docker indisponible.
- Après démarrage de Docker Desktop `29.1.5`, la validation live a signalé `orchestrator-api` indisponible.
- Aucun mock, stub ou fallback n'a remplacé ces dépendances réelles; aucun commit RED artificiel n'a été créé.

Rétablissement et preuves GREEN:

- `uv run ui` a démarré et supervisé la pile réelle requise par les validations live.
- `uv run --locked gate --scope m013` - GREEN; 68 nœuds exécutés, dont le parcours M13 reality live.
- `uv run --locked gate` - GREEN; 436 nœuds exécutés sans erreur terminale.
- Ces démarrages précèdent cette modification documentaire; T-001 n'a ensuite démarré, arrêté ou reconfiguré aucun service et n'a altéré aucune donnée.

Statut final de T-001: GREEN. La dette antérieure et les indisponibilités live observées sont séparées des futures régressions de M13-environments; T-002 peut commencer sur cette baseline qualifiée.

## T-002 - Scénario BDD et preuve RED

Scénario contractuel:

- Given un opérateur choisit un profil parmi `development`, `test` et `production`.
- When le contrat de configuration du profil est validé.
- Then l'identité est complète, appartient à l'ensemble fermé, décrit toutes ses ressources mutables et ne dépend d'aucune valeur implicite ou variable système.

Précondition observée avant le test:

- `uv run --locked gate --scope governance` - GREEN; 25 nœuds exécutés.
- Aucun fichier applicatif, service, stockage ou processus actif n'a été modifié pendant cette vérification.

RED utile:

- `uv run --locked gate --scope m013_environments` - RED attendu; le nœud contractuel échoue avec `ADR_045_REQUIRED:docs/adr/ADR-045-profils-execution-explicites-donnees-etanches.md`.
- Le RED prouve que la succession explicite d'ADR et le contrat M13-environments demandés ne sont pas encore publiés; il ne résulte ni d'une dépendance externe indisponible, ni d'un test affaibli.
- Le test exige également, après publication de l'ADR, la spécification des trois profils, des identités, de l'isolation de chaque ressource mutable, des workers et des quatre erreurs publiques.

Commit RED:

- `264a59d8994a9ff5eb13a38fc4f6bed9b1d7e56a` - `test(m13-environments): couvrir contrat des profils explicites`.

## T-002 - Décision et retour GREEN

Décision publiée:

- ADR-045 accepte l'ensemble fermé `development`, `test`, `production` et remplace explicitement ADR-016 pour la règle du chemin unique `config/application.yaml`.
- ADR-016 conserve son texte décisionnel historique; seuls son statut et son lien `Remplacée par` sont mis à jour.
- La spécification `docs/specs/m013_environments_environnements_explicites.md` définit les trois fichiers complets sans fusion ni héritage, `ApplicationEnvironment`, `environment`, `deployment_id`, la matrice de ressources mutables et les identités attendues des stockages, jobs et workers.
- Les codes `CONFIG_ENVIRONMENT_UNKNOWN`, `CONFIG_ENVIRONMENT_MISMATCH`, `DATASTORE_ENVIRONMENT_MISMATCH` et `WORKER_ENVIRONMENT_MISMATCH` ont une condition et un moment de refus explicites.
- Les interdictions M13-config restent normatives: aucune valeur par défaut, aucun fallback, aucune variable d'environnement applicative et aucun secret en clair.

Périmètre respecté:

- Aucun changement de schéma, chargeur, lanceur UV, fichier YAML, Compose, stockage, message, worker ou service.
- Aucun service actif n'a été démarré, arrêté ou reconfiguré par T-002.
- L'empreinte de `docs/adr/index.md` a été réconciliée par l'outil canonique sans modifier le catalogue historique fermé.

Preuves GREEN:

- test d'acceptation ciblé - GREEN; 1 test exécuté;
- `uv run --locked gate --scope m013_environments` - GREEN; 22 nœuds exécutés, dont le nouveau contrat;
- `uv run --locked gate --scope governance` - GREEN; 25 nœuds exécutés;
- `uv run --locked gate` - GREEN; 437 nœuds exécutés, y compris les validations live existantes, sans exécution manquante, inattendue ou dupliquée.

Commit GREEN prévu:

- `docs(m13-environments): decider isolation des environnements`.

Statut final de T-002: GREEN documentaire. Les réalisations runtime restent explicitement affectées à T-003 et suivantes.

## T-003 - Scénario BDD et preuve RED

Scénario contrôlé:

- Given les trois fichiers complets existent et chaque commande UV est dédiée à un profil.
- When l'opérateur invoque `uv run development`, `uv run test` ou `uv run production`.
- Then le lanceur supervise la pile réelle avec l'unique fichier mappé, propage le profil à la pile et publie un arrêt terminal si le fichier ou la readiness manque.

Précondition GREEN avant modification:

- `uv run --locked gate --scope m013_config` - GREEN; 36 nœuds exécutés.
- `uv run --locked gate` - GREEN; 437 nœuds exécutés, y compris les validations live existantes.

Preuve RED observée:

- les tests d'acceptation invoquent les trois entrypoints réels et contrôlent les états `starting`, `ready`, `failed`, `stopped`;
- les tests unitaires figent le mapping fermé, l'absence de surcharge `--config`, l'erreur de fichier absent, l'arrêt ordonné et le chemin imbriqué `config/environments/<profile>.yaml`;
- le RED doit provenir de l'absence de `app.platform.environment_command`, sans modifier les configurations, stockages ou manifestes réservés à T-005/T-006.

Commit RED:

- `d5b1452be` - `test(platform): couvrir commandes uv des environnements`.
- `uv run --locked gate --scope m013_environments` - RED utile; les deux nouveaux nœuds échouent uniquement sur `ModuleNotFoundError: app.platform.environment_command`, tandis que le contrat T-002 reste GREEN.

## T-003 - Lancement strict et retour GREEN

Implémentation livrée:

- `pyproject.toml` publie exactement `development`, `test` et `production`, chacune reliée à une fonction dédiée du lanceur commun;
- `app/platform/environment_command.py` contient le mapping constant vers `config/environments/<profile>.yaml`, refuse tout profil inconnu, tout argument public et tout fichier absent, sans variable d'environnement ni fallback sur `config/application.yaml`;
- chaque lancement porte le profil dans `EnvironmentLaunchConfiguration`, publie `starting`, `ready`, `failed` ou `stopped` et propage le code terminal `2` des erreurs contractuelles;
- `app/platform/ui_local_stack.py` accepte le chemin imbriqué fermé des trois profils et réutilise sa supervision réelle existante: PostgreSQL, Qdrant, gateway, API, workers documentaires et workers de projection reçoivent le même fichier runtime interne;
- aucun fichier `config/environments/*.yaml`, stockage, volume, secret ou manifeste Compose n'est créé par T-003; ces réalisations restent affectées à T-005/T-006.

Preuve d'absence de fallback:

- `config/application.yaml` existe localement, mais `uv run --isolated --locked development`, `uv run --isolated --locked test` et `uv run --isolated --locked production` retournent chacun `2` avec `CONFIG_FILE_UNREADABLE` sur leur propre chemin absent;
- aucune pile n'est démarrée dans ce cas et aucun chemin historique n'est essayé.

Validations GREEN:

- tests d'acceptation et unitaires T-003 ciblés - GREEN; 2 tests;
- régressions commande et pile `uv run ui` - GREEN; 5 tests;
- scope `m013_environments` - GREEN; 24 nœuds;
- scope `m013_config` - GREEN; 36 nœuds;
- gate complète - GREEN; 439 nœuds, y compris les parcours live existants;
- `git diff --check` - GREEN.

Contrainte Windows observée sans arrêt du processus live:

- après la modification de `pyproject.toml`, la synchronisation automatique de `uv run --locked ...` ne peut pas remplacer `.venv/Scripts/ui.exe`, utilisé par la pile live préexistante;
- les validations post-implémentation ont donc exécuté le même environnement verrouillé avec `uv run --locked --no-sync`, et la gate via `python -m ost_gate.cli`; aucun processus live n'a été interrompu;
- une synchronisation UV normale matérialisera les trois exécutables dès que le processus `ui.exe` ne tiendra plus le fichier.

ADR consultée: ADR-045. Aucune modification d'ADR n'est requise: T-003 réalise le mapping et le cycle de vie déjà décidés sans nouvelle décision structurante.

Commit GREEN prévu: `feat(platform): lancer les environnements par commandes uv`.

## T-004 - Scénario BDD et preuve RED

Scénario contrôlé:

- Given un processus `test` reçoit un stockage portant l'identité `production`.
- When le processus exécute le préflight d'identité avant migration, lecture, écriture, accès Qdrant ou claim d'un job.
- Then il termine avec `DATASTORE_ENVIRONMENT_MISMATCH`, ne crée ni ledger ni donnée métier, ne migre rien et n'appelle aucune opération aval.

Preuves attendues par les tests RED:

- matrice croisée `development`, `test`, `production` sur `environment` et `deployment_id`;
- marqueur strict de racine fichier, initialisé explicitement seulement sur une racine vide et jamais réécrit;
- marqueur Qdrant initialisé explicitement seulement sans collection préexistante;
- préflight PostgreSQL exécuté dans la transaction avant la création du ledger et toute migration;
- absence d'appel aval pour les lectures, écritures, opérations Qdrant et claims après divergence.

ADR consultée: ADR-045. Aucune nouvelle ADR n'est requise: T-004 réalise l'identité de stockage et le fail-closed déjà décidés.

Commit RED:

- `9fe3a22e8` - `test(platform): couvrir identite des stockages`.
- les deux nouveaux nœuds ont échoué uniquement sur `ModuleNotFoundError: app.platform.datastore_identity`; les nœuds T-002/T-003 sont restés GREEN.

## T-004 - Préflights de stockage et retour GREEN

Implémentation livrée:

- le value object `DatastoreIdentity` compare strictement `environment` et `deployment_id`; toute absence, forme invalide, clé supplémentaire ou divergence produit `DATASTORE_ENVIRONMENT_MISMATCH`;
- PostgreSQL porte une table singleton `platform.datastore_identity`, contrôlée sous verrou transactionnel avant le ledger et avant chaque vérification de version; seul un stockage réellement vierge peut être initialisé;
- Qdrant porte un point singleton dans `platform_datastore_identity_v1`; la création de la collection agit comme acquisition exclusive et aucune collection existante sans marqueur n'est adoptée;
- chaque racine fichier utilisée porte `.ostrading-datastore-identity.json`, créé par lien exclusif après écriture synchronisée; une racine non vide, un marqueur illisible, un lien symbolique ou une identité étrangère est refusé sans réécriture;
- le schéma et l'objet `ApplicationConfiguration` portent l'identité attendue obligatoire; l'exemple et la configuration Compose locale déclarent explicitement `development/ostrading-development-local`;
- l'API ouvre le plan de préflight avant sa dépendance de migration; les workers SP et KA exécutent leur plan avant migration, relais d'outbox et `claim_next`;
- le préflight SP couvre `data_root`, `corpus_root` et `canonical_sources_root`; le préflight KA couvre PostgreSQL, Qdrant et `canonical_sources_root`;
- aucun fichier `config/environments/*.yaml`, aucune ressource distincte par profil et aucun manifeste d'environnement n'a été anticipé; ces réalisations restent dans T-005/T-006.

Preuves GREEN:

- tests T-004 ciblés - GREEN; 2 tests couvrant matrice 3 x 3, divergence de `deployment_id`, absence et invalidité des marqueurs, initialisation explicite, adaptateur REST Qdrant, ordre PostgreSQL et absence d'appel aval;
- scope `m013_environments` - GREEN; 26 nœuds;
- scope `m013_config` - GREEN; 36 nœuds;
- scope `m013_fastapi` - GREEN; 80 nœuds, validations live incluses;
- gate complète - GREEN; 441 nœuds, dont les parcours live M-004 et M-013;
- `git diff --check` - GREEN, avec uniquement les avertissements de normalisation LF vers CRLF.

Contrainte Windows conservée:

- `.venv/Scripts/ui.exe` reste utilisé par la pile live; les gates ont donc utilisé l'environnement verrouillé existant via `uv run --locked --no-sync python -m ost_gate.cli`;
- aucun service live n'a été interrompu;
- le fichier local ignoré `config/application.yaml` a reçu l'identité `development` exigée par le nouveau schéma afin de conserver les parcours live; aucun secret ni donnée métier n'a été modifié.

ADR consultée: ADR-045. Aucune nouvelle ADR ni modification de sens n'est requise.

Commit GREEN prévu: `feat(platform): refuser les stockages hors environnement`.

## Validation de la planification

- `uv run --locked gate --scope governance` - GREEN après création des tâches; 25 nœuds, aucune exécution manquante, inattendue ou dupliquée.
- `uv run --locked gate --scope m013_config` - GREEN; 36 nœuds couvrant les préconditions M-001 à M-012 et les validations du chargeur, de la spécification, de Compose, des runbooks, du gateway et de la traçabilité M13-config.
- `git diff --check` - GREEN; avertissement de normalisation LF vers CRLF uniquement, sans erreur d'espacement.

Périmètre contrôlé: un fichier de plan, douze fichiers de tâches et ce journal. Aucun autre artefact n'est modifié.

## T-005 - Scénario BDD et preuve RED

Scénario contrôlé:

- Given un identifiant sentinelle et un PDF réel sont écrits dans les racines d'un profil.
- When les coordonnées PostgreSQL, Qdrant, files, outbox, caches, volumes, chemins et secrets des trois profils sont validées puis que les deux autres profils recherchent ces sentinelles.
- Then chaque coordonnée et autorité mutable est propre au profil, aucune racine résolue ne se chevauche et aucune sentinelle ni référence de secret de production n'est visible depuis les deux autres profils.

Précondition GREEN avant modification:

- `uv run --locked --no-sync python -m ost_gate.cli --scope m013_environments` - GREEN; 26 nœuds exécutés;
- `uv run --locked --no-sync python -m ost_gate.cli` - GREEN; 441 nœuds exécutés, parcours live inclus;
- la pile live existante et le fichier local ignoré `config/application.yaml` sont restés actifs et inchangés pendant cette vérification.

Preuve RED attendue:

- le test d'acceptation exige les trois configurations complètes, inventorie tous les stockages de `app/context_registry.json` et écrit de vraies sentinelles sur les racines fichiers isolées;
- le test unitaire exige un validateur fail-closed de la matrice et couvre collisions d'URL, base, rôle, collection, outbox, secret, chemin résolu, profil absent, alias contradictoire et URL PostgreSQL incohérente;
- le RED doit provenir de l'absence de `app.platform.environment_resources` et des trois fichiers complets, sans démarrer ni reconfigurer les piles réservées à T-006.
- `uv run --locked --no-sync pytest -q gate_tests/ported/tests/m013_environments/validate_environment_resource_isolation_acceptance.py gate_tests/ported/tests/m013_environments/validate_environment_resource_isolation_unit.py` - RED utile; 2 tests échouent uniquement sur `ModuleNotFoundError: No module named 'app.platform.environment_resources'`.

ADR consultée: ADR-045. Aucune nouvelle ADR n'est requise: T-005 matérialise la matrice de ressources déjà décidée.

Commit RED prévu: `test(platform): couvrir etancheite des ressources mutables`.

Commit RED créé:

- `a294ef510` - `test(platform): couvrir etancheite des ressources mutables`.

## T-005 - Isolation des ressources et retour GREEN

Implémentation livrée:

- trois fichiers complets et autonomes existent sous `config/environments/`, avec les identités `ostrading-development-local`, `ostrading-test-ci` et `ostrading-production-primary`;
- chaque profil possède une URL, une base, un rôle, un volume et un chemin de secret PostgreSQL propres;
- chaque profil possède une URL, une instance, un volume, deux collections et un chemin de credential Qdrant propres;
- les files, outbox, espaces de progression, racines de données, corpus, sources canoniques, Qdrant, PostgreSQL, rapports, logs, expériences, caches et cinq chemins de secrets sont liés au profil;
- `app.platform.environment_resources` inventorie tous les stockages de `app/context_registry.json`, exige exactement les trois profils et refuse les collisions textuelles, les alias contradictoires, les incohérences URL/base/rôle et tout chevauchement parent-enfant entre chemins résolus de profils différents;
- le chargeur typé porte les nouvelles coordonnées et refuse les credentials PostgreSQL ou Qdrant en clair dans les URLs;
- les adaptateurs Qdrant d'identité, de projection et de recherche consomment désormais les noms de collections du profil; les noms génériques précédemment codés en dur ont été retirés du code applicatif;
- l'exemple versionné et la configuration Compose historique portent les nouvelles clés sans contenir de secret; le fichier local ignoré `config/application.yaml` a seulement reçu les clés rendues obligatoires, en conservant ses valeurs locales et sans redémarrage de service.

Preuves d'étanchéité:

- le test d'acceptation initialise les neuf racines fichiers de chaque profil avec le vrai `FileRootIdentityPreflight`, écrit un PDF et des sentinelles physiques dans un répertoire temporaire, puis prouve leur invisibilité depuis les dix-huit vues étrangères;
- la matrice compare les coordonnées PostgreSQL, Qdrant, workers, chemins et secrets deux à deux et prouve que les références de secrets de production sont absentes des configurations `development` et `test`;
- PostgreSQL et Qdrant réels ne sont pas démarrés séparément par T-005: leurs écritures croisées réelles nécessitent les piles et secrets de T-006; aucun mock ni fallback ne se substitue à cette preuve différée.

Validations GREEN:

- tests ciblés chargeur, identité et étanchéité - GREEN; 5 tests;
- `uv run --locked --no-sync python -m ost_gate.cli --scope m013_environments` - GREEN; 28 nœuds;
- `uv run --locked --no-sync python -m ost_gate.cli --scope m013_config` - GREEN; 36 nœuds;
- `uv run --locked --no-sync python -m ost_gate.cli --scope m013_fastapi` - GREEN; 80 nœuds, validations live incluses;
- `uv run --locked --no-sync python -m ost_gate.cli` - GREEN; 443 nœuds, parcours live M-004 et M-013 inclus;
- `uv run --locked --no-sync python -m compileall -q app` - GREEN;
- `git diff --check` - GREEN, avec uniquement les avertissements de normalisation LF vers CRLF.

Contrainte d'outillage:

- `.venv/Scripts/ui.exe` reste utilisé par la pile live, donc les commandes conservent `--no-sync`; aucun service live n'a été interrompu ou reconfiguré.

ADR consultée: ADR-045. Aucune nouvelle ADR ni modification de sens n'est requise.

Commit GREEN prévu: `feat(platform): isoler les donnees par environnement`.

## T-006 - Scénario BDD et preuve RED

Scénario contrôlé:

- Given les trois jeux de configuration et de secrets existent.
- When une commande d'environnement démarre sa pile Compose et agrège la readiness de ses composants réels.
- Then seuls les réseaux, volumes, credentials et montages nommés pour ce profil sont attachés, chaque service applicatif reçoit le même fichier et le même répertoire de secrets en lecture seule, et l'état `ready` exige API, UI, gateway, workers, PostgreSQL et Qdrant concordants.

Précondition GREEN avant modification:

- `uv run --locked gate --scope m013_environments` - GREEN; 28 nœuds exécutés, aucune exécution manquante, inattendue ou dupliquée;
- la pile legacy `uv run ui` a été identifiée par sa racine PID 25592 et ses deux conteneurs labellisés `com.ostrading.managed-by=uv-run-ui`, puis arrêtée sans suppression de volume ni de donnée afin de libérer l'exécutable UV et les ports;
- `http://192.168.1.120:8000/v1/models` répond HTTP 200 et publie le modèle réel `google/gemma-4-26B-A4B-it` sans authentification ni TLS, conformément à ADR-014.

Preuve RED attendue:

- le test d'acceptation exige le rendu Docker Compose effectif de trois projets complets, leurs ports loopback distincts, leurs réseaux et volumes sans collision, leurs secrets propres, le montage read-only du fichier de profil et du répertoire de secrets dans tous les services applicatifs, ainsi que le raccordement commun au Spark réel disponible;
- le test unitaire exige un mapping fermé des trois piles et une agrégation fail-closed de la readiness de tous les services, dont `worker-projection`;
- le RED doit provenir de l'absence de `app.platform.environment_compose` et des trois manifestes, sans introduire de fallback vers la pile hôte legacy.
- `uv run --locked pytest -q gate_tests/ported/tests/m013_environments/validate_environment_compose_acceptance.py gate_tests/ported/tests/m013_environments/validate_environment_compose_unit.py` - RED utile; 2 tests échouent uniquement sur `ModuleNotFoundError: No module named 'app.platform.environment_compose'`.

ADR consultées: ADR-045, ADR-026 et ADR-014. Aucune nouvelle ADR n'est requise: T-006 matérialise les décisions déjà acceptées.

Commit RED prévu: `test(deploy): couvrir les trois piles etanches`.

Commit RED créé:

- `7c33adfa2` - `test(deploy): couvrir les trois piles etanches`.

## T-006 - Orchestration réelle et retour GREEN

Implémentation livrée:

- `uv run development`, `uv run test` et `uv run production` sélectionnent
  chacune un projet Compose fermé et son overlay explicite, sans option
  `--config` exposée à l'opérateur;
- chaque pile comporte quinze services requis et dix-sept conteneurs avec deux
  réplicas de `worker-documents` et deux de `worker-projection`;
- les fichiers de configuration, répertoires de secrets, bases PostgreSQL,
  instances Qdrant, volumes applicatifs, réseaux, DNS et ports loopback sont
  propres au profil;
- les manifestes OCRmyPDF et Docling versionnés sont copiés dans l'image du
  worker; les actifs Docling scellés sont montés en lecture seule;
- chaque pile possède un moteur Docker OCR interne, un réseau de contrôle et un
  volume propres. L'image OCRmyPDF est préchargée par digest avant readiness et
  aucun socket Docker hôte n'est exposé;
- la readiness agrège toutes les réplicas et parse le flux NDJSON réel de
  `docker compose ps`; un service absent, étranger, arrêté ou malsain provoque
  un échec terminal;
- l'arrêt des commandes détruit uniquement les conteneurs et réseaux du projet,
  jamais ses volumes.

Corrections issues des démarrages réels:

- les migrations ne sont plus exécutées par `docker-entrypoint-initdb.d`, qui
  cassait la transaction de la migration 017; l'API demeure l'autorité unique
  du runner transactionnel;
- les pourcentages littéraux de l'inventaire PostgreSQL sont échappés pour
  `psycopg` (`pg_toast%%`);
- les racines de données des trois profils sont créées et attribuées à
  l'utilisateur non-root avant montage des volumes;
- les workers documents reçoivent les trois manifestes, les actifs Docling
  réels et le moteur OCR isolé exigés par leur préflight strict;
- le harness produit M13 démarre désormais PostgreSQL et Qdrant réels sur deux
  ports loopback distincts et isole toutes ses racines fichiers dans son
  répertoire temporaire; le préflight d'identité ne dépend plus d'un DNS
  Compose ni des données locales du dépôt.

Preuves live simultanées:

- les trois projets `ostrading-development`, `ostrading-test` et
  `ostrading-production` démarrent simultanément sans collision et atteignent
  tous `running/healthy` pour leurs quinze services requis;
- `https://localhost:18443/health`, `:19443/health` et `:20443/health`
  répondent chacun HTTP 200 avec `healthy`;
- PostgreSQL publie respectivement `development|ostrading-development-local`,
  `test|ostrading-test-ci` et `production|ostrading-production-primary`;
- les marqueurs fichiers portent les mêmes identités et Qdrant ne contient que
  la collection d'identité du profil courant;
- les résolutions croisées `development -> postgres-test`,
  `test -> postgres-production` et `production -> postgres-development`
  échouent, prouvant l'absence de DNS inter-piles;
- le Spark réel `192.168.1.120:8000` est utilisé par les trois gateways et
  publie `google/gemma-4-26B-A4B-it`.

Validations GREEN:

- quatre tests ciblés Compose, commandes et identité - GREEN;
- `uv run --locked gate --scope m013_environments` - GREEN; 30 nœuds;
- `uv run --locked gate --scope m013_config` - GREEN; 36 nœuds;
- `uv run --locked gate --scope m013_fastapi` - GREEN; 80 nœuds, contrôles live
  inclus;
- test produit M13-reality ciblé - GREEN; PostgreSQL, Qdrant, API, gateway et
  Spark réels, 1 test en 31,62 s;
- `uv run --locked gate` - GREEN; 445 nœuds, aucun nœud non GREEN;
- `uv run --locked python -m compileall -q app` - GREEN;
- `git diff --check` - GREEN, hors avertissements LF vers CRLF;
- rendu `docker compose config` des trois profils - GREEN;
- agrégation live de readiness des trois profils - GREEN; quinze services par
  profil.

ADR consultées: ADR-045, ADR-026, ADR-014 et ADR-032. Aucune nouvelle ADR n'est
requise: le moteur OCR dédié matérialise l'isolation d'exécution et l'obligation
d'un runtime réel déjà décidées.

Commit GREEN prévu: `feat(deploy): orchestrer les piles par environnement`.

## T-008 - Opérations administratives bornées

Scénario BDD livré :

- Given un nettoyage `test` reçoit un stockage marqué `production` ;
- When le préflight compare la cible et l'identité observée ;
- Then `DATASTORE_ENVIRONMENT_MISMATCH` est audité, aucune mutation n'est
  appelée et les données étrangères restent intactes.

Implémentation :

- `AdministrativeOperationRequest` rend obligatoires l'opération, le couple
  `environment`/`deployment_id`, le caractère automatique et, pour le
  nettoyage de test, les identifiants de cycle et de propriétaire ;
- migration, sauvegarde, restauration, purge et nettoyage passent tous par le
  même garde-fou avant le callback de mutation ;
- le manifeste `M013-BackupManifest-1.0` porte désormais l'identité de
  l'installation et une restauration croisée est refusée ;
- `backup-v1` et `restore-v1` exigent une configuration explicite, contrôlent
  les stockages réels puis publient une preuve d'autorisation ou de refus ;
- `uv run test` est l'unique propriétaire du `down --volumes` de
  `ostrading-test`, après contrôle de PostgreSQL, Qdrant et de la racine de
  données ; `development` et `production` arrêtent leurs conteneurs sans
  supprimer leurs volumes ;
- si le contrôle du nettoyage test échoue, les conteneurs sont arrêtés, les
  volumes sont conservés et l'erreur n'est pas masquée.

ADR consultées : ADR-013, ADR-021 et ADR-045. Aucune nouvelle ADR n'est
requise : T-008 matérialise leurs décisions de manifeste, migration et bornage
des opérations destructives sans introduire une nouvelle politique.

Commit RED : `f0ef9f32b` - `test(operations): couvrir bornage par environnement`.

Commit GREEN prévu : `feat(operations): proteger les operations par profil`.

Validations GREEN :

- tests d'acceptation et unitaires administratifs : 2 tests ;
- tests ciblés commandes, Compose et opérations : 6 tests ;
- `uv run --locked gate --scope m013_environments` : 34 nœuds ;
- `uv run --locked gate --scope m013_config` : 36 nœuds ;
- `uv run --locked gate --scope m013` : 68 nœuds, parcours produit réel
  inclus ;
- `uv run --locked gate --scope m013_fastapi` : 80 nœuds, migrations et
  opérations runtime incluses ;
- `uv run --locked gate` : 449 nœuds, tous GREEN ;
- `uv run --locked python -m compileall -q app ost_gate` : GREEN ;
- `git diff --check` : GREEN hors avertissements de conversion LF/CRLF ;
- sentinelles Docker avant/après : noms, dates de création et points de
  montage des volumes development, test et production strictement inchangés.

La preuve destructive du `down --volumes` test est différée au parcours T-010,
qui possède explicitement la création et la destruction de ses données. T-008
n'a supprimé, recréé ni modifié aucun volume existant pendant ses validations.

## T-009 - Scénario BDD et preuve RED

Scénario contrôlé :

- Given `uv run development` a rendu la pile réelle prête avec l'identité
  `development` / `ostrading-development-local` et le PDF réel versionné
  `data/corpus/the-original-turtle-trading-rules.pdf` ;
- When le validateur live utilise exclusivement les endpoints publics pour
  enregistrer, diagnostiquer, convertir, projeter, rechercher, interroger le
  Spark réel et ouvrir la citation PDF, puis redémarre la pile sans volume
  supprimé ;
- Then les progressions publiques réussissent, les mêmes objets documentaires
  sont relus après redémarrage et les profils `test` et `production` ne voient
  aucun de leurs identifiants.

Précondition GREEN avant modification :

- `uv run --locked gate --scope m013_environments` : GREEN, 34 nœuds ;
- `uv run --locked gate --scope m013_config` : GREEN, 36 nœuds ;
- `uv run --locked gate --scope m013` : GREEN, 68 nœuds ;
- `uv run --locked gate --scope m013_fastapi` : GREEN, 80 nœuds ;
- `uv run --locked gate` : GREEN, 449 nœuds en 282 secondes.

Preuve RED attendue :

- le test d'acceptation live appelle
  `app.platform.development_e2e.run_development_environment_e2e` avec le PDF
  réel du corpus ;
- le rapport exigé porte les identifiants document, version canonique,
  projection et réponse, l'URL de citation ouvrable, l'identifiant brut Spark,
  les trois progressions réussies, la relecture après redémarrage et les deux
  sondes négatives ;
- le RED doit provenir de l'absence du validateur live, sans mock, stub, fake,
  accès direct aux repositories ou affaiblissement du parcours.

ADR consultées : ADR-031, ADR-032, ADR-038 et ADR-045. Aucune nouvelle ADR
n'est requise : T-009 exécute les décisions déjà acceptées sur la chaîne réelle,
la progression publique, les citations et l'étanchéité des profils.

Commit RED prévu : `test(m13-environments): couvrir parcours reel development`.

## T-009 - Retour GREEN du parcours development réel

Scénario réellement exécuté :

- le PDF suivi `data/corpus/the-original-turtle-trading-rules.pdf` contient 38
  pages et porte le SHA-256
  `073f361ebb4ac6c10765a21ba7cca42d75fde8fabadc84340e6bbfca444fbda4` ;
- le validateur réémet toutes ses pages, vérifie les flux de contenu page par
  page, ajoute uniquement les métadonnées de preuve puis obtient le SHA-256
  distinct `ba58a26e6a853c3cc891e53c19db03eba42bf3e829d2579f37c02969560c24ee` ;
- `uv run development` démarre la pile complète, attend la readiness de
  l'exécution courante, puis les contrats publics couvrent UI, enregistrement,
  diagnostic, conversion, projection, recherche, conversation, réponse,
  citation, PDF original et appel Spark live ;
- la pile est arrêtée, entièrement supprimée sans ses volumes, redémarrée et
  relit les mêmes document, version canonique et projection ;
- les piles test et production sont sondées sans écriture et ne voient pas le
  document development.

Corrections TDD découvertes par les exécutions réelles :

- sérialisation JSON Gemma sûre pour les tableaux Docling ;
- budget du worker documentaire porté à 8 Gio et 4 CPU, healthcheck porté à
  30 secondes ;
- sélection live des gates rendue explicitement opt-in par scope afin qu'un
  gate structurel ne déclenche jamais silencieusement un parcours live ;
- reprise de conversion rendue monotone : les callbacks déjà persistés sont
  absorbés avant le prochain incrément et un conflit publie désormais
  `CONVERSION_PERSISTENCE_CONFLICT` ;
- readiness du harness bornée aux événements de cycle de vie écrits après le
  lancement courant, afin d'ignorer une ancienne pile encore joignable ;
- cache des dépendances de construction des images ;
- checkpoint sans secret écrit avant le premier arrêt et reprise explicite
  d'une preuve existante, sans nouvel upload ;
- superviseur de services indépendant de la sémantique non portable de
  `docker compose wait` : il observe tous les conteneurs, accepte uniquement
  `edge-gateway` arrêtée avec le code 0 et rend terminale toute sortie worker ;
- six décisions unitaires du parcours regroupées dans l'unique nœud pytest
  déclaré au manifeste, conformément au contrat d'exécution atomique du gate.

Les échecs réels rencontrés ont été conservés. En particulier,
`DOC-B84311A80ECFC161` a démontré la reprise durable : son compteur public est
resté à `37/38` pendant le recalcul, puis la tentative 3 a abouti à `38/38`,
`CANONICAL_ACCEPTED`, sans régression de progression.

Preuve finale GREEN :

- rapport :
  `data/environments/development/reports/development-e2e-20260721T224955Z-2351ED7F4FFD468596130493DA499703.json` ;
- image : `f509a25647d417ee1fdaac6ede91785482656be0` ;
- document : `DOC-BA58A26E6A853C3C` ;
- version canonique : `CVER-M004-ROUTED-BA58A26E6A853C3CC891E53C` ;
- projection :
  `PROJ-FF2E986C45A492B10A4DD70C1CC3863FDECEDF609B1709A6F8FB839E671F89F7`,
  55 chunks ;
- réponse : `ANS-LIVE-0AA5A9421114598B47CC`, support
  `PARTIALLY_SUPPORTED` ;
- citation ouvrable :
  `https://localhost:18443/api/v1/documents/DOC-BA58A26E6A853C3C/original#page=36` ;
- réponse brute Spark :
  `chatcmpl-REQ-DEVELOPMENT-E2E-SPARK-2351ED7F4FFD468596130493DA499703` ;
- progressions diagnostic, conversion et projection : trois fois
  `SUCCEEDED` ;
- identités : 6 conteneurs workers vérifiés et 3 jobs development concordants ;
- redémarrage : `restart_persistence_verified=true` ;
- étanchéité : `test:ABSENT`, `production:ABSENT` ;
- volumes : neuf sentinelles development inchangées, aucun conteneur
  development, test ou production laissé actif.

Validations GREEN :

- reprise explicite BA58 avec le parcours complet, deux démarrages réels,
  sondes étrangères et rapport final : code 0 en 392,8 secondes ;
- tests ciblés du validateur, des commandes et de Compose : 3 nœuds GREEN, le
  nœud du parcours agrégeant 6 décisions unitaires ;
- `uv run --locked gate --scope m013_environments` : 36 nœuds GREEN en mode
  offline, unicité du manifeste vérifiée ;
- Ruff, `compileall` ciblé et `git diff --check` : GREEN.

Commits TDD structurants de clôture :

- `1f499d4c3` / `a024bcf67` : readiness de l'exécution courante ;
- `b94564d9c` / `730581f83` : arrêt volontaire par la passerelle ;
- `81c703ec8` / `b8caae5c0`, ensuite remplacé après preuve live ;
- `e79b94f94` / `7b0a13769` : reprise explicite de preuve ;
- `f7f7b8994` / `abdc2b89d` : checkpoint produit avant arrêt ;
- `bc9bacee2` / `f509a2564` : supervision réelle du premier service terminé.

## T-010 - Scénario BDD et preuve RED

Scénario contrôlé :

- Given les ressources `test` sont créées depuis un état vide déterministe,
  les credentials non-test ne sont pas montés et les volumes development et
  production sont enregistrés comme sentinelles ;
- When `uv run test` exécute deux fois le parcours PDF réel complet via API,
  outbox, relais, workers, PostgreSQL, Qdrant et Spark, puis termine ;
- Then les deux rapports écrits avant teardown sont GREEN, les documents sont
  distincts, seules les ressources `ostrading-test` sont supprimées après
  vérification d'identité et les sentinelles étrangères restent inchangées.

Précondition GREEN avant modification :

- `uv run --locked gate --scope m013_environments` : 36 nœuds GREEN.

La preuve RED exige le module `app.platform.test_e2e`, absent avant
implémentation. L'acceptation live refuse tout mock, fallback, accès aux
credentials development/production ou teardown non borné. Le test unitaire
exige exactement deux cycles ordonnés et le refus d'une cible de nettoyage
étrangère.

ADR consultée : ADR-045. Aucune nouvelle ADR n'est requise : T-010 exécute sa
politique déjà acceptée de profil test jetable, d'identité obligatoire et de
suppression exclusivement bornée.

Commit RED prévu : `test(m13-environments): couvrir parcours reel test`.

## T-010 - Retour GREEN des deux parcours test réels

Implémentation :

- `uv run test` n'est plus un serveur persistant : il qualifie deux
  installations test successives, finies et entièrement neuves ;
- une phase initiale reprend une éventuelle installation test existante,
  vérifie son identité réelle puis la supprime avant le premier cycle ;
- chaque cycle réémet les 38 pages du PDF suivi avec un identifiant de preuve
  distinct, exige un corpus public initial vide et traverse UI, API,
  PostgreSQL, outbox, relais, workers, conversion, Qdrant, recherche, chat,
  citation PDF et Spark réel ;
- le validateur rend explicites l'URL, l'environnement, le deployment, le
  conteneur PostgreSQL et les credentials du seul profil courant ;
- le rendu Compose et les 17 conteneurs sont inspectés pour refuser tout
  chemin development/production ;
- les deux workers documentaires sont inspectés à l'exécution : limite de
  8 Gio, 4 CPU et healthcheck de 30 secondes ;
- le rapport de chaque cycle est écrit avant la sortie du contexte ; en cas
  d'échec produit il porte `status=RED`, l'erreur reste terminale et la sortie
  du contexte exécute le teardown contrôlé ;
- le rapport agrégé est écrit après preuve de disparition de toute ressource
  test et égalité exacte des sentinelles development/production avant/après.

Preuve live finale :

- `uv run test` : code 0 en `8093,1 s` ;
- rapport :
  `data/environments/test/reports/test-e2e-20260722T012720Z.json` ;
- exécution 1 : `DOC-EE140CC90ADADCD5`,
  `CVER-M004-ROUTED-EE140CC90ADADCD5E089C53A`, projection `PROJ-69572…`,
  réponse `ANS-LIVE-DC524D9BD92D465A3C99` et Spark live ;
- exécution 2 : `DOC-D20D052ED84E8A50`,
  `CVER-M004-ROUTED-D20D052ED84E8A50B3F6602B`, projection `PROJ-CFB61…`,
  réponse `ANS-LIVE-35657C78A8CCA1AD211F` et Spark live ;
- trois progressions `SUCCEEDED` par cycle, citation PDF page 36 ouvrable,
  six workers et trois jobs d'identité test par cycle ;
- `non_test_credentials_inaccessible=true`,
  `foreign_volume_sentinels_preserved=true`,
  `test_resources_removed=true` ;
- état final : zéro conteneur, volume ou réseau `ostrading-test-*`.

Preuve du chemin RED : le test unitaire force `PRODUCT_RED` dans la chaîne
réelle du superviseur et observe strictement `enter`, écriture du rapport
`RED`, puis `exit`; l'entrypoint propage ensuite `QUALIFICATION_RED` avec le
code 1. Un cleanup visant production reste refusé par
`ADMINISTRATIVE_OPERATION_FORBIDDEN`.

ADR consultée : ADR-045. Aucune nouvelle ADR n'est requise.

Commit RED : `684a8124c` -
`test(m13-environments): couvrir parcours reel test`.

Commit GREEN prévu :
`feat(m13-environments): isoler et executer le profil test`.

Validations GREEN finales :

- test unitaire T-010, acceptation des commandes et non-régression T-009 :
  3 nœuds ;
- `uv run --locked gate --scope m013_environments` : 37 nœuds ;
- `uv run --locked gate --scope m013_config` : GREEN ;
- `uv run --locked gate --scope m013` : GREEN ;
- `uv run --locked gate --scope m013_fastapi` : GREEN ;
- scope M-004 après correction du contrat atomique : 44 nœuds GREEN ;
- `uv run --locked gate --offline` : 439/439 nœuds GREEN, zéro RED,
  zéro `NOT_RUN` et manifeste unique.

Le premier gate global a exposé `GATE_TEST_RESULT_REQUIRED` sur
`validate_parallel_page_conversion_unit.py` : T-009 y avait ajouté un second
test public alors que chaque fichier du manifeste représente un nœud pytest
atomique. Les deux comportements étaient GREEN seuls. Ils sont conservés sans
affaiblissement sous deux fonctions de validation privées appelées par un
unique test public ; le scope M-004 puis le gate complet sont redevenus GREEN.

## T-011 - Scénario BDD et preuve RED

Scénario contrôlé :

- Given `uv run production` a validé l'identité de PostgreSQL, Qdrant, fichiers
  et de chacun de ses workers, sans monter de ressource non-production ;
- When le PDF réel de 38 pages traverse les contrats publics jusqu'à une
  réponse vérifiée, puis la pile redémarre et relit la preuve ;
- Then document, version canonique, projection, réponse, citation et rapport
  restent persistants, les volumes ne sont jamais supprimés et development/test
  ne peuvent lire aucun identifiant production.

Précondition GREEN avant modification :

- `uv run --locked gate --scope m013_environments` : 37 nœuds GREEN.

La preuve RED exige le module `app.platform.production_e2e`, absent avant
implémentation. L'acceptation live refuse tout mock, fallback, cleanup ou
credential non-production. Le test unitaire exige deux phases ordonnées,
l'entrypoint de qualification et le refus structurel d'un montage test.

ADR consultée : ADR-045. Aucune nouvelle ADR n'est requise : T-011 exécute sa
politique déjà acceptée de profil production protégé, persistant et strictement
identifié.

Commit RED prévu : `test(m13-environments): couvrir parcours reel production`.

## T-011 - Retour GREEN du parcours production réel

Implémentation :

- `uv run production` devient une qualification réelle, finie, persistante et
  non destructive avec le seul profil production ;
- le superviseur réémet les 38 pages du PDF suivi sous le répertoire temporaire
  de rapports production, puis traverse UI, API, PostgreSQL, outbox, relais,
  workers, Docling, Qdrant, recherche, chat, citation PDF et Spark live ;
- le rendu Compose et les 17 conteneurs sont inspectés afin de refuser tout
  chemin de configuration, secret ou donnée development/test ;
- les six réplicas workers publient l'identité et le hash production ; les
  workers documentaires sont inspectés à 8 Gio, 4 CPU et 30 secondes de
  healthcheck ;
- un checkpoint produit sans secret est écrit avant le premier arrêt ;
- la pile est arrêtée sans `--volumes`, redémarrée et relit les mêmes document,
  version canonique, projection et PDF original ;
- development est sondé par son contrat public sans mutation et l'absence
  complète de stockage test est exigée, sans créer ni nettoyer test depuis la
  commande production ;
- la sortie finale exige la disparition des conteneurs production, la présence
  exacte des sept volumes attendus et la conservation bit à bit des sentinelles
  déjà présentes.

Preuve live finale :

- `uv run production` : code 0 en `4 348 s` ;
- rapport :
  `data/environments/production/reports/production-e2e-20260722T030253Z-7FC7E3A32E8E433AA03412FA6A1620D0.json` ;
- document `DOC-ABFED3329D1BF463` ;
- version canonique `CVER-M004-ROUTED-ABFED3329D1BF46350220297` ;
- projection
  `PROJ-903E37A59A7030A4CEAA8D37036609135CE4F2CB807B2D076433DE964170A84D` ;
- réponse `ANS-LIVE-DE287349F91D99AB351B`, support
  `PARTIALLY_SUPPORTED` ;
- citation PDF page 34 et réponse brute Spark
  `chatcmpl-REQ-PRODUCTION-E2E-SPARK-7FC7E3A32E8E433AA03412FA6A1620D0` ;
- trois progressions `SUCCEEDED`, conversion `38/38`, six workers et trois jobs
  d'identité production ;
- `restart_persistence_verified=true`, sondes `development:ABSENT` et
  `test:ABSENT`, `production_resources_preserved=true`,
  `non_production_credentials_inaccessible=true` et
  `automatic_cleanup_performed=false` ;
- état final : zéro conteneur development/test/production, sept volumes
  production conservés et zéro volume test.

ADR consultée : ADR-045. Aucune nouvelle ADR n'est requise.

Commit RED : `cff8197b7` -
`test(m13-environments): couvrir parcours reel production`.

Commit GREEN prévu :
`feat(m13-environments): valider parcours production`.

Validations GREEN finales :

- test unitaire production, commandes et non-régressions development/test :
  4 tests GREEN ;
- Ruff, `compileall`, `git diff --check` et scan indépendant du rapport contre
  les cinq secrets production : GREEN ;
- `uv run --locked gate --scope m013_environments` : 38 nœuds GREEN ;
- `uv run --locked gate --scope m013_config` : 36 nœuds GREEN ;
- `uv run --locked gate --scope m013` : GREEN ;
- `uv run --locked gate --scope m013_fastapi` : 70 nœuds GREEN ;
- `uv run --locked gate --offline` : 440/440 nœuds GREEN, zéro RED, zéro
  `NOT_RUN`, manifeste unique.

## T-012 - Scénario BDD et preuve RED

Scénario contrôlé :

- Given les rapports réels development, test et production existent et la
  matrice couvre toutes les ressources mutables et tous les workers ;
- When les gates statique et live M13-environments relient ADR-045,
  spécification, code, tests, runbooks et preuves ;
- Then une preuve absente, une collision, un secret ou une couverture
  incomplète rend la qualification RED et le sous-milestone ne clôt pas M-013
  globalement.

Précondition GREEN avant modification :

- `uv run --locked gate --scope m013_environments` : 38 nœuds GREEN, aucune
  exécution manquante, inattendue ou dupliquée.

Preuve RED utile :

- tests ciblés de gouvernance : 2 échecs strictement causés par
  `ModuleNotFoundError: No module named 'ost_gate.environment_governance'` ;
- commit RED : `9bd76938c` -
  `test(governance): couvrir tracabilite m13 environments`.

ADR consultée : ADR-045. Aucune nouvelle ADR n'est requise : T-012 matérialise
la gouvernance, l'exploitation et les preuves prévues par la décision acceptée
sans la modifier ni la remplacer.

## T-012 - Retour GREEN de la gouvernance environnementale

Implémentation :

- preuve versionnée normalisée de quatre exécutions réelles, reliée par
  SHA-256 aux trois rapports sources et refusant toute donnée sensible ;
- parser strict des rapports development, des deux cycles test et de
  production, avec refus des collisions d'identifiants, hashes de
  configuration partagés, progressions incomplètes, workers absents et
  garde-fous d'isolation manquants ;
- matrice d'accès 3 × 3, inventaire des coordonnées de configuration, projets,
  réseaux, volumes, chemins de secrets et des quatre services workers pour six
  réplicas par profil ;
- runbook unique autour de `uv run development`, `uv run test` et
  `uv run production`, avec arrêt, migration, sauvegarde et restauration
  bornés ;
- traçabilité machine des douze tâches vers ADR-045, spécification, code,
  tests, rapports et runbook ;
- gate statique distincte d'une gate live consolidée dépendant des trois vrais
  parcours E2E ;
- statut fermé `SUBMILESTONE_GREEN_M013_OPEN`, qui interdit toute clôture
  implicite du milestone M-013 global.

Commit GREEN : ce commit -
`docs(governance): relier environnements aux preuves`.

Validations GREEN finales :

- tests de gouvernance unitaire et statique : 2 tests GREEN ;
- consolidation ciblée des trois rapports live existants : 1 test GREEN, sans
  redémarrer les piles coûteuses ;
- `uv run --locked gate --scope m013_environments` : 40 nœuds GREEN, zéro
  exécution manquante, inattendue ou dupliquée ;
- `uv run --locked gate --scope governance` : 25 nœuds GREEN ;
- `uv run --locked gate --offline` : 442/442 nœuds GREEN, zéro RED, zéro
  `NOT_RUN`, manifeste unique ;
- le plan statique enrôle seulement l'acceptation et l'unitaire T-012 ; le plan
  `--live` ajoute les trois vrais E2E puis la consolidation live ;
- Ruff et `compileall` : GREEN.

Les parcours live n'ont pas été rejoués pendant T-012 : leurs rapports réels,
leurs SHA-256 et leurs données d'exécution ont alimenté la gate statique. La
commande live explicite et rejouable reste
`uv run --locked gate --scope m013_environments --live`.
