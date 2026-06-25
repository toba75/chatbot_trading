function Get-RequiredPythonExecutable {
    $pythonCommand = $null
    try {
        $pythonCommand = @(Get-Command python -CommandType Application -ErrorAction Stop)[0]
    }
    catch {
        throw "Python 3.10+ requis: executable python introuvable dans PATH."
    }

    $pythonExecutable = $pythonCommand.Source
    if ([string]::IsNullOrWhiteSpace($pythonExecutable)) {
        $pythonExecutable = $pythonCommand.Path
    }
    if ([string]::IsNullOrWhiteSpace($pythonExecutable)) {
        throw "Python 3.10+ requis: chemin executable python introuvable."
    }

    $versionOutput = & $pythonExecutable -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
    if ($LASTEXITCODE -ne 0) {
        throw "Python 3.10+ requis: version python illisible."
    }

    $version = [version] ([string] $versionOutput).Trim()
    if ($version -lt ([version] "3.10.0")) {
        throw "Python 3.10+ requis: version détectée $version."
    }

    return $pythonExecutable
}
