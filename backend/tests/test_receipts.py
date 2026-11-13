"""Non-fiscal receipt data: legal name wins, it always adds up, and it carries the legend and operation id."""

from datetime import datetime

from app.services import receipts


def test_business_block_prefers_the_legal_name_and_keeps_the_trade_name():
    b = receipts.business_block({"name": "Café Ñandú", "legal_name": "Ñandú S.R.L.", "cuit": "30-1-2", "address": "Av. 1"})
    assert b == {"name": "Ñandú S.R.L.", "trade_name": "Café Ñandú", "cuit": "30-1-2", "address": "Av. 1"}
    assert receipts.business_block({"name": "Café"})["name"] == "Café"
    assert receipts.business_block({"name": "Café", "legal_name": "café"})["trade_name"] == ""
    assert receipts.business_block(None)["name"] == ""


def test_receipt_adds_up_and_shows_the_discount_and_operation():
    r = receipts.build_receipt(
        {"name": "Café"}, number=42, paid_at=datetime(2026, 11, 12, 15, 0), method_label="Mercado Pago",
        lines=[{"qty": 2, "name": "Latte", "size_name": "Grande", "modifiers": ["Avena"], "total_cents": 900000},
               {"qty": 1, "name": "Medialuna", "total_cents": 90000}],
        delivery_fee_cents=50000, total_cents=1000000, operation_id="1234567890", channel_label="Delivery",
    )
    assert r["number"] == "42" and r["paid_at"] == "2026-11-12T15:00:00Z" and r["legend"] == receipts.LEGEND
    assert r["discount_cents"] == 40000  # 900000 + 90000 + 50000 - 1000000
    assert r["operation_id"] == "1234567890" and r["lines"][0]["modifiers"] == ["Avena"]
    no_disc = receipts.build_receipt({}, number=1, paid_at=None, method_label="Efectivo", lines=[{"qty": 1, "name": "X", "total_cents": 100}], total_cents=100)
    assert no_disc["discount_cents"] == 0 and no_disc["paid_at"] is None and no_disc["operation_id"] is None
