$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$gatePath = Join-Path $PSScriptRoot "m000_validation_gate.ps1"

if (-not (Test-Path -LiteralPath $gatePath -PathType Leaf)) {
    throw "Agrégateur de validation absent: scripts/m000_validation_gate.ps1"
}

. $gatePath

$preconditionReportPath = Join-Path $repoRoot "docs/governance/m000_precondition_green_initiale.md"
$m001SpecificationPath = Join-Path $repoRoot "docs/specs/m001_frontieres_ddd_contrats_publies.md"
$m002SpecificationPath = Join-Path $repoRoot "docs/specs/m002_plateforme_locale_sure.md"
$m003SpecificationPath = Join-Path $repoRoot "docs/specs/m003_source_enregistree_diagnostiquee_routee.md"
$m004SpecificationPath = Join-Path $repoRoot "docs/specs/m004_version_canonique_publiee.md"
$m005SpecificationPath = Join-Path $repoRoot "docs/specs/m005_projection_connaissance_recherchable.md"
$m006SpecificationPath = Join-Path $repoRoot "docs/specs/m006_claims_verifiables.md"
$m007SpecificationPath = Join-Path $repoRoot "docs/specs/m007_reponse_documentaire_verifiee.md"
$m008SpecificationPath = Join-Path $repoRoot "docs/specs/m008_conversation_produit.md"
$m009SpecificationPath = Join-Path $repoRoot "docs/specs/m009_recherche_approfondie_multi_sources.md"
$m010SpecificationPath = Join-Path $repoRoot "docs/specs/m010_strategie_candidate_attribuee.md"
$platformTopologyPath = Join-Path $repoRoot "app/platform/topology_registry.json"
$sparkFirewallPath = Join-Path $repoRoot "deploy/spark-firewall/network-boundary.json"
$appRoot = Join-Path $repoRoot "app"
$contextRegistryPath = Join-Path $repoRoot "app/context_registry.json"
$m003PreconditionAcceptancePath = "tests/m003/validate_m003_precondition_acceptance.ps1"
$m004PreconditionAcceptancePath = "tests/m004/validate_m004_precondition_acceptance.ps1"
$m005PreconditionAcceptancePath = "tests/m005/validate_m005_precondition_acceptance.ps1"
$m005PreconditionUnitPath = "tests/m005/validate_m005_precondition_unit.ps1"
$m006PreconditionAcceptancePath = "tests/m006/validate_m006_precondition_acceptance.ps1"
$m006PreconditionUnitPath = "tests/m006/validate_m006_precondition_unit.ps1"
$m007PreconditionAcceptancePath = "tests/m007/validate_m007_precondition_acceptance.ps1"
$m007PreconditionUnitPath = "tests/m007/validate_m007_precondition_unit.ps1"
$m008PreconditionAcceptancePath = "tests/m008/validate_m008_precondition_acceptance.ps1"
$m008PreconditionUnitPath = "tests/m008/validate_m008_precondition_unit.ps1"
$m008SpecificationAcceptancePath = "tests/m008/validate_m008_specification_acceptance.ps1"
$m008SpecificationUnitPath = "tests/m008/validate_m008_specification_unit.ps1"
$m008ConversationTurnAcceptancePath = "tests/m008/validate_conversation_turn_append_only_acceptance.ps1"
$m008ConversationTurnUnitPath = "tests/m008/validate_conversation_turn_append_only_unit.ps1"
$m008ContextSnapshotAcceptancePath = "tests/m008/validate_conversation_context_snapshot_acceptance.ps1"
$m008ContextSnapshotUnitPath = "tests/m008/validate_conversation_context_snapshot_unit.ps1"
$m008FollowupResolutionAcceptancePath = "tests/m008/validate_followup_question_resolution_acceptance.ps1"
$m008FollowupResolutionUnitPath = "tests/m008/validate_followup_question_resolution_unit.ps1"
$m008ModeRoutingAcceptancePath = "tests/m008/validate_conversation_mode_routing_acceptance.ps1"
$m008ModeRoutingUnitPath = "tests/m008/validate_conversation_mode_routing_unit.ps1"
$m008VerifiedResultReuseAcceptancePath = "tests/m008/validate_verified_result_reuse_acceptance.ps1"
$m008VerifiedAnswerAttachmentUnitPath = "tests/m008/validate_verified_answer_attachment_unit.ps1"
$m008AnswerPresentationAcceptancePath = "tests/m008/validate_chat_answer_presentation_acceptance.ps1"
$m008AnswerPresentationUnitPath = "tests/m008/validate_chat_answer_presentation_unit.ps1"
$m008ConversationHttpAcceptancePath = "tests/m008/validate_conversation_http_contract_acceptance.ps1"
$m008ConversationHttpUnitPath = "tests/m008/validate_conversation_http_contract_unit.ps1"
$m008ChatCompletionsAcceptancePath = "tests/m008/validate_chat_completions_contract_acceptance.ps1"
$m008ChatCompletionsUnitPath = "tests/m008/validate_chat_completions_contract_unit.ps1"
$m008TraceabilityAcceptancePath = "tests/m008/validate_m008_traceability_acceptance.ps1"
$m008TraceabilityUnitPath = "tests/m008/validate_m008_traceability_unit.ps1"
$m009PreconditionAcceptancePath = "tests/m009/validate_m009_precondition_acceptance.ps1"
$m009PreconditionUnitPath = "tests/m009/validate_m009_precondition_unit.ps1"
$m009SpecificationAcceptancePath = "tests/m009/validate_m009_specification_acceptance.ps1"
$m009SpecificationUnitPath = "tests/m009/validate_m009_specification_unit.ps1"
$m009DeepResearchPlanningAcceptancePath = "tests/m009/validate_deep_research_planning_acceptance.ps1"
$m009DeepResearchPlanningUnitPath = "tests/m009/validate_deep_research_planning_unit.ps1"
$m009MultiQueryEvidenceAcceptancePath = "tests/m009/validate_multi_query_evidence_collection_acceptance.ps1"
$m009MultiQueryEvidenceUnitPath = "tests/m009/validate_multi_query_evidence_collection_unit.ps1"
$m009VerifiedClaimDependencyAcceptancePath = "tests/m009/validate_verified_claim_dependency_resolution_acceptance.ps1"
$m009VerifiedClaimDependencyUnitPath = "tests/m009/validate_verified_claim_dependency_resolution_unit.ps1"
$m009DeepContradictionClassificationAcceptancePath = "tests/m009/validate_deep_contradiction_classification_acceptance.ps1"
$m009DeepContradictionClassificationUnitPath = "tests/m009/validate_deep_contradiction_classification_unit.ps1"
$m009InsufficientDeepCoverageAcceptancePath = "tests/m009/validate_insufficient_deep_coverage_acceptance.ps1"
$m009InsufficientDeepCoverageUnitPath = "tests/m009/validate_insufficient_deep_coverage_unit.ps1"
$m009MultiSourceSynthesisAcceptancePath = "tests/m009/validate_multi_source_synthesis_acceptance.ps1"
$m009MultiSourceSynthesisUnitPath = "tests/m009/validate_multi_source_synthesis_unit.ps1"
$m009DeepResearchHttpAcceptancePath = "tests/m009/validate_deep_research_http_contract_acceptance.ps1"
$m009DeepResearchHttpUnitPath = "tests/m009/validate_deep_research_http_contract_unit.ps1"
$m009DeepResearchMetricsAcceptancePath = "tests/m009/validate_deep_research_metrics_acceptance.ps1"
$m009DeepResearchMetricsUnitPath = "tests/m009/validate_deep_research_metrics_unit.ps1"
$m009TraceabilityAcceptancePath = "tests/m009/validate_m009_traceability_acceptance.ps1"
$m009TraceabilityUnitPath = "tests/m009/validate_m009_traceability_unit.ps1"
$m010PreconditionAcceptancePath = "tests/m010/validate_m010_precondition_acceptance.ps1"
$m010PreconditionUnitPath = "tests/m010/validate_m010_precondition_unit.ps1"
$m010SpecificationAcceptancePath = "tests/m010/validate_m010_specification_acceptance.ps1"
$m010SpecificationUnitPath = "tests/m010/validate_m010_specification_unit.ps1"
$m010StrategyCandidateCreationAcceptancePath = "tests/m010/validate_strategy_candidate_creation_acceptance.ps1"
$m010StrategyCandidateCreationUnitPath = "tests/m010/validate_strategy_candidate_creation_unit.ps1"
$m010StrategyRuleOriginAcceptancePath = "tests/m010/validate_strategy_rule_origin_acceptance.ps1"
$m010StrategyRuleOriginUnitPath = "tests/m010/validate_strategy_rule_origin_unit.ps1"
$m010StrategyParameterCalibrationAcceptancePath = "tests/m010/validate_strategy_parameter_calibration_acceptance.ps1"
$m010StrategyParameterCalibrationUnitPath = "tests/m010/validate_strategy_parameter_calibration_unit.ps1"
$m010StrategyCompatibilityAcceptancePath = "tests/m010/validate_strategy_compatibility_acceptance.ps1"
$m010StrategyCompatibilityUnitPath = "tests/m010/validate_strategy_compatibility_unit.ps1"
$m010StrategyCandidateDiagnosticsAcceptancePath = "tests/m010/validate_strategy_candidate_diagnostics_acceptance.ps1"
$m010StrategyCandidateDiagnosticsUnitPath = "tests/m010/validate_strategy_candidate_diagnostics_unit.ps1"
$m010StrategyCompilationAcceptancePath = "tests/m010/validate_strategy_compilation_acceptance.ps1"
$m010StrategyCompilationUnitPath = "tests/m010/validate_strategy_compilation_unit.ps1"
$m010StrategySnapshotAcceptancePath = "tests/m010/validate_strategy_snapshot_acceptance.ps1"
$m010StrategySnapshotUnitPath = "tests/m010/validate_strategy_snapshot_unit.ps1"
$m010StrategyHttpContractAcceptancePath = "tests/m010/validate_strategy_http_contract_acceptance.ps1"
$m010StrategyHttpContractUnitPath = "tests/m010/validate_strategy_http_contract_unit.ps1"
$m010TraceabilityAcceptancePath = "tests/m010/validate_m010_traceability_acceptance.ps1"
$m010TraceabilityUnitPath = "tests/m010/validate_m010_traceability_unit.ps1"

$validationCommands = @(
    @{ Path = "scripts/validate_m000_precondition_report.ps1"; Arguments = @("-Path", $preconditionReportPath) },
    @{ Path = "scripts/validate_adr_system.ps1"; Arguments = @() },
    @{ Path = "scripts/validate_task_system.ps1"; Arguments = @() },
    @{ Path = "scripts/validate_traceability.ps1"; Arguments = @() },
    @{ Path = "scripts/validate_definition_of_done.ps1"; Arguments = @() },
    @{ Path = "scripts/validate_m001_specification.ps1"; Arguments = @("-Path", $m001SpecificationPath) },
    @{ Path = "scripts/validate_m002_specification.ps1"; Arguments = @("-Path", $m002SpecificationPath) },
    @{ Path = "scripts/validate_m003_specification.ps1"; Arguments = @("-Path", $m003SpecificationPath) },
    @{ Path = "scripts/validate_m004_specification.ps1"; Arguments = @("-Path", $m004SpecificationPath) },
    @{ Path = "scripts/validate_m005_specification.ps1"; Arguments = @("-Path", $m005SpecificationPath) },
    @{ Path = "scripts/validate_m006_specification.ps1"; Arguments = @("-Path", $m006SpecificationPath) },
    @{ Path = "scripts/validate_m007_specification.ps1"; Arguments = @("-Path", $m007SpecificationPath) },
    @{ Path = "scripts/validate_m008_specification.ps1"; Arguments = @("-Path", $m008SpecificationPath) },
    @{ Path = "scripts/validate_m009_specification.ps1"; Arguments = @("-Path", $m009SpecificationPath) },
    @{ Path = "scripts/validate_m010_specification.ps1"; Arguments = @("-Path", $m010SpecificationPath) },
    @{ Path = "scripts/validate_platform_topology.ps1"; Arguments = @("-Path", $platformTopologyPath) },
    @{ Path = "scripts/validate_local_compose.ps1"; Arguments = @() },
    @{ Path = "scripts/validate_network_boundary.ps1"; Arguments = @("-SparkFirewallPath", $sparkFirewallPath) },
    @{ Path = "scripts/validate_architecture_boundaries.ps1"; Arguments = @("-AppRoot", $appRoot, "-ContextRegistryPath", $contextRegistryPath, "-SpecificationPath", $m001SpecificationPath) }
)

# Les tests M-003 ciblés restent exécutés explicitement hors gate pour éviter une récursion.
$testCommands = @(
    @{ Path = "tests/governance/validate_m000_precondition_report_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/governance/validate_m000_precondition_report_unit.ps1"; Arguments = @() },
    @{ Path = "tests/governance/validate_adr_system_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/governance/validate_adr_system_unit.ps1"; Arguments = @() },
    @{ Path = "tests/governance/validate_task_system_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/governance/validate_task_system_unit.ps1"; Arguments = @() },
    @{ Path = "tests/governance/validate_traceability_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/governance/validate_traceability_unit.ps1"; Arguments = @() },
    @{ Path = "tests/governance/validate_definition_of_done_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/governance/validate_definition_of_done_unit.ps1"; Arguments = @() },
    @{ Path = "tests/governance/validate_m000_validation_commands_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m001/validate_m001_specification_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m001/validate_m001_specification_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m001/validate_context_modules_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m001/validate_context_registry_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m001/validate_contract_identity_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m001/validate_contract_identity_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m001/validate_source_contracts_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m001/validate_source_locator_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m001/validate_evidence_claim_contracts_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m001/validate_evidence_claim_contracts_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m001/validate_research_outcome_contract_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m001/validate_research_outcome_contract_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m001/validate_strategy_experiment_contracts_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m001/validate_strategy_experiment_contracts_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m001/validate_event_envelope_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m001/validate_event_envelope_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m001/validate_architecture_boundaries_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m001/validate_architecture_boundaries_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m001/validate_m001_traceability_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m001/validate_m001_traceability_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m002/validate_m002_specification_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m002/validate_m002_specification_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m002/validate_platform_topology_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m002/validate_platform_topology_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m002/validate_local_compose_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m002/validate_local_compose_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m002/validate_network_boundary_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m002/validate_network_boundary_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m002/validate_llm_gateway_contract_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m002/validate_llm_gateway_contract_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m002/validate_llm_gateway_failures_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m002/validate_llm_gateway_failures_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m002/validate_outbox_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m002/validate_outbox_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m002/validate_job_runtime_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m002/validate_job_runtime_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m002/validate_gateway_observability_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m002/validate_gateway_observability_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m002/validate_m002_traceability_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m002/validate_m002_traceability_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_m003_precondition_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_m003_precondition_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_m003_specification_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_m003_specification_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_source_registration_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_source_registration_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_page_manifest_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_page_manifest_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_page_diagnostics_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_page_diagnostics_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_route_plan_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_route_plan_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_review_quarantine_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_review_quarantine_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_document_commands_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_document_commands_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_document_http_contract_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_m003_audit_signals_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_m003_traceability_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m003/validate_m003_traceability_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m004/validate_m004_precondition_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m004/validate_m004_precondition_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m004/validate_m004_specification_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m004/validate_m004_specification_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m004/validate_page_conversion_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m004/validate_page_conversion_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m004/validate_text_authority_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m004/validate_text_authority_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m004/validate_canonical_quality_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m004/validate_canonical_quality_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m004/validate_canonical_publication_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m004/validate_canonical_publication_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m004/validate_source_locator_resolution_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m004/validate_source_locator_resolution_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m004/validate_canonical_publication_event_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m004/validate_canonical_publication_event_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m004/validate_document_conversion_command_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m004/validate_document_conversion_command_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m004/validate_m004_traceability_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m004/validate_m004_traceability_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_m005_precondition_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_m005_precondition_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_m005_specification_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_m005_specification_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_knowledge_projection_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_knowledge_projection_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_index_command_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_hierarchical_chunking_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_hierarchical_chunking_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_projection_metadata_filters_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_projection_metadata_filters_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_projection_encoding_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_projection_encoding_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_qdrant_projection_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_qdrant_projection_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_knowledge_projection_events_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_hybrid_search_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_hybrid_search_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_search_trace_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_search_command_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_search_command_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_m005_traceability_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m005/validate_m005_traceability_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m006/validate_m006_precondition_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m006/validate_m006_precondition_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m006/validate_m006_specification_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m006/validate_m006_specification_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m006/validate_claim_extraction_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m006/validate_claim_extraction_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m006/validate_claim_evidence_attachment_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m006/validate_claim_evidence_attachment_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m006/validate_claim_verification_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m006/validate_claim_verification_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m006/validate_dependency_group_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m006/validate_dependency_group_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m006/validate_claim_relation_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m006/validate_claim_relation_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m006/validate_claim_retention_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m006/validate_claim_retention_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m006/validate_claim_http_contract_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m006/validate_claim_http_contract_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m006/validate_m006_traceability_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m006/validate_m006_traceability_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m007/validate_m007_precondition_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m007/validate_m007_precondition_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m007/validate_m007_specification_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m007/validate_m007_specification_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m007/validate_research_case_mandate_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m007/validate_research_case_mandate_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m007/validate_evidence_set_sealing_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m007/validate_evidence_set_sealing_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m007/validate_contradiction_gap_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m007/validate_contradiction_gap_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m007/validate_answer_assertion_extraction_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m007/validate_answer_assertion_extraction_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m007/validate_answer_support_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m007/validate_answer_support_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m007/validate_current_data_abstention_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m007/validate_current_data_abstention_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m007/validate_answer_http_contract_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m007/validate_answer_http_contract_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m007/validate_m007_traceability_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m007/validate_m007_traceability_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m008/validate_m008_precondition_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m008/validate_m008_precondition_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m008/validate_m008_specification_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m008/validate_m008_specification_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m008/validate_conversation_turn_append_only_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m008/validate_conversation_turn_append_only_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m008/validate_conversation_context_snapshot_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m008/validate_conversation_context_snapshot_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m008/validate_followup_question_resolution_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m008/validate_followup_question_resolution_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m008/validate_conversation_mode_routing_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m008/validate_conversation_mode_routing_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m008/validate_verified_result_reuse_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m008/validate_verified_answer_attachment_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m008/validate_chat_answer_presentation_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m008/validate_chat_answer_presentation_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m008/validate_conversation_http_contract_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m008/validate_conversation_http_contract_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m008/validate_chat_completions_contract_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m008/validate_chat_completions_contract_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m008/validate_m008_traceability_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m008/validate_m008_traceability_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m009/validate_m009_precondition_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m009/validate_m009_precondition_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m010/validate_m010_precondition_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m010/validate_m010_precondition_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m010/validate_m010_specification_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m010/validate_m010_specification_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m010/validate_strategy_candidate_creation_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m010/validate_strategy_candidate_creation_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m010/validate_strategy_rule_origin_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m010/validate_strategy_rule_origin_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m010/validate_strategy_parameter_calibration_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m010/validate_strategy_parameter_calibration_unit.ps1"; Arguments = @() },
    @{ Path = $m010StrategyCompatibilityAcceptancePath; Arguments = @() },
    @{ Path = $m010StrategyCompatibilityUnitPath; Arguments = @() },
    @{ Path = $m010StrategyCandidateDiagnosticsAcceptancePath; Arguments = @() },
    @{ Path = $m010StrategyCandidateDiagnosticsUnitPath; Arguments = @() },
    @{ Path = $m010StrategyCompilationAcceptancePath; Arguments = @() },
    @{ Path = $m010StrategyCompilationUnitPath; Arguments = @() },
    @{ Path = $m010StrategySnapshotAcceptancePath; Arguments = @() },
    @{ Path = $m010StrategySnapshotUnitPath; Arguments = @() },
    @{ Path = $m010StrategyHttpContractAcceptancePath; Arguments = @() },
    @{ Path = $m010StrategyHttpContractUnitPath; Arguments = @() },
    @{ Path = $m010TraceabilityAcceptancePath; Arguments = @() },
    @{ Path = $m010TraceabilityUnitPath; Arguments = @() },
    @{ Path = "tests/m009/validate_m009_specification_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m009/validate_m009_specification_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m009/validate_deep_research_planning_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m009/validate_deep_research_planning_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m009/validate_multi_query_evidence_collection_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m009/validate_multi_query_evidence_collection_unit.ps1"; Arguments = @() },
    @{ Path = "tests/m009/validate_verified_claim_dependency_resolution_acceptance.ps1"; Arguments = @() },
    @{ Path = "tests/m009/validate_verified_claim_dependency_resolution_unit.ps1"; Arguments = @() },
    @{ Path = $m009DeepContradictionClassificationAcceptancePath; Arguments = @() },
    @{ Path = $m009DeepContradictionClassificationUnitPath; Arguments = @() },
    @{ Path = $m009InsufficientDeepCoverageAcceptancePath; Arguments = @() },
    @{ Path = $m009InsufficientDeepCoverageUnitPath; Arguments = @() },
    @{ Path = $m009MultiSourceSynthesisAcceptancePath; Arguments = @() },
    @{ Path = $m009MultiSourceSynthesisUnitPath; Arguments = @() },
    @{ Path = $m009DeepResearchHttpAcceptancePath; Arguments = @() },
    @{ Path = $m009DeepResearchHttpUnitPath; Arguments = @() },
    @{ Path = $m009DeepResearchMetricsAcceptancePath; Arguments = @() },
    @{ Path = $m009DeepResearchMetricsUnitPath; Arguments = @() },
    @{ Path = $m009TraceabilityAcceptancePath; Arguments = @() },
    @{ Path = $m009TraceabilityUnitPath; Arguments = @() }
)

function Get-GateCommandPaths {
    param(
        [Parameter(Mandatory = $true)]
        [object[]] $Commands
    )

    return @($Commands | ForEach-Object { $_.Path })
}

$excludedPreconditionTestPaths = @()
if ($env:OST_M003_PRECONDITION_ACCEPTANCE_RUNNING -eq "1") {
    Write-Host "Test d'acceptation de précondition M-003 exclu explicitement: exécution imbriquée du validateur de précondition."
    Write-Host "Test d'acceptation de précondition M-004 exclu explicitement: M-003 reste indépendant du milestone aval."
    Write-Host "Tests de précondition M-005 exclus explicitement: M-003 reste indépendant du milestone aval."
    Write-Host "Tests de précondition M-006 exclus explicitement: M-003 reste indépendant du milestone aval."
    Write-Host "Tests de précondition M-007 exclus explicitement: M-003 reste indépendant du milestone aval."
    Write-Host "Tests de précondition M-008 exclus explicitement: M-003 reste indépendant du milestone aval."
    Write-Host "Tests de précondition M-009 exclus explicitement: M-003 reste indépendant du milestone aval."
    Write-Host "Tests de précondition M-010 exclus explicitement: M-003 reste indépendant du milestone aval."
    $excludedPreconditionTestPaths = @(
        $m003PreconditionAcceptancePath,
        $m004PreconditionAcceptancePath,
        $m005PreconditionAcceptancePath,
        $m005PreconditionUnitPath,
        $m006PreconditionAcceptancePath,
        $m006PreconditionUnitPath,
        $m007PreconditionAcceptancePath,
        $m007PreconditionUnitPath,
        $m008PreconditionAcceptancePath,
        $m008PreconditionUnitPath,
        $m008SpecificationAcceptancePath,
        $m008SpecificationUnitPath,
        $m008ConversationTurnAcceptancePath,
        $m008ConversationTurnUnitPath,
        $m008ContextSnapshotAcceptancePath,
        $m008ContextSnapshotUnitPath,
        $m008FollowupResolutionAcceptancePath,
        $m008FollowupResolutionUnitPath,
        $m008ModeRoutingAcceptancePath,
        $m008ModeRoutingUnitPath,
        $m008VerifiedResultReuseAcceptancePath,
        $m008VerifiedAnswerAttachmentUnitPath,
        $m008AnswerPresentationAcceptancePath,
        $m008AnswerPresentationUnitPath,
        $m008ConversationHttpAcceptancePath,
        $m008ConversationHttpUnitPath,
        $m008ChatCompletionsAcceptancePath,
        $m008ChatCompletionsUnitPath,
        $m008TraceabilityAcceptancePath,
        $m008TraceabilityUnitPath,
        $m009PreconditionAcceptancePath,
        $m009PreconditionUnitPath,
        $m009SpecificationAcceptancePath,
        $m009SpecificationUnitPath,
        $m009DeepResearchPlanningAcceptancePath,
        $m009DeepResearchPlanningUnitPath,
        $m009MultiQueryEvidenceAcceptancePath,
        $m009MultiQueryEvidenceUnitPath,
        $m009VerifiedClaimDependencyAcceptancePath,
        $m009VerifiedClaimDependencyUnitPath,
        $m009DeepContradictionClassificationAcceptancePath,
        $m009DeepContradictionClassificationUnitPath,
        $m009InsufficientDeepCoverageAcceptancePath,
        $m009InsufficientDeepCoverageUnitPath,
        $m009MultiSourceSynthesisAcceptancePath,
        $m009MultiSourceSynthesisUnitPath,
        $m009DeepResearchHttpAcceptancePath,
        $m009DeepResearchHttpUnitPath,
        $m009DeepResearchMetricsAcceptancePath,
        $m009DeepResearchMetricsUnitPath,
        $m009TraceabilityAcceptancePath,
        $m009TraceabilityUnitPath,
        $m010PreconditionAcceptancePath,
        $m010PreconditionUnitPath,
        $m010SpecificationAcceptancePath,
        $m010SpecificationUnitPath,
        $m010StrategyCandidateCreationAcceptancePath,
        $m010StrategyCandidateCreationUnitPath,
        $m010StrategyRuleOriginAcceptancePath,
        $m010StrategyRuleOriginUnitPath,
        $m010StrategyParameterCalibrationAcceptancePath,
        $m010StrategyParameterCalibrationUnitPath
    )
}
elseif ($env:OST_M004_PRECONDITION_ACCEPTANCE_RUNNING -eq "1") {
    Write-Host "Test d'acceptation de précondition M-004 exclu explicitement: exécution imbriquée du validateur de précondition."
    Write-Host "Tests de précondition M-005 exclus explicitement: M-004 reste indépendant du milestone aval."
    Write-Host "Tests de précondition M-006 exclus explicitement: M-004 reste indépendant du milestone aval."
    Write-Host "Tests de précondition M-007 exclus explicitement: M-004 reste indépendant du milestone aval."
    Write-Host "Tests de précondition M-008 exclus explicitement: M-004 reste indépendant du milestone aval."
    Write-Host "Tests de précondition M-009 exclus explicitement: M-004 reste indépendant du milestone aval."
    Write-Host "Tests de précondition M-010 exclus explicitement: M-004 reste indépendant du milestone aval."
    $excludedPreconditionTestPaths = @(
        $m004PreconditionAcceptancePath,
        $m005PreconditionAcceptancePath,
        $m005PreconditionUnitPath,
        $m006PreconditionAcceptancePath,
        $m006PreconditionUnitPath,
        $m007PreconditionAcceptancePath,
        $m007PreconditionUnitPath,
        $m008PreconditionAcceptancePath,
        $m008PreconditionUnitPath,
        $m008SpecificationAcceptancePath,
        $m008SpecificationUnitPath,
        $m008ConversationTurnAcceptancePath,
        $m008ConversationTurnUnitPath,
        $m008ContextSnapshotAcceptancePath,
        $m008ContextSnapshotUnitPath,
        $m008FollowupResolutionAcceptancePath,
        $m008FollowupResolutionUnitPath,
        $m008ModeRoutingAcceptancePath,
        $m008ModeRoutingUnitPath,
        $m008VerifiedResultReuseAcceptancePath,
        $m008VerifiedAnswerAttachmentUnitPath,
        $m008AnswerPresentationAcceptancePath,
        $m008AnswerPresentationUnitPath,
        $m008ConversationHttpAcceptancePath,
        $m008ConversationHttpUnitPath,
        $m008ChatCompletionsAcceptancePath,
        $m008ChatCompletionsUnitPath,
        $m008TraceabilityAcceptancePath,
        $m008TraceabilityUnitPath,
        $m009PreconditionAcceptancePath,
        $m009PreconditionUnitPath,
        $m009SpecificationAcceptancePath,
        $m009SpecificationUnitPath,
        $m009DeepResearchPlanningAcceptancePath,
        $m009DeepResearchPlanningUnitPath,
        $m009MultiQueryEvidenceAcceptancePath,
        $m009MultiQueryEvidenceUnitPath,
        $m009VerifiedClaimDependencyAcceptancePath,
        $m009VerifiedClaimDependencyUnitPath,
        $m009DeepContradictionClassificationAcceptancePath,
        $m009DeepContradictionClassificationUnitPath,
        $m009InsufficientDeepCoverageAcceptancePath,
        $m009InsufficientDeepCoverageUnitPath,
        $m009MultiSourceSynthesisAcceptancePath,
        $m009MultiSourceSynthesisUnitPath,
        $m009DeepResearchHttpAcceptancePath,
        $m009DeepResearchHttpUnitPath,
        $m009DeepResearchMetricsAcceptancePath,
        $m009DeepResearchMetricsUnitPath,
        $m009TraceabilityAcceptancePath,
        $m009TraceabilityUnitPath,
        $m010PreconditionAcceptancePath,
        $m010PreconditionUnitPath,
        $m010SpecificationAcceptancePath,
        $m010SpecificationUnitPath,
        $m010StrategyCandidateCreationAcceptancePath,
        $m010StrategyCandidateCreationUnitPath,
        $m010StrategyRuleOriginAcceptancePath,
        $m010StrategyRuleOriginUnitPath,
        $m010StrategyParameterCalibrationAcceptancePath,
        $m010StrategyParameterCalibrationUnitPath
    )
}
elseif ($env:OST_M005_PRECONDITION_ACCEPTANCE_RUNNING -eq "1") {
    Write-Host "Test d'acceptation de précondition M-003 exclu explicitement: M-005 s'appuie sur les preuves amont publiées dans master."
    Write-Host "Test d'acceptation de précondition M-004 exclu explicitement: M-005 s'appuie sur les preuves amont publiées dans master."
    Write-Host "Test d'acceptation de précondition M-005 exclu explicitement: exécution imbriquée du validateur de précondition."
    Write-Host "Tests de précondition M-006 exclus explicitement: M-005 reste indépendant du milestone aval."
    Write-Host "Tests de précondition M-007 exclus explicitement: M-005 reste indépendant du milestone aval."
    Write-Host "Tests de précondition M-008 exclus explicitement: M-005 reste indépendant du milestone aval."
    Write-Host "Tests de précondition M-009 exclus explicitement: M-005 reste indépendant du milestone aval."
    Write-Host "Tests de précondition M-010 exclus explicitement: M-005 reste indépendant du milestone aval."
    $excludedPreconditionTestPaths = @(
        $m003PreconditionAcceptancePath,
        $m004PreconditionAcceptancePath,
        $m005PreconditionAcceptancePath,
        $m006PreconditionAcceptancePath,
        $m006PreconditionUnitPath,
        $m007PreconditionAcceptancePath,
        $m007PreconditionUnitPath,
        $m008PreconditionAcceptancePath,
        $m008PreconditionUnitPath,
        $m008SpecificationAcceptancePath,
        $m008SpecificationUnitPath,
        $m008ConversationTurnAcceptancePath,
        $m008ConversationTurnUnitPath,
        $m008ContextSnapshotAcceptancePath,
        $m008ContextSnapshotUnitPath,
        $m008FollowupResolutionAcceptancePath,
        $m008FollowupResolutionUnitPath,
        $m008ModeRoutingAcceptancePath,
        $m008ModeRoutingUnitPath,
        $m008VerifiedResultReuseAcceptancePath,
        $m008VerifiedAnswerAttachmentUnitPath,
        $m008AnswerPresentationAcceptancePath,
        $m008AnswerPresentationUnitPath,
        $m008ConversationHttpAcceptancePath,
        $m008ConversationHttpUnitPath,
        $m008ChatCompletionsAcceptancePath,
        $m008ChatCompletionsUnitPath,
        $m008TraceabilityAcceptancePath,
        $m008TraceabilityUnitPath,
        $m009PreconditionAcceptancePath,
        $m009PreconditionUnitPath,
        $m009SpecificationAcceptancePath,
        $m009SpecificationUnitPath,
        $m009DeepResearchPlanningAcceptancePath,
        $m009DeepResearchPlanningUnitPath,
        $m009MultiQueryEvidenceAcceptancePath,
        $m009MultiQueryEvidenceUnitPath,
        $m009VerifiedClaimDependencyAcceptancePath,
        $m009VerifiedClaimDependencyUnitPath,
        $m009DeepContradictionClassificationAcceptancePath,
        $m009DeepContradictionClassificationUnitPath,
        $m009InsufficientDeepCoverageAcceptancePath,
        $m009InsufficientDeepCoverageUnitPath,
        $m009MultiSourceSynthesisAcceptancePath,
        $m009MultiSourceSynthesisUnitPath,
        $m009DeepResearchHttpAcceptancePath,
        $m009DeepResearchHttpUnitPath,
        $m009DeepResearchMetricsAcceptancePath,
        $m009DeepResearchMetricsUnitPath,
        $m009TraceabilityAcceptancePath,
        $m009TraceabilityUnitPath,
        $m010PreconditionAcceptancePath,
        $m010PreconditionUnitPath,
        $m010SpecificationAcceptancePath,
        $m010SpecificationUnitPath,
        $m010StrategyCandidateCreationAcceptancePath,
        $m010StrategyCandidateCreationUnitPath,
        $m010StrategyRuleOriginAcceptancePath,
        $m010StrategyRuleOriginUnitPath,
        $m010StrategyParameterCalibrationAcceptancePath,
        $m010StrategyParameterCalibrationUnitPath
    )
}
elseif ($env:OST_M006_PRECONDITION_ACCEPTANCE_RUNNING -eq "1") {
    Write-Host "Test d'acceptation de précondition M-003 exclu explicitement: M-006 s'appuie sur les preuves amont publiées dans master."
    Write-Host "Test d'acceptation de précondition M-004 exclu explicitement: M-006 s'appuie sur les preuves amont publiées dans master."
    Write-Host "Test d'acceptation de précondition M-005 exclu explicitement: M-006 s'appuie sur les preuves amont publiées dans master."
    Write-Host "Test d'acceptation de précondition M-006 exclu explicitement: exécution imbriquée du validateur de précondition."
    Write-Host "Tests de précondition M-007 exclus explicitement: M-006 reste indépendant du milestone aval."
    Write-Host "Tests de précondition M-008 exclus explicitement: M-006 reste indépendant du milestone aval."
    Write-Host "Tests de précondition M-009 exclus explicitement: M-006 reste indépendant du milestone aval."
    Write-Host "Tests de précondition M-010 exclus explicitement: M-006 reste indépendant du milestone aval."
    $excludedPreconditionTestPaths = @(
        $m003PreconditionAcceptancePath,
        $m004PreconditionAcceptancePath,
        $m005PreconditionAcceptancePath,
        $m006PreconditionAcceptancePath,
        $m007PreconditionAcceptancePath,
        $m007PreconditionUnitPath,
        $m008PreconditionAcceptancePath,
        $m008PreconditionUnitPath,
        $m008SpecificationAcceptancePath,
        $m008SpecificationUnitPath,
        $m008ConversationTurnAcceptancePath,
        $m008ConversationTurnUnitPath,
        $m008ContextSnapshotAcceptancePath,
        $m008ContextSnapshotUnitPath,
        $m008FollowupResolutionAcceptancePath,
        $m008FollowupResolutionUnitPath,
        $m008ModeRoutingAcceptancePath,
        $m008ModeRoutingUnitPath,
        $m008VerifiedResultReuseAcceptancePath,
        $m008VerifiedAnswerAttachmentUnitPath,
        $m008AnswerPresentationAcceptancePath,
        $m008AnswerPresentationUnitPath,
        $m008ConversationHttpAcceptancePath,
        $m008ConversationHttpUnitPath,
        $m008ChatCompletionsAcceptancePath,
        $m008ChatCompletionsUnitPath,
        $m008TraceabilityAcceptancePath,
        $m008TraceabilityUnitPath,
        $m009PreconditionAcceptancePath,
        $m009PreconditionUnitPath,
        $m009SpecificationAcceptancePath,
        $m009SpecificationUnitPath,
        $m009DeepResearchPlanningAcceptancePath,
        $m009DeepResearchPlanningUnitPath,
        $m009MultiQueryEvidenceAcceptancePath,
        $m009MultiQueryEvidenceUnitPath,
        $m009VerifiedClaimDependencyAcceptancePath,
        $m009VerifiedClaimDependencyUnitPath,
        $m009DeepContradictionClassificationAcceptancePath,
        $m009DeepContradictionClassificationUnitPath,
        $m009InsufficientDeepCoverageAcceptancePath,
        $m009InsufficientDeepCoverageUnitPath,
        $m009MultiSourceSynthesisAcceptancePath,
        $m009MultiSourceSynthesisUnitPath,
        $m009DeepResearchHttpAcceptancePath,
        $m009DeepResearchHttpUnitPath,
        $m009DeepResearchMetricsAcceptancePath,
        $m009DeepResearchMetricsUnitPath,
        $m009TraceabilityAcceptancePath,
        $m009TraceabilityUnitPath,
        $m010PreconditionAcceptancePath,
        $m010PreconditionUnitPath,
        $m010SpecificationAcceptancePath,
        $m010SpecificationUnitPath,
        $m010StrategyCandidateCreationAcceptancePath,
        $m010StrategyCandidateCreationUnitPath,
        $m010StrategyRuleOriginAcceptancePath,
        $m010StrategyRuleOriginUnitPath,
        $m010StrategyParameterCalibrationAcceptancePath,
        $m010StrategyParameterCalibrationUnitPath
    )
}
elseif ($env:OST_M007_PRECONDITION_ACCEPTANCE_RUNNING -eq "1") {
    Write-Host "Test d'acceptation de précondition M-003 exclu explicitement: M-007 s'appuie sur les claims vérifiables M-006 publiés dans master."
    Write-Host "Test d'acceptation de précondition M-004 exclu explicitement: M-007 s'appuie sur les claims vérifiables M-006 publiés dans master."
    Write-Host "Test d'acceptation de précondition M-005 exclu explicitement: M-007 s'appuie sur les claims vérifiables M-006 publiés dans master."
    Write-Host "Test d'acceptation de précondition M-006 exclu explicitement: M-007 s'appuie sur les claims vérifiables M-006 publiés dans master."
    Write-Host "Test d'acceptation de précondition M-007 exclu explicitement: exécution imbriquée du validateur de précondition."
    Write-Host "Tests de précondition M-008 exclus explicitement: M-007 reste indépendant du milestone aval."
    Write-Host "Tests de précondition M-009 exclus explicitement: M-007 reste indépendant du milestone aval."
    Write-Host "Tests de précondition M-010 exclus explicitement: M-007 reste indépendant du milestone aval."
    $excludedPreconditionTestPaths = @(
        $m003PreconditionAcceptancePath,
        $m004PreconditionAcceptancePath,
        $m005PreconditionAcceptancePath,
        $m006PreconditionAcceptancePath,
        $m007PreconditionAcceptancePath,
        $m008PreconditionAcceptancePath,
        $m008PreconditionUnitPath,
        $m008SpecificationAcceptancePath,
        $m008SpecificationUnitPath,
        $m008ConversationTurnAcceptancePath,
        $m008ConversationTurnUnitPath,
        $m008ContextSnapshotAcceptancePath,
        $m008ContextSnapshotUnitPath,
        $m008FollowupResolutionAcceptancePath,
        $m008FollowupResolutionUnitPath,
        $m008ModeRoutingAcceptancePath,
        $m008ModeRoutingUnitPath,
        $m008VerifiedResultReuseAcceptancePath,
        $m008VerifiedAnswerAttachmentUnitPath,
        $m008AnswerPresentationAcceptancePath,
        $m008AnswerPresentationUnitPath,
        $m008ConversationHttpAcceptancePath,
        $m008ConversationHttpUnitPath,
        $m008ChatCompletionsAcceptancePath,
        $m008ChatCompletionsUnitPath,
        $m008TraceabilityAcceptancePath,
        $m008TraceabilityUnitPath,
        $m009PreconditionAcceptancePath,
        $m009PreconditionUnitPath,
        $m009SpecificationAcceptancePath,
        $m009SpecificationUnitPath,
        $m009DeepResearchPlanningAcceptancePath,
        $m009DeepResearchPlanningUnitPath,
        $m009MultiQueryEvidenceAcceptancePath,
        $m009MultiQueryEvidenceUnitPath,
        $m009VerifiedClaimDependencyAcceptancePath,
        $m009VerifiedClaimDependencyUnitPath,
        $m009DeepContradictionClassificationAcceptancePath,
        $m009DeepContradictionClassificationUnitPath,
        $m009InsufficientDeepCoverageAcceptancePath,
        $m009InsufficientDeepCoverageUnitPath,
        $m009MultiSourceSynthesisAcceptancePath,
        $m009MultiSourceSynthesisUnitPath,
        $m009DeepResearchHttpAcceptancePath,
        $m009DeepResearchHttpUnitPath,
        $m009DeepResearchMetricsAcceptancePath,
        $m009DeepResearchMetricsUnitPath,
        $m009TraceabilityAcceptancePath,
        $m009TraceabilityUnitPath,
        $m010PreconditionAcceptancePath,
        $m010PreconditionUnitPath,
        $m010SpecificationAcceptancePath,
        $m010SpecificationUnitPath,
        $m010StrategyCandidateCreationAcceptancePath,
        $m010StrategyCandidateCreationUnitPath,
        $m010StrategyRuleOriginAcceptancePath,
        $m010StrategyRuleOriginUnitPath,
        $m010StrategyParameterCalibrationAcceptancePath,
        $m010StrategyParameterCalibrationUnitPath
    )
}
elseif ($env:OST_M008_PRECONDITION_ACCEPTANCE_RUNNING -eq "1") {
    Write-Host "Test d'acceptation de précondition M-003 exclu explicitement: M-008 s'appuie sur les réponses documentaires vérifiées M-007 publiées dans master."
    Write-Host "Test d'acceptation de précondition M-004 exclu explicitement: M-008 s'appuie sur les réponses documentaires vérifiées M-007 publiées dans master."
    Write-Host "Test d'acceptation de précondition M-005 exclu explicitement: M-008 s'appuie sur les réponses documentaires vérifiées M-007 publiées dans master."
    Write-Host "Test d'acceptation de précondition M-006 exclu explicitement: M-008 s'appuie sur les réponses documentaires vérifiées M-007 publiées dans master."
    Write-Host "Test d'acceptation de précondition M-007 exclu explicitement: M-008 s'appuie sur les réponses documentaires vérifiées M-007 publiées dans master."
    Write-Host "Test d'acceptation de précondition M-008 exclu explicitement: exécution imbriquée du validateur de précondition."
    Write-Host "Tests de précondition M-009 exclus explicitement: M-008 reste indépendant du milestone aval."
    Write-Host "Tests de précondition M-010 exclus explicitement: M-008 reste indépendant du milestone aval."
    $excludedPreconditionTestPaths = @(
        $m003PreconditionAcceptancePath,
        $m004PreconditionAcceptancePath,
        $m005PreconditionAcceptancePath,
        $m006PreconditionAcceptancePath,
        $m007PreconditionAcceptancePath,
        $m008PreconditionAcceptancePath,
        $m009PreconditionAcceptancePath,
        $m009PreconditionUnitPath,
        $m009SpecificationAcceptancePath,
        $m009SpecificationUnitPath,
        $m009DeepResearchPlanningAcceptancePath,
        $m009DeepResearchPlanningUnitPath,
        $m009MultiQueryEvidenceAcceptancePath,
        $m009MultiQueryEvidenceUnitPath,
        $m009VerifiedClaimDependencyAcceptancePath,
        $m009VerifiedClaimDependencyUnitPath,
        $m009DeepContradictionClassificationAcceptancePath,
        $m009DeepContradictionClassificationUnitPath,
        $m009InsufficientDeepCoverageAcceptancePath,
        $m009InsufficientDeepCoverageUnitPath,
        $m009MultiSourceSynthesisAcceptancePath,
        $m009MultiSourceSynthesisUnitPath,
        $m009DeepResearchHttpAcceptancePath,
        $m009DeepResearchHttpUnitPath,
        $m009DeepResearchMetricsAcceptancePath,
        $m009DeepResearchMetricsUnitPath,
        $m009TraceabilityAcceptancePath,
        $m009TraceabilityUnitPath,
        $m010PreconditionAcceptancePath,
        $m010PreconditionUnitPath,
        $m010SpecificationAcceptancePath,
        $m010SpecificationUnitPath,
        $m010StrategyCandidateCreationAcceptancePath,
        $m010StrategyCandidateCreationUnitPath,
        $m010StrategyRuleOriginAcceptancePath,
        $m010StrategyRuleOriginUnitPath,
        $m010StrategyParameterCalibrationAcceptancePath,
        $m010StrategyParameterCalibrationUnitPath
    )
}
elseif ($env:OST_M009_PRECONDITION_ACCEPTANCE_RUNNING -eq "1") {
    Write-Host "Test d'acceptation de précondition M-003 exclu explicitement: M-009 vérifie les validateurs amont sans récursion."
    Write-Host "Test d'acceptation de précondition M-004 exclu explicitement: M-009 vérifie les validateurs amont sans récursion."
    Write-Host "Test d'acceptation de précondition M-005 exclu explicitement: M-009 vérifie les validateurs amont sans récursion."
    Write-Host "Test d'acceptation de précondition M-006 exclu explicitement: M-009 vérifie les validateurs amont sans récursion."
    Write-Host "Test d'acceptation de précondition M-007 exclu explicitement: M-009 vérifie les validateurs amont sans récursion."
    Write-Host "Test d'acceptation de précondition M-008 exclu explicitement: M-009 vérifie les validateurs amont sans récursion."
    Write-Host "Test d'acceptation de précondition M-009 exclu explicitement: exécution imbriquée du validateur de précondition."
    Write-Host "Tests de précondition M-010 exclus explicitement: M-009 reste indépendant du milestone aval."
    $excludedPreconditionTestPaths = @(
        $m003PreconditionAcceptancePath,
        $m004PreconditionAcceptancePath,
        $m005PreconditionAcceptancePath,
        $m006PreconditionAcceptancePath,
        $m007PreconditionAcceptancePath,
        $m008PreconditionAcceptancePath,
        $m009PreconditionAcceptancePath,
        $m009SpecificationAcceptancePath,
        $m009SpecificationUnitPath,
        $m009DeepResearchPlanningAcceptancePath,
        $m009DeepResearchPlanningUnitPath,
        $m009MultiQueryEvidenceAcceptancePath,
        $m009MultiQueryEvidenceUnitPath,
        $m009VerifiedClaimDependencyAcceptancePath,
        $m009VerifiedClaimDependencyUnitPath,
        $m009DeepContradictionClassificationAcceptancePath,
        $m009DeepContradictionClassificationUnitPath,
        $m009InsufficientDeepCoverageAcceptancePath,
        $m009InsufficientDeepCoverageUnitPath,
        $m009MultiSourceSynthesisAcceptancePath,
        $m009MultiSourceSynthesisUnitPath,
        $m009DeepResearchHttpAcceptancePath,
        $m009DeepResearchHttpUnitPath,
        $m009DeepResearchMetricsAcceptancePath,
        $m009DeepResearchMetricsUnitPath,
        $m009TraceabilityAcceptancePath,
        $m009TraceabilityUnitPath,
        $m010PreconditionAcceptancePath,
        $m010PreconditionUnitPath,
        $m010SpecificationAcceptancePath,
        $m010SpecificationUnitPath,
        $m010StrategyCandidateCreationAcceptancePath,
        $m010StrategyCandidateCreationUnitPath,
        $m010StrategyRuleOriginAcceptancePath,
        $m010StrategyRuleOriginUnitPath,
        $m010StrategyParameterCalibrationAcceptancePath,
        $m010StrategyParameterCalibrationUnitPath
    )
}
elseif ($env:OST_M010_PRECONDITION_ACCEPTANCE_RUNNING -eq "1") {
    Write-Host "Test d'acceptation de précondition M-003 exclu explicitement: M-010 vérifie les validateurs amont sans récursion."
    Write-Host "Test d'acceptation de précondition M-004 exclu explicitement: M-010 vérifie les validateurs amont sans récursion."
    Write-Host "Test d'acceptation de précondition M-005 exclu explicitement: M-010 vérifie les validateurs amont sans récursion."
    Write-Host "Test d'acceptation de précondition M-006 exclu explicitement: M-010 vérifie les validateurs amont sans récursion."
    Write-Host "Test d'acceptation de précondition M-007 exclu explicitement: M-010 vérifie les validateurs amont sans récursion."
    Write-Host "Test d'acceptation de précondition M-008 exclu explicitement: M-010 vérifie les validateurs amont sans récursion."
    Write-Host "Test d'acceptation de précondition M-009 exclu explicitement: M-010 vérifie les validateurs amont sans récursion."
    Write-Host "Test d'acceptation de précondition M-010 exclu explicitement: exécution imbriquée du validateur de précondition."
    $excludedPreconditionTestPaths = @(
        $m003PreconditionAcceptancePath,
        $m004PreconditionAcceptancePath,
        $m005PreconditionAcceptancePath,
        $m006PreconditionAcceptancePath,
        $m007PreconditionAcceptancePath,
        $m008PreconditionAcceptancePath,
        $m009PreconditionAcceptancePath,
        $m010PreconditionAcceptancePath,
        $m010SpecificationAcceptancePath,
        $m010SpecificationUnitPath,
        $m010StrategyCandidateCreationAcceptancePath,
        $m010StrategyCandidateCreationUnitPath,
        $m010StrategyRuleOriginAcceptancePath,
        $m010StrategyRuleOriginUnitPath,
        $m010StrategyParameterCalibrationAcceptancePath,
        $m010StrategyParameterCalibrationUnitPath
    )
}

if ($excludedPreconditionTestPaths.Count -gt 0) {
    $testCommands = @(
        $testCommands | Where-Object { $excludedPreconditionTestPaths -notcontains $_.Path }
    )
}

$expectedValidationPaths = Get-GateCommandPaths -Commands $validationCommands
$expectedTestPaths = Get-GateCommandPaths -Commands $testCommands
$expectedValidationCount = $expectedValidationPaths.Count
$expectedTestCount = $expectedTestPaths.Count
Invoke-M000ValidationGate `
    -GateName "test" `
    -RepositoryRoot $repoRoot `
    -ValidationCommands $validationCommands `
    -TestCommands $testCommands `
    -ExpectedValidationCount $expectedValidationCount `
    -ExpectedTestCount $expectedTestCount `
    -ExpectedValidationPaths $expectedValidationPaths `
    -ExpectedTestPaths $expectedTestPaths
