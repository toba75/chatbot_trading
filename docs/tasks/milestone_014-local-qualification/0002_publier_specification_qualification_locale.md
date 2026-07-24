# P-002 - Publier la spécification de qualification locale

## Milestone

- Nom : M14-local-qualification - Qualification de capacité locale.
- Source : `docs/specs/plan_distribution.md`, T-009 à T-011 ; ADR-050,
  ADR-051 et ADR-052.
- Objectif métier : définir avant l'implémentation ce que l'opérateur observe,
  commande et mesure pour qualifier les deux workers locaux sans reconstruire
  un état depuis les logs ou l'état Docker.

## Contexte DDD

- Domaine : exploitation et qualification du traitement documentaire local.
- Bounded contexts : `platform` possède l'état technique, les claims, les slots
  et les commandes opératoires ; SP publie les résultats, métriques de pages,
  progressions et versions canoniques ; KA publie l'état de projection.
- Objectif métier : établir un langage et des contrats séparés pour le pilotage
  technique, la preuve fonctionnelle et la charge.
- Langage ubiquitaire : instantané d'administration, replica attendu, présence
  expirée, `READY`, `BUSY`, `DRAINING`, slot actif, slot en attente, intention
  de drainage, redémarrage ciblé, reprise fenced, exécution de qualification,
  corpus de charge, verdict mesuré.
- Invariants critiques : l'instantané technique ne devient jamais la
  progression publique ; chaque métrique indique son unité, sa fenêtre et son
  autorité ; chaque commande nomme exactement l'environnement, le déploiement
  et le worker ; un rapport lie Git, image, actifs, configuration, corpus et
  résultats par empreinte.
- Garde-fous : aucune valeur par défaut pour l'environnement, le worker, le
  corpus, le nombre de répétitions ou les seuils ; aucun état `READY` déduit de
  l'existence d'un conteneur ; aucun rapport synthétique, fusion de campagnes
  partielles ou remplacement silencieux d'une dépendance réelle.

## Blocages Ou Préconditions

- État GREEN/RED connu : P-001 GREEN sur 482 nœuds offline et 46 nœuds live du
  scope M14-pipeline. Cette preuve reste réutilisable seulement tant que `HEAD`
  et le worktree n'ont pas changé.
- Présence des milestones amont dans master : M14-local-pipeline fournit les
  jobs de pages, les résultats et métriques techniques persistés, l'assemblage
  canonique et la projection locale ; M14-core fournit le registre de workers
  et les slots Granite fenced.
- Décisions manquantes : aucune dans le périmètre retenu. La surface opératoire
  reste un point d'entrée local et n'ajoute ni API HTTP ni action UI. Une
  exposition HTTP ou UI, une nouvelle autorité de métriques ou un orchestrateur
  distinct constitue une décision structurante et bloque l'implémentation
  jusqu'à une ADR dédiée.
- Risques : confondre santé de processus et disponibilité métier, confondre
  saturation et panne, rendre une commande de redémarrage possible sans
  drainage, ou laisser un rapport déclarer GREEN malgré une métrique absente.

## Tâches

### P-002 - Publier la spécification de qualification locale

- But métier : fournir le contrat exécutable commun à T-009, T-010 et T-011
  avant leur premier test d'acceptation.
- Portée DDD : langage ubiquitaire, propriétaires, ports de lecture et de
  commande, états et transitions, erreurs stables, schémas des preuves live,
  règles d'agrégation, critères de décision, points d'entrée UV
  `m014-local-qualification` et `m014-local-load`, et exclusions.
- Scénario BDD :
  - Given deux replicas locaux du même environnement publient leur présence et
    les autorités PostgreSQL possèdent jobs, claims et slots.
  - When l'opérateur inspecte ou draine un replica, puis une qualification
    fonctionnelle ou de charge produit son rapport.
  - Then chaque état et chaque mesure proviennent d'une autorité explicitement
    nommée, les commandes sont auditées et fenced, et un champ absent rend le
    verdict incomplet ou RED sans valeur inventée.
- Tests d'acceptation à écrire : créer le scope
  `m014_local_qualification`, sa précondition dépendante de
  `m014_local_pipeline` et un validateur exigeant : mission et frontières DDD ;
  contrat d'administration distinct du contrat public ; états workers/jobs/slots ;
  inspection, drainage et redémarrage ; unités et fenêtres des métriques ;
  preuve de chevauchement réel ; protocole de panne ; schémas des rapports
  T-010/T-011 ; exactement cent PDF distincts ; décision ADR-052 ; exclusions
  réseau et fallbacks.
- Tests unitaires à écrire : refuser dans le validateur une autorité absente,
  une progression reconstruite, un worker sans identité complète, une métrique
  sans unité ou fenêtre, un seuil implicite, un rapport synthétique, un corpus
  avec empreintes répétées, un redémarrage avant drainage et toute référence à
  SSH, Kamal, Colima, `arm64` ou stockage réseau.
- Implémentation attendue : créer
  `docs/specs/m014_local_qualification_capacite.md` ; enregistrer le validateur
  sous `ost_gate/`, la précondition sous `gate_tests/preconditions/`, les tests
  sous `gate_tests/ported/tests/m014_local_qualification/` et le scope dans
  `gate.toml` ; relier les comportements aux fichiers 0003 à 0005.
- Invariants et garde-fous : la spécification ne crée aucun code de production ;
  elle conserve `uv run test` et `uv run test-isolation` sous ADR-050 ; T-010
  utilise `uv run --locked m014-local-qualification` et T-011 utilise
  `uv run --locked m014-local-load`, deux points d'entrée versionnés liés au
  profil `test` et à leurs manifestes explicites ; aucun seuil historique n'est
  transformé en promesse portable.
- Dépendances : P-001 ; `docs/specs/plan_distribution.md` ;
  `docs/specs/m014_local_pipeline_documentaire_distribue.md` ;
  `docs/specs/m013_environments_environnements_explicites.md` ; ADR-024,
  ADR-025, ADR-050, ADR-051, ADR-052 et ADR-053.
- Commandes de validation : tests d'acceptation et unitaires ciblés du nouveau
  validateur ; `uv run --locked gate --scope governance` ;
  `uv run --locked gate --scope m014_local_pipeline` ;
  `uv run --locked gate --scope m014_local_qualification`. Le sous-agent ne
  lance aucune gate globale ; l'orchestrateur la réserve au candidat final.
- Commit RED :
  `test(m014-qualification): exiger specification qualification locale`.
- Commit GREEN :
  `docs(m014-qualification): publier specification qualification locale`.
