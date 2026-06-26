# T-001 - Vérifier et rétablir la précondition GREEN M-004

## Milestone
- Nom: M-004 - Version canonique publiée.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, livrables M-004, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 5, 12, 14, 17, 19, 20 et 21.
- Objectif métier: démarrer la publication de versions canoniques uniquement depuis une base validée, avec M-003 présent dans `master` et sans gate rouge héritée.

## Contexte DDD
- Domaine: gouvernance d'exécution du traitement des sources.
- Bounded context: transverse, avec précondition pour `SP`.
- Objectif métier: prouver que les capacités M-000 à M-003 sont disponibles avant de convertir et publier une source canonique.
- Langage ubiquitaire: précondition GREEN, milestone amont, branche courante, `master`, gate `test`, gate `lint`, rapport de précondition.
- Invariants critiques: M-000, M-001, M-002 et M-003 doivent être visibles dans `master`; un test RED existant bloque M-004; une précondition de milestone clôturé ne doit pas imposer silencieusement une ancienne branche de travail.
- Garde-fous: ne pas ignorer `tests/m003/validate_m003_precondition_acceptance.ps1`; ne pas supprimer une gate pour obtenir GREEN; ne pas créer de contournement local non tracé.

## Blocages Ou Préconditions
- État GREEN/RED connu: `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1` est GREEN; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1` est RED sur `tests/m003/validate_m003_precondition_acceptance.ps1` car `scripts/validate_m003_precondition.ps1` attend `codex/milestone-m003-source-routee` alors que la branche courante est `master`.
- Présence des milestones amont dans master: M-000, M-001, M-002 et M-003 sont présents dans `master` après `git fetch origin --prune`.
- Décisions manquantes: aucune ADR si la correction rend seulement la précondition post-merge explicite; une ADR est requise si la stratégie de gate de milestone change structurellement.
- Risques: masquer un RED historique; rendre les préconditions dépendantes d'un nom de branche obsolète; démarrer M-004 sans preuve que M-003 est accepté dans `master`.

## Tâches
### T-001 - Vérifier et rétablir la précondition GREEN M-004
- But métier: garantir que la publication canonique M-004 démarre depuis une base gouvernée et vérifiable.
- Portée DDD: validation de précondition transverse, présence des milestones amont dans `master`, rapport de précondition M-004 et correction explicite du RED de précondition M-003 post-merge.
- Scénario BDD:
  - Given M-000, M-001, M-002 et M-003 sont présents dans `master`.
  - When les gates de précondition M-004 sont exécutées depuis la base courante.
  - Then M-004 ne peut commencer que si `test`, `lint`, la traçabilité, les ADR, les frontières d'architecture et les preuves M-003 sont GREEN sans dépendre d'une ancienne branche M-003.
- Tests d'acceptation à écrire: un test `tests/m004/validate_m004_precondition_acceptance.ps1` qui échoue tant que M-003 n'est pas vérifié dans `master` et tant que le RED de précondition M-003 post-merge reste présent.
- Tests unitaires à écrire: tests du validateur de précondition pour milestone amont absent, divergence `master`/`origin/master`, branche courante autorisée explicitement, gate RED conservée et rapport hors dépôt refusé.
- Implémentation attendue: créer `scripts/validate_m004_precondition.ps1`, produire `docs/governance/m004_precondition_green.md`, corriger le validateur ou l'enrôlement M-003 pour que l'état post-merge soit explicite, puis rétablir `scripts/test.ps1` et `scripts/lint.ps1` en GREEN.
- Invariants et garde-fous: aucun test supprimé sans remplacement; aucune branche implicite; aucun rapport généré hors dépôt; aucun statut GREEN si une gate échoue.
- Dépendances: `master`; `origin/master`; `docs/tasks/milestone_003`; `scripts/test.ps1`; `scripts/lint.ps1`; `scripts/validate_m003_precondition.ps1`.
- Commandes de validation: `git fetch origin --prune`; `git ls-tree -r --name-only master -- docs/tasks/milestone_000 docs/tasks/milestone_001 docs/tasks/milestone_002 docs/tasks/milestone_003`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m004\validate_m004_precondition_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m004): couvrir la precondition green de version canonique`.
- Commit GREEN: `test(m004): retablir la precondition green avant version canonique`.
