$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$governancePath = Join-Path $repoRoot "docs/governance/m013_fastapi_precondition.md"
$expectedBranch = "codex/m13-fastapi"

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

function Assert-Contains {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content,

        [Parameter(Mandatory = $true)]
        [string] $Expected,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    Assert-Condition -Condition $Content.Contains($Expected) -Message $Message
}

function Invoke-BoundedValidation {
    param(
        [Parameter(Mandatory = $true)]
        [string] $RelativePath,

        [Parameter(Mandatory = $true)]
        [string] $ExpectedOutput
    )

    $scriptPath = Join-Path $repoRoot $RelativePath
    Assert-Condition `
        -Condition (Test-Path -LiteralPath $scriptPath -PathType Leaf) `
        -Message "Validation bornée absente: $RelativePath"

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $scriptPath 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    $joinedOutput = $output -join "`n"
    Assert-Condition `
        -Condition ($exitCode -eq 0) `
        -Message "Validation bornée RED: $RelativePath. Code: $exitCode. Sortie: $joinedOutput"
    Assert-Contains `
        -Content $joinedOutput `
        -Expected $ExpectedOutput `
        -Message "La validation bornée n'annonce pas son succès: $RelativePath. Sortie: $joinedOutput"

    return [pscustomobject] @{
        Path = $RelativePath
        Status = "GREEN"
        Output = $joinedOutput
    }
}

# Given M-001 à M-012 et ADR-018 sont présents dans master, avec un worktree pouvant contenir des changements utilisateur.
# When les contrats HTTP et les frontières d'architecture utiles à M13-FastAPI sont vérifiés par des gates bornées.
# Then chaque preuve est GREEN, le RED documentaire futur reste EXPECTED_RED et la gate globale sans verdict reste BLOCKED_EXTERNAL.
foreach ($canonicalPath in @(
    "docs/specs/plan_implementation_milestones_workstreams.md",
    "docs/specs/m003_source_enregistree_diagnostiquee_routee.md",
    "docs/specs/m004_version_canonique_publiee.md",
    "docs/specs/m005_projection_connaissance_recherchable.md",
    "docs/specs/ui.md",
    "docs/adr/ADR-018-ui-exclusivement-via-api-orchestratrice.md",
    "docs/tasks/milestone_013-fastapi/0001_verifier_precondition_green.md",
    "tests/m013/validate_document_api_wiring_acceptance.ps1"
)) {
    Assert-Condition `
        -Condition (Test-Path -LiteralPath (Join-Path $repoRoot $canonicalPath) -PathType Leaf) `
        -Message "Source canonique M13-FastAPI absente: $canonicalPath"
}

$currentBranch = (& git -C $repoRoot rev-parse --abbrev-ref HEAD).Trim()
Assert-Condition -Condition ($LASTEXITCODE -eq 0) -Message "Branche Git courante illisible."
Assert-Condition `
    -Condition ($currentBranch -eq $expectedBranch) `
    -Message "Branche M13-FastAPI inattendue. Attendu: $expectedBranch. Obtenu: $currentBranch"

& git -C $repoRoot merge-base --is-ancestor master HEAD
Assert-Condition -Condition ($LASTEXITCODE -eq 0) -Message "La branche M13-FastAPI ne contient pas master."

$boundedResults = @(
    Invoke-BoundedValidation `
        -RelativePath "tests/m003/validate_document_http_contract_acceptance.ps1" `
        -ExpectedOutput "SP: OK"
    Invoke-BoundedValidation `
        -RelativePath "tests/m004/validate_document_conversion_command_acceptance.ps1" `
        -ExpectedOutput "M-004: OK"
    Invoke-BoundedValidation `
        -RelativePath "tests/m005/validate_index_command_acceptance.ps1" `
        -ExpectedOutput "M-005: OK"
    Invoke-BoundedValidation `
        -RelativePath "tests/m013/validate_ui_corpus_backend_connection_acceptance.ps1" `
        -ExpectedOutput "API orchestratrice: OK"
    Invoke-BoundedValidation `
        -RelativePath "tests/m001/validate_architecture_boundaries_acceptance.ps1" `
        -ExpectedOutput "M-001: OK"
)

Assert-Condition `
    -Condition (($boundedResults | Where-Object { $_.Status -ne "GREEN" }).Count -eq 0) `
    -Message "Une validation bornée M13-FastAPI n'est pas GREEN."

$testGateContent = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $repoRoot "scripts/test.ps1")
Assert-Condition `
    -Condition (-not $testGateContent.Contains("tests/m013/validate_document_api_wiring_acceptance.ps1")) `
    -Message "Le RED documentaire de T-006 ne doit pas être enrôlé dans la gate initiale."

Assert-Condition `
    -Condition (Test-Path -LiteralPath $governancePath -PathType Leaf) `
    -Message "Preuve de précondition M13-FastAPI absente: docs/governance/m013_fastapi_precondition.md"

$governanceContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $governancePath
foreach ($expectedMarker in @(
    "Given les milestones M-001 à M-012",
    "Commit de référence ``35fb5a4f8``",
    "``GREEN``",
    "``EXPECTED_RED``",
    "``BLOCKED_EXTERNAL``",
    "tests/m013/validate_document_api_wiring_acceptance.ps1",
    "8ec5231e4",
    "be62f3e7a",
    "plus d'une heure sans verdict",
    "tests/m013/validate_m013_reality_product_acceptance.ps1",
    "aucune preuve issue d'un mock"
)) {
    Assert-Contains `
        -Content $governanceContent `
        -Expected $expectedMarker `
        -Message "Marqueur de précondition M13-FastAPI absent: $expectedMarker"
}

Write-Host "Test d'acceptation de précondition M13-FastAPI: OK"
