$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$matrixPath = Join-Path $repoRoot "docs/traceability/matrix.md"
$traceabilityValidatorPath = Join-Path $repoRoot "scripts/validate_traceability.ps1"
$testGatePath = Join-Path $repoRoot "scripts/test.ps1"
$lintGatePath = Join-Path $repoRoot "scripts/lint.ps1"
$metricsPath = Join-Path $repoRoot "docs/governance/m009_deep_research_metrics.json"
$journalPath = Join-Path $repoRoot "docs/tasks/milestone_009/journal.md"

function Assert-Contains {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content,

        [Parameter(Mandatory = $true)]
        [string] $Expected,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if (-not $Content.Contains($Expected)) {
        throw "$Message Élément attendu: $Expected"
    }
}

function Assert-NotContains {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content,

        [Parameter(Mandatory = $true)]
        [string] $Forbidden,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if ($Content.Contains($Forbidden)) {
        throw "$Message Élément interdit: $Forbidden"
    }
}

function Assert-File {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Message Chemin attendu: $Path"
    }
}

Assert-File -Path $matrixPath -Message "Matrice de traçabilité absente."
Assert-File -Path $traceabilityValidatorPath -Message "Validateur de traçabilité absent."
Assert-File -Path $testGatePath -Message "Gate test absent."
Assert-File -Path $lintGatePath -Message "Gate lint absent."
Assert-File -Path $metricsPath -Message "Preuve métrique M-009 absente."
Assert-File -Path $journalPath -Message "Journal de clôture M-009 absent."

# Given les comportements M-009 sont implémentés et testés.
# When la matrice de traçabilité et les gates sont exécutées.
# Then chaque exigence M-009 est rattachée à un test GREEN, une commande de validation, une ADR ou justification explicite,
# et une preuve d'observabilité sans payload sensible.
$matrixContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $matrixPath
$traceabilityValidatorContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $traceabilityValidatorPath
$testGateContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $testGatePath
$lintGateContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $lintGatePath
$metricsContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $metricsPath
$journalContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $journalPath

foreach ($requirementId in @(
    "REQ-M009-001",
    "REQ-M009-002",
    "REQ-M009-003",
    "REQ-M009-004",
    "REQ-M009-005",
    "REQ-M009-006",
    "REQ-M009-007",
    "REQ-M009-008",
    "REQ-M009-009",
    "REQ-M009-010",
    "REQ-M009-011"
)) {
    Assert-Contains -Content $matrixContent -Expected $requirementId -Message "Exigence M-009 absente de la matrice."
    Assert-Contains -Content $traceabilityValidatorContent -Expected $requirementId -Message "Exigence M-009 absente du validateur de traçabilité."
}

foreach ($testPath in @(
    "tests/m009/validate_m009_precondition_acceptance.ps1",
    "tests/m009/validate_m009_precondition_unit.ps1",
    "tests/m009/validate_m009_specification_acceptance.ps1",
    "tests/m009/validate_m009_specification_unit.ps1",
    "tests/m009/validate_deep_research_planning_acceptance.ps1",
    "tests/m009/validate_deep_research_planning_unit.ps1",
    "tests/m009/validate_multi_query_evidence_collection_acceptance.ps1",
    "tests/m009/validate_multi_query_evidence_collection_unit.ps1",
    "tests/m009/validate_verified_claim_dependency_resolution_acceptance.ps1",
    "tests/m009/validate_verified_claim_dependency_resolution_unit.ps1",
    "tests/m009/validate_deep_contradiction_classification_acceptance.ps1",
    "tests/m009/validate_deep_contradiction_classification_unit.ps1",
    "tests/m009/validate_insufficient_deep_coverage_acceptance.ps1",
    "tests/m009/validate_insufficient_deep_coverage_unit.ps1",
    "tests/m009/validate_multi_source_synthesis_acceptance.ps1",
    "tests/m009/validate_multi_source_synthesis_unit.ps1",
    "tests/m009/validate_deep_research_http_contract_acceptance.ps1",
    "tests/m009/validate_deep_research_http_contract_unit.ps1",
    "tests/m009/validate_deep_research_metrics_acceptance.ps1",
    "tests/m009/validate_deep_research_metrics_unit.ps1",
    "tests/m009/validate_m009_traceability_acceptance.ps1",
    "tests/m009/validate_m009_traceability_unit.ps1"
)) {
    Assert-Contains -Content $testGateContent -Expected $testPath -Message "Test M-009 non enrôlé dans scripts/test.ps1."
}

Assert-Contains -Content $lintGateContent -Expected "scripts/validate_traceability.ps1" -Message "Validation de traçabilité absente de scripts/lint.ps1."
Assert-Contains -Content $lintGateContent -Expected "scripts/validate_m009_specification.ps1" -Message "Validation de spécification M-009 absente de scripts/lint.ps1."
Assert-Contains -Content $lintGateContent -Expected "scripts/validate_architecture_boundaries.ps1" -Message "Validation des frontières d'architecture absente de scripts/lint.ps1."

Assert-Contains -Content $matrixContent -Expected "tests/m009/validate_m009_traceability_acceptance.ps1" -Message "Test d'acceptation T-011 absent de la matrice."
Assert-Contains -Content $matrixContent -Expected "tests/m009/validate_m009_traceability_unit.ps1" -Message "Test unitaire T-011 absent de la matrice ou de sa commande."
Assert-Contains -Content $matrixContent -Expected "app/research_answering/application/deep_research_metrics.py" -Message "Preuve métrique M-009 absente de la matrice."
Assert-Contains -Content $matrixContent -Expected "app/research_answering/adapters/answer_http.py" -Message "Endpoint RA approfondi absent de la matrice."
Assert-Contains -Content $matrixContent -Expected "app/conversation/application/answer_deep_research_turn.py" -Message "Routage CV vers RA approfondie absent de la matrice."
Assert-Contains -Content $matrixContent -Expected "ADR-006; ADR-010; DDD-ADR-005; DDD-ADR-008" -Message "ADR de clôture M-009 absentes de la matrice."

Assert-Contains -Content $journalContent -Expected "ADR: non requise" -Message "Le journal doit justifier l'absence de nouvelle ADR."
Assert-Contains -Content $journalContent -Expected "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_m009_traceability_acceptance.ps1" -Message "Commande finale du test d'acceptation T-011 absente du journal."
Assert-Contains -Content $journalContent -Expected "powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_m009_traceability_unit.ps1" -Message "Commande finale du test unitaire T-011 absente du journal."
Assert-Contains -Content $journalContent -Expected "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_architecture_boundaries.ps1" -Message "Commande finale de frontières d'architecture absente du journal."
Assert-Contains -Content $journalContent -Expected "Frontières RA/EG/CV" -Message "Vérification RA/EG/CV absente du journal."
Assert-Contains -Content $journalContent -Expected "Aucun payload sensible" -Message "Garantie d'absence de payload sensible absente du journal."

foreach ($forbiddenPayload in @(
    "Texte source complet d'une preuve approfondie qui ne doit pas etre journalise.",
    "Prompt complet demandant au modele de synthétiser toutes les sources.",
    "Réponse approfondie complète qualifiée par les preuves et les limites.",
    "investisseur.prive@example.test",
    "answer_text",
    "source_text",
    "prompt_override",
    "raw_projection_payload"
)) {
    Assert-NotContains -Content $metricsContent -Forbidden $forbiddenPayload -Message "Les métriques M-009 ne doivent pas exposer de payload sensible."
}

Write-Host "Test d'acceptation T-011 traçabilité et gates M-009: OK"
