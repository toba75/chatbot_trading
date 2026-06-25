param(
    [Parameter(Mandatory = $false)]
    [string] $Path
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$expectedBranch = "codex/milestone-m002-plateforme-locale-sure"
$requiredMilestonePaths = @(
    "docs/tasks/milestone_000",
    "docs/tasks/milestone_001"
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

function Assert-M002Condition {
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

function Resolve-M002ReportPath {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string] $ReportPath
    )

    Assert-M002Condition `
        -Condition (-not [string]::IsNullOrWhiteSpace($ReportPath)) `
        -Message "Chemin de rapport M-002 obligatoire via -Path."

    if ([System.IO.Path]::IsPathRooted($ReportPath)) {
        $resolvedReportPath = [System.IO.Path]::GetFullPath($ReportPath)
    }
    else {
        $resolvedReportPath = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $ReportPath))
    }

    $reportDirectory = Split-Path -Parent $resolvedReportPath
    Assert-M002Condition `
        -Condition (-not [string]::IsNullOrWhiteSpace($reportDirectory)) `
        -Message "Répertoire de rapport M-002 introuvable pour le chemin: $ReportPath"

    Assert-M002Condition `
        -Condition (Test-Path -LiteralPath $reportDirectory -PathType Container) `
        -Message "Répertoire de rapport M-002 absent: $reportDirectory"

    return $resolvedReportPath
}

function New-M002Result {
    param(
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

    return [pscustomobject] @{
        Name = $Name
        Command = $Command
        ExitCode = $ExitCode
        OutputLines = $OutputLines
        Status = $Status
        Observation = $Observation
        StartedAtUtc = $StartedAtUtc
        CompletedAtUtc = $CompletedAtUtc
    }
}

function Invoke-M002Process {
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

function ConvertTo-M002MarkdownCell {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string] $Value
    )

    return $Value.Replace("|", "\|").Replace("`r", " ").Replace("`n", " ")
}

function Add-M002ResultTable {
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
        $Lines.Add("| ``$($result.Name)`` | ``$($result.Command)`` | ``$($result.CompletedAtUtc)`` | ``$($result.Status)`` | $(ConvertTo-M002MarkdownCell -Value $result.Observation) |")
    }
}

function Write-M002PreconditionReport {
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
    $lines.Add("# Rapport de précondition GREEN M-002")
    $lines.Add("")
    $lines.Add("## Scénario BDD")
    $lines.Add("")
    $lines.Add("- Given M-000 et M-001 sont présents dans ``master``.")
    $lines.Add("- When les gates de validation sont exécutées avant la première tâche M-002.")
    $lines.Add("- Then M-002 peut commencer uniquement si les tests, la lint, la traçabilité, les ADR et les frontières d'architecture sont GREEN.")
    $lines.Add("")
    $lines.Add("## Résultat")
    $lines.Add("")
    $lines.Add("- Statut: ``$OverallStatus``")
    $lines.Add("- Branche attendue: ``$expectedBranch``")
    $lines.Add("")
    $lines.Add("## Vérifications Git")
    $lines.Add("")
    Add-M002ResultTable -Lines $lines -Results $GitResults
    $lines.Add("")
    $lines.Add("## Gates exécutées")
    $lines.Add("")

    if ($GateResults.Count -eq 0) {
        $lines.Add("Aucune gate exécutée: une précondition Git est RED.")
        $lines.Add("")
    }
    else {
        Add-M002ResultTable -Lines $lines -Results $GateResults
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

function Add-M002GitResult {
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

    $Results.Add((New-M002Result `
        -Name $Name `
        -Command $Command `
        -ExitCode $ExitCode `
        -OutputLines $OutputLines `
        -Status $Status `
        -Observation $Observation `
        -StartedAtUtc $StartedAtUtc `
        -CompletedAtUtc $CompletedAtUtc)) | Out-Null
}

function Add-M002GateResult {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateNotNull()]
        [object] $Results,

        [Parameter(Mandatory = $true)]
        [object] $ProcessResult,

        [Parameter(Mandatory = $true)]
        [string] $Status,

        [Parameter(Mandatory = $true)]
        [string] $Observation
    )

    $Results.Add((New-M002Result `
        -Name $ProcessResult.Name `
        -Command $ProcessResult.Command `
        -ExitCode $ProcessResult.ExitCode `
        -OutputLines $ProcessResult.OutputLines `
        -Status $Status `
        -Observation $Observation `
        -StartedAtUtc $ProcessResult.StartedAtUtc `
        -CompletedAtUtc $ProcessResult.CompletedAtUtc)) | Out-Null
}

$reportPath = Resolve-M002ReportPath -ReportPath $Path
$gitResults = New-Object System.Collections.Generic.List[object]
$gateResults = New-Object System.Collections.Generic.List[object]

$currentBranchResult = Invoke-M002Process `
    -Name "branche courante" `
    -Command "git rev-parse --abbrev-ref HEAD" `
    -Executable "git" `
    -Arguments @("-C", $repoRoot, "rev-parse", "--abbrev-ref", "HEAD")
$currentBranch = if ($currentBranchResult.OutputLines.Count -eq 0) { "" } else { $currentBranchResult.OutputLines[0].Trim() }
if (($currentBranchResult.ExitCode -eq 0) -and ($currentBranch -eq $expectedBranch)) {
    Add-M002GitResult -Results $gitResults -Name "branche courante" -Command $currentBranchResult.Command -ExitCode 0 -OutputLines $currentBranchResult.OutputLines -Status "GREEN" -Observation "Branche M-002 attendue active: $currentBranch" -StartedAtUtc $currentBranchResult.StartedAtUtc -CompletedAtUtc $currentBranchResult.CompletedAtUtc
}
else {
    Add-M002GitResult -Results $gitResults -Name "branche courante" -Command $currentBranchResult.Command -ExitCode $currentBranchResult.ExitCode -OutputLines $currentBranchResult.OutputLines -Status "RED" -Observation "Branche courante invalide. Attendu: $expectedBranch. Obtenu: $currentBranch" -StartedAtUtc $currentBranchResult.StartedAtUtc -CompletedAtUtc $currentBranchResult.CompletedAtUtc
}

$redGitResult = @($gitResults | Where-Object { $_.Status -eq "RED" } | Select-Object -First 1)
if ($redGitResult.Count -gt 0) {
    Write-M002PreconditionReport -ReportPath $reportPath -OverallStatus "RED" -GitResults $gitResults.ToArray() -GateResults $gateResults.ToArray()
    Write-Host "Précondition M-002 RED: $($redGitResult[0].Observation)"
    throw "Précondition M-002 RED: $($redGitResult[0].Observation)"
}

$masterResult = Invoke-M002Process `
    -Name "master local" `
    -Command "git rev-parse --verify master^{commit}" `
    -Executable "git" `
    -Arguments @("-C", $repoRoot, "rev-parse", "--verify", "master^{commit}")
if ($masterResult.ExitCode -eq 0) {
    $masterRevision = $masterResult.OutputLines[0].Trim()
    Add-M002GitResult -Results $gitResults -Name "master local" -Command $masterResult.Command -ExitCode 0 -OutputLines $masterResult.OutputLines -Status "GREEN" -Observation "Révision locale master: $masterRevision" -StartedAtUtc $masterResult.StartedAtUtc -CompletedAtUtc $masterResult.CompletedAtUtc
}
else {
    Add-M002GitResult -Results $gitResults -Name "master local" -Command $masterResult.Command -ExitCode $masterResult.ExitCode -OutputLines $masterResult.OutputLines -Status "RED" -Observation "Référence locale master absente." -StartedAtUtc $masterResult.StartedAtUtc -CompletedAtUtc $masterResult.CompletedAtUtc
}

$redGitResult = @($gitResults | Where-Object { $_.Status -eq "RED" } | Select-Object -First 1)
if ($redGitResult.Count -gt 0) {
    Write-M002PreconditionReport -ReportPath $reportPath -OverallStatus "RED" -GitResults $gitResults.ToArray() -GateResults $gateResults.ToArray()
    Write-Host "Précondition M-002 RED: $($redGitResult[0].Observation)"
    throw "Précondition M-002 RED: $($redGitResult[0].Observation)"
}

$ancestorResult = Invoke-M002Process `
    -Name "branche contient master" `
    -Command "git merge-base --is-ancestor master HEAD" `
    -Executable "git" `
    -Arguments @("-C", $repoRoot, "merge-base", "--is-ancestor", "master", "HEAD")
if ($ancestorResult.ExitCode -eq 0) {
    Add-M002GitResult -Results $gitResults -Name "branche contient master" -Command $ancestorResult.Command -ExitCode 0 -OutputLines $ancestorResult.OutputLines -Status "GREEN" -Observation "La branche courante contient la révision locale master." -StartedAtUtc $ancestorResult.StartedAtUtc -CompletedAtUtc $ancestorResult.CompletedAtUtc
}
else {
    Add-M002GitResult -Results $gitResults -Name "branche contient master" -Command $ancestorResult.Command -ExitCode $ancestorResult.ExitCode -OutputLines $ancestorResult.OutputLines -Status "RED" -Observation "La branche courante ne contient pas la révision locale master." -StartedAtUtc $ancestorResult.StartedAtUtc -CompletedAtUtc $ancestorResult.CompletedAtUtc
}

$redGitResult = @($gitResults | Where-Object { $_.Status -eq "RED" } | Select-Object -First 1)
if ($redGitResult.Count -gt 0) {
    Write-M002PreconditionReport -ReportPath $reportPath -OverallStatus "RED" -GitResults $gitResults.ToArray() -GateResults $gateResults.ToArray()
    Write-Host "Précondition M-002 RED: $($redGitResult[0].Observation)"
    throw "Précondition M-002 RED: $($redGitResult[0].Observation)"
}

foreach ($requiredMilestonePath in $requiredMilestonePaths) {
    $milestoneResult = Invoke-M002Process `
        -Name "$requiredMilestonePath dans master" `
        -Command "git ls-tree -r --name-only master -- $requiredMilestonePath" `
        -Executable "git" `
        -Arguments @("-C", $repoRoot, "ls-tree", "-r", "--name-only", "master", "--", $requiredMilestonePath)
    $matchingPaths = @($milestoneResult.OutputLines | Where-Object { $_ -like "$requiredMilestonePath/*" })

    if (($milestoneResult.ExitCode -eq 0) -and ($matchingPaths.Count -gt 0)) {
        Add-M002GitResult -Results $gitResults -Name "$requiredMilestonePath dans master" -Command $milestoneResult.Command -ExitCode 0 -OutputLines $milestoneResult.OutputLines -Status "GREEN" -Observation "Milestone amont présent dans master: $requiredMilestonePath" -StartedAtUtc $milestoneResult.StartedAtUtc -CompletedAtUtc $milestoneResult.CompletedAtUtc
    }
    else {
        Add-M002GitResult -Results $gitResults -Name "$requiredMilestonePath dans master" -Command $milestoneResult.Command -ExitCode $milestoneResult.ExitCode -OutputLines $milestoneResult.OutputLines -Status "RED" -Observation "Milestone amont absent de master: $requiredMilestonePath" -StartedAtUtc $milestoneResult.StartedAtUtc -CompletedAtUtc $milestoneResult.CompletedAtUtc
    }
}

$redGitResult = @($gitResults | Where-Object { $_.Status -eq "RED" } | Select-Object -First 1)
if ($redGitResult.Count -gt 0) {
    Write-M002PreconditionReport -ReportPath $reportPath -OverallStatus "RED" -GitResults $gitResults.ToArray() -GateResults $gateResults.ToArray()
    Write-Host "Précondition M-002 RED: $($redGitResult[0].Observation)"
    throw "Précondition M-002 RED: $($redGitResult[0].Observation)"
}

foreach ($gateDefinition in $gateDefinitions) {
    $scriptPath = Join-Path $repoRoot $gateDefinition["Script"]
    $gateResult = Invoke-M002Process `
        -Name $gateDefinition["Name"] `
        -Command $gateDefinition["Command"] `
        -Executable "powershell" `
        -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $scriptPath)

    foreach ($outputLine in $gateResult.OutputLines) {
        Write-Host $outputLine
    }

    if ($gateResult.ExitCode -eq 0) {
        Add-M002GateResult -Results $gateResults -ProcessResult $gateResult -Status "GREEN" -Observation "Gate $($gateDefinition["Name"]) GREEN."
    }
    else {
        Add-M002GateResult -Results $gateResults -ProcessResult $gateResult -Status "RED" -Observation "Gate M-002 RED: $($gateDefinition["Name"])"
        Write-M002PreconditionReport -ReportPath $reportPath -OverallStatus "RED" -GitResults $gitResults.ToArray() -GateResults $gateResults.ToArray()
        Write-Host "Gate M-002 RED: $($gateDefinition["Name"])"
        throw "Gate M-002 RED: $($gateDefinition["Name"])"
    }
}

Write-M002PreconditionReport -ReportPath $reportPath -OverallStatus "GREEN" -GitResults $gitResults.ToArray() -GateResults $gateResults.ToArray()
Write-Host "Précondition M-002 GREEN: 2 gate(s), 2 milestone(s) amont vérifié(s). Rapport: $reportPath"
