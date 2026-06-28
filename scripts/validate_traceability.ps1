param(
    [Parameter(Mandatory = $false)]
    [string] $Path,

    [Parameter(Mandatory = $false)]
    [switch] $AllowM000OnlyMatrix
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$matrixPath = $Path
$eAcute = [char] 0x00E9
$eGrave = [char] 0x00E8
$cCedilla = [char] 0x00E7
$traceabilityLabel = "tra$($cCedilla)abilit$($eAcute)"

$requiredHeaders = @(
    "Exigence",
    "Source",
    "Statut",
    "Test",
    "Commande",
    "Code",
    "ADR",
    "Justification ADR"
)

$allowedStatuses = @(
    "Couvert",
    "Partiel",
    "Planifi$($eAcute)",
    "Hors p$($eAcute)rim$($eGrave)tre M-000"
)

$requiredM001Requirements = @(
    [ordered] @{
        Id = "REQ-M001-001"
        Source = "docs/tasks/milestone_001/0001_verifier_precondition_green.md"
        Test = "tests/governance/validate_task_system_acceptance.ps1"
        CommandScript = "scripts/validate_task_system.ps1"
        Code = "scripts/validate_task_system.ps1"
        Adr = "ADR-010"
    },
    [ordered] @{
        Id = "REQ-M001-002"
        Source = "docs/tasks/milestone_001/0002_publier_specification_frontieres_ddd.md"
        Test = "tests/m001/validate_m001_specification_acceptance.ps1"
        CommandScript = "scripts/validate_m001_specification.ps1"
        Code = "docs/specs/m001_frontieres_ddd_contrats_publies.md"
        Adr = "DDD-ADR-001; DDD-ADR-002; DDD-ADR-003"
    },
    [ordered] @{
        Id = "REQ-M001-003"
        Source = "docs/tasks/milestone_001/0003_declarer_contextes_proprietaires.md"
        Test = "tests/m001/validate_context_modules_acceptance.ps1"
        CommandScript = "tests/m001/validate_context_modules_acceptance.ps1"
        Code = "app/context_registry.json"
        Adr = "DDD-ADR-001"
    },
    [ordered] @{
        Id = "REQ-M001-004"
        Source = "docs/tasks/milestone_001/0004_publier_identifiants_contrats_communs.md"
        Test = "tests/m001/validate_contract_identity_acceptance.ps1"
        CommandScript = "tests/m001/validate_contract_identity_acceptance.ps1"
        Code = "app/contracts/identity.py"
        Adr = "Non requise"
    },
    [ordered] @{
        Id = "REQ-M001-005"
        Source = "docs/tasks/milestone_001/0005_publier_source_locator_canonical_source_ref.md"
        Test = "tests/m001/validate_source_contracts_acceptance.ps1"
        CommandScript = "tests/m001/validate_source_contracts_acceptance.ps1"
        Code = "app/contracts/source_references.py"
        Adr = "DDD-ADR-003"
    },
    [ordered] @{
        Id = "REQ-M001-006"
        Source = "docs/tasks/milestone_001/0006_publier_contrats_preuves_claims.md"
        Test = "tests/m001/validate_evidence_claim_contracts_acceptance.ps1"
        CommandScript = "tests/m001/validate_evidence_claim_contracts_acceptance.ps1"
        Code = "app/contracts/evidence_claims.py"
        Adr = "DDD-ADR-005"
    },
    [ordered] @{
        Id = "REQ-M001-007"
        Source = "docs/tasks/milestone_001/0007_publier_research_outcome_acl_strategie.md"
        Test = "tests/m001/validate_research_outcome_contract_acceptance.ps1"
        CommandScript = "tests/m001/validate_research_outcome_contract_acceptance.ps1"
        Code = "app/contracts/research_outcomes.py"
        Adr = "DDD-ADR-001; DDD-ADR-002; DDD-ADR-005; DDD-ADR-007"
    },
    [ordered] @{
        Id = "REQ-M001-008"
        Source = "docs/tasks/milestone_001/0008_publier_snapshot_strategie_resultat_experience.md"
        Test = "tests/m001/validate_strategy_experiment_contracts_acceptance.ps1"
        CommandScript = "tests/m001/validate_strategy_experiment_contracts_acceptance.ps1"
        Code = "app/contracts/strategy_experiments.py"
        Adr = "DDD-ADR-009"
    },
    [ordered] @{
        Id = "REQ-M001-009"
        Source = "docs/tasks/milestone_001/0009_publier_enveloppe_evenement_versionnee.md"
        Test = "tests/m001/validate_event_envelope_acceptance.ps1"
        CommandScript = "tests/m001/validate_event_envelope_acceptance.ps1"
        Code = "app/contracts/event_envelope.py"
        Adr = "DDD-ADR-006; DDD-ADR-008"
    },
    [ordered] @{
        Id = "REQ-M001-010"
        Source = "docs/tasks/milestone_001/0010_interdire_couplages_intercontextes.md"
        Test = "tests/m001/validate_architecture_boundaries_acceptance.ps1"
        CommandScript = "tests/m001/validate_architecture_boundaries_acceptance.ps1"
        Code = "scripts/validate_architecture_boundaries.py"
        Adr = "DDD-ADR-001; ADR-011"
    },
    [ordered] @{
        Id = "REQ-M001-011"
        Source = "docs/tasks/milestone_001/0011_relier_m001_tracabilite_gates.md"
        Test = "tests/m001/validate_m001_traceability_acceptance.ps1"
        CommandScript = "scripts/validate_traceability.ps1"
        Code = "scripts/validate_traceability.ps1"
        Adr = "ADR-010"
    }
)

$requiredM002Requirements = @(
    [ordered] @{
        Id = "REQ-M002-001"
        Source = "docs/tasks/milestone_002/0001_verifier_precondition_green.md"
        Test = "tests/m002/validate_m002_precondition_acceptance.ps1"
        CommandScript = "scripts/validate_m002_precondition.ps1"
        Code = "scripts/validate_m002_precondition.ps1"
        Adr = "ADR-010"
    },
    [ordered] @{
        Id = "REQ-M002-002"
        Source = "docs/tasks/milestone_002/0002_publier_specification_plateforme_locale_sure.md"
        Test = "tests/m002/validate_m002_specification_acceptance.ps1"
        CommandScript = "scripts/validate_m002_specification.ps1"
        Code = "docs/specs/m002_plateforme_locale_sure.md"
        Adr = "ADR-007; ADR-008; ADR-009; DDD-ADR-006; DDD-ADR-008; ADR-010"
    },
    [ordered] @{
        Id = "REQ-M002-003"
        Source = "docs/tasks/milestone_002/0003_declarer_topologie_docker_spark.md"
        Test = "tests/m002/validate_platform_topology_acceptance.ps1"
        CommandScript = "scripts/validate_platform_topology.ps1"
        Code = "app/platform/topology_registry.json"
        Adr = "ADR-007; ADR-009; ADR-012"
    },
    [ordered] @{
        Id = "REQ-M002-004"
        Source = "docs/tasks/milestone_002/0004_configurer_stack_docker_locale.md"
        Test = "tests/m002/validate_local_compose_acceptance.ps1"
        CommandScript = "scripts/validate_local_compose.ps1"
        Code = "deploy/local-compose/compose.yaml"
        Adr = "ADR-007; ADR-008; ADR-009; ADR-012"
    },
    [ordered] @{
        Id = "REQ-M002-005"
        Source = "docs/tasks/milestone_002/0005_publier_contrat_gateway_llm.md"
        Test = "tests/m002/validate_llm_gateway_contract_acceptance.ps1"
        CommandScript = "tests/m002/validate_llm_gateway_contract_acceptance.ps1"
        Code = "app/platform/llm_gateway/__init__.py"
        Adr = "ADR-008; ADR-009"
    },
    [ordered] @{
        Id = "REQ-M002-006"
        Source = "docs/tasks/milestone_002/0006_controler_pannes_inference_spark.md"
        Test = "tests/m002/validate_llm_gateway_failures_acceptance.ps1"
        CommandScript = "tests/m002/validate_llm_gateway_failures_acceptance.ps1"
        Code = "app/platform/llm_gateway/__init__.py"
        Adr = "ADR-008; ADR-009; DDD-ADR-007"
    },
    [ordered] @{
        Id = "REQ-M002-007"
        Source = "docs/tasks/milestone_002/0007_livrer_outbox_evenements_idempotente.md"
        Test = "tests/m002/validate_outbox_acceptance.ps1"
        CommandScript = "tests/m002/validate_outbox_acceptance.ps1"
        Code = "app/platform/event_bus/outbox.py"
        Adr = "DDD-ADR-006; DDD-ADR-008"
    },
    [ordered] @{
        Id = "REQ-M002-008"
        Source = "docs/tasks/milestone_002/0008_livrer_file_jobs_priorisee_idempotente.md"
        Test = "tests/m002/validate_job_runtime_acceptance.ps1"
        CommandScript = "tests/m002/validate_job_runtime_acceptance.ps1"
        Code = "app/platform/job_runtime/__init__.py"
        Adr = "DDD-ADR-006; DDD-ADR-008"
    },
    [ordered] @{
        Id = "REQ-M002-009"
        Source = "docs/tasks/milestone_002/0009_verrouiller_frontiere_reseau_locale.md"
        Test = "tests/m002/validate_network_boundary_acceptance.ps1"
        CommandScript = "scripts/validate_network_boundary.ps1"
        Code = "app/platform/security/network_boundary.py"
        Adr = "ADR-007; ADR-008; ADR-009; ADR-012"
    },
    [ordered] @{
        Id = "REQ-M002-010"
        Source = "docs/tasks/milestone_002/0010_observer_gateway_sans_payloads.md"
        Test = "tests/m002/validate_gateway_observability_acceptance.ps1"
        CommandScript = "tests/m002/validate_gateway_observability_acceptance.ps1"
        Code = "app/platform/observability/__init__.py"
        Adr = "ADR-008; ADR-009"
    },
    [ordered] @{
        Id = "REQ-M002-011"
        Source = "docs/tasks/milestone_002/0011_relier_m002_tracabilite_gates.md"
        Test = "tests/m002/validate_m002_traceability_acceptance.ps1"
        CommandScript = "scripts/validate_traceability.ps1"
        Code = "scripts/validate_traceability.ps1"
        Adr = "ADR-010"
    }
)

$requiredM003Requirements = @(
    [ordered] @{
        Id = "REQ-M003-001"
        Source = "docs/tasks/milestone_003/0001_verifier_precondition_green.md"
        Test = "tests/m003/validate_m003_precondition_acceptance.ps1"
        CommandScript = "scripts/validate_m003_precondition.ps1"
        Code = "scripts/validate_m003_precondition.ps1"
        Adr = "ADR-010"
    },
    [ordered] @{
        Id = "REQ-M003-002"
        Source = "docs/tasks/milestone_003/0002_publier_specification_source_routee.md"
        Test = "tests/m003/validate_m003_specification_acceptance.ps1"
        CommandScript = "scripts/validate_m003_specification.ps1"
        Code = "docs/specs/m003_source_enregistree_diagnostiquee_routee.md"
        Adr = "ADR-002; ADR-003; DDD-ADR-003"
    },
    [ordered] @{
        Id = "REQ-M003-003"
        Source = "docs/tasks/milestone_003/0003_enregistrer_source_immuable.md"
        Test = "tests/m003/validate_source_registration_acceptance.ps1"
        CommandScript = "tests/m003/validate_source_registration_acceptance.ps1"
        Code = "app/source_processing/domain/source_document.py"
        Adr = "DDD-ADR-003"
    },
    [ordered] @{
        Id = "REQ-M003-004"
        Source = "docs/tasks/milestone_003/0004_creer_manifeste_pages_complet.md"
        Test = "tests/m003/validate_page_manifest_acceptance.ps1"
        CommandScript = "tests/m003/validate_page_manifest_acceptance.ps1"
        Code = "app/source_processing/domain/document_processing_run.py"
        Adr = "DDD-ADR-003"
    },
    [ordered] @{
        Id = "REQ-M003-005"
        Source = "docs/tasks/milestone_003/0005_diagnostiquer_pages_source.md"
        Test = "tests/m003/validate_page_diagnostics_acceptance.ps1"
        CommandScript = "tests/m003/validate_page_diagnostics_acceptance.ps1"
        Code = "app/source_processing/domain/document_processing_run.py"
        Adr = "ADR-002; ADR-003"
    },
    [ordered] @{
        Id = "REQ-M003-006"
        Source = "docs/tasks/milestone_003/0006_decider_plan_routage_explicite.md"
        Test = "tests/m003/validate_route_plan_acceptance.ps1"
        CommandScript = "tests/m003/validate_route_plan_acceptance.ps1"
        Code = "app/source_processing/domain/document_processing_run.py"
        Adr = "ADR-002; ADR-003"
    },
    [ordered] @{
        Id = "REQ-M003-007"
        Source = "docs/tasks/milestone_003/0007_bloquer_revue_quarantaine.md"
        Test = "tests/m003/validate_review_quarantine_acceptance.ps1"
        CommandScript = "tests/m003/validate_review_quarantine_acceptance.ps1"
        Code = "app/source_processing/domain/document_processing_run.py"
        Adr = "ADR-002; DDD-ADR-003"
    },
    [ordered] @{
        Id = "REQ-M003-008"
        Source = "docs/tasks/milestone_003/0008_exposer_commandes_documents_sp.md"
        Test = "tests/m003/validate_document_commands_acceptance.ps1"
        CommandScript = "tests/m003/validate_document_commands_acceptance.ps1"
        Code = "app/source_processing/application/document_commands.py"
        Adr = "DDD-ADR-003; ADR-010"
    },
    [ordered] @{
        Id = "REQ-M003-009"
        Source = "docs/tasks/milestone_003/0009_relier_m003_tracabilite_gates.md"
        Test = "tests/m003/validate_m003_audit_signals_acceptance.ps1"
        CommandScript = "tests/m003/validate_m003_audit_signals_acceptance.ps1"
        Code = "app/source_processing/application/audit_signals.py"
        Adr = "ADR-002; ADR-003; DDD-ADR-003"
    },
    [ordered] @{
        Id = "REQ-M003-010"
        Source = "docs/tasks/milestone_003/0009_relier_m003_tracabilite_gates.md"
        Test = "tests/m003/validate_m003_traceability_acceptance.ps1"
        CommandScript = "scripts/validate_traceability.ps1"
        Code = "scripts/validate_traceability.ps1"
        Adr = "ADR-010"
    },
    [ordered] @{
        Id = "REQ-M003-011"
        Source = "docs/tasks/milestone_003/0008_exposer_commandes_documents_sp.md"
        Test = "tests/m003/validate_document_http_contract_acceptance.ps1"
        CommandScript = "tests/m003/validate_document_http_contract_acceptance.ps1"
        Code = "app/source_processing/adapters/document_http.py"
        Adr = "DDD-ADR-003; ADR-010"
    }
)

$requiredM004Requirements = @(
    [ordered] @{
        Id = "REQ-M004-001"
        Source = "docs/tasks/milestone_004/0001_verifier_precondition_green.md"
        Test = "tests/m004/validate_m004_precondition_acceptance.ps1"
        CommandScript = "scripts/validate_m004_precondition.ps1"
        Code = "scripts/validate_m004_precondition.ps1"
        Adr = "ADR-010"
    },
    [ordered] @{
        Id = "REQ-M004-002"
        Source = "docs/tasks/milestone_004/0002_publier_specification_version_canonique.md"
        Test = "tests/m004/validate_m004_specification_acceptance.ps1"
        CommandScript = "scripts/validate_m004_specification.ps1"
        Code = "docs/specs/m004_version_canonique_publiee.md"
        Adr = "ADR-001; ADR-002; ADR-003; ADR-004; DDD-ADR-003"
    },
    [ordered] @{
        Id = "REQ-M004-003"
        Source = "docs/tasks/milestone_004/0003_convertir_pages_selon_route_explicite.md"
        Test = "tests/m004/validate_page_conversion_acceptance.ps1"
        CommandScript = "tests/m004/validate_page_conversion_acceptance.ps1"
        Code = "app/source_processing/application/convert_routed_pages.py"
        Adr = "ADR-001; ADR-002; ADR-003; ADR-004; DDD-ADR-003"
    },
    [ordered] @{
        Id = "REQ-M004-004"
        Source = "docs/tasks/milestone_004/0004_adjuger_autorite_textuelle_page.md"
        Test = "tests/m004/validate_text_authority_acceptance.ps1"
        CommandScript = "tests/m004/validate_text_authority_acceptance.ps1"
        Code = "app/source_processing/domain/page_conversion.py"
        Adr = "ADR-004"
    },
    [ordered] @{
        Id = "REQ-M004-005"
        Source = "docs/tasks/milestone_004/0005_controler_qualite_version_canonique.md"
        Test = "tests/m004/validate_canonical_quality_acceptance.ps1"
        CommandScript = "tests/m004/validate_canonical_quality_acceptance.ps1"
        Code = "app/source_processing/domain/page_conversion.py"
        Adr = "ADR-001; ADR-002; ADR-003; ADR-004"
    },
    [ordered] @{
        Id = "REQ-M004-006"
        Source = "docs/tasks/milestone_004/0006_publier_version_canonique_immuable.md"
        Test = "tests/m004/validate_canonical_publication_acceptance.ps1"
        CommandScript = "tests/m004/validate_canonical_publication_acceptance.ps1"
        Code = "app/source_processing/domain/canonical_source.py"
        Adr = "ADR-001; DDD-ADR-003; DDD-ADR-010"
    },
    [ordered] @{
        Id = "REQ-M004-007"
        Source = "docs/tasks/milestone_004/0007_rendre_source_locator_resolvable.md"
        Test = "tests/m004/validate_source_locator_resolution_acceptance.ps1"
        CommandScript = "tests/m004/validate_source_locator_resolution_acceptance.ps1"
        Code = "app/source_processing/application/source_locator_resolution.py"
        Adr = "DDD-ADR-003"
    },
    [ordered] @{
        Id = "REQ-M004-008"
        Source = "docs/tasks/milestone_004/0008_publier_evenement_canonical_source_published.md"
        Test = "tests/m004/validate_canonical_publication_event_acceptance.ps1"
        CommandScript = "tests/m004/validate_canonical_publication_event_acceptance.ps1"
        Code = "app/source_processing/application/publish_canonical_source_event.py"
        Adr = "ADR-001; DDD-ADR-003; DDD-ADR-006; DDD-ADR-008"
    },
    [ordered] @{
        Id = "REQ-M004-009"
        Source = "docs/tasks/milestone_004/0009_exposer_commande_conversion_documentaire.md"
        Test = "tests/m004/validate_document_conversion_command_acceptance.ps1"
        CommandScript = "tests/m004/validate_document_conversion_command_acceptance.ps1"
        Code = "app/source_processing/application/document_commands.py; app/source_processing/adapters/document_http.py"
        Adr = "ADR-010; DDD-ADR-003; DDD-ADR-006; DDD-ADR-008"
    },
    [ordered] @{
        Id = "REQ-M004-010"
        Source = "docs/tasks/milestone_004/0010_relier_m004_tracabilite_gates.md"
        Test = "tests/m004/validate_m004_traceability_acceptance.ps1"
        CommandScript = "tests/m004/validate_m004_traceability_acceptance.ps1"
        Code = "app/source_processing/application/canonical_audit_signals.py"
        Adr = "ADR-001; ADR-004; ADR-010; DDD-ADR-003; DDD-ADR-006; DDD-ADR-008"
    }
)

$requiredM005Requirements = @(
    [ordered] @{
        Id = "REQ-M005-001"
        Source = "docs/tasks/milestone_005/0001_verifier_precondition_green.md"
        Test = "tests/m005/validate_m005_precondition_acceptance.ps1"
        CommandScript = "scripts/validate_m005_precondition.ps1"
        Code = "scripts/validate_m005_precondition.ps1"
        Adr = "ADR-010"
    },
    [ordered] @{
        Id = "REQ-M005-002"
        Source = "docs/tasks/milestone_005/0002_publier_specification_projection_connaissance.md"
        Test = "tests/m005/validate_m005_specification_acceptance.ps1"
        CommandScript = "scripts/validate_m005_specification.ps1"
        Code = "docs/specs/m005_projection_connaissance_recherchable.md"
        Adr = "ADR-005; ADR-006; ADR-010; DDD-ADR-004; DDD-ADR-008"
    },
    [ordered] @{
        Id = "REQ-M005-004"
        Source = "docs/tasks/milestone_005/0005_enrichir_metadonnees_projection_filtrable.md"
        Test = "tests/m005/validate_projection_metadata_filters_acceptance.ps1"
        CommandScript = "tests/m005/validate_projection_metadata_filters_acceptance.ps1"
        Code = "app/knowledge_access/domain/projection_metadata.py"
        Adr = "ADR-005; DDD-ADR-004"
    },
    [ordered] @{
        Id = "REQ-M005-005"
        Source = "docs/tasks/milestone_005/0006_encoder_projection_dense_sparse.md"
        Test = "tests/m005/validate_projection_encoding_acceptance.ps1"
        CommandScript = "tests/m005/validate_projection_encoding_acceptance.ps1"
        Code = "app/knowledge_access/domain/projection_encoding.py; app/knowledge_access/application/encode_projection.py"
        Adr = "ADR-005; ADR-007; ADR-009; DDD-ADR-004"
    },
    [ordered] @{
        Id = "REQ-M005-006"
        Source = "docs/tasks/milestone_005/0007_publier_index_qdrant_regenerable.md"
        Test = "tests/m005/validate_qdrant_projection_acceptance.ps1"
        CommandScript = "tests/m005/validate_qdrant_projection_acceptance.ps1"
        Code = "app/knowledge_access/domain/projection_index.py; app/knowledge_access/application/publish_projection_index.py; app/knowledge_access/application/projection_events.py; app/knowledge_access/adapters/in_memory_vector_index.py"
        Adr = "ADR-005; DDD-ADR-004; DDD-ADR-008"
    }
)

function Assert-Condition {
    param(
        [Parameter(Mandatory = $true)]
        [bool] $Condition,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

function Split-MarkdownRow {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Line
    )

    return @($Line.Trim().Trim("|").Split("|") | ForEach-Object { $_.Trim() })
}

function Assert-RepositoryRelativeFile {
    param(
        [Parameter(Mandatory = $true)]
        [string] $RelativePath,

        [Parameter(Mandatory = $true)]
        [string] $Context
    )

    Assert-Condition `
        -Condition (-not [string]::IsNullOrWhiteSpace($RelativePath)) `
        -Message "Chemin vide dans la matrice: $Context"

    foreach ($path in (Split-MatrixPathCell -RelativePath $RelativePath)) {
        Assert-Condition `
            -Condition (-not [System.IO.Path]::IsPathRooted($path)) `
            -Message "Chemin absolu interdit dans la matrice ($Context): $path"

        $normalizedRelativePath = $path.Replace("/", [System.IO.Path]::DirectorySeparatorChar).Replace("\", [System.IO.Path]::DirectorySeparatorChar)
        $resolvedRepositoryRoot = [System.IO.Path]::GetFullPath($repoRoot)
        $candidatePath = [System.IO.Path]::GetFullPath((Join-Path $resolvedRepositoryRoot $normalizedRelativePath))
        $repositoryPrefix = $resolvedRepositoryRoot.TrimEnd("\", "/") + [System.IO.Path]::DirectorySeparatorChar

        Assert-Condition `
            -Condition ($candidatePath.StartsWith($repositoryPrefix, [System.StringComparison]::OrdinalIgnoreCase)) `
            -Message "Chemin hors dépôt interdit dans la matrice ($Context): $path"

        Assert-Condition `
            -Condition (Test-Path -LiteralPath $candidatePath -PathType Leaf) `
            -Message "Chemin introuvable dans la matrice ($Context): $path"
    }
}

function Split-MatrixPathCell {
    param(
        [Parameter(Mandatory = $true)]
        [string] $RelativePath
    )

    $paths = @($RelativePath.Split(";") | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" })
    Assert-Condition `
        -Condition ($paths.Count -gt 0) `
        -Message "Chemin vide dans la matrice: $RelativePath"
    return $paths
}

function Convert-ToMatrixRelativePath {
    param(
        [Parameter(Mandatory = $true)]
        [string] $RelativePath
    )

    Assert-Condition `
        -Condition (-not [System.IO.Path]::IsPathRooted($RelativePath)) `
        -Message "Chemin absolu interdit dans la matrice: $RelativePath"

    $normalizedRelativePath = $RelativePath.Replace("\", "/")
    if ($normalizedRelativePath.StartsWith("./")) {
        return $normalizedRelativePath.Substring(2)
    }

    return $normalizedRelativePath
}

function Convert-ToMatrixRelativePathCell {
    param(
        [Parameter(Mandatory = $true)]
        [string] $RelativePath
    )

    return ((Split-MatrixPathCell -RelativePath $RelativePath) | ForEach-Object {
        Convert-ToMatrixRelativePath -RelativePath $_
    }) -join "; "
}

function Get-ExistingAdrIds {
    $adrDir = Join-Path $repoRoot "docs/adr"

    Assert-Condition `
        -Condition (Test-Path -LiteralPath $adrDir -PathType Container) `
        -Message "Répertoire ADR absent: docs/adr"

    $ids = New-Object System.Collections.Generic.HashSet[string]

    foreach ($file in (Get-ChildItem -LiteralPath $adrDir -File)) {
        $match = [regex]::Match($file.Name, "^(?<id>(?:DDD-)?ADR-\d{3})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
        if ($match.Success) {
            [void] $ids.Add($match.Groups["id"].Value)
        }
    }

    return $ids
}

function Assert-AdrCell {
    param(
        [Parameter(Mandatory = $true)]
        [string] $AdrCell,

        [Parameter(Mandatory = $true)]
        [string] $Justification,

        [Parameter(Mandatory = $true)]
        [System.Collections.Generic.HashSet[string]] $ExistingAdrIds,

        [Parameter(Mandatory = $true)]
        [string] $RequirementId
    )

    if ($AdrCell -eq "Non requise") {
        Assert-Condition `
            -Condition ($Justification -match "^Aucune d$($eAcute)cision structurante") `
            -Message "Justification ADR insuffisante pour ${RequirementId}: $Justification"
        return
    }

    $adrMatches = [regex]::Matches($AdrCell, "(?:DDD-)?ADR-\d{3}")
    Assert-Condition `
        -Condition ($adrMatches.Count -gt 0) `
        -Message "Cellule ADR invalide pour ${RequirementId}: $AdrCell"

    $remainingText = [regex]::Replace($AdrCell, "(?:DDD-)?ADR-\d{3}", "")
    Assert-Condition `
        -Condition (($remainingText -eq "") -or ($remainingText -match "^[\s,;]+$")) `
        -Message "Cellule ADR invalide pour ${RequirementId}: $AdrCell"

    foreach ($match in $adrMatches) {
        $adrId = $match.Value
        Assert-Condition `
            -Condition ($ExistingAdrIds.Contains($adrId)) `
            -Message "ADR inexistante dans la matrice pour ${RequirementId}: $adrId"
    }
}

function Assert-CommandCell {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Command,

        [Parameter(Mandatory = $true)]
        [string] $Status,

        [Parameter(Mandatory = $true)]
        [string] $RequirementId
    )

    $commandPattern = "^powershell\s+-NoProfile\s+-ExecutionPolicy\s+Bypass\s+-File\s+(?<script>\.?[\\/][^\s;|&]+)(?:\s+-Path\s+(?<pathArg>\.?[\\/][^\s;|&]+))?\s*$"

    if ($Status -eq "Couvert") {
        Assert-Condition `
            -Condition ($Command -match $commandPattern) `
            -Message "Exigence couverte sans commande PowerShell vérifiable: $RequirementId"
    }
    elseif ($Command -match "^Non applicable:\s+\S") {
        return
    }
    else {
        Assert-Condition `
            -Condition ($Command -match $commandPattern) `
            -Message "Commande invalide pour ${RequirementId}: $Command"
    }

    $scriptPath = $Matches["script"]
    $scriptPath = Convert-ToMatrixRelativePath -RelativePath $scriptPath

    Assert-RepositoryRelativeFile `
        -RelativePath $scriptPath `
        -Context "commande ${RequirementId}"

    if ($Matches["pathArg"]) {
        $pathArgument = Convert-ToMatrixRelativePath -RelativePath $Matches["pathArg"]
        Assert-RepositoryRelativeFile `
            -RelativePath $pathArgument `
            -Context "argument -Path ${RequirementId}"
    }

    return $scriptPath
}

function Assert-M000GateProof {
    param(
        [Parameter(Mandatory = $true)]
        [string] $CodePath,

        [Parameter(Mandatory = $true)]
        [string] $TestPath,

        [Parameter(Mandatory = $false)]
        [AllowNull()]
        [string] $CommandScriptPath,

        [Parameter(Mandatory = $true)]
        [string] $RequirementId
    )

    $normalizedCodePaths = @((Split-MatrixPathCell -RelativePath $CodePath) | ForEach-Object {
        Convert-ToMatrixRelativePath -RelativePath $_
    })
    if (@($normalizedCodePaths | Where-Object { $_ -in @("scripts/test.ps1", "scripts/lint.ps1") }).Count -eq 0) {
        return
    }

    $expectedProofPath = "tests/governance/validate_m000_validation_commands_acceptance.ps1"
    $normalizedTestPath = Convert-ToMatrixRelativePath -RelativePath $TestPath
    $normalizedCommandScriptPath = ""

    if ($null -ne $CommandScriptPath) {
        $normalizedCommandScriptPath = Convert-ToMatrixRelativePath -RelativePath $CommandScriptPath
    }

    Assert-Condition `
        -Condition (($normalizedTestPath -eq $expectedProofPath) -and ($normalizedCommandScriptPath -eq $expectedProofPath)) `
        -Message "Preuve de gate M-000 invalide pour ${RequirementId}: test et commande doivent ex$($eAcute)cuter $expectedProofPath"
}

function Get-MatrixRowCell {
    param(
        [Parameter(Mandatory = $true)]
        [object] $Row,

        [Parameter(Mandatory = $true)]
        [string] $CellName,

        [Parameter(Mandatory = $true)]
        [string] $RequirementId
    )

    $property = $Row.PSObject.Properties[$CellName]
    Assert-Condition `
        -Condition ($null -ne $property) `
        -Message "Cellule $CellName introuvable pour ${RequirementId}."

    return [string] $property.Value
}

function Assert-M001PathCell {
    param(
        [Parameter(Mandatory = $true)]
        [object] $Row,

        [Parameter(Mandatory = $true)]
        [string] $RequirementId,

        [Parameter(Mandatory = $true)]
        [string] $CellName,

        [Parameter(Mandatory = $true)]
        [string] $ExpectedValue
    )

    $actualValue = Convert-ToMatrixRelativePath -RelativePath (Get-MatrixRowCell -Row $Row -CellName $CellName -RequirementId $RequirementId)

    Assert-Condition `
        -Condition ($actualValue -eq $ExpectedValue) `
        -Message "$CellName M-001 invalide pour ${RequirementId}. Attendu: $ExpectedValue. Obtenu: $actualValue"
}

function Test-M001MilestoneIsPresent {
    $milestoneDir = Join-Path $repoRoot "docs/tasks/milestone_001"
    return (Test-Path -LiteralPath $milestoneDir -PathType Container)
}

function Assert-M001RequirementRows {
    param(
        [Parameter(Mandatory = $true)]
        [object[]] $Rows
    )

    if (-not (Test-M001MilestoneIsPresent)) {
        return
    }

    $canonicalMatrixPath = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "docs/traceability/matrix.md"))
    $currentMatrixPath = [System.IO.Path]::GetFullPath($matrixPath)
    if (-not $currentMatrixPath.Equals($canonicalMatrixPath, [System.StringComparison]::OrdinalIgnoreCase)) {
        $containsM001Rows = @($Rows | Where-Object {
            (Get-MatrixRowCell -Row $_ -CellName "Exigence" -RequirementId "ligne inconnue") -match "^REQ-M001-"
        }).Count -gt 0
        if (-not $containsM001Rows) {
            Assert-Condition `
                -Condition $AllowM000OnlyMatrix `
                -Message "Matrice M-001 absente sans autorisation explicite."
            return
        }
    }

    $rowsByRequirementId = @{}
    foreach ($row in $Rows) {
        $requirementId = Get-MatrixRowCell -Row $row -CellName "Exigence" -RequirementId "ligne inconnue"
        $rowsByRequirementId[$requirementId] = $row
    }

    foreach ($expected in $requiredM001Requirements) {
        $requirementId = $expected["Id"]

        Assert-Condition `
            -Condition ($rowsByRequirementId.ContainsKey($requirementId)) `
            -Message "Exigence M-001 livr$($eAcute)e absente: $requirementId"

        $row = $rowsByRequirementId[$requirementId]
        $status = Get-MatrixRowCell -Row $row -CellName "Statut" -RequirementId $requirementId

        Assert-Condition `
            -Condition ($status -eq "Couvert") `
            -Message "Exigence M-001 livr$($eAcute)e non couverte: $requirementId"

        Assert-M001PathCell -Row $row -RequirementId $requirementId -CellName "Source" -ExpectedValue $expected["Source"]
        Assert-M001PathCell -Row $row -RequirementId $requirementId -CellName "Test" -ExpectedValue $expected["Test"]
        Assert-M001PathCell -Row $row -RequirementId $requirementId -CellName "Code" -ExpectedValue $expected["Code"]

        $commandScript = Get-MatrixRowCell -Row $row -CellName "CommandeScript" -RequirementId $requirementId
        Assert-Condition `
            -Condition ($commandScript -eq $expected["CommandScript"]) `
            -Message "Commande M-001 invalide pour ${requirementId}. Attendu: $($expected["CommandScript"]). Obtenu: $commandScript"

        $adr = Get-MatrixRowCell -Row $row -CellName "ADR" -RequirementId $requirementId
        Assert-Condition `
            -Condition ($adr -eq $expected["Adr"]) `
            -Message "ADR M-001 invalide pour ${requirementId}. Attendu: $($expected["Adr"]). Obtenu: $adr"

        $justification = Get-MatrixRowCell -Row $row -CellName "Justification ADR" -RequirementId $requirementId
        if ($adr -eq "Non requise") {
            Assert-Condition `
                -Condition ($justification -match "^Aucune d$($eAcute)cision structurante nouvelle") `
                -Message "Justification ADR M-001 invalide pour ${requirementId}: $justification"
        }
        else {
            Assert-Condition `
                -Condition ($justification -match "^D$($eAcute)cision structurante document$($eAcute)e:") `
                -Message "Justification ADR M-001 invalide pour ${requirementId}: $justification"
        }
    }
}

function Assert-M002PathCell {
    param(
        [Parameter(Mandatory = $true)]
        [object] $Row,

        [Parameter(Mandatory = $true)]
        [string] $RequirementId,

        [Parameter(Mandatory = $true)]
        [string] $CellName,

        [Parameter(Mandatory = $true)]
        [string] $ExpectedValue
    )

    $actualValue = Convert-ToMatrixRelativePath -RelativePath (Get-MatrixRowCell -Row $Row -CellName $CellName -RequirementId $RequirementId)

    Assert-Condition `
        -Condition ($actualValue -eq $ExpectedValue) `
        -Message "$CellName M-002 invalide pour ${RequirementId}. Attendu: $ExpectedValue. Obtenu: $actualValue"
}

function Test-M002MilestoneIsPresent {
    $milestoneDir = Join-Path $repoRoot "docs/tasks/milestone_002"
    return (Test-Path -LiteralPath $milestoneDir -PathType Container)
}

function Assert-M002RequirementRows {
    param(
        [Parameter(Mandatory = $true)]
        [object[]] $Rows
    )

    if (-not (Test-M002MilestoneIsPresent)) {
        return
    }

    $canonicalMatrixPath = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "docs/traceability/matrix.md"))
    $currentMatrixPath = [System.IO.Path]::GetFullPath($matrixPath)
    if (-not $currentMatrixPath.Equals($canonicalMatrixPath, [System.StringComparison]::OrdinalIgnoreCase)) {
        $containsM002Rows = @($Rows | Where-Object {
            (Get-MatrixRowCell -Row $_ -CellName "Exigence" -RequirementId "ligne inconnue") -match "^REQ-M002-"
        }).Count -gt 0
        if (-not $containsM002Rows) {
            Assert-Condition `
                -Condition $AllowM000OnlyMatrix `
                -Message "Matrice M-002 absente sans autorisation explicite."
            return
        }
    }

    $rowsByRequirementId = @{}
    foreach ($row in $Rows) {
        $requirementId = Get-MatrixRowCell -Row $row -CellName "Exigence" -RequirementId "ligne inconnue"
        $rowsByRequirementId[$requirementId] = $row
    }

    foreach ($expected in $requiredM002Requirements) {
        $requirementId = $expected["Id"]

        Assert-Condition `
            -Condition ($rowsByRequirementId.ContainsKey($requirementId)) `
            -Message "Exigence M-002 livr$($eAcute)e absente: $requirementId"

        $row = $rowsByRequirementId[$requirementId]
        $status = Get-MatrixRowCell -Row $row -CellName "Statut" -RequirementId $requirementId

        Assert-Condition `
            -Condition ($status -eq "Couvert") `
            -Message "Exigence M-002 livr$($eAcute)e non couverte: $requirementId"

        Assert-M002PathCell -Row $row -RequirementId $requirementId -CellName "Source" -ExpectedValue $expected["Source"]
        Assert-M002PathCell -Row $row -RequirementId $requirementId -CellName "Test" -ExpectedValue $expected["Test"]
        Assert-M002PathCell -Row $row -RequirementId $requirementId -CellName "Code" -ExpectedValue $expected["Code"]

        $commandScript = Get-MatrixRowCell -Row $row -CellName "CommandeScript" -RequirementId $requirementId
        Assert-Condition `
            -Condition ($commandScript -eq $expected["CommandScript"]) `
            -Message "Commande M-002 invalide pour ${requirementId}. Attendu: $($expected["CommandScript"]). Obtenu: $commandScript"

        $adr = Get-MatrixRowCell -Row $row -CellName "ADR" -RequirementId $requirementId
        Assert-Condition `
            -Condition ($adr -eq $expected["Adr"]) `
            -Message "ADR M-002 invalide pour ${requirementId}. Attendu: $($expected["Adr"]). Obtenu: $adr"

        $justification = Get-MatrixRowCell -Row $row -CellName "Justification ADR" -RequirementId $requirementId
        Assert-Condition `
            -Condition ($justification -match "^D$($eAcute)cision structurante document$($eAcute)e:") `
            -Message "Justification ADR M-002 invalide pour ${requirementId}: $justification"
    }
}

function Assert-M003PathCell {
    param(
        [Parameter(Mandatory = $true)]
        [object] $Row,

        [Parameter(Mandatory = $true)]
        [string] $RequirementId,

        [Parameter(Mandatory = $true)]
        [string] $CellName,

        [Parameter(Mandatory = $true)]
        [string] $ExpectedValue
    )

    $actualValue = Convert-ToMatrixRelativePath -RelativePath (Get-MatrixRowCell -Row $Row -CellName $CellName -RequirementId $RequirementId)

    Assert-Condition `
        -Condition ($actualValue -eq $ExpectedValue) `
        -Message "$CellName M-003 invalide pour ${RequirementId}. Attendu: $ExpectedValue. Obtenu: $actualValue"
}

function Test-M003MilestoneIsPresent {
    $milestoneDir = Join-Path $repoRoot "docs/tasks/milestone_003"
    return (Test-Path -LiteralPath $milestoneDir -PathType Container)
}

function Assert-M003RequirementRows {
    param(
        [Parameter(Mandatory = $true)]
        [object[]] $Rows
    )

    if (-not (Test-M003MilestoneIsPresent)) {
        return
    }

    $canonicalMatrixPath = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "docs/traceability/matrix.md"))
    $currentMatrixPath = [System.IO.Path]::GetFullPath($matrixPath)
    if (-not $currentMatrixPath.Equals($canonicalMatrixPath, [System.StringComparison]::OrdinalIgnoreCase)) {
        $containsM003Rows = @($Rows | Where-Object {
            (Get-MatrixRowCell -Row $_ -CellName "Exigence" -RequirementId "ligne inconnue") -match "^REQ-M003-"
        }).Count -gt 0
        if (-not $containsM003Rows) {
            Assert-Condition `
                -Condition $AllowM000OnlyMatrix `
                -Message "Matrice M-003 absente sans autorisation explicite."
            return
        }
    }

    $rowsByRequirementId = @{}
    foreach ($row in $Rows) {
        $requirementId = Get-MatrixRowCell -Row $row -CellName "Exigence" -RequirementId "ligne inconnue"
        $rowsByRequirementId[$requirementId] = $row
    }

    foreach ($expected in $requiredM003Requirements) {
        $requirementId = $expected["Id"]

        Assert-Condition `
            -Condition ($rowsByRequirementId.ContainsKey($requirementId)) `
            -Message "Exigence M-003 livr$($eAcute)e absente: $requirementId"

        $row = $rowsByRequirementId[$requirementId]
        $status = Get-MatrixRowCell -Row $row -CellName "Statut" -RequirementId $requirementId

        Assert-Condition `
            -Condition ($status -eq "Couvert") `
            -Message "Exigence M-003 livr$($eAcute)e non couverte: $requirementId"

        $commandScript = Get-MatrixRowCell -Row $row -CellName "CommandeScript" -RequirementId $requirementId

        Assert-M003PathCell -Row $row -RequirementId $requirementId -CellName "Source" -ExpectedValue $expected["Source"]
        Assert-M003PathCell -Row $row -RequirementId $requirementId -CellName "Test" -ExpectedValue $expected["Test"]
        Assert-M003PathCell -Row $row -RequirementId $requirementId -CellName "Code" -ExpectedValue $expected["Code"]

        Assert-Condition `
            -Condition ($commandScript -eq $expected["CommandScript"]) `
            -Message "Commande M-003 invalide pour ${requirementId}. Attendu: $($expected["CommandScript"]). Obtenu: $commandScript"

        $adr = Get-MatrixRowCell -Row $row -CellName "ADR" -RequirementId $requirementId
        Assert-Condition `
            -Condition ($adr -eq $expected["Adr"]) `
            -Message "ADR M-003 invalide pour ${requirementId}. Attendu: $($expected["Adr"]). Obtenu: $adr"

        $justification = Get-MatrixRowCell -Row $row -CellName "Justification ADR" -RequirementId $requirementId
        Assert-Condition `
            -Condition ($justification -match "^D$($eAcute)cision structurante document$($eAcute)e:") `
            -Message "Justification ADR M-003 invalide pour ${requirementId}: $justification"
    }
}

function Assert-M004PathCell {
    param(
        [Parameter(Mandatory = $true)]
        [object] $Row,

        [Parameter(Mandatory = $true)]
        [string] $RequirementId,

        [Parameter(Mandatory = $true)]
        [string] $CellName,

        [Parameter(Mandatory = $true)]
        [string] $ExpectedValue
    )

    $actualValue = Convert-ToMatrixRelativePathCell -RelativePath (Get-MatrixRowCell -Row $Row -CellName $CellName -RequirementId $RequirementId)

    Assert-Condition `
        -Condition ($actualValue -eq $ExpectedValue) `
        -Message "$CellName M-004 invalide pour ${RequirementId}. Attendu: $ExpectedValue. Obtenu: $actualValue"
}

function Test-M004MilestoneIsPresent {
    $milestoneDir = Join-Path $repoRoot "docs/tasks/milestone_004"
    return (Test-Path -LiteralPath $milestoneDir -PathType Container)
}

function Assert-M004RequirementRows {
    param(
        [Parameter(Mandatory = $true)]
        [object[]] $Rows
    )

    if (-not (Test-M004MilestoneIsPresent)) {
        return
    }

    $canonicalMatrixPath = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "docs/traceability/matrix.md"))
    $currentMatrixPath = [System.IO.Path]::GetFullPath($matrixPath)
    if (-not $currentMatrixPath.Equals($canonicalMatrixPath, [System.StringComparison]::OrdinalIgnoreCase)) {
        $containsM004Rows = @($Rows | Where-Object {
            (Get-MatrixRowCell -Row $_ -CellName "Exigence" -RequirementId "ligne inconnue") -match "^REQ-M004-"
        }).Count -gt 0
        if (-not $containsM004Rows) {
            Assert-Condition `
                -Condition $AllowM000OnlyMatrix `
                -Message "Matrice M-004 absente sans autorisation explicite."
            return
        }
    }

    $rowsByRequirementId = @{}
    foreach ($row in $Rows) {
        $requirementId = Get-MatrixRowCell -Row $row -CellName "Exigence" -RequirementId "ligne inconnue"
        $rowsByRequirementId[$requirementId] = $row
    }

    foreach ($expected in $requiredM004Requirements) {
        $requirementId = $expected["Id"]

        Assert-Condition `
            -Condition ($rowsByRequirementId.ContainsKey($requirementId)) `
            -Message "Exigence M-004 livr$($eAcute)e absente: $requirementId"

        $row = $rowsByRequirementId[$requirementId]
        $status = Get-MatrixRowCell -Row $row -CellName "Statut" -RequirementId $requirementId

        Assert-Condition `
            -Condition ($status -eq "Couvert") `
            -Message "Exigence M-004 livr$($eAcute)e non couverte: $requirementId"

        $commandScript = Get-MatrixRowCell -Row $row -CellName "CommandeScript" -RequirementId $requirementId

        Assert-M004PathCell -Row $row -RequirementId $requirementId -CellName "Source" -ExpectedValue $expected["Source"]
        Assert-M004PathCell -Row $row -RequirementId $requirementId -CellName "Test" -ExpectedValue $expected["Test"]
        Assert-M004PathCell -Row $row -RequirementId $requirementId -CellName "Code" -ExpectedValue $expected["Code"]

        Assert-Condition `
            -Condition ($commandScript -eq $expected["CommandScript"]) `
            -Message "Commande M-004 invalide pour ${requirementId}. Attendu: $($expected["CommandScript"]). Obtenu: $commandScript"

        $adr = Get-MatrixRowCell -Row $row -CellName "ADR" -RequirementId $requirementId
        Assert-Condition `
            -Condition ($adr -eq $expected["Adr"]) `
            -Message "ADR M-004 invalide pour ${requirementId}. Attendu: $($expected["Adr"]). Obtenu: $adr"

        $justification = Get-MatrixRowCell -Row $row -CellName "Justification ADR" -RequirementId $requirementId
        Assert-Condition `
            -Condition ($justification -match "^D$($eAcute)cision structurante document$($eAcute)e:") `
            -Message "Justification ADR M-004 invalide pour ${requirementId}: $justification"
    }
}

function Assert-M005PathCell {
    param(
        [Parameter(Mandatory = $true)]
        [object] $Row,

        [Parameter(Mandatory = $true)]
        [string] $RequirementId,

        [Parameter(Mandatory = $true)]
        [string] $CellName,

        [Parameter(Mandatory = $true)]
        [string] $ExpectedValue
    )

    $actualValue = Convert-ToMatrixRelativePathCell -RelativePath (Get-MatrixRowCell -Row $Row -CellName $CellName -RequirementId $RequirementId)

    Assert-Condition `
        -Condition ($actualValue -eq $ExpectedValue) `
        -Message "$CellName M-005 invalide pour ${RequirementId}. Attendu: $ExpectedValue. Obtenu: $actualValue"
}

function Test-M005MilestoneIsPresent {
    $milestoneDir = Join-Path $repoRoot "docs/tasks/milestone_005"
    return (Test-Path -LiteralPath $milestoneDir -PathType Container)
}

function Assert-M005RequirementRows {
    param(
        [Parameter(Mandatory = $true)]
        [object[]] $Rows
    )

    if (-not (Test-M005MilestoneIsPresent)) {
        return
    }

    $canonicalMatrixPath = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "docs/traceability/matrix.md"))
    $currentMatrixPath = [System.IO.Path]::GetFullPath($matrixPath)
    if (-not $currentMatrixPath.Equals($canonicalMatrixPath, [System.StringComparison]::OrdinalIgnoreCase)) {
        $containsM005Rows = @($Rows | Where-Object {
            (Get-MatrixRowCell -Row $_ -CellName "Exigence" -RequirementId "ligne inconnue") -match "^REQ-M005-"
        }).Count -gt 0
        if (-not $containsM005Rows) {
            Assert-Condition `
                -Condition $AllowM000OnlyMatrix `
                -Message "Matrice M-005 absente sans autorisation explicite."
            return
        }
    }

    $rowsByRequirementId = @{}
    foreach ($row in $Rows) {
        $requirementId = Get-MatrixRowCell -Row $row -CellName "Exigence" -RequirementId "ligne inconnue"
        $rowsByRequirementId[$requirementId] = $row
    }

    foreach ($expected in $requiredM005Requirements) {
        $requirementId = $expected["Id"]

        Assert-Condition `
            -Condition ($rowsByRequirementId.ContainsKey($requirementId)) `
            -Message "Exigence M-005 livrée absente: $requirementId"

        $row = $rowsByRequirementId[$requirementId]
        $status = Get-MatrixRowCell -Row $row -CellName "Statut" -RequirementId $requirementId

        Assert-Condition `
            -Condition ($status -eq "Couvert") `
            -Message "Exigence M-005 livrée non couverte: $requirementId"

        $commandScript = Get-MatrixRowCell -Row $row -CellName "CommandeScript" -RequirementId $requirementId

        Assert-M005PathCell -Row $row -RequirementId $requirementId -CellName "Source" -ExpectedValue $expected["Source"]
        Assert-M005PathCell -Row $row -RequirementId $requirementId -CellName "Test" -ExpectedValue $expected["Test"]
        Assert-M005PathCell -Row $row -RequirementId $requirementId -CellName "Code" -ExpectedValue $expected["Code"]

        Assert-Condition `
            -Condition ($commandScript -eq $expected["CommandScript"]) `
            -Message "Commande M-005 invalide pour ${requirementId}. Attendu: $($expected["CommandScript"]). Obtenu: $commandScript"

        $adr = Get-MatrixRowCell -Row $row -CellName "ADR" -RequirementId $requirementId
        Assert-Condition `
            -Condition ($adr -eq $expected["Adr"]) `
            -Message "ADR M-005 invalide pour ${requirementId}. Attendu: $($expected["Adr"]). Obtenu: $adr"

        $justification = Get-MatrixRowCell -Row $row -CellName "Justification ADR" -RequirementId $requirementId
        Assert-Condition `
            -Condition ($justification -match "^Décision structurante documentée:") `
            -Message "Justification ADR M-005 invalide pour ${requirementId}: $justification"
    }
}

if (-not $PSBoundParameters.ContainsKey("Path")) {
    $matrixPath = Join-Path $repoRoot "docs/traceability/matrix.md"
}
else {
    Assert-Condition `
        -Condition (-not [string]::IsNullOrWhiteSpace($matrixPath)) `
        -Message "Chemin de matrice vide."

    if (-not [System.IO.Path]::IsPathRooted($matrixPath)) {
        $matrixPath = Join-Path $repoRoot $matrixPath
    }

    $resolvedRepositoryRoot = [System.IO.Path]::GetFullPath($repoRoot)
    $resolvedMatrixPath = [System.IO.Path]::GetFullPath($matrixPath)
    $repositoryPrefix = $resolvedRepositoryRoot.TrimEnd("\", "/") + [System.IO.Path]::DirectorySeparatorChar

    Assert-Condition `
        -Condition ($resolvedMatrixPath.StartsWith($repositoryPrefix, [System.StringComparison]::OrdinalIgnoreCase)) `
        -Message "Chemin hors depot interdit (matrice): $resolvedMatrixPath"

    $matrixPath = $resolvedMatrixPath
}

Assert-Condition `
    -Condition (Test-Path -LiteralPath $matrixPath -PathType Leaf) `
    -Message "Matrice de $traceabilityLabel absente: $matrixPath"

$content = Get-Content -Encoding UTF8 -LiteralPath $matrixPath
$headerIndex = -1

for ($index = 0; $index -lt $content.Count; $index++) {
    if ($content[$index] -match "^\|\s*Exigence\s*\|") {
        $headerIndex = $index
        break
    }
}

Assert-Condition `
    -Condition ($headerIndex -ge 0) `
    -Message "En-tête de matrice introuvable."

$headers = Split-MarkdownRow -Line $content[$headerIndex]

Assert-Condition `
    -Condition ($headers.Count -eq $requiredHeaders.Count) `
    -Message "Nombre de colonnes invalide dans la matrice."

for ($index = 0; $index -lt $requiredHeaders.Count; $index++) {
    Assert-Condition `
        -Condition ($headers[$index] -eq $requiredHeaders[$index]) `
        -Message "Colonne invalide dans la matrice. Attendu: $($requiredHeaders[$index]). Obtenu: $($headers[$index])"
}

Assert-Condition `
    -Condition (($headerIndex + 1) -lt $content.Count) `
    -Message "Séparateur de table absent dans la matrice."

$separatorCells = Split-MarkdownRow -Line $content[$headerIndex + 1]
Assert-Condition `
    -Condition (($separatorCells.Count -eq $requiredHeaders.Count) -and (@($separatorCells | Where-Object { $_ -notmatch "^-{3,}$" }).Count -eq 0)) `
    -Message "Séparateur de table invalide dans la matrice."

$existingAdrIds = Get-ExistingAdrIds
$requirementIds = New-Object System.Collections.Generic.HashSet[string]
$rows = New-Object System.Collections.Generic.List[object]

for ($index = $headerIndex + 2; $index -lt $content.Count; $index++) {
    $line = $content[$index]

    if ($line -notmatch "^\|") {
        continue
    }

    $cells = Split-MarkdownRow -Line $line
    Assert-Condition `
        -Condition ($cells.Count -eq $requiredHeaders.Count) `
        -Message "Ligne de matrice avec nombre de cellules invalide: $line"

    for ($cellIndex = 0; $cellIndex -lt $cells.Count; $cellIndex++) {
        Assert-Condition `
            -Condition (-not [string]::IsNullOrWhiteSpace($cells[$cellIndex])) `
            -Message "Cellule vide dans la matrice, colonne $($requiredHeaders[$cellIndex]), ligne $($index + 1)."
    }

    $row = [ordered] @{}
    for ($cellIndex = 0; $cellIndex -lt $requiredHeaders.Count; $cellIndex++) {
        $row[$requiredHeaders[$cellIndex]] = $cells[$cellIndex]
    }

    $requirementId = $row["Exigence"]
    Assert-Condition `
        -Condition ($requirementId -match "^REQ-[A-Z0-9]+(?:-[A-Z0-9]+)*-\d{3}$") `
        -Message "Identifiant d'exigence invalide: $requirementId"

    Assert-Condition `
        -Condition ($requirementIds.Add($requirementId)) `
        -Message "Identifiant d'exigence dupliqué: $requirementId"

    $status = $row["Statut"]
    Assert-Condition `
        -Condition ($allowedStatuses -contains $status) `
        -Message "Statut de traçabilité non autorisé pour ${requirementId}: $status"

    Assert-RepositoryRelativeFile -RelativePath $row["Source"] -Context "source ${requirementId}"
    Assert-RepositoryRelativeFile -RelativePath $row["Test"] -Context "test ${requirementId}"
    Assert-RepositoryRelativeFile -RelativePath $row["Code"] -Context "code ${requirementId}"

    $commandScriptPath = Assert-CommandCell -Command $row["Commande"] -Status $status -RequirementId $requirementId
    $row["CommandeScript"] = if ($null -eq $commandScriptPath) { "" } else { $commandScriptPath }
    Assert-M000GateProof -CodePath $row["Code"] -TestPath $row["Test"] -CommandScriptPath $commandScriptPath -RequirementId $requirementId
    Assert-AdrCell -AdrCell $row["ADR"] -Justification $row["Justification ADR"] -ExistingAdrIds $existingAdrIds -RequirementId $requirementId

    $rows.Add([pscustomobject] $row)
}

Assert-Condition `
    -Condition ($rows.Count -gt 0) `
    -Message "Aucune exigence n'est déclarée dans la matrice de traçabilité."

Assert-M001RequirementRows -Rows $rows.ToArray()
Assert-M002RequirementRows -Rows $rows.ToArray()
Assert-M003RequirementRows -Rows $rows.ToArray()
Assert-M004RequirementRows -Rows $rows.ToArray()
Assert-M005RequirementRows -Rows $rows.ToArray()

Write-Host "Matrice de $traceabilityLabel valide: $($rows.Count) exigence(s) contr$([char] 0x00F4)l$($eAcute)e(s)."
