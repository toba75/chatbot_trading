$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$appRoot = Join-Path $repoRoot "app"
$registryPath = Join-Path $appRoot "context_registry.json"

$eAcute = [char] 0x00E9
$eGrave = [char] 0x00E8
$aGrave = [char] 0x00E0

$expectedContexts = @(
    @{ Code = "SP"; Module = "source_processing"; Name = "Traitement des sources"; Responsibility = "enregistrer" },
    @{ Code = "KA"; Module = "knowledge_access"; Name = "Acc$($eGrave)s aux connaissances"; Responsibility = "construire" },
    @{ Code = "EG"; Module = "evidence_governance"; Name = "Gouvernance des preuves"; Responsibility = "cr$($eAcute)er" },
    @{ Code = "RA"; Module = "research_answering"; Name = "Recherche et r$($eAcute)ponse"; Responsibility = "planifier" },
    @{ Code = "CV"; Module = "conversation"; Name = "Conversation"; Responsibility = "conserver" },
    @{ Code = "SD"; Module = "strategy_design"; Name = "Conception de strat$($eAcute)gies"; Responsibility = "formaliser" },
    @{ Code = "EX"; Module = "experimentation"; Name = "Exp$($eAcute)rimentation"; Responsibility = "ex$($eAcute)cuter" },
    @{ Code = "EV"; Module = "evaluation"; Name = "$($eAcute.ToString().ToUpper())valuation pilote et calibration"; Responsibility = "mesurer" }
)

$requiredLayers = @("domain", "application", "adapters")

function Assert-PathExists {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw $Message
    }
}

function Assert-DirectoryExists {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw $Message
    }
}

function Assert-FileExists {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw $Message
    }
}

function Assert-StringNotEmpty {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string] $Value,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        throw $Message
    }
}

function Get-ContextByCode {
    param(
        [Parameter(Mandatory = $true)]
        [object[]] $Contexts,

        [Parameter(Mandatory = $true)]
        [string] $Code
    )

    $matches = @($Contexts | Where-Object { $_.code -eq $Code })
    if ($matches.Count -ne 1) {
        throw "Contexte $Code absent ou dupliqu$($eAcute) dans le registre."
    }

    return $matches[0]
}

# Given les huit bounded contexts ont une responsabilite exclusive.
# When l'arborescence applicative est controlee.
# Then chaque contexte possede ses couches canoniques et aucun stockage n'a plusieurs proprietaires.
Assert-DirectoryExists -Path $appRoot -Message "Module racine absent: app"
Assert-FileExists -Path $registryPath -Message "Registre de contextes absent: app/context_registry.json"

$registry = Get-Content -Raw -Encoding UTF8 -LiteralPath $registryPath | ConvertFrom-Json
$contexts = @($registry.contexts)

if ($contexts.Count -ne $expectedContexts.Count) {
    throw "Nombre de contextes invalide: $($contexts.Count)"
}

foreach ($expectedContext in $expectedContexts) {
    $context = Get-ContextByCode -Contexts $contexts -Code $expectedContext.Code
    $modulePath = Join-Path $appRoot $expectedContext.Module

    Assert-DirectoryExists -Path $modulePath -Message "Module de contexte absent: app/$($expectedContext.Module)"
    Assert-FileExists -Path (Join-Path $modulePath "__init__.py") -Message "Module Python non importable: app/$($expectedContext.Module)/__init__.py"

    if ($context.module -ne $expectedContext.Module) {
        throw "Module invalide pour $($expectedContext.Code): $($context.module)"
    }
    if (-not $context.name.Contains($expectedContext.Name)) {
        throw "Nom de contexte invalide pour $($expectedContext.Code)."
    }
    if (-not $context.responsibility.Contains($expectedContext.Responsibility)) {
        throw "Responsabilit$($eAcute) invalide pour $($expectedContext.Code)."
    }
    if ($context.data_owner -ne $expectedContext.Module) {
        throw "Propri$($eAcute)taire de donn$($eAcute)es invalide pour $($expectedContext.Code)."
    }

    foreach ($layer in $requiredLayers) {
        $layerPath = Join-Path $modulePath $layer
        Assert-DirectoryExists -Path $layerPath -Message "Couche absente pour $($expectedContext.Code): $layer"
        Assert-FileExists -Path (Join-Path $layerPath "__init__.py") -Message "Couche Python non importable pour $($expectedContext.Code): $layer"
        if (@($context.layers) -notcontains $layer) {
            throw "Couche non d$($eAcute)clar$($eAcute)e pour $($expectedContext.Code): $layer"
        }
    }

    foreach ($storage in @($context.owned_storages)) {
        Assert-StringNotEmpty -Value $storage.id -Message "Stockage sans identifiant pour $($expectedContext.Code)."
        if ($storage.owner -ne $expectedContext.Code) {
            throw "Propri$($eAcute)taire de stockage invalide pour $($storage.id): $($storage.owner)"
        }
    }
}

$platformPath = Join-Path $appRoot "platform"
Assert-DirectoryExists -Path $platformPath -Message "Module support absent: app/platform"
Assert-FileExists -Path (Join-Path $platformPath "__init__.py") -Message "Module support Python non importable: app/platform/__init__.py"

if ($registry.platform.module -ne "platform") {
    throw "Module platform invalide dans le registre."
}
if ($registry.platform.business_bounded_context -ne $false) {
    throw "Platform ne doit pas $([char] 0x00EA)tre un bounded context m$($eAcute)tier."
}
if (@($registry.platform.layers).Count -ne 0) {
    throw "Platform ne doit pas d$($eAcute)clarer les couches m$($eAcute)tier domain/application/adapters."
}
if (@($contexts | Where-Object { $_.module -eq "platform" -or $_.code -eq "PL" }).Count -ne 0) {
    throw "Platform est d$($eAcute)clar$($eAcute) comme contexte m$($eAcute)tier."
}

Write-Host "Test d'acceptation des modules de contexte M-001: OK"
