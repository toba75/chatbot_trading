param(
    [Parameter(Mandatory = $false)]
    [string] $ComposePath,

    [Parameter(Mandatory = $false)]
    [string] $TopologyPath,

    [Parameter(Mandatory = $false)]
    [string] $SparkFirewallPath,

    [Parameter(Mandatory = $false)]
    [string] $ApplicationConfigPath,

    [Parameter(Mandatory = $false)]
    [string] $AuditPath,

    [Parameter(Mandatory = $false)]
    [string] $MatrixPath,

    [Parameter(Mandatory = $false)]
    [string] $TestGatePath,

    [Parameter(Mandatory = $false)]
    [string] $LintGatePath
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)

$defaultComposePath = "deploy/local-compose/compose.yaml"
$defaultTopologyPath = "app/platform/topology_registry.json"
$defaultSparkFirewallPath = "deploy/spark-firewall/network-boundary.json"
$defaultApplicationConfigPath = "config/application.example.yaml"
$defaultAuditPath = "docs/governance/m013_security_audit.md"
$defaultMatrixPath = "docs/traceability/matrix.md"
$defaultTestGatePath = "scripts/test.ps1"
$defaultLintGatePath = "scripts/lint.ps1"

$requiredDeniedInitiators = @(
    "browser",
    "internet",
    "worker-documents",
    "worker-research",
    "worker-backtest",
    "postgres",
    "qdrant",
    "granite-docling",
    "ui",
    "orchestrator-api"
)

$allowedSparkServices = @(
    "gemma-vllm",
    "spark-model-cache"
)

$requiredAuditMarkers = @(
    "# Audit sécurité réseau Spark M-013",
    "M013-SecurityAuditReport-1.0",
    "SecurityAuditPolicy",
    "Given la topologie V1 cible",
    "When l'audit réseau M-013 inspecte Compose",
    "Then aucun service interne n'est exposé publiquement",
    "le point d'entrée utilisateur reste lié",
    "egress autorisé",
    "ADR-007",
    "ADR-008",
    "ADR-009",
    "ADR-014",
    "deploy/local-compose/compose.yaml",
    "app/platform/topology_registry.json",
    "deploy/spark-firewall/network-boundary.json",
    "scripts/validate_network_boundary.ps1",
    "127.0.0.1",
    "llm-gateway -> spark-inference",
    "browser -> spark-inference | refusé",
    "worker-research -> spark-inference | refusé",
    "Authentification Spark none explicite",
    "TLS Spark disabled explicite",
    "aucun corpus, base, expérience ou secret métier sur Spark",
    "ADR-014"
)

$requiredAuditControls = @(
    "CTRL-M013-NET-001",
    "CTRL-M013-NET-002",
    "CTRL-M013-NET-003",
    "CTRL-M013-NET-004",
    "CTRL-M013-NET-005",
    "CTRL-M013-NET-006",
    "CTRL-M013-NET-007",
    "CTRL-M013-NET-008",
    "CTRL-M013-NET-009",
    "CTRL-M013-NET-010",
    "CTRL-M013-NET-011"
)

$forbiddenAuditPatterns = @(
    "BEGIN PRIVATE KEY",
    "END PRIVATE KEY",
    "POSTGRES_PASSWORD\s*=",
    "QDRANT_API_KEY\s*=",
    "GEMMA_API_KEY\s*=",
    "VLLM_API_KEY\s*=",
    "Authorization:\s*Bearer",
    "SECRET_INTERDIT_M013"
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

function Assert-M013Contains {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Content,

        [Parameter(Mandatory = $true)]
        [string] $Expected,

        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    Assert-M013Condition -Condition ($Content.Contains($Expected)) -Message $Message
}

function Resolve-M013RequiredPath {
    param(
        [Parameter(Mandatory = $false)]
        [AllowEmptyString()]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [string] $DefaultRelativePath,

        [Parameter(Mandatory = $true)]
        [string] $Label
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        $candidatePath = Join-Path $repoRoot $DefaultRelativePath
    }
    elseif ([System.IO.Path]::IsPathRooted($Path)) {
        $candidatePath = $Path
    }
    else {
        $candidatePath = Join-Path $repoRoot $Path
    }

    $resolvedRepositoryRoot = [System.IO.Path]::GetFullPath($repoRoot)
    $resolvedPath = [System.IO.Path]::GetFullPath($candidatePath)
    $repositoryPrefix = $resolvedRepositoryRoot.TrimEnd("\", "/") + [System.IO.Path]::DirectorySeparatorChar

    Assert-M013Condition `
        -Condition ($resolvedPath.StartsWith($repositoryPrefix, [System.StringComparison]::OrdinalIgnoreCase)) `
        -Message "Chemin hors dépôt interdit ($Label): $resolvedPath"
    Assert-M013Condition `
        -Condition (Test-Path -LiteralPath $resolvedPath -PathType Leaf) `
        -Message "Fichier requis absent ($Label): $resolvedPath"

    return $resolvedPath
}

function Invoke-M013ChildValidator {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ScriptRelativePath,

        [Parameter(Mandatory = $true)]
        [AllowEmptyCollection()]
        [string[]] $Arguments
    )

    $scriptPath = Resolve-M013RequiredPath -Path $ScriptRelativePath -DefaultRelativePath $ScriptRelativePath -Label $ScriptRelativePath
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & powershell `
            -NoProfile `
            -ExecutionPolicy Bypass `
            -File $scriptPath `
            @Arguments 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if ($exitCode -ne 0) {
        throw "Validation dépendante M-013 invalide ($ScriptRelativePath): $($output -join "`n")"
    }
}

function Read-M013Json {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [string] $Label
    )

    return (Get-Content -Raw -Encoding UTF8 -LiteralPath $Path).TrimStart([char] 0xFEFF) | ConvertFrom-Json
}

function Assert-M013ComposeEntrypoint {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ComposeContent
    )

    $expectedLoopbackBinding = '"127.0.0.1:${OST_EDGE_HTTPS_PORT?OST_EDGE_HTTPS_PORT requis}:8443"'
    Assert-M013Contains `
        -Content $ComposeContent `
        -Expected $expectedLoopbackBinding `
        -Message "Point d'entrée utilisateur V1 non lié à 127.0.0.1 par défaut."

    foreach ($publicBinding in @("0.0.0.0:", '"${OST_EDGE_HTTPS_PORT?OST_EDGE_HTTPS_PORT requis}:8443"', '"8443:8443"')) {
        if ($ComposeContent.Contains($publicBinding)) {
            throw "Binding public 0.0.0.0 ou implicite interdit pour le point d'entrée utilisateur: $publicBinding"
        }
    }
}

function Assert-M013FirewallPolicy {
    param(
        [Parameter(Mandatory = $true)]
        [object] $Firewall
    )

    Assert-M013Condition -Condition ($Firewall.schema_version -eq "1.0") -Message "Version de politique pare-feu Spark invalide."
    foreach ($adrId in @("ADR-007", "ADR-008", "ADR-009", "ADR-014")) {
        Assert-M013Condition -Condition (@($Firewall.architecture_decisions) -contains $adrId) -Message "ADR pare-feu Spark absente: $adrId"
    }

    Assert-M013Condition -Condition ($Firewall.spark_endpoint.host -eq "spark-inference") -Message "Endpoint Spark hors spark-inference."
    Assert-M013Condition -Condition ($Firewall.spark_endpoint.service -eq "gemma-vllm") -Message "Service Spark attendu absent: gemma-vllm."
    Assert-M013Condition -Condition ([int] $Firewall.spark_endpoint.port -gt 0) -Message "Port Spark explicite absent."
    Assert-M013Condition -Condition ($Firewall.spark_endpoint.protocol -eq "tcp") -Message "Protocole Spark attendu absent: tcp."
    Assert-M013Condition -Condition ($Firewall.spark_endpoint.auth_mode -eq "none") -Message "Mode authentification Spark attendu absent: none."
    Assert-M013Condition -Condition ($Firewall.spark_endpoint.tls_mode -eq "disabled") -Message "Mode TLS Spark attendu absent: disabled."
    Assert-M013Condition -Condition (-not [bool] $Firewall.spark_endpoint.tls_required) -Message "TLS Spark activé malgré le mode disabled."
    Assert-M013Condition -Condition (-not [bool] $Firewall.spark_endpoint.certificate_authority_required) -Message "Autorité de certificat Spark déclarée malgré le mode disabled."

    $allowedIngress = @($Firewall.allowed_ingress)
    Assert-M013Condition -Condition ($allowedIngress.Count -eq 1) -Message "Allow-list Spark invalide: une seule règle llm-gateway est attendue."
    $ingressRule = $allowedIngress[0]
    Assert-M013Condition -Condition ($ingressRule.source_host -eq "docker-local") -Message "Hôte source Spark non autorisé: $($ingressRule.source_host)"
    Assert-M013Condition -Condition ($ingressRule.source_service -eq "llm-gateway") -Message "Seul llm-gateway peut joindre Spark."
    Assert-M013Condition -Condition ($ingressRule.destination_host -eq "spark-inference") -Message "Destination Spark invalide: $($ingressRule.destination_host)"
    Assert-M013Condition -Condition ($ingressRule.destination_service -eq "gemma-vllm") -Message "Destination vLLM invalide: $($ingressRule.destination_service)"
    Assert-M013Condition -Condition ([int] $ingressRule.destination_port -eq [int] $Firewall.spark_endpoint.port) -Message "Port de destination Spark invalide: $($ingressRule.destination_port)"

    $deniedInitiators = @($Firewall.denied_initiators | ForEach-Object { [string] $_ })
    foreach ($initiator in $requiredDeniedInitiators) {
        Assert-M013Condition -Condition ($deniedInitiators -contains $initiator) -Message "Initiateur Spark refusé absent: $initiator"
    }

    Assert-M013Condition -Condition (-not [bool] $Firewall.callbacks_from_spark_allowed) -Message "Callback Spark vers docker-local interdit."
    Assert-M013Condition -Condition (-not [bool] $Firewall.browser_direct_access_allowed) -Message "Accès navigateur direct au Spark interdit."
    Assert-M013Condition -Condition (-not [bool] $Firewall.internet_ingress_allowed) -Message "Ingress Internet Spark interdit."
    Assert-M013Condition -Condition (-not [bool] $Firewall.remote_user_access.enabled) -Message "Profil distant activé alors que la V1 doit rester en 127.0.0.1 par défaut."
    Assert-M013Condition -Condition (@($Firewall.remote_user_access.allowed_bindings).Count -eq 0) -Message "Binding distant déclaré hors profil V1 validé."
}

function Assert-M013SparkStatelessTopology {
    param(
        [Parameter(Mandatory = $true)]
        [object] $Topology
    )

    $sparkHosts = @($Topology.hosts | Where-Object { $_.id -eq "spark-inference" })
    Assert-M013Condition -Condition ($sparkHosts.Count -eq 1) -Message "Hôte spark-inference absent de la topologie."
    $sparkHost = $sparkHosts[0]
    Assert-M013Condition -Condition (-not [bool] $sparkHost.business_storage_allowed) -Message "Stockage métier autorisé sur spark-inference."
    Assert-M013Condition -Condition (-not [bool] $sparkHost.durable_business_storage_allowed) -Message "Stockage métier durable autorisé sur spark-inference."

    $servicesOnSpark = @($Topology.services | Where-Object { $_.host -eq "spark-inference" })
    Assert-M013Condition -Condition ($servicesOnSpark.Count -gt 0) -Message "Aucun service Spark déclaré dans la topologie."
    foreach ($service in $servicesOnSpark) {
        Assert-M013Condition -Condition ($allowedSparkServices -contains $service.id) -Message "Service métier sur Spark interdit: $($service.id)"
        Assert-M013Condition -Condition (-not [bool] $service.business_storage) -Message "Stockage métier interdit sur Spark: $($service.id)"
        Assert-M013Condition -Condition ($service.durability -ne "durable_business") -Message "Durabilité métier interdite sur Spark: $($service.id)"
    }
}

function Assert-M013AuditReport {
    param(
        [Parameter(Mandatory = $true)]
        [string] $AuditContent
    )

    foreach ($marker in $requiredAuditMarkers) {
        Assert-M013Contains -Content $AuditContent -Expected $marker -Message "Marqueur d'audit M-013 absent: $marker"
    }

    foreach ($controlId in $requiredAuditControls) {
        Assert-M013Contains -Content $AuditContent -Expected $controlId -Message "Contrôle d'audit M-013 absent: $controlId"
    }

    foreach ($forbiddenPattern in $forbiddenAuditPatterns) {
        if ([regex]::IsMatch($AuditContent, $forbiddenPattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)) {
            throw "Secret complet interdit dans le rapport d'audit M-013: $forbiddenPattern"
        }
    }
}

function Assert-M013Traceability {
    param(
        [Parameter(Mandatory = $true)]
        [string] $MatrixContent,

        [Parameter(Mandatory = $true)]
        [string] $TestGateContent,

        [Parameter(Mandatory = $true)]
        [string] $LintGateContent
    )

    foreach ($marker in @(
        "REQ-M013-005",
        "docs/tasks/milestone_013/0005_auditer_frontiere_reseau_spark.md",
        "tests/m013/validate_m013_network_security_acceptance.ps1",
        "tests/m013/validate_m013_network_security_unit.ps1",
        "scripts/validate_m013_security.ps1",
        "docs/governance/m013_security_audit.md",
        "ADR-007",
        "ADR-008",
        "ADR-009"
    )) {
        Assert-M013Contains -Content $MatrixContent -Expected $marker -Message "Traçabilité T-005 absente: $marker"
    }

    foreach ($marker in @(
        "scripts/validate_m013_security.ps1",
        "tests/m013/validate_m013_network_security_acceptance.ps1",
        "tests/m013/validate_m013_network_security_unit.ps1"
    )) {
        Assert-M013Contains -Content $TestGateContent -Expected $marker -Message "Gate test sans sécurité réseau M-013: $marker"
    }

    Assert-M013Contains `
        -Content $LintGateContent `
        -Expected "scripts/validate_m013_security.ps1" `
        -Message "Gate lint sans validateur sécurité réseau M-013."
}

$resolvedComposePath = Resolve-M013RequiredPath -Path $ComposePath -DefaultRelativePath $defaultComposePath -Label "compose local"
$resolvedTopologyPath = Resolve-M013RequiredPath -Path $TopologyPath -DefaultRelativePath $defaultTopologyPath -Label "topologie plateforme"
$resolvedSparkFirewallPath = Resolve-M013RequiredPath -Path $SparkFirewallPath -DefaultRelativePath $defaultSparkFirewallPath -Label "pare-feu Spark"
$resolvedApplicationConfigPath = Resolve-M013RequiredPath -Path $ApplicationConfigPath -DefaultRelativePath $defaultApplicationConfigPath -Label "configuration applicative"
$resolvedAuditPath = Resolve-M013RequiredPath -Path $AuditPath -DefaultRelativePath $defaultAuditPath -Label "audit sécurité M-013"
$resolvedMatrixPath = Resolve-M013RequiredPath -Path $MatrixPath -DefaultRelativePath $defaultMatrixPath -Label "matrice"
$resolvedTestGatePath = Resolve-M013RequiredPath -Path $TestGatePath -DefaultRelativePath $defaultTestGatePath -Label "gate test"
$resolvedLintGatePath = Resolve-M013RequiredPath -Path $LintGatePath -DefaultRelativePath $defaultLintGatePath -Label "gate lint"

Invoke-M013ChildValidator -ScriptRelativePath "scripts/validate_local_compose.ps1" -Arguments @("-Path", $resolvedComposePath)
Invoke-M013ChildValidator -ScriptRelativePath "scripts/validate_platform_topology.ps1" -Arguments @("-Path", $resolvedTopologyPath)
Invoke-M013ChildValidator `
    -ScriptRelativePath "scripts/validate_network_boundary.ps1" `
    -Arguments @(
        "-ComposePath",
        $resolvedComposePath,
        "-TopologyPath",
        $resolvedTopologyPath,
        "-SparkFirewallPath",
        $resolvedSparkFirewallPath,
        "-ApplicationConfigPath",
        $resolvedApplicationConfigPath
    )

$composeContent = (Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedComposePath).TrimStart([char] 0xFEFF)
$auditContent = (Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedAuditPath).TrimStart([char] 0xFEFF)
$matrixContent = (Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedMatrixPath).TrimStart([char] 0xFEFF)
$testGateContent = (Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedTestGatePath).TrimStart([char] 0xFEFF)
$lintGateContent = (Get-Content -Raw -Encoding UTF8 -LiteralPath $resolvedLintGatePath).TrimStart([char] 0xFEFF)
$firewall = Read-M013Json -Path $resolvedSparkFirewallPath -Label "pare-feu Spark"
$topology = Read-M013Json -Path $resolvedTopologyPath -Label "topologie plateforme"

Assert-M013ComposeEntrypoint -ComposeContent $composeContent
Assert-M013FirewallPolicy -Firewall $firewall
Assert-M013SparkStatelessTopology -Topology $topology
Assert-M013AuditReport -AuditContent $auditContent
Assert-M013Traceability -MatrixContent $matrixContent -TestGateContent $testGateContent -LintGateContent $lintGateContent

Write-Host "Audit sécurité réseau M-013 valide: 127.0.0.1 par défaut, llm-gateway -> spark-inference, $($requiredAuditControls.Count) contrôle(s), ADR-014."
