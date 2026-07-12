# ADR-022 - Outbox SP et leases de jobs PostgreSQL

**Statut :** Acceptée
**Date :** 2026-07-12
**Décideurs :** Équipe OSTrading
**Remplace :** Aucun
**Remplacée par :** Aucune
**Source :** Findings de revue M13-FastAPI, T-005 à T-007

## Contexte

La commande de diagnostic SP persistait dans une même transaction une tentative appartenant à `source_processing` et un job appartenant à `platform`. Cette écriture inter-propriétaires contredit DDD-ADR-008. De plus, `worker-documents` ne consommait pas la file durable : il attendait indéfiniment sans claim, lease, reprise après crash ni résultat corrélé.

Les lectures d'une tentative étaient également composées par plusieurs requêtes sans snapshot explicite et les mises à jour remplaçaient silencieusement les lignes enfants, ce qui permettait à deux writers d'écraser leurs décisions.

## Décision

- La transaction SP **DOIT** écrire l'agrégat propriétaire et un message dans `source_processing.job_outbox`; elle **NE DOIT PAS** écrire directement `platform.technical_jobs`.
- Un relais PostgreSQL **DOIT** réclamer l'outbox avec `FOR UPDATE SKIP LOCKED`, créer le job `platform` de façon idempotente, puis marquer le message relayé dans la même transaction du relais.
- Un worker **DOIT** réclamer un job compatible par priorité et séquence avec `FOR UPDATE SKIP LOCKED`, enregistrer un propriétaire et une échéance de lease, puis effectuer exclusivement les transitions `pending -> running -> succeeded|failed`.
- Un job `running` dont la lease a expiré **DOIT** redevenir réclamable. Seul le propriétaire courant **DOIT** pouvoir renouveler ou terminer la lease.
- Le `trace_id` HTTP **DOIT** être conservé dans une colonne dédiée de l'outbox puis du job; il **NE DOIT PAS** être ajouté au payload métier ni provoquer la journalisation de ce payload.
- `DocumentProcessingRun` **DOIT** porter une version persistante. Toute sauvegarde d'une version déjà dépassée **DOIT** échouer avec `PROCESSING_RUN_VERSION_CONFLICT` et ne modifier aucune ligne enfant.
- Une lecture de l'agrégat SP, de son manifeste, de ses diagnostics et de ses routes **DOIT** utiliser une transaction `REPEATABLE READ READ ONLY` afin de publier un snapshot cohérent.
- Le schéma **DOIT** évoluer par une migration ascendante exécutée par le runner ADR-021; l'upgrade et sa réexécution **DOIVENT** être idempotents.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Transaction SP écrivant aussi `platform.technical_jobs` | Rejetée | Viole la propriété des contextes définie par DDD-ADR-008. |
| Broker externe | Rejetée | Dépendance et exploitation disproportionnées pour la topologie locale V1. |
| Outbox SP, relais PostgreSQL idempotent et leases | Retenue | Respecte les frontières, l'ordre, la concurrence et la reprise avec l'infrastructure déjà requise. |

## Conséquences

### Positives

- La soumission SP reste atomique sans transaction intercontextes.
- Plusieurs workers peuvent coopérer sans double exécution active.
- Un crash ne laisse pas définitivement un job en cours.
- Les conflits d'agrégat et les lectures incohérentes deviennent explicites et testables.

### Négatives ou coûts

- La visibilité d'un job `platform` est éventuellement cohérente après la transaction SP.
- La durée de lease et la fréquence de polling doivent rester explicitement configurées par le runtime.

### Risques et contrôles

- Risque : exécution répétée après expiration pendant un traitement encore actif. Contrôle : renouvellement de lease et persistance idempotente/versionnée des sorties SP.
- Risque : outbox bloquée. Contrôle : claims expirables, compteur de tentatives et preuve live de reprise.
- Risque : payload sensible dans les logs. Contrôle : corrélation uniquement par `trace_id`, `job_id`, `document_id` et statuts.

## Impact d'implémentation

- Modules concernés : `app/source_processing/adapters/postgres_document_persistence.py`, `app/platform/job_runtime/postgres.py`, `app/platform/local_runtime.py` et worker de diagnostic SP.
- Configuration concernée : concurrence des workers, budgets de démarrage et d'arrêt existants.
- Tests attendus : API vers PostgreSQL puis second processus worker; deux workers concurrents; crash et reprise après lease; conflit optimiste; snapshot avec interleaving; upgrade idempotent.
- Milestones concernées : M13-FastAPI, correctifs de revue T-005 à T-007.

## Liens de traçabilité

- Spécification : `docs/specs/m013_fastapi_api_orchestratrice.md`; DDD-ADR-008.
- Plan d'implémentation : `docs/tasks/milestone_013-fastapi/0005_partager_etat_documentaire_durable.md` à `0007_lire_diagnostic_conversion.md`.
- Tests d'acceptation : `tests/m013_fastapi/validate_document_worker_runtime_acceptance.ps1`; `tests/m013_fastapi/validate_document_worker_live.ps1`.
- Commits : RED `d9f73943f`; GREEN `d1daf1f34`.

## Notes

Cette ADR applique DDD-ADR-008 sans la remplacer : la transaction forte reste locale à SP, puis la synchronisation vers `platform` est éventuellement cohérente et idempotente.

Mise en conformité du 2026-07-13 : `worker-documents` renouvelle désormais la lease pendant tout le diagnostic, sérialise le renouvellement avec la transition terminale, classe les erreurs transitoires et permanentes, borne l'inspection pypdf par taille, pages, temps, texte et objets, puis publie l'échec terminal dans l'état SP. Les preuves sont `validate_worker_data_resilience_acceptance.ps1` et `validate_document_worker_live.ps1`; commits RED `7b7912f09` et GREEN `9d17bc129`. Cette note réalise les obligations existantes sans changer la décision.
