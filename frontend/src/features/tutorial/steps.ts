import type { Permission } from '@/lib/permissions'
import { BRAND } from '@/lib/brand'

export interface TourStep {
  /** `data-tour` value of the element to highlight. No target = centered card. */
  target?: string
  title: string
  body: string
  /** Permissions that show this step (any; admin always). Empty = everyone. */
  perms?: Permission[]
  /** Navigate here before showing the step. */
  route?: string
}

export const TOUR_STEPS: TourStep[] = [
  {
    title: `¡Bienvenido a ${BRAND.name}!`,
    body: 'Te mostramos en un minuto dónde está cada cosa. Podés salir cuando quieras con Esc y repetir el tutorial desde tu usuario, abajo a la izquierda.',
    route: '/',
  },
  {
    target: 'sidebar',
    title: 'El menú',
    body: 'Acá están todas las secciones, agrupadas en Operación, Gestión y Sistema. Con el botón de arriba a la izquierda lo achicás para ganar espacio.',
  },
  {
    target: 'nav-/',
    title: 'Inicio',
    body: 'El resumen del día: ventas, ticket promedio, productos más vendidos, alertas y estado de la caja.',
  },
  {
    target: 'nav-/pos',
    title: 'Punto de venta',
    perms: ['pos.sell'],
    body: 'Para cobrar. Tocá los productos, elegí modificadores (leche, shot extra…) y cobrá con uno o varios medios de pago. Atajo: F1.',
  },
  {
    target: 'nav-/caja',
    title: 'Caja',
    perms: ['cash.open_close', 'cash.movements'],
    body: 'Abrí la caja al empezar el turno, registrá ingresos y retiros, y cerrala con el arqueo al final del día.',
  },
  {
    target: 'nav-/barista',
    title: 'Barista',
    perms: ['barista.use'],
    body: 'Registrá cada shot (dosis, rendimiento, tiempo, molienda, temperatura) y el asistente te sugiere cómo calibrar el espresso.',
  },
  {
    target: 'nav-/productos',
    title: 'Productos',
    perms: ['catalog.edit', 'prices.edit'],
    body: 'El menú del local: precios, categorías y recetas con su costo y margen calculados en vivo.',
  },
  {
    target: 'nav-/stock',
    title: 'Stock',
    perms: ['stock.view'],
    body: 'Insumos con semáforo de stock, mermas, conteos físicos y sugerencias de compra.',
  },
  {
    target: 'nav-/compras',
    title: 'Compras',
    perms: ['purchases.manage'],
    body: 'Proveedores, órdenes de compra, facturas, pagos y vencimientos.',
  },
  {
    target: 'nav-/clientes',
    title: 'Clientes',
    perms: ['customers.edit'],
    body: 'Fichas de clientes, puntos de fidelización y cuenta corriente.',
  },
  {
    target: 'nav-/ventas',
    title: 'Ventas',
    perms: ['pos.sell'],
    body: 'El historial de tickets: buscá una venta, reimprimí el ticket o anulala si hace falta.',
  },
  {
    target: 'nav-/reportes',
    title: 'Reportes',
    perms: ['reports.view'],
    body: 'Ventas, rentabilidad, stock y cajas, exportables a Excel.',
  },
  {
    target: 'nav-/avisos',
    title: 'Avisos y alertas',
    body: 'Alertas automáticas (stock bajo, vencimientos, mantenimiento), el tablón del equipo y los checklists de apertura y cierre.',
  },
  {
    target: 'nav-/config',
    title: 'Configuración',
    body: 'Datos del negocio, usuarios, medios de pago, respaldos y modo red local.',
  },
  {
    target: 'search',
    title: 'Buscar o ir a',
    body: 'Escribí el nombre de una sección o acción y llegás directo. También con Ctrl + K desde cualquier pantalla.',
  },
  {
    target: 'alerts',
    title: 'Alertas',
    body: 'El número indica cuántas alertas hay abiertas; en rojo, si alguna es urgente.',
  },
  {
    target: 'lock',
    title: 'Bloquear',
    body: 'Si te alejás de la compu, bloqueala: el siguiente entra con su PIN. También se bloquea sola después de un rato sin uso.',
  },
  {
    target: 'user',
    title: 'Tu usuario',
    body: 'Cambiá entre tema claro y oscuro, repetí este tutorial o cerrá sesión.',
  },
  {
    title: '¡Listo!',
    body: 'Ya conocés lo básico. Cuando quieras repasar, abrí tu usuario y elegí “Ver tutorial”.',
  },
]
