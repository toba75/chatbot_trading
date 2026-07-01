# Journal M-007

## Planification initiale

- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, milestone `M-007 - Réponse documentaire vérifiée`.
- Dépendance amont: M-006, présent dans `master` au commit `236c2420a84c0439e8d1c101eb2251ba44069fa9`, identique à `origin/master` après `git fetch origin --prune`.
- Précondition observée pendant la planification: `scripts/test.ps1` a expiré une première fois à 904 secondes puis a conclu GREEN après relance large avec `15 validation(s), 134 test(s)`; `scripts/lint.ps1` GREEN avec `15 validation(s), 0 test(s)`; `scripts/validate_task_system.ps1` GREEN avec `7 milestone(s), 67 tâche(s) contrôlée(s)` avant création de M-007; `git diff --check` GREEN.
- Découpage retenu: précondition, spécification RA, cas de recherche avec mandat, jeu de preuves scellé, contradictions et lacunes, extraction d'assertions, support et citations, abstention pour données actuelles, commande `POST /v1/answer`, puis traçabilité et métriques.
- ADR: aucune nouvelle ADR planifiée à ce stade; les tâches appliquent les ADR existantes et exigent une nouvelle ADR si une décision structurante change le contrat public RA, la politique durable de fraîcheur ou le stockage des preuves.

## Clôture T-001 - précondition GREEN

- Scénario BDD: Given M-006 est publié sur `master`; When la précondition M-007 est exécutée; Then M-007 démarre uniquement depuis une base GREEN vérifiée.
- ADR: non requise; application de `ADR-010` pour les gates PowerShell.
- Commits: RED `4d89af92`; GREEN `b0625a1a`.
- Preuves livrées: `scripts/validate_m007_precondition.ps1`, `tests/m007/validate_m007_precondition_acceptance.ps1`, `tests/m007/validate_m007_precondition_unit.ps1`, `docs/governance/m007_precondition_green.md`.

## Clôture T-002 - spécification RA exécutable

- Scénario BDD: Given la mission M-007; When la spécification RA est publiée; Then les comportements, statuts, ports, erreurs et commandes sont contrôlés par validateur.
- ADR: non requise; application de `ADR-006`, `ADR-010`, `DDD-ADR-003`, `DDD-ADR-005`, `DDD-ADR-007` et `DDD-ADR-008`.
- Commits: RED `1b46bb3c`; GREEN `d9eb0154`.
- Preuves livrées: `docs/specs/m007_reponse_documentaire_verifiee.md`, `scripts/validate_m007_specification.ps1`, `tests/m007/validate_m007_specification_acceptance.ps1`, `tests/m007/validate_m007_specification_unit.ps1`.

## Clôture T-003 - ResearchCase et mandat explicite

- Scénario BDD: Given une question autonome et un mandat explicite; When RA ouvre un ResearchCase; Then le cas est planifié sans historique conversationnel brut.
- ADR: non requise; application de `ADR-010`.
- Commits: RED `a391fe25`; GREEN `801e931b`.
- Preuves livrées: `app/research_answering/domain/research_case.py`, `app/research_answering/application/open_research_case.py`, `tests/m007/validate_research_case_mandate_acceptance.ps1`, `tests/m007/validate_research_case_mandate_unit.ps1`.

## Clôture T-004 - EvidenceSet scellé

- Scénario BDD: Given des preuves candidates et claims vérifiés; When RA collecte puis scelle l'EvidenceSet; Then les citations sont ouvrables et la version est figée.
- ADR: non requise; application de `DDD-ADR-003` et `DDD-ADR-008`.
- Commits: RED `935af98d`; GREEN `7c49ccc4`.
- Preuves livrées: `app/research_answering/domain/evidence_set.py`, `app/research_answering/application/collect_evidence.py`, `tests/m007/validate_evidence_set_sealing_acceptance.ps1`, `tests/m007/validate_evidence_set_sealing_unit.ps1`.

## Clôture T-005 - contradictions et lacunes

- Scénario BDD: Given des claims opposés ou une obligation non couverte; When RA classe les diagnostics; Then les conflits et lacunes restent explicites.
- ADR: non requise; application de `DDD-ADR-005`.
- Commits: RED `ff49620f`; GREEN `ed7e8941`.
- Preuves livrées: `app/research_answering/domain/contradiction_assessment.py`, `app/research_answering/application/classify_contradictions.py`, `tests/m007/validate_contradiction_gap_acceptance.ps1`, `tests/m007/validate_contradiction_gap_unit.ps1`.

## Clôture T-006 - assertions de réponse

- Scénario BDD: Given un brouillon de réponse; When RA extrait les assertions importantes; Then chaque assertion atomique est reliée à son origine et à son support attendu.
- ADR: non requise; application de `DDD-ADR-005` et `DDD-ADR-007`.
- Commits: RED `7ddcf248`; GREEN `6859c20a`.
- Preuves livrées: `app/research_answering/application/draft_answer.py`, `app/research_answering/adapters/local_answer_assertion_extractor.py`, `tests/m007/validate_answer_assertion_extraction_acceptance.ps1`, `tests/m007/validate_answer_assertion_extraction_unit.ps1`.

## Clôture T-007 - support et citations

- Scénario BDD: Given des assertions extraites; When RA évalue support, citations, conflits et lacunes; Then la version publiée porte un statut explicite et une provenance non vide.
- ADR: non requise; application de `ADR-006`, `DDD-ADR-003`, `DDD-ADR-005` et `DDD-ADR-007`.
- Commits: RED `1649b614`; GREEN `87574f14`.
- Preuves livrées: `app/research_answering/domain/answer.py`, `app/research_answering/application/verify_answer.py`, `tests/m007/validate_answer_support_acceptance.ps1`, `tests/m007/validate_answer_support_unit.ps1`.

## Clôture T-008 - abstention données actuelles

- Scénario BDD: Given une question qui requiert une donnée actuelle non autorisée; When RA publie la réponse; Then `REQUIRES_CURRENT_DATA` est explicite et aucune valeur de marché n'est inventée.
- ADR: non requise; application de `DDD-ADR-007`.
- Commits: RED `deb13fd6`; GREEN `816c3176`.
- Preuves livrées: `tests/m007/validate_current_data_abstention_acceptance.ps1`, `tests/m007/validate_current_data_abstention_unit.ps1`, politiques d'abstention dans `app/research_answering/domain/answer.py`.

## Clôture T-009 - commande publique de réponse documentaire

- Scénario BDD: Given un appel `POST /v1/answer`; When RA orchestre le workflow documentaire; Then la réponse publique expose le contrat RA sans stockage interne ni prompt.
- ADR: non requise; application de `ADR-010`, `DDD-ADR-003` et `DDD-ADR-005`.
- Commits: RED `4935242a`; GREEN `d1afce64`.
- Preuves livrées: `app/research_answering/adapters/answer_http.py`, `app/research_answering/application/answer_question.py`, `tests/m007/validate_answer_http_contract_acceptance.ps1`, `tests/m007/validate_answer_http_contract_unit.ps1`.

## Clôture T-010 - métriques, traçabilité et gates

- Scénario BDD: Given les comportements M-007 sont implémentés et testés; When la matrice de traçabilité et les gates sont exécutés; Then chaque exigence M-007 est rattachée à un test GREEN, une commande de validation et une ADR ou justification explicite.
- ADR: non requise; T-010 applique localement `ADR-006`, `ADR-010`, `DDD-ADR-005` et `DDD-ADR-008` sans introduire de solution d'observabilité durable, de dépendance externe ou de stockage métrique.
- Commit RED: `5ab39d2e` (`test(m007): couvrir tracabilite metriques gates`).
- Preuves livrées: `app/research_answering/application/traceability_metrics.py`, `tests/m007/validate_m007_traceability_acceptance.ps1`, `tests/m007/validate_m007_traceability_unit.ps1`, `tests/m007/fixtures/m007_response_metrics_fixture.json`, `docs/governance/m007_response_metrics.json`, matrice M-007 complète et enrôlement de tous les tests M-007 dans `scripts/test.ps1`.
- Garde-fous vérifiés: les métriques RA publient des compteurs, statuts, hashes et identifiants; elles ne publient ni prompt, ni brouillon, ni réponse complète, ni texte documentaire complet; le nombre de citations reste un compteur et n'est jamais interprété comme consensus documentaire.
