# T-001 - Vérifier la précondition GREEN de M-002

## Milestone
- Nom: M-002 - Plateforme locale sûre.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, section `M-002 - Plateforme locale sûre`, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 13, 15, 16, 18, 19, 20 et 21.
- Objectif métier: prouver que la gouvernance, les frontières DDD et les contrats publiés sont GREEN avant de livrer la plateforme locale d'exécution.

## Contexte DDD
- Domaine: gouvernance d'implémentation et socle de plateforme local-first.
- Bounded context: `platform`, avec dépendance transverse vers SP, KA, EG, RA, CV, SD et EX.
- Objectif métier: empêcher que la topologie Docker/Spark, l'outbox, les jobs ou le gateway LLM soient créés sur une base documentaire ou contractuelle déjà RED.
- Langage ubiquitaire: précondition GREEN, plateforme locale sûre, `docker-local`, `spark-inference`, `llm-gateway`, outbox, job idempotent, gate, RED, GREEN.
- Invariants critiques: un RED existant bloque M-002; M-000 et M-001 sont présents dans `master`; un test de plateforme ne doit pas assouplir les frontières DDD M-001.
- Garde-fous: exécuter les gates standard; consigner le RED exact; corriger uniquement la cause vérifiée; ne pas créer de contournement silencieux des validateurs.

## Blocages Ou Préconditions
- État GREEN/RED connu: au 2026-06-25, `.\scripts\test.ps1` est GREEN avec 7 validations et 31 tests; `.\scripts\lint.ps1` est GREEN avec 7 validations.
- Présence des milestones amont dans master: `git fetch origin master:master` a aligné `master` sur `origin/master` à `35a5765`; `M-000` et `M-001` sont visibles dans `master`; `b4c9f9b` est ancêtre de `master`.
- Décisions manquantes: aucune décision structurante nouvelle pour la précondition; ADR-010 gouverne déjà les gates PowerShell.
- Risques: démarrer M-002 depuis une branche M-001 non alignée; ignorer une divergence de `master`; déclarer GREEN sur des tests partiels.

## Tâches
### T-001 - Vérifier la précondition GREEN de M-002
- But métier: établir une preuve de départ fiable avant toute livraison de plateforme locale.
- Portée DDD: gouvernance transverse; aucun comportement de plateforme n'est ajouté avant la preuve GREEN.
- Scénario BDD:
  - Given M-000 et M-001 sont présents dans `master`.
  - When les gates de validation sont exécutées avant la première tâche M-002.
  - Then M-002 peut commencer uniquement si les tests, la lint, la traçabilité, les ADR et les frontières d'architecture sont GREEN.
- Tests d'acceptation à écrire: un test de précondition M-002 qui exécute `scripts/test.ps1` et `scripts/lint.ps1`, vérifie la présence de `docs/tasks/milestone_001` dans `master` et échoue explicitement si une gate est RED.
- Tests unitaires à écrire: tests du validateur de précondition avec `master` absent, milestone amont absent, sortie de gate RED et divergence locale de branche.
- Implémentation attendue: créer le validateur ou rapport de précondition M-002, enregistrer les commandes exécutées et refuser toute suite de tâches si la base n'est pas GREEN.
- Invariants et garde-fous: aucun passage GREEN sans exécuter les commandes; aucun fallback vers une branche remote non fusionnée; aucun try/catch qui masque la commande en échec.
- Dépendances: M-000; M-001; `scripts/test.ps1`; `scripts/lint.ps1`; `scripts/validate_task_system.ps1`; `scripts/validate_traceability.ps1`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`; `git ls-tree -r --name-only master -- docs/tasks/milestone_000 docs/tasks/milestone_001`.
- Commit RED: `test(m002): couvrir la précondition green de plateforme`.
- Commit GREEN: `docs(m002): valider la précondition green de plateforme`.
