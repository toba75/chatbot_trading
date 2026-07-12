# Rapport d'audit M13-FastAPI

## Périmètre

- Tâche: T-011, déployer et auditer l'API orchestratrice.
- Date de consolidation: 2026-07-13.
- Décisions: ADR-018, ADR-019, ADR-020, ADR-021 et ADR-022.
- Configuration: M13-config, fichier unique et `configuration_hash` obligatoire.

## État courant

L'état courant ne fige pas un numéro devenu faux dès qu'une migration ascendante est ajoutée. Le schéma courant dérivé des migrations est le préfixe numérique maximal de `deploy/postgres/migrations/*.sql`; la gate live vérifie ce même ensemble via le ledger `platform.schema_migrations`.

L'image locale identifiée par le commit Git complet utilise le tag `ostrading/orchestrator-api:0.1.0-m013-fastapi-schema-<schéma>-<commit-complet>`. Compose transmet les deux valeurs comme arguments de build et l'image les expose dans `org.ostrading.postgres-schema-version` et `org.opencontainers.image.revision`. Une branche, `latest`, un hash abrégé ou un tag historique ne constitue pas une preuve de rollback.

La commande réelle de l'image est `api --config /workspace/config/application.yaml`. Le seul chemin d'exploitation supporté est `docker compose -f .\deploy\local-compose\compose.yaml up --build`; le DNS `postgres` est interne à Compose et aucun lancement hôte n'est documenté comme équivalent.

## Scénario audité

- Given un commit Git complet, les migrations de ce commit et la configuration M13-config.
- When Compose construit l'image verrouillée puis PostgreSQL, Uvicorn et les workers exécutent le parcours PDF.
- Then un seul `orchestrator-api` sert les contrats, le schéma est migré avant readiness et chaque appel reste traçable sans fallback.

## Contrôles courants

| Contrôle | Preuve actuelle | Verdict |
|---|---|---|
| Interpréteur de gate | `uv sync --frozen --no-dev --no-install-project`, puis PATH imposé sur `.venv\Scripts` | Couvert par la gate statique |
| Image builder | Python et uv épinglés par digest; `uv.lock` appliqué avec `--frozen` | Couvert par test de déploiement |
| Identité image/schéma | commit Git complet et dernière migration transmis au tag et aux labels | Couvert par test d'opérations |
| Runtime public unique | commande `api`; ancien `local_runtime` refusé pour orchestrator-api | Couvert par gates statique et live |
| PostgreSQL réel | ledger SHA-256, verrou advisory et readiness dynamique | Couvert par gate live |
| Bind réseau | seul Caddy publie `127.0.0.1`; aucun port FastAPI hôte | Couvert par Compose |
| OpenAPI | création en `201 application/json`; original en `200 application/pdf` uniquement | Couvert sémantiquement |
| Corps HTTP et original | limites Caddy/ASGI, hash avant 200, streaming borné | Couvert par tests et preuve live |
| Pagination corpus | curseur public obligatoire, page de 1 à 100, statut KA lu en lot | Couvert par gate statique |
| Modèles publics | structures imbriquées strictes et union d'absence/projection | Couvert par OpenAPI et tests UI |
| Traçabilité | `X-Trace-ID`, `trace_id`, `configuration_hash`, statut et durée sans payload | Couvert par preuve live |
| Aucun fallback | dépendance ou migration absente arrête le démarrage | Couvert par tests statiques |

## Commandes d'audit actuelles

```powershell
uv lock --check
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_fastapi\validate_reproducible_operations_acceptance.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013_fastapi\validate_orchestrator_deployment_acceptance.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_fastapi.ps1 -Mode Static
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_fastapi.ps1 -Mode Live
```

La preuve live utilise Docker Engine, PostgreSQL, Uvicorn, PDF et workers réels. Un test unitaire isolé ne la remplace pas.

## Limites actuelles

- L'UI reste cliente HTTP de `orchestrator-api`; elle n'est pas migrée vers FastAPI.
- Le runtime M004 de conversion canonique n'est pas livré par ce sous-milestone : aucun adaptateur Docling/OCRmyPDF réel ni publication durable `CanonicalSourcePublished` ne permet encore à `/index` de recevoir un `CanonicalSourceRef` complet. L'indexation et la sélection conversationnelle restent bloquées explicitement; aucune projection n'est fabriquée depuis l'état `DIAGNOSED`.
- Une publication future ne pourra émettre `CanonicalSourcePublished` qu'après fusion Docling, adjudication d'autorité textuelle, QA, stockage de l'artefact et calcul de `canonical_artifact_sha256`; le relais KA devra appliquer DDD-ADR-008 par inbox idempotente sans transaction forte intercontextes.
- `llm-gateway` reste le seul adaptateur réseau vers Spark.
- Qdrant n'est pas une source de vérité de projection.
- Les migrations restent ascendantes; aucun rollback de schéma destructif n'est automatisé.
- `scripts/test.ps1` a dépassé la borne d'observation de dix minutes lors de la revue. Cette exécution est non concluante et n'est jamais présentée comme GREEN.

## Preuves historiques

Les éléments ci-dessous sont conservés pour la traçabilité des décisions; ils ne décrivent pas la commande, l'image ou le schéma courants.

- T-011 initial: RED `b2a00b28a`, GREEN `c07453414`; première preuve HTTP Docker/PostgreSQL/Uvicorn.
- Frontière HTTP ADR-020: RED `ae943a04c` et `d4b64cf26`, GREEN `89acbdd70`; PDF supérieur à 1 Mio, limites agrégées et streaming vérifié.
- Runtime ADR-021: RED `3c4159a86`, GREEN `439b4336f`; introduction du ledger, du verrou et de la readiness dynamique sur le schéma alors courant.
- Worker ADR-022: RED `d9f73943f`, GREEN `d1daf1f34`; outbox, claims, leases et reprise après crash.
- Contrats produit KA/SP/UI: RED `d5f682fdf` et `f3bf36660`, GREEN `3521770cc` et `27bef8d48`.
- Gouvernance/performance: RED `4a448c2c7`, GREEN `f9a7ff3c1`; gate exhaustive Static/Live, OpenAPI typé et lectures bornées.
- API/KA/UI paginées : RED `510d85ac6`, GREEN `c1aadb5f7`; extraction applicative RED `e6cef6a3d`, GREEN `9c5dcda90`; gate Static `31/31` GREEN.
- La tentative historique de `scripts/test.ps1` est restée non concluante après dix minutes, sans verdict applicatif.
