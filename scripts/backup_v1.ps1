param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string] $Manifest
)

$ErrorActionPreference = "Stop"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::InputEncoding = $utf8NoBom
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom
$eAcute = [char] 0x00E9

. (Join-Path $PSScriptRoot "lib/m013_backup_manifest.ps1")

$validatedManifest = Read-M013BackupManifest -Path $Manifest -Label "sauvegarde"
Write-Host "Manifeste de sauvegarde V1 v$($eAcute)rifi$($eAcute): $($validatedManifest.Path) ($($validatedManifest.EntryCount) entr$($eAcute)e(s) restaurable(s))"
