# Rapport des écarts V1 M-012

## Scénario BDD

- Given M-012 a livré corpus, annotations, benchmarks SP, KA, EG, RA, CV, SD, LLM et EX, seuils et décisions.
- When les gates transverses sont exécutées.
- Then chaque exigence M-012 est reliée à un test GREEN ou à un écart scientifique explicite, et M-013 reçoit un rapport V1 exploitable.

## Statut des écarts V1

| Contexte | Statut | Critère V1 | Benchmark source | Corpus | Décision liée | Commande de preuve | Justification |
|---|---|---|---|---|---|---|---|
| SP | différé | Qualité documentaire, formules, cellules, temps, mémoire et stabilité. | `RBRUN-M012-DOCUMENT-ROUTES-0001` | `CORPUS-M012-PILOTE-0001` | `DEC-M012-SP-DEFERRED` | `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_document_quality_calibration_acceptance.ps1` | Les métriques documentaires normatives sont publiées, mais `document_cell_accuracy` reste un Test scientifique RED visible avant durcissement V1. |
| KA | différé | Recherche de connaissances sur pages attendues. | `KSRUN-M012-KNOWLEDGE-0001` | `CORPUS-M012-PILOTE-0001` | `DEC-M012-KA-REJECTED` | `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_knowledge_search_benchmark_acceptance.ps1` | Le rappel pilote reste sous seuil pour `knowledge_recall_at_10`; la gate logicielle GREEN ne masque pas ce résultat scientifique. |
| EG | satisfait | Gouvernance des preuves séparée de RA. | `EGRUN-M012-0001` | `CORPUS-M012-PILOTE-0001` | `DEC-M012-EG-ACCEPTED` | `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_verified_answer_benchmark_acceptance.ps1` | Les claims vérifiés, rejetés, en revue, verdicts, dépendances, supersessions et délais sont mesurés sans stockage interne. |
| RA | différé | Réponses vérifiées, abstention et contradictions. | `VARUN-M012-VERIFIED-ANSWERS-0001` | `CORPUS-M012-PILOTE-0001` | `DEC-M012-RA-DEFERRED` | `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_verified_answer_benchmark_acceptance.ps1` | `answer_correct_abstention_rate` reste à renforcer; le rapport conserve les citations, statuts, obligations et versions obsolètes mesurés. |
| CV | satisfait | Conversation, suivi, routage de mode et absence d'usage factuel de l'historique brut. | `CVRUN-M012-CRITERIA-0001` | `CORPUS-M012-PILOTE-0001` | `DEC-M012-CV-ACCEPTED` | `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_calibration_decisions_acceptance.ps1` | Les critères CV V1 sont reliés aux décisions sans réutiliser l'historique brut comme preuve factuelle. |
| SD | bloquant | Stratégies candidates, compatibilité et paramètres calibrables. | `SBRUN-M012-STRATEGY-BACKTEST-0001` | `CORPUS-M012-PILOTE-0001` | `DEC-M012-SD-REJECTED` | `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_strategy_backtest_benchmark_acceptance.ps1` | Des paramètres restent sans plan de calibration; l'écart bloque toute promotion V1 de stratégie. |
| LLM | bloquant | Promotion du checkpoint principal par chemin réel. | `LLMRUN-M012-REAL-PATH-0001` | `CORPUS-M012-PILOTE-0001` | `DEC-M012-LLM-REJECTED` | `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_llm_benchmark_real_path_acceptance.ps1` | Le checkpoint communautaire est refusé tant qu'une tâche obligatoire reste inférieure aux références officielles. |
| EX | satisfait | Backtests pilotes reproductibles et conservation des résultats négatifs. | `SBRUN-M012-EXPERIMENTS-0001` | `CORPUS-M012-PILOTE-0001` | `DEC-M012-EX-ACCEPTED` | `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_strategy_backtest_benchmark_acceptance.ps1` | Les répétitions, échecs, coûts et résultats négatifs restent versionnés et auditables. |

## Métriques reliées

| Contexte | Métriques ou tâches | Benchmark source | Corpus | Décision liée |
|---|---|---|---|---|
| SP | `source_canonical_version_ratio`, `source_quarantine_rate`, `source_page_without_valid_authority_rate`, `source_adjudication_rate`, `source_quality_supersession_total`, `source_publication_delay_seconds`, `document_cer_wer`, `document_numeric_token_accuracy`, `document_sign_accuracy`, `document_formula_fidelity`, `document_cell_accuracy`, `document_reading_order_accuracy`, `document_page_time_seconds`, `document_memory_bytes`, `document_route_stability_rate` | `RBRUN-M012-DOCUMENT-ROUTES-0001` | `CORPUS-M012-PILOTE-0001` | `DEC-M012-SP-DEFERRED` |
| KA | `knowledge_projection_current_ratio`, `knowledge_unresolvable_locator_rate`, `knowledge_result_diversity_average`, `knowledge_stale_projection_search_rate`, `knowledge_recall_at_5`, `knowledge_recall_at_10`, `knowledge_recall_at_20`, `knowledge_mrr`, `knowledge_ndcg`, `knowledge_expected_page_accuracy`, `knowledge_subtopic_coverage_rate`, `knowledge_fr_to_en_performance` | `KSRUN-M012-KNOWLEDGE-0001` | `CORPUS-M012-PILOTE-0001` | `DEC-M012-KA-REJECTED` |
| EG | `evidence_claim_verified_rate`, `evidence_claim_rejected_rate`, `evidence_claim_review_rate`, `evidence_unsupported_assertion_ratio`, `evidence_verdict_distribution`, `evidence_dependency_group_count`, `evidence_supersession_rate`, `evidence_verification_delay_seconds` | `EGRUN-M012-0001` | `CORPUS-M012-PILOTE-0001` | `DEC-M012-EG-ACCEPTED` |
| RA | `answer_support_status_rate`, `answer_unsupported_assertion_removed_total`, `answer_citation_precision`, `answer_correct_abstention_rate`, `answer_research_obligation_coverage`, `answer_obsolete_version_reuse_rate`, `answer_accuracy_score`, `answer_fidelity_score`, `answer_completeness_score`, `answer_contradiction_management_rate`, `answer_source_deduction_distinction_rate`, `answer_invented_parameter_rejection_rate` | `VARUN-M012-VERIFIED-ANSWERS-0001` | `CORPUS-M012-PILOTE-0001` | `DEC-M012-RA-DEFERRED` |
| CV | `conversation_creation_criterion`, `conversation_follow_up_resolution_rate`, `conversation_mode_routing_justified_rate`, `conversation_raw_history_fact_usage_rejection_total` | `CVRUN-M012-CRITERIA-0001` | `CORPUS-M012-PILOTE-0001` | `DEC-M012-CV-ACCEPTED` |
| SD | `strategy_compilable_rate`, `strategy_rejection_reason_distribution`, `strategy_rule_origin_ratio`, `strategy_parameter_without_calibration_plan_total`, `strategy_compatibility_conflict_total`, `strategy_version_count` | `SBRUN-M012-STRATEGY-BACKTEST-0001` | `CORPUS-M012-PILOTE-0001` | `DEC-M012-SD-REJECTED` |
| LLM | `json_valide`, `extraction_atomique`, `conservation_negations`, `exactitude_nombres`, `conditions_application`, `limites`, `entailment`, `contradiction`, `synthese_fr_en`, `tool_calling`, `citations`, `llm_gateway_latency_ms`, `llm_network_latency_ms`, `llm_vllm_queue_time_ms`, `llm_time_to_first_token_ms`, `llm_tokens_per_second`, `llm_error_rate`, `llm_retry_before_first_token_total`, `llm_structured_output_stability_rate`, `llm_spark_restart_recovery_rate` | `LLMRUN-M012-REAL-PATH-0001` | `CORPUS-M012-PILOTE-0001` | `DEC-M012-LLM-REJECTED` |
| EX | `experiment_reproducible_rate`, `experiment_failure_rate_by_cause`, `negative_experiment_retention_ratio`, `experiment_without_complete_cost_model_total`, `coherent_repeat_count`, `invalidated_result_ratio` | `SBRUN-M012-EXPERIMENTS-0001` | `CORPUS-M012-PILOTE-0001` | `DEC-M012-EX-ACCEPTED` |

## Tests scientifiques RED conservés

Un Test scientifique RED reste publié même quand la gate logiciel GREEN valide le code:

- `document_cell_accuracy` depuis `RBRUN-M012-DOCUMENT-ROUTES-0001`: écart SP `différé`, décision `DEC-M012-SP-DEFERRED`.
- `knowledge_recall_at_10` depuis `KSRUN-M012-KNOWLEDGE-0001`: écart KA `différé`, décision `DEC-M012-KA-REJECTED`.
- `answer_correct_abstention_rate` depuis `VARUN-M012-VERIFIED-ANSWERS-0001`: écart RA `différé`, décision `DEC-M012-RA-DEFERRED`.
- `strategy_parameter_without_calibration_plan_total` depuis `SBRUN-M012-STRATEGY-BACKTEST-0001`: écart SD `bloquant`, décision `DEC-M012-SD-REJECTED`.
- `exactitude_nombres` depuis `LLMRUN-M012-REAL-PATH-0001`: écart LLM `bloquant`, décision `DEC-M012-LLM-REJECTED`.

## Commandes de preuve

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_m012_traceability_acceptance.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_m012_traceability_unit.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m012_traceability.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1
```

## Garde-fous

- Aucun écart V1 sans statut `satisfait`, `bloquant`, `accepté` ou `différé`.
- Aucune métrique ne publie prompt complet, preuve complète, réponse complète, secret ou données de marché complètes.
- Aucun Test scientifique RED n'est transformé en réussite scientifique par une gate logiciel GREEN.
- ADR: non requise; T-012 applique ADR-010 et DDD-ADR-010 sans changer leur sens.
