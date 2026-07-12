param(
    [Parameter(Mandatory = $false)]
    [string] $Path,

    [Parameter(Mandatory = $false)]
    [int] $GateTimeoutSeconds = 600
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$allowedBranches = @(
    "master",
    "codex/milestone-m006-claims-verifiables",
    "codex/milestone-m007-reponse-documentaire-verifiee",
    "codex/milestone-m008-conversation-produit",
    "codex/milestone-m009-recherche-approfondie",
    "codex/milestone-m010-strategie-candidate-attribuee",
    "codex/milestone-m011-experience-reproductible",
    "codex/milestone-m012-evaluation-pilote-calibration",
    "codex/milestone-m013-durcissement-acceptation-v1",
    "codex/m13-config",
    "codex/m13-fastapi"
)
$requiredMasterArtifacts = @(
    [ordered] @{ Path = "docs/tasks/milestone_004"; Kind = "Directory" },
    [ordered] @{ Path = "docs/tasks/milestone_005"; Kind = "Directory" },
    [ordered] @{ Path = "docs/specs/m005_projection_connaissance_recherchable.md"; Kind = "File" },
    [ordered] @{ Path = "tests/m005"; Kind = "Directory" },
    [ordered] @{ Path = "docs/governance/m005_precondition_green.md"; Kind = "File" },
    [ordered] @{ Path = "scripts/test.ps1"; Kind = "File" },
    [ordered] @{ Path = "scripts/lint.ps1"; Kind = "File" }
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

function Assert-M006Condition {
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

function Resolve-M006ReportPath {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string] $ReportPath
    )

    Assert-M006Condition `
        -Condition (-not [string]::IsNullOrWhiteSpace($ReportPath)) `
        -Message "Chemin de rapport M-006 obligatoire via -Path."

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
    Assert-M006Condition `
        -Condition ($resolvedReportPath.StartsWith($repoRootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) `
        -Message "Chemin de rapport M-006 hors dépôt: $resolvedReportPath"

    $reportDirectory = Split-Path -Parent $resolvedReportPath
    Assert-M006Condition `
        -Condition (-not [string]::IsNullOrWhiteSpace($reportDirectory)) `
        -Message "Répertoire de rapport M-006 introuvable pour le chemin: $ReportPath"

    Assert-M006Condition `
        -Condition (Test-Path -LiteralPath $reportDirectory -PathType Container) `
        -Message "Répertoire de rapport M-006 absent: $reportDirectory"

    return $resolvedReportPath
}

function Invoke-M006Process {
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
        TimedOut = $false
        StartedAtUtc = $startedAtUtc
        CompletedAtUtc = $completedAtUtc
    }
}

function Invoke-M006TimedProcess {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name,

        [Parameter(Mandatory = $true)]
        [string] $Command,

        [Parameter(Mandatory = $true)]
        [string] $Executable,

        [Parameter(Mandatory = $true)]
        [string[]] $Arguments,

        [Parameter(Mandatory = $true)]
        [int] $TimeoutSeconds
    )

    Assert-M006Condition `
        -Condition ($TimeoutSeconds -gt 0) `
        -Message "Timeout de gate M-006 invalide: $TimeoutSeconds"

    $startedAtUtc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    $timedOut = $false
    $exitCode = 0

    $quotedArguments = @(
        $Arguments | ForEach-Object {
            $argument = [string] $_
            if (($argument -match "\s") -or ($argument.Contains('"'))) {
                '"' + $argument.Replace('"', '\"') + '"'
            }
            else {
                $argument
            }
        }
    )

    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $Executable
    $startInfo.Arguments = ($quotedArguments -join " ")
    $startInfo.WorkingDirectory = $repoRoot
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.CreateNoWindow = $true
    $processOutputEncoding = [System.Text.Encoding]::UTF8
    $startInfo.StandardOutputEncoding = $processOutputEncoding
    $startInfo.StandardErrorEncoding = $processOutputEncoding

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    [void] $process.Start()
    $standardOutputTask = $process.StandardOutput.ReadToEndAsync()
    $standardErrorTask = $process.StandardError.ReadToEndAsync()

    $timeoutMilliseconds = $TimeoutSeconds * 1000
    if (-not $process.WaitForExit($timeoutMilliseconds)) {
        $timedOut = $true
        $previousKillErrorActionPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try {
            if (-not $process.HasExited) {
                $taskKillOutput = & taskkill.exe /PID $process.Id /T /F 2>&1
            }
        }
        finally {
            $ErrorActionPreference = $previousKillErrorActionPreference
        }
        if (-not $process.WaitForExit(5000)) {
            throw "Processus de gate M-006 non arrêté après timeout: $($process.Id)"
        }
        $exitCode = 124
    }
    else {
        $process.WaitForExit() | Out-Null
        $exitCode = [int] $process.ExitCode
    }

    $standardOutput = $standardOutputTask.Result
    $standardError = $standardErrorTask.Result

    $outputLines = New-Object System.Collections.Generic.List[string]
    $streamContents = @($standardOutput)
    if (($exitCode -ne 0) -or $timedOut) {
        $streamContents += $standardError
    }

    foreach ($streamContent in $streamContents) {
        if ([string]::IsNullOrEmpty($streamContent)) {
            continue
        }

        foreach ($line in ($streamContent -split "`r?`n")) {
            if ($line.Length -gt 0) {
                $outputLines.Add([string] $line) | Out-Null
            }
        }
    }

    $completedAtUtc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

    return [pscustomobject] @{
        Name = $Name
        Command = $Command
        ExitCode = $exitCode
        OutputLines = $outputLines.ToArray()
        TimedOut = $timedOut
        StartedAtUtc = $startedAtUtc
        CompletedAtUtc = $completedAtUtc
    }
}

function Invoke-M006GateProcess {
    param(
        [Parameter(Mandatory = $true)]
        [object] $GateDefinition
    )

    $scriptPath = Join-Path $repoRoot $GateDefinition["Script"]
    $previousRecursionGuard = $env:OST_M006_PRECONDITION_ACCEPTANCE_RUNNING

    if ($GateDefinition["Name"] -eq "test") {
        $env:OST_M006_PRECONDITION_ACCEPTANCE_RUNNING = "1"
    }

    try {
        $escapedScriptPath = $scriptPath.Replace("'", "''")
        $commandText = "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; `$env:PYTHONIOENCODING = 'utf-8'; & '$escapedScriptPath'; exit `$LASTEXITCODE"
        $encodedCommand = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($commandText))

        return Invoke-M006TimedProcess `
            -Name $GateDefinition["Name"] `
            -Command $GateDefinition["Command"] `
            -Executable "powershell" `
            -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-OutputFormat", "Text", "-EncodedCommand", $encodedCommand) `
            -TimeoutSeconds $GateTimeoutSeconds
    }
    finally {
        if ($GateDefinition["Name"] -eq "test") {
            if ($null -eq $previousRecursionGuard) {
                Remove-Item Env:\OST_M006_PRECONDITION_ACCEPTANCE_RUNNING -ErrorAction SilentlyContinue
            }
            else {
                $env:OST_M006_PRECONDITION_ACCEPTANCE_RUNNING = $previousRecursionGuard
            }
        }
    }
}

function ConvertTo-M006MarkdownCell {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string] $Value
    )

    return $Value.Replace("|", "\|").Replace("`r", " ").Replace("`n", " ")
}

function Add-M006Result {
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

function Add-M006ResultTable {
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
        $Lines.Add("| ``$($result.Name)`` | ``$($result.Command)`` | ``$($result.CompletedAtUtc)`` | ``$($result.Status)`` | $(ConvertTo-M006MarkdownCell -Value $result.Observation) |")
    }
}

function Write-M006PreconditionReport {
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
    $lines.Add("# Rapport de précondition GREEN M-006")
    $lines.Add("")
    $lines.Add("## Scénario BDD")
    $lines.Add("")
    $lines.Add("- Given M-004 et M-005 sont présents dans ``master``.")
    $lines.Add("- When les gates de précondition M-006 sont exécutées.")
    $lines.Add("- Then M-006 ne peut commencer que si les validations, la traçabilité, les ADR, les frontières d'architecture et les preuves M-005 sont GREEN ou si le blocage exact est isolé.")
    $lines.Add("")
    $lines.Add("## Résultat")
    $lines.Add("")
    $lines.Add("- Statut: ``$OverallStatus``")
    $allowedBranchLabel = $allowedBranches -join "; "
    $lines.Add("- Branches autorisées: ``$allowedBranchLabel``")
    $lines.Add("- M-006 s'appuie sur les preuves amont M-004 et M-005 publiées dans master.")
    $lines.Add("")
    $lines.Add("## Vérifications Git")
    $lines.Add("")
    Add-M006ResultTable -Lines $lines -Results $GitResults
    $lines.Add("")
    $lines.Add("## Gates exécutées")
    $lines.Add("")

    if ($GateResults.Count -eq 0) {
        $lines.Add("Aucune gate exécutée: une précondition Git est RED.")
        $lines.Add("")
    }
    else {
        Add-M006ResultTable -Lines $lines -Results $GateResults
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

function Stop-M006OnRedGitResult {
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
        Write-M006PreconditionReport -ReportPath $ReportPath -OverallStatus "RED" -GitResults $GitResults.ToArray() -GateResults $GateResults.ToArray()
        Write-Host "Précondition M-006 RED: $($redGitResult[0].Observation)"
        throw "Précondition M-006 RED: $($redGitResult[0].Observation)"
    }
}

function Test-M006MasterArtifactPresent {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyCollection()]
        [string[]] $OutputLines,

        [Parameter(Mandatory = $true)]
        [string] $ArtifactPath,

        [Parameter(Mandatory = $true)]
        [string] $Kind
    )

    if ($Kind -eq "Directory") {
        return (@($OutputLines | Where-Object { $_ -like "$ArtifactPath/*" }).Count -gt 0)
    }

    if ($Kind -eq "File") {
        return ($OutputLines -contains $ArtifactPath)
    }

    throw "Type d'artefact M-006 inconnu: $Kind"
}

$reportPath = Resolve-M006ReportPath -ReportPath $Path
$gitResults = New-Object System.Collections.Generic.List[object]
$gateResults = New-Object System.Collections.Generic.List[object]

$currentBranchResult = Invoke-M006Process `
    -Name "branche courante" `
    -Command "git rev-parse --abbrev-ref HEAD" `
    -Executable "git" `
    -Arguments @("-C", $repoRoot, "rev-parse", "--abbrev-ref", "HEAD")
$currentBranch = if ($currentBranchResult.OutputLines.Count -eq 0) { "" } else { $currentBranchResult.OutputLines[0].Trim() }
if (($currentBranchResult.ExitCode -eq 0) -and ($allowedBranches -contains $currentBranch)) {
    $branchObservation = "Branche M-006 autorisée: $currentBranch"
    Add-M006Result -Results $gitResults -Name "branche courante" -Command $currentBranchResult.Command -ExitCode 0 -OutputLines $currentBranchResult.OutputLines -Status "GREEN" -Observation $branchObservation -StartedAtUtc $currentBranchResult.StartedAtUtc -CompletedAtUtc $currentBranchResult.CompletedAtUtc
    Write-Host $branchObservation
}
else {
    $allowedBranchList = $allowedBranches -join ", "
    Add-M006Result -Results $gitResults -Name "branche courante" -Command $currentBranchResult.Command -ExitCode $currentBranchResult.ExitCode -OutputLines $currentBranchResult.OutputLines -Status "RED" -Observation "Branche courante invalide. Autorisées: $allowedBranchList. Obtenu: $currentBranch" -StartedAtUtc $currentBranchResult.StartedAtUtc -CompletedAtUtc $currentBranchResult.CompletedAtUtc
}

Stop-M006OnRedGitResult -GitResults $gitResults -GateResults $gateResults -ReportPath $reportPath

$masterResult = Invoke-M006Process `
    -Name "master local" `
    -Command "git rev-parse --verify master^{commit}" `
    -Executable "git" `
    -Arguments @("-C", $repoRoot, "rev-parse", "--verify", "master^{commit}")
if ($masterResult.ExitCode -eq 0) {
    $masterRevision = $masterResult.OutputLines[0].Trim()
    Add-M006Result -Results $gitResults -Name "master local" -Command $masterResult.Command -ExitCode 0 -OutputLines $masterResult.OutputLines -Status "GREEN" -Observation "Révision locale master: $masterRevision" -StartedAtUtc $masterResult.StartedAtUtc -CompletedAtUtc $masterResult.CompletedAtUtc
}
else {
    $masterRevision = ""
    Add-M006Result -Results $gitResults -Name "master local" -Command $masterResult.Command -ExitCode $masterResult.ExitCode -OutputLines $masterResult.OutputLines -Status "RED" -Observation "Référence locale master absente." -StartedAtUtc $masterResult.StartedAtUtc -CompletedAtUtc $masterResult.CompletedAtUtc
}

Stop-M006OnRedGitResult -GitResults $gitResults -GateResults $gateResults -ReportPath $reportPath

$originMasterResult = Invoke-M006Process `
    -Name "origin/master" `
    -Command "git rev-parse --verify origin/master^{commit}" `
    -Executable "git" `
    -Arguments @("-C", $repoRoot, "rev-parse", "--verify", "origin/master^{commit}")
if ($originMasterResult.ExitCode -eq 0) {
    $originMasterRevision = $originMasterResult.OutputLines[0].Trim()
    Add-M006Result -Results $gitResults -Name "origin/master" -Command $originMasterResult.Command -ExitCode 0 -OutputLines $originMasterResult.OutputLines -Status "GREEN" -Observation "Révision origin/master: $originMasterRevision" -StartedAtUtc $originMasterResult.StartedAtUtc -CompletedAtUtc $originMasterResult.CompletedAtUtc
}
else {
    $originMasterRevision = ""
    Add-M006Result -Results $gitResults -Name "origin/master" -Command $originMasterResult.Command -ExitCode $originMasterResult.ExitCode -OutputLines $originMasterResult.OutputLines -Status "RED" -Observation "Référence origin/master absente." -StartedAtUtc $originMasterResult.StartedAtUtc -CompletedAtUtc $originMasterResult.CompletedAtUtc
}

Stop-M006OnRedGitResult -GitResults $gitResults -GateResults $gateResults -ReportPath $reportPath

$masterContainsOriginResult = Invoke-M006Process `
    -Name "master contient origin/master" `
    -Command "git merge-base --is-ancestor origin/master master" `
    -Executable "git" `
    -Arguments @("-C", $repoRoot, "merge-base", "--is-ancestor", "origin/master", "master")
if ($masterContainsOriginResult.ExitCode -eq 0) {
    Add-M006Result -Results $gitResults -Name "master contient origin/master" -Command $masterContainsOriginResult.Command -ExitCode 0 -OutputLines @($masterRevision, $originMasterRevision) -Status "GREEN" -Observation "La référence master contient origin/master." -StartedAtUtc $masterContainsOriginResult.StartedAtUtc -CompletedAtUtc $masterContainsOriginResult.CompletedAtUtc
}
else {
    Add-M006Result -Results $gitResults -Name "master contient origin/master" -Command $masterContainsOriginResult.Command -ExitCode $masterContainsOriginResult.ExitCode -OutputLines @($masterRevision, $originMasterRevision) -Status "RED" -Observation "Référence master divergente entre master et origin/master." -StartedAtUtc $masterContainsOriginResult.StartedAtUtc -CompletedAtUtc $masterContainsOriginResult.CompletedAtUtc
}

Stop-M006OnRedGitResult -GitResults $gitResults -GateResults $gateResults -ReportPath $reportPath

$ancestorResult = Invoke-M006Process `
    -Name "branche contient master" `
    -Command "git merge-base --is-ancestor master HEAD" `
    -Executable "git" `
    -Arguments @("-C", $repoRoot, "merge-base", "--is-ancestor", "master", "HEAD")
if ($ancestorResult.ExitCode -eq 0) {
    Add-M006Result -Results $gitResults -Name "branche contient master" -Command $ancestorResult.Command -ExitCode 0 -OutputLines $ancestorResult.OutputLines -Status "GREEN" -Observation "La branche courante contient la révision locale master." -StartedAtUtc $ancestorResult.StartedAtUtc -CompletedAtUtc $ancestorResult.CompletedAtUtc
}
else {
    Add-M006Result -Results $gitResults -Name "branche contient master" -Command $ancestorResult.Command -ExitCode $ancestorResult.ExitCode -OutputLines $ancestorResult.OutputLines -Status "RED" -Observation "La branche courante ne contient pas la révision locale master." -StartedAtUtc $ancestorResult.StartedAtUtc -CompletedAtUtc $ancestorResult.CompletedAtUtc
}

Stop-M006OnRedGitResult -GitResults $gitResults -GateResults $gateResults -ReportPath $reportPath

foreach ($requiredArtifact in $requiredMasterArtifacts) {
    $artifactPath = $requiredArtifact["Path"]
    $artifactKind = $requiredArtifact["Kind"]
    $artifactResult = Invoke-M006Process `
        -Name "$artifactPath dans master" `
        -Command "git ls-tree -r --name-only master -- $artifactPath" `
        -Executable "git" `
        -Arguments @("-C", $repoRoot, "ls-tree", "-r", "--name-only", "master", "--", $artifactPath)

    if (($artifactResult.ExitCode -eq 0) -and (Test-M006MasterArtifactPresent -OutputLines $artifactResult.OutputLines -ArtifactPath $artifactPath -Kind $artifactKind)) {
        Add-M006Result -Results $gitResults -Name "$artifactPath dans master" -Command $artifactResult.Command -ExitCode 0 -OutputLines $artifactResult.OutputLines -Status "GREEN" -Observation "Milestone ou preuve amont présent dans master: $artifactPath" -StartedAtUtc $artifactResult.StartedAtUtc -CompletedAtUtc $artifactResult.CompletedAtUtc
    }
    else {
        Add-M006Result -Results $gitResults -Name "$artifactPath dans master" -Command $artifactResult.Command -ExitCode $artifactResult.ExitCode -OutputLines $artifactResult.OutputLines -Status "RED" -Observation "Milestone ou preuve amont absent de master: $artifactPath" -StartedAtUtc $artifactResult.StartedAtUtc -CompletedAtUtc $artifactResult.CompletedAtUtc
    }
}

Stop-M006OnRedGitResult -GitResults $gitResults -GateResults $gateResults -ReportPath $reportPath

foreach ($gateDefinition in $gateDefinitions) {
    $gateResult = Invoke-M006GateProcess -GateDefinition $gateDefinition

    foreach ($outputLine in $gateResult.OutputLines) {
        Write-Host $outputLine
    }

    if ($gateResult.TimedOut) {
        $observation = "Gate M-006 RED: $($gateDefinition["Name"]) non concluant après $GateTimeoutSeconds seconde(s)."
        Add-M006Result -Results $gateResults -Name $gateResult.Name -Command $gateResult.Command -ExitCode $gateResult.ExitCode -OutputLines $gateResult.OutputLines -Status "RED" -Observation $observation -StartedAtUtc $gateResult.StartedAtUtc -CompletedAtUtc $gateResult.CompletedAtUtc
        Write-M006PreconditionReport -ReportPath $reportPath -OverallStatus "RED" -GitResults $gitResults.ToArray() -GateResults $gateResults.ToArray()
        Write-Host $observation
        throw $observation
    }

    if ($gateResult.OutputLines.Count -eq 0) {
        $observation = "Gate M-006 RED: $($gateDefinition["Name"]) sans sortie."
        Add-M006Result -Results $gateResults -Name $gateResult.Name -Command $gateResult.Command -ExitCode $gateResult.ExitCode -OutputLines $gateResult.OutputLines -Status "RED" -Observation $observation -StartedAtUtc $gateResult.StartedAtUtc -CompletedAtUtc $gateResult.CompletedAtUtc
        Write-M006PreconditionReport -ReportPath $reportPath -OverallStatus "RED" -GitResults $gitResults.ToArray() -GateResults $gateResults.ToArray()
        Write-Host $observation
        throw $observation
    }

    if ($gateResult.ExitCode -eq 0) {
        Add-M006Result -Results $gateResults -Name $gateResult.Name -Command $gateResult.Command -ExitCode $gateResult.ExitCode -OutputLines $gateResult.OutputLines -Status "GREEN" -Observation "Gate $($gateDefinition["Name"]) GREEN." -StartedAtUtc $gateResult.StartedAtUtc -CompletedAtUtc $gateResult.CompletedAtUtc
    }
    else {
        Add-M006Result -Results $gateResults -Name $gateResult.Name -Command $gateResult.Command -ExitCode $gateResult.ExitCode -OutputLines $gateResult.OutputLines -Status "RED" -Observation "Gate M-006 RED: $($gateDefinition["Name"])" -StartedAtUtc $gateResult.StartedAtUtc -CompletedAtUtc $gateResult.CompletedAtUtc
        Write-M006PreconditionReport -ReportPath $reportPath -OverallStatus "RED" -GitResults $gitResults.ToArray() -GateResults $gateResults.ToArray()
        Write-Host "Gate M-006 RED: $($gateDefinition["Name"])"
        throw "Gate M-006 RED: $($gateDefinition["Name"])"
    }
}

Write-M006PreconditionReport -ReportPath $reportPath -OverallStatus "GREEN" -GitResults $gitResults.ToArray() -GateResults $gateResults.ToArray()
Write-Host "Précondition M-006 GREEN: 2 gate(s), $($requiredMasterArtifacts.Count) artefact(s) amont vérifié(s). Rapport: $reportPath"
