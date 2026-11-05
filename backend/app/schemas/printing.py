from typing import Literal

from pydantic import BaseModel, Field, field_validator

PrinterKind = Literal["windows", "network"]
Codepage = Literal["cp858", "cp850", "cp437", "ascii"]
CutMode = Literal["partial", "full", "none"]
TicketMode = Literal["ask", "auto", "never"]


class PrinterCfg(BaseModel):
    id: str = Field(default="", max_length=16)  # assigned by the server on save
    name: str = Field(min_length=1, max_length=60)
    kind: PrinterKind
    # Windows: the printer's name as Windows lists it. Network: IP or host name.
    target: str = Field(min_length=1, max_length=200)
    port: int = Field(default=9100, ge=1, le=65535)
    paper_mm: Literal[58, 80] = 80
    chars: int = Field(default=48, ge=24, le=64)
    codepage: Codepage = "cp858"
    cut: CutMode = "partial"
    feed_lines: int = Field(default=4, ge=0, le=10)

    @field_validator("name", "target")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("No puede quedar vacío")
        return v


class PrintingConfig(BaseModel):
    printers: list[PrinterCfg] = Field(default_factory=list, max_length=20)
    cashier_printer: str | None = None  # tickets + Z report (and the cash drawer)
    ticket_mode: TicketMode = "ask"  # after each sale: ask (button), auto (print), never
    cash_drawer: bool = False  # open the drawer on sales paid (partly) in cash
    drawer_pin: Literal[0, 1] = 0  # drawer connector pin 2 (0) or 5 (1)
    stations: dict[str, str] = Field(default_factory=dict)  # station id -> printer id (Pro stations)


class StationPrinterRef(BaseModel):
    id: int
    name: str
    print_tickets: bool


class PrintingConfigOut(PrintingConfig):
    available: bool
    reason: str | None
    station_list: list[StationPrinterRef]


class PrintingStatus(BaseModel):
    available: bool
    reason: str | None
    ticket_mode: TicketMode
    cashier: bool  # a cashier printer is configured (and direct printing is available)
    cash_drawer: bool


class WindowsPrinter(BaseModel):
    name: str
    default: bool


class PrintTestIn(BaseModel):
    printer: PrinterCfg


class TicketPrintIn(BaseModel):
    open_drawer: bool = False  # right after the sale (not on reprints)


class PrintResult(BaseModel):
    ok: bool
    printer: str | None = None
    drawer: bool = False
