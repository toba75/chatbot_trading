$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$expectedBranch = "codex/m13-fastapi"
$allowedStatuses = @("GREEN", "EXPECTED_RED", "BLOCKED_EXTERNAL")

function Assert-Equal {
    param(
        [Parameter(Mandatory = $false)]
        [AllowNull()]
        [object] $Actual,

        [Parameter(Mandatory = $false)]
        [AllowNull()]
        [object] $Expected,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if ($Actual -ne $Expected) {
        throw "$Message Attendu: $Expected. Obtenu: $Actual"
    }
}

function Assert-Throws {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock] $Action,

        [Parameter(Mandatory = $true)]
        [string] $ExpectedMessage
    )

    try {
        & $Action
    }
    catch {
        if (-not $_.Exception.Message.Contains($ExpectedMessage)) {
            throw "Erreur inattendue. Attendu: $ExpectedMessage. Obtenu: $($_.Exception.Message)"
        }
        return
    }

    throw "Une erreur était attendue: $ExpectedMessage"
}

function Resolve-PreconditionStatus {
    param(
        [Parameter(Mandatory = $false)]
        [AllowNull()]
        [object] $ExitCode,

        [Parameter(Mandatory = $true)]
        [bool] $ExpectedRed,

        [Parameter(Mandatory = $true)]
        [bool] $BlockedExternal
    )

    if ($ExpectedRed -and $BlockedExternal) {
        throw "Classification ambiguë interdite."
    }

    if ($null -eq $ExitCode) {
        if ($BlockedExternal) {
            return "BLOCKED_EXTERNAL"
        }
        throw "Absence de verdict non classée."
    }

    if ($ExitCode -isnot [int]) {
        throw "Code de sortie invalide."
    }

    if ($ExitCode -eq 0) {
        if ($ExpectedRed -or $BlockedExternal) {
            throw "Succès incompatible avec la classification demandée."
        }
        return "GREEN"
    }

    if ($ExpectedRed) {
        return "EXPECTED_RED"
    }

    if ($BlockedExternal) {
        return "BLOCKED_EXTERNAL"
    }

    throw "RED indépendant non classable."
}

Assert-Equal `
    -Actual (Resolve-PreconditionStatus -ExitCode 0 -ExpectedRed $false -BlockedExternal $false) `
    -Expected "GREEN" `
    -Message "Un code zéro doit être GREEN."
Assert-Equal `
    -Actual (Resolve-PreconditionStatus -ExitCode 1 -ExpectedRed $true -BlockedExternal $false) `
    -Expected "EXPECTED_RED" `
    -Message "Le RED futur explicitement attribué doit être EXPECTED_RED."
Assert-Equal `
    -Actual (Resolve-PreconditionStatus -ExitCode $null -ExpectedRed $false -BlockedExternal $true) `
    -Expected "BLOCKED_EXTERNAL" `
    -Message "Une commande bornée sans verdict doit être BLOCKED_EXTERNAL."
Assert-Throws `
    -Action { Resolve-PreconditionStatus -ExitCode 1 -ExpectedRed $false -BlockedExternal $false } `
    -ExpectedMessage "RED indépendant non classable"
Assert-Throws `
    -Action { Resolve-PreconditionStatus -ExitCode $null -ExpectedRed $false -BlockedExternal $false } `
    -ExpectedMessage "Absence de verdict non classée"
Assert-Throws `
    -Action { Resolve-PreconditionStatus -ExitCode 1 -ExpectedRed $true -BlockedExternal $true } `
    -ExpectedMessage "Classification ambiguë interdite"
Assert-Throws `
    -Action { Resolve-PreconditionStatus -ExitCode 0 -ExpectedRed $true -BlockedExternal $false } `
    -ExpectedMessage "Succès incompatible"

foreach ($status in @("GREEN", "EXPECTED_RED", "BLOCKED_EXTERNAL")) {
    if ($allowedStatuses -notcontains $status) {
        throw "Statut de précondition non autorisé: $status"
    }
}

$preconditionValidators = 3..13 | ForEach-Object {
    "scripts/validate_m{0:D3}_precondition.ps1" -f $_
}

foreach ($validatorRelativePath in $preconditionValidators) {
    $validatorPath = Join-Path $repoRoot $validatorRelativePath
    if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
        throw "Validateur de précondition amont absent: $validatorRelativePath"
    }

    $validatorContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $validatorPath
    if (-not $validatorContent.Contains('"' + $expectedBranch + '"')) {
        throw "Allowlist de précondition incompatible avec M13-FastAPI: $validatorRelativePath"
    }
}

Write-Host "Tests unitaires de précondition M13-FastAPI: OK"
