function Resolve-M013FastApiPython {
    param(
        [Parameter(Mandatory = $true)]
        [string] $RepoRoot
    )

    if (-not [string]::IsNullOrWhiteSpace($env:M013_FASTAPI_PYTHON)) {
        if (-not (Test-Path -LiteralPath $env:M013_FASTAPI_PYTHON -PathType Leaf)) {
            throw "M013_FASTAPI_EXPLICIT_PYTHON_INVALID: M013_FASTAPI_PYTHON ne désigne pas un fichier."
        }
        return (Resolve-Path -LiteralPath $env:M013_FASTAPI_PYTHON).Path
    }

    $standalonePython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $standalonePython -PathType Leaf)) {
        throw "M013_FASTAPI_STANDALONE_PYTHON_REQUIRED: exécuter via la gate ou matérialiser explicitement .venv."
    }
    return (Resolve-Path -LiteralPath $standalonePython).Path
}
