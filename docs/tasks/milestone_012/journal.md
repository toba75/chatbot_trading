# Journal M-012 - Évaluation pilote et calibration

## État initial

- Branche de planification: `codex/plan-m012-evaluation-pilote-calibration`.
- Base vérifiée: `master` et `origin/master` à `0a166827f921ec769e16462891aa8cebd0f7f299`.
- Milestone amont requis: M-011 présent dans `master`.
- Preuve de présence M-011: 54 entrées observées sous `docs/tasks/milestone_011`, `docs/specs/m011_experience_reproductible.md`, `scripts/validate_m011_precondition.ps1`, `scripts/validate_m011_specification.ps1`, `scripts/validate_m011_traceability.ps1`, `tests/m011`, `app/experimentation` et `app/contracts/strategy_experiments.py`.
- Gates rapides avant création: `scripts/validate_task_system.ps1` GREEN avec `12 milestone(s), 122 tâche(s) contrôlée(s)`; `scripts/lint.ps1` GREEN avec `22 validation(s), 0 test(s)`.
- Test global avant création: `scripts/test.ps1` RED sur `tests/m003/validate_m003_precondition_acceptance.ps1` avec `La précondition M-003 doit être GREEN sur la base courante. Code obtenu: 1`; T-001 porte cette récupération de précondition pour M-012.
- Gates après création: `scripts/validate_task_system.ps1` GREEN avec `13 milestone(s), 134 tâche(s) contrôlée(s)`; `scripts/lint.ps1` GREEN avec `22 validation(s), 0 test(s)`; `git diff --check` GREEN.
- Test global après création: `scripts/test.ps1` RED sur `tests/m003/validate_m003_precondition_acceptance.ps1` avec `La précondition M-003 doit être GREEN sur la base courante. Code obtenu: 1`; le RED reste porté par T-001.

## Découpage

- T-001 vérifie et rétablit la précondition GREEN M-012.
- T-002 publie la spécification détaillée d'évaluation pilote.
- T-003 constitue le corpus pilote représentatif.
- T-004 publie le jeu annoté page par page.
- T-005 mesure les routes documentaires.
- T-006 calibre les seuils de conversion canonique.
- T-007 mesure la recherche de connaissances.
- T-008 mesure les réponses vérifiées et l'abstention.
- T-009 mesure le LLM principal par le chemin réel.
- T-010 mesure les stratégies et backtests pilotes.
- T-011 publie les décisions de calibration et de promotion.
- T-012 relie M-012 aux écarts V1, à la traçabilité et aux gates.

## Exécution

- T-005 - Mesurer les routes documentaires:
  - Scénario BDD: Given un corpus pilote figé et un jeu annoté page par page; When les routes `Docling standard`, `Granite-Docling direct`, `prétraitement + Granite-Docling` et `double conversion et adjudication` sont mesurées; Then chaque route publie CER/WER, exactitude numérique, signes, formules, cellules, ordre de lecture, temps, mémoire, stabilité, échecs au dénominateur et détails par strate.
  - Commit RED: `f3ee7537a test(m012): couvrir les benchmarks de routes documentaires`.
  - Commit GREEN: `feat(m012): mesurer les routes documentaires`.
  - ADR: non requise; T-005 applique ADR-002 et ADR-010 sans ajouter de route documentaire structurante.
  - Fichiers livrés: `app/evaluation/domain/document_route_benchmark.py`, `app/evaluation/domain/__init__.py`, `tests/m012/validate_document_route_benchmark_acceptance.ps1`, `tests/m012/validate_document_route_benchmark_unit.ps1`, `docs/traceability/matrix.md`.
  - Validations ciblées GREEN: `tests/m012/validate_document_route_benchmark_acceptance.ps1`, `tests/m012/validate_document_route_benchmark_unit.ps1`.
- T-006 - Calibrer les seuils de conversion canonique:
  - Scénario BDD: Given les routes documentaires ont été mesurées sur le corpus pilote; When les seuils de conversion canonique sont calibrés; Then chaque seuil publié référence les métriques qui le justifient et toute insuffisance reste visible comme écart V1.
  - Commit RED: `2209bf6e1 test(m012): couvrir la calibration documentaire`.
  - Commit GREEN: `feat(m012): calibrer les seuils documentaires`.
  - ADR: non requise; T-006 applique ADR-002, ADR-004 et ADR-010 sans changer leur sens.
  - Fichiers livrés: `app/evaluation/domain/document_quality_calibration.py`, `app/evaluation/domain/__init__.py`, `tests/m012/validate_document_quality_calibration_acceptance.ps1`, `tests/m012/validate_document_quality_calibration_unit.ps1`, `docs/evaluation/m012/document_quality_calibration_report.md`, `docs/traceability/matrix.md`.
  - Validations ciblées GREEN: `tests/m012/validate_document_quality_calibration_acceptance.ps1`, `tests/m012/validate_document_quality_calibration_unit.ps1`.
- T-007 - Mesurer la recherche de connaissances:
  - Scénario BDD: Given un jeu de 100 à 300 questions avec pages attendues; When la recherche KA est exécutée sur la projection versionnée du corpus pilote; Then les métriques de rappel, rang, diversité, couverture et FR vers source EN sont publiées avec les échecs visibles.
  - Commit RED: `e4251e367 test(m012): couvrir le benchmark recherche`.
  - Commit GREEN: `feat(m012): mesurer la recherche de connaissances`.
  - ADR: non requise; T-007 applique ADR-005, ADR-010 et DDD-ADR-004 sans changer leur sens.
  - Fichiers livrés: `app/evaluation/domain/knowledge_search_benchmark.py`, `app/evaluation/domain/__init__.py`, `tests/m012/validate_knowledge_search_benchmark_acceptance.ps1`, `tests/m012/validate_knowledge_search_benchmark_unit.ps1`, `docs/evaluation/m012/knowledge_search_benchmark_report.md`, `docs/traceability/matrix.md`.
  - Validations ciblées GREEN: `tests/m012/validate_knowledge_search_benchmark_acceptance.ps1`, `tests/m012/validate_knowledge_search_benchmark_unit.ps1`.
- T-008 - Mesurer les réponses vérifiées et l'abstention:
  - Scénario BDD: Given des questions d'évaluation avec preuves, contradictions ou insuffisances attendues; When RA produit des réponses vérifiées et EG publie les états de claims associés au corpus pilote; Then chaque réponse est mesurée sur support, citations, abstention et limites, et les métriques EG sont publiées sans traiter une réponse plausible comme preuve.
  - Commit RED: `10f769679 test(m012): couvrir le benchmark reponses`.
  - Commit GREEN: `feat(m012): mesurer les reponses verifiees`.
  - ADR: non requise; T-008 applique ADR-010 et DDD-ADR-007 sans changer leur sens.
  - Fichiers livrés: `app/evaluation/domain/verified_answer_benchmark.py`, `app/evaluation/domain/__init__.py`, `tests/m012/validate_verified_answer_benchmark_acceptance.ps1`, `tests/m012/validate_verified_answer_benchmark_unit.ps1`, `docs/evaluation/m012/verified_answer_benchmark_report.md`, `docs/evaluation/m012/evidence_governance_benchmark_report.md`, `docs/traceability/matrix.md`.
  - Validations ciblées GREEN: `tests/m012/validate_verified_answer_benchmark_acceptance.ps1`, `tests/m012/validate_verified_answer_benchmark_unit.ps1`.
- T-009 - Mesurer le LLM principal par le chemin réel:
  - Scénario BDD: Given les checkpoints principaux obligatoires; When ils sont évalués par `docker-local -> llm-gateway -> réseau privé -> vLLM sur Spark`; Then la promotion communautaire est refusée sans tâches obligatoires au moins égales aux références officielles et sans métriques techniques exploitables.
  - Commit RED: `45a07bda3 test(m012): couvrir le benchmark llm chemin reel`.
  - Commit GREEN: `feat(m012): mesurer le llm principal`.
  - ADR: non requise; T-009 applique ADR-008, ADR-010 et DDD-ADR-007 sans changer leur sens.
  - Fichiers livrés: `app/evaluation/domain/llm_real_path_benchmark.py`, `app/evaluation/domain/__init__.py`, `tests/m012/validate_llm_benchmark_real_path_acceptance.ps1`, `tests/m012/validate_llm_benchmark_real_path_unit.ps1`, `docs/evaluation/m012/llm_real_path_benchmark_report.md`, `docs/traceability/matrix.md`.
  - Validations ciblées GREEN: `tests/m012/validate_llm_benchmark_real_path_acceptance.ps1`, `tests/m012/validate_llm_benchmark_real_path_unit.ps1`.
- T-010 - Mesurer les stratégies et backtests pilotes:
  - Scénario BDD: Given des stratégies candidates snapshotées et des expériences reproductibles M-011; When les backtests pilotes sont mesurés selon un protocole M-012; Then les métriques SD, les métriques EX, limites, coûts, périodes, univers et résultats négatifs sont publiés sans promotion implicite de rentabilité.
  - Commit RED: `fd689a6ef test(m012): couvrir le benchmark backtests`.
  - Commit GREEN: `feat(m012): mesurer strategies et backtests pilotes`.
  - ADR: non requise; T-010 applique ADR-010, DDD-ADR-009 et DDD-ADR-010 sans changer leur sens.
  - Fichiers livrés: `app/evaluation/domain/strategy_backtest_benchmark.py`, `app/evaluation/domain/__init__.py`, `tests/m012/validate_strategy_backtest_benchmark_acceptance.ps1`, `tests/m012/validate_strategy_backtest_benchmark_unit.ps1`, `docs/evaluation/m012/strategy_backtest_benchmark_report.md`, `docs/traceability/matrix.md`.
  - Validations ciblées GREEN: `tests/m012/validate_strategy_backtest_benchmark_acceptance.ps1`, `tests/m012/validate_strategy_backtest_benchmark_unit.ps1`.
- T-011 - Publier les décisions de calibration et de promotion:
  - Scénario BDD: Given les benchmarks documentaires, recherche, gouvernance des preuves, réponses, conversation, stratégies, LLM et backtests sont terminés; When les décisions de calibration et promotion sont publiées; Then chaque décision référence ses métriques sources, conserve les refus et reports, et empêche qu'un test scientifique RED soit caché par un gate logiciel GREEN.
  - Commit RED: `b55920721 test(m012): couvrir decisions calibration promotion`.
  - Commit GREEN: `feat(m012): publier decisions calibration promotion`.
  - ADR: non requise; T-011 applique ADR-010 et DDD-ADR-010 sans changer leur sens.
  - Fichiers livrés: `app/evaluation/domain/calibration_decisions.py`, `app/evaluation/domain/__init__.py`, `tests/m012/validate_calibration_decisions_acceptance.ps1`, `tests/m012/validate_calibration_decisions_unit.ps1`, `docs/evaluation/m012/calibration_promotion_decisions_report.md`, `docs/traceability/matrix.md`.
  - Validations ciblées attendues: `tests/m012/validate_calibration_decisions_acceptance.ps1`, `tests/m012/validate_calibration_decisions_unit.ps1`, `scripts/validate_m012_specification.ps1`, `scripts/validate_adr_system.ps1`, `scripts/lint.ps1`.
- T-012 - Relier M-012 aux écarts V1, à la traçabilité et aux gates:
  - Scénario BDD: Given M-012 a livré corpus, annotations, benchmarks SP, KA, EG, RA, CV, SD, LLM et EX, seuils et décisions; When les gates transverses sont exécutés; Then chaque exigence M-012 est reliée à un test GREEN ou à un écart scientifique explicite, et M-013 reçoit un rapport V1 exploitable.
  - Commit RED: `772a1c7b7 test(m012): couvrir ecarts v1 tracabilite gates`.
  - Commit GREEN: à compléter après validation.
  - ADR: non requise; T-012 applique ADR-010 et DDD-ADR-010 sans changer leur sens.
  - Fichiers livrés: `scripts/validate_m012_traceability.ps1`, `tests/m012/validate_m012_traceability_acceptance.ps1`, `tests/m012/validate_m012_traceability_unit.ps1`, `docs/governance/m012_v1_gap_report.md`, `docs/traceability/matrix.md`, `scripts/test.ps1`, `scripts/lint.ps1`, `tests/governance/validate_m000_validation_commands_acceptance.ps1`.
  - Enrôlement final: tous les tests M-012 sont listés dans `scripts/test.ps1`; le validateur `scripts/validate_m012_traceability.ps1` est listé dans `scripts/test.ps1` et `scripts/lint.ps1`; les compteurs attendus sont consolidés à `23 validation(s), 268 test(s)` pour `scripts/test.ps1` et `24 validation(s), 0 test(s)` pour `scripts/lint.ps1`.
  - Validations ciblées GREEN: `tests/m012/validate_m012_traceability_acceptance.ps1`, `tests/m012/validate_m012_traceability_unit.ps1`, `scripts/validate_m012_traceability.ps1`, `scripts/validate_traceability.ps1`, `scripts/lint.ps1`, `git diff --check`.
  - Gate global `scripts/test.ps1`: non conclusif après plus de 60 minutes; dernier arbre observé dans `tests/m009/validate_m009_precondition_acceptance.ps1` -> `scripts/validate_m009_precondition.ps1` -> `scripts/test.ps1` imbriqué, rendu jusqu'à `tests/m006/validate_m006_specification_unit.ps1` avant arrêt manuel des processus de test orphelins.

## Revue d'adhérence

- Findings de revue résolus après planification:
  - T-002, T-011 et T-012 couvrent désormais explicitement les métriques et décisions EG/SD exigées par la section 19 de la spécification v4.1, en plus de SP, KA, RA, LLM et EX.
  - T-003 énumère désormais les strates normatives du corpus pilote: PDF numériques propres, scans propres, scans inclinés, scans bruités, anciennes couches OCR défectueuses, documents mixtes, textes français et anglais, tableaux financiers, équations, graphiques, colonnes multiples et éditions différentes.
  - T-003 rend désormais toute strate normative manquante bloquante: une absence ne peut plus être justifiée comme GREEN et doit rester RED avec écart V1 explicite.
  - T-008 produit désormais le benchmark EG avec taux de claims vérifiés, rejetés et en revue, affirmations sans preuve directe, distribution des verdicts, groupes de dépendance, supersession et délai de vérification.
  - T-010 produit désormais les métriques SD de la section 19: stratégies compilables, raisons de rejet, origines de règles, paramètres sans plan de calibration, conflits de compatibilité et versions par stratégie.
  - T-005 verrouille désormais toutes les métriques documentaires normatives dans les tests RED: CER/WER, exactitude numérique, signes, formules, cellules, ordre de lecture, temps par page, mémoire et stabilité.
  - T-008 couvre désormais les métriques RA obligatoires: statuts `SUPPORTED`, `PARTIALLY_SUPPORTED`, `INSUFFICIENT_EVIDENCE` et `CONFLICTING_EVIDENCE`, assertions non supportées retirées, couverture des obligations de recherche et réponses réutilisant une version obsolète.
  - T-009 verrouille désormais toutes les tâches obligatoires du benchmark LLM et leurs métriques techniques séparées avant toute décision de promotion.
  - T-011 et T-012 relient désormais les métriques RA, les tâches LLM obligatoires et les métriques documentaires normatives aux décisions, à la traçabilité et au rapport d'écarts V1.
  - T-002, T-011 et T-012 couvrent désormais explicitement CV par les critères de conversation, suivi, routage de mode et absence d'usage factuel de l'historique brut, au lieu de limiter le rapport final à SP, KA, EG, RA, SD, LLM et EX.
  - T-012 ne déclare plus M-013 comme dépendance d'implémentation; M-013 est seulement le consommateur aval du rapport d'écarts V1 produit par M-012.
  - T-009 distingue désormais les retries LLM bornés avant premier token, mesurés et idempotents, des retries après premier token ou illimités qui restent interdits.
