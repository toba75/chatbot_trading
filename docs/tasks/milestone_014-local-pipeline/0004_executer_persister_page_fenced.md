# T-006 - Exécuter et persister une page sous fencing

## Milestone

- Nom : M14-local-pipeline - Pipeline documentaire local distribué.
- Source : `docs/specs/plan_distribution.md`, T-006 ; ADR-025 et ADR-052.
- Objectif métier : produire un résultat de page durable une seule fois, même
  après perte d'un worker, redélivrance ou expiration d'un claim.

## Contexte DDD

- Domaine : traitement des sources et capacité d'exécution locale.
- Bounded contexts : `platform` réclame et clôt le travail technique ; SP
  possède le résultat de page et la progression ; le relais sépare leurs
  transactions locales.
- Objectif métier : permettre aux deux replicas d'exécuter les routes décidées
  sans doublon, écriture obsolète ni dépassement du quota Granite.
- Langage ubiquitaire : worker généraliste, claim compatible, lease, fencing,
  slot Granite, enveloppe terminale, résultat de page, progression persistée,
  redélivrance.
- Invariants critiques : tout job exécuté possède un claim actif ; une route
  Granite possède aussi un slot actif ; une route standard ne fabrique aucun
  slot ; l'artefact est vérifié avant lecture et écrit immuablement ; résultat
  et incrément de progression sont atomiques dans SP.
- Garde-fous : aucun résultat SP écrit directement par le worker ; aucun slot
  facultatif ambigu ; aucun appel modèle avant acquisition ; aucun fallback
  CPU, changement de route, progression locale ou acquittement avant persistance.

## Blocages Ou Préconditions

- État GREEN/RED connu : T-005 GREEN ; le fan-out produit des contrats
  `CONVERT_PAGE` réclamables et les résultats `SKIP_EMPTY` sont déjà persistés.
- Présence des milestones amont dans master : `CompletePageExecution`,
  `platform.page_completion_outbox`, `source_processing.page_execution_results`
  et le quota Granite fenced proviennent de M14-core.
- Décisions manquantes : aucune ; les variantes de complétion standard et
  Granite doivent être discriminées strictement à partir de la capacité du
  contrat T-005, jamais de la disponibilité matérielle observée.
- Risques : double progression, ancien détenteur accepté, enveloppe créée après
  expiration, résultat divergent sous la même identité, slot libéré avant
  l'enveloppe, ou erreur worker non livrée à SP.

## Tâches

### T-006 - Exécuter et persister une page sous fencing

- But métier : faire de chaque résultat de page un fait durable, idempotent et
  attribuable au claim qui a réellement autorisé son calcul.
- Portée DDD : boucle `worker-documents`, sélection de route M-003, adaptateurs
  de conversion M-004, ports de complétion `platform`, relais de complétion et
  repository SP de résultat/progression.
- Scénario BDD :
  - Given deux workers du même environnement réclament deux pages distinctes,
    dont une Granite, puis le premier worker perd sa lease avant de publier.
  - When le second worker reprend la page expirée et les enveloppes terminales
    sont redélivrées à SP.
  - Then chaque page possède un seul résultat compatible, la progression
    augmente une seule fois, le détenteur expiré est refusé, le slot Granite est
    libéré sous fencing et aucune route standard ne consomme de slot.
- Tests d'acceptation à écrire : deux workers PostgreSQL concurrents sur un même
  traitement ; route standard et route Granite ; crash avant et après création
  d'enveloppe ; expiration et reprise ; ancien heartbeat, complétion et
  libération refusés ; redélivrance identique idempotente ; contenu ou token
  divergent refusé ; résultat terminal échoué propagé avec code stable ;
  transaction SP prouvant résultat et progression inséparables.
- Tests unitaires à écrire : résolution et SHA-256 de l'artefact source ;
  dispatch fermé de toutes les routes autorisées ; construction de
  `PageResultContract` et métriques ; variantes fenced avec ou sans slot ;
  règles de rejeu ; progression bornée par le total ; aucun convertisseur pour
  `SKIP_EMPTY` ; classification stricte des erreurs.
- Implémentation attendue : enrôler `CONVERT_PAGE` dans les capacités des deux
  workers ; adapter la boucle pour réclamer le job compatible et acquérir un
  slot uniquement si le contrat l'exige ; exécuter le convertisseur décidé ;
  créer l'enveloppe terminale immuable dans `platform`, puis livrer par un relais
  durable à un port SP qui persiste résultat et progression dans une transaction
  locale et acquitte ensuite l'enveloppe par une transaction `platform` séparée.
- Invariants et garde-fous : le relais ne marque pas `relayed` avant le commit
  SP ; une page `FAILED` rend l'action publique terminalement échouée et bloque
  l'assemblage ; la RAM/GPU technique ne devient jamais une unité publique ;
  une erreur d'environnement est refusée avant lecture d'artefact ou modèle.
- Dépendances : T-005 ; ADR-024 ; ADR-025 ; ADR-040 ; ADR-042 ;
  ADR-051 ; ADR-052 ; `app/platform/job_runtime/granite_capacity.py` ;
  `app/source_processing/adapters/worker_runtime.py` ; convertisseurs M-004.
- Commandes de validation : tests unitaires de worker, contrat et relais ; tests
  PostgreSQL live de concurrence, crash, fencing et atomicité ;
  `uv run --locked gate --scope m004` ;
  `uv run --locked gate --scope m013_environments` ;
  `uv run --locked gate --scope m014_distribution_core --live` ;
  `uv run --locked gate --scope m014_local_pipeline --live`. Le sous-agent
  exécute uniquement les tests et scopes ciblés. L'orchestrateur exécute
  exactement une gate globale de clôture avec un timeout de 3 600 000 ms, attend
  le même cell ID après tout yield ou timeout d'affichage et ne la considère
  jamais relancée.
- Commit RED : `test(m014-pipeline): couvrir resultat de page fenced`.
- Commit GREEN : `feat(m014-pipeline): persister resultats de pages sous fencing`.
