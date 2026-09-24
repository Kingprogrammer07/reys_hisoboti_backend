import pytest
from app import rules
from app.rules import RuleError


def test_clean_decimal_with_comma_and_dot():
    assert rules.clean_decimal("12.5") == 12.5
    assert rules.clean_decimal("12,5") == 12.5
    assert rules.clean_decimal(10) == 10.0
    with pytest.raises(RuleError):
        rules.clean_decimal("not_a_number")


def test_reys_payload_validations():
    # Valid payload
    payload = rules.reys_payload(
        tovar_turi="mandarin",
        weight="15.5",
        coefficient="1.5",
        coefficient_mode="fixed",
        box_weight=0,
        photo_count=1,
    )
    assert payload.tovar_turi == "mandarin"
    assert payload.weight == 15.5
    assert payload.coefficient == 1.5
    assert payload.net == 14.0

    # Coefficient larger than weight should raise RuleError
    with pytest.raises(RuleError, match="koeffitsient og'irlikdan katta"):
        rules.reys_payload(
            tovar_turi="mandarin",
            weight="5.0",
            coefficient="6.0",
            coefficient_mode="fixed",
        )


def test_clean_type_name():
    assert rules.clean_type_name("  Mandarin  ") == "mandarin"
    assert rules.clean_type_name("AKB-1") == "akb-1"
    with pytest.raises(RuleError, match="tovar turini kiriting"):
        rules.clean_type_name("")


def test_adjust_payload():
    adj = rules.adjust_payload(from_type="mandarin", to_type="x517", weight="12.5")
    assert adj.from_type == "mandarin"
    assert adj.to_type == "x517"
    assert adj.weight == 12.5

    with pytest.raises(RuleError, match="tovar turlari bir xil bo'lmasin"):
        rules.adjust_payload(from_type="mandarin", to_type="mandarin", weight="10")
