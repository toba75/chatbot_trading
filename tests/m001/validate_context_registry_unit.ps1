$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$registryPath = Join-Path $repoRoot "app/context_registry.json"

$eAcute = [char] 0x00E9
$eGrave = [char] 0x00E8
$aGrave = [char] 0x00E0

$expectedContextCodes = @("SP", "KA", "EG", "RA", "CV", "SD", "EX", "EV")
$requiredLayers = @("domain", "application", "adapters")

function Copy-RegistryObject {
    param(
        [Parameter(Mandatory = $true)]
        [object] $Registry
    )

    return ($Registry | ConvertTo-Json -Depth 20 | ConvertFrom-Json)
}

function Assert-ContextRegistry {
    param(
        [Parameter(Mandatory = $true)]
        [object] $Registry
    )

    $contexts = @($Registry.contexts)
    if ($contexts.Count -ne $expectedContextCodes.Count) {
        throw "Nombre de contextes invalide: $($contexts.Count)"
    }

    $seenCodes = @{}
    $seenStorageIds = @{}

    foreach ($context in $contexts) {
        $code = [string] $context.code
        if ([string]::IsNullOrWhiteSpace($code)) {
            throw "Code de contexte vide."
        }
        if ($expectedContextCodes -notcontains $code) {
            throw "Code de contexte inconnu: $code"
        }
        if ($seenCodes.ContainsKey($code)) {
            throw "Code de contexte dupliqu$($eAcute): $code"
        }
        $seenCodes[$code] = $true

        if ([string]::IsNullOrWhiteSpace([string] $context.module)) {
            throw "Module absent pour $code."
        }
        if ([string]::IsNullOrWhiteSpace([string] $context.data_owner)) {
            throw "Propri$($eAcute)taire de donn$($eAcute)es absent pour $code."
        }

        foreach ($requiredLayer in $requiredLayers) {
            if (@($context.layers) -notcontains $requiredLayer) {
                throw "Couche absente pour ${code}: $requiredLayer"
            }
        }
        foreach ($declaredLayer in @($context.layers)) {
            if ($requiredLayers -notcontains $declaredLayer) {
                throw "Couche inconnue pour ${code}: $declaredLayer"
            }
        }

        foreach ($storage in @($context.owned_storages)) {
            $storageId = [string] $storage.id
            if ([string]::IsNullOrWhiteSpace($storageId)) {
                throw "Stockage sans identifiant pour $code."
            }
            if ([string]::IsNullOrWhiteSpace([string] $storage.owner)) {
                throw "Stockage sans propri$($eAcute)taire: $storageId"
            }
            if ($storage.owner -ne $code) {
                throw "Propri$($eAcute)taire de stockage invalide pour $storageId."
            }
            if ($seenStorageIds.ContainsKey($storageId)) {
                throw "Stockage poss$($eAcute)d$($eAcute) dupliqu$($eAcute): $storageId"
            }
            $seenStorageIds[$storageId] = $code
        }
    }

    foreach ($expectedCode in $expectedContextCodes) {
        if (-not $seenCodes.ContainsKey($expectedCode)) {
            throw "Contexte attendu absent: $expectedCode"
        }
    }

    if ($Registry.platform.module -ne "platform") {
        throw "Module platform absent du registre."
    }
    if ($Registry.platform.business_bounded_context -ne $false) {
        throw "Platform ne doit pas $([char] 0x00EA)tre un bounded context m$($eAcute)tier."
    }

    foreach ($storage in @($Registry.platform.owned_storages)) {
        $storageId = [string] $storage.id
        if ([string]::IsNullOrWhiteSpace($storageId)) {
            throw "Stockage platform sans identifiant."
        }
        if ($storage.owner -ne "platform") {
            throw "Propri$($eAcute)taire de stockage platform invalide pour $storageId."
        }
        if ($seenStorageIds.ContainsKey($storageId)) {
            throw "Stockage poss$($eAcute)d$($eAcute) dupliqu$($eAcute): $storageId"
        }
        $seenStorageIds[$storageId] = "platform"
    }
}

function Assert-FailsWith {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock] $Action,

        [Parameter(Mandatory = $true)]
        [string] $Expected
    )

    $failed = $false
    try {
        & $Action
    }
    catch {
        $failed = $true
        if (-not $_.Exception.Message.Contains($Expected)) {
            throw "Erreur inattendue. Attendu: $Expected. Obtenu: $($_.Exception.Message)"
        }
    }

    if (-not $failed) {
        throw "Une erreur $($eAcute)tait attendue: $Expected"
    }
}

if (-not (Test-Path -LiteralPath $registryPath -PathType Leaf)) {
    throw "Registre de contextes absent: app/context_registry.json"
}

$validRegistry = Get-Content -Raw -Encoding UTF8 -LiteralPath $registryPath | ConvertFrom-Json

Assert-ContextRegistry -Registry $validRegistry

$unknownCodeRegistry = Copy-RegistryObject -Registry $validRegistry
$unknownCodeRegistry.contexts[0].code = "ZZ"
Assert-FailsWith -Expected "Code de contexte inconnu: ZZ" -Action {
    Assert-ContextRegistry -Registry $unknownCodeRegistry
}

$duplicateStorageRegistry = Copy-RegistryObject -Registry $validRegistry
$duplicateStorageRegistry.contexts[1].owned_storages[0].id = $duplicateStorageRegistry.contexts[0].owned_storages[0].id
Assert-FailsWith -Expected "Stockage poss$($eAcute)d$($eAcute) dupliqu$($eAcute)" -Action {
    Assert-ContextRegistry -Registry $duplicateStorageRegistry
}

$missingLayerRegistry = Copy-RegistryObject -Registry $validRegistry
$missingLayerRegistry.contexts[2].layers = @($missingLayerRegistry.contexts[2].layers | Where-Object { $_ -ne "domain" })
Assert-FailsWith -Expected "Couche absente pour EG: domain" -Action {
    Assert-ContextRegistry -Registry $missingLayerRegistry
}

Write-Host "Tests unitaires du registre de contextes M-001: OK"
