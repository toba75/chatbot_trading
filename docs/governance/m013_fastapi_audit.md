# Rapport d'audit M13-FastAPI

## Périmètre

- Tâche : T-011, déployer et auditer l'API orchestratrice.
- Date de consolidation : 2026-07-13.
- Décisions courantes : ADR-018, ADR-019, ADR-020, ADR-021, ADR-023, ADR-024, ADR-025, ADR-026, ADR-027 et ADR-028.
- Configuration : fichier M13-config unique, `configuration_hash` obligatoire et variante conteneur versionnée `deploy/local-compose/application.compose.yaml`.

## État courant

Le schéma courant est le préfixe numérique maximal de `deploy/postgres/migrations/*.sql`. La gate live vérifie le même ensemble via le ledger `platform.schema_migrations`; elle prouve actuellement la migration 009, l'upgrade depuis un volume arrêté à 007 et la réexécution idempotente.

Les images API et worker utilisent respectivement `ostrading/orchestrator-api:0.1.0-m013-fastapi-schema-<schéma>-<commit-complet>` et `ostrading/worker-documents:0.1.0-m013-fastapi-schema-<schéma>-<commit-complet>`. Elles exposent `org.ostrading.postgres-schema-version` et `org.opencontainers.image.revision`, s'exécutent sous `ostrading` et possèdent un entrypoint explicite. Une branche, `latest`, un hash abrégé ou le tag worker historique ne constitue pas une preuve de rollback.

La stack d'exploitation est construite depuis une archive Git, jamais depuis le worktree. L'API exécute `api --config /workspace/config/application.yaml`; les deux replicas worker exécutent le module documentaire dédié avec le fencing d'ADR-025. Seul Caddy publie `127.0.0.1`.

## Scénario audité

- Given un clone propre, un commit Git complet, ses migrations, le secret PostgreSQL et le token API local hors Git.
- When la gate exporte le commit, construit les images finales et démarre la stack Compose.
- Then PostgreSQL, Qdrant, `llm-gateway`, Uvicorn, deux workers, UI et Caddy réalisent le parcours PDF, puis la donnée survit au redémarrage réel de PostgreSQL et de l'API.

## Contrôles courants

| Contrôle | Preuve actuelle | Verdict |
|---|---|---|
| Interpréteur, projet et dépendances | Python `3.12.8`, paquet `chatbot-trading` en version `0.1.0`, setuptools, Pydantic et Starlette directs et exacts, `uv lock --check` | Couvert, y compris depuis un clone sans `*.egg-info` local |
| Contexte de build | Archive Git complète et `.dockerignore` racine borné | Couvert par ADR-026 et test statique |
| Identité PostgreSQL | rôle/base `ostrading`, URL conteneur et secret cohérents | Couvert par Compose réel |
| Identité images | commit complet et schéma 009 dans tags et labels API/worker | Inspectée avant démarrage |
| Runtime public unique | entrypoint `api`; ancien `local_runtime` refusé | Couvert |
| Readiness | ledger PostgreSQL requis et `/health` de `llm-gateway` | Couvert par preuve Compose |
| Workers | deux replicas, identités distinctes et claims fenced | Couvert par ADR-025/ADR-026 |
| Persistance T-005 | PDF traité, PostgreSQL redémarré, API recréée, diagnostic et SHA-256 relus | Couvert par preuve Compose réelle |
| OpenAPI et binaire | multipart, `201`, PDF `200`, bornes Caddy/ASGI et hash avant streaming | Couvert |
| Mutations locales | token backend hors Git, 401/403 directs, Origin/Host strict et absence du secret dans OpenAPI, HTML et logs | Couvert par ADR-028 et preuves UI/Compose |
| Admission corpus | PDF 50 Mio, métadonnées bornées, streaming 64 Kio, quatre transferts simultanés et quota PostgreSQL agrégé | Couvert par migration 009 et course concurrente |
| Bind réseau | seul Caddy publie `127.0.0.1` | Couvert |
| Traçabilité | `X-Trace-ID`, `trace_id`, `configuration_hash`, statut et durée sans payload | Couvert |
| Aucun fallback | dépendance, migration, image ou configuration invalide arrête l'opération | Couvert |

## Commandes d'audit actuelles

```powershell
uv lock --check
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_fastapi\validate_review3_deployment_acceptance.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_fastapi\validate_review3_deployment_live.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_fastapi\validate_postgres_migration_upgrade_live.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_fastapi\validate_review3_ui_security_acceptance.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_fastapi\validate_review3_ui_security_live.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_fastapi\validate_ui_orchestrator_document_flow_acceptance.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_fastapi.ps1 -Mode Static
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_fastapi.ps1 -Mode Live
```

La preuve live exporte le commit, construit la stack finale et emploie Docker Engine, PostgreSQL, Uvicorn, Caddy, le gateway LLM, PDF et workers réels. Un test unitaire isolé ne la remplace pas.

## Limites actuelles

- L'UI reste cliente HTTP de `orchestrator-api`; elle n'est pas réécrite en FastAPI.
- Le runtime M004 de conversion canonique n'est pas livré par ce sous-milestone. Aucun adaptateur Docling/OCRmyPDF réel ni publication durable `CanonicalSourcePublished` ne permet encore à `/index` de recevoir un `CanonicalSourceRef` complet. L'indexation et la sélection conversationnelle restent bloquées explicitement ; aucune projection n'est fabriquée depuis `DIAGNOSED`.
- L'UI affiche `fonctionnalité non livrée` sans retry pour conversion et projection absentes. Ce message est un blocage produit explicite, pas une preuve M004.
- Une publication future devra attendre fusion Docling, adjudication d'autorité textuelle, QA, stockage et calcul de `canonical_artifact_sha256`, puis respecter DDD-ADR-008 par inbox idempotente. Cette description est une contrainte future, pas une preuve M004 livrée.
- `llm-gateway` reste le seul adaptateur réseau vers Spark. Qdrant n'est pas une source de vérité.
- Les migrations restent ascendantes ; aucun rollback de schéma destructif n'est automatisé.
- `scripts/test.ps1` a dépassé dix minutes lors d'une revue antérieure. Cette exécution reste non concluante et n'est jamais présentée comme GREEN.

## Preuves historiques

Ces éléments conservent l'historique sans décrire l'image, le schéma ou la commande courants :

- T-011 initial : RED `b2a00b28a`, GREEN `c07453414`; première preuve HTTP Docker/PostgreSQL/Uvicorn.
- Frontière HTTP ADR-020 : RED `ae943a04c` et `d4b64cf26`, GREEN `89acbdd70`.
- Runtime ADR-021 : RED `3c4159a86`, GREEN `439b4336f`; ledger, verrou et readiness PostgreSQL.
- Worker ADR-022 : RED `d9f73943f`, GREEN `d1daf1f34`; cette architecture a ensuite été remplacée pour le relais par ADR-024.
- Version optimiste ADR-023 : RED `7b7912f09`, GREEN `9d17bc129`, documentation `7a2946c70`.
- Frontière transactionnelle ADR-024 : RED `9afe600cf` puis garde `618b77a46`, GREEN `db9ad998b` puis `669265460`, documentation `59ef15b6f` et `44118989d`.
- Fencing et isolation PDF ADR-025 : RED `31ca4dc5c` et `c46b15e36`, GREEN `3cd3c98f6`, compatibilité `f7e6d1c89`, documentation `9ac974b8c`.
- Déploiement Compose ADR-026 : RED `c64311691` ; corrections du seul harness live `3df97b3b2`, `6b9a94c48`, `fd72ab75d`, `03d301088` et `d38a2142c` ; GREEN fonctionnel `f49ffded1`.
- Contrats produit KA/SP/UI : RED `d5f682fdf` et `f3bf36660`, GREEN `3521770cc` et `27bef8d48`.
- Gouvernance/performance : RED `4a448c2c7`, GREEN `f9a7ff3c1` ; API/KA/UI paginées : RED `510d85ac6`, GREEN `c1aadb5f7`.
- Admission UI, sécurité et quota : RED `9a487beb7`, GREEN `6d6d58c89`; migration 009, auth 401/403, CSRF, streaming, saturation 4+1, quota concurrent et Compose exporté depuis HEAD GREEN.

## Écarts historiques BDD/TDD explicités

Le workflow normatif reste : état GREEN initial, test RED commit distinct, implémentation GREEN commit distinct. Des lots antérieurs ont toutefois ajouté ou adapté des tests dans leur commit GREEN, notamment lors des consolidations produit et gouvernance. Les hashes ne sont pas réécrits : cet écart historique est documenté comme non-conformité de séparation des phases, sans prétendre qu'il respectait le TDD strict.

Pour ADR-026, le contrat d'acceptation a été commité RED avant l'implémentation. Les cinq commits suivants ont corrigé uniquement le harness live encore RED avant le GREEN fonctionnel ; aucun contrat n'a été assoupli dans `f49ffded1`. Le hunk utilisateur de `tests/m013/validate_m013_reality_product_acceptance.ps1` est resté hors staging et hors commits.
