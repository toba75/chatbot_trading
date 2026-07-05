$ErrorActionPreference = "Stop"

function Invoke-M011PythonCase {
    param(
        [Parameter(Mandatory = $true)]
        [string] $CaseName
    )

    $repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
    . (Join-Path $repoRoot "scripts/require_python.ps1")
    $pythonExecutable = Get-RequiredPythonExecutable
    $caseRunnerPath = Join-Path $PSScriptRoot "_m011_cases.py"

    if (-not (Test-Path -LiteralPath $caseRunnerPath -PathType Leaf)) {
        throw "Runner de test M-011 absent: $caseRunnerPath"
    }

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & $pythonExecutable -B $caseRunnerPath $repoRoot $CaseName 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if ($exitCode -ne 0) {
        throw "Cas M-011 invalide ($CaseName). Sortie: $($output -join "`n")"
    }

    Write-Host ($output -join "`n")
}
