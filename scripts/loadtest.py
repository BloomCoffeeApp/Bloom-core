r"""Load test for the local Bloom server: several cashiers selling at once plus screens polling.

Starts its OWN temporary server (own port, own empty database with demo data), so it never touches real data:

    backend\.venv\Scripts\python scripts\loadtest.py                 # 8 cashiers, 20 s
    backend\.venv\Scripts\python scripts\loadtest.py -c 16 -d 60     # 16 cashiers, 60 s
    backend\.venv\Scripts\python scripts\loadtest.py --url http://localhost:8000 --pin 0000   # an already running server

Prints requests, errors and p50/p95/p99 per operation and exits 1 if there is any server error (5xx / failed
request) or a p95 over the budget (`--p95-ms`, default 1500). Plain `httpx` + threads: no extra tools needed.
"""
from __future__ import annotations

import argparse
import os
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from collections import defaultdict
from pathlib import Path

import httpx

BACKEND = Path(__file__).resolve().parents[1] / "backend"
PIN = "0000"


def spawn(port: int) -> tuple[subprocess.Popen, str]:
    tmp = tempfile.mkdtemp(prefix="bloom-load-")
    env = {**os.environ, "CAFE_DATA_DIR": tmp, "CAFE_DB_PATH": str(Path(tmp) / "load.db")}
    py = BACKEND / ".venv" / "Scripts" / ("python.exe" if os.name == "nt" else "python")
    proc = subprocess.Popen([str(py if py.exists() else sys.executable), "-m", "uvicorn", "app.main:app", "--port", str(port), "--log-level", "warning"],
                            cwd=BACKEND, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            if httpx.get(f"{url}/api/health", timeout=1).status_code == 200:
                return proc, url
        except httpx.HTTPError:
            time.sleep(0.3)
    proc.kill()
    raise SystemExit("the test server did not start")


def login(c: httpx.Client, name: str = "Admin", pin: str = PIN) -> dict[str, str]:
    users = c.get("/api/auth/users").json()
    uid = next(u["id"] for u in users if u["name"] == name)
    r = c.post("/api/auth/login", json={"user_id": uid, "pin": pin})
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['token']}"}


class Stats:
    def __init__(self) -> None:
        self.lat: dict[str, list[float]] = defaultdict(list)
        self.errors: dict[str, list[str]] = defaultdict(list)
        self.lock = threading.Lock()

    def add(self, op: str, ms: float, status: int | None, note: str = "") -> None:
        with self.lock:
            self.lat[op].append(ms)
            if status is None or status >= 500:
                self.errors[op].append(f"{status} {note}"[:120])


def timed(stats: Stats, op: str, fn):
    t = time.perf_counter()
    try:
        r = fn()
        stats.add(op, (time.perf_counter() - t) * 1000, r.status_code, r.text[:80] if r.status_code >= 500 else "")
        return r
    except httpx.HTTPError as e:
        stats.add(op, (time.perf_counter() - t) * 1000, None, repr(e))
        return None


def cashier(url: str, headers: dict, products: list[dict], stop: float, stats: Stats, n: int) -> None:
    with httpx.Client(base_url=url, headers=headers, timeout=30) as c:
        i = 0
        while time.time() < stop:
            p = products[(n + i) % len(products)]
            qty = 1 + i % 3
            timed(stats, "sale", lambda: c.post("/api/sales", json={"items": [{"product_id": p["id"], "qty": qty}], "channel": "salon",
                                                                    "payments": [{"method": "debito", "amount_cents": qty * p["price_cents"]}]}))
            timed(stats, "sales list", lambda: c.get("/api/sales", params={"page_size": 20}))
            i += 1


def screens(url: str, headers: dict, stop: float, stats: Stats) -> None:
    with httpx.Client(base_url=url, headers=headers, timeout=30) as c:
        while time.time() < stop:
            timed(stats, "dashboard", lambda: c.get("/api/dashboard"))
            timed(stats, "orders board", lambda: c.get("/api/orders/board"))
            time.sleep(0.5)


def pct(values: list[float], q: float) -> float:
    return statistics.quantiles(values, n=100, method="inclusive")[min(int(q) - 1, 98)] if len(values) > 1 else (values[0] if values else 0)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-c", "--cashiers", type=int, default=8)
    ap.add_argument("-d", "--seconds", type=int, default=20)
    ap.add_argument("--p95-ms", type=float, default=1500)
    ap.add_argument("--url")
    ap.add_argument("--pin", default=PIN)
    a = ap.parse_args()

    proc = None
    if a.url:
        url = a.url.rstrip("/")
    else:
        proc, url = spawn(48990)
        r = httpx.post(f"{url}/api/setup", json={"business_name": "Carga", "admin_name": "Admin", "admin_pin": PIN, "load_demo": True}, timeout=120)
        r.raise_for_status()
    try:
        with httpx.Client(base_url=url, timeout=30) as c:
            headers = login(c, pin=a.pin)
            c.headers.update(headers)
            if c.get("/api/cash/current").json() is None:
                c.post("/api/cash/open", json={"opening_cents": 0}).raise_for_status()
            products = [p for p in c.get("/api/pos/catalog").json()["products"] if p.get("price_cents")][:12]
        stats, stop = Stats(), time.time() + a.seconds
        threads = [threading.Thread(target=cashier, args=(url, headers, products, stop, stats, n)) for n in range(a.cashiers)]
        threads += [threading.Thread(target=screens, args=(url, headers, stop, stats)) for _ in range(max(1, a.cashiers // 4))]
        print(f"{a.cashiers} cashiers + screens against {url} for {a.seconds}s ...")
        [t.start() for t in threads]
        [t.join() for t in threads]
    finally:
        if proc:
            proc.terminate()

    bad = False
    print(f"\n{'operation':14}{'requests':>10}{'errors':>8}{'p50 ms':>9}{'p95 ms':>9}{'p99 ms':>9}")
    for op, lat in sorted(stats.lat.items()):
        errs = len(stats.errors.get(op, []))
        p95 = pct(lat, 95)
        flag = " <-- over budget" if p95 > a.p95_ms else ""
        bad |= errs > 0 or p95 > a.p95_ms
        print(f"{op:14}{len(lat):>10}{errs:>8}{pct(lat, 50):>9.0f}{p95:>9.0f}{pct(lat, 99):>9.0f}{flag}")
    for op, errs in stats.errors.items():
        print(f"  errors in {op}: {errs[:3]}")
    print("\nOK" if not bad else "\nFAILED: server errors or p95 over budget")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
