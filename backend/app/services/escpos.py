"""ESC/POS rendering for thermal receipt printers: sale ticket, Z report (cash close) and kitchen ticket
("comanda"). Pure functions: plain data in (the same dicts the HTML print documents use), bytes out.

Text goes out in a single-byte code page selected with `ESC t n` (CP858 = CP850 + €, the usual choice
for Spanish on Epson-compatible printers). Characters the code page can't print are replaced by a close
ASCII equivalent (curly quotes, dashes, ellipsis) or their accent-less letter, never dropped silently.
"""

import textwrap
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.models.base import utcnow
from app.services.timeutil import TZ, to_local

ESC = b"\x1b"
GS = b"\x1d"

# code page key -> (Python codec, ESC t n). "ascii" sends no ESC t and strips accents.
CODEPAGES: dict[str, tuple[str, int | None]] = {
    "cp858": ("cp858", 19),
    "cp850": ("cp850", 2),
    "cp437": ("cp437", 0),
    "ascii": ("ascii", None),
}
CUTS = ("partial", "full", "none")
CHANNEL_LABEL = {"salon": "Salón", "llevar": "Para llevar", "delivery": "Delivery"}
_REPLACE = {
    "“": '"', "”": '"', "„": '"', "‘": "'", "’": "'", "–": "-", "—": "-",
    "−": "-", "…": "...", " ": " ", " ": " ", "•": "*", "€": "EUR",
}


@dataclass(frozen=True)
class Layout:
    """Printer-dependent settings (from the printer's configuration)."""

    chars: int = 48  # characters per line in the normal font (80 mm ≈ 48, 58 mm ≈ 32)
    codepage: str = "cp858"
    cut: str = "partial"
    feed_lines: int = 4  # blank lines before cutting (paper between the print head and the cutter)


# ---------------------------------------------------------------- formatting (same as the UI: es-AR)


def money(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    whole, frac = divmod(abs(int(cents)), 100)
    return f"{sign}$ {whole:,}".replace(",", ".") + f",{frac:02d}"


def number(n: float, digits: int = 2) -> str:
    s = f"{n:,.{digits}f}".rstrip("0").rstrip(".") if digits else f"{n:,.0f}"
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def date_time(v: datetime | str | None) -> str:
    if v is None:
        return "-"
    if isinstance(v, str):
        v = datetime.fromisoformat(v)
    local = to_local(v) if v.tzinfo is None else v.astimezone(TZ)
    return local.strftime("%d/%m/%Y %H:%M")


def time_of(v: datetime | str | None) -> str:
    return date_time(v)[-5:] if v is not None else "-"


# ---------------------------------------------------------------- document builder


def _encodable(ch: str, codec: str) -> bool:
    try:
        ch.encode(codec)
        return True
    except UnicodeEncodeError:
        return False


class Doc:
    def __init__(self, layout: Layout) -> None:
        if layout.codepage not in CODEPAGES:
            raise ValueError(f"Código de página desconocido: {layout.codepage}")
        self.layout = layout
        self.width = max(16, int(layout.chars))
        self.codec, n = CODEPAGES[layout.codepage]
        self.buf = bytearray(ESC + b"@")  # initialize (clears sizes/styles left by a previous job)
        if n is not None:
            self.buf += ESC + b"t" + bytes([n])

    # -- text helpers
    def printable(self, text: Any) -> str:
        """Same text with every character printable in the code page (and no control characters)."""
        out = []
        for ch in str(text if text is not None else ""):
            if ch in "\r\n\t":
                out.append(" ")
                continue
            if unicodedata.category(ch).startswith("C"):
                continue
            try:
                ch.encode(self.codec)
                out.append(ch)
                continue
            except UnicodeEncodeError:
                pass
            alt = _REPLACE.get(ch) or unicodedata.normalize("NFKD", ch).encode("ascii", "ignore").decode()
            out.append(alt if alt and all(_encodable(c, self.codec) for c in alt) else "?")
        return "".join(out)

    def raw(self, data: bytes) -> "Doc":
        self.buf += data
        return self

    def _emit(self, text: str) -> None:
        self.buf += text.encode(self.codec) + b"\n"

    def align(self, how: str) -> "Doc":
        return self.raw(ESC + b"a" + bytes([{"left": 0, "center": 1, "right": 2}[how]]))

    def bold(self, on: bool) -> "Doc":
        return self.raw(ESC + b"E" + bytes([1 if on else 0]))

    def size(self, w: int = 1, h: int = 1) -> "Doc":
        return self.raw(GS + b"!" + bytes([((w - 1) << 4) | (h - 1)]))

    # -- blocks
    def text(self, text: Any, *, align: str = "left", bold: bool = False, w: int = 1, h: int = 1, indent: int = 0) -> "Doc":
        cols = self.width // w
        s = self.printable(text)
        if align != "left":
            self.align(align)
        if bold:
            self.bold(True)
        if (w, h) != (1, 1):
            self.size(w, h)
        for ln in textwrap.wrap(s, cols - indent, break_long_words=True) or [""]:
            self._emit(" " * indent + ln)
        if (w, h) != (1, 1):
            self.size()
        if bold:
            self.bold(False)
        if align != "left":
            self.align("left")
        return self

    def row(self, left: Any, right: Any, *, bold: bool = False, w: int = 1, h: int = 1, indent: int = 0) -> "Doc":
        """Left text (wrapped) and right-aligned amount on its first line."""
        cols = self.width // w
        lt, rt = self.printable(left), self.printable(right)
        if bold:
            self.bold(True)
        if (w, h) != (1, 1):
            self.size(w, h)
        room = cols - indent - len(rt) - 1
        if room < 8:  # amount too wide: text on its own lines, amount right-aligned below
            for ln in textwrap.wrap(lt, cols - indent) or [""]:
                self._emit(" " * indent + ln)
            self._emit(rt.rjust(cols))
        else:
            lines = textwrap.wrap(lt, room, break_long_words=True) or [""]
            self._emit(" " * indent + lines[0].ljust(room) + " " + rt)
            for ln in lines[1:]:
                self._emit(" " * indent + ln)
        if (w, h) != (1, 1):
            self.size()
        if bold:
            self.bold(False)
        return self

    def rule(self, ch: str = "-") -> "Doc":
        self._emit(ch * self.width)
        return self

    def blank(self, n: int = 1) -> "Doc":
        for _ in range(n):
            self._emit("")
        return self

    def drawer(self, pin: int = 0) -> "Doc":
        """Cash drawer kick: ESC p m t1 t2 (pin 2 = 0, pin 5 = 1; 50 ms on / 500 ms off)."""
        return self.raw(ESC + b"p" + bytes([1 if pin else 0, 25, 250]))

    def finish(self) -> bytes:
        lay = self.layout
        if lay.feed_lines > 0:
            self.raw(ESC + b"d" + bytes([min(int(lay.feed_lines), 10)]))
        if lay.cut == "full":
            self.raw(GS + b"V\x00")
        elif lay.cut == "partial":
            self.raw(GS + b"V\x01")
        return bytes(self.buf)


# ---------------------------------------------------------------- documents


def drawer_kick(pin: int = 0) -> bytes:
    """Only opens the cash drawer (nothing is printed)."""
    return ESC + b"@" + ESC + b"p" + bytes([1 if pin else 0, 25, 250])


def ticket(data: dict[str, Any], layout: Layout, *, open_drawer: bool = False, drawer_pin: int = 0) -> bytes:
    """Sale ticket from `sales.ticket()` (business, sale detail, payment names)."""
    biz, sale, names = data.get("business") or {}, data["sale"], data.get("payment_names") or {}
    d = Doc(layout)
    if open_drawer:
        d.drawer(drawer_pin)
    d.text(biz.get("name") or "Cafetería", align="center", bold=True, w=2, h=2)
    for extra in (biz.get("address"), f"Tel. {biz['phone']}" if biz.get("phone") else None,
                  f"CUIT {biz['cuit']}" if biz.get("cuit") else None):
        if extra:
            d.text(extra, align="center")
    d.rule()
    d.row(f"Ticket #{sale['number']}", date_time(sale["ts"]), bold=True)
    where = CHANNEL_LABEL.get(sale["channel"], sale["channel"])
    if sale.get("table_label"):
        label = str(sale["table_label"])
        where += f" · {label if label.lower().startswith('mesa') else 'Mesa ' + label}"
    d.row(where, sale.get("user_name") or "")
    if sale.get("customer"):
        d.text(f"Cliente: {sale['customer']['name']}")
    if sale["status"] == "voided":
        d.text("*** ANULADO ***", align="center", bold=True, w=2, h=2)
    if sale.get("is_courtesy"):
        d.text("CORTESÍA · INVITA LA CASA", align="center", bold=True)
        if sale.get("courtesy_reason"):
            d.text(sale["courtesy_reason"], align="center")
    d.rule()
    for it in sale["items"]:
        name = f"{number(it['qty'])} x {it['name_snapshot']}" + (f" {it['size_name']}" if it.get("size_name") else "")
        d.row(name, money(it["total_cents"] + it["discount_cents"]))
        for m in it.get("modifiers") or []:
            delta = m.get("price_delta_cents") or 0
            d.text(f"+ {m.get('name', '')}" + (f" ({money(delta)})" if delta else ""), indent=2)
        if it.get("notes"):
            d.text(f"» {it['notes']}", indent=2)
        promo = it.get("promo_discount_cents") or 0
        if it.get("courtesy_reason") and not sale.get("is_courtesy"):  # stamp-card reward line ($0)
            d.row(it["courtesy_reason"], money(-it["discount_cents"]), indent=2)
        elif not sale.get("is_courtesy"):
            if promo and it.get("promo_name"):
                d.row(f"Promo {it['promo_name']}", money(-promo), indent=2)
            manual = it["discount_cents"] - promo
            if manual > 0:
                d.row("Desc.", money(-manual), indent=2)
    d.rule()
    d.row("Subtotal", money(sale["subtotal_cents"]))
    points = sale.get("points_discount_cents") or 0
    reward = sale.get("reward_discount_cents") or 0
    manual_disc = sale["discount_cents"] - points - reward
    if manual_disc > 0:
        d.row("Descuento", money(-manual_disc))
    if points > 0:
        d.row(f"Canje {sale['points_redeemed']} pts", money(-points))
    if reward > 0:
        d.row("Premio fidelidad", money(-reward))
    if sale.get("is_courtesy") and sale.get("courtesy_cents"):
        d.row("Valor de la cortesía", money(sale["courtesy_cents"]))
    d.row("TOTAL", money(sale["total_cents"]), bold=True, h=2)
    if sale["payments"]:
        d.rule()
    for p in sale["payments"]:
        d.row(names.get(p["method"], p["method"]), money(p["amount_cents"]))
        if p.get("tendered_cents") is not None:
            d.row("Entregó", money(p["tendered_cents"]), indent=2)
            d.row("Vuelto", money(p.get("change_cents") or 0), indent=2)
    if sale.get("points_earned"):
        d.rule()
        total = f" · Total: {sale['customer']['points']}" if sale.get("customer") else ""
        d.text(f"Sumaste {sale['points_earned']} puntos{total}")
    d.rule()
    d.text(biz.get("ticket_footer") or "¡Gracias por tu visita!", align="center")
    d.text("Comprobante no válido como factura", align="center")
    return d.finish()


def z_report(s: dict[str, Any], layout: Layout, printed_at: datetime | None = None) -> bytes:
    """Cash close (Z) from `cash.session_summary(detail=True)`."""
    d = Doc(layout)
    d.text((s.get("business") or {}).get("name") or "Cafetería", align="center", bold=True, w=2, h=2)
    d.text(f"CIERRE DE CAJA (Z) · #{s['id']}", align="center", bold=True)
    d.rule()
    d.row("Apertura", f"{date_time(s['opened_at'])} {s.get('opened_by_name') or ''}".strip())
    closed = date_time(s["closed_at"]) if s.get("closed_at") else "Abierta"
    d.row("Cierre", f"{closed} {s.get('closed_by_name') or ''}".strip())
    d.rule()
    d.row("Fondo inicial", money(s["opening_cents"]))
    d.row("Tickets", str(s["tickets"]))
    d.row("Ticket promedio", money(s["avg_ticket_cents"]))
    d.row("Descuentos", money(s["discounts_cents"]))
    d.row(f"Anulaciones ({s['voided_count']})", money(s["voided_total_cents"]))
    d.row(f"Cortesías ({s['courtesy_count']})", money(s["courtesy_cents"]))
    if s["courtesy_count"]:
        d.text("(a precio de carta, no suman a ventas)")
        d.row("Pérdida por cortesías (costo)", money(-s["courtesy_cost_cents"]))
    d.row("VENTAS", money(s["sales_total_cents"]), bold=True, h=2)
    d.rule()
    d.text("Arqueo por medio de pago", bold=True)
    for m in s["by_method"]:
        d.text(m["name"], bold=True)
        d.row("Ventas", money(m["sales_cents"]), indent=2)
        d.row("Esperado", money(m["expected_cents"]), indent=2)
        d.row("Contado", "-" if m["counted_cents"] is None else money(m["counted_cents"]), indent=2)
        diff = m["difference_cents"]
        d.row("Diferencia", "-" if diff is None else ("+" if diff > 0 else "") + money(diff), indent=2)
    diff_total = s.get("difference_cents")
    d.row("Diferencia total", "-" if diff_total is None else ("+" if diff_total > 0 else "") + money(diff_total), bold=True)
    d.rule()
    d.text("Movimientos de caja", bold=True)
    if not s["movements"]:
        d.text("Sin movimientos")
    for mv in s["movements"]:
        sign = 1 if mv["type"] == "in" else -1
        d.row(f"{'Ingreso' if mv['type'] == 'in' else 'Egreso'} · {mv['reason']}", money(sign * mv["amount_cents"]))
    d.row("Ingresos / Egresos", f"{money(s['movements_in_cents'])} / {money(-s['movements_out_cents'])}")
    d.rule()
    d.text("Ventas por categoría", bold=True)
    cats = s.get("by_category") or []
    if not cats:
        d.text("Sin ventas")
    for c in cats:
        d.row(f"{c['name']} ({number(c['qty'])})", money(c["total_cents"]))
    if s.get("notes"):
        d.rule()
        d.text(f"Obs.: {s['notes']}")
    d.rule()
    d.text(f"Impreso {date_time(printed_at or utcnow())}", align="center")
    return d.finish()


def comanda(o: dict[str, Any], station_name: str | None, layout: Layout) -> bytes:
    """Kitchen ticket of one order (from `orders.serialize()`) for a station's printer."""
    d = Doc(layout)
    d.text(f"PEDIDO #{o['number']}", align="center", bold=True, w=2, h=2)
    where = o.get("table_label") or CHANNEL_LABEL.get(o["channel"], o["channel"])
    d.text(where + (f" · {station_name}" if station_name else ""), align="center", bold=True)
    d.text(f"{time_of(o.get('received_at') or o['created_at'])} · objetivo {o['target_minutes']} min", align="center")
    d.rule()
    for i, it in enumerate(o["items"]):
        if i:
            d.rule("-")
        size = f" ({it['size_name']})" if it.get("size_name") else ""
        d.text(f"{number(it['qty'], 1)} x {it['name']}{size}", bold=True, h=2)
        for m in it.get("modifiers") or []:
            d.text(f"+ {m}", indent=2)
        if it.get("notes"):
            d.text(f"» {it['notes']}", bold=True, indent=2)
    if o.get("note"):
        d.rule()
        d.text(f"“{o['note']}”", bold=True)
    return d.finish()


def test_page(printer_name: str, layout: Layout, business_name: str = "") -> bytes:
    """"Imprimir prueba": accents, width ruler, sizes and the cut."""
    d = Doc(layout)
    d.text(business_name or "Bloom", align="center", bold=True, w=2, h=2)
    d.text("Prueba de impresión", align="center", bold=True)
    d.text(printer_name, align="center")
    d.rule()
    d.text(f"{layout.chars} caracteres por línea:")
    d._emit(("1234567890" * 10)[: d.width])
    d.text("Acentos: áéíóú ÁÉÍÓÚ ñÑ üÜ ¿? ¡!")
    d.text("Café con leche · Señor Ñandú")
    d.row("Total", money(123456))
    d.text("Texto grande", bold=True, w=2, h=2)
    d.rule()
    d.text("Si se ve bien, ¡listo!", align="center")
    return d.finish()
