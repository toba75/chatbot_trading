# Journal M-008

## Planification initiale

- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, milestone `M-008 - Conversation produit`.
- Dépendance amont: M-007, présent dans `master` au commit `e211a7ea27050a1226203cec2529c217f9f7cfc4` après `git fetch origin --prune` et réalignement de `master` par `git fetch origin master:master`.
- Précondition observée pendant la planification: `scripts/test.ps1` est RED sur `tests/m003/validate_m003_precondition_acceptance.ps1`, car `scripts/validate_m003_precondition.ps1` refuse la branche `codex/plan-milestone-m008-conversation-produit`; `scripts/lint.ps1` est GREEN avec `16 validation(s), 0 test(s)`; `scripts/validate_task_system.ps1` est GREEN avec `8 milestone(s), 77 tâche(s) contrôlée(s)` avant création de M-008; `git diff --check` est GREEN.
- Découpage retenu: précondition, spécification CV, conversations et tours append-only, snapshot de contexte sans preuve factuelle, résolution des références de suivi, routage de mode justifié, revalidation RA des assertions historiques réutilisées et rattachement des réponses vérifiées, présentation produit des citations et statuts depuis un DTO public RA distinct de `VerifiedResearchOutcome`, endpoints internes de conversation, endpoint compatible `/v1/chat/completions`, puis traçabilité et métriques.
- ADR: aucune nouvelle ADR planifiée à ce stade; les tâches appliquent les ADR existantes et exigent une nouvelle ADR si une décision structurante change la politique de branche et préconditions, la rétention conversationnelle, la compatibilité chat publique, le contrat `VerifiedResearchOutcome` ou l'observabilité persistante.

## T-001 - Précondition GREEN M-008

- Scénario BDD: Given M-007 est présent dans `master`; When les gates de précondition M-008 sont exécutées sur une branche M-008; Then M-008 ne peut commencer que si les validateurs amont acceptent explicitement la branche aval et si `test`, `lint`, traçabilité, ADR et frontières d'architecture sont GREEN.
- Vérification initiale: `git fetch origin --prune` GREEN; `git ls-tree -r --name-only master -- docs/tasks/milestone_007 docs/specs/m007_reponse_documentaire_verifiee.md scripts tests/m007` GREEN; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1` RED sur `tests/m003/validate_m003_precondition_acceptance.ps1`, car la branche M-008 courante n'est pas encore autorisée par les validateurs amont.
- ADR: non requise. La tâche n'introduit pas une nouvelle politique durable; elle applique la politique existante de précondition explicite au jalon aval M-008.
- RED: `a148e192 test(m008): couvrir la precondition green conversation`.
- GREEN: `tests/m008/validate_m008_precondition_unit.ps1` GREEN; `tests/m008/validate_m008_precondition_acceptance.ps1` GREEN; `scripts/validate_m008_precondition.ps1 -Path .\docs\governance\m008_precondition_green.md` GREEN avec `Gate test GREEN: 16 validation(s), 150 test(s).` et `Gate lint GREEN: 16 validation(s), 0 test(s).`
- Rapport produit: `docs/governance/m008_precondition_green.md`.

## T-002 - Publier la spécification de conversation produit

- Scénario BDD: Given la mission M-008 est de permettre une conversation suivie sans preuve historique implicite; When la spécification de conversation produit est publiée; Then chaque comportement CV nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.
- ADR: non requise. La spécification M-008 applique ADR-010, DDD-ADR-001, DDD-ADR-002, DDD-ADR-003, DDD-ADR-007 et DDD-ADR-008 sans modifier leur sens.
- RED: `7293b1f3 test(m008): couvrir la specification conversation produit`.
- GREEN: `tests/m008/validate_m008_specification_acceptance.ps1` GREEN; `tests/m008/validate_m008_specification_unit.ps1` GREEN; `scripts/validate_m008_specification.ps1` GREEN; `scripts/validate_traceability.ps1` GREEN avec `84 exigence(s) contrôlée(s)`; `scripts/lint.ps1` GREEN avec `17 validation(s), 0 test(s)`; `scripts/test.ps1` GREEN après relance longue avec `17 validation(s), 158 test(s)`.
- Garde-fous explicités: historique conversationnel non probant, revalidation RA obligatoire des assertions historiques sans `VerifiedAnswerVersion`, DTO public RA distinct de `VerifiedResearchOutcome`, absence de fallback de mode et archivage CV sans cascade hors CV.

## T-003 - Créer les conversations et tours append-only

- Scénario BDD: Given une conversation active existe pour un mandat documentaire; When l'utilisateur ajoute un message dans cette conversation; Then un nouveau tour append-only est créé avec son ordre, son horodatage et son appartenance à la conversation sans modifier les tours précédents.
- ADR: non requise. La tâche introduit des repositories mémoire stricts CV sans nouvelle persistance durable ni politique de purge.
- RED: `7b8a5470 test(m008): couvrir conversations tours append only`, avec `ModuleNotFoundError` attendu sur `app.conversation.adapters.in_memory_conversation_repository`.
- GREEN ciblé: `tests/m008/validate_conversation_turn_append_only_acceptance.ps1` GREEN; `tests/m008/validate_conversation_turn_append_only_unit.ps1` GREEN; `scripts/validate_architecture_boundaries.ps1 -AppRoot .\app -ContextRegistryPath .\app\context_registry.json -SpecificationPath .\docs\specs\m001_frontieres_ddd_contrats_publies.md` GREEN avec `130 fichier(s), 734 import(s) contrôlé(s)`.
- Garde-fous implémentés: identifiants explicites `CONV-*` et `TURN-*`, aucune conversation anonyme, tours immuables, ordre strict par conversation, refus des tours orphelins et refus d'ajout sur conversation archivée.

## T-004 - Compacter le contexte sans preuve factuelle

- Scénario BDD: Given une conversation contient une préférence utilisateur et une réponse précédente vérifiée; When le contexte conversationnel est compacté; Then le snapshot conserve la préférence et la référence vérifiée sans recopier l'historique comme preuve factuelle.
- ADR: non requise. La tâche applique DDD-ADR-003 et DDD-ADR-007 sans décider une nouvelle politique durable de rétention, chiffrement ou purge.
- RED: `ba2a91a1 test(m008): couvrir snapshot contexte sans preuve`, avec `ModuleNotFoundError` attendu sur `app.conversation.adapters.in_memory_context_store`.
- GREEN ciblé: `tests/m008/validate_conversation_context_snapshot_acceptance.ps1` GREEN; `tests/m008/validate_conversation_context_snapshot_unit.ps1` GREEN.
- Gates: `scripts/lint.ps1` GREEN avec `17 validation(s), 0 test(s)`; `scripts/test.ps1` GREEN avec `17 validation(s), 162 test(s)`; `git diff --check` GREEN.
- Garde-fous implémentés: snapshot immuable, mandat actif obligatoire, préférences séparées des références vérifiées, assertions historiques sans `VerifiedAnswerVersion` conservées pour revalidation, clés sensibles refusées (`raw_turns`, `prompt`, `answer_text`, `document_text`) et store mémoire sans mutation silencieuse.

## T-005 - Résoudre une référence de suivi en question autonome

- Scénario BDD: Given une conversation portant sur le volatility targeting; When l'utilisateur écrit `compare-la maintenant à Kelly`; Then une question autonome mentionnant explicitement le volatility targeting et Kelly est produite avant tout appel à RA.
- ADR: non requise. La tâche introduit un port `QuestionResolver` CV déterministe local, sans rendre obligatoire un modèle externe ni changer une décision structurante existante.
- RED: `33d93245 test(m008): couvrir resolution reference suivi`, avec `ModuleNotFoundError` attendu sur `app.conversation.application.resolve_followup_question`.
- GREEN ciblé: `tests/m008/validate_followup_question_resolution_acceptance.ps1` GREEN; `tests/m008/validate_followup_question_resolution_unit.ps1` GREEN.
- Gates: `scripts/lint.ps1` GREEN avec `17 validation(s), 0 test(s)`; `scripts/test.ps1` GREEN avec `17 validation(s), 164 test(s)`; `git diff --check` GREEN.
- Garde-fous implémentés: référence pronominale refusée sans antécédent unique, statut `CLARIFICATION_REQUIRED` sans payload aval en cas d'ambiguïté, question autonome avant routage, conservation du mandat actif, des documents sélectionnés et des références vérifiées, événement sans message brut.

## T-006 - Sélectionner un mode conversationnel visible et justifié

- Scénario BDD: Given une question autonome demande de tester une stratégie avec des coûts doublés; When le mode conversationnel est sélectionné; Then le tour enregistre `BACKTEST` avec une justification et ne bascule pas silencieusement vers `CHAT_DOCUMENTAIRE`.
- ADR: non requise. La tâche applique ADR-010 et DDD-ADR-007 sans créer un nouveau contrat externe ni exécuter les contextes aval SD ou EX.
- RED: `320ebd42 test(m008): couvrir routage modes conversation`, avec `ModuleNotFoundError` attendu sur `app.conversation.application.select_mode`.
- GREEN ciblé: `tests/m008/validate_conversation_mode_routing_acceptance.ps1` GREEN; `tests/m008/validate_conversation_mode_routing_unit.ps1` GREEN.
- Gates: `scripts/lint.ps1` GREEN avec `17 validation(s), 0 test(s)`; `scripts/test.ps1` GREEN avec `17 validation(s), 166 test(s)`; `git diff --check` GREEN.
- Garde-fous implémentés: modes explicites `CHAT_DOCUMENTAIRE`, `RECHERCHE_APPROFONDIE`, `COMPARAISON`, `CONCEPTION_STRATEGIE`, `CALCUL`, `BACKTEST` et `CLARIFICATION_INTERNE`, mode forcé validé, mode indisponible refusé, justification obligatoire, aucune bascule documentaire implicite.

## T-007 - Revalider une assertion historique et rattacher la réponse

- Scénario BDD: Given une réponse précédente contient une assertion sans `VerifiedAnswerVersion`; When l'utilisateur réutilise cette assertion dans un nouveau tour documentaire; Then CV appelle `ResearchFacade` pour rechercher et vérifier à nouveau l'assertion avant de rattacher le résultat public RA au tour.
- ADR: non requise. La tâche applique DDD-ADR-003, DDD-ADR-007 et DDD-ADR-008 sans modifier `VerifiedResearchOutcome` ni introduire un accès au stockage RA.
- RED: `e50a51ce test(m008): couvrir revalidation historique`, avec module `answer_conversation_turn` absent côté CV.
- GREEN ciblé: `tests/m008/validate_verified_result_reuse_acceptance.ps1` GREEN; `tests/m008/validate_verified_answer_attachment_unit.ps1` GREEN; `scripts/validate_architecture_boundaries.ps1 -AppRoot .\app -ContextRegistryPath .\app\context_registry.json -SpecificationPath .\docs\specs\m001_frontieres_ddd_contrats_publies.md` GREEN avec `139 fichier(s), 807 import(s) contrôlé(s)`.
- Gates: `scripts/lint.ps1` GREEN avec `17 validation(s), 0 test(s)`; `scripts/test.ps1` GREEN avec `17 validation(s), 168 test(s)`; `git diff --check` GREEN.
- Garde-fous implémentés: assertion historique non versionnée envoyée à RA, port `ResearchFacade` sans import d'adaptateur RA interne, rattachement unique par tour, statut RA conservé, version `ANS-*@[n]` conservée, validation structurelle de `VerifiedResearchOutcome` sans enrichissement par `answer_text` ou `citations`.
