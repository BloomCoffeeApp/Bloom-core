"""Fixed sample data for the ESC/POS golden tests (same shape the services return)."""

from datetime import datetime

TS = datetime(2026, 11, 2, 15, 30)  # naive UTC = 12:30 in Buenos Aires

BUSINESS = {"name": "Café Ñandú", "address": "Av. Corrientes 1234", "phone": "11 5555-0000", "cuit": "20-12345678-9",
            "ticket_footer": "¡Gracias por tu visita!"}


def _item(name, qty, unit, total, discount=0, **kw):
    base = {"id": 1, "product_id": 1, "name_snapshot": name, "size_id": None, "size_name": None, "qty": qty,
            "unit_price_cents": unit, "discount_cents": discount, "total_cents": total, "cost_cents": 0,
            "modifiers": None, "notes": None, "promo_id": None, "promo_name": None, "promo_discount_cents": 0,
            "reward_program_id": None, "courtesy_reason": None}
    return base | kw


def sale(**kw):
    items = [
        _item("Latte", 2, 450000, 765000, 135000, size_id=3, size_name="Grande",
              modifiers=[{"id": 9, "name": "Leche de almendras", "price_delta_cents": 50000}],
              notes="Bien caliente", promo_id=4, promo_name="Happy hour", promo_discount_cents=90000),
        _item("Medialuna de manteca", 3, 90000, 270000),
        _item("Espresso", 1, 220000, 0, 220000, courtesy_reason="Premio fidelidad", reward_program_id=2),
    ]
    base = {
        "id": 10, "number": 42, "ts": TS, "status": "completed", "is_courtesy": False, "courtesy_cents": 0,
        "courtesy_reason": None, "channel": "salon", "table_label": "Mesa 4", "cash_session_id": 1, "user_id": 1,
        "user_name": "Sofía", "customer_id": 5, "customer_name": "José Pérez",
        "subtotal_cents": 1035000, "discount_cents": 150000, "points_discount_cents": 50000, "total_cents": 885000,
        "cost_cents": 0, "points_earned": 8, "points_redeemed": 100, "reward_discount_cents": 0, "notes": None,
        "void_reason": None, "voided_by": None, "voided_by_name": None, "voided_at": None, "methods": ["efectivo"],
        "items_count": 6, "items": items,
        "payments": [{"id": 1, "method": "efectivo", "amount_cents": 500000, "tendered_cents": 1000000, "change_cents": 500000},
                     {"id": 2, "method": "mercadopago", "amount_cents": 385000, "tendered_cents": None, "change_cents": 0}],
        "customer": {"id": 5, "name": "José Pérez", "phone": None, "points": 230, "balance_cents": 0},
        "change_cents": 500000, "table_tab": None,
    }
    return base | kw


def ticket(**kw):
    return {"business": BUSINESS, "sale": sale(**kw), "payment_names": {"efectivo": "Efectivo", "mercadopago": "Mercado Pago"}}


def delivery_ticket():
    """Delivery sale: 2 medialunas + $ 500,00 de envío (el total ya lo incluye)."""
    return ticket(
        channel="delivery", table_label=None, delivery_fee_cents=50000, subtotal_cents=180000, discount_cents=0,
        points_discount_cents=0, total_cents=230000, points_earned=0, points_redeemed=0, customer=None,
        items=[_item("Medialuna de manteca", 2, 90000, 180000)],
        payments=[{"id": 1, "method": "mercadopago", "amount_cents": 230000, "tendered_cents": None, "change_cents": 0}],
        change_cents=0,
    )


def courtesy_ticket():
    return ticket(
        is_courtesy=True, courtesy_cents=270000, courtesy_reason="Cumpleaños del dueño", subtotal_cents=0, discount_cents=0,
        points_discount_cents=0, total_cents=0, points_earned=0, points_redeemed=0, payments=[], customer=None,
        items=[_item("Medialuna de manteca", 3, 90000, 0, 270000)],
    )


def z_session():
    return {
        "id": 7, "status": "closed", "opened_at": datetime(2026, 11, 2, 11, 0), "opened_by": 1, "opened_by_name": "Sofía",
        "closed_at": datetime(2026, 11, 2, 23, 5), "closed_by": 2, "closed_by_name": "Martín", "opening_cents": 2000000,
        "notes": "Faltó cambio a la tarde", "sales_total_cents": 15430000, "tickets": 37, "avg_ticket_cents": 417027,
        "voided_count": 1, "voided_total_cents": 340000, "courtesy_count": 2, "courtesy_cents": 610000,
        "courtesy_cost_cents": 180000, "discounts_cents": 250000, "movements_in_cents": 500000, "movements_out_cents": 120000,
        "expected_cash_cents": 9380000, "difference_cents": -5000,
        "by_method": [
            {"method": "efectivo", "name": "Efectivo", "sales_cents": 7000000, "count": 20, "expected_cents": 9380000,
             "counted_cents": 9375000, "difference_cents": -5000},
            {"method": "mercadopago", "name": "Mercado Pago", "sales_cents": 8430000, "count": 17, "expected_cents": 8430000,
             "counted_cents": 8430000, "difference_cents": 0},
        ],
        "movements": [
            {"id": 1, "type": "in", "amount_cents": 500000, "reason": "Cambio del banco", "user_id": 1, "user_name": "Sofía", "ts": TS},
            {"id": 2, "type": "out", "amount_cents": 120000, "reason": "Compra de hielo", "user_id": 1, "user_name": "Sofía", "ts": TS},
        ],
        "by_category": [
            {"category_id": 1, "name": "Cafetería", "qty": 52.0, "total_cents": 11000000},
            {"category_id": 2, "name": "Panadería", "qty": 40.5, "total_cents": 4430000},
        ],
        "business": BUSINESS,
    }


def order():
    return {
        "id": 3, "number": 12, "source": "table", "status": "received", "channel": "salon", "table_id": 4,
        "table_label": "Mesa 4", "station_id": 1, "sale_id": None, "sale_number": None, "note": "Sin apuro, es para compartir",
        "target_minutes": 8, "created_at": TS, "received_at": TS, "started_at": None, "ready_at": None, "prepared_by_name": None,
        "items": [
            {"id": 1, "product_id": 1, "name": "Latte", "size_name": "Grande", "qty": 2, "modifiers": ["Leche de almendras", "Extra shot"],
             "notes": "Uno tibio"},
            {"id": 2, "product_id": 2, "name": "Tostado de jamón y queso", "size_name": None, "qty": 1, "modifiers": [], "notes": None},
        ],
    }
