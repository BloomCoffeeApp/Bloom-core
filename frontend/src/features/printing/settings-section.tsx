import { Loader2, Plus, Printer, RefreshCw, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { EmptyState } from '@/components/empty-state'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'

import { CardSkeleton, Field, NumberInput, SettingsCard, SwitchRow } from '../settings/form'
import { usePrintingConfig, useSavePrinting, useTestPrint, useWindowsPrinters } from './api'
import type { Codepage, CutMode, PrinterCfg, PrintingConfig, PrintingConfigOut, TicketMode } from './types'

const NONE = '__none__'
const CODEPAGES: { value: Codepage; label: string }[] = [
  { value: 'cp858', label: 'CP858 (recomendada, con acentos y €)' },
  { value: 'cp850', label: 'CP850 (con acentos)' },
  { value: 'cp437', label: 'CP437 (impresoras viejas)' },
  { value: 'ascii', label: 'Sin acentos' },
]
const CUTS: { value: CutMode; label: string }[] = [
  { value: 'partial', label: 'Corte parcial' },
  { value: 'full', label: 'Corte total' },
  { value: 'none', label: 'Sin corte (cortar a mano)' },
]
const MODES: { value: TicketMode; label: string; hint: string }[] = [
  { value: 'ask', label: 'Preguntar', hint: 'Después de cobrar aparece «Imprimir ticket».' },
  { value: 'auto', label: 'Automático', hint: 'Se imprime solo después de cada venta.' },
  { value: 'never', label: 'Nunca', hint: 'No se ofrece; se puede reimprimir desde Ventas.' },
]

const newId = () => Math.random().toString(16).slice(2, 10)

function newPrinter(n: number): PrinterCfg {
  return {
    id: newId(),
    name: n ? `Impresora ${n + 1}` : 'Caja',
    kind: 'windows',
    target: '',
    port: 9100,
    paper_mm: 80,
    chars: 48,
    codepage: 'cp858',
    cut: 'partial',
    feed_lines: 4,
  }
}

function toConfig(c: PrintingConfigOut): PrintingConfig {
  return {
    printers: c.printers,
    cashier_printer: c.cashier_printer,
    ticket_mode: c.ticket_mode,
    cash_drawer: c.cash_drawer,
    drawer_pin: c.drawer_pin,
    stations: c.stations,
  }
}

function PrinterEditor({
  p,
  onChange,
  onRemove,
  windowsNames,
  loadingWindows,
  onReloadWindows,
}: {
  p: PrinterCfg
  onChange: (p: PrinterCfg) => void
  onRemove: () => void
  windowsNames: string[]
  loadingWindows: boolean
  onReloadWindows: () => void
}) {
  const test = useTestPrint()
  const set = <K extends keyof PrinterCfg>(k: K, v: PrinterCfg[K]) => onChange({ ...p, [k]: v })
  const names = p.target && !windowsNames.includes(p.target) ? [p.target, ...windowsNames] : windowsNames
  const runTest = () => {
    if (!p.name.trim() || !p.target.trim()) return toast.error('Completá el nombre y la impresora antes de probar')
    test.mutate(p)
  }
  return (
    <div className="space-y-4 rounded-xl border p-4" data-testid="printer-row">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Nombre" htmlFor={`pn-${p.id}`}>
          <Input id={`pn-${p.id}`} value={p.name} maxLength={60} onChange={(e) => set('name', e.target.value)} />
        </Field>
        <Field label="Conexión">
          <ToggleGroup
            type="single"
            variant="outline"
            value={p.kind}
            onValueChange={(v) => v && onChange({ ...p, kind: v as PrinterCfg['kind'], target: '' })}
          >
            <ToggleGroupItem value="windows" className="px-3">
              Instalada en Windows
            </ToggleGroupItem>
            <ToggleGroupItem value="network" className="px-3">
              De red (IP)
            </ToggleGroupItem>
          </ToggleGroup>
        </Field>
      </div>
      {p.kind === 'windows' ? (
        <Field
          label="Impresora de Windows"
          hint="USB o compartida, instalada con el driver del fabricante o «Generic / Text Only»."
        >
          <div className="flex gap-2">
            <Select value={p.target || NONE} onValueChange={(v) => set('target', v === NONE ? '' : v)}>
              <SelectTrigger className="w-full" aria-label="Impresora de Windows">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NONE}>Elegí una impresora…</SelectItem>
                {names.map((n) => (
                  <SelectItem key={n} value={n}>
                    {n}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button variant="outline" size="icon" onClick={onReloadWindows} aria-label="Volver a buscar impresoras" disabled={loadingWindows}>
              <RefreshCw className={loadingWindows ? 'animate-spin' : undefined} />
            </Button>
          </div>
        </Field>
      ) : (
        <div className="grid gap-4 sm:grid-cols-[1fr_8rem]">
          <Field label="Dirección IP" htmlFor={`pt-${p.id}`} hint="La de la impresora en la red del local (por ejemplo 192.168.0.50).">
            <Input id={`pt-${p.id}`} value={p.target} placeholder="192.168.0.50" onChange={(e) => set('target', e.target.value.trim())} />
          </Field>
          <Field label="Puerto" htmlFor={`pp-${p.id}`}>
            <NumberInput id={`pp-${p.id}`} value={p.port} min={1} max={65535} onChange={(v) => set('port', v)} />
          </Field>
        </div>
      )}
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Papel">
          <ToggleGroup
            type="single"
            variant="outline"
            value={String(p.paper_mm)}
            onValueChange={(v) => v && onChange({ ...p, paper_mm: v === '58' ? 58 : 80, chars: v === '58' ? 32 : 48 })}
          >
            <ToggleGroupItem value="58" className="px-3">
              58 mm
            </ToggleGroupItem>
            <ToggleGroupItem value="80" className="px-3">
              80 mm
            </ToggleGroupItem>
          </ToggleGroup>
        </Field>
        <Field label="Caracteres por línea" htmlFor={`pc-${p.id}`} hint="Normalmente 32 (58 mm) o 48 (80 mm).">
          <NumberInput id={`pc-${p.id}`} value={p.chars} min={24} max={64} onChange={(v) => set('chars', v)} />
        </Field>
        <Field label="Al terminar">
          <Select value={p.cut} onValueChange={(v) => set('cut', v as CutMode)}>
            <SelectTrigger className="w-full" aria-label="Corte del papel">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {CUTS.map((c) => (
                <SelectItem key={c.value} value={c.value}>
                  {c.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
      </div>
      <Field label="Acentos (página de códigos)" hint="Si salen símbolos raros en vez de «á» o «ñ», probá con otra.">
        <Select value={p.codepage} onValueChange={(v) => set('codepage', v as Codepage)}>
          <SelectTrigger className="w-full sm:w-80" aria-label="Página de códigos">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {CODEPAGES.map((c) => (
              <SelectItem key={c.value} value={c.value}>
                {c.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>
      <div className="flex flex-wrap justify-end gap-2">
        <Button variant="ghost" className="text-destructive" onClick={onRemove}>
          <Trash2 /> Quitar
        </Button>
        <Button variant="outline" onClick={runTest} disabled={test.isPending}>
          {test.isPending ? <Loader2 className="animate-spin" /> : <Printer />} Imprimir prueba
        </Button>
      </div>
    </div>
  )
}

function PrintersForm({ initial }: { initial: PrintingConfigOut }) {
  const save = useSavePrinting()
  const [cfg, setCfg] = useState<PrintingConfig>(() => toConfig(initial))
  const needsWindows = cfg.printers.some((p) => p.kind === 'windows')
  const windows = useWindowsPrinters(needsWindows)
  const windowsNames = (windows.data ?? []).map((w) => w.name)
  const printerOptions = cfg.printers.filter((p) => p.name.trim())

  const update = (i: number, p: PrinterCfg) => setCfg((c) => ({ ...c, printers: c.printers.map((x, j) => (j === i ? p : x)) }))
  const remove = (i: number) =>
    setCfg((c) => {
      const gone = c.printers[i].id
      return {
        ...c,
        printers: c.printers.filter((_, j) => j !== i),
        cashier_printer: c.cashier_printer === gone ? null : c.cashier_printer,
        stations: Object.fromEntries(Object.entries(c.stations).filter(([, pid]) => pid !== gone)),
      }
    })
  const add = () =>
    setCfg((c) => {
      const p = newPrinter(c.printers.length)
      return { ...c, printers: [...c.printers, p], cashier_printer: c.cashier_printer ?? p.id }
    })
  const onSave = () => {
    const bad = cfg.printers.find((p) => !p.name.trim() || !p.target.trim() || !Number.isFinite(p.chars) || !Number.isFinite(p.port))
    if (bad) return toast.error(`Completá los datos de «${bad.name || 'la impresora'}» (nombre, impresora o IP, caracteres)`)
    save.mutate(cfg, { onSuccess: (c) => setCfg(toConfig(c)) })
  }
  const printerSelect = (value: string | null, onChange: (v: string | null) => void, label: string) => (
    <Select value={value ?? NONE} onValueChange={(v) => onChange(v === NONE ? null : v)}>
      <SelectTrigger className="w-full sm:w-72" aria-label={label}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={NONE}>Ninguna (diálogo de impresión)</SelectItem>
        {printerOptions.map((p) => (
          <SelectItem key={p.id} value={p.id}>
            {p.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )

  return (
    <SettingsCard
      title="Impresoras"
      description="Tickets, cierres Z y comandas directo a la impresora térmica (ESC/POS), sin el diálogo de Windows. Si no hay impresora o falla, se usa el diálogo de impresión de siempre."
      onSave={onSave}
      saving={save.isPending}
    >
      <div className="space-y-3">
        {cfg.printers.length === 0 ? (
          <EmptyState
            icon={Printer}
            title="Sin impresoras térmicas"
            description="Agregá la impresora de la caja (USB instalada en Windows o de red por IP)."
          />
        ) : (
          cfg.printers.map((p, i) => (
            <PrinterEditor
              key={p.id}
              p={p}
              onChange={(np) => update(i, np)}
              onRemove={() => remove(i)}
              windowsNames={windowsNames}
              loadingWindows={windows.isFetching}
              onReloadWindows={() => windows.refetch()}
            />
          ))
        )}
        <Button variant="outline" onClick={add} disabled={cfg.printers.length >= 20}>
          <Plus /> Agregar impresora
        </Button>
      </div>

      <div className="space-y-4 border-t pt-5">
        <Field label="Impresora de la caja" hint="Imprime los tickets y el cierre Z, y abre el cajón.">
          {printerSelect(cfg.cashier_printer, (v) => setCfg((c) => ({ ...c, cashier_printer: v })), 'Impresora de la caja')}
        </Field>
        <Field label="Ticket después de cada venta" hint={MODES.find((m) => m.value === cfg.ticket_mode)?.hint}>
          <ToggleGroup
            type="single"
            variant="outline"
            value={cfg.ticket_mode}
            onValueChange={(v) => v && setCfg((c) => ({ ...c, ticket_mode: v as TicketMode }))}
          >
            {MODES.map((m) => (
              <ToggleGroupItem key={m.value} value={m.value} className="px-3">
                {m.label}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        </Field>
        <SwitchRow
          title="Abrir el cajón en ventas en efectivo"
          description="El cajón va conectado a la impresora de la caja. No se abre al reimprimir."
          control={
            <div className="flex items-center gap-3">
              {cfg.cash_drawer && (
                <Select value={String(cfg.drawer_pin)} onValueChange={(v) => setCfg((c) => ({ ...c, drawer_pin: v === '1' ? 1 : 0 }))}>
                  <SelectTrigger className="w-28" aria-label="Conector del cajón">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="0">Pin 2</SelectItem>
                    <SelectItem value="1">Pin 5</SelectItem>
                  </SelectContent>
                </Select>
              )}
              <Switch
                checked={cfg.cash_drawer}
                onCheckedChange={(v) => setCfg((c) => ({ ...c, cash_drawer: v }))}
                aria-label="Abrir el cajón en ventas en efectivo"
              />
            </div>
          }
        />
      </div>

      <div className="space-y-3 border-t pt-5">
        <div>
          <p className="font-medium">Comandas por estación</p>
          <p className="text-sm text-muted-foreground">
            Cuando llega un pedido a una estación con «Imprimir comanda» (Configuración → Pedidos), sale solo por su impresora,
            aunque su pantalla esté cerrada.
          </p>
        </div>
        {initial.station_list.length === 0 ? (
          <p className="rounded-xl bg-muted/50 p-3 text-sm text-muted-foreground">
            Las estaciones (barra, cocina) son parte de Pedidos avanzados. Sin estaciones, las comandas se imprimen desde la
            pantalla de pedidos con el diálogo de impresión.
          </p>
        ) : (
          initial.station_list.map((st) => (
            <div key={st.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border p-3">
              <div>
                <p className="font-medium">{st.name}</p>
                <p className="text-xs text-muted-foreground">
                  {st.print_tickets ? 'Imprime comanda de cada pedido' : '«Imprimir comanda» desactivado en Pedidos'}
                </p>
              </div>
              {printerSelect(
                cfg.stations[String(st.id)] ?? null,
                (v) =>
                  setCfg((c) => {
                    const stations = { ...c.stations }
                    if (v) stations[String(st.id)] = v
                    else delete stations[String(st.id)]
                    return { ...c, stations }
                  }),
                `Impresora de ${st.name}`,
              )}
            </div>
          ))
        )}
      </div>
    </SettingsCard>
  )
}

export function PrintersSection() {
  const config = usePrintingConfig()
  if (config.isLoading || !config.data) return config.error ? <p className="text-sm text-destructive">{config.error.message}</p> : <CardSkeleton />
  if (!config.data.available) {
    return (
      <SettingsCard title="Impresoras">
        <div className="rounded-xl border border-warning/40 bg-warning/10 p-4 text-sm" data-testid="printing-unavailable">
          {config.data.reason}
        </div>
      </SettingsCard>
    )
  }
  return <PrintersForm key={JSON.stringify(toConfig(config.data))} initial={config.data} />
}
