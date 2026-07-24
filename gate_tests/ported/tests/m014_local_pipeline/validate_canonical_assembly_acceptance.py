"""ATDD T-007 : assemblage canonique borné par les résultats de pages."""

import pytest

from app.source_processing.application.assemble_canonical_document import (
    CanonicalAssemblyPolicy,
)
from app.source_processing.domain.distribution_contracts import (
    DistributionContractError,
)
from validate_canonical_assembly_unit import _contract, _result


def test_given_pages_terminees_when_assemblage_then_ordre_et_completude_exiges() -> None:
    policy = CanonicalAssemblyPolicy()
    contract = _contract()

    ordered = policy.validate_results(
        contract=contract,
        results=(_result(3), _result(1), _result(2)),
    )

    assert tuple(result.page_number for result in ordered) == (1, 2, 3)
    with pytest.raises(DistributionContractError, match="PAGE_MANIFEST_INCOMPLETE"):
        policy.validate_results(
            contract=contract,
            results=(_result(1), _result(2)),
        )
