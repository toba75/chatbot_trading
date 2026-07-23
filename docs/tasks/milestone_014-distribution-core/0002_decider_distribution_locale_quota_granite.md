# T-002 - Décider la distribution locale et le quota Granite

## Milestone

- Nom : M14-distribution-core - Socle de distribution locale durable.
- Source : `docs/specs/plan_distribution.md`, T-002 ; ADR-024, ADR-025,
  ADR-040, ADR-042, ADR-046 et ADR-051.
- Objectif métier : décider avant implémentation comment deux workers locaux
  peuvent traiter des pages indépendantes tout en partageant exactement deux
  slots Granite fenced.

## Contexte DDD

- Domaine : exécution distribuée locale des traitements documentaires.
- Bounded contexts : Source Processing possède le traitement et les résultats
  de pages ; `platform` possède la file technique et la capacité d'exécution.
- Objectif métier : préserver une autorité documentaire unique malgré une
  exécution au moins une fois sur deux replicas.
- Langage ubiquitaire : orchestration parent, job de page, résultat de page,
  slot Granite, lease de slot, heartbeat, expiration, drainage, génération de
  claim, token de fencing, worker généraliste.
- Invariants critiques : PostgreSQL reste l'unique autorité des jobs, claims,
  leases et slots ; deux slots globaux au maximum ; un slot au maximum par
  worker ; aucune spécialisation de file ; aucune exécution Granite sans slot
  actif ; aucun fallback CPU.
- Garde-fous : ADR-051 demeure l'autorité de l'exécution `cuda:0` stricte ;
  ADR-052 remplace explicitement, pour le périmètre M-014, toute mention devenue
  obsolète d'une flotte CPU multiarchitecture ou distante sans réécrire
  ADR-051 ; aucune transaction forte ne mélange les propriétaires SP et
  `platform`.

## Blocages Ou Préconditions

- État GREEN/RED connu : T-001 est GREEN et son baseline est publié.
- Présence des milestones amont dans master : M-000 à M-013 sont présents ;
  M14-local-pipeline n'est pas requis et reste interdit avant la gate de ce
  sous-milestone.
- Décisions manquantes : ADR-052 doit choisir le mécanisme PostgreSQL exact du
  quota, la propriété de ses données, le cycle de vie des slots, les bornes de
  reprise et la relation avec les claims ADR-025.
- Risques : sémaphore seulement en mémoire, troisième conversion réellement
  démarrée, slot orphelin après crash, ancien détenteur autorisé à libérer ou
  renouveler, spécialisation implicite d'un replica, ou réintroduction du réseau
  distant.

## Tâches

### T-002 - Décider la distribution locale et le quota Granite

- But métier : rendre testable la topologie locale et la capacité Granite avant
  toute migration ou modification du runtime.
- Portée DDD : frontières SP/`platform`, unité de distribution à la page,
  modèle de lease du slot, règles de compatibilité d'un claim et stratégie de
  reprise fenced.
- Scénario BDD :
  - Given deux workers documentaires généralistes du même environnement ont
    chacun acquis un slot Granite lié à leur claim fenced.
  - When un troisième job Granite tente d'acquérir la capacité, puis qu'un des
    deux slots expire après perte de son worker.
  - Then le troisième job reste en attente sans lancer le modèle ni changer de
    route, peut acquérir le slot expiré avec une nouvelle génération et un
    nouveau token, et l'ancien détenteur ne peut plus renouveler, libérer ou
    publier sous cette lease.
- Tests d'acceptation à écrire : ajouter un test RED qui exige ADR-052,
  `docs/adr/index.md` et une décision couvrant fan-out à la page, propriété des
  données, acquisition atomique, heartbeat, expiration, drainage, fencing,
  idempotence, deux slots globaux, un par worker, identité d'environnement,
  attente du troisième job, absence de fallback et exclusions réseau.
- Tests unitaires à écrire : couvrir le validateur ADR avec quota non borné,
  compteur en mémoire comme autorité, token ou génération absent, libération
  non fenced, route spécialisée, file supplémentaire, hôte distant, modification
  silencieuse d'ADR-051 et option retenue sans conséquences ni rollback.
- Implémentation attendue : créer ADR-052 depuis `docs/adr/TEMPLATE.md`, choisir
  et justifier le mécanisme PostgreSQL parmi les options étudiées, préciser les
  transactions locales et ports concernés, indexer l'ADR, relier la décision au
  plan, aux scénarios DIST-001 à DIST-003 et aux tests T-004, puis compléter le
  journal du milestone.
- Invariants et garde-fous : décision sans valeur automatique ; aucun Redis,
  Taskiq, Celery, broker, verrou local seul ou détection matérielle implicite ;
  aucun changement de route M-003 ; l'état d'attente n'est pas un succès ni une
  erreur terminale inventée.
- Dépendances : T-001 ; `docs/adr/TEMPLATE.md` ; ADR-021, ADR-024, ADR-025,
  ADR-040, ADR-042, ADR-046 et ADR-051.
- Commandes de validation : tests ciblés ADR-052 ;
  `uv run --locked gate --scope governance` ;
  `uv run --locked gate --scope m014_distribution_core` ;
  `uv run --locked gate`.
- Commit RED : `test(m014-core): exiger décision distribution locale ADR-052`.
- Commit GREEN : `docs(adr): décider quota Granite local ADR-052`.
