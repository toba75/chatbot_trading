$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m013_runbooks.ps1"
$temporaryRoot = Join-Path $repoRoot (".tmp_m013_runbooks_unit_" + [System.Guid]::NewGuid().ToString("N"))

function Invoke-Validator {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProjectRoot
    )

    $runbookRoot = Join-Path $ProjectRoot "docs/runbooks"
    $userGuidePath = Join-Path $ProjectRoot "docs/user/v1_guide_utilisateur.md"
    $documentationIndexPath = Join-Path $ProjectRoot "docs/governance/m013_documentation_index.md"
    $matrixPath = Join-Path $ProjectRoot "docs/traceability/matrix.md"
    $testGatePath = Join-Path $ProjectRoot "scripts/test.ps1"
    $lintGatePath = Join-Path $ProjectRoot "scripts/lint.ps1"

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & powershell `
            -NoProfile `
            -ExecutionPolicy Bypass `
            -File $validatorPath `
            -RunbookRoot $runbookRoot `
            -UserGuidePath $userGuidePath `
            -DocumentationIndexPath $documentationIndexPath `
            -MatrixPath $matrixPath `
            -TestGatePath $testGatePath `
            -LintGatePath $lintGatePath 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    return [pscustomobject] @{
        ExitCode = $exitCode
        Output = ($output -join "`n")
    }
}

function Assert-OutputContains {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Output,

        [Parameter(Mandatory = $true)]
        [string] $Expected,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if (-not $Output.Contains($Expected)) {
        throw "$Message Sortie obtenue: $Output"
    }
}

function New-FixtureProject {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name
    )

    $projectRoot = Join-Path $temporaryRoot $Name
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "docs") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $projectRoot "scripts") -Force | Out-Null

    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/runbooks") -Destination (Join-Path $projectRoot "docs/runbooks") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/user") -Destination (Join-Path $projectRoot "docs/user") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/governance") -Destination (Join-Path $projectRoot "docs/governance") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/traceability") -Destination (Join-Path $projectRoot "docs/traceability") -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot "scripts/test.ps1") -Destination (Join-Path $projectRoot "scripts/test.ps1")
    Copy-Item -LiteralPath (Join-Path $repoRoot "scripts/lint.ps1") -Destination (Join-Path $projectRoot "scripts/lint.ps1")

    return $projectRoot
}

function Assert-ValidatorFails {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name,

        [Parameter(Mandatory = $true)]
        [scriptblock] $Mutate,

        [Parameter(Mandatory = $true)]
        [string] $ExpectedMessage
    )

    $projectRoot = New-FixtureProject -Name $Name
    & $Mutate $projectRoot
    $result = Invoke-Validator -ProjectRoot $projectRoot

    if ($result.ExitCode -eq 0) {
        throw "Le cas RED $Name doit échouer."
    }

    Assert-OutputContains `
        -Output $result.Output `
        -Expected $ExpectedMessage `
        -Message "Le cas RED $Name doit nommer la règle violée."
}

function Remove-TemporaryRoot {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    for ($attempt = 1; $attempt -le 5; $attempt++) {
        try {
            Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
            return
        }
        catch {
            if ($attempt -eq 5) {
                throw
            }
            Start-Sleep -Milliseconds (200 * $attempt)
        }
    }
}

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
    throw "Validateur runbooks documentation utilisateur M-013 absent: scripts/validate_m013_runbooks.ps1"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null
try {
    # Given les runbooks et la documentation V1 sont publiés.
    # When le validateur T-010 contrôle les artefacts documentaires.
    # Then il refuse les oublis de procédure, preuve, commande, statut public,
    # écart V1, secret, fallback textuel, exposition interne et promesse financière.
    $validProjectRoot = New-FixtureProject -Name "valid"
    $validResult = Invoke-Validator -ProjectRoot $validProjectRoot
    if ($validResult.ExitCode -ne 0) {
        throw "La fixture valide T-010 doit réussir. Sortie: $($validResult.Output)"
    }
    Assert-OutputContains `
        -Output $validResult.Output `
        -Expected "Runbooks documentation utilisateur M-013 valides" `
        -Message "La fixture valide doit annoncer le GREEN T-010."

    Assert-ValidatorFails `
        -Name "documentation-utilisateur-absente" `
        -ExpectedMessage "Fichier requis absent (documentation utilisateur V1)" `
        -Mutate {
            param($projectRoot)
            Remove-Item -LiteralPath (Join-Path $projectRoot "docs/user/v1_guide_utilisateur.md")
        }

    Assert-ValidatorFails `
        -Name "commande-absente" `
        -ExpectedMessage "Commande PowerShell référencée absente: scripts/commande_absente.ps1" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/runbooks/monitoring_local.md"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace("scripts\validate_m013_monitoring.ps1", "scripts\commande_absente.ps1") |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }

    Assert-ValidatorFails `
        -Name "secret-documente" `
        -ExpectedMessage "Secret interdit dans la documentation M-013" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/user/v1_guide_utilisateur.md"
            Add-Content -Encoding UTF8 -LiteralPath $path -Value "`nAuthorization: Bearer SECRET_INTERDIT_M013"
        }

    Assert-ValidatorFails `
        -Name "fallback-textuel" `
        -ExpectedMessage "Fallback textuel interdit" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/runbooks/conversation_v1.md"
            Add-Content -Encoding UTF8 -LiteralPath $path -Value "`nEn panne Spark, fournir une réponse de secours textuelle."
        }

    Assert-ValidatorFails `
        -Name "commande-destructive" `
        -ExpectedMessage "Commande destructive sans précondition" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/runbooks/sauvegarde_restauration.md"
            Add-Content -Encoding UTF8 -LiteralPath $path -Value "`nCommande: Remove-Item -Recurse -Force .\data"
        }

    Assert-ValidatorFails `
        -Name "ecart-non-accepte-masque" `
        -ExpectedMessage "Écart V1 non accepté absent: SD" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/user/v1_guide_utilisateur.md"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace("SD | bloquant", "SD | masqué") |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }

    Assert-ValidatorFails `
        -Name "statut-public-absent" `
        -ExpectedMessage "Statut public absent: LLM_UNAVAILABLE" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/runbooks/spark_reseau_incidents.md"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace("LLM_UNAVAILABLE", "STATUT_MASQUE") |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }

    Assert-ValidatorFails `
        -Name "runbook-spark-absent" `
        -ExpectedMessage "Runbook critique absent: spark_reseau_incidents" `
        -Mutate {
            param($projectRoot)
            Remove-Item -LiteralPath (Join-Path $projectRoot "docs/runbooks/spark_reseau_incidents.md")
        }

    Assert-ValidatorFails `
        -Name "preuve-cassee" `
        -ExpectedMessage "Preuve référencée absente: docs/governance/m013_absente.md" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/runbooks/sauvegarde_restauration.md"
            (Get-Content -Raw -Encoding UTF8 -LiteralPath $path).Replace("docs/governance/m013_backup_restore_drill.md", "docs/governance/m013_absente.md") |
                Set-Content -Encoding UTF8 -LiteralPath $path
        }

    Assert-ValidatorFails `
        -Name "spark-public" `
        -ExpectedMessage "Publication de service interne interdite" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/runbooks/spark_reseau_incidents.md"
            Add-Content -Encoding UTF8 -LiteralPath $path -Value "`nCommande: docker run -p 0.0.0.0:8443:8443 gemma-vllm"
        }

    Assert-ValidatorFails `
        -Name "promesse-rentabilite" `
        -ExpectedMessage "Promesse de rentabilité interdite" `
        -Mutate {
            param($projectRoot)
            $path = Join-Path $projectRoot "docs/user/v1_guide_utilisateur.md"
            Add-Content -Encoding UTF8 -LiteralPath $path -Value "`nLa stratégie garantit la rentabilité."
        }
}
finally {
    Remove-TemporaryRoot -Path $temporaryRoot
}

Write-Host "Tests unitaires du validateur runbooks documentation utilisateur M-013: OK"
