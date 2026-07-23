# Journal M14-distribution-core - Socle de distribution locale durable

## Prévol de planification

- Date : 2026-07-23.
- Branche de planification : `codex/m14-distribution-core`.
- Base contrôlée : `master` et `origin/master` à
  `c67e8aebb` après `git fetch origin --prune`.
- État initial du worktree principal : propre avant création des tâches.
- Présence amont : les têtes contrôlées de M-013 principal,
  M13-environments et M13-FastAPI sont ancêtres de `master`; les dossiers de
  tâches M-000 à M-013 et leurs artefacts canoniques sont visibles depuis
  `master`.
- Premier prévol détaché : `uv run --locked gate` a terminé `PARTIAL RED` sur
  `test.m004.validate-granite-gemma-recovery-unit` avec
  `CONFIG_FILE_UNREADABLE` parce que le worktree propre ne contenait pas le
  fichier local ignoré `config/application.yaml`.
- Qualification du prévol : le fichier local existant a été relié temporairement
  au worktree sans être versionné ni affiché; la même commande a ensuite exécuté
  451 nœuds exactement une fois et terminé avec le code 0,
  `PARTIAL GREEN: offline`.
- Conclusion : M-013 est présent et la baseline logicielle de `master` est
  GREEN pour planifier M14-distribution-core. Le fichier local qualifié reste
  requis pour reproduire la gate complète dans un worktree détaché.

## Commits techniques déjà présents sur la branche

- `436c682e9` : test RED exigeant Granite sur CUDA selon ADR-051.
- `89a73a075` : implémentation GREEN de Granite sur `cuda:0` selon ADR-051.
- `975a12c27` : limite des workers documentaires à 2 Gio.
- `dad3ec98e` : recadrage documentaire de M-014 sur deux workers locaux.
- Ces commits ne servent pas à déclarer M-013 présent dans `master`. Ils forment
  les prérequis techniques et documentaires propres à la branche de
  planification M14.

## Sources canoniques consultées

- `AGENTS.md` et `docs/tasks/README.md`.
- `docs/specs/plan_implementation_milestones_workstreams.md`, sections M-014 et
  M14-distribution-core.
- `docs/specs/plan_distribution.md`, notamment les invariants, le modèle
  d'exécution, DIST-001 à DIST-003, T-001 à T-004, les tests, migrations et
  risques.
- `docs/specs/m004_version_canonique_publiee.md` et
  `docs/specs/m013_environments_environnements_explicites.md`.
- ADR-021, ADR-024, ADR-025, ADR-040, ADR-042, ADR-046 et ADR-051.
- Contrats et runtime existants : `app/contracts/technical_jobs.py`,
  `app/platform/job_runtime`, domaine pagewise M-004, limiteurs Docling/Granite,
  persistance SP, configuration stricte et composition des environnements.
- Migrations PostgreSQL 001 à 021 et tests portés M-004/M13-environments.

## Synthèse DDD

- Source Processing reste propriétaire de `DocumentProcessingRun`, des routes,
  résultats de pages, artefacts et de la publication canonique.
- `platform` reste propriétaire de la file technique, des claims fenced et de
  la capacité d'exécution locale.
- Les deux workers documentaires sont des replicas généralistes identiques ; un
  job déclare une capacité requise mais ne cible jamais une instance.
- L'effet persistant doit être exactement une fois malgré une exécution au
  moins une fois ; toutes les écritures post-claim transportent génération et
  token.
- PostgreSQL est l'autorité du quota Granite. Les sémaphores M-004 existants
  restent des limites de processus, pas la preuve du plafond global.
- L'environnement `test` porte les preuves fonctionnelles ; `development` et
  `production` reçoivent uniquement des contrôles structurels pour cette
  tranche.

## Découpage initial

- T-001 vérifie la précondition GREEN, inventorie l'existant et publie un
  baseline comparable à un puis deux workers.
- T-002 crée ADR-052 et décide le fan-out local, le quota PostgreSQL, le cycle de
  vie des slots et le fencing.
- T-003 publie les contrats versionnés de jobs, résultats, artefacts, erreurs et
  configuration locale stricte.
- T-004 ajoute les migrations ascendantes et implémente les deux slots Granite
  fenced avec preuve PostgreSQL réelle.
- Les jobs de pages, leur exécution métier, l'assemblage canonique et la
  projection restent réservés à M14-local-pipeline.

## Règles d'exécution

- Chaque tâche commence par la vérification GREEN pertinente.
- Le scénario BDD et le test d'acceptation échouant pour la bonne raison sont
  commités avant le code applicatif.
- Le commit RED ne contient aucune implémentation ; le commit GREEN contient
  uniquement le comportement strict nécessaire.
- Aucune valeur par défaut, aucun fallback silencieux, aucune conversion
  ambiguë et aucun état synthétique ne sont admis.
- Toute évolution de la décision structurante ADR-052 crée une ADR remplaçante
  et met à jour `docs/adr/index.md`.

## Risques ouverts avant implémentation

- Le mécanisme PostgreSQL exact des deux slots doit être choisi par ADR-052.
- Les noms et propriétaires des tables de résultats de pages doivent respecter
  les frontières ADR-024 et ADR-025.
- La capacité Granite actuelle est bornée en mémoire dans chaque processus ;
  elle ne prouve pas encore le plafond global entre replicas.
- Les mesures réelles doivent conserver la même page, les mêmes actifs, la même
  image et les mêmes limites pour éviter un faux gain de débit.
- Les mentions historiques de flotte CPU multiarchitecture dans ADR-051 ne
  doivent pas être modifiées silencieusement ; ADR-052 doit les superséder de
  façon bornée pour M-014 tout en conservant la décision CUDA stricte.

## 2026-07-23 - T-001 baseline locale reproductible

- Précondition GREEN : `uv run --locked gate` a exécuté 452 nœuds exactement
  une fois et terminé avec le code 0, `PARTIAL GREEN: offline`, avant toute
  modification T-001.
- Scénario BDD et portée de gate ajoutés sous
  `gate_tests/ported/tests/m014_distribution_core/`, avec la précondition
  `gate_tests/preconditions/test_m014_distribution_core.py` et le scope
  `m014_distribution_core` enregistré dans `gate.toml`.
- RED utile : le scope a terminé `PARTIAL RED` et Pytest a refusé la collecte
  avec `ModuleNotFoundError: ost_gate.m014_distribution_core`. Commit RED
  `c0a136bcfb5c5f51c0d9b31f627e0a96ff13ee35`.
- Validateur strict : `ost_gate/m014_distribution_core.py` refuse preuve
  synthétique, champ ou commit absent, durée non positive, hash invalide,
  sorties divergentes, limite autre que 2 Gio, preuve CUDA absente et capacité
  `ssh`, Kamal, Colima, `arm64` ou worker distant active.
- Preuve structurée :
  `docs/evaluation/m014/distribution_core_baseline.json` ; compte rendu :
  `docs/governance/m014_distribution_core_baseline.md`.
- Charge mesurée : page 2 de la fixture M-013, route `MIXED_PAGEWISE`, image
  scellée `sha256:2af4bfdfd1b7c6f4c43896fb2767cfe2e87646dcab84b5569f5fd4e3c84f7bfd`,
  actifs Granite au manifeste
  `575eb811c47bb48a6401006bdde1084605ab4f6e158901651f9dbfcbc659e368`.
- Un worker : 24,955 s, pic RAM 1 872 605 741 octets, pic VRAM 1 396 Mio,
  pic GPU 34 %, deux items `granite_docling`.
- Deux workers : 25,539 s pour deux pages concurrentes, pics RAM
  1 871 531 999 et 1 464 583 848 octets, pic VRAM total 2 719 Mio, pic GPU
  8 %, deux items par réponse.
- Les trois sorties possèdent le même SHA-256
  `21eb4e0b719b644bca4e193546cfc53b6be7666f732200ec9da0e44d921a2977`.
  Le débit dérivé du lot atteint `1,954x` par rapport à deux durées unitaires.
- Résultats négatifs conservés : deux courses du collecteur `docker stats`
  sans preuve retenue ; une conversion réussie en 24,601 s rejetée parce que
  son SHA-256 de réponse était absent.
- Inventaire observé : contrats `app/contracts/technical_jobs.py`, runtime
  `app/platform/job_runtime`, worker SP, tables de jobs, outbox, runs,
  progression et routes, migrations `003`, `008`, `012`, `014`, `020`, `021`,
  configurations et volumes du profil `test`.
- ADR consultées : ADR-025, ADR-040, ADR-042, ADR-046 et ADR-051. ADR nouvelle :
  non requise ; ADR-052 demeure réservée à T-002.
- Validations GREEN : Pytest ciblé 2/2 ; scope `m014_distribution_core` 26
  nœuds ; `governance` 25 nœuds ; `m004` 45 nœuds ; `m013_environments` 49
  nœuds ; aucune absence, surprise ou duplication.
- Gate canonique finale : 455 nœuds exécutés exactement une fois, code 0,
  aucune absence, surprise ou duplication, `PARTIAL GREEN: offline`.
- Lint ciblée : Ruff GREEN sur le validateur, les tests et la précondition.
- Commit GREEN : `fd30fcdebd2f8c554615fed2d91535d1c630c343`.
