"""Signed plan limits in the license token (`limits`, e.g. {"tables": 10}): parsed by the core, absent = none."""

from app.licensing import status
from app.licensing.status import parse_limits
from tests.conftest import pro_token


def test_parse_limits_only_accepts_non_negative_integers():
    assert parse_limits(None) == {}
    assert parse_limits(["tables", 3]) == {}
    assert parse_limits({"tables": 10, "x": "5", "y": -1, "z": True, "w": 2.5, "zero": 0}) == {"tables": 10, "zero": 0}


def test_status_carries_the_limits_of_a_valid_token(client):
    s = status.store_token(pro_token(limits={"tables": 4}))
    assert s.valid and s.limits == {"tables": 4}
    assert status.store_token(pro_token()).limits == {}
