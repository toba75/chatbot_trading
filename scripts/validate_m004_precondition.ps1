param(
    [Parameter(Mandatory = $false)]
    [string] $Path
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$allowedBranches = @(
    "master",
    "codex/milestone-m004-version-canonique-publiee",
    "codex/milestone-m005-projection-connaissance",
    "codex/milestone-m006-claims-verifiables",
    "codex/milestone-m007-reponse-documentaire-verifiee",
    "codex/milestone-m008-conversation-produit",
    "codex/milestone-m009-recherche-approfondie",
    "codex/milestone-m010-strategie-candidate-attribuee",
    "codex/milestone-m011-experience-reproductible",
    "codex/milestone-m012-evaluation-pilote-calibration"
)
$requiredMilestonePaths = @(
    "docs/tasks/milestone_000",
    "docs/tasks/milestone_001",
    "docs/tasks/milestone_002",
    "docs/tasks/milestone_003"
)
$gateDefinitions = @(
    [ordered] @{
        Name = "test"
        Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1"
        Script = "scripts/test.ps1"
    },
    [ordered] @{
        Name = "lint"
        Command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1"
        Script = "scripts/lint.ps1"
    }
)

function Assert-M004Condition {
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

function Resolve-M004ReportPath {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string] $ReportPath
    )

    Assert-M004Condition `
        -Condition (-not [string]::IsNullOrWhiteSpace($ReportPath)) `
        -Message "Chemin de rapport M-004 obligatoire via -Path."

    if ([System.IO.Path]::IsPathRooted($ReportPath)) {
        $resolvedReportPath = [System.IO.Path]::GetFullPath($ReportPath)
    }
    else {
        $resolvedReportPath = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $ReportPath))
    }

    $repoRootPath = [System.IO.Path]::GetFullPath($repoRoot).TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    )
    $repoRootPrefix = $repoRootPath + [System.IO.Path]::DirectorySeparatorChar
    Assert-M004Condition `
        -Condition ($resolvedReportPath.StartsWith($repoRootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) `
        -Message "Chemin de rapport M-004 hors dépôt: $resolvedReportPath"

    $reportDirectory = Split-Path -Parent $resolvedReportPath
    Assert-M004Condition `
        -Condition (-not [string]::IsNullOrWhiteSpace($reportDirectory)) `
        -Message "Répertoire de rapport M-004 introuvable pour le chemin: $ReportPath"

    Assert-M004Condition `
        -Condition (Test-Path -LiteralPath $reportDirectory -PathType Container) `
        -Message "Répertoire de rapport M-004 absent: $reportDirectory"

    return $resolvedReportPath
}

function Invoke-M004Process {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name,

        [Parameter(Mandatory = $true)]
        [string] $Command,

        [Parameter(Mandatory = $true)]
        [string] $Executable,

        [Parameter(Mandatory = $true)]
        [string[]] $Arguments
    )

    $startedAtUtc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    try {
        $output = & $Executable @Arguments 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    $completedAtUtc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

    if ($null -eq $output) {
        $outputLines = @()
    }
    else {
        $outputLines = @($output | ForEach-Object { [string] $_ })
    }

    return [pscustomobject] @{
        Name = $Name
        Command = $Command
        ExitCode = $exitCode
        OutputLines = $outputLines
        StartedAtUtc = $startedAtUtc
        CompletedAtUtc = $completedAtUtc
    }
}

function Invoke-M004GateProcess {
    param(
        [Parameter(Mandatory = $true)]
        [object] $GateDefinition
    )

    $scriptPath = Join-Path $repoRoot $GateDefinition["Script"]
    $previousRecursionGuard = $env:OST_M004_PRECONDITION_ACCEPTANCE_RUNNING

    if ($GateDefinition["Name"] -eq "test") {
        $env:OST_M004_PRECONDITION_ACCEPTANCE_RUNNING = "1"
    }

    try {
        return Invoke-M004Process `
            -Name $GateDefinition["Name"] `
            -Command $GateDefinition["Command"] `
            -Executable "powershell" `
            -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $scriptPath)
    }
    finally {
        if ($GateDefinition["Name"] -eq "test") {
            if ($null -eq $previousRecursionGuard) {
                Remove-Item Env:\OST_M004_PRECONDITION_ACCEPTANCE_RUNNING -ErrorAction SilentlyContinue
            }
            else {
                $env:OST_M004_PRECONDITION_ACCEPTANCE_RUNNING = $previousRecursionGuard
            }
        }
    }
}

function ConvertTo-M004MarkdownCell {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string] $Value
    )

    return $Value.Replace("|", "\|").Replace("`r", " ").Replace("`n", " ")
}

function Add-M004Result {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateNotNull()]
        [object] $Results,

        [Parameter(Mandatory = $true)]
        [string] $Name,

        [Parameter(Mandatory = $true)]
        [string] $Command,

        [Parameter(Mandatory = $true)]
        [int] $ExitCode,

        [Parameter(Mandatory = $true)]
        [AllowEmptyCollection()]
        [string[]] $OutputLines,

        [Parameter(Mandatory = $true)]
        [string] $Status,

        [Parameter(Mandatory = $true)]
        [string] $Observation,

        [Parameter(Mandatory = $true)]
        [string] $StartedAtUtc,

        [Parameter(Mandatory = $true)]
        [string] $CompletedAtUtc
    )

    $Results.Add([pscustomobject] @{
        Name = $Name
        Command = $Command
        ExitCode = $ExitCode
        OutputLines = $OutputLines
        Status = $Status
        Observation = $Observation
        StartedAtUtc = $StartedAtUtc
        CompletedAtUtc = $CompletedAtUtc
    }) | Out-Null
}

function Add-M004ResultTable {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateNotNull()]
        [object] $Lines,

        [Parameter(Mandatory = $true)]
        [AllowEmptyCollection()]
        [object[]] $Results
    )

    $Lines.Add("| Élément | Commande | Date UTC | Résultat | Observation |")
    $Lines.Add("|---|---|---|---|---|")

    foreach ($result in $Results) {
        $Lines.Add("| ``$($result.Name)`` | ``$($result.Command)`` | ``$($result.CompletedAtUtc)`` | ``$($result.Status)`` | $(ConvertTo-M004MarkdownCell -Value $result.Observation) |")
    }
}

function Write-M004PreconditionReport {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ReportPath,

        [Parameter(Mandatory = $true)]
        [string] $OverallStatus,

        [Parameter(Mandatory = $true)]
        [AllowEmptyCollection()]
        [object[]] $GitResults,

        [Parameter(Mandatory = $true)]
        [AllowEmptyCollection()]
        [object[]] $GateResults
    )

    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("# Rapport de précondition GREEN M-004")
    $lines.Add("")
    $lines.Add("## Scénario BDD")
    $lines.Add("")
    $lines.Add("- Given M-000, M-001, M-002 et M-003 sont présents dans ``master``.")
    $lines.Add("- When les gates de précondition M-004 sont exécutées depuis la base courante.")
    $lines.Add("- Then M-004 peut commencer uniquement si ``test``, ``lint``, la traçabilité, les ADR, les frontières d'architecture et la précondition M-003 post-merge sont GREEN.")
    $lines.Add("")
    $lines.Add("## Résultat")
    $lines.Add("")
    $lines.Add("- Statut: ``$OverallStatus``")
    $allowedBranchLabel = $allowedBranches -join "; "
    $lines.Add("- Branches autorisées: ``$allowedBranchLabel``")
    $lines.Add("")
    $lines.Add("## Vérifications Git")
    $lines.Add("")
    Add-M004ResultTable -Lines $lines -Results $GitResults
    $lines.Add("")
    $lines.Add("## Gates exécutées")
    $lines.Add("")

    if ($GateResults.Count -eq 0) {
        $lines.Add("Aucune gate exécutée: une précondition Git est RED.")
        $lines.Add("")
    }
    else {
        Add-M004ResultTable -Lines $lines -Results $GateResults
        $lines.Add("")
        $lines.Add("## Sorties des gates")
        $lines.Add("")

        foreach ($gateResult in $GateResults) {
            $lines.Add("### $($gateResult.Name)")
            $lines.Add("")
            $lines.Add("~~~text")
            if ($gateResult.OutputLines.Count -eq 0) {
                $lines.Add("<aucune sortie>")
            }
            else {
                foreach ($outputLine in $gateResult.OutputLines) {
                    $lines.Add($outputLine)
                }
            }
            $lines.Add("~~~")
            $lines.Add("")
        }
    }

    while (($lines.Count -gt 0) -and ([string]::IsNullOrWhiteSpace($lines[$lines.Count - 1]))) {
        $lines.RemoveAt($lines.Count - 1)
    }

    Set-Content -Encoding UTF8 -LiteralPath $ReportPath -Value $lines
}

function Stop-M004OnRedGitResult {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateNotNull()]
        [object] $GitResults,

        [Parameter(Mandatory = $true)]
        [ValidateNotNull()]
        [object] $GateResults,

        [Parameter(Mandatory = $true)]
        [string] $ReportPath
    )

    $redGitResult = @($GitResults | Where-Object { $_.Status -eq "RED" } | Select-Object -First 1)
    if ($redGitResult.Count -gt 0) {
        Write-M004PreconditionReport -ReportPath $ReportPath -OverallStatus "RED" -GitResults $GitResults.ToArray() -GateResults $GateResults.ToArray()
        Write-Host "Précondition M-004 RED: $($redGitResult[0].Observation)"
        throw "Précondition M-004 RED: $($redGitResult[0].Observation)"
    }
}

$reportPath = Resolve-M004ReportPath -ReportPath $Path
$gitResults = New-Object System.Collections.Generic.List[object]
$gateResults = New-Object System.Collections.Generic.List[object]

$currentBranchResult = Invoke-M004Process `
    -Name "branche courante" `
    -Command "git rev-parse --abbrev-ref HEAD" `
    -Executable "git" `
    -Arguments @("-C", $repoRoot, "rev-parse", "--abbrev-ref", "HEAD")
$currentBranch = if ($currentBranchResult.OutputLines.Count -eq 0) { "" } else { $currentBranchResult.OutputLines[0].Trim() }
if (($currentBranchResult.ExitCode -eq 0) -and ($allowedBranches -contains $currentBranch)) {
    $branchObservation = "Branche M-004 autorisée: $currentBranch"
    Add-M004Result -Results $gitResults -Name "branche courante" -Command $currentBranchResult.Command -ExitCode 0 -OutputLines $currentBranchResult.OutputLines -Status "GREEN" -Observation $branchObservation -StartedAtUtc $currentBranchResult.StartedAtUtc -CompletedAtUtc $currentBranchResult.CompletedAtUtc
    Write-Host $branchObservation
}
else {
    $allowedBranchList = $allowedBranches -join ", "
    Add-M004Result -Results $gitResults -Name "branche courante" -Command $currentBranchResult.Command -ExitCode $currentBranchResult.ExitCode -OutputLines $currentBranchResult.OutputLines -Status "RED" -Observation "Branche courante invalide. Autorisées: $allowedBranchList. Obtenu: $currentBranch" -StartedAtUtc $currentBranchResult.StartedAtUtc -CompletedAtUtc $currentBranchResult.CompletedAtUtc
}

Stop-M004OnRedGitResult -GitResults $gitResults -GateResults $gateResults -ReportPath $reportPath

$masterResult = Invoke-M004Process `
    -Name "master local" `
    -Command "git rev-parse --verify master^{commit}" `
    -Executable "git" `
    -Arguments @("-C", $repoRoot, "rev-parse", "--verify", "master^{commit}")
if ($masterResult.ExitCode -eq 0) {
    $masterRevision = $masterResult.OutputLines[0].Trim()
    Add-M004Result -Results $gitResults -Name "master local" -Command $masterResult.Command -ExitCode 0 -OutputLines $masterResult.OutputLines -Status "GREEN" -Observation "Révision locale master: $masterRevision" -StartedAtUtc $masterResult.StartedAtUtc -CompletedAtUtc $masterResult.CompletedAtUtc
}
else {
    $masterRevision = ""
    Add-M004Result -Results $gitResults -Name "master local" -Command $masterResult.Command -ExitCode $masterResult.ExitCode -OutputLines $masterResult.OutputLines -Status "RED" -Observation "Référence locale master absente." -StartedAtUtc $masterResult.StartedAtUtc -CompletedAtUtc $masterResult.CompletedAtUtc
}

Stop-M004OnRedGitResult -GitResults $gitResults -GateResults $gateResults -ReportPath $reportPath

$originMasterResult = Invoke-M004Process `
    -Name "origin/master" `
    -Command "git rev-parse --verify origin/master^{commit}" `
    -Executable "git" `
    -Arguments @("-C", $repoRoot, "rev-parse", "--verify", "origin/master^{commit}")
if ($originMasterResult.ExitCode -eq 0) {
    $originMasterRevision = $originMasterResult.OutputLines[0].Trim()
    Add-M004Result -Results $gitResults -Name "origin/master" -Command $originMasterResult.Command -ExitCode 0 -OutputLines $originMasterResult.OutputLines -Status "GREEN" -Observation "Révision origin/master: $originMasterRevision" -StartedAtUtc $originMasterResult.StartedAtUtc -CompletedAtUtc $originMasterResult.CompletedAtUtc
}
else {
    $originMasterRevision = ""
    Add-M004Result -Results $gitResults -Name "origin/master" -Command $originMasterResult.Command -ExitCode $originMasterResult.ExitCode -OutputLines $originMasterResult.OutputLines -Status "RED" -Observation "Référence origin/master absente." -StartedAtUtc $originMasterResult.StartedAtUtc -CompletedAtUtc $originMasterResult.CompletedAtUtc
}

Stop-M004OnRedGitResult -GitResults $gitResults -GateResults $gateResults -ReportPath $reportPath

$masterContainsOriginResult = Invoke-M004Process `
    -Name "master contient origin/master" `
    -Command "git merge-base --is-ancestor origin/master master" `
    -Executable "git" `
    -Arguments @("-C", $repoRoot, "merge-base", "--is-ancestor", "origin/master", "master")
if ($masterContainsOriginResult.ExitCode -eq 0) {
    Add-M004Result -Results $gitResults -Name "master contient origin/master" -Command $masterContainsOriginResult.Command -ExitCode 0 -OutputLines @($masterRevision, $originMasterRevision) -Status "GREEN" -Observation "La référence master contient origin/master." -StartedAtUtc $masterContainsOriginResult.StartedAtUtc -CompletedAtUtc $masterContainsOriginResult.CompletedAtUtc
}
else {
    Add-M004Result -Results $gitResults -Name "master contient origin/master" -Command $masterContainsOriginResult.Command -ExitCode $masterContainsOriginResult.ExitCode -OutputLines @($masterRevision, $originMasterRevision) -Status "RED" -Observation "Référence master divergente entre master et origin/master." -StartedAtUtc $masterContainsOriginResult.StartedAtUtc -CompletedAtUtc $masterContainsOriginResult.CompletedAtUtc
}

Stop-M004OnRedGitResult -GitResults $gitResults -GateResults $gateResults -ReportPath $reportPath

$ancestorResult = Invoke-M004Process `
    -Name "branche contient master" `
    -Command "git merge-base --is-ancestor master HEAD" `
    -Executable "git" `
    -Arguments @("-C", $repoRoot, "merge-base", "--is-ancestor", "master", "HEAD")
if ($ancestorResult.ExitCode -eq 0) {
    Add-M004Result -Results $gitResults -Name "branche contient master" -Command $ancestorResult.Command -ExitCode 0 -OutputLines $ancestorResult.OutputLines -Status "GREEN" -Observation "La branche courante contient la révision locale master." -StartedAtUtc $ancestorResult.StartedAtUtc -CompletedAtUtc $ancestorResult.CompletedAtUtc
}
else {
    Add-M004Result -Results $gitResults -Name "branche contient master" -Command $ancestorResult.Command -ExitCode $ancestorResult.ExitCode -OutputLines $ancestorResult.OutputLines -Status "RED" -Observation "La branche courante ne contient pas la révision locale master." -StartedAtUtc $ancestorResult.StartedAtUtc -CompletedAtUtc $ancestorResult.CompletedAtUtc
}

Stop-M004OnRedGitResult -GitResults $gitResults -GateResults $gateResults -ReportPath $reportPath

foreach ($requiredMilestonePath in $requiredMilestonePaths) {
    $milestoneResult = Invoke-M004Process `
        -Name "$requiredMilestonePath dans master" `
        -Command "git ls-tree -r --name-only master -- $requiredMilestonePath" `
        -Executable "git" `
        -Arguments @("-C", $repoRoot, "ls-tree", "-r", "--name-only", "master", "--", $requiredMilestonePath)
    $matchingPaths = @($milestoneResult.OutputLines | Where-Object { $_ -like "$requiredMilestonePath/*" })

    if (($milestoneResult.ExitCode -eq 0) -and ($matchingPaths.Count -gt 0)) {
        Add-M004Result -Results $gitResults -Name "$requiredMilestonePath dans master" -Command $milestoneResult.Command -ExitCode 0 -OutputLines $milestoneResult.OutputLines -Status "GREEN" -Observation "Milestone amont présent dans master: $requiredMilestonePath" -StartedAtUtc $milestoneResult.StartedAtUtc -CompletedAtUtc $milestoneResult.CompletedAtUtc
    }
    else {
        Add-M004Result -Results $gitResults -Name "$requiredMilestonePath dans master" -Command $milestoneResult.Command -ExitCode $milestoneResult.ExitCode -OutputLines $milestoneResult.OutputLines -Status "RED" -Observation "Milestone amont absent de master: $requiredMilestonePath" -StartedAtUtc $milestoneResult.StartedAtUtc -CompletedAtUtc $milestoneResult.CompletedAtUtc
    }
}

Stop-M004OnRedGitResult -GitResults $gitResults -GateResults $gateResults -ReportPath $reportPath

foreach ($gateDefinition in $gateDefinitions) {
    $gateResult = Invoke-M004GateProcess -GateDefinition $gateDefinition

    foreach ($outputLine in $gateResult.OutputLines) {
        Write-Host $outputLine
    }

    if ($gateResult.OutputLines.Count -eq 0) {
        $observation = "Gate M-004 RED: $($gateDefinition["Name"]) sans sortie."
        Add-M004Result -Results $gateResults -Name $gateResult.Name -Command $gateResult.Command -ExitCode $gateResult.ExitCode -OutputLines $gateResult.OutputLines -Status "RED" -Observation $observation -StartedAtUtc $gateResult.StartedAtUtc -CompletedAtUtc $gateResult.CompletedAtUtc
        Write-M004PreconditionReport -ReportPath $reportPath -OverallStatus "RED" -GitResults $gitResults.ToArray() -GateResults $gateResults.ToArray()
        Write-Host $observation
        throw $observation
    }

    if ($gateResult.ExitCode -eq 0) {
        Add-M004Result -Results $gateResults -Name $gateResult.Name -Command $gateResult.Command -ExitCode $gateResult.ExitCode -OutputLines $gateResult.OutputLines -Status "GREEN" -Observation "Gate $($gateDefinition["Name"]) GREEN." -StartedAtUtc $gateResult.StartedAtUtc -CompletedAtUtc $gateResult.CompletedAtUtc
    }
    else {
        Add-M004Result -Results $gateResults -Name $gateResult.Name -Command $gateResult.Command -ExitCode $gateResult.ExitCode -OutputLines $gateResult.OutputLines -Status "RED" -Observation "Gate M-004 RED: $($gateDefinition["Name"])" -StartedAtUtc $gateResult.StartedAtUtc -CompletedAtUtc $gateResult.CompletedAtUtc
        Write-M004PreconditionReport -ReportPath $reportPath -OverallStatus "RED" -GitResults $gitResults.ToArray() -GateResults $gateResults.ToArray()
        Write-Host "Gate M-004 RED: $($gateDefinition["Name"])"
        throw "Gate M-004 RED: $($gateDefinition["Name"])"
    }
}

Write-M004PreconditionReport -ReportPath $reportPath -OverallStatus "GREEN" -GitResults $gitResults.ToArray() -GateResults $gateResults.ToArray()
Write-Host "Précondition M-004 GREEN: 2 gate(s), 4 milestone(s) amont vérifié(s). Rapport: $reportPath"
