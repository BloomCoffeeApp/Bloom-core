"""Online demo mode (app/demo): per-visitor sandboxes, caps, cleanup, disabled features, FROZEN guard."""

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import config, demo
from app.demo import DEMO_ADMIN, DemoSettings
from app.demo.sandboxes import build_template


@pytest.fixture(scope="module")
def template(tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("demo-template") / "template.db"
    build_template(path)
    return path


@pytest.fixture()
def make_demo(template, tmp_path, monkeypatch):
    """Returns a factory of demo apps (BLOOM_DEMO=1) sharing the prebuilt template."""
    monkeypatch.setenv("BLOOM_DEMO", "1")
    from app.auth import login_throttle

    login_throttle.reset()

    def _make(**overrides):
        from app.main import create_app

        settings = DemoSettings(root=tmp_path / "demo", users=demo.DEMO_USERS, **overrides)
        monkeypatch.setattr(DemoSettings, "from_env", classmethod(lambda cls: settings))
        app = create_app(run_lifespan=False)
        demo.manager().use_template(template)
        return app

    yield _make
    demo.uninstall()


def visitor(app) -> TestClient:
    c = TestClient(app)
    r = c.get("/")  # first page load creates the sandbox and sets the cookie
    assert "bloom_demo" in c.cookies, r.status_code
    return c


def login(c: TestClient, name: str = DEMO_ADMIN["name"], pin: str = DEMO_ADMIN["pin"]) -> dict[str, str]:
    users = c.get("/api/auth/users").json()
    uid = next(u["id"] for u in users if u["name"] == name)
    r = c.post("/api/auth/login", json={"user_id": uid, "pin": pin})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def customer_names(c: TestClient, headers) -> set[str]:
    r = c.get("/api/customers", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    rows = body["items"] if isinstance(body, dict) else body
    return {row["name"] for row in rows}


# ---------------------------------------------------------------- enabling


def test_off_by_default(monkeypatch):
    monkeypatch.delenv("BLOOM_DEMO", raising=False)
    assert demo.is_enabled() is False


def test_ignored_in_the_desktop_build(monkeypatch):
    monkeypatch.setenv("BLOOM_DEMO", "1")
    monkeypatch.setattr(config, "FROZEN", True)
    assert demo.is_enabled() is False
    from app.licensing.status import current_status
    from app.main import create_app

    app = create_app(run_lifespan=False)
    assert demo.manager() is None
    c = TestClient(app)
    assert "demo" not in c.get("/api/health").json()
    assert "bloom_demo" not in c.cookies
    assert current_status(force=True).customer != "Demo online"  # the real (test) license, not the demo one
    from app.licensing.client import server_url

    monkeypatch.setenv("BLOOM_LICENSE_SERVER", "https://licencias.example.com")
    assert server_url() == "https://licencias.example.com"
    try:
        from bloom_pro import _guard
    except ImportError:
        return
    monkeypatch.setattr(_guard, "_features_now", lambda: frozenset())  # no license on this PC
    monkeypatch.setattr(_guard, "_cache", None)
    monkeypatch.setattr(_guard, "FROZEN", True)
    assert _guard.features() == frozenset()  # BLOOM_DEMO=1 unlocks nothing in the desktop build
    monkeypatch.setattr(_guard, "_cache", None)
    monkeypatch.setattr(_guard, "FROZEN", False)
    assert _guard.features() == frozenset({"*"})  # …only on a demo server run from source


# ---------------------------------------------------------------- sandboxes


def test_template_copy_has_the_demo_data(make_demo):
    c = visitor(make_demo())
    health = c.get("/api/health").json()
    assert health["demo"]["idle_hours"] == 2.0
    assert {u["name"] for u in health["demo"]["users"]} >= {DEMO_ADMIN["name"], "Caja Demo"}
    status = c.get("/api/setup/status").json()
    assert status["needs_setup"] is False and status["business"]["name"] == "Café Demo"
    h = login(c)
    assert c.get("/api/products", headers=h).status_code == 200
    assert "Cliente Frecuente (demo)" in customer_names(c, h)


def test_two_visitors_never_see_each_other(make_demo):
    app = make_demo()
    a, b = visitor(app), visitor(app)
    assert a.cookies["bloom_demo"] != b.cookies["bloom_demo"]
    ha, hb = login(a), login(b)
    r = a.post("/api/customers", json={"name": "Solo de la visita A"}, headers=ha)
    assert r.status_code in (200, 201), r.text
    assert "Solo de la visita A" in customer_names(a, ha)
    assert "Solo de la visita A" not in customer_names(b, hb)
    # A token from one sandbox means nothing in another.
    assert b.get("/api/auth/me", headers=ha).status_code == 401
    files = sorted(p.name for p in demo.manager().sandbox_dir.glob("*.db"))
    assert files == sorted(f"{c.cookies['bloom_demo']}.db" for c in (a, b))


def test_cookie_is_random_httponly_lax_and_secure_behind_https(make_demo):
    app = make_demo(proxy_hops=1)
    c = TestClient(app)
    plain = c.get("/").headers["set-cookie"]
    assert "HttpOnly" in plain and "SameSite=Lax" in plain and "Secure" not in plain
    sid = c.cookies["bloom_demo"]
    assert len(sid) == 32 and int(sid, 16) >= 0
    secure = TestClient(app).get("/", headers={"X-Forwarded-Proto": "https"}).headers["set-cookie"]
    assert "Secure" in secure


def test_forged_cookies_cannot_escape_the_sandbox_folder(make_demo, tmp_path):
    app = make_demo()
    for forged in ("../../template", "..%2F..%2Fx", "a" * 31, "G" * 32, "/etc/passwd"):
        r = TestClient(app).get("/", headers={"Cookie": f"bloom_demo={forged}"})
        issued = r.headers["set-cookie"].split(";")[0].removeprefix("bloom_demo=")
        assert issued != forged and len(issued) == 32 and int(issued, 16) >= 0
    sandbox_dir = demo.manager().sandbox_dir
    assert all(p.parent == sandbox_dir for p in sandbox_dir.rglob("*"))
    assert not list((tmp_path / "demo").glob("*.db"))  # nothing written next to the sandboxes


def test_only_page_loads_create_sandboxes(make_demo):
    """The app fires several API calls at once: if each created a sandbox they'd race for the cookie."""
    app = make_demo()
    c = TestClient(app)
    r = c.get("/api/setup/status")
    assert r.status_code == 409 and r.json()["demo_expired"] is True
    assert demo.manager().count() == 0 and "bloom_demo" not in c.cookies
    assert c.get("/api/health").json()["demo"]["session"] is False
    r = c.get("/api/demo/new", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/" and "bloom_demo" in c.cookies
    sid = c.cookies["bloom_demo"]
    assert c.get("/api/health").json()["demo"]["session"] is True
    assert c.get("/api/setup/status").status_code == 200
    c.get("/api/demo/new", follow_redirects=False)  # already has one: kept
    assert c.cookies["bloom_demo"] == sid and demo.manager().count() == 1


def test_static_files_and_health_do_not_create_sandboxes(make_demo):
    app = make_demo()
    c = TestClient(app)
    c.get("/api/health")
    c.get("/favicon.ico")
    assert demo.manager().count() == 0 and "bloom_demo" not in c.cookies


def test_idle_sandboxes_are_deleted(make_demo):
    app = make_demo(idle_hours=1)
    c = visitor(app)
    mgr = demo.manager()
    sid = c.cookies["bloom_demo"]
    path = mgr.sandbox_dir / f"{sid}.db"
    assert path.exists()
    assert mgr.cleanup(now=time.time() + 600) == 0  # 10 min idle: kept
    assert mgr.cleanup(now=time.time() + 3601) == 1
    assert not path.exists() and mgr.count() == 0
    c.get("/")  # coming back later: a fresh sandbox under a new id
    assert c.cookies["bloom_demo"] != sid and mgr.count() == 1


def test_sandbox_in_use_is_never_deleted(make_demo):
    app = make_demo(idle_hours=1)
    c = visitor(app)
    mgr = demo.manager()
    box = mgr.get(c.cookies["bloom_demo"])
    mgr.acquire(box)
    try:
        assert mgr.cleanup(now=time.time() + 7200) == 0
    finally:
        mgr.release(box)


def test_cap_on_concurrent_sandboxes(make_demo):
    app = make_demo(max_sandboxes=2)
    visitor(app), visitor(app)
    full = TestClient(app)
    r = full.get("/")
    assert r.status_code == 503 and "Volvé en unos minutos" in r.text and r.headers["retry-after"]
    assert full.get("/api/demo/new", follow_redirects=False).status_code == 503
    assert demo.manager().count() == 2


def test_client_ip_behind_proxies(make_demo):
    from app.demo.middleware import DemoMiddleware

    mgr_app = make_demo(proxy_hops=2)
    mw = DemoMiddleware(mgr_app, demo.manager())
    scope = {"client": ("10.0.0.9", 1)}
    # visitor-sent junk, the visitor (added by the Worker), the Worker (added by Render)
    assert mw.client_ip(scope, {"x-forwarded-for": "6.6.6.6, 1.2.3.4, 172.64.0.1"}) == "1.2.3.4"
    assert mw.client_ip(scope, {}) == "10.0.0.9"
    make_demo(proxy_hops=0)
    assert DemoMiddleware(mgr_app, demo.manager()).client_ip(scope, {"x-forwarded-for": "1.2.3.4"}) == "10.0.0.9"


def test_new_sandboxes_per_ip_are_limited(make_demo):
    app = make_demo(new_per_ip_per_hour=2)
    visitor(app), visitor(app)
    r = TestClient(app).get("/")
    assert r.status_code == 429


def test_request_rate_limit(make_demo):
    app = make_demo(requests_per_minute=5)
    c = visitor(app)
    codes = [c.get("/api/setup/status").status_code for _ in range(6)]
    assert codes[-1] == 429 and 429 not in codes[:4]


def test_template_not_ready_shows_a_waiting_page(make_demo):
    app = make_demo()
    demo.manager()._template = None
    r = TestClient(app).get("/pos")
    assert r.status_code == 503 and "Preparando" in r.text


def test_pin_lockout_is_per_sandbox(make_demo):
    app = make_demo()
    a, b = visitor(app), visitor(app)
    users = a.get("/api/auth/users").json()
    uid = next(u["id"] for u in users if u["name"] == DEMO_ADMIN["name"])
    for _ in range(6):
        a.post("/api/auth/login", json={"user_id": uid, "pin": "9999"})
    assert a.post("/api/auth/login", json={"user_id": uid, "pin": DEMO_ADMIN["pin"]}).status_code == 429
    from app.auth import login_throttle

    login_throttle.reset()  # the per-IP key is shared by both TestClients; only the user key matters here
    for _ in range(6):
        a.post("/api/auth/login", json={"user_id": uid, "pin": "9999"})
    login_throttle._state = {k: v for k, v in login_throttle._state.items() if not k.endswith(":ip:testclient")}
    login(b)  # same user id, other sandbox: not locked


# ---------------------------------------------------------------- features


def test_every_pro_feature_is_on(make_demo):
    c = visitor(make_demo())
    h = login(c)
    lic = c.get("/api/license", headers=h).json()
    assert lic["valid"] is True and lic["customer"] == "Demo online" and "*" in lic["features"]
    try:
        import bloom_pro  # noqa: F401
    except ImportError:
        return
    assert c.get("/api/barista/coffees", headers=h).status_code == 200
    assert c.get("/api/reports/products", headers=h).status_code in (200, 422)


@pytest.mark.parametrize(
    ("method", "path", "fragment"),
    [
        ("POST", "/api/license/activate", "ya están activas"),
        ("POST", "/api/license/trial", "ya están activas"),
        ("GET", "/api/license/plans", "ya están activas"),
        ("POST", "/api/account/link/start", "cuenta"),
        ("POST", "/api/updates/check", "actualiza"),
        ("POST", "/api/updates/install", "actualiza"),
        ("POST", "/api/system/backups", "respaldos"),
        ("POST", "/api/system/restore", "respaldos"),
        ("GET", "/api/system/backups/x.db/download", "respaldos"),
        ("GET", "/api/system/lan-qr", "red local"),
        ("PUT", "/api/settings/network", "red local"),
        ("PUT", "/api/products/1/photo", "fotos"),
        ("POST", "/api/public-menu/online/publish", "menú online"),
        ("POST", "/api/setup", "configurada"),
    ],
)
def test_disabled_features_answer_a_friendly_403(make_demo, method, path, fragment):
    c = visitor(make_demo())
    h = login(c)
    r = c.request(method, path, headers=h, json={})
    assert r.status_code == 403, r.text
    assert fragment in r.json()["detail"] and r.json()["demo"] is True


def test_license_server_is_never_used(make_demo, monkeypatch):
    make_demo()
    monkeypatch.setenv("BLOOM_LICENSE_SERVER", "https://licencias.example.com")
    from app.licensing.client import server_url

    assert server_url() is None


def test_menu_qr_points_at_the_demo(make_demo):
    c = visitor(make_demo())
    h = login(c)
    r = c.get("/api/system/menu-qr", headers=h)
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"


def test_lifespan_builds_the_template_and_never_touches_the_shared_db(template, tmp_path, monkeypatch):
    monkeypatch.setenv("BLOOM_DEMO", "1")
    monkeypatch.setenv("BLOOM_DEMO_DIR", str(tmp_path / "live"))
    from app import migrate

    monkeypatch.setattr(migrate, "upgrade_db", lambda: pytest.fail("demo mode must not migrate the shared DB"))
    from app.main import create_app

    try:
        with TestClient(create_app()) as c:
            deadline = time.time() + 60
            while not demo.manager().template_ready and time.time() < deadline:
                time.sleep(0.2)
            assert demo.manager().template_ready
            assert c.get("/").status_code in (200, 404)
            assert "bloom_demo" in c.cookies
    finally:
        demo.uninstall()
