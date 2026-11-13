"""Non-fiscal receipt («comprobante») data: what the customer sees and downloads after paying.

Pure data, no database: callers pass the business settings and what was bought. It is *not* an invoice:
the legend says so, and «Pedir factura» tells the café to issue one (when ARCA invoicing exists the
invoice replaces this receipt). Amounts are integer cents like everywhere else.
"""

from datetime import datetime
from typing import Any

LEGEND = "Comprobante no válido como factura"


def business_block(biz: dict[str, Any] | None) -> dict[str, str]:
    """Name as it should read on the receipt: the legal name when set (trade name kept next to it)."""
    biz = biz or {}
    trade = str(biz.get("name") or "").strip()
    legal = str(biz.get("legal_name") or "").strip()
    return {
        "name": legal or trade,
        "trade_name": trade if legal and legal.lower() != trade.lower() else "",
        "cuit": str(biz.get("cuit") or "").strip(),
        "address": str(biz.get("address") or "").strip(),
    }


def build_receipt(
    biz: dict[str, Any] | None,
    *,
    number: int | str,
    paid_at: datetime | None,
    lines: list[dict[str, Any]],
    total_cents: int,
    method_label: str,
    delivery_fee_cents: int = 0,
    operation_id: str | None = None,
    channel_label: str | None = None,
) -> dict[str, Any]:
    """`lines`: {qty, name, size_name?, modifiers?, total_cents}. Whatever the lines plus the shipping
    fee exceed `total_cents` by is shown as a discount, so the receipt always adds up."""
    clean = [
        {
            "qty": ln["qty"],
            "name": str(ln["name"])[:120],
            "size_name": ln.get("size_name"),
            "modifiers": [str(m)[:60] for m in (ln.get("modifiers") or [])][:20],
            "total_cents": int(ln["total_cents"]),
        }
        for ln in lines
    ]
    gross = sum(ln["total_cents"] for ln in clean) + delivery_fee_cents
    return {
        "business": business_block(biz),
        "number": str(number),
        "paid_at": paid_at.isoformat() + "Z" if paid_at else None,
        "channel_label": channel_label,
        "lines": clean,
        "delivery_fee_cents": int(delivery_fee_cents),
        "discount_cents": max(gross - int(total_cents), 0),
        "total_cents": int(total_cents),
        "method_label": method_label,
        "operation_id": operation_id or None,
        "legend": LEGEND,
    }
