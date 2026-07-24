# T-005 - Éclater la conversion en jobs de pages

## Milestone

- Nom : M14-local-pipeline - Pipeline documentaire local distribué.
- Source : `docs/specs/plan_distribution.md`, T-005 ; ADR-024 et ADR-052.
- Objectif métier : transformer un traitement documentaire routé en unités de
  page indépendamment réclamables sans perdre le manifeste ni la progression.

## Contexte DDD

- Domaine : traitement des sources documentaires.
- Bounded context : SP possède `DocumentProcessingRun`, le manifeste, les
  routes, la demande de conversion et l'outbox de jobs ; `platform` ne reçoit
  que les enveloppes techniques relayées.
- Objectif métier : permettre aux deux workers de traiter des pages distinctes
  d'un même document avec un total public immuable.
- Langage ubiquitaire : fan-out, manifeste figé, job de page, page vide,
  résultat `SKIP_EMPTY`, clé d'idempotence, outbox transactionnelle, total de
  progression.
- Invariants critiques : exactement une décision par page du manifeste ; aucun
  job pour `SKIP_EMPTY` ; exactement un `CONVERT_PAGE` par page non vide ; la
  clé inclut traitement, page, route, politique et version de contrat ; le
  total est fixé avant le premier relais.
- Garde-fous : aucun insert SP direct dans `platform.technical_jobs` ; aucune
  route recalculée ; aucun fan-out en mémoire comme autorité ; aucune page vide
  envoyée à Docling, Granite, OCRmyPDF ou Gemma.

## Blocages Ou Préconditions

- État GREEN/RED connu : P-001 et P-002 GREEN ; scope
  `m014_local_pipeline` présent avec uniquement ses tests de spécification.
- Présence des milestones amont dans master : contrats M-003/M-004, outbox
  ADR-024, claims ADR-025 et contrats M14-core disponibles.
- Décisions manquantes : le discriminateur versionné d'activation du parcours
  distribué doit être nommé dans la spécification P-002 ; aucune valeur absente
  ne peut sélectionner silencieusement l'ancien ou le nouveau parcours.
- Risques : fan-out partiel, double job après rejeu, progression comptée à la
  soumission au lieu du résultat, traitement déjà commencé basculé de version,
  ou payload de page couplé à un chemin Docker libre.

## Tâches

### T-005 - Éclater la conversion en jobs de pages

- But métier : matérialiser une fois le travail de chaque page routée et rendre
  le backlog réclamable par les deux replicas généralistes.
- Portée DDD : cas d'usage SP `CONVERT_DOCUMENT`, repository de traitement,
  résultats `SKIP_EMPTY`, outbox SP et relais idempotent vers la file `platform`.
- Scénario BDD :
  - Given un traitement SP routé de quatre pages, dont une page `SKIP_EMPTY`,
    possède un manifeste et une politique figés dans l'environnement `test`.
  - When `CONVERT_DOCUMENT` active explicitement le parcours distribué et
    exécute le fan-out deux fois avec la même identité.
  - Then SP persiste une seule fois le résultat vide, un total public égal à
    quatre et trois enveloppes `CONVERT_PAGE` identiques ; le relais crée trois
    jobs techniques sans doublon et aucune conversion n'est encore exécutée.
- Tests d'acceptation à écrire : test ATDD du scénario complet avec PostgreSQL
  réel ; crash après une partie des inserts puis rollback total ; rejeu exact ;
  refus d'un manifeste, hash, route, politique, environnement ou payload
  divergent ; vérification qu'un traitement démarré sous l'ancienne version ne
  bascule pas ; preuve qu'aucun convertisseur n'est appelé.
- Tests unitaires à écrire : construction déterministe du hash de manifeste et
  des `ConvertPageContract` ; ordre PDF ; `SKIP_EMPTY` terminal sans artefact ni
  métrique inventée ; total stable ; activation explicite ; comparaison de
  rejeu ; refus de page absente, dupliquée ou hors manifeste.
- Implémentation attendue : introduire le cas d'usage de fan-out sous SP ;
  étendre la persistance PostgreSQL pour écrire dans une seule transaction SP
  l'état d'exécution, les résultats vides et les entrées
  `source_processing.job_outbox` ; relayer les contrats existants vers
  `platform` avec `JobOutboxRelay` ; conserver le job parent distinct de l'état
  public jusqu'à la publication canonique.
- Invariants et garde-fous : un acquittement du job parent ne vaut ni
  complétion de page ni succès public ; `completed_units` n'augmente que pour
  le `SKIP_EMPTY` persisté à ce stade ; les artefacts utilisent
  `LocalArtifactIdentity` et leur SHA-256, jamais un chemin arbitraire.
- Dépendances : P-002 ; ADR-024 ; ADR-025 ; ADR-052 ;
  `app/source_processing/application/document_commands.py` ;
  `app/source_processing/adapters/postgres_document_persistence.py` ;
  `app/source_processing/domain/distribution_contracts.py`.
- Commandes de validation : tests unitaires et d'acceptation du fan-out ; tests
  PostgreSQL live de transaction et rejeu ;
  `uv run --locked gate --scope m004` ;
  `uv run --locked gate --scope m013_environments` ;
  `uv run --locked gate --scope m014_distribution_core` ;
  `uv run --locked gate --scope m014_local_pipeline`. Le sous-agent exécute
  uniquement les tests et scopes ciblés. La gate globale de clôture appartient
  à l’orchestrateur selon la politique unique du journal.
- Commit RED : `test(m014-pipeline): couvrir fan-out transactionnel des pages`.
- Commit GREEN : `feat(m014-pipeline): eclater conversion en jobs de pages`.
