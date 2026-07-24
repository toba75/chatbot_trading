# P-001 - Vérifier la précondition GREEN du pipeline local

## Milestone

- Nom : M14-local-pipeline - Pipeline documentaire local distribué.
- Source : `docs/specs/plan_distribution.md`, sous-milestone
  `M14-local-pipeline` ; plan d'implémentation, section homonyme.
- Objectif métier : établir que le fan-out documentaire peut commencer sur un
  socle M14-distribution-core réellement GREEN et sur une configuration locale
  conforme au contrat d'un slot Granite par worker.

## Contexte DDD

- Domaine : traitement documentaire local et plateforme d'exécution.
- Bounded contexts : Source Processing (SP), Knowledge Access (KA) et module
  technique `platform`, sans transfert de propriété entre eux.
- Objectif métier : séparer les défauts amont des régressions que pourrait
  introduire le pipeline distribué.
- Langage ubiquitaire : précondition GREEN, traitement documentaire, résultat
  de page, claim fenced, slot Granite, version canonique, projection locale.
- Invariants critiques : `M14-distribution-core` est présent et GREEN dans
  `master` ; ADR-051 acceptée n'est pas réécrite ; chaque worker déclare une
  concurrence Granite égale à un ; aucune implémentation T-005 à T-008 ne
  commence sur une gate RED.
- Garde-fous : aucun RED n'est masqué, aucun fichier local ignoré n'est commité,
  aucune empreinte de document n'est changée sans test ; le sous-agent reste
  sur les tests et scopes ciblés et transmet ses preuves à l'orchestrateur.

## Blocages Ou Préconditions

- État GREEN/RED connu : au prévol du 2026-07-24, `uv run --locked gate`
  exécute 465 nœuds et termine `PARTIAL RED`. Le premier RED est
  `test.m004.validate-granite-gemma-recovery-unit` : le fichier local ignoré
  `config/application.yaml` porte `services.workers.granite_concurrency: 2`,
  alors que `config/application.schema.json` impose la constante `1`.
- État du scope amont : `uv run --locked gate --scope
  m014_distribution_core` exécute 36 nœuds et termine `PARTIAL RED` sur
  `test.m014-distribution-core.validate-distribution-decision-unit` avec
  `M014_DISTRIBUTION_ADR_051_CHANGED`. L'empreinte SHA-256 observée d'ADR-051
  est `2e81990a61b956f63f903b671dcf64acd494e90ad856f4130d67a8d07003d6e1`,
  tandis que `ost_gate/m014_distribution_core.py` attend encore
  `70d219179c703b36b44b877cace124e6aa671364e857a06f411c05c89d18183d`.
- Présence des milestones amont dans master : `master` et `origin/master`
  pointent sur `665e2ae8f`, merge de M14-distribution-core ; M-013, ses
  sous-milestones applicables et `docs/tasks/milestone_014-distribution-core`
  sont visibles depuis `master`.
- Décisions manquantes : aucune pour corriger les deux incohérences ; ADR-052
  remplace déjà partiellement ADR-051 pour M-014. Toute modification du sens
  accepté d'ADR-051 exigerait en revanche une nouvelle ADR.
- Risques : traiter un fichier local comme une preuve versionnée, mettre à jour
  l'empreinte sans vérifier le lien réciproque ADR-051/ADR-052, ou démarrer un
  test RED du pipeline alors que le scope amont reste RED.

## Tâches

### P-001 - Vérifier la précondition GREEN du pipeline local

- But métier : obtenir une baseline reproductible où les contrats hérités et
  la capacité locale sont cohérents avant le premier changement du pipeline.
- Portée DDD : gouvernance de milestone, configuration locale M13, décision
  ADR-052 et scope `m014_distribution_core` ; aucun comportement T-005 à T-008.
- Scénario BDD :
  - Given `master` contient le merge de M14-distribution-core, un fichier local
    de configuration explicitement choisi et les ADR-051/ADR-052 réciproques.
  - When la configuration locale est réalignée sur un slot Granite par worker,
    puis le validateur ADR-051 et les gates amont sont exécutés.
  - Then le scope `m014_distribution_core` est GREEN, le fichier ignoré reste
    non versionné et aucune ADR acceptée n'a changé de sens ; l'orchestrateur
    conserve seul la responsabilité de la preuve globale finale.
- Tests d'acceptation à écrire : aucun test fonctionnel du pipeline ; conserver
  les deux RED observés comme preuves, puis vérifier le scope M14-core après
  correction. Si le validateur d'ADR ne couvre pas le lien
  réciproque accepté, ajouter un test ciblé qui exige les métadonnées et notes
  actuelles d'ADR-051 sans figer un contenu étranger à la décision.
- Tests unitaires à écrire : mettre à jour ou compléter le test du validateur
  M14-core pour accepter exactement l'ADR-051 réciproque actuelle et refuser
  toute autre mutation ; ne créer aucun test artificiellement RED pour le
  fichier local ignoré.
- Implémentation attendue : réaligner explicitement
  `config/application.yaml` avec la configuration de profil choisie sans le
  commiter ; corriger la preuve versionnée dans `ost_gate/m014_distribution_core.py`
  et son test, sans modifier ADR-051 ni ADR-052 ; consigner les nouvelles sorties
  terminales et références Git dans `journal.md`.
- Invariants et garde-fous : `granite_concurrency` reste égal à un par worker ;
  le quota global reste deux ; l'empreinte ne remplace pas la validation
  sémantique ; aucun fallback CPU, fichier de configuration alternatif ou
  exclusion de test n'est introduit.
- Dépendances : `AGENTS.md` ; `docs/tasks/README.md` ; M-013 ;
  M14-distribution-core ; ADR-051 ; ADR-052 ; configuration M13-environments.
- Commandes de validation : `git fetch origin --prune` ;
  `git rev-list --left-right --count master...origin/master` ;
  `git ls-tree -r --name-only master -- docs/tasks/milestone_013 docs/tasks/milestone_014-distribution-core docs/adr app gate_tests` ;
  `git check-ignore -v config/application.yaml` ;
  `uv run --locked gate --scope governance` ;
  `uv run --locked gate --scope m004` ;
  `uv run --locked gate --scope m014_distribution_core`. Le sous-agent exécute
  uniquement les tests et scopes ciblés. L'orchestrateur exécute exactement une
  gate globale de clôture avec un timeout de 3 600 000 ms, attend le même cell ID
  après tout yield ou timeout d'affichage et ne la considère jamais relancée.
- Commit RED : aucun commit RED artificiel ; les deux échecs de prévol sont les
  RED existants à fermer avant le TDD du pipeline.
- Commit GREEN : `fix(m014-core): realigner preuve reciproque ADR-051` ; la
  correction du fichier local ignoré ne produit aucun commit.
