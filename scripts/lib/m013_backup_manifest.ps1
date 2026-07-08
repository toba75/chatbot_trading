$requiredContexts = @("SP", "KA", "EG", "RA", "CV", "SD", "EX", "EV", "platform")
$requiredArtifactKinds = @(
    "corpus_original",
    "canonical_versions",
    "qdrant_projection",
    "claim_registry",
    "verified_answers",
    "conversation_turns",
    "strategy_snapshots",
    "experiment_results",
    "evaluation_reports",
    "governance_artifacts"
)
$expectedContextByArtifactKind = @{
    "corpus_original" = "SP"
    "canonical_versions" = "SP"
    "qdrant_projection" = "KA"
    "claim_registry" = "EG"
    "verified_answers" = "RA"
    "conversation_turns" = "CV"
    "strategy_snapshots" = "SD"
    "experiment_results" = "EX"
    "evaluation_reports" = "EV"
    "governance_artifacts" = "platform"
}
$requiredNegativeContexts = @("EG", "RA", "SD", "EX", "EV")
$sensitiveFragments = @(
    "api key",
    "api_key",
    "authorization",
    "bearer",
    "clé privée",
    "cle privee",
    "mot de passe",
    "password",
    "passphrase",
    "private key",
    "secret_interdit_m013"
)

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

function Get-M013Property {
    param(
        [Parameter(Mandatory = $true)]
        [object] $Object,

        [Parameter(Mandatory = $true)]
        [string] $Name
    )

    $property = $Object.PSObject.Properties[$Name]
    Assert-M013Condition -Condition ($null -ne $property) -Message "Champ manifeste absent: $Name"
    return $property.Value
}

function Get-M013Text {
    param(
        [Parameter(Mandatory = $true)]
        [object] $Object,

        [Parameter(Mandatory = $true)]
        [string] $Name
    )

    $value = Get-M013Property -Object $Object -Name $Name
    Assert-M013Condition -Condition ($value -is [string]) -Message "Champ manifeste non textuel: $Name"
    Assert-M013Condition -Condition (-not [string]::IsNullOrWhiteSpace($value)) -Message "Champ manifeste vide: $Name"
    Assert-M013Condition -Condition ($value -eq $value.Trim()) -Message "Champ manifeste non normalisé: $Name"
    return $value
}

function Get-M013Bool {
    param(
        [Parameter(Mandatory = $true)]
        [object] $Object,

        [Parameter(Mandatory = $true)]
        [string] $Name
    )

    $value = Get-M013Property -Object $Object -Name $Name
    Assert-M013Condition -Condition ($value -is [bool]) -Message "Champ manifeste non booléen: $Name"
    return [bool] $value
}

function Get-M013Sha256 {
    param(
        [Parameter(Mandatory = $true)]
        [object] $Object,

        [Parameter(Mandatory = $true)]
        [string] $Name
    )

    $value = Get-M013Text -Object $Object -Name $Name
    Assert-M013Condition -Condition ($value -match "^[0-9a-f]{64}$") -Message "Hash manifeste invalide: $Name"
    Assert-M013Condition -Condition (-not ($value -match "^([0-9a-f])\1{63}$")) -Message "Hash placeholder interdit"
    return $value
}

function Assert-M013NoSensitiveText {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Value
    )

    $normalized = $Value.ToLowerInvariant()
    foreach ($fragment in $sensitiveFragments) {
        if ($normalized.Contains($fragment)) {
            throw "Secret en clair interdit dans le manifeste"
        }
    }
}

function Read-M013BackupManifest {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [string] $Label
    )

    Assert-M013Condition -Condition (Test-Path -LiteralPath $Path -PathType Leaf) -Message "Manifeste $Label V1 absent: $Path"
    $content = (Get-Content -Raw -Encoding UTF8 -LiteralPath $Path).TrimStart([char] 0xFEFF)
    Assert-M013Condition -Condition (-not [string]::IsNullOrWhiteSpace($content)) -Message "Manifeste $Label V1 vide: $Path"
    try {
        $manifest = $content | ConvertFrom-Json
    }
    catch {
        throw "Manifeste $Label V1 JSON invalide: $($_.Exception.Message)"
    }

    Assert-M013Condition -Condition ((Get-M013Text -Object $manifest -Name "contract_version") -eq "M013-BackupManifest-1.0") -Message "Version contrat manifeste invalide"
    Get-M013Text -Object $manifest -Name "manifest_id" | Out-Null
    Get-M013Text -Object $manifest -Name "backup_command" | Out-Null
    Get-M013Text -Object $manifest -Name "restore_command" | Out-Null
    Assert-M013Condition -Condition ((Get-M013Text -Object $manifest -Name "restore_target") -eq "local_isolated") -Message "Cible de restauration isolée requise"
    Assert-M013Condition -Condition (Get-M013Bool -Object $manifest -Name "complete") -Message "Manifeste incomplet"
    Assert-M013Condition -Condition (Get-M013Bool -Object $manifest -Name "archive_encrypted") -Message "Archive chiffrée requise"
    Assert-M013Condition -Condition (-not (Get-M013Bool -Object $manifest -Name "key_git_tracked")) -Message "Clé versionnée interdite"

    $encryptionProof = Get-M013Text -Object $manifest -Name "encryption_proof"
    Assert-M013NoSensitiveText -Value $encryptionProof
    Assert-M013Condition -Condition ($encryptionProof -match "ciphertext_sha256=[0-9a-f]{64}") -Message "Preuve de chiffrement requise"
    $ciphertextHash = [regex]::Match($encryptionProof, "ciphertext_sha256=([0-9a-f]{64})").Groups[1].Value
    Assert-M013Condition -Condition (-not ($ciphertextHash -match "^([0-9a-f])\1{63}$")) -Message "Hash placeholder interdit"

    $keyReference = Get-M013Text -Object $manifest -Name "key_reference"
    Assert-M013NoSensitiveText -Value $keyReference
    Assert-M013Condition -Condition ($keyReference.StartsWith("hors_depot://")) -Message "Clé hors dépôt requise"

    $entriesValue = Get-M013Property -Object $manifest -Name "entries"
    Assert-M013Condition -Condition ($entriesValue -is [array]) -Message "Entrées manifeste absentes"
    $entries = @($entriesValue)
    Assert-M013Condition -Condition ($entries.Count -gt 0) -Message "Entrées manifeste absentes"

    $contexts = New-Object "System.Collections.Generic.HashSet[string]"
    $artifactKinds = New-Object "System.Collections.Generic.HashSet[string]"
    $entryIds = New-Object "System.Collections.Generic.HashSet[string]"
    $stableIds = New-Object "System.Collections.Generic.HashSet[string]"
    $negativeContexts = New-Object "System.Collections.Generic.HashSet[string]"
    $projectionCount = 0

    foreach ($entry in $entries) {
        $entryId = Get-M013Text -Object $entry -Name "entry_id"
        Assert-M013Condition -Condition ($entryIds.Add($entryId)) -Message "Entrée manifeste dupliquée"
        $context = Get-M013Text -Object $entry -Name "context"
        Assert-M013Condition -Condition ($requiredContexts -contains $context) -Message "Contexte V1 inconnu"
        $artifactKind = Get-M013Text -Object $entry -Name "artifact_kind"
        Assert-M013Condition -Condition ($requiredArtifactKinds -contains $artifactKind) -Message "Catégorie artefact V1 inconnue"
        Assert-M013Condition -Condition ($expectedContextByArtifactKind[$artifactKind] -eq $context) -Message "Catégorie artefact contexte incohérente"
        $stableId = Get-M013Text -Object $entry -Name "stable_identifier"
        Assert-M013Condition -Condition ($stableIds.Add($stableId)) -Message "Identifiant stable dupliqué"

        Assert-M013Condition -Condition ((Get-M013Text -Object $entry -Name "storage_host") -eq "docker-local") -Message "Stockage métier Spark interdit"
        $authority = Get-M013Bool -Object $entry -Name "authority"
        Get-M013Bool -Object $entry -Name "immutable" | Out-Null
        $regenerableProjection = Get-M013Bool -Object $entry -Name "regenerable_projection"
        $retainedNegative = Get-M013Bool -Object $entry -Name "retained_negative_or_superseded"
        Assert-M013Condition -Condition (-not (Get-M013Bool -Object $entry -Name "contains_plain_secret")) -Message "Secret en clair interdit"
        Assert-M013Condition -Condition (-not (Get-M013Bool -Object $entry -Name "git_tracked_key_material")) -Message "Clé versionnée interdite"
        Assert-M013Condition -Condition (-not (Get-M013Bool -Object $entry -Name "spark_business_storage")) -Message "Stockage métier Spark interdit"
        Assert-M013Condition -Condition (-not (Get-M013Bool -Object $entry -Name "destructive_restore")) -Message "Restauration destructive interdite"

        $backupSha256 = Get-M013Sha256 -Object $entry -Name "backup_sha256"
        $restoredSha256 = Get-M013Sha256 -Object $entry -Name "restored_sha256"
        Assert-M013Condition -Condition ($backupSha256 -eq $restoredSha256) -Message "Hash restauré divergent"

        if ($artifactKind -eq "qdrant_projection") {
            Assert-M013Condition -Condition $regenerableProjection -Message "Projection régénérable requise"
        }
        if ($regenerableProjection) {
            Assert-M013Condition -Condition (-not $authority) -Message "Projection régénérable non autorité"
            $projectionCount++
        }
        if ($retainedNegative) {
            $negativeContexts.Add($context) | Out-Null
        }
        $contexts.Add($context) | Out-Null
        $artifactKinds.Add($artifactKind) | Out-Null
    }

    foreach ($context in $requiredContexts) {
        Assert-M013Condition -Condition ($contexts.Contains($context)) -Message "Contexte V1 absent"
    }
    foreach ($artifactKind in $requiredArtifactKinds) {
        Assert-M013Condition -Condition ($artifactKinds.Contains($artifactKind)) -Message "Catégorie artefact V1 absente"
    }
    foreach ($context in $requiredNegativeContexts) {
        Assert-M013Condition -Condition ($negativeContexts.Contains($context)) -Message "Résultats négatifs et supersédés absents pour le contexte: $context"
    }
    Assert-M013Condition -Condition ($projectionCount -gt 0) -Message "Projection régénérable requise"

    return [pscustomobject] @{
        Path = (Resolve-Path -LiteralPath $Path).Path
        ManifestId = Get-M013Text -Object $manifest -Name "manifest_id"
        Entries = $entries
        EntryCount = $entries.Count
    }
}
