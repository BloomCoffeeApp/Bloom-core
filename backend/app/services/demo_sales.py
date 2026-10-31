"""Synthetic, deterministic sales history for the demo dataset (called from seed.seed_demo).

Generates ~60–140 tickets per day with morning/afternoon peaks, closed cash sessions with
counts, loyalty points, a bit of cuenta corriente, and leaves ONE open cash session today.
Uses Core bulk inserts so it runs in ~1–2 s for 90 days.
"""

import math
import random
from collections import defaultdict
from datetime import datetime, time, timedelta
from typing import Any

from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session

from app.models import (
    CashMovement,
    CashSession,
    CashSessionCount,
    Customer,
    CustomerAccountMovement,
    LoyaltyTransaction,
    Modifier,
    ModifierGroup,
    PaymentMethod,
    Product,
    ProductModifierGroup,
    Sale,
    SaleItem,
    SalePayment,
    StockItem,
    StockMovement,
    User,
)
from app.services import recipes, settings
from app.services import stock as stock_svc
from app.services.timeutil import local_now, to_utc_naive

HOUR_WEIGHTS = {7: 2, 8: 8, 9: 10, 10: 9, 11: 6, 12: 5, 13: 5, 14: 4, 15: 5, 16: 8, 17: 9, 18: 8, 19: 6, 20: 2}
PRODUCT_WEIGHTS = {
    "Cortado": 10, "Latte": 9, "Capuccino": 7, "Medialuna": 12, "Espresso": 6, "Espresso doble": 3,
    "Americano": 5, "Flat white": 5, "Tostado de jamón y queso": 4, "Iced latte": 3, "Cold brew": 2,
    "Submarino": 3, "Budín de limón": 3, "Filtrado de especialidad (V60)": 2,
}
METHOD_WEIGHTS = {"efectivo": 34, "debito": 20, "credito": 8, "transferencia": 12, "qr": 26}
OPEN_T, CLOSE_T = time(7, 30), time(20, 30)


def _ceil_to(amount: int, step: int) -> int:
    return int(math.ceil(amount / step) * step)


def generate_demo_sales(db: Session, days: int = 90) -> None:
    if db.scalar(select(func.count(Sale.id))):
        return
    rng = random.Random(42)

    users = list(db.scalars(select(User).where(User.active.is_(True)).order_by(User.id)))
    by_role = defaultdict(list)
    for u in users:
        by_role[u.role].append(u.id)
    if not users:
        return
    cashier_ids = by_role.get("cajero") or [users[0].id]
    manager_ids = by_role.get("encargado") or by_role.get("admin") or [users[0].id]

    products = list(db.scalars(select(Product).where(Product.active.is_(True), Product.show_in_pos.is_(True))))
    methods = set(db.scalars(select(PaymentMethod.code).where(PaymentMethod.active.is_(True))))
    if not products or "efectivo" not in methods:
        return
    pay_codes = [m for m in METHOD_WEIGHTS if m in methods]
    pay_weights = [METHOD_WEIGHTS[m] for m in pay_codes]

    groups_by_product: dict[int, list[ModifierGroup]] = defaultdict(list)
    groups = {g.id: g for g in db.scalars(select(ModifierGroup))}
    mods_by_group: dict[int, list[Modifier]] = defaultdict(list)
    for m in db.scalars(select(Modifier).order_by(Modifier.sort_order)):
        mods_by_group[m.group_id].append(m)
    for pmg in db.scalars(select(ProductModifierGroup)):
        if pmg.group_id in groups:
            groups_by_product[pmg.product_id].append(groups[pmg.group_id])

    prod_weights = [PRODUCT_WEIGHTS.get(p.name, 3) for p in products]
    customers = list(db.scalars(select(Customer).where(Customer.active.is_(True)).order_by(Customer.id)))
    cc_customer = next((c for c in customers if c.credit_limit_cents > 0), None)
    loyalty = settings.get(db, "loyalty") or {}
    ppp = int(loyalty.get("pesos_per_point") or 0) if loyalty.get("enabled", True) else 0

    combo_cache: dict[tuple[int, tuple[int, ...]], tuple[int, int, dict[int, float], list[dict[str, Any]] | None]] = {}

    def combo(p: Product, mods: list[Modifier]):
        key = (p.id, tuple(m.id for m in mods))
        if key not in combo_cache:
            ids = list(key[1])
            unit = p.price_cents + sum(m.price_delta_cents for m in mods)
            cost = recipes.cost_cents(db, p, ids)
            cons = recipes.consumption(db, p, ids)
            mjson = [{"id": m.id, "name": m.name, "price_delta_cents": m.price_delta_cents} for m in mods] or None
            combo_cache[key] = (unit, cost, cons, mjson)
        return combo_cache[key]

    def pick_mods(p: Product) -> list[Modifier]:
        chosen: list[Modifier] = []
        for g in groups_by_product.get(p.id, []):
            options = [m for m in mods_by_group[g.id] if m.price_delta_cents > 0 or "Sin" in m.name]
            pool = options or mods_by_group[g.id]
            k = g.min_select if g.min_select > 0 else (1 if rng.random() < 0.14 else 0)
            k = min(k, len(pool), g.max_select or k)
            if k:
                chosen.extend(rng.sample(pool, k))
        return chosen

    stock_items = {s.id: s for s in db.scalars(select(StockItem).where(StockItem.active.is_(True)))}

    now_local = local_now().replace(tzinfo=None)
    today = now_local.date()
    first_day = today - timedelta(days=days)

    # Back-date the seed's initial stock so the movement history reads chronologically.
    first_ts = to_utc_naive(datetime.combine(first_day, time(7, 0)))
    for mv in db.scalars(select(StockMovement).where(StockMovement.reason == "Stock inicial (demo)")):
        mv.ts = first_ts

    sale_id = int(db.scalar(select(func.max(Sale.id))) or 0)
    number = int(db.scalar(select(func.max(Sale.number))) or 0)
    session_id = int(db.scalar(select(func.max(CashSession.id))) or 0)

    sessions_rows: list[dict] = []
    counts_rows: list[dict] = []
    cash_mv_rows: list[dict] = []
    sale_rows: list[dict] = []
    item_rows: list[dict] = []
    pay_rows: list[dict] = []
    loyalty_rows: list[dict] = []
    cc_rows: list[dict] = []
    points_add: dict[int, int] = defaultdict(int)
    cc_balance = cc_customer.balance_cents if cc_customer else 0
    prev_consumption: dict[int, float] = {}

    for offset in range(days, -1, -1):
        day = today - timedelta(days=offset)
        is_today = offset == 0
        wd = day.weekday()
        factor = 1.35 if wd >= 5 else (1.15 if wd == 4 else 1.0)
        n_tickets = min(int(rng.randint(58, 100) * factor), 140)

        open_local = datetime.combine(day, OPEN_T)
        close_local = datetime.combine(day, CLOSE_T)
        if is_today:
            if now_local < open_local + timedelta(minutes=45):
                open_local = now_local - timedelta(minutes=75)
            close_local = now_local - timedelta(minutes=2)

        # --- Restock in the morning (before sales) when running low ---
        restock_ts = to_utc_naive(open_local - timedelta(minutes=20))
        for sid, item in stock_items.items():
            daily = prev_consumption.get(sid, 0.0)
            if daily <= 0:
                continue
            if item.current_qty < item.min_qty * 1.5 + daily * 2:
                target = item.min_qty * 2 + daily * 7
                qty = round(target - item.current_qty, 2)
                if qty > 0:
                    mv = stock_svc.apply_movement(db, sid, qty, "purchase", unit_cost_cents=item.avg_cost_cents, ref_type="demo", reason="Reposición (demo)")
                    mv.ts = restock_ts

        # --- Cash session ---
        session_id += 1
        opening = rng.choice([2000000, 2500000, 3000000])
        opener = rng.choice(cashier_ids + manager_ids)
        sessions_rows.append(
            {
                "id": session_id, "opened_by": opener, "opened_at": to_utc_naive(open_local), "opening_cents": opening,
                "closed_by": None if is_today else rng.choice(manager_ids + cashier_ids),
                "closed_at": None if is_today else to_utc_naive(close_local + timedelta(minutes=rng.randint(5, 25))),
                "notes": None, "status": "open" if is_today else "closed",
            }
        )
        mv_in = mv_out = 0
        if not is_today or rng.random() < 0.5:
            if rng.random() < 0.35:
                amt = rng.choice([500000, 800000, 1200000, 2000000])
                mv_out += amt
                cash_mv_rows.append({"session_id": session_id, "type": "out", "amount_cents": amt, "reason": rng.choice(["Pago a proveedor en efectivo (demo)", "Compra de insumos menores (demo)", "Retiro parcial (demo)"]), "user_id": opener, "ts": to_utc_naive(open_local + timedelta(hours=rng.randint(2, 8)))})
            if rng.random() < 0.12:
                amt = rng.choice([500000, 1000000])
                mv_in += amt
                cash_mv_rows.append({"session_id": session_id, "type": "in", "amount_cents": amt, "reason": "Ingreso de cambio (demo)", "user_id": opener, "ts": to_utc_naive(open_local + timedelta(hours=rng.randint(1, 6)))})

        # --- Ticket timestamps ---
        span = (close_local - open_local).total_seconds()
        stamps: list[datetime] = []
        hours = [h for h in HOUR_WEIGHTS]
        hw = [HOUR_WEIGHTS[h] for h in hours]
        attempts = 0
        max_attempts = n_tickets if is_today else n_tickets * 4  # today: only the hours already elapsed
        while len(stamps) < n_tickets and attempts < max_attempts:
            attempts += 1
            h = rng.choices(hours, hw)[0]
            ts = datetime.combine(day, time(h, rng.randint(0, 59), rng.randint(0, 59)))
            if open_local < ts < close_local:
                stamps.append(ts)
        if is_today and len(stamps) < 5:
            stamps += [open_local + timedelta(seconds=rng.uniform(60, max(span - 60, 120))) for _ in range(5 - len(stamps))]
            stamps = [s for s in stamps if s < now_local - timedelta(minutes=1)] or [now_local - timedelta(minutes=3)]
        stamps.sort()

        method_totals: dict[str, int] = defaultdict(int)
        day_consumption: dict[int, float] = defaultdict(float)

        for ts_local in stamps:
            sale_id += 1
            number += 1
            seller = rng.choice(cashier_ids) if rng.random() < 0.7 else rng.choice(manager_ids)
            n_lines = rng.choices([1, 2, 3, 4], [55, 30, 11, 4])[0]
            subtotal = cost_total = 0
            cons_sale: dict[int, float] = defaultdict(float)
            lines = []
            for _ in range(n_lines):
                p = rng.choices(products, prod_weights)[0]
                mods = pick_mods(p)
                unit, cost, cons, mjson = combo(p, mods)
                qty = rng.choices([1, 2, 3], [70, 22, 8])[0] if p.name == "Medialuna" else (2 if rng.random() < 0.08 else 1)
                line_total = unit * qty
                subtotal += line_total
                cost_total += cost * qty
                for k, v in cons.items():
                    cons_sale[k] += v * qty
                lines.append({"sale_id": sale_id, "product_id": p.id, "name_snapshot": p.name, "qty": float(qty), "unit_price_cents": unit, "discount_cents": 0, "total_cents": line_total, "cost_cents": cost * qty, "modifiers": mjson, "notes": None})
            discount = 0
            if rng.random() < 0.03:
                discount = round(subtotal * 0.10)
                seller = rng.choice(manager_ids)
            total = subtotal - discount

            customer = rng.choice(customers) if customers and rng.random() < 0.025 else None
            voided = rng.random() < 0.004

            # Payments
            pays: list[dict] = []
            if customer is not None and customer is cc_customer and rng.random() < 0.6 and cc_balance + total <= cc_customer.credit_limit_cents:
                pays.append({"method": "cuenta_corriente", "amount_cents": total, "tendered_cents": None, "change_cents": 0})
            elif rng.random() < 0.04 and total >= 400000:
                cash_part = _ceil_to(total // 2, 100000)
                pays.append({"method": "efectivo", "amount_cents": cash_part, "tendered_cents": cash_part, "change_cents": 0})
                pays.append({"method": rng.choice(["qr", "debito"]), "amount_cents": total - cash_part, "tendered_cents": None, "change_cents": 0})
            else:
                m = rng.choices(pay_codes, pay_weights)[0]
                if m == "efectivo":
                    options = [total, _ceil_to(total, 100000), _ceil_to(total, 1000000), _ceil_to(total, 2000000)]
                    tendered = rng.choice(options)
                    pays.append({"method": m, "amount_cents": total, "tendered_cents": tendered, "change_cents": tendered - total})
                else:
                    pays.append({"method": m, "amount_cents": total, "tendered_cents": None, "change_cents": 0})
            for pay in pays:
                pay_rows.append({"sale_id": sale_id, **pay})

            earned = 0
            if not voided:
                for pay in pays:
                    method_totals[pay["method"]] += pay["amount_cents"]
                for k, v in cons_sale.items():
                    day_consumption[k] += v
                if customer is not None:
                    earned = total // (ppp * 100) if ppp > 0 else 0
                    if earned:
                        points_add[customer.id] += earned
                        loyalty_rows.append({"customer_id": customer.id, "points": earned, "reason": f"Compra ticket #{number}", "sale_id": sale_id, "ts": to_utc_naive(ts_local)})
                    cc_amt = sum(p["amount_cents"] for p in pays if p["method"] == "cuenta_corriente")
                    if cc_amt:
                        cc_balance += cc_amt
                        cc_rows.append({"customer_id": customer.id, "amount_cents": cc_amt, "type": "charge", "method": "cuenta_corriente", "sale_id": sale_id, "user_id": seller, "ts": to_utc_naive(ts_local)})

            channel = rng.choices(["salon", "llevar", "delivery"], [60, 32, 8])[0]
            ts_utc = to_utc_naive(ts_local)
            sale_rows.append(
                {
                    "id": sale_id, "number": number, "cash_session_id": session_id, "user_id": seller,
                    "customer_id": customer.id if customer else None, "channel": channel,
                    "table_label": str(rng.randint(1, 12)) if channel == "salon" and rng.random() < 0.4 else None,
                    "subtotal_cents": subtotal, "discount_cents": discount, "total_cents": total, "cost_cents": cost_total,
                    "points_earned": earned, "points_redeemed": 0, "status": "voided" if voided else "completed", "notes": None,
                    "void_reason": "Error de carga (demo)" if voided else None,
                    "voided_by": rng.choice(manager_ids) if voided else None,
                    "voided_at": ts_utc + timedelta(minutes=3) if voided else None, "ts": ts_utc,
                }
            )
            item_rows.extend(lines)

        # --- Stock: one aggregated sale movement per insumo per day ---
        day_ts = to_utc_naive(min(close_local, datetime.combine(day, CLOSE_T)))
        for sid, qty in day_consumption.items():
            if sid in stock_items and abs(qty) > 1e-9:
                mv = stock_svc.apply_movement(db, sid, -round(qty, 3), "sale", ref_type="sale", reason=f"Ventas del día {day.strftime('%d/%m')} (demo)")
                mv.ts = day_ts
        prev_consumption = dict(day_consumption)

        # --- Close the session with counts (small differences on some days) ---
        if not is_today:
            expected = dict(method_totals)
            expected["efectivo"] = opening + method_totals.get("efectivo", 0) + mv_in - mv_out
            for code, exp in expected.items():
                counted = exp
                if code == "efectivo" and rng.random() < 0.25:
                    counted = exp + rng.choice([-50000, -20000, -10000, 10000, 30000])
                counts_rows.append({"session_id": session_id, "payment_method": code, "expected_cents": exp, "counted_cents": counted})

        # Office customer settles its account on Fridays.
        if cc_customer and wd == 4 and cc_balance > 0 and not is_today:
            cc_rows.append({"customer_id": cc_customer.id, "amount_cents": -cc_balance, "type": "payment", "method": "transferencia", "sale_id": None, "user_id": manager_ids[0], "ts": to_utc_naive(close_local)})
            cc_balance = 0

    # --- Bulk insert (FK order) ---
    db.flush()
    db.execute(insert(CashSession.__table__), sessions_rows)
    if counts_rows:
        db.execute(insert(CashSessionCount.__table__), counts_rows)
    if cash_mv_rows:
        db.execute(insert(CashMovement.__table__), cash_mv_rows)
    db.execute(insert(Sale.__table__), sale_rows)
    db.execute(insert(SaleItem.__table__), item_rows)
    db.execute(insert(SalePayment.__table__), pay_rows)
    if loyalty_rows:
        db.execute(insert(LoyaltyTransaction.__table__), loyalty_rows)
    if cc_rows:
        db.execute(insert(CustomerAccountMovement.__table__), cc_rows)

    for c in customers:
        if points_add.get(c.id):
            c.points += points_add[c.id]
    if cc_customer:
        cc_customer.balance_cents = cc_balance

    # --- Leave stock at a reasonable level: 2–4x the minimum ---
    final_ts = to_utc_naive(now_local - timedelta(minutes=1))
    for sid, item in stock_items.items():
        if item.min_qty <= 0:
            continue
        target = round(item.min_qty * rng.uniform(2.0, 4.0), 0 if item.unit == "u" else 1)
        diff = round(target - item.current_qty, 3)
        if abs(diff) < 1e-6:
            continue
        if diff > 0:
            mv = stock_svc.apply_movement(db, sid, diff, "purchase", unit_cost_cents=item.avg_cost_cents, ref_type="demo", reason="Reposición de ajuste (demo)")
        else:
            mv = stock_svc.apply_movement(db, sid, diff, "adjustment", ref_type="demo", reason="Ajuste de stock (demo)")
        mv.ts = final_ts
    db.flush()
