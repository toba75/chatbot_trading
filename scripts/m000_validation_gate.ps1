$ErrorActionPreference = "Stop"

$eAcute = [char] 0x00E9

function Get-M000CommandField {
    param(
        [Parameter(Mandatory = $true)]
        [object] $Command,

        [Parameter(Mandatory = $true)]
        [string] $FieldName,

        [Parameter(Mandatory = $true)]
        [string] $Kind
    )

    if ($Command -is [hashtable]) {
        if (-not $Command.ContainsKey($FieldName)) {
            throw "Commande de $Kind sans champ $FieldName."
        }

        return $Command[$FieldName]
    }

    $property = $Command.PSObject.Properties[$FieldName]
    if ($null -eq $property) {
        throw "Commande de $Kind sans champ $FieldName."
    }

    return $property.Value
}

function Get-M000CommandDescriptor {
    param(
        [Parameter(Mandatory = $true)]
        [object] $Command,

        [Parameter(Mandatory = $true)]
        [string] $Kind,

        [Parameter(Mandatory = $true)]
        [string] $RepositoryRoot
    )

    $path = Get-M000CommandField -Command $Command -FieldName "Path" -Kind $Kind
    $arguments = @(Get-M000CommandField -Command $Command -FieldName "Arguments" -Kind $Kind)

    if ([string]::IsNullOrWhiteSpace($path)) {
        throw "Commande de $Kind sans chemin."
    }

    if ([System.IO.Path]::IsPathRooted($path)) {
        throw "Chemin absolu interdit pour la commande de ${Kind}: $path"
    }

    foreach ($argument in $arguments) {
        if ($null -eq $argument) {
            throw "Argument nul interdit pour la commande de ${Kind}: $path"
        }

        if (($argument -is [string]) -and [string]::IsNullOrWhiteSpace($argument)) {
            throw "Argument vide interdit pour la commande de ${Kind}: $path"
        }
    }

    $displayPath = $path.Replace("\", "/")
    if ($displayPath.StartsWith("./")) {
        $displayPath = $displayPath.Substring(2)
    }

    if (($displayPath -eq "..") -or $displayPath.StartsWith("../") -or $displayPath.Contains("/../")) {
        throw "Chemin hors dépôt interdit pour la commande de ${Kind}: $path"
    }

    $relativePath = $displayPath.Replace("/", [System.IO.Path]::DirectorySeparatorChar)
    $resolvedRepositoryRoot = [System.IO.Path]::GetFullPath($RepositoryRoot)
    $fullPath = [System.IO.Path]::GetFullPath((Join-Path $resolvedRepositoryRoot $relativePath))
    $repositoryPrefix = $resolvedRepositoryRoot.TrimEnd("\", "/") + [System.IO.Path]::DirectorySeparatorChar

    if (-not $fullPath.StartsWith($repositoryPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Chemin hors dépôt interdit pour la commande de ${Kind}: $path"
    }

    return [pscustomobject] @{
        DisplayPath = $displayPath
        FullPath = $fullPath
        Arguments = $arguments
    }
}

function Invoke-M000RequiredCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string] $RepositoryRoot,

        [Parameter(Mandatory = $true)]
        [object] $Command,

        [Parameter(Mandatory = $true)]
        [ValidateSet("Validation", "Test")]
        [string] $Kind
    )

    $descriptor = Get-M000CommandDescriptor -Command $Command -Kind $Kind -RepositoryRoot $RepositoryRoot

    if ($Kind -eq "Validation") {
        $absentMessage = "Validation requise absente"
        $failedMessage = "Validation $($eAcute)chou$($eAcute)e"
        $greenMessage = "Validation GREEN"
        $requiredMessage = "Validation requise"
    }
    else {
        $absentMessage = "Test requis absent"
        $failedMessage = "Test $($eAcute)chou$($eAcute)"
        $greenMessage = "Test GREEN"
        $requiredMessage = "Test requis"
    }

    if (-not (Test-Path -LiteralPath $descriptor.FullPath -PathType Leaf)) {
        throw "${absentMessage}: $($descriptor.DisplayPath)"
    }

    Write-Host "${requiredMessage}: $($descriptor.DisplayPath)"

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $descriptor.FullPath @($descriptor.Arguments) 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    foreach ($line in $output) {
        Write-Host $line
    }

    if ($exitCode -ne 0) {
        throw "${failedMessage}: $($descriptor.DisplayPath)"
    }

    Write-Host "${greenMessage}: $($descriptor.DisplayPath)"
}

function Invoke-M000ValidationGate {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateNotNullOrEmpty()]
        [string] $GateName,

        [Parameter(Mandatory = $true)]
        [ValidateNotNullOrEmpty()]
        [string] $RepositoryRoot,

        [Parameter(Mandatory = $true)]
        [ValidateNotNull()]
        [AllowEmptyCollection()]
        [object[]] $ValidationCommands,

        [Parameter(Mandatory = $true)]
        [ValidateNotNull()]
        [AllowEmptyCollection()]
        [object[]] $TestCommands
    )

    if (-not (Test-Path -LiteralPath $RepositoryRoot -PathType Container)) {
        throw "Racine de dépôt introuvable pour la gate ${GateName}: $RepositoryRoot"
    }

    $resolvedRepositoryRoot = (Resolve-Path -LiteralPath $RepositoryRoot).Path
    $validationCommandList = @($ValidationCommands)
    $testCommandList = @($TestCommands)
    $commandCount = $validationCommandList.Count + $testCommandList.Count

    if ($commandCount -eq 0) {
        throw "Gate $GateName sans commande requise."
    }

    foreach ($command in $validationCommandList) {
        Invoke-M000RequiredCommand -RepositoryRoot $resolvedRepositoryRoot -Command $command -Kind "Validation"
    }

    foreach ($command in $testCommandList) {
        Invoke-M000RequiredCommand -RepositoryRoot $resolvedRepositoryRoot -Command $command -Kind "Test"
    }

    Write-Host "Gate $GateName GREEN: $($validationCommandList.Count) validation(s), $($testCommandList.Count) test(s)."
}
