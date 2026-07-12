# ADR-021 - Migrations PostgreSQL versionnées avant readiness

**Statut :** Acceptée
**Date :** 2026-07-12
**Décideurs :** Équipe OSTrading
**Remplace :** Aucun
**Remplacée par :** Aucune
**Source :** Findings de revue M13-FastAPI, T-011

## Contexte

Le montage des scripts SQL dans `/docker-entrypoint-initdb.d` ne les exécute que lors de l'initialisation d'un volume PostgreSQL vide. Un volume créé avant M13-FastAPI peut donc démarrer sans les read-models requis alors que `pg_isready` et `SELECT 1` réussissent. L'API annoncerait alors une readiness trompeuse.

Le démarrage doit aussi rester borné par la configuration M13-config, sérialisé entre plusieurs instances et réversible sans masquer une migration incomplète.

## Décision

- `orchestrator-api` **DOIT** exécuter, avant sa readiness, les migrations SQL versionnées livrées dans son image.
- Le runner **DOIT** prendre un verrou advisory transactionnel PostgreSQL, créer et maintenir un ledger contenant version, nom et SHA-256, puis appliquer les versions manquantes dans l'ordre strict.
- Une migration déjà inscrite **DOIT** avoir le même nom et le même SHA-256; toute divergence **DOIT** arrêter le démarrage explicitement.
- L'application d'une version et son inscription au ledger **DOIVENT** appartenir à la même transaction. Une erreur **NE DOIT PAS** publier une version partielle.
- La readiness **DOIT** rouvrir une connexion et vérifier dynamiquement que la version requise par l'image est inscrite avec son empreinte attendue.
- Le timeout de connexion PostgreSQL, le budget de démarrage, le timeout de requête et le délai d'arrêt Uvicorn **DOIVENT** provenir de la configuration applicative validée.
- Un rollback applicatif **NE DOIT PAS** supprimer le volume ni exécuter implicitement une migration descendante. Il **DOIT** redéployer une image qui déclare explicitement la même version de schéma, ou livrer une migration corrective ascendante.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Scripts `docker-entrypoint-initdb.d` seuls | Rejetée | Ils ignorent les volumes existants. |
| Migration automatique sans ledger ni verrou | Rejetée | Les exécutions concurrentes et les dérives de scripts ne sont pas détectées. |
| Runner transactionnel, ledger SHA-256 et verrou advisory | Retenue | Il rend l'upgrade idempotent, observable et sûr pour un volume existant. |
| Migrations descendantes automatiques au rollback | Rejetée | Elles peuvent détruire des données et couplent silencieusement image et volume. |

## Conséquences

### Positives

- Un volume pré-M13 converge vers la version requise avant toute readiness positive.
- La dérive d'un fichier SQL déjà appliqué est détectée.
- Plusieurs instances peuvent démarrer sans appliquer deux fois une migration.

### Négatives ou coûts

- Le démarrage dépend du répertoire de migrations embarqué dans l'image.
- Une migration longue consomme le budget de démarrage et doit être conçue explicitement pour ce budget.

### Risques et contrôles

- Risque : verrou bloqué. Contrôle : transaction et timeouts PostgreSQL bornés.
- Risque : rollback vers une image incompatible. Contrôle : tag d'image et version de schéma explicites dans Compose et le runbook.
- Risque : faux positif de readiness après panne PostgreSQL. Contrôle : revalidation dynamique par connexion et ledger.

## Impact d'implémentation

- Modules concernés : `app/platform/postgres_migrations.py`, runtime et composition orchestratrice.
- Configuration concernée : `runtime.timeouts.startup_seconds`, `request_seconds`, `shutdown_seconds`.
- Tests attendus : upgrade live d'un volume pré-M13, idempotence, verrou/ledger, readiness dynamique, propagation des timeouts.
- Milestones concernées : M13-FastAPI, correctifs de revue T-011.

## Liens de traçabilité

- Spécification : `docs/specs/m013_fastapi_api_orchestratrice.md`.
- Plan d'implémentation : `docs/tasks/milestone_013-fastapi/0011_deployer_auditer_api_orchestratrice.md`.
- Tests d'acceptation : `tests/m013_fastapi/validate_runtime_operations_acceptance.ps1`; `tests/m013_fastapi/validate_postgres_migration_upgrade_live.ps1`.
- Commits : RED `3c4159a86`; GREEN `439b4336f`.

## Notes

La stratégie est strictement ascendante. Toute évolution destructive nécessite une décision distincte et une procédure d'exploitation dédiée.
