$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$reportPath = Join-Path $repoRoot "docs/governance/m000_precondition_green_initiale.md"

function Assert-MatchInReport {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content,

        [Parameter(Mandatory = $true)]
        [string] $Pattern,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if ($Content -notmatch $Pattern) {
        throw $Message
    }
}

if (-not (Test-Path -LiteralPath $reportPath -PathType Leaf)) {
    throw "Rapport de précondition M-000 absent: docs/governance/m000_precondition_green_initiale.md"
}

$content = Get-Content -Raw -Encoding UTF8 -LiteralPath $reportPath

Assert-MatchInReport `
    -Content $content `
    -Pattern 'Given le d.p.t `master` contient la sp.cification v4\.1 et le registre ADR\.' `
    -Message "Le scénario BDD ne contient pas le Given attendu."

Assert-MatchInReport `
    -Content $content `
    -Pattern 'When la pr.condition de M-000 est v.rifi.e\.' `
    -Message "Le scénario BDD ne contient pas le When attendu."

Assert-MatchInReport `
    -Content $content `
    -Pattern "Then l'.tat des validations existantes, des commandes absentes et des t.ches versionn.es est d.clar. sans ambigu.t.\." `
    -Message "Le scénario BDD ne contient pas le Then attendu."

Assert-MatchInReport `
    -Content $content `
    -Pattern '\*\*R.vision master observ.e :\*\* `[0-9a-f]{40}`' `
    -Message "La révision master observée doit être renseignée avec un hash Git complet."

Assert-MatchInReport `
    -Content $content `
    -Pattern '\| `powershell -NoProfile -ExecutionPolicy Bypass -File \.\\scripts\\validate_adr_system\.ps1` \| `\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z` \| `GREEN` \|' `
    -Message "La commande ADR exécutée doit être datée et déclarée GREEN."

Assert-MatchInReport `
    -Content $content `
    -Pattern '\| `\.\\scripts\\test\.ps1` \| `\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z` \| `RED` \|' `
    -Message "La commande scripts/test.ps1 absente doit être nommée et déclarée RED."

Assert-MatchInReport `
    -Content $content `
    -Pattern '\| `\.\\scripts\\lint\.ps1` \| `\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z` \| `RED` \|' `
    -Message "La commande scripts/lint.ps1 absente doit être nommée et déclarée RED."

Assert-MatchInReport `
    -Content $content `
    -Pattern 'docs/tasks/milestone_000.*master.*`RED`' `
    -Message "L'état des tâches M-000 versionnées dans master doit être déclaré sans ambiguïté."

Write-Host "Test d'acceptation M-000 précondition GREEN: OK"
