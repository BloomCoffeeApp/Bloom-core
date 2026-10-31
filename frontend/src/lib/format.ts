import { format, formatDistanceToNow, parseISO } from 'date-fns'
import { es } from 'date-fns/locale'

const money = new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', minimumFractionDigits: 2 })
const moneyShort = new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', maximumFractionDigits: 0 })
const number = new Intl.NumberFormat('es-AR', { maximumFractionDigits: 2 })

/** Formats integer cents as "$ 1.234,56". */
export const fmtMoney = (cents: number | null | undefined, opts?: { short?: boolean }) =>
  cents == null ? '—' : (opts?.short ? moneyShort : money).format(cents / 100)

export const fmtNumber = (n: number | null | undefined, digits = 2) =>
  n == null ? '—' : new Intl.NumberFormat('es-AR', { maximumFractionDigits: digits }).format(n)

export const fmtPct = (n: number | null | undefined, digits = 1) =>
  n == null ? '—' : `${new Intl.NumberFormat('es-AR', { maximumFractionDigits: digits }).format(n)}%`

const UNIT_LABEL: Record<string, string> = { g: 'g', ml: 'ml', u: 'u' }

/** Quantity with unit, auto-scaling g→kg and ml→L for readability. */
export function fmtQty(qty: number | null | undefined, unit: string) {
  if (qty == null) return '—'
  if ((unit === 'g' || unit === 'ml') && Math.abs(qty) >= 1000) {
    return `${number.format(qty / 1000)} ${unit === 'g' ? 'kg' : 'L'}`
  }
  return `${number.format(qty)} ${UNIT_LABEL[unit] ?? unit}`
}

/** Backend sends naive UTC datetimes; normalise them before parsing. */
export function toDate(value: string | Date): Date {
  if (value instanceof Date) return value
  const v = /[zZ]|[+-]\d\d:?\d\d$/.test(value) || value.length <= 10 ? value : `${value}Z`
  return parseISO(v)
}

export const fmtDate = (v: string | Date | null | undefined) => (v ? format(toDate(v), 'dd/MM/yyyy') : '—')
export const fmtDateTime = (v: string | Date | null | undefined) =>
  v ? format(toDate(v), 'dd/MM/yyyy HH:mm') : '—'
export const fmtTime = (v: string | Date | null | undefined) => (v ? format(toDate(v), 'HH:mm') : '—')
export const fmtRelative = (v: string | Date | null | undefined) =>
  v ? formatDistanceToNow(toDate(v), { addSuffix: true, locale: es }) : '—'

/** "2026-10-30" for <input type="date"> and API date params (local time). */
export const isoDate = (d: Date = new Date()) => format(d, 'yyyy-MM-dd')

/** Parses "1.234,56" or "1234.56" into integer cents. */
export function parseMoneyToCents(input: string): number | null {
  const clean = input.replace(/[^\d,.-]/g, '')
  if (!clean) return null
  const normalized = clean.includes(',') ? clean.replace(/\./g, '').replace(',', '.') : clean
  const n = Number(normalized)
  return Number.isFinite(n) ? Math.round(n * 100) : null
}

export const ROLE_LABEL: Record<string, string> = {
  admin: 'Administrador',
  encargado: 'Encargado',
  cajero: 'Cajero',
  barista: 'Barista',
}

export const PAYMENT_LABEL: Record<string, string> = {
  efectivo: 'Efectivo',
  debito: 'Débito',
  credito: 'Crédito',
  transferencia: 'Transferencia',
  qr: 'QR / Billetera',
  cuenta_corriente: 'Cuenta corriente',
}

/** Formats a CUIT/CUIL as the user types: digits only, "XX-XXXXXXXX-X". */
export function formatCuit(input: string) {
  const d = input.replace(/\D/g, '').slice(0, 11)
  if (d.length <= 2) return d
  if (d.length <= 10) return `${d.slice(0, 2)}-${d.slice(2)}`
  return `${d.slice(0, 2)}-${d.slice(2, 10)}-${d.slice(10)}`
}
