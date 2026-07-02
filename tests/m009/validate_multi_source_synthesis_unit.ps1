$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys
from types import SimpleNamespace

sys.path.insert(0, sys.argv[1])

from app.contracts.evidence_claims import EvidenceRef, VerifiedClaimRef
from app.contracts.source_references import (
    ACCEPTED_CANONICAL_VERSION_STATUS,
    CanonicalSourceRef,
    SourceLocator,
    SourceLocatorValidationPolicy,
)
from app.research_answering.domain.answer import (
    AnswerAssertion,
    AssertionOrigin,
    AssertionOriginType,
    AssertionPublicationStatus,
    AssertionSupportDecision,
    DeepResearchReport,
    DeepResearchReportSection,
    DeepResearchReportSectionName,
)
from app.research_answering.domain.contradiction_assessment import SupportStatus
from app.research_answering.domain.evidence_set import Citation, EvidenceSet, EvidenceSetVersion


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


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


def assert_no_strategy_parameter(value, path="payload"):
    forbidden_markers = {"strategy_parameter", "kelly_fraction", "volatility_target", "candidate_strategy"}
    if isinstance(value, dict):
        for key, child in value.items():
            assert_false(
                key.lower() in forbidden_markers,
                f"Paramètre de stratégie inventé publié dans {path}.{key}.",
            )
            assert_no_strategy_parameter(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            assert_no_strategy_parameter(child, f"{path}[{index}]")


def hash_for(seed):
    return format(seed, "x") * 64


def source_locator_policy(*, suffix, content_hash):
    canonical_source = CanonicalSourceRef(
        schema_version="1.0",
        canonical_source_id=f"CSRC-M009-T008-{suffix}",
        document_id=f"DOC-M009-T008-{suffix}",
        canonical_version_id=f"CVER-M009-T008-{suffix}",
        source_sha256=hash_for(10),
        canonical_artifact_sha256=hash_for(11),
        page_count=4,
        accepted_at="2026-07-02T14:00:00Z",
        quality_policy_version="canonical-quality-m004-v1",
    )
    return SourceLocatorValidationPolicy(
        canonical_sources_by_version_id={canonical_source.canonical_version_id: canonical_source},
        version_statuses_by_version_id={
            canonical_source.canonical_version_id: ACCEPTED_CANONICAL_VERSION_STATUS,
        },
        resolvable_item_ids_by_version_id={
            canonical_source.canonical_version_id: {f"item-m009-t008-{suffix.lower()}": content_hash},
        },
    )


def source_locator(*, suffix, content_seed):
    content_hash = hash_for(content_seed)
    return SourceLocator.from_payload(
        {
            "schema_version": "1.0",
            "canonical_version_id": f"CVER-M009-T008-{suffix}",
            "document_id": f"DOC-M009-T008-{suffix}",
            "page_pdf": 1,
            "item_id": f"item-m009-t008-{suffix.lower()}",
            "bbox": [0.1, 0.2, 0.8, 0.9],
            "content_hash": content_hash,
        },
        validation_policy=source_locator_policy(suffix=suffix, content_hash=content_hash),
    )


def evidence_ref(*, suffix, content_seed, span_seed):
    locator = source_locator(suffix=suffix, content_seed=content_seed)
    return EvidenceRef.from_payload(
        {
            "schema_version": "1.0",
            "evidence_id": f"EVS-M009-T008-{suffix}",
            "source_locator": locator.to_payload(),
            "relation": "SUPPORTS_DIRECTLY",
            "quoted_span_hash": hash_for(span_seed),
        },
        source_locator_validation_policy=source_locator_policy(
            suffix=suffix,
            content_hash=locator.content_hash,
        ),
    )


def verified_claim_ref(*, suffix, evidence, canonical_text):
    return VerifiedClaimRef.from_payload(
        {
            "schema_version": "1.0",
            "claim_id": f"CLM-M009-T008-{suffix}",
            "claim_version": 1,
            "canonical_text": canonical_text,
            "scope": {
                "universe": "portefeuille convexe documente",
                "horizon": "connaissances documentaires stables",
                "metric": "synthese multi-sources",
                "frequency": "documentaire",
            },
            "status": "VERIFIED",
            "verification_id": f"VER-M009-T008-{suffix}",
            "evidence_refs": [evidence.to_payload()],
            "dependency_group_ids": [f"DEP-M009-T008-{suffix}"],
        },
        source_locator_validation_policy=source_locator_policy(
            suffix=suffix,
            content_hash=evidence.source_locator.content_hash,
        ),
    )


def evidence_set_with_claims():
    methodes = evidence_ref(suffix="METHODES", content_seed=1, span_seed=5)
    favorable = evidence_ref(suffix="FAVORABLE", content_seed=2, span_seed=6)
    unfavorable = evidence_ref(suffix="DEFAVORABLE", content_seed=3, span_seed=7)
    return EvidenceSet(
        evidence_set_id="EVS-M009-T008-REPORT",
        research_case_id="RSC-M009-T008-REPORT",
        version=EvidenceSetVersion(1),
        coverage_obligations=(
            "methodes",
            "preuves_favorables",
            "preuves_defavorables",
            "dependances",
            "limites",
            "zones_non_documentees",
        ),
        evidence_refs=(methodes, favorable, unfavorable),
        verified_claim_refs=(
            verified_claim_ref(
                suffix="METHODES",
                evidence=methodes,
                canonical_text="La methode Kelly depend explicitement de la mesure d'avantage.",
            ),
            verified_claim_ref(
                suffix="FAVORABLE",
                evidence=favorable,
                canonical_text="La preuve favorable documente une reduction du drawdown.",
            ),
            verified_claim_ref(
                suffix="DEFAVORABLE",
                evidence=unfavorable,
                canonical_text="La preuve defavorable documente une amplification du risque.",
            ),
        ),
        citations=tuple(Citation.from_evidence_ref(ref) for ref in (methodes, favorable, unfavorable)),
        coverage_policy_version="deep-evidence-coverage-m009-v1",
        diversification_policy_version="deep-evidence-diversification-m009-v1",
        sealed=True,
    )


def source_origin(claim_id):
    return AssertionOrigin(
        origin_type=AssertionOriginType.SOURCE,
        basis_refs=(claim_id,),
        rationale="Assertion issue d'un claim vérifié.",
    )


def deduction_origin(*claim_ids):
    return AssertionOrigin(
        origin_type=AssertionOriginType.DEDUCTION,
        basis_refs=claim_ids,
        rationale="Déduction qualifiée depuis plusieurs claims vérifiés.",
    )


def design_origin():
    return AssertionOrigin(
        origin_type=AssertionOriginType.DESIGN_CHOICE,
        basis_refs=("DESIGN-M009-SYNTHESIS-STRUCTURE",),
        rationale="Choix de présentation sans paramètre de stratégie.",
    )


def assertion(*, answer_id, sequence, text, origin):
    return AnswerAssertion.from_extracted(
        answer_id=answer_id,
        draft_version=1,
        sequence=sequence,
        text=text,
        origin=origin,
    )


def supported_decision(assertion, claim, citation):
    return AssertionSupportDecision(
        assertion_id=assertion.assertion_id,
        basis_refs=assertion.origin.basis_refs,
        publication_status=AssertionPublicationStatus.SUPPORTED,
        reason_code="SUPPORTED",
        public_reason="Assertion supportée par claim vérifié et citation ouvrable.",
        claim_refs=(claim,),
        citation_ids=(citation.citation_id,),
    )


def qualified_decision(assertion, reason_code):
    return AssertionSupportDecision(
        assertion_id=assertion.assertion_id,
        basis_refs=assertion.origin.basis_refs,
        publication_status=AssertionPublicationStatus.QUALIFIED,
        reason_code=reason_code,
        public_reason="Assertion qualifiée dans la synthèse approfondie.",
        claim_refs=(),
        citation_ids=(),
    )


def mandatory_sections(citation_ids):
    names = (
        DeepResearchReportSectionName.MANDATE,
        DeepResearchReportSectionName.DOCUMENTARY_SCOPE,
        DeepResearchReportSectionName.METHODS,
        DeepResearchReportSectionName.APPLICATION_CONDITIONS,
        DeepResearchReportSectionName.FAVORABLE_EVIDENCE,
        DeepResearchReportSectionName.UNFAVORABLE_EVIDENCE,
        DeepResearchReportSectionName.DEPENDENCIES,
        DeepResearchReportSectionName.CONTRADICTIONS,
        DeepResearchReportSectionName.LIMITS,
        DeepResearchReportSectionName.UNDOCUMENTED_ZONES,
        DeepResearchReportSectionName.CONCLUSION,
        DeepResearchReportSectionName.UNCERTAINTY,
    )
    return tuple(
        DeepResearchReportSection(
            section_name=name,
            content=f"{name.value}: contenu vérifiable de synthèse M-009.",
            citation_ids=citation_ids,
        )
        for name in names
    )


def valid_report():
    evidence_set = evidence_set_with_claims()
    claims = evidence_set.verified_claim_refs
    citations = evidence_set.citations
    answer_id = "ANS-M009-T008-REPORT"
    assertions = (
        assertion(
            answer_id=answer_id,
            sequence=1,
            text="Kelly depend de la mesure avantage.",
            origin=source_origin(claims[0].claim_id),
        ),
        assertion(
            answer_id=answer_id,
            sequence=2,
            text="La preuve favorable reduit le drawdown.",
            origin=source_origin(claims[1].claim_id),
        ),
        assertion(
            answer_id=answer_id,
            sequence=3,
            text="La preuve defavorable amplifie le risque.",
            origin=source_origin(claims[2].claim_id),
        ),
        assertion(
            answer_id=answer_id,
            sequence=4,
            text="La conclusion reste conditionnelle.",
            origin=deduction_origin(claims[1].claim_id, claims[2].claim_id),
        ),
        assertion(
            answer_id=answer_id,
            sequence=5,
            text="La synthese separe faits deductions choix.",
            origin=design_origin(),
        ),
    )
    decisions = (
        supported_decision(assertions[0], claims[0], citations[0]),
        supported_decision(assertions[1], claims[1], citations[1]),
        supported_decision(assertions[2], claims[2], citations[2]),
        qualified_decision(assertions[3], "DEEP_SYNTHESIS_DEDUCTION_QUALIFIED"),
        qualified_decision(assertions[4], "DEEP_SYNTHESIS_DESIGN_CHOICE"),
    )
    return DeepResearchReport(
        answer_id=answer_id,
        research_case_id=evidence_set.research_case_id,
        evidence_set_id=evidence_set.evidence_set_id,
        evidence_set_version=evidence_set.version.value,
        evidence_hash=evidence_set.evidence_hash,
        support_status=SupportStatus.PARTIALLY_SUPPORTED,
        sections=mandatory_sections(tuple(citation.citation_id for citation in citations)),
        final_assertions=assertions,
        final_assertion_decisions=decisions,
        citations=citations,
        claim_refs=claims,
        policy_version="multi-source-synthesis-m009-v1",
        published_at="2026-07-02T14:30:00Z",
    )


# Given un rapport approfondi couvre toutes les sections obligatoires.
report = valid_report()

# Then le payload distingue source, déduction, choix de conception et conserve les citations ouvrables.
payload = report.to_payload()
assert_equal(
    report.section_names,
    tuple(name for name in DeepResearchReportSectionName),
    "La synthèse doit exposer toutes les sections obligatoires dans l'ordre publié.",
)
assert_equal(report.support_status, SupportStatus.PARTIALLY_SUPPORTED, "Le statut qualifié doit être conservé.")
assert_true(report.has_origin_type(AssertionOriginType.SOURCE), "Les assertions de source doivent rester visibles.")
assert_true(report.has_origin_type(AssertionOriginType.DEDUCTION), "Les déductions doivent rester visibles.")
assert_true(report.has_origin_type(AssertionOriginType.DESIGN_CHOICE), "Les choix de conception doivent rester visibles.")
assert_true(
    len(payload["final_assertions"]) == len(report.final_assertions),
    "Les assertions finales vérifiées doivent être publiées.",
)
assert_true(
    all(citation["source_locator"] for citation in payload["citations"]),
    "Chaque citation doit rester ouvrable via SourceLocator.",
)
assert_no_strategy_parameter(payload)

# Une section obligatoire manquante rend le rapport invalide.
assert_raises(
    "section obligatoire absente: UNFAVORABLE_EVIDENCE",
    lambda: DeepResearchReport(
        **{
            **report.to_constructor_payload(),
            "sections": tuple(
                section
                for section in report.sections
                if section.section_name is not DeepResearchReportSectionName.UNFAVORABLE_EVIDENCE
            ),
        }
    ),
)

# Une assertion de source sans citation supportée ne peut pas devenir finale.
unsupported_source_decision = AssertionSupportDecision(
    assertion_id=report.final_assertions[0].assertion_id,
    basis_refs=report.final_assertions[0].origin.basis_refs,
    publication_status=AssertionPublicationStatus.QUALIFIED,
    reason_code="ANSWER_ASSERTION_UNSUPPORTED",
    public_reason="Citation absente pour une assertion de source.",
    claim_refs=(),
    citation_ids=(),
)
assert_raises(
    "assertion source finale non supportee",
    lambda: DeepResearchReport(
        **{
            **report.to_constructor_payload(),
            "final_assertion_decisions": (unsupported_source_decision,) + tuple(report.final_assertion_decisions[1:]),
        }
    ),
)

# Les preuves défavorables, contradictions et zones non documentées ne peuvent pas être vides.
for section_name, expected_fragment in (
    (DeepResearchReportSectionName.UNFAVORABLE_EVIDENCE, "preuves defavorables absentes"),
    (DeepResearchReportSectionName.CONTRADICTIONS, "contradictions absentes"),
    (DeepResearchReportSectionName.UNDOCUMENTED_ZONES, "zones non documentees absentes"),
):
    assert_raises(
        expected_fragment,
        lambda section_name=section_name: DeepResearchReportSection(
            section_name=section_name,
            content="",
            citation_ids=("CIT-M009-T008-REPORT",),
        ),
    )

# Un paramètre de stratégie inventé est refusé avant toute publication M-010.
assert_raises(
    "parametre de strategie interdit",
    lambda: DeepResearchReport.from_generated_payload(
        {
            **payload,
            "strategy_parameter": {"kelly_fraction": 0.25},
        }
    ),
)

# Un rapport SUPPORTED ne peut pas contenir de déduction ou choix de conception qualifié.
assert_raises(
    "SUPPORTED avec assertion finale non supportee",
    lambda: DeepResearchReport(
        **{
            **report.to_constructor_payload(),
            "support_status": SupportStatus.SUPPORTED,
        }
    ),
)

# Le rapport reste strictement rattaché à un EvidenceSet scellé.
assert_raises(
    "evidence_hash absent",
    lambda: DeepResearchReport(
        **{
            **report.to_constructor_payload(),
            "evidence_hash": "",
        }
    ),
)

print("Tests unitaires T-008 synthèse multi-sources traçable M-009: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m009_multi_source_synthesis_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-008 synthèse multi-sources traçable M-009: OK"
