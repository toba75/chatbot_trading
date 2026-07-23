# ADR-052 - Distribution locale à la page et quota Granite fenced

**Statut :** Proposée
**Date :** 2026-07-23
**Décideurs :** Équipe OSTrading
**Remplace :** Pour M-014 uniquement, les mentions d’une flotte CPU multiarchitecture ou distante d’ADR-051
**Remplacée par :** Aucune
**Source :** M14-distribution-core T-002 ; `docs/specs/plan_distribution.md`

## Contexte

M-014 doit distribuer les pages d’un même traitement entre exactement deux
replicas locaux `worker-documents`, sans déplacer l’autorité documentaire hors
de Source Processing. Les deux replicas sont généralistes : une capacité
Granite contrainte ne constitue ni une route supplémentaire, ni une file
spécialisée, ni une identité de worker dédiée.

Les sémaphores de processus décidés par ADR-040 et ADR-042 protègent un worker,
mais ne prouvent pas un plafond partagé entre deux processus. ADR-025 impose le
fencing des claims de jobs par génération et token, tandis qu’ADR-024 interdit
une transaction forte qui écrirait simultanément les données de Source
Processing et celles de `platform`. Le quota doit donc être durable, observable
et possédé par `platform`, puis transporter sa preuve sans transférer la
propriété du résultat de page.

ADR-051 reste l’autorité de l’exécution Granite sur `cuda:0`, de l’erreur
`GRANITE_CUDA_UNAVAILABLE` et de l’interdiction du fallback CPU. Ses mentions
historiques d’une future flotte CPU multiarchitecture ou distante sont devenues
obsolètes pour M-014 : ce milestone reste entièrement sur la station locale.
Cette ADR remplace uniquement ces mentions de contexte et ne modifie pas
ADR-051.

## Scénario BDD

- **Given** deux workers documentaires généralistes du même environnement ont
  chacun acquis un slot Granite lié à leur claim fenced.
- **When** un troisième job Granite tente d’acquérir la capacité, puis qu’un des
  deux couples claim-slot expire après la perte de son worker.
- **Then** le troisième job reste en attente dans la file PostgreSQL sans
  lancer le modèle ni changer de route, peut acquérir le slot libéré avec une
  nouvelle génération et un nouveau token, et l’ancien détenteur ne peut plus
  renouveler, libérer ou publier sous sa lease expirée.

## Décision

### Frontières de propriété et fan-out

- Source Processing **DOIT** rester propriétaire de
  `DocumentProcessingRun`, du manifeste, des routes M-003, des résultats de
  pages, de la progression et de la publication canonique.
- L’orchestration `CONVERT_DOCUMENT` **DOIT** produire idempotemment un job
  `CONVERT_PAGE` par page non vide au moyen de son outbox. Sa clé d’idempotence
  **DOIT** inclure le traitement, la page, la route et la version de politique.
- `platform` **DOIT** rester propriétaire de `platform.technical_jobs`, des
  claims ADR-025, de la capacité d’exécution et de la nouvelle table
  `platform.granite_slots`.
- Une transaction forte **NE DOIT PAS** lire ou écrire à la fois un agrégat
  Source Processing et une table `platform`. Les échanges entre propriétaires
  **DOIVENT** passer par des enveloppes idempotentes et des relais à
  transactions locales selon ADR-024.

### Mécanisme PostgreSQL retenu

- `platform.granite_slots` **DOIT** contenir exactement deux lignes pour chaque
  couple explicite `(environment, deployment_id)`. Leur identité
  `slot_ordinal` **DOIT** satisfaire `slot_ordinal IN (1, 2)` et la clé primaire
  **DOIT** interdire tout troisième slot.
- Chaque ligne **DOIT** porter au minimum `environment`, `deployment_id`,
  `slot_ordinal`, `lease_owner`, `job_id`, `claim_generation`, `claim_token`,
  `slot_generation`, `slot_token` et `lease_until`. Aucun de ces champs actifs
  **NE DOIT** recevoir une valeur par défaut implicite.
- `slot_generation` **DOIT** croître monotonement pour la ligne et `slot_token`
  **DOIT** être un UUID v4 neuf à chaque attribution. Ils complètent, sans les
  remplacer, `claim_generation` et `claim_token` d’ADR-025.
- Une contrainte unique sur le détenteur actif **DOIT** garantir au plus un slot
  par `worker_instance_id` dans le couple `(environment, deployment_id)`. Un
  worker dont l’ancien slot est expiré **DOIT** recycler cette ligne sous une
  nouvelle génération avant de pouvoir en obtenir une autre.
- PostgreSQL **DOIT** constituer l’unique autorité du quota. Un compteur, un
  sémaphore en mémoire, un verrou de fichier ou l’état Docker **NE DOIT PAS**
  autoriser une conversion Granite.

### Acquisition atomique et attente

- Le port `ClaimCompatibleTechnicalJob` de `platform` **DOIT** sélectionner le
  job compatible et, pour une capacité Granite, une ligne de slot libre ou
  expirée avec `FOR UPDATE SKIP LOCKED`, puis attribuer le claim et le slot dans
  la même transaction PostgreSQL.
- L’acquisition **DOIT** vérifier dans cette transaction l’identité complète
  `environment`, `deployment_id`, `configuration_hash`, l’identité de stockage,
  l’état `READY` non drainant et les capacités publiées du worker.
- La lease du claim et celle du slot **DOIVENT** recevoir la même échéance
  explicite. Le slot **DOIT** enregistrer le `job_id`, la génération et le token
  du claim qui l’autorise.
- Si les deux slots sont actifs, le troisième job Granite **DOIT** rester dans
  l’état non terminal existant `pending`, sans claim attribué. L’attente
  **N’EST** ni un succès, ni une erreur terminale, ni une tentative
  d’exécution ; elle **NE DOIT PAS** lancer le modèle, modifier la route M-003,
  créer une autre file ou sélectionner le CPU.
- Après libération ou expiration, un job Granite en attente **PEUT** acquérir la
  ligne admissible. Cette attribution **DOIT** créer une nouvelle génération et
  un nouveau token de claim ainsi qu’une nouvelle génération et un nouveau
  token de slot.

### Heartbeat, expiration, libération et drainage

- Le port `HeartbeatClaimAndGraniteSlot` **DOIT** renouveler le claim et le slot
  dans une transaction `platform` unique. La requête **DOIT** comparer le
  worker, le job, les deux générations, les deux tokens, l’état actif et une
  `lease_until` strictement future avant toute écriture.
- L’expiration **DOIT** être évaluée avec l’horloge PostgreSQL. Un claim et son
  slot expirés redeviennent réclamables atomiquement ; aucun processus de
  nettoyage en mémoire n’est l’autorité de cette reprise.
- Le port `ReleaseGraniteSlot` **DOIT** comparer le même tuple fenced complet et
  une lease encore active. Succès, échec terminal et abandon explicite
  **DOIVENT** libérer le slot dans une transaction `platform`; une libération
  provenant d’un détenteur expiré **DOIT** échouer sans mutation.
- Le drainage d’un worker **DOIT** interdire tout nouveau claim. Le worker
  **DOIT** continuer les heartbeats de son couple claim-slot courant jusqu’à sa
  terminaison ou jusqu’à l’échéance de drainage explicitement configurée ;
  après cette échéance, il **NE DOIT PAS** forcer une libération non fenced et
  la reprise **DOIT** attendre l’expiration PostgreSQL.

### Fencing de la publication et idempotence

- Un worker **NE DOIT PAS** écrire directement un résultat de page dans Source
  Processing. Le port `CompletePageExecution` **DOIT**, dans une transaction
  exclusivement `platform`, vérifier le claim et le slot actifs avec leurs
  générations et tokens, enregistrer une enveloppe de complétion immuable et
  libérer le slot.
- Un relais **DOIT** livrer cette enveloppe à Source Processing. Dans une
  transaction exclusivement Source Processing, le résultat de page et l’unique
  incrément de progression **DOIVENT** être persistés atomiquement, puis
  l’enveloppe **DOIT** être acquittée par une transaction `platform` séparée.
- La redélivrance d’une enveloppe identique **DOIT** être idempotente. Une même
  identité avec un contenu, un artefact, un hash, une route, une génération ou
  un token divergent **DOIT** être refusée explicitement.
- L’enveloppe de complétion **DOIT** être créée avant l’expiration. Un ancien
  détenteur qui présente un claim expiré, un ancien token de claim ou un ancien
  token de slot **NE DOIT** ni renouveler, ni libérer, ni créer une enveloppe,
  ni publier un résultat.

### Topologie locale et absence de fallback

- Les deux replicas `worker-documents` **DOIVENT** exécuter le même code et
  publier les mêmes capacités généralistes. Aucun worker spécialisé Granite,
  aucune route spécialisée et aucune file supplémentaire **NE DOIVENT** être
  créés.
- Le mécanisme **DOIT** utiliser uniquement le PostgreSQL de l’environnement et
  les artefacts locaux de cet environnement. Redis, Taskiq, Celery, un broker,
  SSH, Kamal, Colima, `arm64`, un worker distant et un stockage d’objets réseau
  **SONT INTERDITS** dans M-014.
- Granite **DOIT** rester sur `cuda:0` selon ADR-051. La saturation ou
  l’indisponibilité **NE DOIT** déclencher ni CPU, ni sélection `auto`, ni
  détection matérielle implicite, ni changement de route.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Deux sémaphores en mémoire, un par worker | Rejetée | Ne prouvent pas un plafond global et perdent leur état au crash. |
| Compteur PostgreSQL unique sans identité de slot | Rejetée | Ne relie pas une unité de capacité à un claim et ne permet pas une reprise fenced par ligne. |
| Verrou advisory conservé pendant la conversion | Rejetée | Lie la capacité à une session, masque le propriétaire métier et rend heartbeat, expiration et inspection moins explicites. |
| Deux lignes `platform.granite_slots`, leases et double fencing | Retenue | Rend le plafond, le détenteur, l’expiration et la reprise atomiques, durables et inspectables avec l’autorité PostgreSQL existante. |
| Redis, Taskiq, Celery ou autre broker de capacité | Rejetée | Introduit une seconde autorité et une exploitation hors du besoin local. |

## Conséquences

### Positives

- Deux conversions Granite au maximum peuvent être autorisées dans un
  environnement, avec un slot au maximum par worker.
- Le crash d’un worker ne laisse pas un slot permanent et l’ancien détenteur
  est refusé après réattribution.
- Le fan-out à la page préserve les propriétaires DDD et la publication
  canonique reste sous l’autorité de Source Processing.
- Le quota, ses détenteurs et l’attente sont inspectables depuis l’état
  PostgreSQL persistant.

### Négatives ou coûts

- Le claim d’un job Granite verrouille et met à jour une ligne de capacité dans
  la même transaction.
- Une complétion de page traverse une enveloppe durable et un acquittement
  supplémentaire afin de respecter les frontières transactionnelles.
- Les lignes expirées doivent être recyclées par une acquisition fenced ; leur
  simple présence ne signifie pas qu’une conversion est active.

### Risques et contrôles

- Risque : troisième processus Granite malgré le quota. Contrôle : seulement
  deux ordinaux admissibles, sélection verrouillée et absence de claim Granite
  sans slot.
- Risque : ancien détenteur encore actif après expiration. Contrôle : double
  génération, double token et échéance future comparés à chaque mutation.
- Risque : un worker détient deux slots. Contrôle : contrainte unique de
  détenteur et recyclage transactionnel de sa ligne expirée.
- Risque : progression comptée deux fois. Contrôle : enveloppe immuable,
  consommation idempotente et transaction Source Processing unique.
- Risque : saturation traitée comme panne. Contrôle : le job reste `pending` et
  l’attente est une métrique administrative persistante, pas un état terminal
  inventé.
- Risque : mélange d’environnements. Contrôle : identité complète vérifiée dans
  le prédicat de claim et la clé des slots.

## Migration et rollback

- T-004 **DOIT** livrer une migration ADR-021 uniquement ascendante qui crée et
  initialise les deux lignes de slot sans modifier une migration déjà
  appliquée. La migration **NE DOIT PAS** activer le fan-out.
- L’activation **DOIT** être une configuration versionnée et explicite pour les
  nouveaux traitements. Aucune détection de matériel ou de schéma **NE DOIT**
  choisir automatiquement le parcours distribué.
- Un rollback **DOIT** arrêter explicitement la création de nouveaux jobs de
  pages, drainer les workers, laisser terminer ou expirer les claims et slots
  actifs, conserver les résultats et reprendre seulement les nouveaux
  documents avec le parcours antérieur explicitement configuré.
- Le rollback **NE DOIT PAS** supprimer les tables ou colonnes, réécrire un
  résultat, changer une route, basculer Granite sur CPU ou transférer un job
  vers un autre environnement.

## Impact d'implémentation

- Modules concernés : `app.contracts.technical_jobs`,
  `app.platform.job_runtime`, relais de complétion et ports Source Processing de
  résultat de page.
- Configuration concernée : identité d’environnement et de déploiement,
  durée de lease et échéance de drainage obligatoires ; aucune valeur par
  défaut.
- Migration concernée : nouvelle migration ascendante T-004 pour
  `platform.granite_slots` et l’enveloppe de complétion.
- Tests attendus : T-004 prouve PostgreSQL réel, deux acquisitions, attente de
  la troisième, heartbeat, expiration, reprise et refus de l’ancien détenteur.
- Milestones concernées : M14-distribution-core et M14-local-pipeline.

## Liens de traçabilité

- Spécification : `docs/specs/plan_distribution.md`, scénarios DIST-001,
  DIST-002 et DIST-003.
- Plan d’implémentation :
  `docs/specs/plan_implementation_milestones_workstreams.md`, section
  `M14-distribution-core`.
- Tâches :
  `docs/tasks/milestone_014-distribution-core/0002_decider_distribution_locale_quota_granite.md`
  et T-004
  `0004_migrer_quota_granite_fenced.md`.
- Tests d’acceptation :
  `gate_tests/ported/tests/m014_distribution_core/validate_distribution_decision_acceptance.py`
  et `validate_distribution_decision_unit.py` ; tests PostgreSQL réels de T-004.
- ADR liées : ADR-021, ADR-024, ADR-025, ADR-040, ADR-042, ADR-046 et ADR-051.
- Commits : RED et GREEN de T-002 à reporter dans le journal du milestone.

## Notes

Le quota décidé ici est global dans l’autorité PostgreSQL d’un environnement
et d’un déploiement. L’étanchéité interdit de partager une ligne ou un détenteur
entre `development`, `test` et `production`. La qualification fonctionnelle
s’exécute dans `test` ; les autres profils sont contrôlés structurellement.

Cette ADR reste proposée jusqu’aux preuves PostgreSQL de T-004 et aux preuves
live de M14-local-qualification. Une preuve qui invalide le mécanisme exigera
une ADR remplaçante ; ADR-052 ne sera pas réécrite silencieusement.
