# ADR-024 - Relais outbox par transactions locales

**Statut :** Acceptée
**Date :** 2026-07-13
**Décideurs :** Équipe OSTrading
**Remplace :** ADR-022
**Remplacée par :** Aucune
**Source :** Revue M13-FastAPI, frontière transactionnelle SP vers plateforme

## Contexte

ADR-022 séparait la soumission SP de la création du job plateforme, mais demandait encore au relais de créer `platform.technical_jobs` puis de marquer `source_processing.job_outbox` relayé dans une même transaction PostgreSQL. La clé étrangère de l'outbox SP vers le job plateforme renforçait ce couplage. Malgré deux schémas, le relais restait donc une transaction forte intercontextes, contraire à DDD-ADR-008.

Un crash après la création du job et avant l'acquittement SP doit être toléré par redélivrance. Cette redélivrance exige une consommation plateforme idempotente qui distingue strictement un doublon identique d'une réutilisation divergente du même identifiant.

## Décision

- La transaction productrice SP **DOIT** persister l'agrégat propriétaire et son message dans `source_processing.job_outbox`; elle **NE DOIT PAS** écrire dans le schéma `platform`.
- Un relais **DOIT** réclamer un message dans une transaction courte exclusivement SP avec `FOR UPDATE SKIP LOCKED`, un propriétaire et une échéance de lease, puis committer ce claim avant toute consommation.
- La plateforme **DOIT** consommer le message dans une deuxième transaction exclusivement `platform`, identifiée par `source_message_id` et une empreinte SHA-256 canonique du contenu complet.
- Une redélivrance identique **DOIT** retourner le même `job_id` sans créer de doublon. Le même `source_message_id`, ou la même identité technique de job, associé à un contenu divergent **DOIT** échouer avec `JOB_RELAY_MESSAGE_CONFLICT`.
- Après le commit plateforme, le relais **DOIT** acquitter le message dans une troisième transaction exclusivement SP. Si le processus tombe avant cet ACK, l'expiration de la lease **DOIT** rendre le message réclamable et la plateforme **DOIT** traiter la redélivrance de manière idempotente.
- Aucune transaction **NE DOIT** lire ou écrire simultanément `source_processing.job_outbox` et `platform.technical_jobs`. Aucune clé étrangère **NE DOIT** relier ces schémas pour ce protocole.
- Le `trace_id` **DOIT** être conservé dans le message puis le job sans être injecté dans le payload métier ni journalisé avec celui-ci.
- Les claims, renouvellements et transitions terminales des jobs, la version optimiste de `DocumentProcessingRun` et les snapshots `REPEATABLE READ READ ONLY` décidés par ADR-022 restent obligatoires. ADR-023 reste la décision active pour généraliser la version optimiste aux agrégats PostgreSQL.
- L'évolution **DOIT** être une migration ascendante ADR-021, compatible avec un volume au schéma 006 et réexécutable via le ledger sans modifier les migrations déjà appliquées.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Transaction unique interschémas et clé étrangère | Rejetée | Constitue une transaction forte intercontextes et empêche une autonomie réelle des propriétaires. |
| Transaction SP puis insertion plateforme sans identité de message | Rejetée | Un crash avant ACK peut créer un doublon ou masquer un contenu divergent. |
| Claim SP, consommation plateforme idempotente, ACK SP | Retenue | Applique DDD-ADR-008, tolère la redélivrance et rend les conflits explicites sans broker supplémentaire. |
| Broker externe | Rejetée | Ajoute une dépendance et une exploitation disproportionnées pour la topologie locale V1. |

## Conséquences

### Positives

- Chaque transaction forte reste sous un seul propriétaire de données.
- Le crash entre commit plateforme et ACK SP devient un cas nominal de redélivrance idempotente.
- Deux relais concurrents ne peuvent pas détenir simultanément le même message actif.
- La divergence de contenu n'est jamais assimilée silencieusement à un doublon.

### Négatives ou coûts

- L'outbox possède un état intermédiaire `relaying` et une lease distincte de celle du job.
- La plateforme conserve l'identifiant et l'empreinte du message source pour prouver l'idempotence.
- L'état SP peut rester temporairement non acquitté alors que le job plateforme existe déjà.

### Risques et contrôles

- Risque : lease de relais expirée pendant la transaction plateforme. Contrôle : transaction plateforme courte et ACK refusé explicitement si le propriétaire a perdu sa lease.
- Risque : collision entre soumission directe et message relayé. Contrôle : comparaison stricte de priorité, payload, trace et identité avant association du message.
- Risque : réintroduction d'un accès SP dans le consommateur plateforme. Contrôle : preuve statique interdisant `source_processing.job_outbox` dans `PostgresJobQueue` et validateur des frontières d'imports.

## Impact d'implémentation

- Modules concernés : `app/platform/job_runtime/relay.py`, `app/platform/job_runtime/postgres.py`, `app/source_processing/adapters/postgres_job_outbox.py`, composition de persistance SP et worker documentaire.
- Configuration concernée : la durée de lease explicite du worker est aussi utilisée pour son relais outbox; aucune valeur implicite ni fallback.
- Migration concernée : `007_job_outbox_context_boundary.sql`, upgrade 006 vers 007 idempotent, suppression de la clé étrangère interschéma et ajout des identités de consommation.
- Tests attendus : unité crash/redélivrance, concurrence PostgreSQL réelle, crash après commit avant ACK, conflit divergent, absence de clé étrangère, upgrade 006 vers 007, worker diagnostic et gate statique.
- Milestones concernées : M13-FastAPI.

## Liens de traçabilité

- Spécifications : `docs/specs/m013_fastapi_api_orchestratrice.md`; DDD-ADR-008; ADR-021; ADR-023.
- Plan d'implémentation : `docs/tasks/milestone_013-fastapi/0005_partager_etat_documentaire_durable.md` à `0007_lire_diagnostic_conversion.md`; correctif de revue itération 2.
- Tests d'acceptation : `tests/m013_fastapi/validate_job_outbox_boundary_acceptance.ps1`; `tests/m013_fastapi/validate_job_outbox_boundary_live.ps1`; `tests/m013_fastapi/validate_document_worker_live.ps1`; `tests/m013_fastapi/validate_postgres_migration_upgrade_live.ps1`.
- Commits : RED `9afe600cf`; GREEN `db9ad998b`; RED de garde globale `618b77a46`; GREEN `669265460`.

## Notes

ADR-024 remplace ADR-022 parce qu'elle corrige le protocole de relais tout en reprenant ses autres obligations de leases, corrélation, version optimiste et snapshot. Cette correction ne transforme pas le job technique en événement de domaine et ne modifie pas le pipeline `CanonicalSourcePublished`.
