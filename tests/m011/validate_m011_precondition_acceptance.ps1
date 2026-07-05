$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "run_m011_case.ps1")
Invoke-M011PythonCase -CaseName "precondition_acceptance"
