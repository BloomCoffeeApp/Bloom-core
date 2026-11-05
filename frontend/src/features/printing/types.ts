/** Mirrors `backend/app/schemas/printing.py`. */
export type PrinterKind = 'windows' | 'network'
export type Codepage = 'cp858' | 'cp850' | 'cp437' | 'ascii'
export type CutMode = 'partial' | 'full' | 'none'
export type TicketMode = 'ask' | 'auto' | 'never'

export interface PrinterCfg {
  /** Assigned by the server on save ('' for a new one). */
  id: string
  name: string
  kind: PrinterKind
  /** Windows: the printer's name as Windows lists it. Network: IP or host name. */
  target: string
  port: number
  paper_mm: 58 | 80
  chars: number
  codepage: Codepage
  cut: CutMode
  feed_lines: number
}

export interface PrintingConfig {
  printers: PrinterCfg[]
  /** Tickets + Z report (and the cash drawer). */
  cashier_printer: string | null
  ticket_mode: TicketMode
  cash_drawer: boolean
  drawer_pin: 0 | 1
  /** Station id → printer id (stations are Pro `orders_pro`). */
  stations: Record<string, string>
}

export interface PrintingConfigOut extends PrintingConfig {
  available: boolean
  reason: string | null
  station_list: { id: number; name: string; print_tickets: boolean }[]
}

export interface PrintingStatus {
  available: boolean
  reason: string | null
  ticket_mode: TicketMode
  /** A cashier printer is configured (and direct printing is available). */
  cashier: boolean
  cash_drawer: boolean
}

export interface WindowsPrinter {
  name: string
  default: boolean
}

export interface PrintResult {
  ok: boolean
  printer: string | null
  drawer: boolean
}
