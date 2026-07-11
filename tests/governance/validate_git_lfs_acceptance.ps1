$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$attributesPath = Join-Path $repoRoot ".gitattributes"
$expectedRule = "*.pdf filter=lfs diff=lfs merge=lfs -text"

if (-not (Test-Path -LiteralPath $attributesPath -PathType Leaf)) {
    throw "Configuration Git LFS absente: .gitattributes"
}

$attributeLines = @(Get-Content -Encoding UTF8 -LiteralPath $attributesPath)
if ($attributeLines -notcontains $expectedRule) {
    throw "Règle Git LFS PDF absente: $expectedRule"
}

$probePath = "data/corpus/acceptance-probe.pdf"
$attributes = & git -C $repoRoot check-attr filter diff merge text -- $probePath
if ($LASTEXITCODE -ne 0) {
    throw "Lecture des attributs Git impossible pour $probePath"
}

$expectedAttributes = @(
    "${probePath}: filter: lfs",
    "${probePath}: diff: lfs",
    "${probePath}: merge: lfs",
    "${probePath}: text: unset"
)

foreach ($expectedAttribute in $expectedAttributes) {
    if ($attributes -notcontains $expectedAttribute) {
        throw "Attribut Git LFS PDF invalide ou absent: $expectedAttribute"
    }
}

Write-Host "Configuration Git LFS valide: les PDF sont suivis par pointeurs LFS."
