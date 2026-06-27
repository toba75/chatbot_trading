$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_traceability.ps1"
$matrixPath = Join-Path $repoRoot "docs/traceability/matrix.md"
$journalPath = Join-Path $repoRoot "docs/tasks/milestone_004/journal.md"
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m004_traceability_acceptance_" + [System.Guid]::NewGuid().ToString("N"))
$eAcute = [char] 0x00E9
$eGrave = [char] 0x00E8
$cCedilla = [char] 0x00E7

function Split-MarkdownRow {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Line
    )

    return @($Line.Trim().Trim("|").Split("|") | ForEach-Object { $_.Trim() })
}

function Join-MarkdownRow {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyCollection()]
        [AllowEmptyString()]
        [string[]] $Cells
    )

    return "| " + ($Cells -join " | ") + " |"
}

function Remove-MatrixRow {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [string] $RequirementId
    )

    $lines = [System.Collections.Generic.List[string]] (Get-Content -Encoding UTF8 -LiteralPath $Path)

    for ($index = $lines.Count - 1; $index -ge 0; $index--) {
        if ($lines[$index] -notmatch "^\|") {
            continue
        }

        $cells = Split-MarkdownRow -Line $lines[$index]
        if (($cells.Count -gt 0) -and ($cells[0] -eq $RequirementId)) {
            $lines.RemoveAt($index)
        }
    }

    Set-Content -Encoding UTF8 -LiteralPath $Path -Value $lines
}

function Set-MatrixCell {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [string] $RequirementId,

        [Parameter(Mandatory = $true)]
        [string] $ColumnName,

        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string] $Value
    )

    $lines = [System.Collections.Generic.List[string]] (Get-Content -Encoding UTF8 -LiteralPath $Path)
    $headerIndex = -1

    for ($index = 0; $index -lt $lines.Count; $index++) {
        if ($lines[$index] -match "^\|\s*Exigence\s*\|") {
            $headerIndex = $index
            break
        }
    }

    if ($headerIndex -lt 0) {
        throw "En-t$($eGrave)te de matrice introuvable."
    }

    $headers = Split-MarkdownRow -Line $lines[$headerIndex]
    $columnIndex = [array]::IndexOf($headers, $ColumnName)

    if ($columnIndex -lt 0) {
        throw "Colonne introuvable dans la matrice: $ColumnName"
    }

    for ($index = $headerIndex + 1; $index -lt $lines.Count; $index++) {
        if ($lines[$index] -notmatch "^\|") {
            continue
        }

        $cells = Split-MarkdownRow -Line $lines[$index]
        if (($cells.Count -gt 0) -and ($cells[0] -eq $RequirementId)) {
            $cells[$columnIndex] = $Value
            $lines[$index] = Join-MarkdownRow -Cells $cells
            Set-Content -Encoding UTF8 -LiteralPath $Path -Value $lines
            return
        }
    }

    throw "Exigence introuvable dans la matrice: $RequirementId"
}

function New-TemporaryProject {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name
    )

    $projectRoot = Join-Path $temporaryRoot $Name
    New-Item -ItemType Directory -Path $projectRoot -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs") -Force | Out-Null

    Copy-Item -LiteralPath (Join-Path $repoRoot "scripts") -Destination (Join-Path $projectRoot "scripts") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "tests") -Destination (Join-Path $projectRoot "tests") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/adr") -Destination (Join-Path $projectRoot "docs/adr") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/governance") -Destination (Join-Path $projectRoot "docs/governance") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/specs") -Destination (Join-Path $projectRoot "docs/specs") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/tasks") -Destination (Join-Path $projectRoot "docs/tasks") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/traceability") -Destination (Join-Path $projectRoot "docs/traceability") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "app") -Destination (Join-Path $projectRoot "app") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "deploy") -Destination (Join-Path $projectRoot "deploy") -Recurse

    return $projectRoot
}

function Invoke-Validator {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProjectRoot
    )

    $scriptPath = Join-Path $ProjectRoot "scripts/validate_traceability.ps1"
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    try {
        $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $scriptPath 2>&1
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    return [pscustomobject] @{
        ExitCode = $LASTEXITCODE
        Output = ($output -join "`n")
    }
}

function Invoke-PythonAuditCheck {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProjectRoot,

        [Parameter(Mandatory = $true)]
        [string] $Script
    )

    $previousPythonPath = $env:PYTHONPATH
    $env:PYTHONPATH = $ProjectRoot
    $scriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m004_traceability_audit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
    $Script | Set-Content -Encoding UTF8 -LiteralPath $scriptPath

    try {
        $previousErrorActionPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $output = & python $scriptPath 2>&1
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
        Remove-Item -LiteralPath $scriptPath -Force
        if ($null -eq $previousPythonPath) {
            Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue
        }
        else {
            $env:PYTHONPATH = $previousPythonPath
        }
    }

    return [pscustomobject] @{
        ExitCode = $LASTEXITCODE
        Output = ($output -join "`n")
    }
}

function Assert-ExitCode {
    param(
        [Parameter(Mandatory = $true)]
        [int] $Actual,

        [Parameter(Mandatory = $true)]
        [int] $Expected,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if ($Actual -ne $Expected) {
        throw "$Message Code obtenu: $Actual"
    }
}

function Assert-OutputContains {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Output,

        [Parameter(Mandatory = $true)]
        [string] $Expected,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if (-not $Output.Contains($Expected)) {
        throw "$Message Sortie obtenue: $Output"
    }
}

function Assert-OutputNotContains {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Output,

        [Parameter(Mandatory = $true)]
        [string] $Forbidden,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if ($Output.Contains($Forbidden)) {
        throw "$Message Sortie obtenue: $Output"
    }
}

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
    throw "Validateur de tra$($cCedilla)abilit$($eAcute) absent: scripts/validate_traceability.ps1"
}

if (-not (Test-Path -LiteralPath $matrixPath -PathType Leaf)) {
    throw "Matrice de tra$($cCedilla)abilit$($eAcute) absente: docs/traceability/matrix.md"
}

if (-not (Test-Path -LiteralPath $journalPath -PathType Leaf)) {
    throw "Journal M-004 absent: docs/tasks/milestone_004/journal.md"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    # Given les comportements M-004 sont implémentés et testés.
    # When les gates de clôture sont exécutées.
    # Then chaque exigence M-004 est reliée à une preuve et la clôture est refusée si un test, une ADR, une commande, un locator ou un signal d'audit manque.
    $validProjectRoot = New-TemporaryProject -Name "valid"
    $validResult = Invoke-Validator -ProjectRoot $validProjectRoot
    Assert-ExitCode -Actual $validResult.ExitCode -Expected 0 -Message "La matrice M-004 complète doit être acceptée."
    Assert-OutputContains `
        -Output $validResult.Output `
        -Expected "Matrice de tra$($cCedilla)abilit$($eAcute) valide: 53 exigence(s)" `
        -Message "La matrice doit compter les exigences M-004 de précondition et de clôture."

    $missingPreconditionProjectRoot = New-TemporaryProject -Name "missing-precondition"
    Remove-MatrixRow `
        -Path (Join-Path $missingPreconditionProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M004-001"
    $missingPreconditionResult = Invoke-Validator -ProjectRoot $missingPreconditionProjectRoot
    Assert-ExitCode -Actual $missingPreconditionResult.ExitCode -Expected 1 -Message "Une précondition M-004 livrée absente doit être refusée."
    Assert-OutputContains `
        -Output $missingPreconditionResult.Output `
        -Expected "Exigence M-004 livr$($eAcute)e absente: REQ-M004-001" `
        -Message "La précondition M-004 absente doit être nommée."

    $missingClosureProjectRoot = New-TemporaryProject -Name "missing-closure"
    Remove-MatrixRow `
        -Path (Join-Path $missingClosureProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M004-010"
    $missingClosureResult = Invoke-Validator -ProjectRoot $missingClosureProjectRoot
    Assert-ExitCode -Actual $missingClosureResult.ExitCode -Expected 1 -Message "Une clôture M-004 livrée absente doit être refusée."
    Assert-OutputContains `
        -Output $missingClosureResult.Output `
        -Expected "Exigence M-004 livr$($eAcute)e absente: REQ-M004-010" `
        -Message "L'exigence de clôture M-004 absente doit être nommée."

    $coveredWithoutCommandProjectRoot = New-TemporaryProject -Name "covered-without-command"
    Set-MatrixCell `
        -Path (Join-Path $coveredWithoutCommandProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M004-010" `
        -ColumnName "Commande" `
        -Value "Non applicable: commande absente."
    $coveredWithoutCommandResult = Invoke-Validator -ProjectRoot $coveredWithoutCommandProjectRoot
    Assert-ExitCode -Actual $coveredWithoutCommandResult.ExitCode -Expected 1 -Message "Une ligne M-004 couverte sans commande doit être refusée."
    Assert-OutputContains `
        -Output $coveredWithoutCommandResult.Output `
        -Expected "REQ-M004-010" `
        -Message "La commande manquante de clôture M-004 doit être nommée."

    $missingAuditProjectRoot = New-TemporaryProject -Name "missing-audit"
    Set-MatrixCell `
        -Path (Join-Path $missingAuditProjectRoot "docs/traceability/matrix.md") `
        -RequirementId "REQ-M004-010" `
        -ColumnName "Code" `
        -Value "scripts/validate_traceability.ps1"
    $missingAuditResult = Invoke-Validator -ProjectRoot $missingAuditProjectRoot
    Assert-ExitCode -Actual $missingAuditResult.ExitCode -Expected 1 -Message "Une clôture M-004 sans preuve d'audit canonique doit être refusée."
    Assert-OutputContains `
        -Output $missingAuditResult.Output `
        -Expected "Code M-004 invalide pour REQ-M004-010" `
        -Message "La preuve de métriques M-004 absente doit être nommée."

    $auditScript = @'
from app.source_processing.application.canonical_audit_signals import (
    CanonicalAuditEvent,
    build_canonical_audit_signals,
)

events = (
    CanonicalAuditEvent(
        trace_id="TRACE-M004-A",
        document_id="DOC-M004-A",
        canonical_version_id="CANON-M004-A",
        phase="canonical_publication",
        status="PUBLISHED",
        page_count=3,
        pages_rejected_by_qa=0,
        ambiguous_text_authorities=0,
        artifact_hash="sha256:" + "a" * 64,
        error_code=None,
    ),
    CanonicalAuditEvent(
        trace_id="TRACE-M004-B",
        document_id="DOC-M004-B",
        canonical_version_id="CANON-M004-B",
        phase="canonical_quality",
        status="REJECTED",
        page_count=2,
        pages_rejected_by_qa=1,
        ambiguous_text_authorities=1,
        artifact_hash="sha256:" + "b" * 64,
        error_code="PAGE_AUTHORITY_AMBIGUOUS",
    ),
)

signals = build_canonical_audit_signals(events)
metrics = {(metric.name, tuple(sorted(metric.tags.items()))): metric.value for metric in signals.metrics}

assert metrics[("versions_canoniques_publiees", (("scope", "m004"),))] == 1.0
assert metrics[("pages_refusees_qa", (("scope", "m004"),))] == 1.0
assert metrics[("autorites_textuelles_ambiguës", (("scope", "m004"),))] == 1.0

serialized_logs = str([log.to_mapping() for log in signals.logs])
for forbidden in ("PERFORMANCE_TABLE_FULL_TEXT", "Texte documentaire complet", "page_text"):
    assert forbidden not in serialized_logs, forbidden

print("audit m004 ok")
'@
    $auditResult = Invoke-PythonAuditCheck -ProjectRoot $validProjectRoot -Script $auditScript
    Assert-ExitCode -Actual $auditResult.ExitCode -Expected 0 -Message "Les métriques d'audit M-004 doivent être produites sans contenu documentaire complet."
    Assert-OutputContains -Output $auditResult.Output -Expected "audit m004 ok" -Message "Le contrôle d'audit M-004 doit annoncer son succès."
    Assert-OutputNotContains -Output $auditResult.Output -Forbidden "PERFORMANCE_TABLE_FULL_TEXT" -Message "L'audit M-004 ne doit pas exposer le contenu documentaire complet."
}
finally {
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
}

Write-Host "Test d'acceptation de la tra$($cCedilla)abilit$($eAcute) M-004: OK"
