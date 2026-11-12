"""ESC/POS renderer: golden bytes for a ticket (accents, sizes, modifiers, promo, stamp-card reward,
points, change), a courtesy ticket on 58 mm, the Z report and a kitchen ticket, plus the building blocks.

Regenerate the golden files after an intended change with `BLOOM_UPDATE_GOLDEN=1 pytest tests/test_escpos.py`
and review the diff (`python -m tests.test_escpos` prints them readable)."""

import os
from pathlib import Path

import pytest

from app.services import escpos
from tests import escpos_samples as S

GOLDEN = Path(__file__).parent / "golden"
UPDATE = os.environ.get("BLOOM_UPDATE_GOLDEN") == "1"
ESC, GS = b"\x1b", b"\x1d"


def _docs() -> dict[str, bytes]:
    return {
        "ticket_80mm": escpos.ticket(S.ticket(), escpos.Layout(), open_drawer=True),
        "ticket_delivery_80mm": escpos.ticket(S.delivery_ticket(), escpos.Layout()),
        "ticket_courtesy_58mm": escpos.ticket(S.courtesy_ticket(), escpos.Layout(chars=32, cut="full")),
        "ticket_ascii": escpos.ticket(S.ticket(), escpos.Layout(codepage="ascii", cut="none", feed_lines=0)),
        "z_58mm": escpos.z_report(S.z_session(), escpos.Layout(chars=32), printed_at=S.TS),
        "comanda_80mm": escpos.comanda(S.order(), "Cocina", escpos.Layout()),
    }


@pytest.mark.parametrize("name", list(_docs()))
def test_golden_bytes(name):
    data = _docs()[name]
    path = GOLDEN / f"{name}.bin"
    if UPDATE:
        path.write_bytes(data)
    assert path.exists(), f"Missing golden file {path.name}: run with BLOOM_UPDATE_GOLDEN=1"
    assert data == path.read_bytes(), f"{name} changed: review it and regenerate the golden file"


def _lines(data: bytes, codec: str = "cp858") -> list[str]:
    """Printed text lines without the control sequences we emit."""
    import re

    text = re.sub(rb"\x1b[@]|\x1b[taEdp].|\x1b p..|\x1d!.|\x1dV.", b"", data.replace(b"\x1bp\x00\x19\xfa", b""))
    return text.decode(codec).split("\n")


@pytest.mark.parametrize("chars", [32, 42, 48])
def test_no_line_exceeds_the_paper_width(chars):
    for doc in (
        escpos.ticket(S.ticket(), escpos.Layout(chars=chars)),
        escpos.z_report(S.z_session(), escpos.Layout(chars=chars), printed_at=S.TS),
        escpos.comanda(S.order(), "Barra", escpos.Layout(chars=chars)),
    ):
        assert max(len(ln) for ln in _lines(doc)) <= chars


def test_ticket_contents_in_cp858():
    data = escpos.ticket(S.ticket(), escpos.Layout())
    assert data.startswith(ESC + b"@" + ESC + b"t\x13")  # init + code page 19 (CP858)
    assert "Café Ñandú".encode("cp858") in data and b"Caf\x82" in data  # é = 0x82
    text = "\n".join(_lines(data))
    for piece in ("2 x Latte Grande", "+ Leche de almendras ($ 500,00)", "» Bien caliente", "Promo Happy hour",
                  "-$ 900,00", "Premio fidelidad", "Canje 100 pts", "Entregó", "Vuelto", "Mercado Pago",
                  "Salón · Mesa 4", "Comprobante no válido como factura"):
        assert piece in text, piece
    assert "Mesa Mesa" not in text
    assert ESC + b"p" not in data  # drawer only when asked
    assert data.endswith(ESC + b"d\x04" + GS + b"V\x01")  # feed 4 + partial cut


def test_delivery_fee_line_is_printed_before_total():
    lines = _lines(escpos.ticket(S.delivery_ticket(), escpos.Layout()))
    env = next(i for i, ln in enumerate(lines) if ln.startswith("Envío"))
    total = next(i for i, ln in enumerate(lines) if ln.startswith("TOTAL"))
    assert env < total and "$ 500,00" in lines[env]
    no_fee = "\n".join(_lines(escpos.ticket(S.ticket(channel="delivery"), escpos.Layout())))
    assert "Envío" not in no_fee


def test_courtesy_and_voided_marks():
    text = "\n".join(_lines(escpos.ticket(S.courtesy_ticket(), escpos.Layout(chars=32))))
    assert "CORTESÍA · INVITA LA CASA" in text and "Cumpleaños del dueño" in text and "Valor de la cortesía" in text
    voided = "\n".join(_lines(escpos.ticket(S.ticket(status="voided"), escpos.Layout())))
    assert "*** ANULADO ***" in voided


def test_drawer_cut_and_codepage_options():
    assert escpos.ticket(S.ticket(), escpos.Layout(), open_drawer=True, drawer_pin=1).startswith(ESC + b"@" + ESC + b"t\x13" + ESC + b"p\x01\x19\xfa")
    assert escpos.drawer_kick(0) == ESC + b"@" + ESC + b"p\x00\x19\xfa"
    full = escpos.ticket(S.ticket(), escpos.Layout(cut="full", feed_lines=0))
    assert full.endswith(GS + b"V\x00") and ESC + b"d" not in full
    assert escpos.ticket(S.ticket(), escpos.Layout(cut="none", feed_lines=2)).endswith(ESC + b"d\x02")
    cp850 = escpos.ticket(S.ticket(), escpos.Layout(codepage="cp850"))
    assert cp850.startswith(ESC + b"@" + ESC + b"t\x02")
    ascii_ = escpos.ticket(S.ticket(), escpos.Layout(codepage="ascii"))
    assert ESC + b"t" not in ascii_[:4] and b"Cafe Nandu" in ascii_
    with pytest.raises(ValueError):
        escpos.Doc(escpos.Layout(codepage="utf8"))


def test_unprintable_characters_are_replaced_not_dropped():
    d = escpos.Doc(escpos.Layout())
    assert d.printable("“Té” — ok…\tsí\x07") == '"Té" - ok... sí'
    assert d.printable("Ø ☕ €") == "Ø ? €"  # Ø and € exist in CP858; the emoji doesn't
    assert escpos.Doc(escpos.Layout(codepage="cp437")).printable("€ ñ") == "EUR ñ"


def test_number_and_money_formats():
    assert escpos.money(123456) == "$ 1.234,56"
    assert escpos.money(-5) == "-$ 0,05"
    assert escpos.money(100000000) == "$ 1.000.000,00"
    assert escpos.number(2) == "2" and escpos.number(1.5) == "1,5" and escpos.number(1234.25) == "1.234,25"


def test_comanda_contents():
    text = "\n".join(_lines(escpos.comanda(S.order(), "Cocina", escpos.Layout())))
    for piece in ("PEDIDO #12", "Mesa 4 · Cocina", "12:30 · objetivo 8 min", "2 x Latte (Grande)", "+ Extra shot",
                  "» Uno tibio", "1 x Tostado de jamón y queso", '"Sin apuro, es para compartir"'):
        assert piece in text, piece


if __name__ == "__main__":  # readable dump of the golden documents
    for name, data in _docs().items():
        print(f"===== {name}")
        print(data.decode("cp858", errors="replace").replace("\x1b", "<ESC>").replace("\x1d", "<GS>"))
