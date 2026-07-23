# T-004 - Migrer le quota Granite fenced

## Milestone

- Nom : M14-distribution-core - Socle de distribution locale durable.
- Source : `docs/specs/plan_distribution.md`, T-004 ; ADR-021, ADR-025 et
  ADR-052.
- Objectif métier : rendre durable et concurrent le plafond de deux conversions
  Granite avant que le pipeline documentaire ne distribue réellement ses pages.

## Contexte DDD

- Domaine : capacité d'exécution locale et persistance des résultats de pages.
- Bounded contexts : `platform` possède le quota d'exécution et ses leases ;
  Source Processing possède les résultats de pages et leur idempotence ; chaque
  transaction forte reste sous un seul propriétaire.
- Objectif métier : garantir qu'un troisième travail Granite attend sans
  lancer le modèle et qu'un slot perdu devient récupérable sans autoriser
  l'ancien détenteur à écrire.
- Langage ubiquitaire : slot Granite, acquisition, lease active, heartbeat,
  expiration, drainage, claim fenced, génération, token, résultat de page,
  migration ascendante, rejeu idempotent.
- Invariants critiques : deux slots actifs au maximum par environnement et
  déploiement ; un slot actif au maximum par instance de worker ; acquisition et
  réattribution atomiques ; token UUID v4 et génération monotone ; toute mutation
  compare le claim du job et la lease du slot ; une troisième acquisition
  n'appelle aucun convertisseur.
- Garde-fous : aucune modification d'une migration appliquée ; aucune suppression
  de table ou colonne ; aucun verrou ou compteur en mémoire comme autorité ;
  aucune libération non fenced dans un `finally` qui masquerait la perte de
  lease ; aucun fallback CPU ou changement de route.

## Blocages Ou Préconditions

- État GREEN/RED connu : T-001 à T-003 sont GREEN ; ADR-052 et les contrats
  versionnés gouvernent l'implémentation.
- Présence des milestones amont dans master : migrations PostgreSQL 001 à 021,
  protocole ADR-025 et contrôles M13-environments présents.
- Décisions manquantes : aucune ; si le schéma nécessaire ne peut pas respecter
  les propriétaires définis par ADR-052, arrêter et créer une ADR remplaçante.
- Risques : double acquisition, slot orphelin, réattribution sans nouvelle
  identité, ancien heartbeat accepté, migration non rejouable, mélange
  d'environnements ou démarrage du modèle pendant l'attente.

## Tâches

### T-004 - Migrer le quota Granite fenced

- But métier : matérialiser dans PostgreSQL le quota décidé et prouver son
  comportement sous concurrence et reprise réelle.
- Portée DDD : migration ADR-021 suivante, repository de slots, service
  d'acquisition et heartbeat, adaptation Granite bornée, structures nécessaires
  aux futurs résultats de pages sans activer encore le fan-out T-005.
- Scénario BDD :
  - Given deux claims de pages Granite valides, détenus par deux workers du même
    environnement, occupent les deux slots durables.
  - When un troisième claim tente une acquisition, puis que la lease du premier
    expire et que l'ancien détenteur tente encore de la renouveler.
  - Then le troisième claim reste en attente sans appel Granite, acquiert ensuite
    le slot avec une génération et un token nouveaux, et toutes les mutations de
    l'ancien détenteur échouent explicitement sans résultat ni progression.
- Tests d'acceptation à écrire : migration réelle depuis la version 021,
  réexécution par le ledger et schéma descendant interdit ; deux acquisitions
  concurrentes réussies et troisième en attente ; plafond d'un slot par worker ;
  heartbeat actif ; expiration et reprise ; ancien renouvellement, libération et
  succès refusés ; incompatibilité d'environnement refusée ; absence vérifiée
  d'appel au modèle tant qu'aucun slot n'est acquis.
- Tests unitaires à écrire : validation de l'identité du slot, génération et
  token, transition `available -> leased -> available`, drainage, délai de lease
  invalide, claim absent ou incohérent, statut d'attente non terminal, libération
  répétée, résultat divergent et propagation des codes d'erreur stables définis
  en T-003.
- Implémentation attendue : ajouter uniquement la migration ascendante suivante
  sous `deploy/postgres/migrations/`, l'enrôler dans le ledger, créer le port et
  l'adaptateur PostgreSQL du quota selon ADR-052, câbler un seul contrôleur de
  capacité autour de toutes les routes Granite, renouveler la lease pendant le
  sous-processus et libérer sous fencing après succès ou échec explicite ;
  préparer les tables ou colonnes de résultats de pages appartenant à SP sans
  créer les jobs ni l'assemblage du sous-milestone suivant.
- Invariants et garde-fous : ordre des locks documenté et testé ; transactions
  courtes ; requêtes de claim compatibles avec `FOR UPDATE SKIP LOCKED` ; index
  des chemins chauds prouvés sur PostgreSQL ; deux profils différents ne voient
  jamais les mêmes slots ; l'expiration ne vaut ni succès ni publication.
- Dépendances : T-003 ; ADR-021, ADR-024, ADR-025 et ADR-052 ;
  `app/platform/job_runtime` ; migrations 008, 020 et 021 ; limiteur Granite
  partagé M-004.
- Commandes de validation : tests unitaires du quota ; tests PostgreSQL live de
  migration, concurrence, fencing et reprise ;
  `uv run --locked gate --scope m004` ;
  `uv run --locked gate --scope m013_environments` ;
  `uv run --locked gate --scope m014_distribution_core` ;
  `uv run --locked gate`.
- Commit RED : `test(m014-core): couvrir quota Granite fenced PostgreSQL`.
- Commit GREEN : `feat(m014-core): persister deux slots Granite fenced`.
