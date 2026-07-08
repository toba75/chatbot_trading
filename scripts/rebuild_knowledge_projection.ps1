param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string] $Source,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string] $SourceRoot,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string] $Target
)

$ErrorActionPreference = "Stop"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::InputEncoding = $utf8NoBom
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom
$eAcute = [char] 0x00E9

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

Assert-M013Condition -Condition ($Source -eq "SP") -Message "Source reconstruction projection invalide: $Source"
Assert-M013Condition -Condition (Test-Path -LiteralPath $SourceRoot -PathType Container) -Message "Source SP introuvable: $SourceRoot"
Assert-M013Condition -Condition (-not (Test-Path -LiteralPath $Target -PathType Leaf)) -Message "Cible projection KA invalide: $Target"
Assert-M013Condition `
    -Condition (-not ((Test-Path -LiteralPath $Target -PathType Container) -and @(Get-ChildItem -LiteralPath $Target -Force).Count -gt 0)) `
    -Message "Cible projection KA non vide: $Target"

$resolvedSourceRoot = [System.IO.Path]::GetFullPath((Resolve-Path -LiteralPath $SourceRoot).Path)
$resolvedTargetPath = [System.IO.Path]::GetFullPath($Target)
$sourcePrefix = $resolvedSourceRoot.TrimEnd("\", "/") + [System.IO.Path]::DirectorySeparatorChar
Assert-M013Condition `
    -Condition (-not (
        $resolvedTargetPath.Equals($resolvedSourceRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
        $resolvedTargetPath.StartsWith($sourcePrefix, [System.StringComparison]::OrdinalIgnoreCase)
    )) `
    -Message "Cible projection KA sous source SP interdite: $Target"

$corpusMarker = Join-Path $SourceRoot "corpus_originals.marker"
$canonicalMarker = Join-Path $SourceRoot "canonical_versions.marker"
Assert-M013Condition -Condition (Test-Path -LiteralPath $corpusMarker -PathType Leaf) -Message "Originaux SP absents pour reconstruction KA"
Assert-M013Condition -Condition (Test-Path -LiteralPath $canonicalMarker -PathType Leaf) -Message "Versions canoniques SP absentes pour reconstruction KA"

$sourceFileCount = 0
Get-ChildItem -LiteralPath $SourceRoot -File -Recurse | ForEach-Object {
    $sourceFileCount++
}
Assert-M013Condition -Condition ($sourceFileCount -gt 0) -Message "Aucun artefact SP disponible pour reconstruction KA"

$staging = $Target + ".staging-" + [System.Guid]::NewGuid().ToString("N")
New-Item -ItemType Directory -Path $staging | Out-Null
try {
    $manifest = [ordered] @{
        source = "SP"
        source_root = $resolvedSourceRoot
        target = $Target
        reconstructed_item_count = $sourceFileCount
        corpus_marker = (Get-Content -Raw -Encoding UTF8 -LiteralPath $corpusMarker).Trim()
        canonical_marker = (Get-Content -Raw -Encoding UTF8 -LiteralPath $canonicalMarker).Trim()
        status = "GREEN"
    }
    $manifestJson = $manifest | ConvertTo-Json -Depth 5
    Set-Content -Encoding UTF8 -LiteralPath (Join-Path $staging "projection_manifest.json") -Value $manifestJson

    if (Test-Path -LiteralPath $Target -PathType Container) {
        Remove-Item -LiteralPath $Target -Force
    }
    Move-Item -LiteralPath $staging -Destination $Target
}
catch {
    if (Test-Path -LiteralPath $staging) {
        Remove-Item -LiteralPath $staging -Recurse -Force
    }
    throw
}

$resolvedTarget = (Resolve-Path -LiteralPath $Target).Path
Write-Host "Projection KA reconstruite depuis SP: $sourceFileCount artefact(s), preuve v$($eAcute)rifi$($eAcute)e: $resolvedTarget"
