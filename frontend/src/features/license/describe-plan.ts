import { fmtDate } from '@/lib/format'

import type { LicenseInfo } from './api'

const fromUnix = (s: number | null) => (s ? new Date(s * 1000) : null)

/** Plan name + one-line status, shared by the settings card and the user menu. */
export function describePlan(info: LicenseInfo): { title: string; detail: string } {
  const until = fromUnix(info.expires_at)
  if (info.valid && info.perpetual) return { title: `${info.pro_label} · licencia perpetua`, detail: `A nombre de ${info.customer}. No vence.` }
  if (info.valid && info.plan === 'trial')
    return { title: `Prueba de ${info.pro_label}`, detail: `Termina el ${fmtDate(until)} (${info.days_left} día/s).` }
  if (info.valid)
    return {
      title: info.pro_label,
      detail: info.in_grace
        ? `Vencida el ${fmtDate(until)}: sigue activa ${info.days_left} día(s) más mientras se renueva.`
        : `A nombre de ${info.customer}. Pagado hasta el ${fmtDate(until)}.`,
    }
  return { title: 'Plan gratuito', detail: 'Punto de venta, caja, productos, stock, clientes y avisos. Sin vencimiento.' }
}
