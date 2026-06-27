$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m004_specification.ps1"
$temporaryRoot = Join-Path $repoRoot (".tmp/ost_m004_spec_unit_" + [System.Guid]::NewGuid().ToString("N"))

$eAcute = [char] 0x00E9
$eGrave = [char] 0x00E8
$aGrave = [char] 0x00E0

function New-ValidM004SpecificationContent {
    return @"
# M-004 - Version canonique publi$($eAcute)e

## Statut

- Milestone: M-004 - Version canonique publi$($eAcute)e.
- ADR consult$($eAcute)es: ADR-001, ADR-002, ADR-003, ADR-004, ADR-010, DDD-ADR-003, DDD-ADR-006, DDD-ADR-008, DDD-ADR-010.
- ADR: non requise, car M-004 applique les d$($eAcute)cisions existantes sans changer leur sens.

## Sc$($eAcute)nario BDD

- Given une source M-003 enregistr$($eAcute)e, diagnostiqu$($eAcute)e et rout$($eAcute)e.
- When la sp$($eAcute)cification M-004 est publi$($eAcute)e.
- Then chaque comportement de version canonique nomme son invariant, son sc$($eAcute)nario BDD, son test RED, ses ADR applicables et sa commande de validation.

## Mission

M-004 publie le contrat ex$($eAcute)cutable du bounded context SP pour produire une CanonicalSource structur$($eAcute)e, contr$([char] 0x00F4)l$($eAcute)e, immutable et publiable depuis une source M-003 rout$($eAcute)e. M-004 produit un Docling JSON canonique et conserve le PDF original comme r$($eAcute)f$($eAcute)rence $($eAcute)ditoriale.

## Contexte DDD

- Domaine: traitement des sources documentaires.
- Bounded context: SP.
- Objectif m$($eAcute)tier: convertir les pages rout$($eAcute)es en DoclingDocument unique, choisir une autorit$($eAcute) textuelle unique par page et publier une version canonique immuable.
- Garde-fous: aucune source en quarantaine n'est publiable; aucun fallback Docling vers Granite n'est silencieux; Markdown et HTML restent des exports r$($eAcute)g$($eAcute)n$($eAcute)rables.
- Chaque page poss$($eGrave)de exactement une autorit$($eAcute) textuelle unique.

## Langage ubiquitaire M-004

| Terme | Sens M-004 |
|---|---|
| CanonicalSource | Agr$($eAcute)gat qui poss$($eGrave)de une version canonique accept$($eAcute)e, publiable et immutable. |
| CanonicalVersionId | Identifiant de version immuable; une correction en cr$($eAcute)e un nouveau. |
| DoclingDocument unique | Repr$($eAcute)sentation structur$($eAcute)e obtenue par fusion pagewise dans l'ordre du PDF. |
| Docling JSON canonique | Artefact canonique s$($eAcute)rialis$($eAcute) depuis le DoclingDocument. |
| TextAuthorityManifest | Manifeste qui associe chaque page $($aGrave) son autorit$($eAcute) textuelle. |
| SourceLocator | Langage publi$($eAcute) qui r$($eAcute)sout document, version, page, item et hash. |

## Agr$($eAcute)gats et objets-valeur

| Agr$($eAcute)gat | Responsabilit$($eAcute) M-004 | Invariants | $($eAcute)v$($eAcute)nements |
|---|---|---|---|
| CanonicalSource | Publier ou supers$($eAcute)der une version canonique accept$($eAcute)e. | La version publi$($eAcute)e est immuable; une correction cr$($eAcute)e une nouvelle version canonique et ne modifie jamais la version publi$($eAcute)e en place; une source en quarantaine n'est pas publiable. | CanonicalSourcePublished; CanonicalSourceSuperseded |

| Objet-valeur | Sens M-004 | Invariants |
|---|---|---|
| CanonicalVersionId | Identit$($eAcute) stable d'une version canonique. | Jamais r$($eAcute)utilis$($eAcute)e pour une correction. |
| CanonicalArtifactRef | R$($eAcute)f$($eAcute)rence vers le Docling JSON canonique. | Pointe vers un artefact contr$([char] 0x00F4)l$($eAcute). |
| TextAuthorityManifest | Autorit$($eAcute) textuelle retenue page par page. | Chaque page poss$($eGrave)de une seule autorit$($eAcute). |
| QualityDecision | Verdict de QA pr$($eAcute) et post-conversion. | Toute alerte bloquante refuse la publication. |
| CanonicalArtifactHash | Hash de contenu canonique. | Identique tant que la version est immuable. |

## Politiques normatives M-004

| Politique | D$($eAcute)cision | Invariants | ADR |
|---|---|---|---|
| TextAuthoritySelectionPolicy | S$($eAcute)lectionne l'autorit$($eAcute) textuelle unique d'une page. | Les transcriptions concurrentes ne sont pas fusionn$($eAcute)es silencieusement. | ADR-004 |
| CanonicalAcceptancePolicy | D$($eAcute)cide si la conversion peut devenir CanonicalSource. | Aucune page ne peut $([char] 0x00EA)tre omise; une source en quarantaine est refus$($eAcute)e. | ADR-001; ADR-002; ADR-003; ADR-004; DDD-ADR-003 |
| CriticalPageSamplingPolicy | Choisit les pages critiques pour contr$([char] 0x00F4)le renforc$($eAcute). | Les tableaux, formules, pages faibles et routes minoritaires sont $($eAcute)chantillonn$($eAcute)s. | ADR-002; ADR-003; ADR-004 |

## Machine d'$($eAcute)tats M-004

| $($eAcute)tat | Port$($eAcute)e | Sens M-004 | Transition autoris$($eAcute)e |
|---|---|---|---|
| ROUTED | DocumentProcessingRun | M-003 a produit une route explicite. | Vers PRE_QA_PASSED ou QUARANTINED. |
| PRE_QA_PASSED | DocumentProcessingRun | Les pages critiques et routes sont admissibles avant conversion. | Vers CONVERTED. |
| CONVERTED | DocumentProcessingRun | Les sorties de pages sont produites. | Vers POST_QA_PASSED ou REJECTED. |
| POST_QA_PASSED | DocumentProcessingRun | Le DoclingDocument unique satisfait les contr$([char] 0x00F4)les. | Vers ACCEPTED. |
| ACCEPTED | CanonicalSource | La version canonique est accept$($eAcute)e. | Vers PUBLISHED. |
| PUBLISHED | CanonicalSource | CanonicalSourcePublished peut $([char] 0x00EA)tre $($eAcute)mis. | Vers SUPERSEDED. |
| SUPERSEDED | CanonicalSource | Une version plus r$($eAcute)cente remplace la version courante. | Terminale. |
| QUARANTINED | DocumentProcessingRun | Publication interdite. | Terminale tant qu'une d$($eAcute)cision explicite ne relance pas une nouvelle tentative. |
| REJECTED | DocumentProcessingRun | QA ou invariants refusent la conversion. | Terminale. |

## Fusion pagewise vers DoclingDocument unique

La fusion pagewise ajoute chaque page dans l'ordre du PDF original, conserve le num$($eAcute)ro de page, normalise les coordonn$($eAcute)es, maintient les identifiants d'items uniques et relie chaque item au PDF original par SourceLocator. Aucune page ne peut $([char] 0x00EA)tre omise.

## QA pr$($eAcute)-conversion

La QA pr$($eAcute)-conversion contr$([char] 0x00F4)le les pages critiques choisies par CriticalPageSamplingPolicy, les routes minoritaires, les tableaux, les formules, les pages $($aGrave) faible confiance et les pages complexes avant conversion.

## QA post-conversion

La QA post-conversion contr$([char] 0x00F4)le le nombre de pages, le JSON valide, les identifiants uniques, la provenance de chaque item, les nombres, signes, pourcentages, tableaux, figures et l'autorit$($eAcute) enregistr$($eAcute)e.

## $($eAcute)v$($eAcute)nements M-004

| $($eAcute)v$($eAcute)nement | D$($eAcute)clencheur | Payload publi$($eAcute) |
|---|---|---|
| CanonicalSourcePublished | La version est publi$($eAcute)e vers KA et EG. | `CanonicalSourceRef` contractuel; `canonical_artifact_sha256` inclus; `SourceLocator` r$($eAcute)solu via le registre T-007 |
| CanonicalSourceSuperseded | Une correction publie une nouvelle version. | previous_canonical_version_id; new_canonical_version_id |
| CanonicalAuditEvent | Une publication, un refus QA ou une quarantaine post-canonique doit $([char] 0x00EA)tre observ$($eAcute). | trace_id; document_id; canonical_version_id; phase; status; page_count; pages_rejected_by_qa; ambiguous_text_authorities; artifact_hash; error_code |
| PreCanonicalAuditEvent | Une demande de conversion est accept$($eAcute)e ou refus$($eAcute)e avant existence d'une version canonique. | trace_id; document_id; phase; status; page_count; error_code; canonical_version_id nul; artifact_hash nul |

## Comportements v$($eAcute)rifiables M-004

| Comportement | Invariant | Sc$($eAcute)nario BDD | Test RED | ADR | Commande |
|---|---|---|---|---|---|
| SP-009 - Sp$($eAcute)cification ex$($eAcute)cutable M-004 | La sp$($eAcute)cification nomme mission, agr$($eAcute)gat, politiques, QA, HTTP, ADR et exclusions. | Given une source M-003 rout$($eAcute)e; When la sp$($eAcute)cification M-004 est publi$($eAcute)e; Then elle est valid$($eAcute)e par commande PowerShell. | T-002 | ADR-001; ADR-002; ADR-003; ADR-004; DDD-ADR-003 | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m004_specification.ps1 |
| SP-010 - Fusion pagewise vers DoclingDocument unique | Aucune page ne peut $([char] 0x00EA)tre omise. | Given des pages rout$($eAcute)es; When la conversion fusionne les sorties; Then le DoclingDocument unique conserve toutes les pages dans l'ordre. | T-003 | ADR-001; ADR-002; ADR-003; ADR-004 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m004\validate_page_conversion_acceptance.ps1 |
| SP-011 - Autorit$($eAcute) textuelle unique par page | Chaque page poss$($eGrave)de une seule autorit$($eAcute). | Given une sortie native et Granite; When TextAuthoritySelectionPolicy arbitre; Then une seule autorit$($eAcute) est retenue. | T-004 | ADR-004 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m004\validate_text_authority_acceptance.ps1 |
| SP-012 - QA pr$($eAcute) et post-conversion | Les pages critiques et le Docling JSON sont contr$([char] 0x00F4)l$($eAcute)s. | Given une conversion candidate; When CanonicalAcceptancePolicy $($eAcute)value la version; Then les chiffres, signes, tableaux et provenance sont v$($eAcute)rifi$($eAcute)s. | T-005 | ADR-001; ADR-002; ADR-003; ADR-004 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m004\validate_canonical_quality_acceptance.ps1 |
| SP-013 - Publication immuable | Une correction cr$($eAcute)e une nouvelle version. | Given une version publi$($eAcute)e; When une correction est accept$($eAcute)e; Then l'ancienne version reste r$($eAcute)solvable et une nouvelle version est publi$($eAcute)e. | T-006 | ADR-001; DDD-ADR-003; DDD-ADR-010 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m004\validate_canonical_publication_acceptance.ps1 |
| SP-014 - SourceLocator r$($eAcute)solvable | Tout item canonique pointe vers document, version, page, item et hash. | Given un item canonique; When un contexte aval ouvre sa preuve; Then SourceLocator r$($eAcute)sout l'item sans lire les tables SP. | T-007 | DDD-ADR-003 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m004\validate_source_locator_resolution_acceptance.ps1 |
| SP-015 - $($eAcute)v$($eAcute)nement CanonicalSourcePublished | SP est l'unique producteur de CanonicalSourcePublished. | Given une CanonicalSource publi$($eAcute)e; When l'outbox publie l'$($eAcute)v$($eAcute)nement; Then KA et EG re$([char] 0x00E7)oivent une r$($eAcute)f$($eAcute)rence idempotente. | T-008 | ADR-001; DDD-ADR-003; DDD-ADR-006; DDD-ADR-008 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m004\validate_canonical_publication_event_acceptance.ps1 |
| SP-016 - Contrat HTTP de conversion | Le client ne voit que les statuts publics et erreurs stables. | Given un client appelle POST /v1/documents/{id}/convert; When la commande est accept$($eAcute)e ou refus$($eAcute)e; Then la r$($eAcute)ponse ne divulgue pas d'identifiant interne. | T-009 | ADR-010; DDD-ADR-003; DDD-ADR-006; DDD-ADR-008 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m004\validate_document_conversion_command_acceptance.ps1 |
| SP-017 - Tra$([char] 0x00E7)abilit$($eAcute) et gates M-004 | Aucun GREEN n'est implicite. | Given les preuves M-004; When les gates s'ex$($eAcute)cutent; Then test, lint et validate_m004_specification.ps1 sont enr$([char] 0x00F4)l$($eAcute)s. | T-010 | ADR-001; ADR-004; ADR-010; DDD-ADR-003; DDD-ADR-006; DDD-ADR-008 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m004\validate_m004_traceability_acceptance.ps1 |

## Contrat HTTP M-004

| Endpoint | Succ$($eGrave)s | Erreurs publiques | Corps public |
|---|---|---|---|
| POST /v1/documents/{id}/convert | 202 CONVERSION_REQUESTED quand la source rout$($eAcute)e est accept$($eAcute)e pour conversion; 202 CANONICAL_ACCEPTED quand la version canonique est d$($eAcute)j$($aGrave) accept$($eAcute)e. | 400 HTTP_REQUEST_INVALID; 404 SOURCE_NOT_FOUND; 409 SOURCE_NOT_ROUTED; 409 SOURCE_QUARANTINED; 409 CONVERSION_ALREADY_REQUESTED; 422 PAGE_AUTHORITY_MISSING; 422 SOURCE_NOT_CANONICAL. | document_id; conversion_status; canonical_version_id seulement avec CANONICAL_ACCEPTED. |

## Commandes de validation

La commande sans -Path cible exclusivement docs/specs/m004_version_canonique_publiee.md.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m004\validate_m004_specification_acceptance.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m004_specification.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1
```

## Exclusions M-005

- M-004 ne cr$($eAcute)e aucune KnowledgeProjection.
- M-004 n'indexe rien dans Qdrant.
- M-004 ne d$($eAcute)coupe pas les chunks de recherche.
- M-004 ne d$($eAcute)clenche pas POST /v1/search.
"@
}

function Invoke-M004SpecificationValidator {
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
    throw "Validateur de sp$($eAcute)cification M-004 absent: scripts/validate_m004_specification.ps1"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    $validContent = New-ValidM004SpecificationContent
    $validSpecPath = New-TemporarySpec -Name "valid" -Content $validContent
    $validResult = Invoke-M004SpecificationValidator -SpecPath $validSpecPath
    Assert-ExitCode -Actual $validResult.ExitCode -Expected 0 -Message "Une sp$($eAcute)cification M-004 conforme doit $([char] 0x00EA)tre accept$($eAcute)e."

    $missingSectionSpecPath = New-TemporarySpec `
        -Name "missing-section" `
        -Content ($validContent.Replace("## Fusion pagewise vers DoclingDocument unique", "## Fusion incompl$($eGrave)te"))
    $missingSectionResult = Invoke-M004SpecificationValidator -SpecPath $missingSectionSpecPath
    Assert-ExitCode -Actual $missingSectionResult.ExitCode -Expected 1 -Message "Une section obligatoire absente doit $([char] 0x00EA)tre refus$($eAcute)e."
    Assert-OutputContains -Output $missingSectionResult.Output -Expected "Section obligatoire absente: ## Fusion pagewise vers DoclingDocument unique" -Message "La section absente doit $([char] 0x00EA)tre nomm$($eAcute)e."

    $missingAdrSpecPath = New-TemporarySpec `
        -Name "missing-adr" `
        -Content ($validContent.Replace("ADR-004", "ADR-004-RETIR$($eAcute)E"))
    $missingAdrResult = Invoke-M004SpecificationValidator -SpecPath $missingAdrSpecPath
    Assert-ExitCode -Actual $missingAdrResult.ExitCode -Expected 1 -Message "Une ADR documentaire absente doit $([char] 0x00EA)tre refus$($eAcute)e."
    Assert-OutputContains -Output $missingAdrResult.Output -Expected "ADR applicable absente: ADR-004" -Message "L'ADR absente doit $([char] 0x00EA)tre nomm$($eAcute)e."

    $missingAuthoritySpecPath = New-TemporarySpec `
        -Name "missing-authority" `
        -Content ($validContent.Replace("Chaque page poss$($eGrave)de exactement une autorit$($eAcute) textuelle unique.", "La page publi$($eAcute)e peut rester sans autorit$($eAcute) textuelle."))
    $missingAuthorityResult = Invoke-M004SpecificationValidator -SpecPath $missingAuthoritySpecPath
    Assert-ExitCode -Actual $missingAuthorityResult.ExitCode -Expected 1 -Message "L'absence d'autorit$($eAcute) textuelle unique doit $([char] 0x00EA)tre refus$($eAcute)e."
    Assert-OutputContains -Output $missingAuthorityResult.Output -Expected "Chaque page poss$($eGrave)de exactement une autorit$($eAcute) textuelle unique." -Message "L'invariant d'autorit$($eAcute) doit $([char] 0x00EA)tre nomm$($eAcute)."

    $omittedPageSpecPath = New-TemporarySpec `
        -Name "omitted-page" `
        -Content ($validContent.Replace("Aucune page ne peut $([char] 0x00EA)tre omise", "Une page peut $([char] 0x00EA)tre omise silencieusement"))
    $omittedPageResult = Invoke-M004SpecificationValidator -SpecPath $omittedPageSpecPath
    Assert-ExitCode -Actual $omittedPageResult.ExitCode -Expected 1 -Message "Une omission de page doit $([char] 0x00EA)tre refus$($eAcute)e."
    Assert-OutputContains -Output $omittedPageResult.Output -Expected "Page omise interdite" -Message "L'omission de page doit $([char] 0x00EA)tre nomm$($eAcute)e."

    $mutationSpecPath = New-TemporarySpec `
        -Name "mutation-in-place" `
        -Content ($validContent.Replace("une correction cr$($eAcute)e une nouvelle version canonique et ne modifie jamais la version publi$($eAcute)e en place", "une correction modifie la version publi$($eAcute)e en place"))
    $mutationResult = Invoke-M004SpecificationValidator -SpecPath $mutationSpecPath
    Assert-ExitCode -Actual $mutationResult.ExitCode -Expected 1 -Message "Une mutation en place doit $([char] 0x00EA)tre refus$($eAcute)e."
    Assert-OutputContains -Output $mutationResult.Output -Expected "Mutation en place interdite" -Message "La mutation en place doit $([char] 0x00EA)tre nomm$($eAcute)e."

    $renamedPolicySpecPath = New-TemporarySpec `
        -Name "renamed-policy" `
        -Content ($validContent.Replace("TextAuthoritySelectionPolicy", "TextAuthorityChoicePolicy"))
    $renamedPolicyResult = Invoke-M004SpecificationValidator -SpecPath $renamedPolicySpecPath
    Assert-ExitCode -Actual $renamedPolicyResult.ExitCode -Expected 1 -Message "Une politique normative renomm$($eAcute)e doit $([char] 0x00EA)tre refus$($eAcute)e."
    Assert-OutputContains -Output $renamedPolicyResult.Output -Expected "TextAuthoritySelectionPolicy" -Message "La politique normative absente doit $([char] 0x00EA)tre nomm$($eAcute)e."

    $kaProjectionSpecPath = New-TemporarySpec `
        -Name "ka-projection" `
        -Content ($validContent + "`nM-004 cr$($eAcute)e une projection KA searchable dans Qdrant.`n")
    $kaProjectionResult = Invoke-M004SpecificationValidator -SpecPath $kaProjectionSpecPath
    Assert-ExitCode -Actual $kaProjectionResult.ExitCode -Expected 1 -Message "Une projection KA introduite trop t$([char] 0x00F4)t doit $([char] 0x00EA)tre refus$($eAcute)e."
    Assert-OutputContains -Output $kaProjectionResult.Output -Expected "Projection KA interdite" -Message "La projection KA pr$($eAcute)matur$($eAcute)e doit $([char] 0x00EA)tre nomm$($eAcute)e."
}
finally {
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
}

Write-Host "Tests unitaires du validateur de sp$($eAcute)cification M-004: OK"
