$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$validatorPath = Join-Path $repoRoot "scripts/validate_m013_security.ps1"
$temporaryRoot = Join-Path $repoRoot (".tmp/ost_m013_network_security_unit_" + [System.Guid]::NewGuid().ToString("N"))

function Invoke-M013NetworkSecurityValidator {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProjectRoot
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & powershell `
            -NoProfile `
            -ExecutionPolicy Bypass `
            -File $validatorPath `
            -ComposePath (Join-Path $ProjectRoot "deploy/local-compose/compose.yaml") `
            -TopologyPath (Join-Path $ProjectRoot "app/platform/topology_registry.json") `
            -SparkFirewallPath (Join-Path $ProjectRoot "deploy/spark-firewall/network-boundary.json") `
            -ApplicationConfigPath (Join-Path $ProjectRoot "config/application.yaml") `
            -AuditPath (Join-Path $ProjectRoot "docs/governance/m013_security_audit.md") `
            -MatrixPath (Join-Path $ProjectRoot "docs/traceability/matrix.md") `
            -TestGatePath (Join-Path $ProjectRoot "scripts/test.ps1") `
            -LintGatePath (Join-Path $ProjectRoot "scripts/lint.ps1") 2>&1
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
    foreach ($relativeDirectory in @(
        "deploy/local-compose",
        "deploy/spark-firewall",
        "app/platform",
        "config",
        "docs/governance",
        "docs/traceability",
        "scripts"
    )) {
        New-Item -ItemType Directory -Path (Join-Path $projectRoot $relativeDirectory) -Force | Out-Null
    }

    Copy-Item -LiteralPath (Join-Path $repoRoot "deploy/local-compose/compose.yaml") -Destination (Join-Path $projectRoot "deploy/local-compose/compose.yaml")
    Copy-Item -LiteralPath (Join-Path $repoRoot "deploy/spark-firewall/network-boundary.json") -Destination (Join-Path $projectRoot "deploy/spark-firewall/network-boundary.json")
    Copy-Item -LiteralPath (Join-Path $repoRoot "app/platform/topology_registry.json") -Destination (Join-Path $projectRoot "app/platform/topology_registry.json")
    Copy-Item -LiteralPath (Join-Path $repoRoot "config/application.example.yaml") -Destination (Join-Path $projectRoot "config/application.yaml")
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/governance/m013_security_audit.md") -Destination (Join-Path $projectRoot "docs/governance/m013_security_audit.md")
    Copy-Item -LiteralPath (Join-Path $repoRoot "docs/traceability/matrix.md") -Destination (Join-Path $projectRoot "docs/traceability/matrix.md")
    Copy-Item -LiteralPath (Join-Path $repoRoot "scripts/test.ps1") -Destination (Join-Path $projectRoot "scripts/test.ps1")
    Copy-Item -LiteralPath (Join-Path $repoRoot "scripts/lint.ps1") -Destination (Join-Path $projectRoot "scripts/lint.ps1")

    return $projectRoot
}

function Set-FixtureText {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [scriptblock] $Mutate
    )

    $content = Get-Content -Raw -Encoding UTF8 -LiteralPath $Path
    $updatedContent = & $Mutate $content
    Set-Content -Encoding UTF8 -LiteralPath $Path -Value $updatedContent
}

function Set-FixtureJson {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [scriptblock] $Mutate
    )

    $json = Get-Content -Raw -Encoding UTF8 -LiteralPath $Path | ConvertFrom-Json
    & $Mutate $json
    $json | ConvertTo-Json -Depth 20 | Set-Content -Encoding UTF8 -LiteralPath $Path
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
    $result = Invoke-M013NetworkSecurityValidator -ProjectRoot $projectRoot
    if ($result.ExitCode -eq 0) {
        throw "Le cas RED $Name doit échouer."
    }
    Assert-OutputContains -Output $result.Output -Expected $ExpectedMessage -Message "Le cas RED $Name doit nommer la règle violée."
}

if (-not (Test-Path -LiteralPath $validatorPath -PathType Leaf)) {
    throw "Validateur sécurité réseau M-013 absent: scripts/validate_m013_security.ps1"
}

New-Item -ItemType Directory -Path $temporaryRoot | Out-Null
try {
    $validProjectRoot = New-FixtureProject -Name "valid"
    $validResult = Invoke-M013NetworkSecurityValidator -ProjectRoot $validProjectRoot
    if ($validResult.ExitCode -ne 0) {
        throw "La fixture valide T-005 doit réussir. Sortie: $($validResult.Output)"
    }
    Assert-OutputContains -Output $validResult.Output -Expected "Audit sécurité réseau M-013 valide" -Message "La fixture valide doit annoncer l'audit GREEN."

    Assert-ValidatorFails `
        -Name "vllm-public-compose" `
        -ExpectedMessage "Service Gemma/vLLM principal interdit" `
        -Mutate {
            param($projectRoot)
            $composePath = Join-Path $projectRoot "deploy/local-compose/compose.yaml"
            Set-FixtureText -Path $composePath -Mutate {
                param($content)
                $gemmaService = @'
  gemma-vllm:
    image: ostrading/gemma-vllm:0.0.0-m013
    ports:
      - "0.0.0.0:8443:8443"
    networks:
      - spark-egress
    healthcheck:
      test:
        - CMD-SHELL
        - "true"
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s

'@
                return [regex]::Replace($content, '(?m)^networks:', $gemmaService + "networks:", 1)
            }
        }

    Assert-ValidatorFails `
        -Name "qdrant-port-public" `
        -ExpectedMessage "Port publié interdit pour service interne: qdrant" `
        -Mutate {
            param($projectRoot)
            $composePath = Join-Path $projectRoot "deploy/local-compose/compose.yaml"
            Set-FixtureText -Path $composePath -Mutate {
                param($content)
                return [regex]::Replace(
                    $content,
                    '(?s)(  qdrant:\r?\n.*?image:.*?\r?\n)    expose:\r?\n      - "6333"',
                    "`$1    ports:`n      - ""0.0.0.0:6333:6333""",
                    1
                )
            }
        }

    Assert-ValidatorFails `
        -Name "point-entree-non-loopback" `
        -ExpectedMessage "Port utilisateur non lié à 127.0.0.1" `
        -Mutate {
            param($projectRoot)
            $composePath = Join-Path $projectRoot "deploy/local-compose/compose.yaml"
            Set-FixtureText -Path $composePath -Mutate {
                param($content)
                return $content.Replace('"127.0.0.1:${OST_EDGE_HTTPS_PORT?OST_EDGE_HTTPS_PORT requis}:8443"', '"192.168.1.10:${OST_EDGE_HTTPS_PORT?OST_EDGE_HTTPS_PORT requis}:8443"')
            }
        }

    Assert-ValidatorFails `
        -Name "binding-0-0-0-0" `
        -ExpectedMessage "0.0.0.0" `
        -Mutate {
            param($projectRoot)
            $composePath = Join-Path $projectRoot "deploy/local-compose/compose.yaml"
            Set-FixtureText -Path $composePath -Mutate {
                param($content)
                return $content.Replace('"127.0.0.1:${OST_EDGE_HTTPS_PORT?OST_EDGE_HTTPS_PORT requis}:8443"', '"0.0.0.0:${OST_EDGE_HTTPS_PORT?OST_EDGE_HTTPS_PORT requis}:8443"')
            }
        }

    Assert-ValidatorFails `
        -Name "navigateur-spark" `
        -ExpectedMessage "Accès navigateur direct au Spark interdit" `
        -Mutate {
            param($projectRoot)
            $firewallPath = Join-Path $projectRoot "deploy/spark-firewall/network-boundary.json"
            Set-FixtureJson -Path $firewallPath -Mutate {
                param($json)
                $json.browser_direct_access_allowed = $true
            }
        }

    Assert-ValidatorFails `
        -Name "worker-egress-spark" `
        -ExpectedMessage "Réseau spark-egress interdit pour service: worker-research" `
        -Mutate {
            param($projectRoot)
            $composePath = Join-Path $projectRoot "deploy/local-compose/compose.yaml"
            Set-FixtureText -Path $composePath -Mutate {
                param($content)
                return [regex]::Replace(
                    $content,
                    '(?s)(  worker-research:\r?\n.*?\r?\n    networks:\r?\n      - core)',
                    "`$1`n      - spark-egress",
                    1
                )
            }
        }

    Assert-ValidatorFails `
        -Name "auth-mode-absent" `
        -ExpectedMessage "Variable gateway Spark absente: GEMMA_AUTH_MODE" `
        -Mutate {
            param($projectRoot)
            $composePath = Join-Path $projectRoot "deploy/local-compose/compose.yaml"
            Set-FixtureText -Path $composePath -Mutate {
                param($content)
                return [regex]::Replace($content, '(?m)^\s{6}GEMMA_AUTH_MODE: "none"\r?\n', "", 1)
            }
        }

    Assert-ValidatorFails `
        -Name "corpus-sur-spark" `
        -ExpectedMessage "Stockage métier interdit" `
        -Mutate {
            param($projectRoot)
            $topologyPath = Join-Path $projectRoot "app/platform/topology_registry.json"
            Set-FixtureJson -Path $topologyPath -Mutate {
                param($json)
                foreach ($service in @($json.services)) {
                    if ($service.id -eq "corpus-store") {
                        $service.host = "spark-inference"
                    }
                }
            }
        }

    Assert-ValidatorFails `
        -Name "callback-spark" `
        -ExpectedMessage "Callback Spark interdit" `
        -Mutate {
            param($projectRoot)
            $firewallPath = Join-Path $projectRoot "deploy/spark-firewall/network-boundary.json"
            Set-FixtureJson -Path $firewallPath -Mutate {
                param($json)
                $json.callbacks_from_spark_allowed = $true
            }
        }

    Assert-ValidatorFails `
        -Name "secret-metier-rapport" `
        -ExpectedMessage "Secret complet interdit dans le rapport d'audit M-013" `
        -Mutate {
            param($projectRoot)
            $auditPath = Join-Path $projectRoot "docs/governance/m013_security_audit.md"
            Add-Content -Encoding UTF8 -LiteralPath $auditPath -Value "`nPOSTGRES_PASSWORD=secret-interdit"
        }

    Assert-ValidatorFails `
        -Name "bearer-rapport" `
        -ExpectedMessage "Secret complet interdit dans le rapport d'audit M-013" `
        -Mutate {
            param($projectRoot)
            $auditPath = Join-Path $projectRoot "docs/governance/m013_security_audit.md"
            Add-Content -Encoding UTF8 -LiteralPath $auditPath -Value "`nAuthorization: Bearer secret-interdit"
        }

    Assert-ValidatorFails `
        -Name "mono-hote-non-dev" `
        -ExpectedMessage "Hôte attendu absent: spark-inference" `
        -Mutate {
            param($projectRoot)
            $topologyPath = Join-Path $projectRoot "app/platform/topology_registry.json"
            Set-FixtureJson -Path $topologyPath -Mutate {
                param($json)
                $json.hosts = @($json.hosts | Where-Object { $_.id -ne "spark-inference" })
            }
        }

    Assert-ValidatorFails `
        -Name "allow-list-absente" `
        -ExpectedMessage "allowed_ingress vide" `
        -Mutate {
            param($projectRoot)
            $firewallPath = Join-Path $projectRoot "deploy/spark-firewall/network-boundary.json"
            Set-FixtureJson -Path $firewallPath -Mutate {
                param($json)
                $json.allowed_ingress = @()
            }
        }

    Assert-ValidatorFails `
        -Name "gate-test-absente" `
        -ExpectedMessage "Gate test sans sécurité réseau M-013" `
        -Mutate {
            param($projectRoot)
            $gatePath = Join-Path $projectRoot "scripts/test.ps1"
            Set-FixtureText -Path $gatePath -Mutate {
                param($content)
                return $content.Replace("tests/m013/validate_m013_network_security_acceptance.ps1", "tests/m013/network_security_missing.ps1")
            }
        }
}
finally {
    if (Test-Path -LiteralPath $temporaryRoot) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}

Write-Host "Tests unitaires sécurité réseau M-013: OK"
