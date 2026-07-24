# P-001 - Vérifier la précondition GREEN de la qualification locale

## Milestone

- Nom : M14-local-qualification - Qualification de capacité locale.
- Source : `docs/specs/plan_distribution.md`, T-009 à T-011 ; plan
  d'implémentation, section `M14-local-qualification`.
- Objectif métier : établir que la qualification porte sur le pipeline local
  distribué réellement fusionné et GREEN, avant d'ajouter une surface
  opératoire ou de produire une nouvelle mesure de capacité.

## Contexte DDD

- Domaine : traitement documentaire local et exploitation de la plateforme.
- Bounded contexts : Source Processing (SP) reste propriétaire du traitement,
  des résultats de pages, de la progression et de la version canonique ;
  Knowledge Access (KA) reste propriétaire de la projection ; `platform`
  possède les workers, jobs, claims, slots et opérations techniques.
- Objectif métier : distinguer une régression amont d'un défaut introduit par
  l'observabilité, les opérations ou le protocole de qualification.
- Langage ubiquitaire : précondition GREEN, replica documentaire, slot Granite,
  qualification réelle, baseline mono-worker, reprise fenced, rapport de
  capacité, campagne de charge.
- Invariants critiques : `M14-local-pipeline` est présent dans `master` ; les
  deux replicas restent locaux, généralistes et limités à 2 Gio ; Granite reste
  sur `cuda:0`, avec deux slots globaux et un slot par worker ; la progression
  métier publique reste indépendante de l'état technique.
- Garde-fous : aucun RED n'est masqué ; une gate offline n'est jamais présentée
  comme une preuve GPU ; aucun PDF répété, copié ou synthétique ne compte comme
  un document distinct de la campagne T-011 ; aucun fallback CPU, distant ou
  vers une autre route n'est admis.

## Blocages Ou Préconditions

- État GREEN/RED connu : le 2026-07-24, sur le `HEAD` propre
  `e7534217bd63`, `uv run --locked gate` planifie 482 nœuds et termine
  `PARTIAL GREEN: offline`, code 0, sans nœud absent, inattendu ni dupliqué.
  `uv run --locked gate --scope m014_local_pipeline --live` planifie 46
  nœuds et termine `SCOPE GREEN`, avec les preuves PostgreSQL et Qdrant réelles.
- Présence des milestones amont dans master : après
  `git fetch origin --prune`, `master` et `origin/master` pointent sur
  `e7534217bd63` ; M-013, `M14-distribution-core`,
  `M14-local-pipeline`, leurs ADR, migrations, tests et code sont visibles dans
  `master`.
- Décisions manquantes : aucune avant T-009. ADR-052 reste proposée jusqu'aux
  preuves de T-010 et T-011 ; elle ne peut être acceptée ou remplacée qu'en
  T-011 à partir des rapports réels.
- Risques : le dépôt ne contient actuellement que douze PDF suivis par Git LFS,
  donc pas encore les cent PDF réels distincts requis par T-011 ; cette absence
  ne bloque pas T-009 ou T-010, mais bloque l'exécution de la campagne T-011
  tant qu'un manifeste de cent empreintes distinctes n'est pas disponible.

## Tâches

### P-001 - Vérifier la précondition GREEN de la qualification locale

- But métier : figer une preuve attribuable que la qualification mesure le
  pipeline M14 livré et non une branche, un mock ou une configuration locale
  divergente.
- Portée DDD : gouvernance de milestone, identité Git, configuration
  M13-environments, scopes M14-core et M14-pipeline ; aucun comportement T-009
  à T-011 n'est implémenté.
- Scénario BDD :
  - Given `master` contient M14-local-pipeline, les profils explicites et les
    deux workers documentaires locaux configurés à 2 Gio.
  - When les références Git, les artefacts amont et les gates ciblées offline
    puis live sont vérifiés sur un worktree propre.
  - Then les scopes amont sont GREEN, la preuve live reste distincte de la gate
    offline et tout écart exact bloque le premier test RED de P-002.
- Tests d'acceptation à écrire : aucun test fonctionnel artificiel ; conserver
  les sorties exactes des gates et vérifier que le futur scope
  `m014_local_qualification` dépend de `precondition.m014_local_pipeline`.
- Tests unitaires à écrire : aucun si les contrôles restent GREEN ; si un écart
  de manifeste de gate est découvert, ajouter uniquement le test ciblé qui
  reproduit cet écart avant sa correction.
- Implémentation attendue : consigner dans `journal.md` les références Git, le
  nombre de nœuds, les verdicts offline/live, l'identité de configuration et
  l'inventaire du corpus réel ; ne créer ni surface opératoire ni rapport de
  capacité dans cette tâche.
- Invariants et garde-fous : le fichier local ignoré
  `config/application.yaml` ne devient jamais une preuve versionnée ; la gate
  live M14-pipeline prouve PostgreSQL/Qdrant, pas encore la concurrence Granite
  réelle de T-010 ; la campagne de cent PDF ne peut être simulée par cent
  soumissions du même document.
- Dépendances : `AGENTS.md` ; `docs/tasks/README.md` ; M-013 ;
  M14-distribution-core ; M14-local-pipeline ; ADR-050, ADR-051, ADR-052 et
  ADR-053.
- Commandes de validation : `git fetch origin --prune` ;
  `git rev-list --left-right --count master...origin/master` ;
  `git ls-tree -r --name-only master -- docs/tasks/milestone_013 docs/tasks/milestone_014-distribution-core docs/tasks/milestone_014-local-pipeline docs/adr app gate_tests` ;
  `git lfs ls-files` ; `uv run --locked gate --scope governance` ;
  `uv run --locked gate --scope m013_environments` ;
  `uv run --locked gate --scope m014_distribution_core --live` ;
  `uv run --locked gate --scope m014_local_pipeline --live` ;
  `git diff --check`. Le sous-agent n'exécute que ces scopes ciblés.
  L'orchestrateur conserve seul la preuve globale réutilisable et l'unique gate
  globale de clôture du candidat final.
- Commit RED : aucun commit RED artificiel lorsque toutes les préconditions sont
  GREEN ; tout RED réel est conservé avec sa commande et sa sortie exactes.
- Commit GREEN : aucun commit si aucune correction n'est requise ; sinon un
  commit ciblé `fix(m014-qualification): retablir precondition green` précède
  P-002.
