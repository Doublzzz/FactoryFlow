"""No invented codes, inferred identities, or default quantity units."""

import pytest
from factoryflow.kernel.contracts import BusinessError
from factoryflow.modules.materials.domain.material import prepare_material, signature


def test_preparation_preserves_code_case_spaces_and_leading_zero():
    assert prepare_material({"name": " Synthetic ", "own_code": "  000a-B  "}) == {
        "name": "Synthetic",
        "own_code": "000a-B",
        "specification": None,
        "unit": None,
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("name", "  "),
        ("name", "x" * 501),
        ("name", 12),
        ("own_code", "x" * 101),
        ("specification", "x" * 1001),
        ("unit", "x" * 41),
    ],
)
def test_invalid_master_values_are_rejected_without_truncation(field, value):
    with pytest.raises(BusinessError):
        prepare_material({"name": "Synthetic"} | {field: value})


def test_source_unit_alias_is_canonical_but_unknown_never_becomes_pcs():
    assert signature({"item_name": "Synthetic", "unit": "件"})["canonical_unit"] == "PCS"
    assert signature({"item_name": "Synthetic", "unit": "unknown"})["canonical_unit"] is None
    assert signature({"description": "Guessing would be wrong"})["item_name"] is None
