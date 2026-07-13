function Copy-TraceabilityRootArtifacts {
    param(
        [Parameter(Mandatory = $true)]
        [string] $SourceRoot,

        [Parameter(Mandatory = $true)]
        [string] $DestinationRoot
    )

    if (-not (Test-Path -LiteralPath $SourceRoot -PathType Container)) {
        throw "Racine source de la fixture de traçabilité absente: $SourceRoot"
    }

    if (-not (Test-Path -LiteralPath $DestinationRoot -PathType Container)) {
        throw "Racine de destination de la fixture de traçabilité absente: $DestinationRoot"
    }

    foreach ($artifact in @(".dockerignore", ".gitattributes", ".gitignore", "pyproject.toml", "uv.lock")) {
        $sourcePath = Join-Path $SourceRoot $artifact
        if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
            throw "Artefact racine requis absent du dépôt source: $artifact"
        }

        $destinationPath = Join-Path $DestinationRoot $artifact
        Copy-Item -LiteralPath $sourcePath -Destination $destinationPath

        if (-not (Test-Path -LiteralPath $destinationPath -PathType Leaf)) {
            throw "Copie de l'artefact racine requise absente: $artifact"
        }
    }
}

function New-TrackedCorpusPdfPlaceholders {
    param(
        [Parameter(Mandatory = $true)]
        [string] $SourceRoot,

        [Parameter(Mandatory = $true)]
        [string] $DestinationRoot
    )

    if (-not (Test-Path -LiteralPath $SourceRoot -PathType Container)) {
        throw "Racine source de la fixture Git absente: $SourceRoot"
    }

    if (-not (Test-Path -LiteralPath $DestinationRoot -PathType Container)) {
        throw "Racine de destination de la fixture Git absente: $DestinationRoot"
    }

    $trackedCorpusPdfPaths = @(& git -C $SourceRoot ls-files -- "data/corpus/*.pdf")
    if ($LASTEXITCODE -ne 0) {
        throw "Lecture des PDF LFS suivis impossible dans la racine source."
    }

    $trackedCorpusPdfPaths = @($trackedCorpusPdfPaths | Sort-Object -Unique)
    if ($trackedCorpusPdfPaths.Count -ne 11) {
        throw "La fixture Git exige exactement onze PDF corpus suivis. Obtenu: $($trackedCorpusPdfPaths.Count)"
    }

    foreach ($relativePath in $trackedCorpusPdfPaths) {
        $normalizedPath = $relativePath.Replace("\", "/")
        if (-not $normalizedPath.StartsWith("data/corpus/", [System.StringComparison]::Ordinal) -or
            -not $normalizedPath.EndsWith(".pdf", [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Chemin PDF corpus suivi hors périmètre: $relativePath"
        }

        $destinationPath = Join-Path $DestinationRoot $normalizedPath
        New-Item -ItemType Directory -Path (Split-Path -Parent $destinationPath) -Force | Out-Null
        [System.IO.File]::WriteAllBytes($destinationPath, [byte[]] @())

        if (-not (Test-Path -LiteralPath $destinationPath -PathType Leaf)) {
            throw "Placeholder PDF corpus absent: $relativePath"
        }
    }
}
