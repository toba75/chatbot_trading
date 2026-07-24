# T-010 - Qualifier le parcours réel à deux workers

## Milestone

- Nom : M14-local-qualification - Qualification de capacité locale.
- Source : `docs/specs/plan_distribution.md`, T-010 ; scénarios DIST-001 à
  DIST-006.
- Objectif métier : prouver sur un PDF réel que deux workers locaux traitent
  simultanément des pages, qu'une panne est reprise sous fencing et que le
  document canonique puis sa projection restent identiques au contrôle
  mono-worker.

## Contexte DDD

- Domaine : qualification fonctionnelle du traitement documentaire distribué.
- Bounded contexts : SP orchestre le manifeste, les résultats, la progression
  et la publication ; `platform` distribue, réclame et borne Granite ; KA
  projette uniquement la publication canonique complète.
- Objectif métier : établir une preuve reproductible du gain de concurrence et
  de la sûreté de reprise sur le parcours produit réel.
- Langage ubiquitaire : exécution de contrôle mono-worker, exécution à deux
  workers, chevauchement de pages, troisième page en attente, panne injectée,
  expiration, reprise fenced, version canonique de référence, projection de
  référence, verdict fonctionnel et capacitaire.
- Invariants critiques : la configuration déclare toujours deux replicas ; le
  contrôle mono-worker est obtenu par drainage explicite d'un replica, pas par
  une configuration non conforme ; chaque page porte son worker, ses horaires,
  son claim et, si Granite, son slot ; aucun ancien détenteur ne publie après
  reprise.
- Garde-fous : vrai PDF versionné et vrai parcours HTTP vers PostgreSQL,
  workers, convertisseurs, artefacts, Qdrant et lecture publique ; aucun mock,
  stub, résultat préchargé, appel direct au cas d'usage ou fallback ; aucun
  seuil dérivé d'une seule mesure.

## Blocages Ou Préconditions

- État GREEN/RED connu : T-009 GREEN ; inspection, drainage et redémarrage
  ciblé sont disponibles et qualifiés avant toute panne injectée.
- Présence des milestones amont dans master : la fixture réelle
  `data/corpus/ostrading-environment-qualification-5-pages.pdf`, ses cinq routes,
  le pipeline à la page, l'assemblage, la projection et les commandes de profil
  `test` sont disponibles.
- Décisions manquantes : P-002 doit fixer un nombre explicite de répétitions et
  la règle statistique. Le plan exige au minimum trois répétitions de contrôle
  et trois à deux workers ; modifier cette règle après observation invalide la
  campagne et exige une nouvelle exécution complète.
- Risques : mesurer deux processus sans chevauchement réel, arrêter un worker
  avant son claim, comparer des documents ou configurations différents,
  ignorer une troisième page Granite, ou présenter une gate PostgreSQL comme
  preuve CUDA.

## Tâches

### T-010 - Qualifier le parcours réel à deux workers

- But métier : publier un rapport live qui démontre concurrence, reprise,
  fidélité documentaire, projection et limites de ressources sur la RTX 4090.
- Portée DDD : orchestrateur de qualification du profil `test`, commandes T-009,
  preuve d'affectation et de chevauchement, injection de panne, lecture des
  autorités persistées, comparaison canonique/projection et rapport signé par
  ses empreintes.
- Scénario BDD :
  - Given deux workers locaux `READY`, deux slots Granite sur `cuda:0` et le PDF
    réel de qualification dont le manifeste contient plusieurs pages Granite.
  - When un contrôle est exécuté avec un worker drainé, puis plusieurs runs à
    deux workers sont exécutés et une instance détenant un claim-slot est
    arrêtée avant sa complétion.
  - Then deux pages se chevauchent réellement sur deux workers, une troisième
    attend sans CPU ni changement de route, l'autre worker reprend la page avec
    de nouveaux tokens, et les empreintes canoniques et de projection égalent
    celles du contrôle.
- Tests d'acceptation à écrire : test du point d'entrée UV dédié et de son
  rapport ; preuve HTTP réelle de soumission et de progression ; affectations
  distinctes et intervalle de chevauchement strictement positif ; deux slots
  au plus, troisième page en attente ; arrêt non gracieux de la cible après
  claim ; expiration PostgreSQL, reprise et refus de l'ancien token ; une seule
  publication et une seule projection `SEARCHABLE` ; absence de fuite vers
  `development`/`production` ; erreurs terminales si Docker, CUDA, métrique,
  artefact ou dépendance manque.
- Tests unitaires à écrire : validation du protocole et du rapport ; calcul des
  intervalles, médianes, débit et attente ; comparaison des identités et
  empreintes ; refus d'une répétition absente, d'une mesure partielle, d'un
  worker identique sur les deux pages, d'une chronologie sans chevauchement,
  d'un token réutilisé et d'un pic RAM supérieur ou égal à 2 Gio.
- Implémentation attendue : créer un point d'entrée UV court et dédié à la
  qualification M14 locale, lié exclusivement au profil `test` versionné ;
  démarrer la pile réelle vide ; exécuter les contrôles et runs prévus ; utiliser
  T-009 pour drainer et injecter la panne ciblée ; capturer identités, versions,
  horaires, routes, claims, slots, RAM, GPU, VRAM, puissance, durées et attentes ;
  publier la preuve structurée sous `docs/evaluation/m014/` et sa synthèse dans
  `docs/governance/`, puis compléter la traçabilité et `journal.md`.
- Invariants et garde-fous : les 2 Gio sont un plafond par conteneur ; un OOM
  rend le run RED ; les mesures mono/deux workers utilisent le même PDF, les
  mêmes actifs, la même image, la même configuration et la même révision ; les
  valeurs historiques de M14-core sont comparatives, jamais substituées aux
  nouvelles répétitions.
- Dépendances : T-009 ; ADR-050, ADR-051 et ADR-052 ;
  `docs/evaluation/m014/distribution_core_baseline.json` ;
  `app/platform/test_e2e.py` ; `app/platform/environment_command.py` ;
  `docs/runbooks/distribution_locale.md`.
- Commandes de validation : tests unitaires ciblés du protocole et du rapport ;
  tests d'acceptation ciblés du point d'entrée ;
  `uv run --locked gate --scope m014_local_qualification` ;
  `uv run --locked m014-local-qualification` ;
  `uv run --locked gate --scope m014_local_qualification --live`.
  Le sous-agent ne lance ni la gate globale ni la campagne de cent PDF.
- Commit RED :
  `test(m014-qualification): exiger parcours reel deux workers`.
- Commit GREEN :
  `feat(m014-qualification): qualifier parcours reel deux workers`.
