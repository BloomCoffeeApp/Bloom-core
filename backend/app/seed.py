"""Base and demo data. ALL demo data is fictional (no real people, businesses or contacts)."""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.auth import hash_pin
from app.config import APP_DISPLAY_NAME
from app.models import (
    BrewRecipe,
    Checklist,
    ChecklistItem,
    Coffee,
    Customer,
    Equipment,
    MaintenanceTask,
    Modifier,
    ModifierGroup,
    ModifierRecipeItem,
    Notice,
    PaymentMethod,
    Product,
    ProductCategory,
    ProductModifierGroup,
    RecipeItem,
    StockCategory,
    StockItem,
    Supplier,
    User,
)
from app.services import stock as stock_svc

PAYMENT_METHODS = [
    ("efectivo", "Efectivo"),
    ("debito", "Débito"),
    ("credito", "Crédito"),
    ("transferencia", "Transferencia"),
    ("qr", "QR / Billetera"),
    ("cuenta_corriente", "Cuenta corriente"),
]
# Collected through the cafe's own Mercado Pago (services/collect.py): off until it's connected.
COLLECT_METHODS = [("mp_qr", "QR Mercado Pago"), ("mp_point", "Point (posnet)")]


def seed_base(db: Session) -> None:
    """Minimum data every install needs."""
    for i, (code, name) in enumerate(PAYMENT_METHODS):
        db.add(PaymentMethod(code=code, name=name, sort_order=i))
    for i, (code, name) in enumerate(COLLECT_METHODS, start=len(PAYMENT_METHODS)):
        db.add(PaymentMethod(code=code, name=name, sort_order=i, active=False))
    opening = Checklist(name="Apertura del local", kind="opening")
    opening.items = [
        ChecklistItem(text=t, sort_order=i)
        for i, t in enumerate(
            [
                "Encender máquina de espresso y esperar temperatura",
                "Purgar grupos y lanzar shot de prueba",
                "Calibrar molienda del día",
                "Revisar stock de leche y descartables",
                "Abrir caja con cambio",
            ]
        )
    ]
    closing = Checklist(name="Cierre del local", kind="closing")
    closing.items = [
        ChecklistItem(text=t, sort_order=i)
        for i, t in enumerate(
            [
                "Backflush con detergente",
                "Limpiar vaporizadores y bandejas",
                "Vaciar y limpiar tolva del molino",
                "Cerrar caja y hacer arqueo",
                "Guardar lácteos en heladera",
            ]
        )
    ]
    db.add_all([opening, closing])
    db.flush()


def seed_demo(db: Session, admin_id: int | None = None) -> None:
    seed_base(db)

    db.add_all(
        [
            User(name="Caja Demo", pin_hash=hash_pin("1111"), role="cajero", color="sky"),
            User(name="Barista Demo", pin_hash=hash_pin("2222"), role="barista", color="emerald"),
            User(name="Encargado Demo", pin_hash=hash_pin("3333"), role="encargado", color="violet"),
        ]
    )

    sup_cafe = Supplier(name="Tostadores del Sur (demo)", phone="11 0000-0001", payment_terms="30 días")
    sup_lact = Supplier(name="Lácteos La Pradera (demo)", phone="11 0000-0002", payment_terms="Contado")
    sup_pan = Supplier(name="Panadería El Molino (demo)", phone="11 0000-0003", payment_terms="Semanal")
    sup_desc = Supplier(name="Descartables Express (demo)", phone="11 0000-0004", payment_terms="15 días")
    db.add_all([sup_cafe, sup_lact, sup_pan, sup_desc])

    cats = {n: StockCategory(name=n) for n in ["Café", "Lácteos", "Panadería", "Descartables", "Varios"]}
    db.add_all(cats.values())
    db.flush()

    def si(name: str, cat: str, unit: str, min_qty: float, sup: Supplier, **kw) -> StockItem:
        item = StockItem(name=name, category_id=cats[cat].id, unit=unit, min_qty=min_qty, default_supplier_id=sup.id, **kw)
        db.add(item)
        return item

    cafe_blend = si("Café blend de la casa", "Café", "g", 2000, sup_cafe)
    cafe_origen = si("Café de especialidad Etiopía", "Café", "g", 1000, sup_cafe)
    leche = si("Leche entera", "Lácteos", "ml", 10000, sup_lact)
    leche_avena = si("Bebida de avena", "Lácteos", "ml", 3000, sup_lact)
    crema = si("Crema de leche", "Lácteos", "ml", 1000, sup_lact, track_expiry=True)
    medialuna = si("Medialuna de manteca", "Panadería", "u", 24, sup_pan)
    tostado_pan = si("Pan de miga (sándwich)", "Panadería", "u", 10, sup_pan)
    jamon_queso = si("Feta jamón y queso", "Varios", "u", 20, sup_pan)
    budin = si("Budín de limón (porción)", "Panadería", "u", 6, sup_pan)
    vaso_chico = si("Vaso térmico 8oz", "Descartables", "u", 100, sup_desc)
    vaso_grande = si("Vaso térmico 12oz", "Descartables", "u", 100, sup_desc)
    tapa = si("Tapa para vaso", "Descartables", "u", 150, sup_desc)
    azucar = si("Sobre de azúcar", "Varios", "u", 200, sup_desc)
    chocolate = si("Cacao en polvo", "Varios", "g", 500, sup_desc)
    db.flush()

    initial = [
        (cafe_blend, 6000, 2.8), (cafe_origen, 2000, 5.5), (leche, 24000, 0.12), (leche_avena, 6000, 0.35),
        (crema, 2000, 0.6), (medialuna, 48, 350), (tostado_pan, 30, 150), (jamon_queso, 40, 220),
        (budin, 12, 600), (vaso_chico, 400, 90), (vaso_grande, 300, 120), (tapa, 600, 40),
        (azucar, 1000, 8), (chocolate, 1500, 1.9),
    ]
    for item, qty, cost in initial:
        stock_svc.apply_movement(db, item.id, qty, "purchase", unit_cost_cents=cost * 100, reason="Stock inicial (demo)", user_id=admin_id)

    pc = {
        n: ProductCategory(name=n, color=c, icon=i, sort_order=k)
        for k, (n, c, i) in enumerate(
            [("Cafetería", "amber", "coffee"), ("Con leche", "orange", "milk"), ("Frías", "sky", "glass-water"),
             ("Panadería", "yellow", "croissant"), ("Salado", "rose", "sandwich")]
        )
    }
    pc["Panadería"].send_to_orders = False  # handed over at the counter: not for the order screen
    db.add_all(pc.values())
    db.flush()

    def prod(name: str, cat: str, price: int, recipe: list[tuple[StockItem, float]], stock_item: StockItem | None = None) -> Product:
        p = Product(name=name, category_id=pc[cat].id, price_cents=price * 100, stock_item_id=stock_item.id if stock_item else None)
        p.recipe_items = [RecipeItem(stock_item_id=s.id, qty=q) for s, q in recipe]
        db.add(p)
        return p

    espresso = prod("Espresso", "Cafetería", 2200, [(cafe_blend, 18), (azucar, 1)])
    doble = prod("Espresso doble", "Cafetería", 2800, [(cafe_blend, 20), (azucar, 1)])
    americano = prod("Americano", "Cafetería", 2600, [(cafe_blend, 18), (vaso_grande, 1), (tapa, 1)])
    filtrado = prod("Filtrado de especialidad (V60)", "Cafetería", 3800, [(cafe_origen, 15)])
    filtrado.prep_minutes = 6
    cortado = prod("Cortado", "Con leche", 2600, [(cafe_blend, 18), (leche, 40), (azucar, 1)])
    latte = prod("Latte", "Con leche", 3400, [(cafe_blend, 18), (leche, 200), (vaso_grande, 1), (tapa, 1)])
    capuccino = prod("Capuccino", "Con leche", 3400, [(cafe_blend, 18), (leche, 150), (chocolate, 2), (vaso_chico, 1), (tapa, 1)])
    flat = prod("Flat white", "Con leche", 3600, [(cafe_blend, 20), (leche, 120), (vaso_chico, 1), (tapa, 1)])
    prod("Submarino", "Con leche", 3500, [(leche, 250), (chocolate, 25)])
    prod("Iced latte", "Frías", 3900, [(cafe_blend, 18), (leche, 180), (vaso_grande, 1), (tapa, 1)])
    prod("Cold brew", "Frías", 3700, [(cafe_origen, 25), (vaso_grande, 1), (tapa, 1)])
    prod("Medialuna", "Panadería", 900, [], medialuna)
    prod("Budín de limón", "Panadería", 2500, [], budin)
    prod("Tostado de jamón y queso", "Salado", 5200, [(tostado_pan, 2), (jamon_queso, 2)]).prep_minutes = 12
    db.flush()

    leche_grp = ModifierGroup(name="Tipo de leche", min_select=0, max_select=1)
    m_avena = Modifier(name="Bebida de avena", price_delta_cents=60000, sort_order=1)
    m_avena.recipe_items = [ModifierRecipeItem(stock_item_id=leche.id, qty_delta=-200), ModifierRecipeItem(stock_item_id=leche_avena.id, qty_delta=200)]
    leche_grp.modifiers = [Modifier(name="Leche entera", price_delta_cents=0, sort_order=0), m_avena]
    extra_grp = ModifierGroup(name="Extras", min_select=0, max_select=3)
    m_shot = Modifier(name="Shot extra", price_delta_cents=80000, sort_order=0)
    m_shot.recipe_items = [ModifierRecipeItem(stock_item_id=cafe_blend.id, qty_delta=18)]
    m_crema = Modifier(name="Con crema", price_delta_cents=50000, sort_order=1)
    m_crema.recipe_items = [ModifierRecipeItem(stock_item_id=crema.id, qty_delta=30)]
    extra_grp.modifiers = [m_shot, m_crema, Modifier(name="Sin azúcar", price_delta_cents=0, sort_order=2)]
    db.add_all([leche_grp, extra_grp])
    db.flush()
    for p in (cortado, latte, capuccino, flat):
        db.add(ProductModifierGroup(product_id=p.id, group_id=leche_grp.id))
    for p in (espresso, doble, americano, cortado, latte, capuccino, flat, filtrado):
        db.add(ProductModifierGroup(product_id=p.id, group_id=extra_grp.id))

    today = date.today()
    db.add_all(
        [
            Customer(name="Cliente Frecuente (demo)", phone="11 5555-0101", birthday=today, notes="Latte con avena, sin azúcar", points=80),
            Customer(name="Oficina Ejemplo SA (demo)", phone="11 5555-0102", credit_limit_cents=5000000, notes="Paga a fin de mes"),
            Customer(name="Vecina del barrio (demo)", phone="11 5555-0103", birthday=today + timedelta(days=12), points=35),
            Customer(name="Estudiante (demo)", email="estudiante@example.com", points=12),
        ]
    )

    blend = Coffee(name="Blend de la casa", roaster="Tostadores del Sur (demo)", origin="Brasil / Colombia", process="Natural / Lavado",
                   roast_level="Medio", roast_date=today - timedelta(days=9), tasting_notes="Chocolate, avellana, caramelo", stock_item_id=cafe_blend.id,
                   flavor_notes=["chocolate", "avellana", "caramelo"], roast_point="city", menu_role="house",
                   taste_profile={"body": 4, "aroma": 3, "sweetness": 4, "bitterness": 2, "acidity": 2})
    etiopia = Coffee(name="Etiopía Yirgacheffe", roaster="Tostadores del Sur (demo)", origin="Etiopía", variety="Heirloom", process="Lavado",
                     altitude_m=2000, roast_level="Claro", roast_date=today - timedelta(days=14), tasting_notes="Floral, bergamota, durazno", stock_item_id=cafe_origen.id,
                     flavor_notes=["jazmin", "te_negro", "durazno", "limon"], roast_point="medium",
                     taste_profile={"body": 2, "aroma": 5, "sweetness": 3, "bitterness": 1, "acidity": 4})
    machine = Equipment(kind="machine", name="Máquina 2 grupos", brand="Genérica", model="E61", notes="Equipo de ejemplo")
    grinder = Equipment(kind="grinder", name="Molino espresso", brand="Genérico", model="64mm", grind_scale="1-40 numérico")
    grinder2 = Equipment(kind="grinder", name="Molino filtrado", brand="Genérico", model="Cónico", grind_scale="Clicks 0-50")
    db.add_all([blend, etiopia, machine, grinder, grinder2])
    db.flush()
    db.add_all(
        [
            MaintenanceTask(equipment_id=machine.id, name="Backflush con detergente", every_days=1),
            MaintenanceTask(equipment_id=machine.id, name="Cambio de gomas de grupo", every_shots=15000),
            MaintenanceTask(equipment_id=machine.id, name="Cambio de filtro de agua", every_days=90),
            MaintenanceTask(equipment_id=grinder.id, name="Limpieza de muelas", every_days=14),
            BrewRecipe(coffee_id=blend.id, method="espresso", name="Espresso blend 1:2", dose_g=18, yield_g=36, time_min_s=25, time_max_s=32,
                       temp_c=93, pressure_bar=9, preinfusion_s=4, grind_ref="12", is_current=True),
            BrewRecipe(coffee_id=etiopia.id, method="v60", name="V60 Etiopía 1:16", dose_g=15, yield_g=250, time_min_s=150, time_max_s=180,
                       temp_c=94, grind_ref="22 clicks",
                       steps=[{"label": "Bloom", "start_s": 0, "end_s": 45, "target_g": 40},
                              {"label": "Primer vertido", "start_s": 45, "end_s": 75, "target_g": 150},
                              {"label": "Segundo vertido", "start_s": 75, "end_s": 105, "target_g": 250},
                              {"label": "Drenado", "start_s": 105, "end_s": 165, "target_g": 250}]),
            BrewRecipe(method="aeropress", name="Aeropress clásica", dose_g=15, yield_g=200, time_min_s=110, time_max_s=130, temp_c=88,
                       steps=[{"label": "Agregar agua", "start_s": 0, "end_s": 15, "target_g": 200},
                              {"label": "Revolver", "start_s": 15, "end_s": 25},
                              {"label": "Infusión", "start_s": 25, "end_s": 90},
                              {"label": "Presionar", "start_s": 90, "end_s": 120}]),
            Notice(author_id=admin_id, title=f"¡Bienvenido a {APP_DISPLAY_NAME}!", body="Estos son datos de demostración. Podés borrarlos o editarlos desde cada módulo.", pinned=True),
        ]
    )
    db.flush()

    from app.services import expenses as expenses_svc  # demo rent, services, salaries… (fictional)

    expenses_svc.seed_demo(db, admin_id)

    try:  # Pro edition: demo drink guides for these products.
        import bloom_pro
    except ImportError:
        bloom_pro = None
    if bloom_pro:
        bloom_pro.seed_demo(db, {"espresso": espresso, "cortado": cortado, "cappuccino": capuccino, "latte": latte})

    try:  # Optional: synthetic sales history, provided by the sales module when available.
        from app.services.demo_sales import generate_demo_sales
    except ImportError:
        return
    generate_demo_sales(db, days=90)
