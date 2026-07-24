# T-011 - Qualifier la charge et clôturer la décision

## Milestone

- Nom : M14-local-qualification - Qualification de capacité locale.
- Source : `docs/specs/plan_distribution.md`, T-011 et scénario DIST-007.
- Objectif métier : mesurer un backlog de cent PDF réels avec les deux workers
  à 2 Gio, publier les succès et échecs sans les masquer, puis accepter ou
  remplacer explicitement ADR-052 selon les preuves.

## Contexte DDD

- Domaine : qualification de capacité et gouvernance de la distribution locale.
- Bounded contexts : SP porte les traitements et versions canoniques ;
  `platform` porte jobs, workers, claims, slots et métriques d'exécution ; KA
  porte les projections ; la gouvernance publie le corpus, le protocole, le
  rapport et le verdict ADR.
- Objectif métier : déterminer si la topologie locale à deux workers est une
  capacité exploitable pour un backlog réel, pas seulement un succès de fixture.
- Langage ubiquitaire : corpus de charge, manifeste figé, document terminal,
  succès canonique, échec terminal, débit du backlog, latence page/document,
  attente Granite, reprise, pic RAM, pic GPU/VRAM, OOM, verdict de capacité.
- Invariants critiques : exactement cent PDF réels et cent SHA-256 distincts ;
  chaque entrée possède chemin, empreinte, taille et nombre de pages ; chaque
  document atteint un état terminal ; tout succès possède une version canonique
  complète et une projection ; tout échec conserve son code et sa phase.
- Garde-fous : aucun PDF dupliqué, copié, généré ou soumis plusieurs fois pour
  atteindre cent ; aucun échantillon exclu après observation ; aucune moyenne
  qui efface les percentiles ou erreurs ; aucune acceptation d'ADR-052 sans
  preuve live complète et aucun changement silencieux de son sens.

## Blocages Ou Préconditions

- État GREEN/RED connu : T-010 GREEN avec rapport réel complet, seuils figés et
  absence de fallback.
- Présence des milestones amont dans master : T-009 et T-010 sont fusionnées ;
  le point d'entrée de campagne réutilise leurs contrats d'observation et de
  qualification.
- Décisions manquantes : le manifeste de cent PDF réels distincts n'existe pas
  encore dans le dépôt au 2026-07-24 ; T-011 est bloquée avant son commit RED
  tant que cent fichiers lisibles et leurs droits d'usage ne sont pas fournis
  explicitement. Les douze PDF Git LFS actuels ne peuvent pas être répétés ou
  copiés pour contourner cette précondition.
- Risques : durée non bornée, disque insuffisant, arrêt de campagne perdant les
  résultats déjà terminaux, métriques GPU partielles, teardown supprimant le
  rapport, ou décision ADR prise sur un sous-ensemble favorable.

## Tâches

### T-011 - Qualifier la charge et clôturer la décision

- But métier : publier une mesure complète et auditable de la capacité locale
  sur cent PDF, puis fermer le statut architectural de la distribution M-014.
- Portée DDD : manifeste immuable du corpus, orchestrateur de campagne,
  checkpoints durables, agrégation de métriques, rapport de verdict, statut ou
  remplacement d'ADR-052 et documentation de clôture.
- Scénario BDD :
  - Given un manifeste figé de cent PDF réels distincts dans `test`, deux
    workers `READY`, deux slots Granite et le rapport T-010 GREEN.
  - When la campagne dédiée soumet chaque document par le contrat HTTP réel et
    attend tous les états terminaux malgré les erreurs individuelles.
  - Then les succès sont canoniques et projetés, les échecs restent visibles,
    le rapport compare débit, latences, attentes, RAM, GPU, VRAM, reprises et
    OOM au contrôle mono-worker, puis ADR-052 est acceptée ou explicitement
    remplacée selon le verdict.
- Tests d'acceptation à écrire : validation du manifeste à cent entrées et
  empreintes distinctes ; point d'entrée UV de campagne hors gate de PR ;
  reprise d'une campagne interrompue depuis des checkpoints sans resoumettre un
  document terminal ; conservation des erreurs ; rapport exhaustif dont les
  dénominateurs totalisent cent ; vérification de chaque succès canonique et
  `SEARCHABLE` ; refus d'un rapport partiel, synthétique, sans métrique ou issu
  d'un autre environnement ; cohérence du statut ADR et de `docs/adr/index.md`.
- Tests unitaires à écrire : manifeste, checkpoints et identités ; calcul de
  débit, latences p50/p95/p99, attente Granite, pics RAM/VRAM/GPU, taux de
  reprise, erreurs et OOM ; agrégation sans division implicite ; comparaison au
  rapport T-010 ; règle de verdict ; validateur d'ADR proposée, acceptée ou
  remplacée.
- Implémentation attendue : créer le manifeste versionné du corpus et le point
  d'entrée UV court défini par P-002 ; vérifier espace disque et dépendances
  avant la première soumission ; exécuter une seule campagne réelle dans
  `test`, avec checkpoints et teardown borné ; publier les données structurées
  sous `docs/evaluation/m014/` et la synthèse sous `docs/governance/` ; si les
  preuves confirment la décision, passer ADR-052 de proposée à acceptée et
  mettre l'index à jour, sinon créer depuis `docs/adr/TEMPLATE.md` une ADR qui
  remplace explicitement ADR-052 ; compléter le runbook, la traçabilité et
  `journal.md`.
- Invariants et garde-fous : la campagne n'appartient pas à la gate répétée de
  chaque PR ; sa commande, sa révision et son manifeste sont figés avant
  exécution ; un OOM, une fuite d'environnement, un fallback CPU, un troisième
  processus Granite ou une métrique obligatoire absente interdit le verdict
  GREEN ; le déploiement réseau reste hors périmètre quel que soit le résultat.
- Dépendances : T-010 ; ADR-051, ADR-052 et ADR-053 ;
  `docs/adr/TEMPLATE.md` ; rapport T-010 ; corpus réel explicitement fourni ;
  espaces `data/environments/test` et `docs/evaluation/m014`.
- Commandes de validation : tests unitaires ciblés du manifeste, des
  checkpoints, des agrégats et du verdict ; tests d'acceptation ciblés du point
  d'entrée sans lancer la charge ; `uv run --locked m014-local-load`, exécuté
  une seule fois au jalon de qualification ;
  `uv run --locked gate --scope governance` ;
  `uv run --locked gate --scope m014_local_qualification` ;
  `uv run --locked gate --scope m014_local_qualification --live`.
  L'orchestrateur seul exécute ensuite l'unique gate globale de clôture du
  candidat final.
- Commit RED :
  `test(m014-qualification): exiger campagne cent pdf et verdict`.
- Commit GREEN :
  `feat(m014-qualification): publier charge locale et cloturer ADR-052`.
