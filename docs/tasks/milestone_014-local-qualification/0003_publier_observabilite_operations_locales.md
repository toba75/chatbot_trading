# T-009 - Publier l'observabilité et les opérations locales

## Milestone

- Nom : M14-local-qualification - Qualification de capacité locale.
- Source : `docs/specs/plan_distribution.md`, T-009 ; ADR-025 et ADR-052.
- Objectif métier : permettre à l'opérateur de connaître l'état réel des deux
  workers et de drainer puis redémarrer une cible sans interrompre l'autre ni
  perdre le fencing de ses travaux.

## Contexte DDD

- Domaine : exploitation de la capacité documentaire locale.
- Bounded context : `platform` possède le read-model d'administration, les
  intentions opératoires, le registre des workers, les jobs et les slots ; SP
  reste l'autorité des résultats et métriques de pages ; KA reste l'autorité de
  la projection.
- Objectif métier : rendre la capacité inspectable et opérable sans transformer
  Docker, les logs ou l'UI métier en source de vérité.
- Langage ubiquitaire : replica attendu, instance enregistrée, présence active,
  `READY`, `BUSY`, `DRAINING`, absence constatée, job prêt/réclamé/repris/échoué,
  slot actif/en attente, intention de drainage, échéance, redémarrage ciblé,
  preuve d'opération.
- Invariants critiques : exactement deux replicas attendus ; une instance
  `BUSY` possède un claim actif et, pour Granite, son slot correspondant ; le
  drainage ferme les admissions avant toute action runtime ; une instance
  redémarrée reçoit une nouvelle identité et ne réutilise aucun token expiré.
- Garde-fous : aucune commande sans environnement, déploiement, hash de
  configuration et cible exacts ; aucune libération forcée d'un slot ; aucun
  redémarrage de service entier lorsque seule une instance est ciblée ; aucune
  donnée de progression métier calculée depuis le read-model technique.

## Blocages Ou Préconditions

- État GREEN/RED connu : P-002 GREEN et scope
  `m014_local_qualification` créé ; les scopes M14-core et M14-pipeline restent
  GREEN sur le même candidat de départ.
- Présence des milestones amont dans master : le registre
  `platform.document_workers`, `platform.technical_jobs`,
  `platform.granite_slots`, les métriques de `PageResult` et le cycle
  `RegisteredDocumentWorkerLifecycle` sont disponibles.
- Décisions manquantes : aucune si la surface reste le point d'entrée opérateur
  local décidé en P-002. Une UI ou une API d'administration exposée au réseau
  exige une ADR et une chaîne réelle complète avant d'être rendue disponible.
- Risques : état périmé présenté comme `READY`, confusion entre job en attente
  et échec, résolution ambiguë d'une instance Compose, opération non auditée,
  ou collecte GPU absente transformée en zéro.

## Tâches

### T-009 - Publier l'observabilité et les opérations locales

- But métier : observer les deux replicas, leurs travaux et leur capacité, puis
  exécuter inspection, drainage et redémarrage ciblé avec une preuve durable.
- Portée DDD : contrats d'instantané et de commande, ports de lecture
  PostgreSQL, identité de participant runtime, audit d'opération, adaptateur
  d'exécution local et documentation opérateur.
- Scénario BDD :
  - Given deux replicas du profil `test` sont enregistrés, l'un exécute une page
    Granite et l'autre reste disponible.
  - When l'opérateur inspecte la capacité, demande le drainage du premier puis
    son redémarrage ciblé après terminaison ou expiration fenced.
  - Then l'instantané publie les états, jobs, slots et métriques avec leurs
    unités, le second replica continue ses admissions, l'ancien détenteur ne
    peut plus écrire et chaque décision opératoire est auditée.
- Tests d'acceptation à écrire : test PostgreSQL réel avec deux présences, un
  claim et un slot actifs ; lecture des comptes prêts/réclamés/repris/échoués ;
  métriques de durée, attente, RAM, GPU, VRAM, puissance, assemblage et
  projection ; drainage d'une seule cible ; refus d'un nouveau claim ;
  redémarrage après terminaison puis après expiration ; refus d'une cible
  étrangère, périmée ou ambiguë ; refus d'un troisième replica ou d'une limite
  différente de 2 Gio.
- Tests unitaires à écrire : value objects et sérialisation de l'instantané ;
  calcul strict de `READY`, `BUSY`, `DRAINING` et absence à partir des autorités
  persistées ; validation des unités et fenêtres ; politique et ordre des
  opérations ; idempotence d'une même intention ; audit des succès et refus ;
  absence d'import de logs comme autorité et absence de mutation de la
  progression publique.
- Implémentation attendue : ajouter les ports et adaptateurs d'administration
  à `platform` ; compléter si nécessaire la migration ascendante avec
  l'identité runtime et l'audit sans valeur par défaut ; lire les métriques de
  pages déjà persistées ; exposer le point d'entrée opérateur local défini par
  P-002 ; raccorder drainage puis redémarrage ciblé à l'instance enregistrée ;
  compléter `docs/runbooks/distribution_locale.md`, la traçabilité et
  `journal.md`.
- Invariants et garde-fous : le processus Docker n'est qu'un adaptateur d'effet,
  jamais l'autorité de l'état métier ; une métrique indisponible porte une
  erreur explicite ; `GRANITE_CUDA_UNAVAILABLE` et OOM restent terminaux ; un
  restart ne change ni image, ni configuration, ni route, ni environnement.
- Dépendances : P-002 ; M13-environments ; M14-distribution-core T-004 ;
  M14-local-pipeline T-006 à T-008 ; ADR-024, ADR-025, ADR-046, ADR-051 et
  ADR-052 ; `app/platform/job_runtime/granite_capacity.py` ;
  `app/source_processing/adapters/worker_runtime.py` ;
  `app/platform/administrative_operations.py`.
- Commandes de validation : tests unitaires ciblés des contrats, read-models et
  opérations ; tests PostgreSQL réels ciblés ; tests de composition locale
  ciblés ; `uv run --locked gate --scope m013_environments` ;
  `uv run --locked gate --scope m014_distribution_core` ;
  `uv run --locked gate --scope m014_local_pipeline` ;
  `uv run --locked gate --scope m014_local_qualification` ;
  `uv run --locked gate --scope m014_local_qualification --live`. Le
  sous-agent ne lance aucune gate globale.
- Commit RED :
  `test(m014-qualification): couvrir observabilite et operations locales`.
- Commit GREEN :
  `feat(m014-qualification): publier observabilite et operations locales`.
