$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m003_specification.ps1"
$temporaryRoot = Join-Path $repoRoot (".tmp/ost_m003_spec_unit_" + [System.Guid]::NewGuid().ToString("N"))

$eAcute = [char] 0x00E9
$eGrave = [char] 0x00E8
$aGrave = [char] 0x00E0
$uGrave = [char] 0x00F9
$eCircumflex = [char] 0x00EA
$cCedilla = [char] 0x00E7

function New-ValidM003SpecificationContent {
    return @"
# M-003 - Source enregistr$($eAcute)e, diagnostiqu$($eAcute)e et rout$($eAcute)e

## Statut

- Milestone: M-003 - Source enregistr$($eAcute)e, diagnostiqu$($eAcute)e et rout$($eAcute)e.
- Source canonique: ``docs/specs/plan_implementation_milestones_workstreams.md``, section ``M-003 - Source enregistr$($eAcute)e, diagnostiqu$($eAcute)e et rout$($eAcute)e``.
- Sp$($eAcute)cification normative: ``docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md``, sections 5, 12, 17, 19, 20 et 21.
- ADR consult$($eAcute)es: ADR-002, ADR-003, DDD-ADR-003.
- Contrats amont: ``docs/specs/m001_frontieres_ddd_contrats_publies.md`` et ``docs/specs/m002_plateforme_locale_sure.md``.
- ADR: non requise, car M-003 applique le routage hybride, l'usage OCRmyPDF conditionnel et le langage publi$($eAcute) documentaire sans changer leur sens.

## Sc$($eAcute)nario BDD

- Given la sp$($eAcute)cification v4.1 d$($eAcute)finit SP comme propri$($eAcute)taire du diagnostic et du routage documentaire.
- When la sp$($eAcute)cification M-003 est publi$($eAcute)e.
- Then chaque comportement M-003 nomme son invariant, son sc$($eAcute)nario BDD, son test RED, ses ADR applicables et sa commande de validation.

## Mission

M-003 publie le contrat ex$($eAcute)cutable du bounded context SP pour transformer un PDF original en ``SourceDocument`` enregistr$($eAcute), diagnostiqu$($eAcute) page par page et muni d'une route explicite. Le PDF original reste immuable, chaque page est repr$($eAcute)sent$($eAcute)e dans un manifeste de pages et une route incertaine produit une revue manuelle ou une quarantaine explicite.

M-003 ne publie aucune version canonique et ne d$($eAcute)cide pas l'autorit$($eAcute) textuelle finale. Ces comportements restent exclus et rel$($eGrave)vent de M-004.

## Contexte DDD

- Domaine: traitement des sources documentaires.
- Bounded context: SP.
- Objectif m$($eAcute)tier: d$($eAcute)finir comment un PDF original devient une source enregistr$($eAcute)e, diagnostiqu$($eAcute)e page par page et munie d'une route explicite sans conversion canonique encore publi$($eAcute)e.
- Agr$($eAcute)gats concern$($eAcute)s: ``SourceDocument`` et ``DocumentProcessingRun``.
- Int$($eAcute)grations: M-003 consomme les capacit$($eAcute)s techniques M-002 et pr$($eAcute)pare les contrats SP qui seront publi$($eAcute)s apr$($eGrave)s M-004 via ``SourceLocator``.
- Garde-fous: aucun choix implicite de route n'est accept$($eAcute), aucune bascule silencieuse n'est accept$($eAcute)e, une source en quarantaine n'est pas publiable.

## Langage ubiquitaire M-003

| Terme | Sens M-003 |
|---|---|
| SourceDocument | Agr$($eAcute)gat qui poss$($eGrave)de l'enregistrement du PDF original, son empreinte stable, son $($eAcute)tat de source et son statut de publication interdit tant que le diagnostic n'est pas rout$($eAcute). |
| DocumentProcessingRun | Agr$($eAcute)gat qui poss$($eGrave)de une tentative de diagnostic et de routage pour un SourceDocument donn$($eAcute). |
| PDF original | Fichier source conserv$($eAcute) comme artefact immuable; le syst$($eGrave)me ne le modifie pas. |
| empreinte stable | Hash calcul$($eAcute) sur l'original pour identifier la source et refuser les substitutions silencieuses. |
| manifeste de pages | Inventaire complet des pages attendues pour le PDF original. |
| diagnostic de page | Ensemble de signaux observ$($eAcute)s sur une page: texte natif, image, structure, OCR existant, rotation et lisibilit$($eAcute). |
| route de page | D$($eAcute)cision explicite de traitement page par page ou document par document. |
| revue manuelle | $($eAcute)tat explicite demand$($eAcute) quand la route ne peut pas $($eCircumflex)tre d$($eAcute)cid$($eAcute)e sans risque. |
| quarantaine | $($eAcute)tat bloquant qui interdit toute publication de la source. |

## Agr$($eAcute)gats et objets-valeur

| Agr$($eAcute)gat | Responsabilit$($eAcute) M-003 | Invariants | $($eAcute)v$($eAcute)nements |
|---|---|---|---|
| SourceDocument | Enregistrer le PDF original immuable, son empreinte stable et son $($eAcute)tat de source. | L'original reste immuable; une source en quarantaine n'est pas publiable. | SourceDocumentRegistered; SourceDocumentQuarantined |
| DocumentProcessingRun | Construire le manifeste de pages, enregistrer les diagnostics page par page et produire une route explicite. | Chaque page du PDF est repr$($eAcute)sent$($eAcute)e; une route incertaine produit une revue manuelle explicite. | PageManifestCreated; PageDiagnosticRecorded; PageRoutePlanned; ManualReviewRequested |

| Objet-valeur | Sens M-003 | Invariants |
|---|---|---|
| OriginalFingerprint | Empreinte stable du PDF original. | Calcul$($eAcute)e sur le fichier original et jamais remplac$($eAcute)e sans nouvelle source. |
| PageManifest | Liste compl$($eGrave)te des pages attendues. | Le nombre de pages diagnostiqu$($eAcute)es doit $($eCircumflex)tre $($eAcute)gal au nombre de pages du manifeste. |
| PageDiagnostic | Signaux observ$($eAcute)s pour une page. | Les signaux insuffisants ne produisent pas de route implicite. |
| PageRoute | D$($eAcute)cision explicite de traitement. | La route doit $($eCircumflex)tre nomm$($eAcute)e et justifi$($eAcute)e. |

## Politiques de domaine M-003

| Politique | D$($eAcute)cision | Invariants | ADR |
|---|---|---|---|
| SourceRegistrationPolicy | Accepte l'enregistrement seulement avec PDF original, empreinte stable et identit$($eAcute) de source explicites. | L'original reste immuable. | DDD-ADR-003 |
| PageManifestCompletenessPolicy | Refuse un diagnostic qui laisse une page hors manifeste. | Chaque page est repr$($eAcute)sent$($eAcute)e dans le manifeste. | DDD-ADR-003 |
| PageDiagnosticPolicy | Mesure les signaux de texte natif, image, structure et OCR existant sans publier de conversion. | Le diagnostic pr$($eAcute)c$($eGrave)de tout routage. | ADR-002; ADR-003 |
| PageRoutingPolicy | Choisit une route explicite ou demande une revue manuelle. | Une route incertaine produit une revue explicite; aucune bascule silencieuse n'est accept$($eAcute)e. | ADR-002 |
| QuarantinePublicationPolicy | Bloque toute publication d'une source en quarantaine. | Une source en quarantaine n'est pas publiable. | DDD-ADR-003 |

## Machine d'$($eAcute)tats M-003

| $($eAcute)tat | Port$($eAcute)e | Sens M-003 | Transition autoris$($eAcute)e |
|---|---|---|---|
| REGISTERED | SourceDocument | Le PDF original et son empreinte stable sont enregistr$($eAcute)s. | Vers MANIFEST_CREATED. |
| MANIFEST_CREATED | DocumentProcessingRun | Le manifeste de pages couvre toutes les pages attendues. | Vers DIAGNOSED ou QUARANTINED. |
| DIAGNOSED | DocumentProcessingRun | Chaque page poss$($eGrave)de un diagnostic. | Vers ROUTE_PLANNED, MANUAL_REVIEW ou QUARANTINED. |
| ROUTE_PLANNED | DocumentProcessingRun | Chaque page poss$($eGrave)de une route explicite et justifi$($eAcute)e. | Fin M-003; M-004 pourra consommer la route. |
| MANUAL_REVIEW | DocumentProcessingRun | Une incertitude exige une d$($eAcute)cision humaine explicite. | Vers ROUTE_PLANNED ou QUARANTINED apr$($eGrave)s d$($eAcute)cision. |
| QUARANTINED | SourceDocument | La source est bloqu$($eAcute)e et non publiable. | Fin bloquante tant qu'aucune d$($eAcute)cision explicite ne la remplace. |

## Comportements v$($eAcute)rifiables M-003

| Comportement | Invariant | Sc$($eAcute)nario BDD | Test RED | ADR | Commande |
|---|---|---|---|---|---|
| SP-001 - Enregistrement immuable | L'original reste immuable et l'empreinte stable identifie la source. | Given un PDF original ajout$($eAcute); When SP enregistre la source; Then l'original et son empreinte stable sont conserv$($eAcute)s sans modification. | T-003 | DDD-ADR-003 | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m003_specification.ps1 |
| SP-002 - Manifeste complet | Chaque page est repr$($eAcute)sent$($eAcute)e dans le manifeste de pages. | Given un SourceDocument enregistr$($eAcute); When le manifeste est cr$($eAcute)$($eAcute); Then aucune page du PDF original ne reste hors manifeste. | T-004 | DDD-ADR-003 | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m003_specification.ps1 |
| SP-003 - Diagnostic page par page | Chaque page poss$($eGrave)de un diagnostic avant routage. | Given un manifeste complet; When le diagnostic est demand$($eAcute); Then chaque page re$($cCedilla)oit ses signaux documentaires. | T-005 | ADR-002; ADR-003 | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m003_specification.ps1 |
| SP-004 - Routage explicite | La route de page est nomm$($eAcute)e et justifi$($eAcute)e. | Given des diagnostics complets; When la politique de routage s'ex$($eAcute)cute; Then chaque page re$($cCedilla)oit une route explicite. | T-006 | ADR-002 | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m003_specification.ps1 |
| SP-005 - Revue manuelle d'incertitude | Une route incertaine produit une revue manuelle explicite. | Given des signaux contradictoires; When aucune route s$($uGrave)re ne peut $($eCircumflex)tre d$($eAcute)cid$($eAcute)e; Then SP demande une revue manuelle au lieu de changer de route implicitement. | T-006 | ADR-002; ADR-003 | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m003_specification.ps1 |
| SP-006 - Quarantaine non publiable | Une source en quarantaine n'est pas publiable. | Given une source en quarantaine; When une publication est demand$($eAcute)e; Then la publication est refus$($eAcute)e explicitement. | T-007 | DDD-ADR-003 | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m003_specification.ps1 |
| SP-007 - Commandes de validation | Aucun GREEN n'est implicite. | Given la sp$($eAcute)cification M-003; When les gates sont ex$($eAcute)cut$($eAcute)s; Then le validateur M-003, test et lint sont tous nomm$($eAcute)s. | T-002 | ADR-002; ADR-003; DDD-ADR-003 | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m003_specification.ps1 |
| SP-008 - Contrat HTTP documentaire | Les commandes publiques exposent les statuts et erreurs client sans identifiant interne. | Given un client appelle les commandes documentaires SP; When l'enregistrement ou le diagnostic est demand$($eAcute); Then les r$($eAcute)ponses HTTP nomment cr$($eAcute)ation, doublon, acceptation, erreurs client et erreurs m$($eAcute)tier sans fallback. | T-008 | DDD-ADR-003; ADR-010 | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m003_specification.ps1 |

## Contrat HTTP M-003

| Endpoint | Succ$($eGrave)s | Erreurs publiques | Corps public |
|---|---|---|---|
| POST /v1/documents | 201 pour une source cr$($eAcute)$($eAcute)e; 200 avec ``DUPLICATE_SOURCE`` pour un doublon binaire existant. | 400 ``HTTP_REQUEST_INVALID`` pour ``original_content`` ou ``bibliographic_metadata`` absent; 422 ``SOURCE_UNREADABLE`` pour PDF corrompu ou chiffr$($eAcute). | ``document_id``, ``document_status``, et ``duplicate`` seulement quand le statut est ``DUPLICATE_SOURCE``. |
| POST /v1/documents/{id}/diagnose | 202 ``DIAGNOSTIC_REQUESTED`` quand le job ``DIAGNOSE`` est accept$($eAcute). | 400 ``HTTP_REQUEST_INVALID`` pour ``document_id`` invalide; 404 ``SOURCE_NOT_FOUND``; 409 ``DIAGNOSTIC_ALREADY_REQUESTED``. | ``document_id`` et ``diagnostic_status``, sans ``processing_run_id``, sans ``original_storage_ref`` et sans route. |

## Commandes de validation

La commande sans ``-Path`` cible exclusivement ``docs/specs/m003_source_enregistree_diagnostiquee_routee.md``.

````powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m003\validate_m003_specification_acceptance.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m003_specification.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1
````

## Exclusions M-004

- M-003 ne publie aucune version canonique.
- M-003 ne produit pas le Docling JSON final.
- M-003 ne d$($eAcute)cide pas l'autorit$($eAcute) textuelle unique par page.
- M-003 ne publie aucun ``CanonicalSourcePublished`` vers KA ou EG.
- M-003 n'introduit pas Docling comme mod$($eGrave)le de domaine; Docling reste un outil de conversion gouvern$($eAcute) par les politiques SP ult$($eAcute)rieures.
"@
}

function Invoke-M003SpecificationValidator {
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
    throw "Validateur de sp$($eAcute)cification M-003 absent: scripts/validate_m003_specification.ps1"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    $validContent = New-ValidM003SpecificationContent
    $validSpecPath = New-TemporarySpec -Name "valid" -Content $validContent
    $validResult = Invoke-M003SpecificationValidator -SpecPath $validSpecPath
    if ($validResult.ExitCode -ne 0) {
        throw "Une sp$($eAcute)cification M-003 conforme doit $([char] 0x00EA)tre accept$($eAcute)e. Sortie du validateur: $($validResult.Output)"
    }
    Assert-ExitCode -Actual $validResult.ExitCode -Expected 0 -Message "Une sp$($eAcute)cification M-003 conforme doit $([char] 0x00EA)tre accept$($eAcute)e."

    $missingSectionSpecPath = New-TemporarySpec `
        -Name "missing-section" `
        -Content ($validContent.Replace("## Mission", "## Mission incompl$($eGrave)te"))
    $missingSectionResult = Invoke-M003SpecificationValidator -SpecPath $missingSectionSpecPath
    Assert-ExitCode -Actual $missingSectionResult.ExitCode -Expected 1 -Message "Une section obligatoire absente doit $([char] 0x00EA)tre refus$($eAcute)e."
    Assert-OutputContains -Output $missingSectionResult.Output -Expected "Section obligatoire absente: ## Mission" -Message "La section absente doit $([char] 0x00EA)tre nomm$($eAcute)e."

    $missingAdrSpecPath = New-TemporarySpec `
        -Name "missing-adr" `
        -Content ($validContent.Replace("ADR-002", "ADR-002-RETIR$($eAcute)E"))
    $missingAdrResult = Invoke-M003SpecificationValidator -SpecPath $missingAdrSpecPath
    Assert-ExitCode -Actual $missingAdrResult.ExitCode -Expected 1 -Message "Une ADR applicable absente doit $([char] 0x00EA)tre refus$($eAcute)e."
    Assert-OutputContains -Output $missingAdrResult.Output -Expected "ADR applicable absente: ADR-002" -Message "L'ADR absente doit $([char] 0x00EA)tre nomm$($eAcute)e."

    $silentFallbackSpecPath = New-TemporarySpec `
        -Name "silent-fallback" `
        -Content ($validContent.Replace("aucune bascule silencieuse n'est accept$($eAcute)e", "un fallback silencieux autoris$($eAcute) vers NATIVE_STANDARD est configur$($eAcute)"))
    $silentFallbackResult = Invoke-M003SpecificationValidator -SpecPath $silentFallbackSpecPath
    Assert-ExitCode -Actual $silentFallbackResult.ExitCode -Expected 1 -Message "Un fallback silencieux doit $([char] 0x00EA)tre refus$($eAcute)."
    Assert-OutputContains -Output $silentFallbackResult.Output -Expected "Fallback silencieux interdit" -Message "Le fallback silencieux doit $([char] 0x00EA)tre nomm$($eAcute)."

    $defaultRouteSpecPath = New-TemporarySpec `
        -Name "default-route" `
        -Content ($validContent.Replace("aucun choix implicite de route n'est accept$($eAcute)", "une route par d$($eAcute)faut autoris$($eAcute)e NATIVE_STANDARD est appliqu$($eAcute)e"))
    $defaultRouteResult = Invoke-M003SpecificationValidator -SpecPath $defaultRouteSpecPath
    Assert-ExitCode -Actual $defaultRouteResult.ExitCode -Expected 1 -Message "Une route par d$($eAcute)faut doit $([char] 0x00EA)tre refus$($eAcute)e."
    Assert-OutputContains -Output $defaultRouteResult.Output -Expected "Route par d$($eAcute)faut interdite" -Message "La route par d$($eAcute)faut doit $([char] 0x00EA)tre nomm$($eAcute)e."

    $m004LeakSpecPath = New-TemporarySpec `
        -Name "m004-leak" `
        -Content ($validContent + "`nExigence: M-004 est impl$($eAcute)ment$($eAcute) par M-003 avec une conversion canonique publi$($eAcute)e.`n")
    $m004LeakResult = Invoke-M003SpecificationValidator -SpecPath $m004LeakSpecPath
    Assert-ExitCode -Actual $m004LeakResult.ExitCode -Expected 1 -Message "Une exigence M-004 gliss$($eAcute)e dans M-003 doit $([char] 0x00EA)tre refus$($eAcute)e."
    Assert-OutputContains -Output $m004LeakResult.Output -Expected "Exigence M-004 interdite dans M-003" -Message "La d$($eAcute)rive M-004 doit $([char] 0x00EA)tre nomm$($eAcute)e."
}
finally {
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
}

Write-Host "Tests unitaires du validateur de sp$($eAcute)cification M-003: OK"
