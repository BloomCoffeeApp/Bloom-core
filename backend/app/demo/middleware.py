"""ASGI middleware for the online demo: picks the visitor's sandbox, sets the cookie, enforces caps,
rate limits and the list of features that are off in the demo."""

from __future__ import annotations

import hmac
import json
import re
from contextvars import ContextVar
from http.cookies import CookieError, SimpleCookie

import anyio

from app.demo.sandboxes import SandboxesFull, SandboxManager, TemplateNotReady, valid_sid

COOKIE = "bloom_demo"
START_PATH = "/api/demo/new"  # GET: creates a sandbox (if the cookie has none) and redirects to /
EXPIRED = "Tu demo se borró por inactividad. Recargá la página para empezar otra."
current_sandbox_id: ContextVar[str | None] = ContextVar("bloom_demo_sandbox", default=None)

_DOWNLOAD = "Descargá Bloom gratis para usarlo en tu local."
# (methods or None = any, path regex, message). Checked in order; first match wins.
DISABLED: list[tuple[frozenset[str] | None, re.Pattern[str], str]] = [
    (None, re.compile(r"^/api/license/.+"), "En la demo todas las funciones Pro ya están activas: no hace falta licencia."),
    (frozenset({"POST", "PUT", "DELETE"}), re.compile(r"^/api/license$"), "En la demo todas las funciones Pro ya están activas."),
    (frozenset({"POST", "PUT", "PATCH", "DELETE"}), re.compile(r"^/api/account(/.*)?$"), f"La demo no se vincula a ninguna cuenta. {_DOWNLOAD}"),
    (None, re.compile(r"^/api/account/preferences$"), f"La demo no se vincula a ninguna cuenta. {_DOWNLOAD}"),
    (frozenset({"POST"}), re.compile(r"^/api/updates/.+"), "La demo se actualiza sola: no hay actualizaciones para instalar."),
    (frozenset({"POST"}), re.compile(r"^/api/system/(backups|restore)$"), f"Los respaldos están desactivados en la demo. {_DOWNLOAD}"),
    (None, re.compile(r"^/api/system/backups/.+"), f"Los respaldos están desactivados en la demo. {_DOWNLOAD}"),
    (None, re.compile(r"^/api/system/lan-qr$"), f"El modo red local está desactivado en la demo. {_DOWNLOAD}"),
    (frozenset({"PUT"}), re.compile(r"^/api/settings/network$"), f"El modo red local está desactivado en la demo. {_DOWNLOAD}"),
    (frozenset({"PUT"}), re.compile(r"^/api/products/[^/]+/photo$"), f"Subir fotos está desactivado en la demo. {_DOWNLOAD}"),
    (None, re.compile(r"^/api/public-menu/online/.+"), f"El menú online está desactivado en la demo. {_DOWNLOAD}"),
    (None, re.compile(r"^/api/setup$"), "La demo ya está configurada."),
    (frozenset({"POST", "PUT"}), re.compile(r"^/api/printing/.+"), "La impresión directa está desactivada en la demo: se usa el diálogo de impresión."),
]

_FULL_HTML = """<!doctype html><html lang="es"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Demo de Bloom</title>
<meta http-equiv="refresh" content="{refresh}">
<style>body{{margin:0;min-height:100svh;display:grid;place-items:center;font-family:system-ui,sans-serif;
background:#FAF7F2;color:#3b2a1d;text-align:center;padding:1.5rem}}h1{{font-family:Georgia,serif;color:#8B5A2B}}
@media (prefers-color-scheme:dark){{body{{background:#1f1913;color:#efe7dc}}h1{{color:#C8874A}}}}</style>
<main><h1>{title}</h1><p>{body}</p></main></html>"""


def disabled_reason(method: str, path: str) -> str | None:
    for methods, pattern, message in DISABLED:
        if (methods is None or method in methods) and pattern.match(path):
            return message
    return None


def _is_document(method: str, path: str) -> bool:
    """A page of the SPA (/, /pos, /menu…), as opposed to the API or a static file."""
    if method not in ("GET", "HEAD") or path.startswith(("/api/", "/assets/", "/uploads/")) or path == "/api":
        return False
    return "." not in path.rsplit("/", 1)[-1]


def _headers(scope) -> dict[str, str]:
    return {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}


def _cookie_sid(headers: dict[str, str]) -> str | None:
    raw = headers.get("cookie")
    if not raw:
        return None
    try:
        jar = SimpleCookie(raw)
    except CookieError:
        return None
    morsel = jar.get(COOKIE)
    return morsel.value if morsel and valid_sid(morsel.value) else None


class DemoMiddleware:
    def __init__(self, app, manager: SandboxManager) -> None:
        self.app = app
        self.manager = manager

    def trusted_hops(self, headers: dict[str, str]) -> int:
        """Forwarded entries we may trust. The Worker's hop counts only with its shared secret, so a
        visitor calling the server directly can't pick their own IP with a forged X-Forwarded-For."""
        settings = self.manager.settings
        hops = settings.proxy_hops
        if hops > 1:
            sent = headers.get("x-demo-proxy-secret", "")
            if not (settings.proxy_secret and hmac.compare_digest(sent, settings.proxy_secret)):
                hops = 1
        return hops

    def client_ip(self, scope, headers: dict[str, str]) -> str:
        hops = self.trusted_hops(headers)
        if hops:
            # Each trusted proxy appends the address it saw: the visitor is `hops` entries from the
            # right. Entries further left are whatever the visitor sent and can't be trusted.
            fwd = [p.strip() for p in headers.get("x-forwarded-for", "").split(",") if p.strip()]
            if fwd:
                return fwd[-min(hops, len(fwd))]
        client = scope.get("client")
        return client[0] if client else "?"

    def is_https(self, scope, headers: dict[str, str]) -> bool:
        if scope.get("scheme") == "https":
            return True
        return bool(self.manager.settings.proxy_hops) and headers.get("x-forwarded-proto", "").split(",")[0].strip() == "https"

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        method, path = scope["method"], scope["path"]
        if path.startswith(("/assets/", "/uploads/")):
            await self.app(scope, receive, send)
            return
        headers = _headers(scope)
        if path == "/api/health":  # never creates a sandbox; tells the banner whether ours is alive
            scope.setdefault("state", {})["demo_session"] = self.manager.peek(_cookie_sid(headers))
            await self.app(scope, receive, send)
            return
        ip = self.client_ip(scope, headers)
        start = path == START_PATH
        document = start or _is_document(method, path)
        api = path.startswith("/api/") and not start

        if not self.manager.allow_request(ip):
            await self._reply(send, document, 429, "Demasiados pedidos", "Esperá un minuto y volvé a intentar.", retry=60)
            return
        if reason := disabled_reason(method, path):
            await self._json(send, 403, {"detail": reason, "demo": True})
            return

        box = self.manager.get(_cookie_sid(headers))
        new = False
        if box is None:
            if api:
                # Only a page load creates a sandbox: the app fires several API calls at once and
                # each would otherwise get its own. A missing/expired one = start over (banner).
                # 409, not 401: a 401 would log the app out and wipe its cache under the banner.
                await self._json(send, 409, {"detail": EXPIRED, "demo": True, "demo_expired": True})
                return
            if not document:
                await self.app(scope, receive, send)  # favicon, robots.txt…: no sandbox needed
                return
            if not self.manager.allow_new(ip):
                await self._reply(send, document, 429, "Ya abriste varias demos",
                                  "Abriste muchas demos seguidas desde esta conexión. Probá de nuevo en un rato.", retry=600)
                return
            try:
                box = await anyio.to_thread.run_sync(self.manager.create)
            except SandboxesFull:
                await self._reply(send, document, 503, "La demo está llena",
                                  "Hay muchas personas probando Bloom en este momento. Volvé en unos minutos.", retry=120)
                return
            except TemplateNotReady:
                await self._reply(send, document, 503, "Preparando la demo…",
                                  "Estamos cargando los datos de ejemplo. La página se recarga sola.", retry=5)
                return
            new = True

        if start:  # "Empezar de nuevo" (and dev servers that serve the page themselves)
            cookie = self._cookie(box.sid, self.is_https(scope, headers)) if new else None
            extra = [(b"location", b"/")] + ([(b"set-cookie", cookie.encode("latin-1"))] if cookie else [])
            await send({"type": "http.response.start", "status": 303,
                        "headers": [(b"cache-control", b"no-store"), (b"content-length", b"0"), *extra]})
            await send({"type": "http.response.body", "body": b""})
            return

        if path == "/api/system/menu-qr" and method == "GET":
            await self._menu_qr(scope, send, headers)
            return

        scope.setdefault("state", {})["demo_sandbox"] = box
        token = current_sandbox_id.set(box.sid)
        self.manager.acquire(box)
        cookie = self._cookie(box.sid, self.is_https(scope, headers)) if new else None

        async def send_with_cookie(message) -> None:
            if cookie and message["type"] == "http.response.start":
                message = {**message, "headers": [*message.get("headers", []), (b"set-cookie", cookie.encode("latin-1"))]}
            await send(message)

        try:
            await self.app(scope, receive, send_with_cookie)
        finally:
            self.manager.release(box)
            current_sandbox_id.reset(token)

    @staticmethod
    def _cookie(sid: str, secure: bool) -> str:
        # Session cookie (no Max-Age): it only names the sandbox; the sandbox itself expires when idle.
        return f"{COOKIE}={sid}; Path=/; HttpOnly; SameSite=Lax" + ("; Secure" if secure else "")

    async def _menu_qr(self, scope, send, headers: dict[str, str]) -> None:
        """The QR of the customer menu points at this demo's /menu (there is no local network here)."""
        from app.services.system import qr_png

        scheme = "https" if self.is_https(scope, headers) else "http"
        host = headers.get("x-forwarded-host") if self.manager.settings.proxy_hops else None
        host = (host or headers.get("host") or "localhost").split(",")[0].strip()
        body = await anyio.to_thread.run_sync(qr_png, f"{scheme}://{host}/menu")
        await self._raw(send, 200, body, b"image/png")

    async def _reply(self, send, document: bool, status: int, title: str, body: str, retry: int) -> None:
        if document:
            html = _FULL_HTML.format(refresh=max(retry, 5), title=title, body=body).encode()
            await self._raw(send, status, html, b"text/html; charset=utf-8", retry)
        else:
            await self._json(send, status, {"detail": f"{title}. {body}", "demo": True}, retry)

    async def _json(self, send, status: int, payload: dict, retry: int | None = None) -> None:
        await self._raw(send, status, json.dumps(payload, ensure_ascii=False).encode(), b"application/json", retry)

    @staticmethod
    async def _raw(send, status: int, body: bytes, content_type: bytes, retry: int | None = None) -> None:
        headers = [(b"content-type", content_type), (b"content-length", str(len(body)).encode()),
                   (b"cache-control", b"no-store"), (b"x-content-type-options", b"nosniff")]
        if retry:
            headers.append((b"retry-after", str(retry).encode()))
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": body})
