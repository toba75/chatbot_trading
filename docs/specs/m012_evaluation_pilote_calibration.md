# M-012 - Évaluation pilote et calibration

## Statut

- Milestone: M-012 - Évaluation pilote et calibration.
- Tâche source: `docs/tasks/milestone_012/0002_publier_specification_evaluation_pilote.md`.
- Source normative: `docs/specs/plan_implementation_milestones_workstreams.md`, M-012, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 19, 20, 21 et 22.
- Statut: spécification exécutable publiée pour guider T-003 à T-012.
- ADR applicables: ADR-002; ADR-005; ADR-008; ADR-010; DDD-ADR-007; DDD-ADR-009; DDD-ADR-010.

## Scénario BDD

- Given la mission M-012 est de mesurer le système sur corpus pilote avant acceptation V1.
- When la spécification d'évaluation pilote est publiée.
- Then chaque comportement M-012 nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.

## Mission M-012

M-012 mesure la qualité du système sur un corpus pilote représentatif avant acceptation V1. La mission publie un protocole vérifiable pour relier `PilotCorpus`, `PageAnnotation`, `EvaluationRun`, `BenchmarkResult`, `CalibrationDecision`, `PromotionDecision` et `V1GapReport` sans modifier les artefacts immuables produits par SP, KA, EG, RA, CV, SD ou EX.

M-012 sépare les tests logiciels des tests scientifiques. Un test scientifique échoué reste visible même si les tests logiciels sont GREEN. Une décision de calibration ou de promotion ne peut pas être produite par préférence implicite, par valeur de seuil non sourcée ou par résultat masqué.

## Contexte DDD

- Domaine: évaluation scientifique et calibration des seuils.
- Bounded context: transverse d'évaluation, propriétaire des artefacts de benchmark et consommateur des contrats publics des contextes métier.
- Intégrations: SP fournit versions et routes documentaires; KA fournit résultats de recherche traçables; EG fournit verdicts de claims; RA fournit réponses vérifiées; CV fournit critères de conversation; SD fournit stratégies et paramètres; EX fournit expériences reproductibles; le LLM principal est mesuré via le chemin réel `docker-local -> llm-gateway -> Spark`.
- Garde-fous: aucune écriture dans les stockages métier amont; aucune lecture de table interne comme contrat public; aucune décision structurante implicite; aucun fallback silencieux; aucun résultat scientifique masqué par une gate logicielle.

## Langage ubiquitaire M-012

| Terme | Sens M-012 | Invariant |
|---|---|---|
| PilotCorpus | Ensemble figé de documents pilotes. | Contient 50 à 100 PDF et couvre toutes les strates normatives publiées. |
| PilotDocument | Document inclus dans le corpus pilote. | Porte un identifiant stable et une strate d'évaluation explicite. |
| PageAnnotation | Oracle page par page indépendant du système évalué. | Contient état attendu, route attendue, transcription, valeurs critiques, structures, ordre de lecture et zones de provenance. |
| EvaluationRun | Exécution versionnée d'un benchmark. | Référence corpus, annotations, version de politique, version de code et commande. |
| BenchmarkResult | Résultat append-only d'une mesure scientifique. | Conserve protocole, entrées, métriques, échecs et dénominateur. |
| CalibrationDecision | Décision versionnée de seuil ou de critère. | Référence les BenchmarkResult comparables qui la justifient. |
| PromotionDecision | Décision d'accepter, refuser ou différer une promotion. | Refuse toute promotion sans benchmark comparable. |
| V1GapReport | Rapport des écarts entre mesures M-012 et critères V1. | Liste chaque écart avec statut explicite et commande de preuve. |

## Artefacts d'évaluation M-012

| Artefact | Responsabilité | Invariants |
|---|---|---|
| PilotCorpus | Figer le périmètre représentatif du pilote. | 50 à 100 PDF; strates normatives complètes; chemins résolvables; identifiants stables. |
| PilotDocument | Décrire chaque PDF évalué. | Aucune strate implicite; aucune substitution silencieuse de fichier. |
| PageAnnotation | Publier l'oracle indépendant page par page. | Toute page évaluée a une annotation; aucune annotation générée par le système évalué n'est acceptée. |
| EvaluationRun | Relier une exécution aux versions mesurées. | Entrées, politique, code, commande et horodatage sont traçables. |
| BenchmarkResult | Publier les mesures scientifiques. | Les échecs restent dans le dénominateur; aucune réécriture de résultat. |
| CalibrationDecision | Transformer une mesure en seuil ou critère calibré. | Aucune valeur de seuil non sourcée; source benchmark obligatoire. |
| PromotionDecision | Décider une promotion de route, modèle ou politique. | Le checkpoint communautaire n'est promu que si les tâches obligatoires égalent ou dépassent les références. |
| V1GapReport | Préparer M-013. | Chaque critère V1 satisfait, bloquant, accepté ou différé est explicite. |

## Politiques normatives M-012

| Politique | Décision | Invariants | ADR |
|---|---|---|---|
| PilotCorpusCoveragePolicy | Contrôle le corpus pilote. | 50 à 100 PDF; toutes les strates M-012 sont présentes. | ADR-010 |
| PageAnnotationPolicy | Contrôle l'oracle page par page. | Chaque page évaluée porte état, route, transcription, valeurs critiques, tableaux, ordre de lecture et provenance. | ADR-002; ADR-010 |
| DocumentRouteBenchmarkPolicy | Mesure les routes documentaires. | Les routes incertaines et les quarantaines restent explicites, sans route alternative silencieuse. | ADR-002; ADR-010 |
| ScientificMetricPolicy | Publie des métriques comparables. | Les tests scientifiques RED restent visibles malgré des tests logiciels GREEN. | ADR-010; DDD-ADR-010 |
| KnowledgeBenchmarkPolicy | Mesure KA sur questions annotées. | Recall@5, Recall@10, Recall@20, MRR et nDCG sont calculés sur pages attendues. | ADR-005; ADR-010 |
| EvidenceAnswerBenchmarkPolicy | Mesure EG et RA. | Claims, statuts RA, citations, abstention et contradictions restent séparés. | ADR-010; DDD-ADR-007 |
| ConversationCriterionPolicy | Mesure CV par critères V1. | Conversation, question de suivi, routage de mode et absence d'usage factuel de l'historique brut sont obligatoires. | ADR-010; DDD-ADR-007 |
| LlmRealPathBenchmarkPolicy | Mesure le LLM principal par le chemin réel. | Les prompts et preuves complets ne sont pas publiés dans les métriques. | ADR-008; ADR-010; DDD-ADR-007 |
| StrategyExperimentBenchmarkPolicy | Mesure SD et EX. | Stratégies, paramètres, coûts, environnement, résultats négatifs et répétitions restent versionnés. | ADR-010; DDD-ADR-009; DDD-ADR-010 |
| CalibrationDecisionPolicy | Produit les seuils et promotions. | Toute décision référence un benchmark comparable et conserve les refus. | ADR-010; DDD-ADR-010 |
| V1GapReportPolicy | Publie les écarts V1. | Aucun écart n'est masqué; chaque statut est exploitable par M-013. | ADR-010 |

## Corpus pilote borné

Le corpus pilote contient 50 à 100 PDF. Il couvre obligatoirement les strates suivantes:

- PDF numériques propres;
- scans propres;
- scans inclinés;
- scans bruités;
- anciennes couches OCR défectueuses;
- documents mixtes;
- textes français et anglais;
- tableaux financiers;
- équations;
- graphiques;
- colonnes multiples;
- éditions différentes.

Un `PilotDocument` sans identifiant stable, strate explicite ou chemin résolvable est rejeté.

## Annotations page par page

Chaque `PageAnnotation` contient:

- état attendu;
- route attendue;
- transcription de référence;
- valeurs numériques critiques avec signe et unité;
- structure de tableaux;
- ordre de lecture;
- zones de provenance;
- statut de validation de l'annotation.

Les annotations produites par le système évalué ne peuvent pas servir d'oracle M-012.

## Métriques normatives par contexte

| Signal | Contexte | Source normative | Invariant |
|---|---|---|---|
| source_canonical_version_ratio | SP | Section 19, traitement des sources. | Proportion de documents ayant une version canonique. |
| source_quarantine_rate | SP | Section 19, traitement des sources. | Taux de quarantaine publié avec dénominateur. |
| source_page_without_valid_authority_rate | SP | Section 19, traitement des sources. | Pages sans autorité valide visibles. |
| source_adjudication_rate | SP | Section 19, traitement des sources. | Taux d'adjudication séparé par route. |
| source_quality_supersession_total | SP | Section 19, traitement des sources. | Versions supersédées pour défaut de qualité conservées. |
| source_publication_delay_seconds | SP | Section 19, traitement des sources. | Délai entre enregistrement et publication canonique. |
| document_cer | SP | Section 20, évaluation des routes documentaires. | CER sur échantillon annoté. |
| document_wer | SP | Section 20, évaluation des routes documentaires. | WER sur échantillon annoté. |
| document_numeric_token_accuracy | SP | Section 20, évaluation des routes documentaires. | Exactitude des tokens numériques. |
| document_sign_accuracy | SP | Section 20, évaluation des routes documentaires. | Exactitude des signes. |
| document_formula_fidelity | SP | Section 20, évaluation des routes documentaires. | Fidélité des formules. |
| document_cell_accuracy | SP | Section 20, évaluation des routes documentaires. | Exactitude des cellules. |
| document_reading_order_accuracy | SP | Section 20, évaluation des routes documentaires. | Ordre de lecture contrôlé. |
| document_page_time_seconds | SP | Section 20, évaluation des routes documentaires. | Temps par page publié. |
| document_memory_bytes | SP | Section 20, évaluation des routes documentaires. | Mémoire consommée publiée sans payload. |
| document_route_stability_rate | SP | Section 20, évaluation des routes documentaires. | Stabilité de route mesurée. |
| document_failure_rate | SP | Section 20, évaluation des routes documentaires. | Pages échouées conservées dans le dénominateur. |
| knowledge_projection_current_ratio | KA | Section 19, accès aux connaissances. | Part des versions canoniques avec projection actuelle. |
| knowledge_unresolvable_locator_rate | KA | Section 19, accès aux connaissances. | Taux de localisateurs non résolvables. |
| knowledge_document_diversity | KA | Section 19, accès aux connaissances. | Diversité documentaire des résultats. |
| knowledge_stale_projection_search_rate | KA | Section 19, accès aux connaissances. | Recherches sur projection stale visibles. |
| knowledge_recall_at_5 | KA | Section 20, évaluation de la recherche. | Recall@5 sur questions annotées. |
| knowledge_recall_at_10 | KA | Section 20, évaluation de la recherche. | Recall@10 sur questions annotées. |
| knowledge_recall_at_20 | KA | Section 20, évaluation de la recherche. | Recall@20 sur questions annotées. |
| knowledge_mrr | KA | Section 20, évaluation de la recherche. | MRR publié. |
| knowledge_ndcg | KA | Section 20, évaluation de la recherche. | nDCG publié. |
| knowledge_expected_page_accuracy | KA | Section 20, évaluation de la recherche. | Exactitude de page attendue. |
| knowledge_subtheme_coverage | KA | Section 20, évaluation de la recherche. | Couverture des sous-thèmes. |
| knowledge_fr_to_en_recall_at_10 | KA | Section 20, évaluation de la recherche. | Recall@10 des questions FR vers source EN. |
| evidence_claim_verified_rate | EG | Section 19, gouvernance des preuves. | Taux de claims vérifiés. |
| evidence_claim_rejected_rate | EG | Section 19, gouvernance des preuves. | Taux de claims rejetés. |
| evidence_claim_review_rate | EG | Section 19, gouvernance des preuves. | Taux de claims en revue. |
| evidence_unsupported_assertion_ratio | EG | Section 19, gouvernance des preuves. | Proportion d'affirmations sans preuve directe. |
| evidence_verdict_distribution | EG | Section 19, gouvernance des preuves. | Distribution des verdicts. |
| evidence_dependency_group_count | EG | Section 19, gouvernance des preuves. | Groupes de dépendance par sujet. |
| evidence_supersession_rate | EG | Section 19, gouvernance des preuves. | Taux de supersession. |
| evidence_verification_delay_seconds | EG | Section 19, gouvernance des preuves. | Délai de vérification. |
| answer_support_status_rate | RA | Section 19, recherche et réponse. | Taux SUPPORTED, PARTIALLY_SUPPORTED, INSUFFICIENT_EVIDENCE et CONFLICTING_EVIDENCE. |
| answer_unsupported_assertion_removed_total | RA | Section 19, recherche et réponse. | Assertions non supportées retirées. |
| answer_citation_precision | RA | Section 19, recherche et réponse. | Précision des citations. |
| answer_correct_abstention_rate | RA | Section 19, recherche et réponse. | Taux d'abstention correcte. |
| answer_research_obligation_coverage | RA | Section 19, recherche et réponse. | Couverture des obligations de recherche. |
| answer_obsolete_version_reuse_rate | RA | Section 19, recherche et réponse. | Réponses réutilisant une version obsolète. |
| answer_accuracy_score | RA | Section 20, évaluation des réponses. | Exactitude mesurée sur oracle. |
| answer_fidelity_score | RA | Section 20, évaluation des réponses. | Fidélité aux preuves mesurée. |
| answer_completeness_score | RA | Section 20, évaluation des réponses. | Complétude mesurée. |
| answer_contradiction_management_rate | RA | Section 20, évaluation des réponses. | Gestion des contradictions mesurée. |
| answer_source_deduction_distinction_rate | RA | Section 20, évaluation des réponses. | Distinction source/déduction mesurée. |
| answer_invented_parameter_rejection_rate | RA | Section 20, évaluation des réponses. | Paramètres inventés refusés. |
| conversation_creation_criterion | CV | Section 21, critères V1. | L'utilisateur peut créer une conversation. |
| conversation_follow_up_resolution_rate | CV | Section 21 et M-008. | Une question de suivi reprend sans ambiguïté le contexte utile. |
| conversation_mode_routing_justified_rate | CV | Section 21 et M-008. | Le routage de mode est explicite et justifié. |
| conversation_raw_history_fact_usage_rejection_total | CV | Section 21 et M-008. | absence d'usage factuel de l'historique brut. |
| conversation_prompt_payload_rejected_total | CV | M-008. | Payloads refusés contenant historique brut ou prompt override. |
| conversation_public_error_total | CV | M-008. | Erreurs publiques CV par code. |
| strategy_compilable_rate | SD | Section 19, stratégies. | Taux de stratégies compilables. |
| strategy_rejection_reason_distribution | SD | Section 19, stratégies. | Raisons principales de rejet. |
| strategy_rule_origin_ratio | SD | Section 19, stratégies. | Proportion de règles par origine. |
| strategy_parameter_without_calibration_plan_total | SD | Section 19, stratégies. | Paramètres sans plan de calibration. |
| strategy_compatibility_conflict_total | SD | Section 19, stratégies. | Conflits de compatibilité par catégorie. |
| strategy_version_count | SD | Section 19, stratégies. | Nombre de versions par stratégie. |
| experiment_reproducible_rate | EX | Section 19, expériences. | Taux d'expériences reproductibles. |
| experiment_failure_rate_by_cause | EX | Section 19, expériences. | Taux d'échec par cause. |
| negative_experiment_retention_ratio | EX | Section 19, expériences. | Résultats négatifs conservés. |
| experiment_without_complete_cost_model_total | EX | Section 19, expériences. | Expériences sans modèle de coûts complet. |
| coherent_repeat_count | EX | Section 19, expériences. | Répétitions cohérentes. |
| invalidated_result_ratio | EX | Section 19, expériences. | Résultats invalidés après audit. |

## Critères CV V1

Les critères CV obligatoires pour M-012 sont:

- conversation: création et ajout de tours visibles;
- question de suivi: résolution autonome avant appel aval;
- routage de mode: mode documentaire, approfondi, stratégie, calcul ou backtest explicitement justifié;
- absence d'usage factuel de l'historique brut: une assertion historique est revalidée contre une preuve ou refusée.

Ces critères reprennent les exigences V1 et `docs/specs/m008_conversation_produit.md`.

## Benchmark LLM principal

Le benchmark LLM mesure au minimum les checkpoints suivants:

- nvidia/Gemma-4-31B-IT-NVFP4;
- YCWTG/gemma-4-31B-it-NVFP4A16-GPTQ;
- google/gemma-4-31B-it-qat-w4a16-ct.

Le chemin de mesure est `docker-local -> llm-gateway -> Spark`. Les tâches obligatoires sont JSON valide, extraction atomique, conservation des négations, exactitude des nombres, conditions d'application, limites, entailment, contradiction, synthèse FR/EN, tool calling et citations.

Les signaux techniques publiés sont `llm_gateway_latency_ms`, `llm_network_latency_ms`, `llm_vllm_queue_time_ms`, `llm_time_to_first_token_ms`, `llm_tokens_per_second`, `llm_error_rate`, `llm_retry_before_first_token_total`, `llm_structured_output_stability_rate` et `llm_spark_restart_recovery_rate`. Les prompts complets, preuves complètes et réponses complètes restent exclus des métriques publiques.

## Benchmark EX

Le benchmark EX relie les résultats de stratégies et backtests pilotes à `ExperimentResult` sans verdict de rentabilité non qualifié. Les métriques obligatoires sont `experiment_reproducible_rate`, `experiment_failure_rate_by_cause`, `negative_experiment_retention_ratio`, `experiment_without_complete_cost_model_total`, `coherent_repeat_count` et `invalidated_result_ratio`.

## Décisions de calibration

Chaque `CalibrationDecision` ou `PromotionDecision` contient:

- identifiant de décision;
- version de politique;
- BenchmarkResult source;
- contexte mesuré;
- métrique utilisée;
- statut accepté, refusé ou différé;
- justification textuelle;
- lien vers V1GapReport lorsque l'écart reste ouvert.

Aucune valeur de seuil non sourcée n'est publiée par T-002. Les seuils chiffrés sont produits uniquement par les tâches de calibration et de décision qui référencent leurs benchmarks sources.

## Rapport d'écarts V1

Le `V1GapReport` publie les écarts SP, KA, EG, RA, CV, SD, LLM et EX. Chaque écart contient:

- critère V1 concerné;
- métrique ou benchmark source;
- statut satisfait, bloquant, accepté ou différé;
- justification;
- commande de validation;
- décision de calibration ou de promotion liée si elle existe.

Un écart ne peut pas être supprimé parce qu'une gate logicielle est GREEN.

## Erreurs publiques

M-012 ne crée pas d'endpoint HTTP. Les statuts ci-dessous décrivent les diagnostics publics à exposer par un adaptateur existant si un cas M-012 est rendu accessible via API; ils ne constituent pas un nouveau contrat HTTP.

| Code | Statut HTTP | Sens public |
|---|---|---|
| HTTP_REQUEST_INVALID | 400 | Requête d'évaluation invalide. |
| ENDPOINT_NOT_FOUND | 404 | Endpoint d'évaluation absent. |
| PILOT_CORPUS_OUT_OF_BOUNDS | 422 | Corpus pilote hors borne 50 à 100 PDF. |
| PILOT_DOCUMENT_STRATUM_REQUIRED | 422 | Strate de document pilote absente. |
| PAGE_ANNOTATION_REQUIRED | 422 | Annotation page par page absente. |
| BENCHMARK_RESULT_REQUIRED | 422 | Benchmark source absent pour une mesure ou décision. |
| SCIENTIFIC_RESULT_RED | 422 | Diagnostic scientifique RED conservé et visible, sans transformer le RED en erreur logicielle. |
| CALIBRATION_DECISION_REQUIRED | 422 | Décision de calibration absente. |
| V1_GAP_REPORT_REQUIRED | 422 | Rapport d'écarts V1 absent. |
| PUBLIC_STORAGE_FIELD_FORBIDDEN | 422 | Champ de stockage interne interdit dans le contrat public. |
| FALLBACK_FORBIDDEN | 422 | Fallback silencieux interdit. |

## Comportements vérifiables M-012

| Comportement | Invariant | Scénario BDD | Test RED | ADR | Commande |
|---|---|---|---|---|---|
| EV-001 - Spécification exécutable M-012 | La spécification nomme mission, artefacts, corpus, annotations, métriques SP/KA/EG/RA/CV/SD/EX, benchmark LLM, décisions, écarts V1, erreurs, gates et exclusions. | Given la mission M-012 est de mesurer le système sur corpus pilote avant acceptation V1; When la spécification d'évaluation pilote est publiée; Then elle est validée par commande PowerShell. | T-002 | ADR-002; ADR-005; ADR-008; ADR-010; DDD-ADR-007; DDD-ADR-009; DDD-ADR-010 | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m012_specification.ps1 |
| EV-002 - Corpus pilote représentatif | PilotCorpus contient 50 à 100 PDF et toutes les strates. | Given les sources candidates sont disponibles; When le corpus pilote est constitué; Then chaque PDF porte identifiant, strate et chemin résolvable. | T-003 | ADR-010 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_pilot_corpus_acceptance.ps1 |
| EV-003 - Jeu annoté page par page | PageAnnotation couvre chaque page évaluée. | Given un PilotCorpus figé; When le jeu annoté est publié; Then route, transcription, valeurs, tableaux, ordre et provenance sont vérifiables. | T-004 | ADR-002; ADR-010 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_page_annotation_set_acceptance.ps1 |
| EV-004 - Benchmarks de routes documentaires | Les routes documentaires conservent échecs, temps, mémoire et stabilité. | Given un jeu annoté; When les routes documentaires sont mesurées; Then CER/WER, nombres, signes, formules, cellules, ordre, temps, mémoire et stabilité sont publiés. | T-005 | ADR-002; ADR-010 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_document_route_benchmark_acceptance.ps1 |
| EV-005 - Calibration documentaire | Une décision documentaire référence son benchmark. | Given des résultats de routes documentaires; When un seuil est calibré; Then aucune valeur non sourcée n'est promue. | T-006 | ADR-002; ADR-010 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_document_quality_calibration_acceptance.ps1 |
| EV-006 - Recherche de connaissances | KA publie Recall@5, Recall@10, Recall@20, MRR et nDCG. | Given 100 à 300 questions annotées; When la recherche est mesurée; Then les pages attendues et candidats traçables justifient les métriques. | T-007 | ADR-005; ADR-010 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_knowledge_search_benchmark_acceptance.ps1 |
| EV-007 - Réponses vérifiées, abstention et preuves | EG et RA restent séparés et mesurés. | Given des questions et preuves annotées; When les réponses sont évaluées; Then statuts, citations, abstention, claims et contradictions sont mesurés. | T-008 | ADR-010; DDD-ADR-007 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_verified_answer_benchmark_acceptance.ps1 |
| EV-008 - LLM principal par chemin réel | Le modèle est mesuré via docker-local -> llm-gateway -> Spark. | Given les checkpoints candidats; When le benchmark LLM est exécuté; Then les tâches obligatoires et métriques techniques sont comparables sans payload complet. | T-009 | ADR-008; ADR-010; DDD-ADR-007 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_llm_benchmark_real_path_acceptance.ps1 |
| EV-009 - Stratégies et backtests pilotes | SD et EX publient limites, coûts, résultats négatifs et répétitions. | Given des stratégies candidates attribuées; When les backtests pilotes sont mesurés; Then les métriques SD et EX proviennent des artefacts déterministes. | T-010 | ADR-010; DDD-ADR-009; DDD-ADR-010 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_strategy_backtest_benchmark_acceptance.ps1 |
| EV-010 - Décisions de calibration et promotion | Toute décision conserve son benchmark source et son statut. | Given les benchmarks M-012 publiés; When une décision est prise; Then acceptation, refus ou report sont versionnés et auditables. | T-011 | ADR-010; DDD-ADR-010 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_calibration_decisions_acceptance.ps1 |
| EV-011 - Écarts V1 et traçabilité gates | M-013 reçoit des écarts V1 exploitables. | Given M-012 a livré corpus, annotations, benchmarks et décisions; When la traçabilité est validée; Then chaque exigence relie test, commande, artefact, ADR et écart éventuel. | T-012 | ADR-010; DDD-ADR-010 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_m012_traceability_acceptance.ps1 |

## Commandes de validation

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_m012_specification_acceptance.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m012\validate_m012_specification_unit.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m012_specification.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1
```

## Exclusions M-012

- M-012 T-002 ne constitue pas le corpus pilote, ne publie pas les annotations et ne produit aucun benchmark réel.
- M-012 T-002 ne publie pas de seuil chiffré et ne transforme aucun résultat scientifique en décision d'acceptation V1.
- Aucun fallback silencieux n'est autorisé dans M-012.
- Aucun champ de stockage interne dans le contrat public.
- Aucun prompt complet, preuve complète, réponse complète, table interne, collection Qdrant ou payload moteur brut n'est publié comme métrique ou contrat public.
- Les résultats scientifiques RED restent visibles dans `BenchmarkResult` et `V1GapReport`.
- Les ADR acceptées sont appliquées sans changement de sens; aucune ADR nouvelle n'est requise pour cette publication documentaire.
