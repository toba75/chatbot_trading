# ADR-025 - Fencing des claims et inspection PDF isolée

**Statut :** Acceptée
**Date :** 2026-07-13
**Décideurs :** Équipe OSTrading
**Remplace :** Aucun
**Remplacée par :** Aucune
**Source :** Revue de sûreté et de concurrence M13-FastAPI

## Contexte

ADR-024 sépare correctement le claim outbox SP, la consommation plateforme et l'ACK SP en transactions locales. Une identité de propriétaire seule ne suffit toutefois pas à interdire l'écriture d'un ancien détenteur après expiration puis réattribution de sa lease : deux processus redémarrés avec le même nom logique peuvent présenter le même propriétaire. Le même risque existe pour le claim d'un job et pour l'ACK de son message outbox.

Le worker doit aussi distinguer un échec transitoire d'un échec permanent, borner exactement ses retries et publier l'échec SP avant la terminalisation du job plateforme. Un crash entre ces deux écritures doit rester réconciliable sans masquer l'état public.

Enfin, l'ouverture d'un PDF hostile dans le processus long de l'API ou du worker expose ces runtimes à un blocage ou à une consommation non bornée de ressources. La simple présence du marqueur `%PDF` ne prouve pas la lisibilité du document. Le replay d'une projection KA à version identique présente un risque comparable de divergence silencieuse si seule une partie des sorties est comparée.

## Décision

- Chaque claim de job plateforme **DOIT** persister et restituer le triplet `lease_owner`, `claim_generation`, `claim_token`. `claim_generation` **DOIT** être monotone par job et `claim_token` **DOIT** être un UUID v4 nouveau à chaque attribution.
- Tout renouvellement, succès, échec ou replanification **DOIT** comparer le propriétaire, la génération, le token, le statut `running` et une lease encore active. Un ancien détenteur **DOIT** recevoir `JOB_LEASE_LOST`, même s'il réutilise le même nom logique.
- Chaque instance de worker **DOIT** compléter son identifiant logique par une identité d'instance unique. Cette identité ne remplace pas le fencing persistant.
- Les claims outbox SP **DOIVENT** appliquer la même génération monotone et un token UUID v4. L'ACK **DOIT** comparer propriétaire, génération, token et lease active.
- Un échec transitoire **DOIT** être replanifié tant que `execution_attempts < 3`. À la troisième tentative, il **DOIT** devenir terminal. Une violation d'intégrité PostgreSQL ou une autre erreur permanente **NE DOIT PAS** être retryée.
- Pour un échec terminal, le worker **DOIT** persister idempotemment l'échec public SP avant de marquer le job plateforme `failed`. Si le processus tombe entre les deux écritures, l'expiration puis la reprise de lease **DOIVENT** réconcilier la terminalisation sans réexécuter une publication divergente.
- Les DTO du protocole de jobs **DOIVENT** être neutres et publiés dans `app.contracts.technical_jobs`. Les applications métier **NE DOIVENT PAS** dépendre d'un repository PostgreSQL ou d'une file concrète. La composition plateforme **DOIT** recevoir le port outbox producteur par injection.
- L'inspection `pypdf` d'un contenu non fiable **DOIT** s'exécuter dans un sous-processus jetable. Le parent **DOIT** appliquer un délai dur, terminer le processus à expiration et imposer explicitement les budgets de taille, pages, texte, objets XObject, mémoire et temps processeur disponibles sur la plateforme.
- L'enregistrement et le diagnostic **DOIVENT** utiliser la même politique d'inspection isolée. Un faux marqueur PDF, un PDF illisible ou un budget dépassé **DOIT** produire `SOURCE_UNREADABLE`; aucun fallback ni analyse dans le processus parent n'est autorisé.
- Une page réelle sans signal textuel ni image **DOIT** produire l'état explicite `EMPTY` et rester soumise à revue manuelle; elle **NE DOIT PAS** être assimilée à un parseur défaillant ou à un signal absent.
- Un replay KA à la même version **DOIT** comparer une empreinte canonique de toutes les sorties persistées : statut, profil, nombre de chunks, échantillons, textes, `SourceLocator` et temps observé. Une identité exacte est idempotente; toute divergence **DOIT** échouer avec `KA_PROJECTION_REPLAY_DIVERGENCE`.
- Une projection `SEARCHABLE` **DOIT** posséder un nombre de chunks strictement positif et au moins un échantillon avant toute écriture.
- La migration ascendante ADR-021 **DOIT** ajouter les colonnes de fencing, l'empreinte de replay KA et les index partiels des chemins chauds de claim pending/expiré. Elle **NE DOIT PAS** modifier une migration déjà appliquée.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Propriétaire logique seul | Rejetée | Ne distingue pas deux incarnations successives du même worker et autorise un ancien writer. |
| Génération seule | Rejetée | Fournit un ordre, mais un token aléatoire rend aussi chaque attribution non devinable et explicitement transportable. |
| Génération monotone et token UUID par claim | Retenue | Fencing durable, vérifiable à chaque écriture et applicable symétriquement aux jobs et à l'outbox. |
| Analyse PDF dans le processus API/worker | Rejetée | Un timeout de coroutine ne reprend pas un parseur bloqué et n'isole pas la mémoire. |
| Sous-processus jetable avec budgets durs | Retenue | Permet la terminaison forcée et limite l'impact d'un contenu hostile sans fallback. |
| Replay KA accepté sur la seule version | Rejetée | Masque une divergence de sorties sous une identité déjà publiée. |

## Conséquences

### Positives

- Un writer ou un ACK obsolète ne peut plus muter l'état après réattribution.
- Les retries ont une borne déterministe et les échecs publics SP précèdent toujours la terminalisation plateforme.
- Un PDF hostile ne s'exécute plus dans les processus longs de l'API ou du worker.
- Les pages réellement vides et les entrées illisibles ont deux sémantiques distinctes.
- Un replay KA divergent est détecté avant d'altérer la projection.
- Les requêtes de claim utilisent des index partiels alignés sur leurs prédicats chauds.

### Négatives ou coûts

- Chaque mutation de job ou d'outbox transporte deux champs de fencing supplémentaires.
- L'inspection PDF démarre un processus par document et sérialise un rapport borné vers le parent.
- Les limites mémoire et processeur du sous-processus dépendent des primitives offertes par le système; le délai dur parent reste obligatoire sur toutes les plateformes.
- L'empreinte KA duplique une représentation canonique des sorties pour prouver l'idempotence stricte.

### Risques et contrôles

- Risque : fin de lease entre le dernier heartbeat et la transition. Contrôle : la transition compare aussi l'échéance dans la même requête SQL.
- Risque : crash après publication SP et avant `platform.failed`. Contrôle : publication SP idempotente, lease expirée puis reprise fenced et terminalisation répétable.
- Risque : sous-processus PDF non coopératif. Contrôle : délai parent, `terminate`, puis `kill` si nécessaire; aucune poursuite dans le parent.
- Risque : limite documentaire trop restrictive. Contrôle : budgets versionnés dans une factory M13 unique et erreurs explicites, sans relâchement silencieux.
- Risque : scan SQL sur une file croissante. Contrôle : index partiels `pending` et leases expirées prouvés sur PostgreSQL réel.

## Impact d'implémentation

- Modules concernés : `app/contracts/technical_jobs.py`, `app/platform/job_runtime/`, `app/source_processing/adapters/worker_runtime.py`, `app/source_processing/adapters/postgres_job_outbox.py`, `app/source_processing/adapters/pdf_inspection_process.py`, `app/source_processing/adapters/pdf_inspection_worker.py`, `app/knowledge_access/adapters/postgres_projection_read.py`.
- Configuration concernée : aucune valeur implicite; les budgets M13 sont construits par une factory unique et la durée de lease reste fournie explicitement au runtime.
- Migration concernée : `008_claim_fencing_and_projection_replay.sql`, upgrade 007 vers 008 idempotent via le ledger ADR-021.
- Tests attendus : sûreté unitaire, PostgreSQL live, expiration/réattribution, ancien writer/ACK, retries transitoires et permanents, replay KA, PDF hostile et page vide.
- Milestones concernées : M13-FastAPI.

## Liens de traçabilité

- Spécifications : `docs/specs/m013_fastapi_api_orchestratrice.md`; ADR-020; ADR-021; ADR-024; DDD-ADR-008.
- Plan d'implémentation : `docs/tasks/milestone_013-fastapi/0005_partager_etat_documentaire_durable.md` à `0009_lire_projection_connaissance.md`; correctif de revue 3.
- Tests d'acceptation : `tests/m013_fastapi/validate_review3_safety_acceptance.ps1`; `tests/m013_fastapi/validate_review3_safety_live.ps1`; `tests/m013_fastapi/validate_worker_data_resilience_acceptance.ps1`; `tests/m013_fastapi/validate_postgres_migration_upgrade_live.ps1`.
- Commits : RED `31ca4dc5c`; RED `c46b15e36`; GREEN `3cd3c98f6`.

## Notes

ADR-025 complète ADR-024 sans la remplacer : ADR-024 gouverne la séparation des transactions et propriétaires; ADR-025 ajoute l'identité fenced de chaque attribution et les règles de terminalisation. Elle complète aussi ADR-020 pour le traitement interne d'un PDF déjà borné à la frontière HTTP.
