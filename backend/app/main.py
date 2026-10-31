from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import APP_DISPLAY_NAME, APP_ID, APP_VERSION, FROZEN, FRONTEND_DIST, UPLOAD_DIR
from app.routers import (
    alerts,
    auth,
    catalog,
    customers,
    dashboard,
    license,
    sales,
    stock,
    system,
    users,
)

try:  # Pro edition only: private package, absent from the public repo.
    import bloom_pro
except ImportError:
    bloom_pro = None

ROUTER_MODULES = (auth, license, users, dashboard, catalog, stock, sales, customers, alerts, system)
EDITION = "pro" if bloom_pro else "free"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from app.jobs import start_jobs, stop_jobs
    from app.migrate import upgrade_db

    upgrade_db()
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
    def health() -> dict:
        # `app` lets the desktop launcher verify the port is really ours (not another local app).
        return {"status": "ok", "app": APP_ID, "name": APP_DISPLAY_NAME, "version": APP_VERSION, "edition": EDITION}

    for module in ROUTER_MODULES:
        app.include_router(module.router)
    if bloom_pro:
        bloom_pro.register(app)

    app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

    if FRONTEND_DIST.exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            # Unknown API paths (e.g. a Pro endpoint in the Free edition) are a 404, never the app page.
            if path == "api" or path.startswith("api/"):
                raise HTTPException(404, "Not Found")
            candidate = (FRONTEND_DIST / path).resolve()
            if path and candidate.is_file() and FRONTEND_DIST.resolve() in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(FRONTEND_DIST / "index.html")

    return app


app = create_app()
