r"""Load test for the local Bloom server: several cashiers selling at once plus screens polling.

Starts its OWN temporary server (own port, own empty database with demo data), so it never touches real data:

    backend\.venv\Scripts\python scripts\loadtest.py                 # 8 cashiers, 20 s
    backend\.venv\Scripts\python scripts\loadtest.py -c 16 -d 60     # 16 cashiers, 60 s
    backend\.venv\Scripts\python scripts\loadtest.py --seed-sales 200000   # a café with two years of history (~1 min to load)
    backend\.venv\Scripts\python scripts\loadtest.py --url http://localhost:8000 --pin 0000   # an already running server

Prints requests, errors and p50/p95/p99 per operation and exits 1 if there is any server error (5xx / failed
request) or a p95 over the budget of that operation (`BUDGETS`; `--p95-ms` sets one for all). Plain `httpx` + threads: no extra tools needed.
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
# p95 budgets per operation (ms). Measured with 200,000 sales loaded (`--seed-sales 200000`), 8 cashiers + 2 screens:
# sale 164, sales list 390, orders board 353, dashboard 627. About 3x of margin so a slower PC does not trip it, but a
# lost index (the 0007 ones) or an accidental full scan does.
BUDGETS = {"sale": 500, "sales list": 1200, "orders board": 1000, "dashboard": 1800}


def spawn(port: int) -> tuple[subprocess.Popen, str]:
    tmp = tempfile.mkdtemp(prefix="bloom-load-")
    env = {**os.environ, "CAFE_DATA_DIR": tmp, "CAFE_DB_PATH": str(Path(tmp) / "load.db")}
    py = BACKEND / ".venv" / "Scripts" / ("python.exe" if os.name == "nt" else "python")
    proc = subprocess.Popen([str(py if py.exists() else sys.executable), "-m", "uvicorn", "app.main:app", "--port", str(port), "--log-level", "warning"],
                            cwd=BACKEND, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    proc.env_used = env  # type: ignore[attr-defined]  # the seeder child process needs the same database
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            if httpx.get(f"{url}/api/health", timeout=1).status_code == 200:
                return proc, url
        except httpx.HTTPError:
            time.sleep(0.3)
    proc.kill()
    raise SystemExit("the test server did not start")


def seed_sales(n: int) -> None:
    """Child-process mode (`--_seed N`): bulk-inserts N completed sales, 2 items and 1 payment each, spread over the last
    two years, straight into the database the env points at. Runs before the cashiers start, so the p95 is measured
    against a café with a long history (the indexes of migration 0007 were sized for 200k sales)."""
    import random
    from datetime import UTC, datetime, timedelta

    sys.path.insert(0, str(BACKEND))
    from sqlalchemy import func, insert, select

    from app.db import SessionLocal
    from app.models import Product, Sale, SaleItem, SalePayment

    rnd = random.Random(7)
    now = datetime.now(UTC).replace(tzinfo=None)  # the database keeps naive UTC
    with SessionLocal() as db:
        products = [(p.id, p.name, p.price_cents) for p in db.scalars(select(Product).where(Product.price_cents > 0).limit(30))]
        first = (db.scalar(select(func.max(Sale.number))) or 0) + 1
        base_id = db.scalar(select(func.max(Sale.id))) or 0
        for start in range(0, n, 5000):
            size = min(5000, n - start)
            sales, items, pays = [], [], []
            for k in range(size):
                sid = base_id + start + k + 1
                ts = now - timedelta(minutes=rnd.randint(1, 60 * 24 * 730))
                picks = [rnd.choice(products) for _ in range(2)]
                total = sum(p[2] * (1 + k % 3) for p in picks)
                sales.append(dict(id=sid, number=first + start + k, channel="salon", subtotal_cents=total, discount_cents=0, total_cents=total,
                                  cost_cents=total // 3, status="completed", ts=ts))
                items += [dict(sale_id=sid, product_id=p[0], name_snapshot=p[1], qty=1 + k % 3, unit_price_cents=p[2], total_cents=p[2] * (1 + k % 3),
                               cost_cents=p[2] // 3) for p in picks]
                pays.append(dict(sale_id=sid, method=rnd.choice(["efectivo", "debito", "transferencia"]), amount_cents=total))
            db.execute(insert(Sale), sales)
            db.execute(insert(SaleItem), items)
            db.execute(insert(SalePayment), pays)
            db.commit()
    print(f"seeded {n} sales")


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
    ap.add_argument("--p95-ms", type=float, default=None, help="one p95 budget for every operation (default: BUDGETS per operation, 1500 for the rest)")
    ap.add_argument("--url")
    ap.add_argument("--pin", default=PIN)
    ap.add_argument("--seed-sales", type=int, default=0, help="first load N completed sales into the temporary database (e.g. 200000)")
    ap.add_argument("--_seed", type=int, help=argparse.SUPPRESS)
    a = ap.parse_args()
    if a._seed:
        seed_sales(a._seed)
        return 0
    if a.seed_sales and a.url:
        raise SystemExit("--seed-sales only works with the temporary server (never loads fake sales into a running one)")

    proc = None
    if a.url:
        url = a.url.rstrip("/")
    else:
        proc, url = spawn(48990)
        r = httpx.post(f"{url}/api/setup", json={"business_name": "Carga", "admin_name": "Admin", "admin_pin": PIN, "load_demo": True}, timeout=120)
        r.raise_for_status()
        if a.seed_sales:
            print(f"seeding {a.seed_sales} sales ...")
            t0 = time.time()
            subprocess.run([sys.executable if not (BACKEND / ".venv").exists() else str(BACKEND / ".venv" / "Scripts" / "python.exe"),
                            str(Path(__file__).resolve()), "--_seed", str(a.seed_sales)], cwd=BACKEND, env=proc.env_used, check=True)  # type: ignore[attr-defined]
            print(f"  done in {time.time() - t0:.0f}s")
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
        budget = a.p95_ms if a.p95_ms is not None else BUDGETS.get(op, 1500)  # an explicit --p95-ms applies to every operation
        flag = f" <-- over budget ({budget:.0f})" if p95 > budget else ""
        bad |= errs > 0 or p95 > budget
        print(f"{op:14}{len(lat):>10}{errs:>8}{pct(lat, 50):>9.0f}{p95:>9.0f}{pct(lat, 99):>9.0f}{flag}")
    for op, errs in stats.errors.items():
        print(f"  errors in {op}: {errs[:3]}")
    print("\nOK" if not bad else "\nFAILED: server errors or p95 over budget")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
