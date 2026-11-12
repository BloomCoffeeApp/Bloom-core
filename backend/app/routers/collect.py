"""Collecting payments (Pro `payments`): POS charges, transfer confirmation, refunds, customer screens.

Logic lives in services/collect.py. The Mercado Pago connection endpoints are Pro (bloom_pro).
"""

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import CurrentUser, Perm
from app.db import get_db
from app.models import User
from app.schemas.sales import SaleDetail, SaleIn
from app.services import collect
from app.services import sales as sales_svc

router = APIRouter(prefix="/api", tags=["collect"])

Seller = Perm("pos.sell")
Refunder = Perm("sales.void")
SettingsAdmin = Perm("settings.manage")


def _licensed() -> None:
    collect.require_license()


Licensed = Depends(_licensed)


class TransferCfg(BaseModel):
    enabled: bool = False
    alias: str = Field(default="", max_length=40)
    cbu: str = Field(default="", max_length=30, pattern=r"^[0-9 ]*$")
    holder: str = Field(default="", max_length=80)
    bank: str = Field(default="", max_length=60)
    cuit: str = Field(default="", max_length=20)


class ConfigIn(BaseModel):
    provider: str | None = None
    transfer: TransferCfg | None = None
    expires_minutes: int | None = Field(default=None, ge=2, le=60)
    point_device_id: str | None = Field(default=None, max_length=80)
    point_device_name: str | None = Field(default=None, max_length=80)
    default_screen_id: int | None = None


class PosChargeIn(BaseModel):
    sale: SaleIn
    method: Literal["mp_qr", "mp_point", "transferencia"]
    screen_id: int | None = None


class ChargeOut(BaseModel):
    id: int
    status: str
    status_detail: str | None
    kind: str
    provider: str
    amount_cents: int
    refunded_cents: int
    description: str
    qr_data: str | None
    url: str | None
    device_id: str | None
    expires_at: datetime | None
    approved_at: datetime | None
    ref: str
    ref_type: str
    ref_id: int | None
    sale_id: int | None
    screen_id: int | None
    error: str | None
    items: list[dict[str, Any]]
    created_at: datetime
    # POS: the sale once the payment was approved (same shape as POST /api/sales).
    sale: dict[str, Any] | None = None
    qr_png: str | None = None  # data URL of the QR while pending (POS dialog)


class RefundIn(BaseModel):
    amount_cents: int | None = Field(default=None, gt=0)
    reason: str | None = Field(default=None, max_length=200)
    # Full refund: also void the sale (stock back, out of the cash totals).
    void_sale: bool = False


class SimulateIn(BaseModel):
    status: Literal["approved", "rejected", "cancelled"] = "approved"


class ScreenIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)


class ScreenPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    active: bool | None = None
    rotate: bool = False


def _charge_out(db: Session, ch) -> dict:
    out = collect.serialize(ch)
    if ch.status == "pending" and (ch.qr_data or ch.url) and ch.kind in ("qr", "link"):
        out["qr_png"] = collect._qr_data_url(ch.qr_data or ch.url)
    if ch.sale_id:
        out["sale"] = SaleDetail.model_validate(sales_svc.get_detail(db, ch.sale_id)).model_dump(mode="json")
    return out


# ---------------------------------------------------------------- status and configuration


@router.get("/collect/status")
def collect_status(db: Session = Depends(get_db), _: User = CurrentUser) -> dict:
    return collect.status(db)


@router.put("/collect/config", dependencies=[Licensed])
def put_config(data: ConfigIn, db: Session = Depends(get_db), user: User = SettingsAdmin) -> dict:
    collect.save_config(db, data.model_dump(exclude_unset=True), user.id)
    return collect.status(db)


# ---------------------------------------------------------------- charges


@router.post("/collect/pos-charges", response_model=ChargeOut)
def pos_charge(data: PosChargeIn, db: Session = Depends(get_db), user: User = Seller) -> dict:
    ch = collect.pos_charge(db, data.sale, data.method, user, data.screen_id)
    return _charge_out(db, ch)


@router.get("/collect/charges/{charge_id}", response_model=ChargeOut, dependencies=[Licensed])
def get_charge(charge_id: int, db: Session = Depends(get_db), _: User = Seller) -> dict:
    ch = collect.refresh(db, collect.get_charge(db, charge_id))
    return _charge_out(db, ch)


@router.post("/collect/charges/{charge_id}/cancel", response_model=ChargeOut, dependencies=[Licensed])
def cancel_charge(charge_id: int, db: Session = Depends(get_db), user: User = Seller) -> dict:
    return _charge_out(db, collect.cancel_charge(db, charge_id, user.id))


@router.post("/collect/charges/{charge_id}/confirm", response_model=ChargeOut, dependencies=[Licensed])
def confirm_charge(charge_id: int, db: Session = Depends(get_db), user: User = Seller) -> dict:
    """Transfer: «Pago recibido»."""
    return _charge_out(db, collect.confirm_manual(db, charge_id, user.id))


@router.post("/collect/charges/{charge_id}/retry", response_model=ChargeOut, dependencies=[Licensed])
def retry_charge(charge_id: int, db: Session = Depends(get_db), user: User = Seller) -> dict:
    return _charge_out(db, collect.retry_handler(db, charge_id, user.id))


@router.post("/collect/charges/{charge_id}/simulate", response_model=ChargeOut, dependencies=[Licensed])
def simulate_charge(charge_id: int, data: SimulateIn, db: Session = Depends(get_db), _: User = Seller) -> dict:
    """Test mode only: the customer «pays» (or the payment is rejected)."""
    return _charge_out(db, collect.simulate(db, charge_id, data.status))


@router.get("/collect/sales/{sale_id}")
def sale_charge(sale_id: int, db: Session = Depends(get_db), _: User = Seller) -> dict:
    """The charge behind a sale (for «Devolver» in the sale detail)."""
    ch = collect.charge_for_sale(db, sale_id)
    if ch is None:
        return {"charge": None, "refunds": [], "refundable_cents": 0}
    refunds = [
        {"id": r.id, "amount_cents": r.amount_cents, "reason": r.reason, "ts": r.ts, "user_id": r.user_id}
        for r in collect.refunds_of(db, ch.id)
    ]
    refundable = ch.amount_cents - ch.refunded_cents if ch.status == "approved" and ch.provider != "manual" else 0
    return {"charge": collect.serialize(ch), "refunds": refunds, "refundable_cents": refundable}


@router.post("/collect/sales/{sale_id}/refund", dependencies=[Licensed])
def refund_sale(sale_id: int, data: RefundIn, db: Session = Depends(get_db), user: User = Refunder) -> dict:
    ch = collect.charge_for_sale(db, sale_id)
    if ch is None:
        raise HTTPException(404, "Esta venta no se cobró con Mercado Pago")
    ch = collect.refund(db, ch.id, data.amount_cents, user.id, data.reason)
    if data.void_sale and ch.status == "refunded":
        sale = sales_svc.get_detail(db, sale_id)
        if sale["status"] == "completed":
            sales_svc.void_sale(db, sale_id, f"Devolución por Mercado Pago. {data.reason or ''}".strip()[:300], user)
    return sale_charge(sale_id, db, user)


# ---------------------------------------------------------------- customer screens


def _screen_out(s, base: str | None) -> dict:
    path = f"/pantalla-cliente?token={s.token}"
    return {
        "id": s.id, "name": s.name, "token": s.token, "active": s.active, "last_seen_at": s.last_seen_at,
        "path": path, "url": f"{base}{path}" if base else None,
        "qr_png": collect._qr_data_url(f"{base}{path}") if base else None,
    }


def _lan_base() -> str | None:
    from app.services import system

    try:
        return system.lan_url()
    except Exception:  # noqa: BLE001 - no network is fine: the screen can be opened on this PC
        return None


@router.get("/collect/screens", dependencies=[Licensed])
def list_screens(db: Session = Depends(get_db), _: User = SettingsAdmin) -> list[dict]:
    base = _lan_base()
    return [_screen_out(s, base) for s in collect.screens(db)]


@router.post("/collect/screens", dependencies=[Licensed])
def create_screen(data: ScreenIn, db: Session = Depends(get_db), user: User = SettingsAdmin) -> dict:
    return _screen_out(collect.create_screen(db, data.name, user.id), _lan_base())


@router.patch("/collect/screens/{screen_id}", dependencies=[Licensed])
def patch_screen(screen_id: int, data: ScreenPatch, db: Session = Depends(get_db), user: User = SettingsAdmin) -> dict:
    s = collect.update_screen(db, screen_id, user.id, data.name, data.active, data.rotate)
    return _screen_out(s, _lan_base())


@router.delete("/collect/screens/{screen_id}", dependencies=[Licensed])
def delete_screen(screen_id: int, db: Session = Depends(get_db), user: User = SettingsAdmin) -> dict:
    collect.delete_screen(db, screen_id, user.id)
    return {"ok": True}


@router.get("/public/customer-screen")
def customer_screen(token: str, db: Session = Depends(get_db)) -> dict:
    """The customer-facing screen (tablet/TV on the LAN). No login: the screen's secret token."""
    return collect.screen_state(db, token[:64])
