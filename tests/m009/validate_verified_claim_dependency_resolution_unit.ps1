$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import ast
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, sys.argv[1])

from app.contracts.evidence_claims import EvidenceRef, VerifiedClaimRef
from app.contracts.source_references import (
    ACCEPTED_CANONICAL_VERSION_STATUS,
    CanonicalSourceRef,
    SourceLocator,
    SourceLocatorValidationPolicy,
)
from app.research_answering.application.collect_evidence import CandidateEvidence
from app.research_answering.application.resolve_claim_dependencies import (
    ResolveVerifiedClaimDependenciesCommand,
    ResolveVerifiedClaimDependenciesHandler,
    VerifiedClaimDependency,
)
from app.research_answering.domain.evidence_set import EvidenceSet


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_false(condition, message):
    if condition:
        raise AssertionError(message)


def assert_raises(expected_fragment, action):
    try:
        action()
    except (AttributeError, TypeError, ValueError) as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


def hash_for(seed):
    return format(seed, "x") * 64


def source_locator_policy(*, suffix, document_id, canonical_version_id, content_hash, item_id=None):
    resolved_item_id = item_id or f"item-m009-t005-unit-{suffix.lower()}"
    canonical_source = CanonicalSourceRef(
        schema_version="1.0",
        canonical_source_id=f"CSRC-M009-T005-UNIT-{suffix}",
        document_id=document_id,
        canonical_version_id=canonical_version_id,
        source_sha256=hash_for(10),
        canonical_artifact_sha256=hash_for(11),
        page_count=7,
        accepted_at="2026-07-02T11:20:00Z",
        quality_policy_version="canonical-quality-m004-v1",
    )
    return SourceLocatorValidationPolicy(
        canonical_sources_by_version_id={canonical_source.canonical_version_id: canonical_source},
        version_statuses_by_version_id={
            canonical_source.canonical_version_id: ACCEPTED_CANONICAL_VERSION_STATUS,
        },
        resolvable_item_ids_by_version_id={
            canonical_source.canonical_version_id: {resolved_item_id: content_hash},
        },
    )


def source_locator(*, suffix, document_id, canonical_version_id, content_hash):
    return SourceLocator.from_payload(
        {
            "schema_version": "1.0",
            "canonical_version_id": canonical_version_id,
            "document_id": document_id,
            "page_pdf": 3,
            "item_id": f"item-m009-t005-unit-{suffix.lower()}",
            "bbox": [0.1, 0.2, 0.8, 0.9],
            "content_hash": content_hash,
        },
        validation_policy=source_locator_policy(
            suffix=suffix,
            document_id=document_id,
            canonical_version_id=canonical_version_id,
            content_hash=content_hash,
        ),
    )


def evidence_ref(*, suffix, content_seed, span_seed):
    document_id = f"DOC-M009-T005-UNIT-{suffix}"
    canonical_version_id = f"CVER-M009-T005-UNIT-{suffix}"
    locator = source_locator(
        suffix=suffix,
        document_id=document_id,
        canonical_version_id=canonical_version_id,
        content_hash=hash_for(content_seed),
    )
    return EvidenceRef.from_payload(
        {
            "schema_version": "1.0",
            "evidence_id": f"EVS-M009-T005-UNIT-{suffix}",
            "source_locator": locator.to_payload(),
            "relation": "SUPPORTS_DIRECTLY",
            "quoted_span_hash": hash_for(span_seed),
        },
        source_locator_validation_policy=source_locator_policy(
            suffix=suffix,
            document_id=locator.document_id,
            canonical_version_id=locator.canonical_version_id,
            content_hash=locator.content_hash,
            item_id=locator.item_id,
        ),
    )


def verified_claim_ref(*, evidence_refs, dependency_group_ids=("DEP-M009-T005-UNIT-PRIMARY",), claim_version=2):
    return VerifiedClaimRef(
        schema_version="1.0",
        claim_id="CLM-M009-T005-UNIT",
        claim_version=claim_version,
        canonical_text="Claim unitaire M-009 T-005.",
        scope={"milestone": "M-009", "task": "T-005"},
        status="VERIFIED",
        verification_id="VER-M009-T005-UNIT-CASE",
        evidence_refs=tuple(evidence_refs),
        dependency_group_ids=tuple(dependency_group_ids),
    )


def candidate(*, evidence, suffix):
    return CandidateEvidence(
        evidence_ref=evidence,
        source_text=f"Preuve unitaire M-009 T-005 {suffix}.",
        search_trace_id=f"STRC-M009T005UNIT{suffix:0>20}",
        document_id=evidence.source_locator.document_id,
        covered_obligations=("dependances",),
        evidence_polarity="NEUTRAL",
        source_kind="PRIMARY",
    )


def evidence_set_for(claim_ref):
    return EvidenceSet.assemble(
        research_case_id="RSC-M009-T005-UNIT",
        coverage_obligations=("dependances",),
        candidates=tuple(
            candidate(evidence=evidence, suffix=str(index))
            for index, evidence in enumerate(claim_ref.evidence_refs, start=1)
        ),
        verified_claim_refs=(claim_ref,),
        coverage_policy_version="deep-evidence-coverage-m009-v1",
        diversification_policy_version="deep-evidence-diversification-m009-v1",
    )


class PublicClaimEvidenceResult:
    def __init__(
        self,
        *,
        claim_status,
        public_claim_ref,
        evidence_refs,
        dependency_group_ids,
        verification_case_ids,
        independent_confirmation_count=None,
    ):
        self.claim = SimpleNamespace(
            status=claim_status,
            verified_claim_ref=public_claim_ref,
            accepted_verification_id=(
                verification_case_ids[0] if len(verification_case_ids) > 0 else None
            ),
        )
        self.evidence_refs = tuple(evidence_refs)
        self.dependency_group_ids = tuple(dependency_group_ids)
        self.verification_case_ids = tuple(verification_case_ids)
        if independent_confirmation_count is not None:
            self.independent_confirmation_count = independent_confirmation_count


class FakePublicVerifiedClaimCatalog:
    def __init__(self, result):
        self.result = result
        self.requests = []
        self.internal_reads = 0
        self.mutations = 0

    def read_evidence(self, claim_id, claim_version):
        self.requests.append((claim_id, claim_version))
        return self.result

    def groups_for_claim(self, claim_id):
        self.internal_reads += 1
        raise AssertionError("Lecture EG interne interdite.")

    def claim_for_version(self, claim_id, claim_version):
        self.internal_reads += 1
        raise AssertionError("Lecture EG interne interdite.")

    def save(self, value):
        self.mutations += 1
        raise AssertionError("Mutation EG interdite.")


primary = evidence_ref(suffix="PRIMARY", content_seed=1, span_seed=4)
secondary = evidence_ref(suffix="SECONDARY", content_seed=2, span_seed=5)
valid_claim_ref = verified_claim_ref(evidence_refs=(primary, secondary))
valid_public_result = PublicClaimEvidenceResult(
    claim_status="VERIFIED",
    public_claim_ref=valid_claim_ref,
    evidence_refs=valid_claim_ref.evidence_refs,
    dependency_group_ids=valid_claim_ref.dependency_group_ids,
    verification_case_ids=(valid_claim_ref.verification_id,),
)


def resolve_with(public_result):
    handler = ResolveVerifiedClaimDependenciesHandler(
        verified_claim_catalog=FakePublicVerifiedClaimCatalog(public_result)
    )
    return handler.resolve(
        ResolveVerifiedClaimDependenciesCommand(
            evidence_set=evidence_set_for(valid_claim_ref),
            occurred_at="2026-07-02T11:30:00Z",
        )
    )


# Un port public EG absent est refusé.
assert_raises(
    "verified_claim_catalog sans read_evidence",
    lambda: ResolveVerifiedClaimDependenciesHandler(verified_claim_catalog=object()),
)

# Un claim non vérifié ne peut pas soutenir la synthèse approfondie.
assert_raises(
    "claim non verifie",
    lambda: resolve_with(
        PublicClaimEvidenceResult(
            claim_status="REJECTED",
            public_claim_ref=None,
            evidence_refs=valid_claim_ref.evidence_refs,
            dependency_group_ids=valid_claim_ref.dependency_group_ids,
            verification_case_ids=(),
        )
    ),
)

# Une preuve du deep EvidenceSet absente des preuves publiques du claim est refusée.
assert_raises(
    "evidence_ref non attachee",
    lambda: resolve_with(
        PublicClaimEvidenceResult(
            claim_status="VERIFIED",
            public_claim_ref=valid_claim_ref,
            evidence_refs=(primary,),
            dependency_group_ids=valid_claim_ref.dependency_group_ids,
            verification_case_ids=(valid_claim_ref.verification_id,),
        )
    ),
)

# Les groupes de dépendance doivent être publics, explicites et non dupliqués.
assert_raises(
    "dependency_group absent",
    lambda: resolve_with(
        PublicClaimEvidenceResult(
            claim_status="VERIFIED",
            public_claim_ref=valid_claim_ref,
            evidence_refs=valid_claim_ref.evidence_refs,
            dependency_group_ids=(),
            verification_case_ids=(valid_claim_ref.verification_id,),
        )
    ),
)
assert_raises(
    "dependency_group duplique",
    lambda: resolve_with(
        PublicClaimEvidenceResult(
            claim_status="VERIFIED",
            public_claim_ref=valid_claim_ref,
            evidence_refs=valid_claim_ref.evidence_refs,
            dependency_group_ids=("DEP-M009-T005-UNIT-PRIMARY", "DEP-M009-T005-UNIT-PRIMARY"),
            verification_case_ids=(valid_claim_ref.verification_id,),
        )
    ),
)

# La version de claim et le cas de vérification restent obligatoires.
claim_ref_without_version = SimpleNamespace(
    claim_id=valid_claim_ref.claim_id,
    claim_version=None,
    status="VERIFIED",
    verification_id=valid_claim_ref.verification_id,
    evidence_refs=valid_claim_ref.evidence_refs,
    dependency_group_ids=valid_claim_ref.dependency_group_ids,
)
assert_raises(
    "claim_version absente",
    lambda: resolve_with(
        PublicClaimEvidenceResult(
            claim_status="VERIFIED",
            public_claim_ref=claim_ref_without_version,
            evidence_refs=valid_claim_ref.evidence_refs,
            dependency_group_ids=valid_claim_ref.dependency_group_ids,
            verification_case_ids=(valid_claim_ref.verification_id,),
        )
    ),
)
assert_raises(
    "verification_case_id absent",
    lambda: resolve_with(
        PublicClaimEvidenceResult(
            claim_status="VERIFIED",
            public_claim_ref=valid_claim_ref,
            evidence_refs=valid_claim_ref.evidence_refs,
            dependency_group_ids=valid_claim_ref.dependency_group_ids,
            verification_case_ids=(),
        )
    ),
)

# Un comptage d'indépendance fourni par le port public doit rester cohérent avec les DependencyGroup.
assert_raises(
    "confirmation independante incoherente",
    lambda: resolve_with(
        PublicClaimEvidenceResult(
            claim_status="VERIFIED",
            public_claim_ref=valid_claim_ref,
            evidence_refs=valid_claim_ref.evidence_refs,
            dependency_group_ids=valid_claim_ref.dependency_group_ids,
            verification_case_ids=(valid_claim_ref.verification_id,),
            independent_confirmation_count=2,
        )
    ),
)

# Le value object de résolution refuse aussi une incohérence locale de confirmation.
assert_raises(
    "confirmation independante incoherente",
    lambda: VerifiedClaimDependency(
        claim_id=valid_claim_ref.claim_id,
        claim_version=valid_claim_ref.claim_version,
        verification_case_id=valid_claim_ref.verification_id,
        accepted_evidence_ids=(primary.evidence_id, secondary.evidence_id),
        dependency_group_ids=valid_claim_ref.dependency_group_ids,
        independent_confirmation_count=2,
    ),
)

# Le chemin valide ne lit pas les internes EG et ne mute pas EG.
catalog = FakePublicVerifiedClaimCatalog(valid_public_result)
handler = ResolveVerifiedClaimDependenciesHandler(verified_claim_catalog=catalog)
result = handler.resolve(
    ResolveVerifiedClaimDependenciesCommand(
        evidence_set=evidence_set_for(valid_claim_ref),
        occurred_at="2026-07-02T11:35:00Z",
    )
)
assert_equal(result.dependency_set.claim_dependencies[0].independent_confirmation_count, 1, "Le compteur doit suivre les groupes.")
assert_equal(catalog.requests, [(valid_claim_ref.claim_id, valid_claim_ref.claim_version)], "La lecture doit passer par read_evidence versionne.")
assert_equal(catalog.internal_reads, 0, "Aucune lecture interne EG ne doit être appelée.")
assert_equal(catalog.mutations, 0, "Aucune mutation EG ne doit être appelée.")

# Le module RA ne doit pas importer de registre, repository ou domaine EG interne.
module_path = Path(sys.argv[1]) / "app" / "research_answering" / "application" / "resolve_claim_dependencies.py"
tree = ast.parse(module_path.read_text(encoding="utf-8"))
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        imported_modules = {alias.name for alias in node.names}
    elif isinstance(node, ast.ImportFrom) and node.module is not None:
        imported_modules = {node.module}
    else:
        imported_modules = set()
    for imported_module in imported_modules:
        forbidden_imports = {
            "app.evidence_governance.adapters",
            "app.evidence_governance.domain",
        }
        for forbidden_import in forbidden_imports:
            if imported_module == forbidden_import or imported_module.startswith(forbidden_import + "."):
                raise AssertionError(f"Import EG interne interdit dans RA: {imported_module}")

source = module_path.read_text(encoding="utf-8")
for forbidden_marker in (
    "ClaimRepository",
    "DependencyGroupRepository",
    "claim_for_id",
    "claim_for_version",
    "groups_for_claim",
    "assignment_for_claim_evidence",
    "eg_registry_table",
):
    assert_false(forbidden_marker in source, f"Lecture ou stockage EG interne interdit: {forbidden_marker}")

print("Tests unitaires T-005 dépendances de claims vérifiés M-009: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m009_verified_claim_dependency_resolution_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
try {
    $env:PYTHONIOENCODING = "utf-8"
    $output = & $pythonExecutable -B $pythonScriptPath $repoRoot 2>&1
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
    Remove-Item -LiteralPath $pythonScriptPath -Force
}

if ($LASTEXITCODE -ne 0) {
    throw ($output -join "`n")
}

Write-Host "Tests unitaires T-005 dépendances de claims vérifiés M-009: OK"
