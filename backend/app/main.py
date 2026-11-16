import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import demo
from app.config import APP_DISPLAY_NAME, APP_ID, APP_VERSION, FROZEN, FRONTEND_DIST, UPLOAD_DIR
from app.routers import (
    account,
    alerts,
    auth,
    business,
    catalog,
    channel_supplies,
    collect,
    customers,
    dashboard,
    diagnostics,
    expenses,
    license,
    orders,
    printing,
    remote_config,
    roles,
    sales,
    stock,
    system,
    team,
    updates,
    users,
)

try:  # Pro edition only: private package, absent from the public repo.
    import bloom_pro
except ImportError:
    bloom_pro = None

ROUTER_MODULES = (
    account,
    auth, license, remote_config, users, roles, business, dashboard, catalog, stock, sales, orders, customers, alerts, system, updates,
    printing, expenses, collect, channel_supplies, diagnostics, team,
)
EDITION = "pro" if bloom_pro else "free"


def _audit_recovery() -> None:
    """If this start had to restore a backup over a damaged database, leave it in the audit log."""
    from app import migrate

    if not migrate.last_recovery:
        return
    from app.db import SessionLocal
    from app.services import audit

    try:
        with SessionLocal() as db:
            audit.log(db, None, "recover", "database", None, migrate.last_recovery)
            _recovery_alert(db, migrate.last_recovery)
            db.commit()
    except Exception:
        logging.getLogger("cafeteria.migrate").exception("Could not audit the database recovery")


def _recovery_alert(db, recovery: dict) -> None:
    """A notice in the bell / Avisos for who manages backups: «Restauramos la copia del día X». It stays until read."""
    import re

    from app.models import Alert

    name = str(recovery.get("backup") or "")
    m = re.match(r"cafeteria-(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})", name)
    when = f"{m[3]}/{m[2]} a las {m[4]}:{m[5]}" if m else "más reciente"
    key = f"db_recovered:{name}:{recovery.get('at')}"[:120]
    if db.query(Alert).filter(Alert.dedupe_key == key).first() is not None:
        return
    db.add(Alert(
        type="db_recovered", severity="critical", title=f"Restauramos la copia del {when}"[:160],
        message=("La base de datos estaba dañada al abrir Bloom y se recuperó sola con una copia de seguridad: lo que se "
                 "cargó después de ese momento puede faltar. Revisá las ventas y la caja de hoy. Los archivos dañados "
                 "quedaron aparte (data.db.danada-…) por si hay que analizarlos."),
        link="/configuracion", dedupe_key=key, status="open",
    ))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from app.jobs import start_jobs, stop_jobs
    from app.migrate import upgrade_db

    if demo.manager() is not None:  # online demo: per-visitor sandboxes, no shared DB, no jobs
        demo.manager().start()
        yield
        demo.manager().shutdown()
        return
    upgrade_db()
    _audit_recovery()
    start_jobs()
    yield
    stop_jobs()


def create_app(run_lifespan: bool = True) -> FastAPI:
    app = FastAPI(
        title=APP_DISPLAY_NAME,
        version=APP_VERSION,
        lifespan=lifespan if run_lifespan else None,
        # API docs only in development: no need to publish the API surface on the LAN.
        docs_url=None if FROZEN else "/api/docs",
        redoc_url=None,
        openapi_url=None if FROZEN else "/api/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.get("/api/health")
    def health(request: Request) -> dict:
        # `app` lets the desktop launcher verify the port is really ours (not another local app).
        info = {"status": "ok", "app": APP_ID, "name": APP_DISPLAY_NAME, "version": APP_VERSION, "edition": EDITION}
        if demo_info := demo.public_info(request):
            info["demo"] = demo_info
        return info

    for module in ROUTER_MODULES:
        app.include_router(module.router)
    if bloom_pro:
        bloom_pro.register(app)

    if demo.is_enabled():  # BLOOM_DEMO=1 and not the desktop build (see app/demo)
        demo.install(app)

    app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

    if FRONTEND_DIST.exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            # Unknown API paths (e.g. a Pro endpoint in the Free edition) are a 404, never the app page.
            if path == "api" or path.startswith("api/"):
                raise HTTPException(404, "Not Found")
            # PWA: the service worker, the manifest and the shell must be revalidated on every load,
            # or tablets would keep an old version (hashed /assets/* can be cached forever).
            revalidate = {"Cache-Control": "no-cache"}
            candidate = (FRONTEND_DIST / path).resolve()
            if path and candidate.is_file() and FRONTEND_DIST.resolve() in candidate.parents:
                if path in ("manifest.webmanifest", "equipo.webmanifest"):
                    return FileResponse(candidate, media_type="application/manifest+json", headers=revalidate)
                if path in ("sw.js", "index.html"):
                    return FileResponse(candidate, headers=revalidate)
                return FileResponse(candidate)
            return FileResponse(FRONTEND_DIST / "index.html", headers=revalidate)

    return app


app = create_app()
