# Rapport d'audit M13-FastAPI

## Périmètre

- Tâche: T-011, déployer et auditer l'API orchestratrice.
- Date: 2026-07-12.
- Décisions: ADR-019, FastAPI et Uvicorn uniquement pour `orchestrator-api`; ADR-021, migrations versionnées sous ledger et verrou avant readiness.
- Configuration: M13-config, fichier unique et `configuration_hash` obligatoire.

## Scénario audité

- Given l'application ASGI et les contrats documentaires sont GREEN.
- When PostgreSQL réel démarre dans Docker, Uvicorn démarre puis reçoit un PDF réel par HTTP multipart.
- Then les routes de santé, readiness, OpenAPI, enregistrement, diagnostic, corpus, original et projection publique répondent par un seul runtime traçable.

## Contrôles

| Contrôle | Preuve attendue | Verdict |
|---|---|---|
| Runtime public unique | Compose exécute `uv run --no-sync api`; aucune commande `local_runtime` pour `orchestrator-api` | Couvert par la gate |
| PostgreSQL réel | Conteneur PostgreSQL épinglé, upgrade d'un volume pré-M13, ledger SHA-256 et readiness dynamique du schéma 003 | Couvert par la gate live |
| Budgets M13-config | connexion/startup 120 s, requête/healthcheck 300 s, arrêt Uvicorn/Compose 30 s | Couvert par tests runtime et Compose |
| Erreurs infrastructure | JSON public `error_code`, `X-Trace-ID` et log JSON sans secret, y compris exception, timeout et trace invalide | Couvert par test runtime |
| PDF réel | PDF valide produit avec `pypdf`, transmis multipart, hash identique à la restitution | Couvert par la gate live |
| Traçabilité | `X-Trace-ID`, log `trace_id`, `configuration_hash`, statut et durée sans payload | Couvert par la gate live |
| OpenAPI borné | `/openapi.json` sans référence de stockage, job, secret ni identifiant Qdrant | Couvert par la gate live |
| Configuration obligatoire | `--config` requis; secret et dépendance manquants arrêtent le démarrage | Couvert par tests et runtime |
| Aucun fallback | aucune route de secours, aucun backend alternatif, aucune réactivation de l'ancien serveur | Couvert par tests statiques |
| Corps HTTP agrégé | Caddy et ASGI refusent au-delà de 54 Mo, même sans `Content-Length` | Couvert par tests routeur et déploiement |
| Spool multipart | Racine en lecture seule et `tmpfs /tmp` limité à 128 Mio pour les deux spools bornés | Couvert par Compose et preuve live > 1 Mio |
| Original PDF | SHA-256 vérifié avant 200, chunks de 64 Kio maximum et fermeture garantie | Couvert par tests unitaires et concurrence bornée |
| Dépendances | `pypdf==6.14.2`, `python-multipart==0.0.32`, verrou cohérent | Couvert par gate et `uv lock --check` |
| Image runtime | Résolution dans le builder, aucune installation de `uv` dans le runtime | Couvert par gate de déploiement et build Compose |

## Commandes d'audit

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_fastapi\validate_orchestrator_deployment_acceptance.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_fastapi\validate_document_http_live_acceptance.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_fastapi\validate_orchestrator_deployment_unit.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_fastapi\validate_m013_fastapi_traceability_unit.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_fastapi.ps1 -Mode Live
```

La preuve live utilise Docker Engine, PostgreSQL, Uvicorn et HTTP réels. Aucun mock, stub, fake, serveur de test ASGI ni fallback n'est admis dans cette preuve. Les tests unitaires isolés ne remplacent pas cette preuve live.

## Limites et rollback

- L'UI reste cliente HTTP de `orchestrator-api`; elle n'est pas migrée vers FastAPI.
- `llm-gateway` reste le seul adaptateur réseau vers Spark et n'est pas migré.
- Qdrant ne devient pas une source de vérité de projection; l'état public KA est lu depuis PostgreSQL.
- Le rollback suit `docs/runbooks/api_orchestratrice.md` et ne réactive jamais deux runtimes concurrents.
- La page corpus publique est actuellement bornée à 100 documents par lecture; l'exposition d'un curseur UI complet reste une évolution produit distincte. Le port PostgreSQL accepte un curseur `after_document_id` explicite et n'effectue aucune lecture non bornée.
- Les métriques M13-FastAPI sont émises dans les événements JSON locaux configurés; aucun exporteur externe ni stockage longue durée n'est introduit.
- Les handlers conversation et benchmark réutilisent encore les fonctions publiques de calcul du module runtime pendant la migration progressive; les routeurs ne dépendent plus de noms privés. L'extraction complète du moteur LLM hors du module runtime reste un risque de maintenabilité suivi, sans fallback fonctionnel.
- La migration `005` ajoute des index en ligne lors du démarrage; sur un corpus beaucoup plus volumineux que le profil local V1, la durée de verrou doit être mesurée avant production multi-utilisateur.

## Résultats observés

- Correctif de revue final : gate statique `28/28` GREEN et gate live `32/32` GREEN, avec contrôle d'exhaustivité du catalogue.
- OpenAPI : multipart PDF, DTO publics, `application/pdf`, statuts `201`, `202`, `4xx` et `5xx` validés sémantiquement.
- M13-reality : GREEN avec PostgreSQL Docker et migrations réelles, `uv run --no-sync api`, llm-gateway et Spark/vLLM réels.
- Compatibilité : les 23 validations M-005, la parité API, l'architecture, la traçabilité à 173 exigences et le lint à 38 validations sont GREEN.
- Gate globale : tentative bornée à 10 minutes, expirée sans sortie ni verdict applicatif; résultat non concluant.
- Commits : RED `4a448c2c7`; GREEN `f9a7ff3c1`; commit documentaire de clôture séparé afin de conserver les hashes de preuve.

- Docker Engine: serveur `29.1.5` disponible.
- Image Compose: `ostrading/orchestrator-api:0.0.0-m002` construite avec `uv sync --frozen --no-dev`; manifeste local `sha256:51de59597a927e0cb59030a630ae3af81fd2a599ef0835697f1791fdb076ae84`.
- Preuve HTTP: document `DOC-BC6CFA26B1753E74`, PDF SHA-256 `bc6cfa26b1753e740c2749f8a854828770965f5862134ec304cb11a25e98d02a`, PostgreSQL Docker et transport `uvicorn-http`.
- Gate M13-FastAPI initiale: quatre preuves GREEN, dont la preuve live sans double.
- Gate lint: GREEN, 38 validations.
- Gate de traçabilité: GREEN, 163 exigences.
- Gate globale `scripts/test.ps1`: tentative bornée à 10 minutes, expirée sans sortie ni code de sortie applicatif; résultat non concluant et jamais présenté comme GREEN.

## Correctif de revue runtime et opérations

- Décision applicable : ADR-021.
- Commits : RED `3c4159a86`, `test(runtime): couvrir migrations et budgets ADR-021`; GREEN `439b4336f`, `feat(runtime): fiabiliser demarrage et migrations ADR-021`.
- Scénarios : upgrade d'un volume pré-M13 vers le schéma 003; revalidation dynamique après démarrage; timeouts configurés; rollback des ressources partielles; réponses infrastructure traçables; timeout de lecture UI traduit sans fallback.
- Version livrée : image `ostrading/orchestrator-api:0.1.0-m013-fastapi-schema-003`, migrations `001`, `002` et `003`, ledger `platform.schema_migrations`.
- Le contrat historique `GET /` n'existe pas dans les tests publics de `master`; aucune rupture d'alias n'est introduite ni documentée comme API publique.
- Rollback : uniquement vers une image explicitement compatible avec le ledger 003, sans suppression de volume ni migration descendante implicite.

## Correctif de revue sécurité HTTP

- Décision applicable : ADR-020, complément d'ADR-019 pour les corps binaires bornés.
- Preuves RED : commit `ae943a04c` pour la frontière HTTP, le streaming et le déploiement; commit `d4b64cf26` pour les invariants du value object bibliographique.
- Audit de dépendances : `pip-audit` n'est pas disponible dans l'environnement local; aucune installation opportuniste ni fallback de scanner n'a été exécuté. Les versions exactes et `uv.lock` sont vérifiés par la gate.
- La preuve live génère un PDF `pypdf` supérieur à 1 Mio, l'enregistre par HTTP multipart réel puis compare le SHA-256 de la restitution streamée.
- La gate M13-FastAPI durcie exécute six preuves, dont les limites du routeur et le streaming original avant la preuve live.
- Commit GREEN : `89acbdd70`, `feat(api): borner frontiere http et streaming original ADR-020`.
- Image multi-stage reconstruite : manifeste local `sha256:cc413e65961544241f11682021b886e76e0f2b5b5ec8967f9c806958b14cc450`; runtime non privilégié sans exécutable `uv`.
- Preuve live finale : `DOC-ACCDE60BF0517081`, SHA-256 `accde60bf05170810a4e22bb71f72c1b944d7135aa6672eb8bf1aaedbcdb5692`.
