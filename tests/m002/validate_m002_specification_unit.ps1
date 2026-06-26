$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m002_specification.ps1"
$temporaryRoot = Join-Path $repoRoot (".tmp/ost_m002_spec_unit_" + [System.Guid]::NewGuid().ToString("N"))

$eAcute = [char] 0x00E9
$eGrave = [char] 0x00E8
$aGrave = [char] 0x00E0
$eCircumflex = [char] 0x00EA
$uCircumflex = [char] 0x00FB
$oCircumflex = [char] 0x00F4

function New-ValidM002SpecificationContent {
    return @"
# M-002 - Plateforme locale s$($uCircumflex)re

## Statut

- Milestone: M-002 - Plateforme locale s$($uCircumflex)re.
- ADR consult$($eAcute)es: ADR-007, ADR-008, ADR-009, DDD-ADR-006, DDD-ADR-008.
- Contrat amont: ``docs/specs/m001_frontieres_ddd_contrats_publies.md``.

## Sc$($eAcute)nario BDD

- Given la sp$($eAcute)cification v4.1 impose deux plans physiques et une coh$($eAcute)rence $($eAcute)ventuelle par outbox.
- When la sp$($eAcute)cification M-002 est publi$($eAcute)e.
- Then chaque r$($eGrave)gle de plateforme nomme le comportement attendu, les invariants, les tests et les ADR qui la gouvernent.

## Contexte DDD

- Domaine: ex$($eAcute)cution locale s$($uCircumflex)re et auditable.
- Bounded context: ``platform``, sans devenir un bounded context m$($eAcute)tier.
- Objectif m$($eAcute)tier: d$($eAcute)finir comment les contextes m$($eAcute)tier obtiennent jobs, livraison d'$($eAcute)v$($eAcute)nements et inf$($eAcute)rence LLM sans exposer les donn$($eAcute)es ni masquer les pannes.

## Langage ubiquitaire M-002

Le langage M-002 publie les termes suivants: h$($oCircumflex)te Docker local ``docker-local``, Spark d'inf$($eAcute)rence ``spark-inference``, gateway LLM ``llm-gateway``, outbox transactionnelle, job prioris$($eAcute), appel d'inf$($eAcute)rence, panne explicite, observabilit$($eAcute) technique.

## Relations avec M-001

Les contrats M-001 restent les contrats de communication intercontextes. ``platform`` fournit une capacit$($eAcute) technique; il ne publie aucun mod$($eGrave)le m$($eAcute)tier et ne lit aucun mod$($eGrave)le interne d'un contexte.

## Placement des capacit$($eAcute)s

| Capacit$($eAcute) | H$($oCircumflex)te obligatoire | R$($eGrave)gle |
|---|---|---|
| Gemma 4 et vLLM principal | spark-inference | Le Spark calcule des inf$($eAcute)rences seulement et ne poss$($eGrave)de aucune donn$($eAcute)e m$($eAcute)tier. |
| Application m$($eAcute)tier, API, UI et workers | docker-local | Les contextes m$($eAcute)tier et leurs traitements restent sur docker-local. |
| PostgreSQL, Qdrant, corpus et exp$($eAcute)riences | docker-local | Les stockages et artefacts canoniques restent sur docker-local. |
| llm-gateway | docker-local | Le gateway local est le seul adaptateur r$($eAcute)seau autoris$($eAcute) vers spark-inference. |
| Outbox et file de jobs | docker-local | Les $($eAcute)v$($eAcute)nements intercontextes et jobs techniques restent poss$($eAcute)d$($eAcute)s localement. |
| Granite-Docling, embeddings et reranker | docker-local | Ces capacit$($eAcute)s ne sont pas d$($eAcute)port$($eAcute)es sur le Spark sans nouvelle ADR. |

## R$($eGrave)gles de plateforme M-002

| R$($eGrave)gle | Comportement attendu | Invariants | Tests | ADR |
|---|---|---|---|---|
| PLAT-001 - Placement docker-local | ``docker-local`` poss$($eGrave)de l'application, les donn$($eAcute)es, les traitements, les jobs et l'outbox. | Aucun stockage m$($eAcute)tier ni worker documentaire ne quitte ``docker-local``. | T-003, T-004, T-009 | ADR-007; ADR-009 |
| PLAT-002 - Spark d'inf$($eAcute)rence sans $($eAcute)tat m$($eAcute)tier | ``spark-inference`` sert Gemma 4 par vLLM et calcule des inf$($eAcute)rences seulement. | Le Spark ne conserve ni corpus, ni conversations, ni claims, ni strat$($eAcute)gies, ni exp$($eAcute)riences. | T-003, T-005, T-009 | ADR-007; ADR-008; ADR-009 |
| PLAT-003 - Gateway LLM unique | ``llm-gateway`` est l'unique adaptateur r$($eAcute)seau vers ``spark-inference``. | Le gateway ne prend aucune d$($eAcute)cision m$($eAcute)tier et aucun contexte n'appelle vLLM directement. | T-005, T-006, T-009 | ADR-008; ADR-009 |
| PLAT-004 - Outbox transactionnelle | Les $($eAcute)v$($eAcute)nements intercontextes sont $($eAcute)crits dans l'outbox avec l'$($eAcute)tat producteur. | Les consommateurs sont idempotents; les jobs ne sont pas des $($eAcute)v$($eAcute)nements de domaine. | T-007 | DDD-ADR-006; DDD-ADR-008 |
| PLAT-005 - Jobs techniques prioris$($eAcute)s | La file de jobs ex$($eAcute)cute les unit$($eAcute)s techniques avec priorit$($eAcute) et idempotence. | Un job ne porte pas de fait de domaine et ne remplace pas un $($eAcute)v$($eAcute)nement publi$($eAcute). | T-008 | DDD-ADR-006 |
| PLAT-006 - Pannes explicites d'inf$($eAcute)rence | Une indisponibilit$($eAcute) Spark retourne ``LLM_UNAVAILABLE`` ou une erreur TLS explicite. | Aucun fallback silencieux n'est autoris$($eAcute); aucune publication partielle apr$($eGrave)s streaming interrompu. | T-006 | ADR-008; ADR-009 |
| PLAT-007 - Observabilit$($eAcute) technique | Les logs et m$($eAcute)triques couvrent disponibilit$($eAcute) Spark, DNS, TCP, TLS, authentification, latence, TTFT, retries et circuit breaker. | Les prompts, preuves et r$($eAcute)ponses complets ne sont pas journalis$($eAcute)s. | T-010 | ADR-008; ADR-009 |
| PLAT-008 - Commandes de validation | La sp$($eAcute)cification est valid$($eAcute)e par les commandes M-002, test et lint. | Aucun GREEN n'est implicite; chaque commande doit $($eCircumflex)tre ex$($eAcute)cut$($eAcute)e explicitement. | T-002, T-011 | ADR-010 |

## Commandes de validation

````powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m002_specification.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1
````

## Hors p$($eAcute)rim$($eGrave)tre M-002

- Aucun Compose local n'est impl$($eAcute)ment$($eAcute) par cette sp$($eAcute)cification.
- Aucun endpoint Spark n'est cod$($eAcute) en dur dans le domaine.
- Aucun provider externe de remplacement n'est introduit.
- Aucune valeur par d$($eAcute)faut implicite n'est accept$($eAcute)e.
"@
}

function Invoke-M002Validator {
    param(
        [Parameter(Mandatory = $true)]
        [string] $SpecPath
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $validatorPath -Path $SpecPath 2>&1
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    return [pscustomobject] @{
        ExitCode = $LASTEXITCODE
        Output = ($output -join "`n")
    }
}

function Assert-ExitCode {
    param(
        [Parameter(Mandatory = $true)]
        [int] $Actual,

        [Parameter(Mandatory = $true)]
        [int] $Expected,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    if ($Actual -ne $Expected) {
        throw "$Message Code obtenu: $Actual"
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

function New-TemporarySpec {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name,

        [Parameter(Mandatory = $true)]
        [string] $Content
    )

    $specPath = Join-Path $temporaryRoot "$Name.md"
    $Content | Set-Content -Encoding UTF8 -LiteralPath $specPath
    return $specPath
}

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
    throw "Validateur de sp$($eAcute)cification M-002 absent: scripts/validate_m002_specification.ps1"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    $validContent = New-ValidM002SpecificationContent
    $validSpecPath = New-TemporarySpec -Name "valid" -Content $validContent
    $validResult = Invoke-M002Validator -SpecPath $validSpecPath
    if ($validResult.ExitCode -ne 0) {
        throw "Une sp$($eAcute)cification M-002 conforme doit $([char] 0x00EA)tre accept$($eAcute)e. Sortie du validateur: $($validResult.Output)"
    }
    Assert-ExitCode -Actual $validResult.ExitCode -Expected 0 -Message "Une sp$($eAcute)cification M-002 conforme doit $([char] 0x00EA)tre accept$($eAcute)e."

    $missingSectionSpecPath = New-TemporarySpec `
        -Name "missing-section" `
        -Content ($validContent.Replace("## R$($eGrave)gles de plateforme M-002", "## R$($eGrave)gles incompl$($eGrave)tes"))
    $missingSectionResult = Invoke-M002Validator -SpecPath $missingSectionSpecPath
    Assert-ExitCode -Actual $missingSectionResult.ExitCode -Expected 1 -Message "Une section obligatoire absente doit $([char] 0x00EA)tre refus$($eAcute)e."
    Assert-OutputContains -Output $missingSectionResult.Output -Expected "Section obligatoire absente: ## R$($eGrave)gles de plateforme M-002" -Message "La section absente doit $([char] 0x00EA)tre nomm$($eAcute)e."

    $missingAdrSpecPath = New-TemporarySpec `
        -Name "missing-adr" `
        -Content ($validContent.Replace("ADR-009", "ADR-009-RETIR$($eAcute)E"))
    $missingAdrResult = Invoke-M002Validator -SpecPath $missingAdrSpecPath
    Assert-ExitCode -Actual $missingAdrResult.ExitCode -Expected 1 -Message "Une ADR applicable absente doit $([char] 0x00EA)tre refus$($eAcute)e."
    Assert-OutputContains -Output $missingAdrResult.Output -Expected "ADR applicable absente: ADR-009" -Message "L'ADR absente doit $([char] 0x00EA)tre nomm$($eAcute)e."

    $wrongPlacementSpecPath = New-TemporarySpec `
        -Name "wrong-placement" `
        -Content ($validContent.Replace("| Gemma 4 et vLLM principal | spark-inference |", "| Gemma 4 et vLLM principal | docker-local |"))
    $wrongPlacementResult = Invoke-M002Validator -SpecPath $wrongPlacementSpecPath
    Assert-ExitCode -Actual $wrongPlacementResult.ExitCode -Expected 1 -Message "Un placement physique incoh$($eAcute)rent doit $([char] 0x00EA)tre refus$($eAcute)."
    Assert-OutputContains -Output $wrongPlacementResult.Output -Expected "Placement invalide pour Gemma 4 et vLLM principal" -Message "Le placement incoh$($eAcute)rent doit $([char] 0x00EA)tre nomm$($eAcute)."

    $silentFallbackSpecPath = New-TemporarySpec `
        -Name "silent-fallback" `
        -Content ($validContent.Replace("Aucun fallback silencieux n'est autoris$($eAcute)", "Un fallback silencieux autoris$($eAcute) vers un fournisseur distant de secours est configur$($eAcute)"))
    $silentFallbackResult = Invoke-M002Validator -SpecPath $silentFallbackSpecPath
    Assert-ExitCode -Actual $silentFallbackResult.ExitCode -Expected 1 -Message "Un fallback silencieux doit $([char] 0x00EA)tre refus$($eAcute)."
    Assert-OutputContains -Output $silentFallbackResult.Output -Expected "Fallback silencieux interdit" -Message "Le fallback silencieux doit $([char] 0x00EA)tre nomm$($eAcute)."

    $requiredObservabilityTerms = @(
        "disponibilit$($eAcute) Spark",
        "DNS",
        "TCP",
        "authentification",
        "TTFT"
    )
    foreach ($term in $requiredObservabilityTerms) {
        $weakenedObservabilitySpecPath = New-TemporarySpec `
            -Name ("missing-observability-" + ($term -replace "[^A-Za-z0-9]", "-")) `
            -Content ($validContent.Replace("$term, ", "").Replace(", $term", ""))
        $weakenedObservabilityResult = Invoke-M002Validator -SpecPath $weakenedObservabilitySpecPath
        Assert-ExitCode -Actual $weakenedObservabilityResult.ExitCode -Expected 1 -Message "Une observabilit$($eAcute) PLAT-007 incompl$($eGrave)te doit $([char] 0x00EA)tre refus$($eAcute)e: $term."
        Assert-OutputContains -Output $weakenedObservabilityResult.Output -Expected "Dimension d'observabilit$($eAcute) absente: $term" -Message "La dimension d'observabilit$($eAcute) absente doit $([char] 0x00EA)tre nomm$($eAcute)e."
    }

    $hardcodedEndpointSpecPath = New-TemporarySpec `
        -Name "hardcoded-endpoint" `
        -Content ($validContent + "`nEndpoint Spark cod$($eAcute): https://spark-inference.home.arpa:8443/v1`n")
    $hardcodedEndpointResult = Invoke-M002Validator -SpecPath $hardcodedEndpointSpecPath
    Assert-ExitCode -Actual $hardcodedEndpointResult.ExitCode -Expected 1 -Message "Un endpoint Spark cod$($eAcute) en dur doit $([char] 0x00EA)tre refus$($eAcute)."
    Assert-OutputContains -Output $hardcodedEndpointResult.Output -Expected "Endpoint Spark cod$($eAcute) en dur interdit" -Message "L'endpoint cod$($eAcute) en dur doit $([char] 0x00EA)tre nomm$($eAcute)."
}
finally {
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
}

Write-Host "Tests unitaires du validateur de sp$($eAcute)cification M-002: OK"
