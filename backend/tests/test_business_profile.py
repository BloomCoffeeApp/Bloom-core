"""Business types (profiles): defaults per profile, module overrides, switching keeps data,
setup wizard choice and the order screen not receiving sales while it's hidden."""

from sqlalchemy import func, select

from app.models import Order, Product, Sale
from app.services import business_profile as svc
from tests.conftest import login


def _setup(client, **extra):
    r = client.post("/api/setup", json={"business_name": "Café", "admin_name": "Admin", "admin_pin": "0000",
                                        "load_demo": False, **extra})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_profile_defaults():
    assert all(svc._PROFILES["salon"].defaults().values())
    take = svc._resolve("takeaway", {})
    assert take["takeaway"] and not take["dine_in"] and not take["tables"] and take["orders"]
    small = svc._resolve("small", {})
    assert small["dine_in"] and not small["tables"] and not small["orders"] and not small["stations"]
    deliv = svc._resolve("delivery", {})
    assert deliv["delivery"] and deliv["takeaway"] and not deliv["dine_in"] and not deliv["barista"]
    # Every profile leaves a sales channel and only knows existing modules.
    for p in svc.PROFILES:
        mods = p.defaults()
        assert set(mods) == set(svc.MODULE_KEYS)
        assert any(mods[c] for c in svc.CHANNEL_MODULES), p.key
        assert p.off <= set(svc.MODULE_KEYS)


def test_existing_install_without_profile_shows_everything(seeded):
    client, h = seeded
    r = client.get("/api/business/modules", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["profile"] == "salon"  # demo data = café con salón
    assert all(body["modules"].values())
    assert {p["key"] for p in body["profiles"]} == {"takeaway", "small", "salon", "delivery"}
    assert {m["key"] for m in body["catalog"]} == set(svc.MODULE_KEYS)


def test_setup_wizard_stores_profile_and_overrides(client):
    h = _setup(client, profile="takeaway", modules={"purchases": True, "loyalty": False})
    body = client.get("/api/business/modules", headers=h).json()
    assert body["profile"] == "takeaway"
    assert body["overrides"] == {"purchases": True, "loyalty": False}
    assert body["modules"]["purchases"] and not body["modules"]["loyalty"] and not body["modules"]["tables"]


def test_setup_rejects_unknown_profile(client):
    r = client.post("/api/setup", json={"business_name": "Café", "admin_name": "Admin", "admin_pin": "0000",
                                        "load_demo": False, "profile": "panaderia"})
    assert r.status_code == 422
    assert client.get("/api/setup/status").json()["needs_setup"] is True


def test_overrides_only_keep_differences_and_requirements(seeded):
    client, h = seeded
    # Turning on something the profile already has is not an override; tables need dine-in.
    r = client.put("/api/business/profile", headers=h,
                   json={"profile": "takeaway", "modules": {"orders": True, "tables": True}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["overrides"] == {}
    assert body["modules"]["tables"] is False
    # Turning one module on from the hidden page also turns on what it needs.
    r = client.put("/api/business/modules/tables", headers=h, json={"enabled": True})
    assert r.status_code == 200
    body = r.json()
    assert body["profile"] == "takeaway"
    assert body["modules"]["tables"] and body["modules"]["dine_in"]
    assert body["overrides"] == {"tables": True, "dine_in": True}


def test_validation(seeded):
    client, h = seeded
    bad = client.put("/api/business/profile", headers=h, json={"profile": "nope", "modules": {}})
    assert bad.status_code == 422
    bad = client.put("/api/business/profile", headers=h, json={"profile": "salon", "modules": {"rockola": True}})
    assert bad.status_code == 422
    no_channel = {"dine_in": False, "takeaway": False, "delivery": False}
    bad = client.put("/api/business/profile", headers=h, json={"profile": "salon", "modules": no_channel})
    assert bad.status_code == 422 and "canal" in bad.json()["detail"]
    assert client.put("/api/business/modules/rockola", headers=h, json={"enabled": True}).status_code == 404
    # Not through the generic settings endpoint.
    r = client.put("/api/settings/business_profile", headers=h, json={"profile": "small", "modules": {}})
    assert r.status_code == 404


def test_only_admin_changes_it_but_everyone_reads_it(seeded):
    client, _ = seeded
    cajero = login(client, "Caja Demo", "1111")
    assert client.get("/api/business/modules", headers=cajero).status_code == 200
    r = client.put("/api/business/profile", headers=cajero, json={"profile": "small", "modules": {}})
    assert r.status_code == 403


def test_switching_profile_keeps_data(seeded, db):
    client, h = seeded
    counts = lambda: (db.scalar(select(func.count(Sale.id))), db.scalar(select(func.count(Product.id))),  # noqa: E731
                      db.scalar(select(func.count(Order.id))))
    before = counts()
    customers = client.get("/api/customers", headers=h).json()
    for profile in ("delivery", "small", "takeaway"):
        r = client.put("/api/business/profile", headers=h, json={"profile": profile, "modules": {}})
        assert r.status_code == 200
        # Hidden modules' routes keep working (hiding is UI-level).
        assert client.get("/api/customers", headers=h).json() == customers
        assert client.get("/api/orders/settings", headers=h).status_code == 200
    r = client.put("/api/business/profile", headers=h, json={"profile": "salon", "modules": {}})
    assert all(r.json()["modules"].values())
    db.expire_all()
    assert counts() == before


def _sell(client, h, db):
    pid = db.scalar(select(Product.id).where(Product.name == "Espresso"))
    return client.post("/api/sales", headers=h, json={
        "channel": "llevar", "items": [{"product_id": pid}],
        "payments": [{"method": "efectivo", "amount_cents": 220000}],
    })


def test_hidden_order_screen_receives_no_sales(seeded, db):
    client, h = seeded
    n = lambda: db.scalar(select(func.count(Order.id)))  # noqa: E731
    before = n()
    r = _sell(client, h, db)
    assert r.status_code == 200, r.text
    db.expire_all()
    assert n() == before + 1
    client.put("/api/business/profile", headers=h, json={"profile": "small", "modules": {}})  # no order screen
    r = _sell(client, h, db)
    assert r.status_code == 200, r.text
    db.expire_all()
    assert n() == before + 1


def test_catalog_is_public_for_the_setup_wizard(client):
    r = client.get("/api/business/catalog")
    assert r.status_code == 200
    body = r.json()
    assert [p["key"] for p in body["profiles"]] == ["takeaway", "small", "salon", "delivery"]
    assert "modules" not in body and "profile" not in body
