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
- Implémentation: limite Caddy/ASGI de 54 Mo, PDF métier 50 Mio, métadonnées courtes, `tmpfs /tmp` 128 Mio pour le double spool borné, streaming par chunks 64 Kio, threadpool FastAPI et image builder/runtime.
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
- Validations: gate M13-FastAPI 8 preuves GREEN, lint 38 validations GREEN, système ADR GREEN, Compose statique et `docker compose config` GREEN, preuves live PostgreSQL et PDF/Uvicorn GREEN.
- Modification utilisateur protégée: `tests/m013/validate_m013_reality_product_acceptance.ps1`, hors staging et hors commits.
