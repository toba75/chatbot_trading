# T-008 - Projeter localement le document publié

## Milestone

- Nom : M14-local-pipeline - Pipeline documentaire local distribué.
- Source : `docs/specs/plan_distribution.md`, T-008 ; spécification M-005.
- Objectif métier : rendre la version canonique distribuée recherchable dans le
  Qdrant local du même environnement, sans dupliquer ni devancer la publication.

## Contexte DDD

- Domaine : accès aux connaissances.
- Bounded contexts : SP publie `CanonicalSourcePublished` ; KA consomme ce fait,
  possède `KnowledgeProjection` et son outbox ; `platform` exécute le job
  technique local sans devenir propriétaire de la projection.
- Objectif métier : préserver la cohérence éventuelle SP vers KA tout en
  garantissant une projection complète, idempotente et étanche.
- Langage ubiquitaire : version canonique publiée, demande de projection,
  `PROJECT_DOCUMENT`, empreinte de build, projection `SEARCHABLE`, génération
  Qdrant, événement redélivré.
- Invariants critiques : aucune projection avant `CanonicalSourcePublished` ;
  une version et un profil déterminent une empreinte stable ; un même événement
  et un même job ne créent qu'une projection ; Qdrant, artefact et job portent
  la même identité d'environnement.
- Garde-fous : aucun accès KA aux tables privées SP ; aucun identifiant de
  collection fourni par un client ; aucune collection de secours ; aucun
  fallback dense, sparse, modèle ou Qdrant ; aucune progression issue des logs.

## Blocages Ou Préconditions

- État GREEN/RED connu : T-007 GREEN ; la publication canonique et son événement
  outbox sont atomiques et idempotents.
- Présence des milestones amont dans master : projection M-005, consumer
  `CanonicalSourcePublishedProjectionConsumer`, worker `PROJECT_DOCUMENT`,
  Qdrant et progression publique M13-environments disponibles.
- Décisions manquantes : aucune ; `PROJECT_DOCUMENT` reste au niveau document
  et local. Le découpage de projection en lots distribués ou un stockage réseau
  reste hors périmètre.
- Risques : demande manuelle et événement créant deux projections, job soumis
  avant disponibilité de l'artefact, build répété divergent, collection d'un
  autre profil, index partiel marqué `SEARCHABLE` ou acquittement prématuré.

## Tâches

### T-008 - Projeter localement le document publié

- But métier : fermer le parcours M14-local-pipeline par une projection unique
  et recherchable de la version canonique complète.
- Portée DDD : relais d'événement SP vers KA, consumer idempotent, repository et
  outbox KA, job `PROJECT_DOCUMENT`, lecture de l'artefact canonique, publication
  d'une génération Qdrant locale et progression KA persistée.
- Scénario BDD :
  - Given une version canonique complète de l'environnement `test` publie deux
    fois le même événement `CanonicalSourcePublished`.
  - When KA consomme les redélivrances puis le worker local exécute et rejoue le
    job `PROJECT_DOCUMENT`.
  - Then une seule `KnowledgeProjection` et une seule génération Qdrant deviennent
    `SEARCHABLE`, les chunks couvrent la version publiée, la progression est
    persistée une seule fois et aucune ressource d'un autre environnement n'est lue.
- Tests d'acceptation à écrire : relais événementiel PostgreSQL réel ;
  événement identique et événement divergent ; concurrence de création de
  projection et de job ; Qdrant local réel avec génération complète puis rejeu ;
  refus de version absente, non publiée, hash divergent, identité étrangère ou
  index partiel ; preuve que la recherche retrouve les mêmes localisateurs que
  le baseline fonctionnel.
- Tests unitaires à écrire : empreinte de build déterministe ; registre
  d'événements traités ; création atomique projection/outbox ; contrat du job ;
  sélection de la collection depuis la configuration complète ; transitions
  `REQUESTED` à `SEARCHABLE` ; rejeu exact ; progression et erreurs terminales.
- Implémentation attendue : raccorder l'événement persistant au consumer KA ;
  persister dans une transaction KA la projection et son outbox
  `PROJECT_DOCUMENT` ; conserver le worker document-level existant, renforcer
  ses contrôles d'environnement et d'idempotence, publier atomiquement la
  génération Qdrant puis l'état `SEARCHABLE` ; mettre à jour la matrice de
  traçabilité, les preuves du scope et `journal.md` pour T-005 à T-008.
- Invariants et garde-fous : l'API manuelle et l'événement convergent sur la
  même empreinte sans double job ; l'échec Qdrant produit `FAILED` sans index de
  secours ; la source canonique SP reste immuable ; les opérations et mesures
  de capacité T-009 à T-011 restent réservées à M14-local-qualification.
- Dépendances : T-007 ; M-005 ; M13-environments ; ADR-005 ;
  ADR-010 ; ADR-024 ; DDD-ADR-004 ; DDD-ADR-008 ;
  `app/knowledge_access/application/request_projection.py` ;
  `app/knowledge_access/adapters/projection_runtime.py`.
- Commandes de validation : tests unitaires d'événement, projection et rejeu ;
  tests PostgreSQL et Qdrant live du parcours local ;
  `uv run --locked gate --scope m005` ;
  `uv run --locked gate --scope m013_environments` ;
  `uv run --locked gate --scope m014_local_pipeline` ;
  `uv run --locked gate --scope m014_local_pipeline --live` ;
  `uv run --locked gate`.
- Commit RED : `test(m014-pipeline): couvrir projection locale idempotente`.
- Commit GREEN : `feat(m014-pipeline): projeter version canonique locale`.
