$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m005_specification.ps1"
$temporaryRoot = Join-Path $repoRoot (".tmp/ost_m005_spec_unit_" + [System.Guid]::NewGuid().ToString("N"))
$eAcute = [char] 0x00E9
$eGrave = [char] 0x00E8
$aGrave = [char] 0x00E0
$capitalEAcute = [char] 0x00C9

function New-ValidM005SpecificationContent {
    $canonicalSpecPath = Join-Path $repoRoot "docs/specs/m005_projection_connaissance_recherchable.md"
    if (-not (Test-Path -LiteralPath $canonicalSpecPath -PathType Leaf)) {
        throw "Spécification canonique M-005 absente pour le fixture unitaire: docs/specs/m005_projection_connaissance_recherchable.md"
    }

    return Get-Content -Raw -Encoding UTF8 -LiteralPath $canonicalSpecPath

    return @'
# M-005 - Projection de connaissance recherchable

## Statut

- Milestone: M-005 - Projection de connaissance recherchable.
- ADR consultées: ADR-005, ADR-006, ADR-010, DDD-ADR-004, DDD-ADR-008.
- ADR: non requise, car M-005 applique les décisions existantes sans changer leur sens.

## Scénario BDD

- Given une version canonique M-004 publiée.
- When la spécification M-005 est publiée.
- Then chaque comportement de projection et recherche nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.

## Mission KA

KA construit des projections de recherche dérivées des versions canoniques publiées et retourne des preuves candidates traçables sans devenir source de vérité documentaire ou registre de claims.

## Contexte DDD

- Domaine: accès aux connaissances.
- Bounded context: KA.
- Objectif métier: rendre une version canonique interrogeable tout en conservant SP comme source documentaire et EG comme registre des claims.
- Garde-fous: Qdrant reste une projection régénérable; aucun claim EG dans l'index documentaire; RA consomme KnowledgeSearchPort sans accès direct à Qdrant; un score n'est pas une vérité métier.

## Langage ubiquitaire KA

| Terme | Sens M-005 |
|---|---|
| KnowledgeProjection | Agrégat KA qui relie une version canonique, un profil et un build régénérable. |
| ProjectionStatus | État observable de projection: REQUESTED, BUILDING, BUILT, INDEXING, SEARCHABLE, STALE, FAILED, RETIRED. |
| SearchKnowledge | Commande de recherche KA qui retourne des preuves candidates. |
| RequestKnowledgeProjection | Commande KA qui demande la construction d'une projection. |
| SearchScoreBundle | Détail des scores dense, sparse, fusion, rerank et diversification sans verdict de vérité. |
| SearchTracePolicy | Politique qui rend la recherche auditable. |
| SearchTraceStore | Port de persistance de la trace de fusion et des paramètres de recherche. |

## Agrégat KnowledgeProjection

| Agrégat | Responsabilité M-005 | Invariants | Événements |
|---|---|---|---|
| KnowledgeProjection | Construire, indexer, rendre recherchable, marquer stale, échouer ou retirer une projection KA. | Une projection ne peut être construite que depuis une version canonique publiée; une projection STALE ne doit pas être utilisée silencieusement; supprimer la projection ne supprime jamais la source canonique. | KnowledgeProjectionRequested; KnowledgeProjectionBuilt; KnowledgeProjectionBecameSearchable; KnowledgeProjectionFailed; KnowledgeProjectionBecameStale; KnowledgeProjectionRetired |

## Objets-valeur KA

| Objet-valeur | Sens M-005 | Invariants |
|---|---|---|
| KnowledgeProjectionId | Identité stable de projection. | Jamais dérivée d'un identifiant Qdrant. |
| CanonicalVersionRef | Référence à la version canonique M-004. | Obligatoire pour toute projection. |
| ProjectionProfile | Profil d'indexation versionné. | Aucun profil par défaut implicite. |
| BuildFingerprint | Empreinte des entrées de build. | Doit permettre une reconstruction idempotente. |
| SourceLocator | Localisateur résolvable de preuve candidate. | Obligatoire dans chaque résultat de recherche. |
| ContentHash | Hash du contenu canonique projeté. | Doit rester cohérent avec SourceLocator. |
| SearchScoreBundle | Scores de recherche détaillés. | Ne contient aucun verdict de vérité. |
| SearchTraceId | Identité de trace de recherche. | Obligatoire pour toute recherche auditable. |

## Politiques normatives M-005

| Politique | Décision | Invariants | ADR |
|---|---|---|---|
| ProjectionEligibilityPolicy | Autorise seulement les versions canoniques publiées et non mises en quarantaine. | Aucune source non canonique n'est indexable. | DDD-ADR-004; DDD-ADR-008 |
| ProjectionFreshnessPolicy | Refuse l'usage silencieux d'une projection STALE lorsqu'une projection actuelle est requise. | La fraîcheur est explicite dans la réponse ou l'erreur. | DDD-ADR-004 |
| HybridRetrievalPolicy | Combine dense, sparse, filtres, fusion, rerank et diversification. | Aucun fallback dense ou lexical silencieux. | ADR-005 |
| SearchTracePolicy | Persiste paramètres, versions, modèles, profils, filtres et trace de fusion. | Aucune recherche auditable sans SearchTraceStore. | ADR-010; DDD-ADR-008 |
| EvidenceCandidatePolicy | Retourne des preuves candidates et jamais des claims vérifiés. | L'index documentaire ne stocke aucun claim EG. | ADR-006 |

## Machine d'états M-005

| État | Portée | Sens M-005 | Transition autorisée |
|---|---|---|---|
| REQUESTED | KnowledgeProjection | La demande est acceptée. | Vers BUILDING ou FAILED. |
| BUILDING | KnowledgeProjection | Les chunks et métadonnées sont construits. | Vers BUILT ou FAILED. |
| BUILT | KnowledgeProjection | La projection documentaire est prête à indexer. | Vers INDEXING, STALE ou RETIRED. |
| INDEXING | KnowledgeProjection | L'index technique est publié. | Vers SEARCHABLE ou FAILED. |
| SEARCHABLE | KnowledgeProjection | La projection peut répondre à SearchKnowledge. | Vers STALE ou RETIRED. |
| STALE | KnowledgeProjection | Une entrée de build ou version amont a changé. | Vers BUILDING ou RETIRED. |
| FAILED | KnowledgeProjection | La construction ou indexation a échoué explicitement. | Vers REQUESTED après nouvelle commande. |
| RETIRED | KnowledgeProjection | La projection n'est plus servie. | Terminale. |

## Ports et adaptateurs KA

| Port | Responsabilité | Interdiction |
|---|---|---|
| CanonicalSourceReader | Lit les références canoniques publiées par SP. | Ne modifie jamais SP. |
| KnowledgeProjectionRepository | Persiste l'agrégat KnowledgeProjection. | Ne stocke pas les claims EG. |
| VectorIndex | Encapsule Qdrant comme projection technique régénérable. | RA et EG ne l'appellent jamais directement. |
| DenseEncoder | Produit les vecteurs denses versionnés. | Aucun modèle par défaut implicite. |
| SparseEncoder | Produit les représentations sparse versionnées. | Aucun fallback silencieux vers dense. |
| KnowledgeSearchPort | Contrat consommé par RA et EG pour obtenir des preuves candidates. | Aucun accès direct à Qdrant. |
| SearchTraceStore | Persiste la trace de fusion et les paramètres de recherche. | Aucune recherche auditable sans trace. |

## Événements KA

| Événement | Déclencheur | Payload publié |
|---|---|---|
| KnowledgeProjectionRequested | Une commande d'indexation KA est acceptée. | projection_id; document_id; canonical_version_id; projection_profile_id |
| KnowledgeProjectionBuilt | Chunks, métadonnées et empreinte sont construits. | projection_id; canonical_version_id; build_fingerprint; chunk_count |
| KnowledgeProjectionBecameSearchable | L'index régénérable est publié complètement. | projection_id; canonical_version_id; projection_profile_id; index_generation; published_at |
| KnowledgeProjectionFailed | Une étape échoue explicitement. | projection_id; failed_step; public_error_code; retry_allowed |
| KnowledgeProjectionBecameStale | Une version canonique ou un profil rend la projection obsolète. | projection_id; stale_reason; superseding_input_ref |
| KnowledgeProjectionRetired | Une projection est retirée du service de recherche. | projection_id; retired_reason |
| SearchKnowledgePerformed | Une recherche auditable est exécutée. | search_trace_id; projection_id; query_hash; filters_hash; result_count |

## API publique KA

| Endpoint | Succès | Erreurs publiques | Corps public |
|---|---|---|---|
| POST /v1/documents/{document_id}/index | 202 INDEXATION_REQUESTED quand la version canonique est acceptée pour projection. | 400 HTTP_REQUEST_INVALID; 404 SOURCE_NOT_FOUND; 409 SOURCE_NOT_CANONICAL; 409 SOURCE_QUARANTINED; 409 PROJECTION_ALREADY_REQUESTED; 422 PROJECTION_PROFILE_INVALID. | document_id; projection_id; projection_status; canonical_version_id. |
| POST /v1/search | 200 SEARCH_COMPLETED quand les preuves candidates sont retournées avec trace. | 400 HTTP_REQUEST_INVALID; 404 PROJECTION_NOT_FOUND; 409 PROJECTION_STALE; 422 FILTER_NOT_SUPPORTED; 422 SEARCH_PROFILE_UNSUPPORTED; 503 SEARCH_INDEX_UNAVAILABLE. | search_trace_id; projection_id; results; warnings; applied_filters. |

## Erreurs publiques

| Code | Statut HTTP | Sens public |
|---|---|---|
| HTTP_REQUEST_INVALID | 400 | Requête KA invalide. |
| SOURCE_NOT_FOUND | 404 | Source ou document inconnu. |
| SOURCE_NOT_CANONICAL | 409 | La version canonique publiée est absente. |
| SOURCE_QUARANTINED | 409 | La source est explicitement non indexable. |
| PROJECTION_ALREADY_REQUESTED | 409 | Une demande identique existe déjà. |
| PROJECTION_PROFILE_INVALID | 422 | Le profil de projection est invalide. |
| PROJECTION_NOT_FOUND | 404 | Projection absente. |
| PROJECTION_STALE | 409 | Projection obsolète refusée explicitement. |
| FILTER_NOT_SUPPORTED | 422 | Filtre inconnu ou non supporté. |
| SEARCH_PROFILE_UNSUPPORTED | 422 | Profil de recherche non supporté. |
| SEARCH_INDEX_UNAVAILABLE | 503 | Projection technique indisponible sans fallback silencieux. |

## Métriques et traces

| Signal | Type | Invariant |
|---|---|---|
| knowledge_projection_build_total | Métrique | Compte les builds par statut public. |
| knowledge_projection_searchable_total | Métrique | Compte les projections devenues SEARCHABLE. |
| knowledge_projection_failed_total | Métrique | Compte les échecs par code public. |
| knowledge_search_latency_seconds | Métrique | Mesure la latence sans payload documentaire complet. |
| knowledge_search_stale_projection_total | Métrique | Compte les refus de projection STALE. |
| knowledge_search_recall_at_k | Métrique d'évaluation | Mesure initiale M-005, pas seuil métier V1. |
| knowledge_search_mrr | Métrique d'évaluation | Mesure initiale M-005, pas seuil métier V1. |
| knowledge_search_ndcg | Métrique d'évaluation | Mesure initiale M-005, pas seuil métier V1. |
| search_trace_persisted_total | Trace | Prouve la persistance des paramètres, versions, modèles, profils, filtres et trace de fusion. |

## Comportements vérifiables M-005

| Comportement | Invariant | Scénario BDD | Test RED | ADR | Commande |
|---|---|---|---|---|---|
| KA-001 - Spécification exécutable M-005 | La spécification nomme mission KA, KnowledgeProjection, états, politiques, ports, événements, API, erreurs, métriques, exclusions et garde-fous. | Given une version canonique M-004 publiée; When la spécification M-005 est publiée; Then elle est validée par commande PowerShell. | T-002 | ADR-005; ADR-006; ADR-010; DDD-ADR-004; DDD-ADR-008 | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m005_specification.ps1 |
| KA-002 - Projection depuis version canonique | Une projection ne naît que depuis une version canonique publiée. | Given une CanonicalSource publiée; When RequestKnowledgeProjection est accepté; Then KnowledgeProjection est REQUESTED sans mutation SP. | T-003 | DDD-ADR-004; DDD-ADR-008; ADR-010 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m005\validate_knowledge_projection_acceptance.ps1 |
| KA-003 - Chunking traçable | Chaque chunk conserve SourceLocator et ContentHash. | Given un contenu canonique; When KA découpe le contenu; Then chaque chunk reste relié à la version canonique. | T-004 | DDD-ADR-004 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m005\validate_hierarchical_chunking_acceptance.ps1 |
| KA-004 - Métadonnées filtrables | Un filtre demandé est appliqué ou refusé explicitement. | Given une projection avec métadonnées; When SearchKnowledge reçoit des filtres; Then les filtres sont appliqués ou refusés. | T-005 | ADR-005; DDD-ADR-004 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m005\validate_projection_metadata_filters_acceptance.ps1 |
| KA-005 - Encodage dense et sparse | Les versions de modèles et paramètres sont obligatoires. | Given une projection construite; When l'encodage démarre; Then dense et sparse sont produits sans fallback silencieux. | T-006 | ADR-005; DDD-ADR-004 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m005\validate_projection_encoding_acceptance.ps1 |
| KA-006 - Index Qdrant régénérable | Qdrant reste une projection technique reconstruisible. | Given des encodages complets; When l'index est publié; Then KnowledgeProjectionBecameSearchable est émis après publication complète. | T-007 | ADR-005; DDD-ADR-004; DDD-ADR-008 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m005\validate_qdrant_projection_acceptance.ps1 |
| KA-007 - Recherche hybride traçable | Chaque résultat contient SourceLocator, ContentHash, SearchScoreBundle et trace de fusion. | Given une projection SEARCHABLE; When SearchKnowledge exécute une recherche hybride; Then KA retourne des preuves candidates auditées. | T-008 | ADR-005; ADR-006; DDD-ADR-004; DDD-ADR-008 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m005\validate_hybrid_search_acceptance.ps1 |
| KA-008 - Commande de recherche publique | Le contrat POST /v1/search masque Qdrant et expose seulement KA. | Given un client appelle POST /v1/search; When la recherche est valide; Then la réponse contient seulement le contrat public KA. | T-009 | ADR-005; ADR-010; DDD-ADR-004 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m005\validate_search_command_acceptance.ps1 |
| KA-009 - Traçabilité et métriques M-005 | Aucun GREEN n'est implicite et les métriques ne sont pas des seuils V1. | Given les preuves M-005; When les gates s'exécutent; Then test, lint, traceability et validate_m005_specification sont enrôlés. | T-010 | ADR-005; ADR-006; ADR-010; DDD-ADR-004; DDD-ADR-008 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m005\validate_m005_traceability_acceptance.ps1 |

## Commandes de validation

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m005\validate_m005_specification_acceptance.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m005\validate_m005_specification_unit.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m005_specification.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1
```

## Exclusions M-006 et M-007

- M-005 ne crée, ne vérifie et ne stocke aucun claim EG.
- M-005 ne produit aucune réponse RA, aucune synthèse et aucun verdict de vérité.
- M-005 ne publie pas POST /v1/claims/extract, POST /v1/claims/{id}/verify, POST /v1/answer ou POST /v1/research/deep.
'@
}

function Invoke-M005SpecificationValidator {
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
    throw "Validateur de spécification M-005 absent: scripts/validate_m005_specification.ps1"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    $validContent = New-ValidM005SpecificationContent
    $validSpecPath = New-TemporarySpec -Name "valid" -Content $validContent
    $validResult = Invoke-M005SpecificationValidator -SpecPath $validSpecPath
    Assert-ExitCode -Actual $validResult.ExitCode -Expected 0 -Message "Une spécification M-005 conforme doit être acceptée."

    $missingSectionSpecPath = New-TemporarySpec `
        -Name "missing-mission-ka" `
        -Content ($validContent.Replace("## Mission KA", "## Mission incomplète"))
    $missingSectionResult = Invoke-M005SpecificationValidator -SpecPath $missingSectionSpecPath
    Assert-ExitCode -Actual $missingSectionResult.ExitCode -Expected 1 -Message "Une section obligatoire absente doit être refusée."
    Assert-OutputContains -Output $missingSectionResult.Output -Expected "Section obligatoire absente: ## Mission KA" -Message "La section absente doit être nommée."

    $missingBehaviorSpecPath = New-TemporarySpec `
        -Name "missing-behavior" `
        -Content ($validContent.Replace("KA-007 - Recherche hybride", "KA-007 - Recherche hybride incompl$($eGrave)te"))
    $missingBehaviorResult = Invoke-M005SpecificationValidator -SpecPath $missingBehaviorSpecPath
    Assert-ExitCode -Actual $missingBehaviorResult.ExitCode -Expected 1 -Message "Un comportement obligatoire absent doit être refusé."
    Assert-OutputContains -Output $missingBehaviorResult.Output -Expected "Comportement attendu absent: KA-007 - Recherche hybride tra$([char] 0x00E7)able" -Message "Le comportement absent doit être nommé."

    $missingAdrSpecPath = New-TemporarySpec `
        -Name "missing-adr" `
        -Content ($validContent.Replace("DDD-ADR-004", "DDD-ADR-004-RETIRÉE"))
    $missingAdrResult = Invoke-M005SpecificationValidator -SpecPath $missingAdrSpecPath
    Assert-ExitCode -Actual $missingAdrResult.ExitCode -Expected 1 -Message "Une ADR documentaire absente doit être refusée."
    Assert-OutputContains -Output $missingAdrResult.Output -Expected "ADR applicable absente: DDD-ADR-004" -Message "L'ADR absente doit être nommée."

    $missingIndexEndpointSpecPath = New-TemporarySpec `
        -Name "missing-index-endpoint" `
        -Content ($validContent.Replace("POST /v1/documents/{document_id}/index", "POST /v1/documents/{document_id}/project"))
    $missingIndexEndpointResult = Invoke-M005SpecificationValidator -SpecPath $missingIndexEndpointSpecPath
    Assert-ExitCode -Actual $missingIndexEndpointResult.ExitCode -Expected 1 -Message "L'endpoint d'indexation KA doit être obligatoire."
    Assert-OutputContains -Output $missingIndexEndpointResult.Output -Expected "POST /v1/documents/{document_id}/index" -Message "L'endpoint absent doit être nommé."

    $missingEventsSpecPath = New-TemporarySpec `
        -Name "missing-events" `
        -Content ($validContent.Replace("KnowledgeProjectionBecameSearchable", "KnowledgeProjectionIndexed"))
    $missingEventsResult = Invoke-M005SpecificationValidator -SpecPath $missingEventsSpecPath
    Assert-ExitCode -Actual $missingEventsResult.ExitCode -Expected 1 -Message "Les événements KA obligatoires doivent être contrôlés."
    Assert-OutputContains -Output $missingEventsResult.Output -Expected "$($capitalEAcute)v$($eAcute)nement attendu absent: KnowledgeProjectionBecameSearchable" -Message "L'événement absent doit être nommé."

    $missingTraceStoreSpecPath = New-TemporarySpec `
        -Name "missing-search-trace-store" `
        -Content ($validContent.Replace("SearchTraceStore", "SearchTraceWriter"))
    $missingTraceStoreResult = Invoke-M005SpecificationValidator -SpecPath $missingTraceStoreSpecPath
    Assert-ExitCode -Actual $missingTraceStoreResult.ExitCode -Expected 1 -Message "SearchTraceStore doit être obligatoire."
    Assert-OutputContains -Output $missingTraceStoreResult.Output -Expected "SearchTraceStore" -Message "Le port de trace absent doit être nommé."

    $qdrantAsSourceSpecPath = New-TemporarySpec `
        -Name "qdrant-source" `
        -Content ($validContent + "`nQdrant est la source de v$($eAcute)rit$($eAcute) documentaire de KA.`n")
    $qdrantAsSourceResult = Invoke-M005SpecificationValidator -SpecPath $qdrantAsSourceSpecPath
    Assert-ExitCode -Actual $qdrantAsSourceResult.ExitCode -Expected 1 -Message "Qdrant source de vérité doit être refusé."
    Assert-OutputContains -Output $qdrantAsSourceResult.Output -Expected "Qdrant source de v$($eAcute)rit$($eAcute) interdit" -Message "La confusion Qdrant doit être nommée."

    $claimInIndexSpecPath = New-TemporarySpec `
        -Name "claim-in-index" `
        -Content ($validContent + "`nL'index documentaire stocke les claims EG vérifiés.`n")
    $claimInIndexResult = Invoke-M005SpecificationValidator -SpecPath $claimInIndexSpecPath
    Assert-ExitCode -Actual $claimInIndexResult.ExitCode -Expected 1 -Message "Les claims dans l'index documentaire doivent être refusés."
    Assert-OutputContains -Output $claimInIndexResult.Output -Expected "Claim EG dans l'index documentaire interdit" -Message "Le claim stocké doit être nommé."

    $directRaQdrantSpecPath = New-TemporarySpec `
        -Name "direct-ra-qdrant" `
        -Content ($validContent + "`nRA lit Qdrant directement pour accélérer la recherche.`n")
    $directRaQdrantResult = Invoke-M005SpecificationValidator -SpecPath $directRaQdrantSpecPath
    Assert-ExitCode -Actual $directRaQdrantResult.ExitCode -Expected 1 -Message "L'accès RA direct à Qdrant doit être refusé."
    Assert-OutputContains -Output $directRaQdrantResult.Output -Expected "Acc$($eGrave)s RA direct $($aGrave) Qdrant interdit" -Message "L'accès direct doit être nommé."

    $scoreTruthSpecPath = New-TemporarySpec `
        -Name "score-truth" `
        -Content ($validContent + "`nLe score hybride est une v$($eAcute)rit$($eAcute) m$($eAcute)tier suffisante pour décider une affirmation.`n")
    $scoreTruthResult = Invoke-M005SpecificationValidator -SpecPath $scoreTruthSpecPath
    Assert-ExitCode -Actual $scoreTruthResult.ExitCode -Expected 1 -Message "Un score comme vérité métier doit être refusé."
    Assert-OutputContains -Output $scoreTruthResult.Output -Expected "Score trait$($eAcute) comme v$($eAcute)rit$($eAcute) interdit" -Message "Le score-vérité doit être nommé."
}
finally {
    Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
}

Write-Host "Tests unitaires du validateur de spécification M-005: OK"
