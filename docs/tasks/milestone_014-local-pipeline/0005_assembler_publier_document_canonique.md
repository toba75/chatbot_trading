# T-007 - Assembler et publier le document canonique

## Milestone

- Nom : M14-local-pipeline - Pipeline documentaire local distribué.
- Source : `docs/specs/plan_distribution.md`, T-007 ; spécification M-004.
- Objectif métier : reconstruire depuis les résultats persistés une seule
  version canonique complète, conforme aux autorités textuelles M-004.

## Contexte DDD

- Domaine : traitement des sources documentaires.
- Bounded context : SP possède la complétude, l'assemblage, la QA, l'artefact
  canonique, la publication et l'événement `CanonicalSourcePublished`.
- Objectif métier : empêcher qu'une exécution distribuée rende visible un
  document partiel, divergent ou publié plusieurs fois.
- Langage ubiquitaire : complétude, assembleur canonique, autorité textuelle,
  `DoclingDocument unique`, QA canonique, publication atomique, version
  immuable, événement de publication.
- Invariants critiques : toutes les pages du manifeste sont représentées dans
  l'ordre PDF ; toute page non vide a un résultat réussi et une autorité unique ;
  `SKIP_EMPTY` reste audité sans autorité synthétique ; un résultat échoué ou
  divergent interdit toute publication ; un rejeu exact conserve la même version.
- Garde-fous : aucun modèle n'est réexécuté ; aucun contenu n'est fusionné
  silencieusement ; aucune version n'est visible avant persistance complète ;
  aucun événement n'est émis sans version canonique acceptée.

## Blocages Ou Préconditions

- État GREEN/RED connu : T-006 GREEN ; les résultats et progressions SP sont
  durables, idempotents et issus d'enveloppes fenced.
- Présence des milestones amont dans master : politiques M-004 de fusion,
  autorité, QA, artefact immuable et événement outbox disponibles.
- Décisions manquantes : aucune ; la publication publique doit rester atomique
  côté SP. Un stockage d'artefact local ne peut être rendu transactionnel avec
  PostgreSQL par une transaction intercontextes inventée.
- Risques : job d'assemblage créé plusieurs fois, résultat manquant pris pour
  vide, ordre de pages altéré, artefact orphelin rendu public, événement émis
  avant commit, ou nouvel identifiant canonique à chaque rejeu.

## Tâches

### T-007 - Assembler et publier le document canonique

- But métier : rendre visible une version canonique unique seulement lorsque
  le traitement distribué est complet et contractuellement valide.
- Portée DDD : déclenchement idempotent du job
  `ASSEMBLE_CANONICAL_DOCUMENT`, lecture SP du manifeste/résultats, politiques
  M-004, stockage immuable, persistance de la version et outbox métier.
- Scénario BDD :
  - Given toutes les pages sauf une possèdent un résultat valide et plusieurs
    redélivrances tentent de déclencher l'assemblage.
  - When le dernier résultat compatible est persisté puis deux workers
    réclament successivement le même assemblage.
  - Then aucune version n'existe avant complétude, un seul job d'assemblage est
    créé, une seule version canonique complète est publiée et le rejeu retourne
    la même identité sans second événement ni progression supplémentaire.
- Tests d'acceptation à écrire : PostgreSQL réel avec page absente, doublon
  identique, doublon divergent, `FAILED`, `SKIP_EMPTY`, ordre PDF et autorité
  unique ; concurrence de création et de claim de l'assembleur ; crash après
  écriture de l'artefact mais avant commit SP ; rejeu après commit ; preuve
  atomique de version, succès public et outbox `CanonicalSourcePublished`.
- Tests unitaires à écrire : calcul de complétude par manifeste ; vérification
  des versions et hashes de résultats ; reconstruction des sorties pagewise ;
  sélection d'autorité et QA M-004 ; identité déterministe de version et de job ;
  refus des pages manquantes, surnuméraires, échouées ou divergentes ; aucun
  appel aux ports de modèles.
- Implémentation attendue : créer l'outbox d'assemblage dans la transaction SP
  qui constate la dernière complétion ; exécuter un handler dédié lisant
  uniquement les données SP ; réutiliser les politiques et le stockage M-004 ;
  rendre un artefact préparé invisible tant que la transaction de publication
  n'est pas validée ; persister version, état public `SUCCEEDED` et événement
  métier dans une transaction SP, puis acquitter le job technique séparément.
- Invariants et garde-fous : une panne après préparation d'un artefact peut
  laisser un fichier immuable non référencé, jamais une version partielle ; le
  rejeu vérifie les octets et le hash attendus ; toute divergence échoue
  explicitement ; la progression réussie vaut exactement le total figé.
- Dépendances : T-006 ; spécification M-004 ; ADR-001 à ADR-004 ;
  ADR-024 ; ADR-052 ; `app/source_processing/application/publish_canonical_source.py` ;
  `app/source_processing/application/publish_canonical_source_event.py`.
- Commandes de validation : tests unitaires d'assemblage, autorité et QA ; tests
  PostgreSQL live de complétude, concurrence, crash et publication atomique ;
  `uv run --locked gate --scope m004` ;
  `uv run --locked gate --scope m014_local_pipeline --live`. Le sous-agent
  exécute uniquement les tests et scopes ciblés. La gate globale de clôture
  appartient à l’orchestrateur selon la politique unique du journal.
- Commit RED : `test(m014-pipeline): couvrir assemblage canonique atomique`.
- Commit GREEN : `feat(m014-pipeline): publier document canonique complet`.
