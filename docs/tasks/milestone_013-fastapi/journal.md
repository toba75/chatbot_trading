# Journal M13-FastAPI

## Planification initiale

- Date: 2026-07-12.
- Statut: PLANIFIÉ, non implémenté.
- Source canonique: `docs/specs/plan_implementation_milestones_workstreams.md`, section `M13-FastAPI - API orchestratrice ASGI raccordée`.
- Sous-milestone: `M13-FastAPI` conserve l'ancrage M-013, requiert M-001 à M-012 dans `master` et ne clôt pas M-013.
- Précondition observée: M-001 à M-012 présents dans `master` au commit `8670e88f9`.
- Décision attendue: ADR-019 pour `FastAPI + Uvicorn` sur `orchestrator-api` uniquement.
- ADR gouvernante existante: ADR-018, UI exclusivement via l'API orchestratrice.
- Test RED préexistant à reprendre: commit `8ec5231e4`, `tests/m013/validate_document_api_wiring_acceptance.ps1`.
- Modification utilisateur hors périmètre: `tests/m013/validate_m013_reality_product_acceptance.ps1`.

## Ordre d'exécution

1. T-001 - Précondition GREEN.
2. T-002 - Décision et spécification de la frontière HTTP.
3. T-003 - Application ASGI, composition et santé.
4. T-004 - Parité des contrats existants.
5. T-005 - État documentaire durable partagé.
6. T-006 - Enregistrement PDF et diagnostic.
7. T-007 - Lectures diagnostic et conversion.
8. T-008 - PDF original contrôlé.
9. T-009 - Lecture de projection KA.
10. T-010 - UI exclusivement via l'API.
11. T-011 - Déploiement, audit et gates.

## Limites de planification

- Aucun code `app/` n'est implémenté par cette planification.
- Aucun résultat GREEN futur n'est déclaré.
- Aucun repository en mémoire, mock, stub ou fallback n'est admis comme runtime ou preuve de parcours réel.
- Une dépendance non câblée conserve une erreur explicite jusqu'à son raccordement effectif.

## T-001 - Précondition GREEN

- Date: 2026-07-12.
- Statut: IMPLÉMENTÉE par gates bornées; la gate globale reste sans verdict.
- Base reconstruite: `master` et `origin/master` au commit `35fb5a4f8`.
- Commit RED: `c79f93b2c`, `test(platform): couvrir precondition m13 fastapi`.
- Implémentation: récupération strictement bornée des allowlists M-003 à M-013 pour `codex/m13-fastapi` et publication de `docs/governance/m013_fastapi_precondition.md`.
- Preuves GREEN: contrats M-003, M-004, M-005, frontière UI/API, frontières d'import et validateurs T-001.
- RED attendu conservé: `tests/m013/validate_document_api_wiring_acceptance.ps1`, source `8ec5231e4`, réécrit localement en `be62f3e7a`, réservé à T-006 et non enrôlé.
- Limite: `scripts/test.ps1` a dépassé une heure sur `master` sans code de sortie; aucun GREEN global n'est déclaré.
- Modification utilisateur protégée: `tests/m013/validate_m013_reality_product_acceptance.ps1`, hors staging et hors commits T-001.
- ADR: ADR-018 consultée et inchangée; aucune nouvelle ADR requise pour cette récupération locale de gate.

## T-002 - Frontière HTTP publique

- Date: 2026-07-12.
- Statut: IMPLÉMENTÉE par décision d'architecture et spécification exécutable; aucune dépendance ni application ASGI ajoutée dans cette tâche.
- Scénario: Given le routeur conditionnel partagé; When la frontière HTTP est publiée; Then FastAPI, Uvicorn, la composition root, les responsabilités interdites et la migration progressive sont vérifiables.
- Décision: ADR-019 retient FastAPI pour l'application ASGI et Uvicorn pour son serveur, uniquement dans `platform` et les adaptateurs HTTP autorisés.
- Propriété métier: SP, KA, RA et CV conservent commandes, invariants, erreurs et read-models; le transport délègue sans logique métier.
- Migration: contrat par contrat, preuve de parité avant bascule, aucun fallback silencieux et aucune migration big bang des autres services.
- ADR-018: inchangée; elle continue d'imposer le passage exclusif de l'UI par `orchestrator-api`.
- Commit RED: `7a3c3c231`, `test(architecture): couvrir frontiere asgi orchestratrice`.
- Commit GREEN: `docs(architecture): decider fastapi uvicorn ADR-019`.
- Gates: spécification, politique d'import FastAPI/Uvicorn, système ADR et validateur M13-FastAPI.

## T-011 - Déploiement et audit de l'API orchestratrice

- Date: 2026-07-12.
- Statut: implémentation et validation T-011.
- Scénario: Given l'application ASGI et les contrats documentaires GREEN; When PostgreSQL Docker et la stack Uvicorn exécutent le parcours d'un PDF réel; Then un seul `orchestrator-api` sert les contrats, trace chaque appel et bloque toute régression par la gate M13-FastAPI.
- Commit RED: `b2a00b28a`, `test(platform): couvrir deploiement audit m13 fastapi`.
- Commit GREEN: `feat(platform): deployer api orchestratrice fastapi`.
- Runtime: commande `uv run api --config`, service Compose Uvicorn au port interne 8080, readiness PostgreSQL bloquante et aucun ancien routeur actif.
- Preuve live: Docker/PostgreSQL, migrations réelles, PDF valide, HTTP multipart, lectures publiques, hash original, OpenAPI borné et traces corrélées.
- Gate: `scripts/validate_m013_fastapi.ps1`, enrôlée dans `scripts/test.ps1` et `scripts/lint.ps1`.
- ADR: ADR-019 consultée et appliquée; ADR-018 inchangée; aucune nouvelle ADR requise.
- Hors périmètre préservé: UI et `llm-gateway` ne sont pas migrés vers FastAPI.
- Résultat live: `DOC-BC6CFA26B1753E74`, PDF SHA-256 `bc6cfa26b1753e740c2749f8a854828770965f5862134ec304cb11a25e98d02a`, PostgreSQL Docker et Uvicorn HTTP.
- Image Compose: construction GREEN de `ostrading/orchestrator-api:0.0.0-m002` avec le verrou `uv.lock`.
- Gates GREEN: quatre preuves T-011, traçabilité 163 exigences, lint 38 validations et vingt validations de non-régression T-003 à T-010.
- Gate globale: `scripts/test.ps1` non concluante après la borne explicite de 10 minutes, sans sortie; aucun verdict GREEN global déclaré.

## Correctif de revue - Frontière HTTP binaire bornée

- Date: 2026-07-12.
- Source: findings sécurité, dépendances, configuration et performance sur T-006, T-008 et T-011.
- Scénario: Given un upload multipart ou un original PDF; When les octets franchissent Caddy, l'ASGI et SP; Then consommation, spool, métadonnées et chunks restent bornés, le hash est vérifié et aucune opération synchrone lourde ne bloque directement l'event-loop.
- ADR: ADR-020 créée pour compléter ADR-019 sans modifier la propriété métier de SP.
- Commits RED: `ae943a04c`, `test(api): couvrir frontiere binaire bornee ADR-020`; `d4b64cf26`, `test(sp): borner metadonnees bibliographiques ADR-020`.
- Implémentation: limite Caddy/ASGI de 54 Mo, PDF métier 50 Mio, métadonnées courtes, comptage ASGI sans double spool avant le parseur multipart, `tmpfs /tmp` 128 Mio, streaming par chunks 64 Kio, threadpool FastAPI et image builder/runtime.
- Dépendances: `pypdf==6.14.2` et `python-multipart==0.0.32`, verrou régénéré par `uv lock`.
- Preuve réelle: PDF `pypdf` supérieur à 1 Mio transmis à PostgreSQL/Uvicorn réels puis restitué avec hash identique.
- Audit dépendances: `pip-audit` indisponible localement; aucun scanner alternatif silencieux.
- Commit GREEN: `89acbdd70`, `feat(api): borner frontiere http et streaming original ADR-020`.

## Correctif de revue - Runtime et opérations

- Date: 2026-07-12.
- Source: findings migrations, timeouts, erreurs publiques, cycle de vie des ressources, client UI et runbook sur T-011.
- Scénario: Given un volume PostgreSQL pré-M13 et la configuration M13-config; When `orchestrator-api` démarre, traite une requête puis s'arrête; Then le schéma 003 est migré sous ledger/verrou avant readiness, les budgets sont propagés, toute erreur infrastructure reste JSON et traçable, et toutes les ressources sont fermées sans masquer l'erreur primaire.
- ADR: ADR-021 créée pour gouverner le runner transactionnel, le ledger SHA-256, la readiness dynamique et le rollback strictement ascendant.
- Commit RED: `3c4159a86`, `test(runtime): couvrir migrations et budgets ADR-021`.
- Commit GREEN: `439b4336f`, `feat(runtime): fiabiliser demarrage et migrations ADR-021`.
- Preuve PostgreSQL: upgrade concurrent et idempotent d'un volume pré-M13 vers `001`, `002` et `003`, avec `platform.schema_migrations` et verrou advisory.
- Budgets: `startup_seconds` pilote connexion et démarrage/migrations, `request_seconds` borne requête et healthcheck, `shutdown_seconds` pilote Uvicorn et Compose.
- Erreurs: `TRACE_ID_INVALID` en 400, timeout en 504, exception en 500, toutes avec `error_code`, `X-Trace-ID` et log JSON sans payload ni secret.
- Déploiement: image `ostrading/orchestrator-api:0.1.0-m013-fastapi-schema-003`, commandes hôte/edge séparées et rollback compatible ledger sans suppression de volume.
- Contrat historique: aucun alias public `GET /` n'est confirmé par les tests de `master`; aucune rupture d'alias public n'est introduite.
- Validations: gate M13-FastAPI 10 preuves GREEN, lint 38 validations GREEN, système ADR GREEN, Compose statique et `docker compose config` GREEN, preuves live PostgreSQL, PDF/Uvicorn et worker concurrent GREEN.
- Modification utilisateur protégée: `tests/m013/validate_m013_reality_product_acceptance.ps1`, hors staging et hors commits.
## Correctif de revue T-005 à T-007 - worker et cohérence des données

- Scénario BDD : Given une demande de diagnostic acceptée et persistée par SP; When deux processus workers concurrents relaient et réclament les jobs PostgreSQL, et qu'un propriétaire s'arrête avant résultat; Then chaque job suit `pending -> running -> succeeded|failed`, une lease expirée permet la reprise, les sorties page par page sont persistées une fois, le `trace_id` reste corrélé hors payload et un writer obsolète est refusé.
- Décision : ADR-022 applique DDD-ADR-008 par outbox SP atomique puis relais `platform`, claims `FOR UPDATE SKIP LOCKED`, leases et version optimiste; ADR-021 gouverne la migration ascendante `003_document_worker_runtime.sql`.
- Commit RED : `d9f73943f`, `test(worker): couvrir outbox leases et reprise ADR-022`.
- Commit GREEN : `d1daf1f34`, `feat(worker): executer diagnostics durables ADR-022`.
- Preuves : API Uvicorn réelle vers PostgreSQL Docker puis deux seconds processus workers; trois jobs réussis; crash/reprise; `trace_id` absent du payload; conflit `PROCESSING_RUN_VERSION_CONFLICT`; interleaving `REPEATABLE READ`; upgrade schema 003 exécuté deux fois avec ledger idempotent.
- Validations : T-005 persistance, T-006 commandes, T-007 read-models, architecture, gate M13-FastAPI et lint GREEN (38 validations).

## Correctif de revue T-009/T-010 - contrats produit KA, SP et UI

- Date : 2026-07-12.
- Scénario : Given des transitions `KnowledgeProjection` et des DTO documentaires servis par l'application FastAPI réelle; When PostgreSQL redémarre et que l'utilisateur charge, diagnostique ou inspecte un PDF; Then KA relit les états et `SourceLocator` bornés, l'UI applique les statuts SP exacts, refuse les diagnostics incohérents et présente une navigation HTML accessible sans fallback.
- ADR : ADR-018, ADR-021 et ADR-022 consultées et appliquées; aucune nouvelle ADR requise. La migration ascendante `004_knowledge_projection_chunk_samples.sql` suit ADR-021.
- Commit RED : `d5f682fdf`, `test(produit): couvrir contrats KA SP UI stricts`.
- Commit GREEN : `3521770cc`, `feat(produit): durcir contrats KA SP UI ADR-018 ADR-021 ADR-022`.
- Conformité du producteur KA : RED `f3bf36660`, GREEN `27bef8d48`; le repository PostgreSQL implémente désormais `save_if_absent`, contrôle d'empreinte, lectures par empreinte/identité et `save_transition`, tandis que `save_projection_outputs` persiste les échantillons bornés.
- Migration : schéma PostgreSQL `004`, table `knowledge_access.knowledge_projection_chunk_samples`, image `schema-004` et lecture `REPEATABLE READ READ ONLY` avec `sample_limit` SQL.
- Preuves live : PostgreSQL Docker réel redémarré avec `BUILDING`, `SEARCHABLE`, `STALE`, `FAILED`; Uvicorn/FastAPI réels avec upload multipart, diagnostic, conversion, projection et original par le client UI.
- UI : origine hôte `127.0.0.1` issue de la configuration, origine Compose `orchestrator-api`, succès POST en `303`, erreurs françaises `role=alert`, inspections sémantiques et retrait du bouton de sélection non raccordé.
- Modification utilisateur protégée : `tests/m013/validate_m013_reality_product_acceptance.ps1`, hors staging et hors commits.

## Correctif de revue gouvernance, OpenAPI, runtime et performance

- Exigences consolidées : `REQ-M013-FASTAPI-001`, `REQ-M013-FASTAPI-002`, `REQ-M013-FASTAPI-003`, `REQ-M013-FASTAPI-004`, `REQ-M013-FASTAPI-005`, `REQ-M013-FASTAPI-006`, `REQ-M013-FASTAPI-007`, `REQ-M013-FASTAPI-008`, `REQ-M013-FASTAPI-009`, `REQ-M013-FASTAPI-010`, `REQ-M013-FASTAPI-011`.
- Scénario BDD : Given les contrats M13-FastAPI, les preuves statiques et les preuves live; When la gate, OpenAPI, le runtime, PostgreSQL et le worker sont audités; Then toutes les tâches sont traçables, le lint reste indépendant de Docker, la gate live est explicite, les contrats sont typés et les volumes restent bornés sans donnée sensible.
- Gate : `-Mode Static` exécute les preuves sans Docker; `-Mode Live` exécute le catalogue exhaustif, y compris PostgreSQL, Uvicorn, PDF et workers réels. Une invocation sans mode échoue avec `M013_FASTAPI_LIVE_MODE_REQUIRED`.
- Runtime : `local_runtime serve-http orchestrator-api` est rejeté par `ORCHESTRATOR_LEGACY_RUNTIME_FORBIDDEN`; les routes conversation, benchmark, recherche et indexation reçoivent des services publics injectés par la composition.
- PostgreSQL : schéma `005`, pagination par `DocumentId`, snapshot `REPEATABLE READ READ ONLY`, lectures groupées à nombre constant de requêtes, insertions page par lots JSONB et index éditorial composite.
- Observabilité : corrélation HTTP vers outbox puis worker; compteurs succès/erreur, durée et volume sans payload, selon la configuration de tracing.
- Dérogation historique : les sujets de commits antérieurs sans accents ne sont pas réécrits afin de préserver la traçabilité des hashes. Tous les nouveaux sujets utilisent désormais l'accentuation française.
- Commit RED : `4a448c2c7`, `test(platform): couvrir gouvernance et performance M13-FastAPI`.
- Commit GREEN : `f9a7ff3c1`, `feat(platform): durcir API orchestratrice et gates M13-FastAPI`.
- Validations : gate statique `28/28` GREEN; gate live `32/32` GREEN; lint `38` validations GREEN; traçabilité `173` exigences GREEN; M13-reality GREEN sur PostgreSQL/migrations, `uv run api`, llm-gateway et Spark/vLLM réels; les `23` validations M-005 sont GREEN.
- Suite globale : tentative bornée de `scripts/test.ps1` à 10 minutes, expirée sans sortie ni verdict applicatif; résultat non concluant, jamais présenté comme GREEN.
- Préservation utilisateur : le hunk `wait_health` du fichier `tests/m013/validate_m013_reality_product_acceptance.ps1` est resté hors index et hors commits; seuls les hunks de migration vers FastAPI/PostgreSQL ont été commités.

## Correctif de revue - Opérations reproductibles et documentation courante

- Date : 2026-07-13.
- Scénario BDD : Given un clone propre, un commit Git complet et les migrations de ce commit; When l'exploitant matérialise l'environnement verrouillé puis construit la stack Compose; Then la gate utilise un seul interpréteur issu de `uv.lock`, l'image expose la révision et le schéma courants, le bind reste local et aucune recette hôte ou image mutable ne sert de rollback.
- ADR : ADR-021 consultée et appliquée; aucune nouvelle décision structurante n'est introduite.
- Commit RED : `f9aec200a`, `test(opérations): couvrir exécution reproductible M13-FastAPI`.
- Commit GREEN : `6e8b532d9`, `feat(opérations): verrouiller exécution M13-FastAPI ADR-021`.
- Gate : `uv sync --frozen --no-dev --no-install-project` matérialise les dépendances, puis `.venv\Scripts\python.exe` devient l'unique Python visible des preuves M13-FastAPI.
- Image : Python et uv sont épinglés par digest; le tag et les labels associent la dernière migration livrée au hash Git complet, sans registre externe ni tag `latest`.
- Exploitation : le chemin supporté est Compose; seul Caddy publie `127.0.0.1`; la commande hôte ambiguë et le rollback par tag réutilisable sont retirés.
- OpenAPI : `POST /v1/documents` est documenté en `201 application/json`; l'original est documenté en `200 application/pdf` uniquement.
- Preuves GREEN : acceptation des opérations reproductibles, acceptation du déploiement, `uv lock --check`, `docker compose config`, build multi-stage et inspection des labels image/schéma.
- Gate statique globale : son bootstrap verrouillé est prouvé; son verdict final est différé pendant les correctifs de revue concurrents dont les tests RED sont déjà présents dans le worktree partagé.
- Suite globale : aucune nouvelle conclusion n'est déclarée pour `scripts/test.ps1`; la tentative précédente reste non concluante après dix minutes.

## Correctif de revue - API, KA et UI paginées

- Date : 2026-07-13.
- Scénario BDD : Given plus de cent documents et des lectures synchrones PostgreSQL; When l'UI consulte le corpus ou une preuve documentaire; Then elle suit un curseur public borné, reçoit le statut KA par lot sans fan-out `1+N`, et l'event-loop déporte chaque cas d'usage synchrone vers le threadpool.
- ADR : ADR-018, ADR-019 et ADR-020 consultées et appliquées; aucune nouvelle décision structurante n'est introduite.
- Commit RED : `510d85ac6`, `test(api-ui): couvrir pagination et contrats stricts`.
- Commit GREEN : `c1aadb5f7`, `feat(api-ui): paginer et typer les contrats publics`.
- Extraction applicative : RED `e6cef6a3d`, GREEN `9c5dcda90`; conversation, évaluation, recherche et indexation sont composées hors du runtime HTTP historique.
- Contrats : manifeste, signaux page, route, profil, fraîcheur, chunks et `SourceLocator` sont des modèles OpenAPI imbriqués stricts; l'absence de projection et la projection complète forment une union explicite.
- UI : la limite agrégée est contrôlée avant lecture du corps par le proxy UI, les erreurs conservent leur statut HTTP, le champ public fautif est affiché et les preuves imbriquées restent inspectables en fenêtre étroite.
- Limite explicite : M13-FastAPI raccorde la frontière ASGI, mais ne livre pas le runtime de conversion M004. Le worker réel s'arrête après le diagnostic; aucun adaptateur Docling/OCRmyPDF réel, aucune publication PostgreSQL `CanonicalSourcePublished` et aucun consommateur KA durable ne sont présents. `/v1/documents/{document_id}/index` reste donc explicitement indisponible et l'UI ne simule aucune projection. Le `PostgresKnowledgeProjectionRepository` est validé comme producteur durable, sans inventer de `CanonicalSourceRef` depuis un diagnostic.
- Validation : gate M13-FastAPI Static `31/31` GREEN et lint ciblé GREEN. La preuve live documentaire complète reste réservée au runtime M004 qui produit effectivement `page_count`, `SourceLocator` et `canonical_artifact_sha256` après fusion, QA et stockage de l'artefact canonique.

## Correctif de revue - Frontière transactionnelle du relais outbox

- Date : 2026-07-13.
- Scénario BDD : Given un message SP réclamé avec une lease; When la plateforme committe le job puis que le relais tombe avant l'ACK SP; Then la lease expirée permet une redélivrance, le même `job_id` est retrouvé sans doublon et tout contenu divergent échoue explicitement.
- Décision : ADR-024 remplace ADR-022. Claim SP, consommation plateforme et ACK SP utilisent trois transactions locales; aucune transaction ni clé étrangère ne traverse les propriétaires définis par DDD-ADR-008.
- Migration : `007_job_outbox_context_boundary.sql` supprime la clé étrangère interschéma, ajoute la lease de relais et l'identité SHA-256 de consommation plateforme; l'upgrade 006 vers 007 et sa réexécution sont GREEN.
- Commit RED : `9afe600cf`, `test(worker): couvrir frontière transactionnelle outbox ADR-024`.
- Commit GREEN : `db9ad998b`, `feat(worker): séparer relais SP et plateforme ADR-024`.
- Garde globale : RED `618b77a46`, GREEN `669265460`; la migration supprime aussi la clé étrangère historique de `document_conversion_requests` vers `platform.technical_jobs`.
- Preuves : unité crash/redélivrance, deux relais PostgreSQL concurrents, crash après commit avant ACK, conflit divergent `JOB_RELAY_MESSAGE_CONFLICT`, absence de clé étrangère interschéma, diagnostics réels et `trace_id` préservé.
- Validations : gate M13-FastAPI Static `31/31` GREEN; frontière d'imports `215` fichiers et `1419` imports GREEN; tests live outbox, migration et worker GREEN.
- Hors périmètre : aucune modification du pipeline `CanonicalSourcePublished`, de Docling ou des diagnostics PDF réels.

## Correctif de revue - Preuve UI sur le serveur réel

- Date : 2026-07-13.
- Scénario BDD : Given PostgreSQL Docker, les migrations du commit, la factory FastAPI de production et le worker documentaire; When un navigateur charge un PDF par le vrai `ThreadingHTTPServer` de `local_runtime`; Then l'UI suit `POST-Redirect-GET`, restitue le corpus et l'original, affiche les diagnostics page par page, conserve les statuts HTTP d'erreur et bloque conversion/indexation sans fallback.
- ADR : ADR-018, ADR-019, ADR-020, ADR-021 et ADR-022 consultées et appliquées; aucune nouvelle décision structurante n'est introduite.
- Commit RED : `3d554eebd`, `test(ui): prouver le serveur réel via FastAPI et PostgreSQL`.
- Commit GREEN : `e663c95d5`, `fix(ui): exécuter le parcours réel sur serveur local`.
- Runtime : PostgreSQL, Uvicorn/FastAPI et l'UI utilisent trois ports libres; aucune injection de `ProductPorts`, aucun repository direct, aucun fake de projection et aucun fallback ne participent à la preuve.
- Parcours prouvé : upload multipart d'un PDF `pypdf`, redirection `303`, corpus responsive et accessible, commande de diagnostic, worker PostgreSQL réel, inspection des signaux et routes, récupération binaire identique de l'original.
- Blocages explicites : conversion absente en `409 CONVERSION_NOT_REQUESTED`; commande d'indexation hors parcours UI en `404 UI_DOCUMENT_COMMAND_FORBIDDEN`; champ obligatoire absent en `400 HTTP_REQUEST_INVALID`; document inconnu en `404`, toujours rendu en page HTML `role=alert` avec retour au corpus.
- Performance UI : une lecture de corpus produit un seul appel paginé `GET /v1/documents`; aucun appel `1+N` vers `/projection` n'est émis.
- Catalogue : la preuve dépendante de Docker quitte `-Mode Static` et rejoint exclusivement `-Mode Live`; la gate Static reste autonome.

## Correctif de revue 3 - Sûreté, concurrence et isolation PDF

- Date : 2026-07-13.
- Scénario BDD : Given des claims réattribuables, un worker susceptible de tomber entre deux écritures, une projection KA rejouée et un PDF non fiable; When la lease expire, qu'un ancien writer tente une transition, que les retries s'épuisent, que les sorties divergent ou que le parseur dépasse un budget; Then génération et token fenced refusent l'ancien détenteur, l'échec SP précède l'échec plateforme, le replay divergent est rejeté et le sous-processus PDF est arrêté sans fallback.
- Décision : ADR-025 complète ADR-024 par une génération monotone et un token UUID v4 sur chaque claim job/outbox; elle complète ADR-020 par une inspection `pypdf` exclusivement dans un sous-processus jetable à budgets explicites.
- Contrats : les DTO de jobs techniques deviennent neutres dans `app.contracts.technical_jobs`; les applications SP ne dépendent plus de la file PostgreSQL concrète et la composition plateforme injecte le port outbox.
- Données : la migration ascendante `008_claim_fencing_and_projection_replay.sql` ajoute le fencing, l'empreinte complète de replay KA et les index partiels des claims pending/expirés.
- Retry : les erreurs transitoires sont replanifiées jusqu'à trois exécutions; les erreurs d'intégrité sont terminales dès la première; toute terminalisation publie d'abord l'échec SP et reste réconciliable après crash.
- PDF : faux marqueur, document illisible, dépassement de taille/pages/texte/XObjects/mémoire/temps et timeout échouent explicitement; une page réellement blanche devient `EMPTY` et requiert une revue manuelle.
- Commits RED : `31ca4dc5c`, `test(runtime): couvrir fencing retries et PDF isolé ADR-025`; `c46b15e36`, `test(worker): couvrir épuisement retry récupérable ADR-025`.
- Commit GREEN : `3cd3c98f6`, `feat(runtime): clôturer sûreté concurrence review3 ADR-025`.
- Preuves GREEN ciblées : architecture `215` fichiers; sûreté unitaire; lint ciblé; compilation; PostgreSQL live `schema=008`, lease renouvelée, réattribution fenced, identités de réplicas distinctes, trois tentatives transitoires, erreur d'intégrité permanente, ancien ACK fenced et replay KA strict.
- Upgrade réel : volume au schéma 007 migré vers 008, ledger idempotent et verrou advisory GREEN.
- Hors staging : les adaptations mécaniques des tests historiques restent séparées; le hunk utilisateur `tests/m013/validate_m013_reality_product_acceptance.ps1` reste hors index et hors commits.

## Correctif de revue 3 - Déploiement Compose reproductible ADR-026

- Date : 2026-07-13.
- Scénario BDD : Given un clone propre et un commit Git complet; When la gate exporte ce commit, construit les images finales et démarre la stack Compose; Then PostgreSQL, Qdrant, le gateway LLM, l'API, deux workers, l'UI et Caddy exécutent les artefacts étiquetés par ce commit et le schéma 008, sans fichier non suivi ni fallback.
- Décisions : ADR-023 gouverne les versions optimistes; ADR-024 sépare claim SP, consommation plateforme et ACK SP; ADR-025 impose fencing, replay strict et inspection PDF isolée; ADR-026 complète ADR-021/ADR-025 avec l'archive Git, les images API/worker immuables, la readiness PostgreSQL + LLM, les deux replicas et la prévalidation du rollback.
- Commit RED : `c64311691`, `test(déploiement): couvrir stack Compose reproductible ADR-026`.
- Corrections du harness encore RED : `3df97b3b2`, `6b9a94c48`, `fd72ab75d`, `03d301088` et `d38a2142c`. Ces commits ne changent que la mécanique de la preuve live avant le GREEN fonctionnel.
- Commit GREEN : `f49ffded1`, `feat(déploiement): livrer stack Compose reproductible ADR-026`.
- Dépendances : Python `3.12.8`, setuptools `80.10.2`, Pydantic `2.13.4` et Starlette `1.3.1` sont directs, exacts et cohérents avec `uv.lock`.
- Configuration : l'identité PostgreSQL `ostrading` correspond à l'URL montée; les conteneurs utilisent le DNS `llm-gateway`; les clés d'observabilité sans consommateur ont été retirées du schéma strict.
- Preuve Compose réelle : archive du commit `cdbd5bbff6a9c443e0a6238d44abd9f20e4f2b28`, images API/worker inspectées, utilisateur non-root, entrypoints explicites, deux workers, readiness PostgreSQL + LLM, OpenAPI, multipart et migration 008 GREEN.
- Preuve T-005 réelle : après upload et diagnostic d'un PDF, PostgreSQL a été redémarré et l'API recréée dans un nouveau processus; le diagnostic `DIAGNOSED` et le SHA-256 de l'original ont été relus sans doublure. `validate_document_persistence_restart_acceptance.ps1` reste une preuve de contrat isolée; `validate_review3_deployment_live.ps1` porte désormais la preuve réelle.
- Upgrade réel : volume au schéma 007 migré vers 008, ledger idempotent et verrou advisory GREEN.
- Limite M004 : le diagnostic PDF est réel, mais aucune conversion canonique Docling/OCRmyPDF, publication `CanonicalSourcePublished` ou projection KA issue d'un `CanonicalSourceRef` complet n'est revendiquée.
- Validations GREEN : déploiement revue 3 statique et live, opérations reproductibles, déploiement orchestrateur, configuration M13-config, Compose local, migration PostgreSQL live, `uv lock --check` et système ADR.
- Écart historique explicite : certains lots antérieurs ont adapté ou ajouté des tests dans leur commit GREEN. Les hashes sont conservés et cet écart à la séparation RED/GREEN stricte est documenté sans réécriture. Pour ADR-026, le contrat a été commité RED, le harness a été stabilisé dans des commits exclusivement tests, puis l'implémentation a été commitée GREEN sans assouplir le contrat.
- Préservation utilisateur : le hunk `tests/m013/validate_m013_reality_product_acceptance.ps1` reste hors staging et hors commits.

## Correctif de revue 3 - Admission UI, sécurité et quota ADR-028

- Date : 2026-07-13.
- Scénario BDD : Given l’interface locale, un jeton Bearer conservé côté serveur et un quota corpus PostgreSQL; When plusieurs transferts documentaires concurrents traversent l’UI et l’API; Then les mutations sont authentifiées, les requêtes intersites sont refusées, les octets restent diffusés par blocs, l’admission est atomique et la saturation retourne une erreur publique explicite sans fallback.
- Décision : ADR-028 complète ADR-018 et ADR-020. Le navigateur reste client de l’UI locale, qui injecte le secret uniquement vers l’API; les lectures et la santé restent publiques, tandis que l’enregistrement et le diagnostic exigent le jeton local.
- Commit RED : `9a487beb7`, `test(api-ui): couvrir sécurité streaming et quota RED`.
- Commit GREEN : `6d6d58c89`, `feat(api-ui): sécuriser les transferts et le quota corpus`.
- Configuration et données : `security.secrets.local_api_token_path` désigne un secret d’au moins 32 octets hors Git; `paths.corpus_quota_bytes` fixe le quota obligatoire; la migration ascendante `009_corpus_quota.sql` ajoute le verrou d’admission singleton et les réservations idempotentes par empreinte.
- Frontière HTTP : les mutations documentaires répondent `401` ou `403` sans jeton valide; l’UI impose `Origin == Host`, borne quatre requêtes concurrentes, applique des timeouts socket et backend de 30 secondes et retourne `503` lorsqu’elle est saturée.
- Flux binaires : upload navigateur vers UI puis API, stockage temporaire et téléchargement API vers UI puis navigateur sont transmis par blocs de 64 Kio; le PDF métier reste borné à 50 Mio et un dépassement retourne une page `413` accessible.
- Read-model : le corpus est lu page par page par lots de 100, sans fan-out `1+N`; les raisons publiques de revue manuelle et les codes d’échec restent inspectables; le POST-Redirect-GET conserve `document_id` et `duplicate`.
- Quota réel : deux réservations PostgreSQL concurrentes de 600 octets sous un quota de 1 000 n’en acceptent qu’une; l’autre échoue avec `CORPUS_QUOTA_EXCEEDED`, et le rejeu de la même empreinte reste idempotent.
- Preuves GREEN : acceptation statique sécurité/streaming/quota; preuve live PostgreSQL du quota; parcours réel UI/FastAPI/PostgreSQL/worker; upgrade 007 vers 009; outbox et sûreté live; artefact Compose exporté depuis le commit GREEN, migrations 001 à 009, redémarrage PostgreSQL/API et relecture du diagnostic et du SHA-256 original.
- Nettoyage prouvé : les processus UI, API et gateway, les conteneurs PostgreSQL temporaires, les secrets temporaires, les répertoires de travail et les variables de test sont supprimés dans les blocs `finally`; aucun conteneur de preuve n’est resté actif.
- Limite M004 : la conversion canonique n’est pas livrée; l’UI affiche exactement `fonctionnalité non livrée`, sans retry, projection inventée ni statut de succès implicite.
- Préservation utilisateur : le hunk `tests/m013/validate_m013_reality_product_acceptance.ps1` reste hors staging et hors commits.
