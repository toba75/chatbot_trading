param(
    [Parameter(Mandatory = $false)]
    [string] $Path,

    [Parameter(Mandatory = $false)]
    [int] $GateTimeoutSeconds = 5400
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$m013Branch = "codex/milestone-m013-durcissement-acceptation-v1"
$m013ConfigBranch = "codex/m13-config"
$allowedBranches = @(
    "master",
    $m013Branch,
    $m013ConfigBranch
)
$requiredMasterArtifacts = @(
    [ordered] @{ Path = "docs/tasks/milestone_012"; Kind = "Directory" },
    [ordered] @{ Path = "docs/specs/m012_evaluation_pilote_calibration.md"; Kind = "File" },
    [ordered] @{ Path = "scripts/validate_m012_precondition.ps1"; Kind = "File" },
    [ordered] @{ Path = "scripts/validate_m012_specification.ps1"; Kind = "File" },
    [ordered] @{ Path = "scripts/validate_m012_traceability.ps1"; Kind = "File" },
    [ordered] @{ Path = "tests/m012"; Kind = "Directory" },
    [ordered] @{ Path = "app/evaluation"; Kind = "Directory" },
    [ordered] @{ Path = "docs/governance/m012_v1_gap_report.md"; Kind = "File" },
    [ordered] @{ Path = "docs/traceability/matrix.md"; Kind = "File" },
    [ordered] @{ Path = "scripts/test.ps1"; Kind = "File" },
    [ordered] @{ Path = "scripts/lint.ps1"; Kind = "File" },
    [ordered] @{ Path = "scripts/validate_task_system.ps1"; Kind = "File" }
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
$requiredUpstreamPreconditionValidators = @(
    [ordered] @{ Name = "M-003"; Path = "scripts/validate_m003_precondition.ps1" },
    [ordered] @{ Name = "M-004"; Path = "scripts/validate_m004_precondition.ps1" },
    [ordered] @{ Name = "M-005"; Path = "scripts/validate_m005_precondition.ps1" },
    [ordered] @{ Name = "M-006"; Path = "scripts/validate_m006_precondition.ps1" },
    [ordered] @{ Name = "M-007"; Path = "scripts/validate_m007_precondition.ps1" },
    [ordered] @{ Name = "M-008"; Path = "scripts/validate_m008_precondition.ps1" },
    [ordered] @{ Name = "M-009"; Path = "scripts/validate_m009_precondition.ps1" },
    [ordered] @{ Name = "M-010"; Path = "scripts/validate_m010_precondition.ps1" },
    [ordered] @{ Name = "M-011"; Path = "scripts/validate_m011_precondition.ps1" },
    [ordered] @{ Name = "M-012"; Path = "scripts/validate_m012_precondition.ps1" }
)
$eAcute = [char] 0x00E9
$requiredGapContexts = @("SP", "KA", "EG", "RA", "CV", "SD", "LLM", "EX")
$allowedGapStatuses = @("satisfait", "bloquant", "accept$eAcute", ("diff$eAcute" + "r$eAcute"))
$requiredTestGateEvidence = @(
    "Test GREEN: tests/m013/validate_m013_precondition_unit.ps1",
    "Validation GREEN: scripts/validate_traceability.ps1",
    "Validation GREEN: scripts/validate_m012_traceability.ps1",
    "Validation GREEN: scripts/validate_adr_system.ps1"
)

function Assert-M013Condition {
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

function Resolve-M013ReportPath {
    param(
        [Parameter(Mandatory = $false)]
        [AllowEmptyString()]
        [string] $ReportPath
    )

    if ([string]::IsNullOrWhiteSpace($ReportPath)) {
        $ReportPath = "docs/governance/m013_precondition_green.md"
    }

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
    Assert-M013Condition `
        -Condition ($resolvedReportPath.StartsWith($repoRootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) `
        -Message "Chemin de rapport M-013 hors dépôt: $resolvedReportPath"

    $reportDirectory = Split-Path -Parent $resolvedReportPath
    Assert-M013Condition `
        -Condition (-not [string]::IsNullOrWhiteSpace($reportDirectory)) `
        -Message "Répertoire de rapport M-013 introuvable pour le chemin: $ReportPath"

    Assert-M013Condition `
        -Condition (Test-Path -LiteralPath $reportDirectory -PathType Container) `
        -Message "Répertoire de rapport M-013 absent: $reportDirectory"

    return $resolvedReportPath
}

function Invoke-M013Process {
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

function Invoke-M013TimedProcess {
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

    Assert-M013Condition `
        -Condition ($TimeoutSeconds -gt 0) `
        -Message "Timeout de gate M-013 invalide: $TimeoutSeconds"

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
            throw "Processus de gate M-013 non arrêté après timeout: $($process.Id)"
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

function Invoke-M013GateProcess {
    param(
        [Parameter(Mandatory = $true)]
        [object] $GateDefinition
    )

    $scriptPath = Join-Path $repoRoot $GateDefinition["Script"]
    $previousRecursionGuard = $env:OST_M013_PRECONDITION_ACCEPTANCE_RUNNING

    if ($GateDefinition["Name"] -eq "test") {
        $env:OST_M013_PRECONDITION_ACCEPTANCE_RUNNING = "1"
    }

    try {
        $escapedScriptPath = $scriptPath.Replace("'", "''")
        $commandText = "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; `$env:PYTHONIOENCODING = 'utf-8'; & '$escapedScriptPath'; exit `$LASTEXITCODE"
        $encodedCommand = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($commandText))

        return Invoke-M013TimedProcess `
            -Name $GateDefinition["Name"] `
            -Command $GateDefinition["Command"] `
            -Executable "powershell" `
            -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-OutputFormat", "Text", "-EncodedCommand", $encodedCommand) `
            -TimeoutSeconds $GateTimeoutSeconds
    }
    finally {
        if ($GateDefinition["Name"] -eq "test") {
            if ($null -eq $previousRecursionGuard) {
                Remove-Item Env:\OST_M013_PRECONDITION_ACCEPTANCE_RUNNING -ErrorAction SilentlyContinue
            }
            else {
                $env:OST_M013_PRECONDITION_ACCEPTANCE_RUNNING = $previousRecursionGuard
            }
        }
    }
}

function ConvertTo-M013MarkdownCell {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string] $Value
    )

    return $Value.Replace("|", "\|").Replace("`r", " ").Replace("`n", " ")
}

function Add-M013Result {
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
        [AllowEmptyString()]
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

function Add-M013ResultTable {
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
        $Lines.Add("| ``$($result.Name)`` | ``$($result.Command)`` | ``$($result.CompletedAtUtc)`` | ``$($result.Status)`` | $(ConvertTo-M013MarkdownCell -Value $result.Observation) |")
    }
}

function Write-M013PreconditionReport {
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
    $lines.Add("# Rapport de précondition GREEN M-013")
    $lines.Add("")
    $lines.Add("## Scénario BDD")
    $lines.Add("")
    $lines.Add("- Given M-012 est présent dans ``master`` avec ses tâches, sa spécification, ses validateurs, ses tests, son contexte EV et son rapport d'écarts V1.")
    $lines.Add("- When les gates de précondition M-013 sont exécutées sur une branche M-013 créée depuis ``master``.")
    $lines.Add("- Then M-013 ne peut commencer que si la présence M-012, les écarts V1, la branche de travail et les gates amont ont un verdict explicite.")
    $lines.Add("")
    $lines.Add("## Résultat")
    $lines.Add("")
    $lines.Add("- Statut: ``$OverallStatus``")
    $allowedBranchLabel = $allowedBranches -join "; "
    $lines.Add("- Branches autorisées: ``$allowedBranchLabel``")
    $lines.Add("- M-013 consomme le rapport d'écarts V1 M-012 sans requalifier les statuts scientifiques ni masquer les tests RED conservés.")
    $lines.Add("")
    $lines.Add("## Vérifications Git Et V1")
    $lines.Add("")
    Add-M013ResultTable -Lines $lines -Results $GitResults
    $lines.Add("")
    $lines.Add("## Gates exécutées")
    $lines.Add("")

    if ($GateResults.Count -eq 0) {
        $lines.Add("Aucune gate exécutée: une précondition Git ou V1 est RED.")
        $lines.Add("")
    }
    else {
        Add-M013ResultTable -Lines $lines -Results $GateResults
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

function Stop-M013OnRedGitResult {
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
        Write-M013PreconditionReport -ReportPath $ReportPath -OverallStatus "RED" -GitResults $GitResults.ToArray() -GateResults $GateResults.ToArray()
        Write-Host "Précondition M-013 RED: $($redGitResult[0].Observation)"
        throw "Précondition M-013 RED: $($redGitResult[0].Observation)"
    }
}

function Test-M013MasterArtifactPresent {
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

    throw "Type d'artefact M-013 inconnu: $Kind"
}

function Test-M013GateEvidencePresent {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyCollection()]
        [string[]] $OutputLines,

        [Parameter(Mandatory = $true)]
        [string] $ExpectedEvidence
    )

    return (@($OutputLines | Where-Object { $_.Contains($ExpectedEvidence) }).Count -gt 0)
}

function Test-M013UpstreamValidatorAcceptsBranch {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ValidatorPath,

        [Parameter(Mandatory = $true)]
        [string] $BranchName
    )

    $fullValidatorPath = Join-Path $repoRoot $ValidatorPath
    Assert-M013Condition `
        -Condition (Test-Path -LiteralPath $fullValidatorPath -PathType Leaf) `
        -Message "Validateur amont M-013 absent: $ValidatorPath"

    $content = Get-Content -Raw -Encoding UTF8 -LiteralPath $fullValidatorPath
    return $content.Contains($BranchName)
}

function ConvertFrom-M013GapStatuses {
    param(
        [Parameter(Mandatory = $true)]
        [string] $GapReportContent
    )

    $statusesByContext = @{}
    foreach ($line in ($GapReportContent -split "`r?`n")) {
        if ($line -notmatch "^\|") {
            continue
        }

        $cells = @($line.Trim().Trim("|").Split("|") | ForEach-Object { $_.Trim() })
        if ($cells.Count -lt 2) {
            continue
        }

        $context = $cells[0]
        if (($requiredGapContexts -contains $context) -and (-not $statusesByContext.ContainsKey($context))) {
            $statusesByContext[$context] = $cells[1]
        }
    }

    return $statusesByContext
}

$reportPath = Resolve-M013ReportPath -ReportPath $Path
$gitResults = New-Object System.Collections.Generic.List[object]
$gateResults = New-Object System.Collections.Generic.List[object]

$currentBranchResult = Invoke-M013Process `
    -Name "branche courante" `
    -Command "git rev-parse --abbrev-ref HEAD" `
    -Executable "git" `
    -Arguments @("-C", $repoRoot, "rev-parse", "--abbrev-ref", "HEAD")
$currentBranch = if ($currentBranchResult.OutputLines.Count -eq 0) { "" } else { $currentBranchResult.OutputLines[0].Trim() }
if (($currentBranchResult.ExitCode -eq 0) -and ($allowedBranches -contains $currentBranch)) {
    if ($currentBranch -eq "master") {
        $branchObservation = "Branche master autorisée pour vérifier la précondition M-013 après fusion: $currentBranch"
    }
    else {
        $branchObservation = "Branche M-013 autorisée: $currentBranch"
    }
    Add-M013Result -Results $gitResults -Name "branche courante" -Command $currentBranchResult.Command -ExitCode 0 -OutputLines $currentBranchResult.OutputLines -Status "GREEN" -Observation $branchObservation -StartedAtUtc $currentBranchResult.StartedAtUtc -CompletedAtUtc $currentBranchResult.CompletedAtUtc
    Write-Host $branchObservation
}
else {
    $allowedBranchList = $allowedBranches -join ", "
    Add-M013Result -Results $gitResults -Name "branche courante" -Command $currentBranchResult.Command -ExitCode $currentBranchResult.ExitCode -OutputLines $currentBranchResult.OutputLines -Status "RED" -Observation "Branche courante invalide. Autorisées: $allowedBranchList. Obtenu: $currentBranch" -StartedAtUtc $currentBranchResult.StartedAtUtc -CompletedAtUtc $currentBranchResult.CompletedAtUtc
}

Stop-M013OnRedGitResult -GitResults $gitResults -GateResults $gateResults -ReportPath $reportPath

$masterResult = Invoke-M013Process `
    -Name "master local" `
    -Command "git rev-parse --verify master^{commit}" `
    -Executable "git" `
    -Arguments @("-C", $repoRoot, "rev-parse", "--verify", "master^{commit}")
if ($masterResult.ExitCode -eq 0) {
    $masterRevision = $masterResult.OutputLines[0].Trim()
    Add-M013Result -Results $gitResults -Name "master local" -Command $masterResult.Command -ExitCode 0 -OutputLines $masterResult.OutputLines -Status "GREEN" -Observation "Révision locale master: $masterRevision" -StartedAtUtc $masterResult.StartedAtUtc -CompletedAtUtc $masterResult.CompletedAtUtc
}
else {
    $masterRevision = ""
    Add-M013Result -Results $gitResults -Name "master local" -Command $masterResult.Command -ExitCode $masterResult.ExitCode -OutputLines $masterResult.OutputLines -Status "RED" -Observation "Référence locale master absente." -StartedAtUtc $masterResult.StartedAtUtc -CompletedAtUtc $masterResult.CompletedAtUtc
}

Stop-M013OnRedGitResult -GitResults $gitResults -GateResults $gateResults -ReportPath $reportPath

$originMasterResult = Invoke-M013Process `
    -Name "origin/master" `
    -Command "git rev-parse --verify origin/master^{commit}" `
    -Executable "git" `
    -Arguments @("-C", $repoRoot, "rev-parse", "--verify", "origin/master^{commit}")
if ($originMasterResult.ExitCode -eq 0) {
    $originMasterRevision = $originMasterResult.OutputLines[0].Trim()
    Add-M013Result -Results $gitResults -Name "origin/master" -Command $originMasterResult.Command -ExitCode 0 -OutputLines $originMasterResult.OutputLines -Status "GREEN" -Observation "Révision origin/master: $originMasterRevision" -StartedAtUtc $originMasterResult.StartedAtUtc -CompletedAtUtc $originMasterResult.CompletedAtUtc
}
else {
    $originMasterRevision = ""
    Add-M013Result -Results $gitResults -Name "origin/master" -Command $originMasterResult.Command -ExitCode $originMasterResult.ExitCode -OutputLines $originMasterResult.OutputLines -Status "RED" -Observation "Référence origin/master absente." -StartedAtUtc $originMasterResult.StartedAtUtc -CompletedAtUtc $originMasterResult.CompletedAtUtc
}

Stop-M013OnRedGitResult -GitResults $gitResults -GateResults $gateResults -ReportPath $reportPath

$masterContainsOriginResult = Invoke-M013Process `
    -Name "master contient origin/master" `
    -Command "git merge-base --is-ancestor origin/master master" `
    -Executable "git" `
    -Arguments @("-C", $repoRoot, "merge-base", "--is-ancestor", "origin/master", "master")
if ($masterContainsOriginResult.ExitCode -eq 0) {
    Add-M013Result -Results $gitResults -Name "master contient origin/master" -Command $masterContainsOriginResult.Command -ExitCode 0 -OutputLines @($masterRevision, $originMasterRevision) -Status "GREEN" -Observation "La référence master contient origin/master." -StartedAtUtc $masterContainsOriginResult.StartedAtUtc -CompletedAtUtc $masterContainsOriginResult.CompletedAtUtc
}
else {
    Add-M013Result -Results $gitResults -Name "master contient origin/master" -Command $masterContainsOriginResult.Command -ExitCode $masterContainsOriginResult.ExitCode -OutputLines @($masterRevision, $originMasterRevision) -Status "RED" -Observation "Référence master divergente entre master et origin/master." -StartedAtUtc $masterContainsOriginResult.StartedAtUtc -CompletedAtUtc $masterContainsOriginResult.CompletedAtUtc
}

Stop-M013OnRedGitResult -GitResults $gitResults -GateResults $gateResults -ReportPath $reportPath

$ancestorResult = Invoke-M013Process `
    -Name "branche contient master" `
    -Command "git merge-base --is-ancestor master HEAD" `
    -Executable "git" `
    -Arguments @("-C", $repoRoot, "merge-base", "--is-ancestor", "master", "HEAD")
if ($ancestorResult.ExitCode -eq 0) {
    Add-M013Result -Results $gitResults -Name "branche contient master" -Command $ancestorResult.Command -ExitCode 0 -OutputLines $ancestorResult.OutputLines -Status "GREEN" -Observation "La branche courante contient la révision locale master." -StartedAtUtc $ancestorResult.StartedAtUtc -CompletedAtUtc $ancestorResult.CompletedAtUtc
}
else {
    Add-M013Result -Results $gitResults -Name "branche contient master" -Command $ancestorResult.Command -ExitCode $ancestorResult.ExitCode -OutputLines $ancestorResult.OutputLines -Status "RED" -Observation "La branche courante ne contient pas la révision locale master." -StartedAtUtc $ancestorResult.StartedAtUtc -CompletedAtUtc $ancestorResult.CompletedAtUtc
}

Stop-M013OnRedGitResult -GitResults $gitResults -GateResults $gateResults -ReportPath $reportPath

foreach ($upstreamValidator in $requiredUpstreamPreconditionValidators) {
    $validatorPath = $upstreamValidator["Path"]
    $validatorName = $upstreamValidator["Name"]
    $startedAtUtc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    $acceptsM013Branch = Test-M013UpstreamValidatorAcceptsBranch -ValidatorPath $validatorPath -BranchName $m013Branch
    $completedAtUtc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

    if ($acceptsM013Branch) {
        Add-M013Result `
            -Results $gitResults `
            -Name "$validatorPath accepte M-013" `
            -Command "Select-String -Path $validatorPath -Pattern $m013Branch" `
            -ExitCode 0 `
            -OutputLines @($validatorPath, $m013Branch) `
            -Status "GREEN" `
            -Observation "Validateur amont $validatorName autorise explicitement la branche M-013." `
            -StartedAtUtc $startedAtUtc `
            -CompletedAtUtc $completedAtUtc
    }
    else {
        Add-M013Result `
            -Results $gitResults `
            -Name "$validatorPath accepte M-013" `
            -Command "Select-String -Path $validatorPath -Pattern $m013Branch" `
            -ExitCode 1 `
            -OutputLines @($validatorPath) `
            -Status "RED" `
            -Observation "Validateur amont $validatorName n'accepte pas la branche M-013: $validatorPath" `
            -StartedAtUtc $startedAtUtc `
            -CompletedAtUtc $completedAtUtc
    }
}

Stop-M013OnRedGitResult -GitResults $gitResults -GateResults $gateResults -ReportPath $reportPath

foreach ($requiredArtifact in $requiredMasterArtifacts) {
    $artifactPath = $requiredArtifact["Path"]
    $artifactKind = $requiredArtifact["Kind"]
    $artifactResult = Invoke-M013Process `
        -Name "$artifactPath dans master" `
        -Command "git ls-tree -r --name-only master -- $artifactPath" `
        -Executable "git" `
        -Arguments @("-C", $repoRoot, "ls-tree", "-r", "--name-only", "master", "--", $artifactPath)

    if (($artifactResult.ExitCode -eq 0) -and (Test-M013MasterArtifactPresent -OutputLines $artifactResult.OutputLines -ArtifactPath $artifactPath -Kind $artifactKind)) {
        Add-M013Result -Results $gitResults -Name "$artifactPath dans master" -Command $artifactResult.Command -ExitCode 0 -OutputLines $artifactResult.OutputLines -Status "GREEN" -Observation "Milestone ou preuve amont présent dans master: $artifactPath" -StartedAtUtc $artifactResult.StartedAtUtc -CompletedAtUtc $artifactResult.CompletedAtUtc
    }
    else {
        Add-M013Result -Results $gitResults -Name "$artifactPath dans master" -Command $artifactResult.Command -ExitCode $artifactResult.ExitCode -OutputLines $artifactResult.OutputLines -Status "RED" -Observation "Milestone ou preuve amont absent de master: $artifactPath" -StartedAtUtc $artifactResult.StartedAtUtc -CompletedAtUtc $artifactResult.CompletedAtUtc
    }
}

Stop-M013OnRedGitResult -GitResults $gitResults -GateResults $gateResults -ReportPath $reportPath

$gapReportResult = Invoke-M013TimedProcess `
    -Name "rapport écarts V1 M-012" `
    -Command "git show master:docs/governance/m012_v1_gap_report.md" `
    -Executable "git" `
    -Arguments @("-C", $repoRoot, "show", "master:docs/governance/m012_v1_gap_report.md") `
    -TimeoutSeconds 60
if ($gapReportResult.ExitCode -ne 0) {
    Add-M013Result -Results $gitResults -Name "rapport écarts V1 M-012" -Command $gapReportResult.Command -ExitCode $gapReportResult.ExitCode -OutputLines $gapReportResult.OutputLines -Status "RED" -Observation "Rapport d'écarts V1 M-012 illisible depuis master." -StartedAtUtc $gapReportResult.StartedAtUtc -CompletedAtUtc $gapReportResult.CompletedAtUtc
    Stop-M013OnRedGitResult -GitResults $gitResults -GateResults $gateResults -ReportPath $reportPath
}

$gapReportContent = $gapReportResult.OutputLines -join "`n"
$statusesByContext = ConvertFrom-M013GapStatuses -GapReportContent $gapReportContent
foreach ($context in $requiredGapContexts) {
    $startedAtUtc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    $completedAtUtc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

    if (-not $statusesByContext.ContainsKey($context)) {
        Add-M013Result -Results $gitResults -Name "Écart V1 $context statuté" -Command $gapReportResult.Command -ExitCode 1 -OutputLines $gapReportResult.OutputLines -Status "RED" -Observation "Écart V1 absent pour $context" -StartedAtUtc $startedAtUtc -CompletedAtUtc $completedAtUtc
        continue
    }

    $status = ([string] $statusesByContext[$context]).Trim()
    if ([string]::IsNullOrWhiteSpace($status)) {
        Add-M013Result -Results $gitResults -Name "Écart V1 $context statuté" -Command $gapReportResult.Command -ExitCode 1 -OutputLines $gapReportResult.OutputLines -Status "RED" -Observation "Écart V1 sans statut exploitable pour $context" -StartedAtUtc $startedAtUtc -CompletedAtUtc $completedAtUtc
        continue
    }

    $normalizedStatus = $status.ToLowerInvariant()
    if ($allowedGapStatuses -contains $normalizedStatus) {
        Add-M013Result -Results $gitResults -Name "Écart V1 $context statuté" -Command $gapReportResult.Command -ExitCode 0 -OutputLines @("${context}: $status") -Status "GREEN" -Observation "Écart V1 $context statuté: $status" -StartedAtUtc $startedAtUtc -CompletedAtUtc $completedAtUtc
    }
    else {
        Add-M013Result -Results $gitResults -Name "Écart V1 $context statuté" -Command $gapReportResult.Command -ExitCode 1 -OutputLines @("${context}: $status") -Status "RED" -Observation "Statut d'écart V1 invalide pour ${context}: $status" -StartedAtUtc $startedAtUtc -CompletedAtUtc $completedAtUtc
    }
}

$redScienceStartedAtUtc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$redScienceCompletedAtUtc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
if ($gapReportContent.Contains("Test scientifique RED")) {
    Add-M013Result -Results $gitResults -Name "Tests scientifiques RED conservés" -Command $gapReportResult.Command -ExitCode 0 -OutputLines @("Test scientifique RED") -Status "GREEN" -Observation "Test scientifique RED conservé dans le rapport V1 M-012." -StartedAtUtc $redScienceStartedAtUtc -CompletedAtUtc $redScienceCompletedAtUtc
}
else {
    Add-M013Result -Results $gitResults -Name "Tests scientifiques RED conservés" -Command $gapReportResult.Command -ExitCode 1 -OutputLines $gapReportResult.OutputLines -Status "RED" -Observation "Tests scientifiques RED M-012 absents du rapport V1." -StartedAtUtc $redScienceStartedAtUtc -CompletedAtUtc $redScienceCompletedAtUtc
}

Stop-M013OnRedGitResult -GitResults $gitResults -GateResults $gateResults -ReportPath $reportPath

Write-M013PreconditionReport -ReportPath $reportPath -OverallStatus "PENDING" -GitResults $gitResults.ToArray() -GateResults $gateResults.ToArray()

foreach ($gateDefinition in $gateDefinitions) {
    $gateResult = Invoke-M013GateProcess -GateDefinition $gateDefinition

    foreach ($outputLine in $gateResult.OutputLines) {
        Write-Host $outputLine
    }

    if ($gateResult.TimedOut) {
        $observation = "Gate M-013 RED: $($gateDefinition["Name"]) non concluant après $GateTimeoutSeconds seconde(s)."
        Add-M013Result -Results $gateResults -Name $gateResult.Name -Command $gateResult.Command -ExitCode $gateResult.ExitCode -OutputLines $gateResult.OutputLines -Status "RED" -Observation $observation -StartedAtUtc $gateResult.StartedAtUtc -CompletedAtUtc $gateResult.CompletedAtUtc
        Write-M013PreconditionReport -ReportPath $reportPath -OverallStatus "RED" -GitResults $gitResults.ToArray() -GateResults $gateResults.ToArray()
        Write-Host $observation
        throw $observation
    }

    if ($gateResult.OutputLines.Count -eq 0) {
        $observation = "Gate M-013 RED: $($gateDefinition["Name"]) sans sortie."
        Add-M013Result -Results $gateResults -Name $gateResult.Name -Command $gateResult.Command -ExitCode $gateResult.ExitCode -OutputLines $gateResult.OutputLines -Status "RED" -Observation $observation -StartedAtUtc $gateResult.StartedAtUtc -CompletedAtUtc $gateResult.CompletedAtUtc
        Write-M013PreconditionReport -ReportPath $reportPath -OverallStatus "RED" -GitResults $gitResults.ToArray() -GateResults $gateResults.ToArray()
        Write-Host $observation
        throw $observation
    }

    if ($gateResult.ExitCode -eq 0) {
        if ($gateDefinition["Name"] -eq "test") {
            foreach ($expectedEvidence in $requiredTestGateEvidence) {
                if (-not (Test-M013GateEvidencePresent -OutputLines $gateResult.OutputLines -ExpectedEvidence $expectedEvidence)) {
                    $evidenceLabel = $expectedEvidence.Replace("Test GREEN: ", "").Replace("Validation GREEN: ", "")
                    $observation = "Gate M-013 RED: test sans preuve obligatoire pour $evidenceLabel."
                    Add-M013Result -Results $gateResults -Name $gateResult.Name -Command $gateResult.Command -ExitCode $gateResult.ExitCode -OutputLines $gateResult.OutputLines -Status "RED" -Observation $observation -StartedAtUtc $gateResult.StartedAtUtc -CompletedAtUtc $gateResult.CompletedAtUtc
                    Write-M013PreconditionReport -ReportPath $reportPath -OverallStatus "RED" -GitResults $gitResults.ToArray() -GateResults $gateResults.ToArray()
                    Write-Host $observation
                    throw $observation
                }
            }
        }

        Add-M013Result -Results $gateResults -Name $gateResult.Name -Command $gateResult.Command -ExitCode $gateResult.ExitCode -OutputLines $gateResult.OutputLines -Status "GREEN" -Observation "Gate $($gateDefinition["Name"]) GREEN." -StartedAtUtc $gateResult.StartedAtUtc -CompletedAtUtc $gateResult.CompletedAtUtc
    }
    else {
        Add-M013Result -Results $gateResults -Name $gateResult.Name -Command $gateResult.Command -ExitCode $gateResult.ExitCode -OutputLines $gateResult.OutputLines -Status "RED" -Observation "Gate M-013 RED: $($gateDefinition["Name"])" -StartedAtUtc $gateResult.StartedAtUtc -CompletedAtUtc $gateResult.CompletedAtUtc
        Write-M013PreconditionReport -ReportPath $reportPath -OverallStatus "RED" -GitResults $gitResults.ToArray() -GateResults $gateResults.ToArray()
        Write-Host "Gate M-013 RED: $($gateDefinition["Name"])"
        throw "Gate M-013 RED: $($gateDefinition["Name"])"
    }
}

Write-M013PreconditionReport -ReportPath $reportPath -OverallStatus "GREEN" -GitResults $gitResults.ToArray() -GateResults $gateResults.ToArray()
Write-Host "Précondition M-013 GREEN: 2 gate(s), $($requiredMasterArtifacts.Count) artefact(s) M-012 et $($requiredGapContexts.Count) écart(s) V1 vérifié(s). Rapport: $reportPath"
