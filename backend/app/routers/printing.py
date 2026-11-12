"""Direct printing (ESC/POS) to thermal printers: configuration, test page, tickets, drawer and Z report."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import CurrentUser, Perm
from app.db import get_db
from app.models import User
from app.schemas.printing import (
    PrintingConfig,
    PrintingConfigOut,
    PrintingStatus,
    PrintResult,
    PrintTestIn,
    TicketPrintIn,
    WindowsPrinter,
)
from app.services import printing as svc

router = APIRouter(prefix="/api/printing", tags=["printing"])

Seller = Perm("pos.sell")
AdminOnly = Perm("settings.manage")


@router.get("/status", response_model=PrintingStatus)
def status(db: Session = Depends(get_db), _: User = CurrentUser) -> dict:
    return svc.status(db)


@router.get("/config", response_model=PrintingConfigOut)
def get_config(db: Session = Depends(get_db), _: User = AdminOnly) -> dict:
    return svc.config_out(db)


@router.put("/config", response_model=PrintingConfigOut)
def put_config(data: PrintingConfig, db: Session = Depends(get_db), me: User = AdminOnly) -> dict:
    svc.save_cfg(db, data, me)
    return svc.config_out(db)


@router.get("/windows-printers", response_model=list[WindowsPrinter])
def windows_printers(_: User = AdminOnly) -> list[dict]:
    return svc.windows_printers()


@router.post("/test", response_model=PrintResult)
def test_print(data: PrintTestIn, db: Session = Depends(get_db), _: User = AdminOnly) -> dict:
    return svc.print_test(db, data.printer)


@router.post("/sales/{sale_id}/ticket", response_model=PrintResult)
def print_ticket(sale_id: int, data: TicketPrintIn, db: Session = Depends(get_db), _: User = Seller) -> dict:
    return svc.print_ticket(db, sale_id, data.open_drawer)


@router.post("/sales/{sale_id}/drawer", response_model=PrintResult)
def open_drawer(sale_id: int, db: Session = Depends(get_db), _: User = Seller) -> dict:
    return svc.kick_drawer(db, sale_id)


@router.post("/cash-sessions/{session_id}/z", response_model=PrintResult)
def print_z(session_id: int, db: Session = Depends(get_db), _: User = Perm("cash.open_close")) -> dict:
    return svc.print_z(db, session_id)
