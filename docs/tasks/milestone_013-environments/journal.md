# Journal M13-environments

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
