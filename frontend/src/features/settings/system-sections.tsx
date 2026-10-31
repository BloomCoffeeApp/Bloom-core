import {
  AlertTriangle,
  Database,
  Download,
  ExternalLink,
  HardDrive,
  History,
  Loader2,
  Plus,
  RotateCcw,
  Scale,
  Wifi,
  WifiOff,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import { toast } from 'sonner'

import { ConfirmDialog } from '@/components/confirm-dialog'
import { type ColumnDef, DataTable } from '@/components/data-table'
import { EmptyState } from '@/components/empty-state'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import { fmtDateTime, fmtNumber, fmtPct, fmtRelative } from '@/lib/format'

import {
  downloadBackup,
  useBackups,
  useCreateBackup,
  useLanQr,
  usePaymentMethods,
  useUpdatePaymentMethod,
  useRestoreBackup,
  useSaveSetting,
  useSystemInfo,
} from './api'
import { Field, NumberInput, SettingsCard, SwitchRow } from './form'
import type { BackupRow, BackupSettings, PaymentMethod, RestoreResult } from './types'
import { Logo } from '@/components/logo'
import { useHasFeature } from '@/features/license/api'
import { BRAND } from '@/lib/brand'

export function fmtBytes(n: number | null | undefined) {
  if (n == null) return '—'
  if (n < 1024) return `${n} B`
  if (n < 1024 ** 2) return `${fmtNumber(n / 1024, 1)} KB`
  if (n < 1024 ** 3) return `${fmtNumber(n / 1024 ** 2, 1)} MB`
  return `${fmtNumber(n / 1024 ** 3, 2)} GB`
}

const LABEL: Record<string, { text: string; variant: 'default' | 'secondary' | 'outline' }> = {
  manual: { text: 'Manual', variant: 'default' },
  auto: { text: 'Automático', variant: 'secondary' },
  'pre-restore': { text: 'Antes de restaurar', variant: 'outline' },
  'pre-migracion': { text: 'Antes de actualizar', variant: 'outline' },
}

export function BackupSection({ settings }: { settings: BackupSettings }) {
  const backups = useBackups(true)
  const info = useSystemInfo(true)
  const create = useCreateBackup()
  const restore = useRestoreBackup()
  const saveCfg = useSaveSetting('backup', 'Respaldo automático guardado')
  const [cfg, setCfg] = useState(settings)
  const [toRestore, setToRestore] = useState<BackupRow | null>(null)
  const [restored, setRestored] = useState<RestoreResult | null>(null)
  const [downloading, setDownloading] = useState<string | null>(null)
  const canExport = useHasFeature('backup_export') !== false

  const columns = useMemo<ColumnDef<BackupRow, unknown>[]>(
    () => [
      {
        accessorKey: 'created_at',
        header: 'Fecha',
        cell: ({ row }) => (
          <div>
            <p className="tabular font-medium">{fmtDateTime(row.original.created_at)}</p>
            <p className="text-xs text-muted-foreground">{fmtRelative(row.original.created_at)}</p>
          </div>
        ),
      },
      {
        accessorKey: 'label',
        header: 'Tipo',
        cell: ({ getValue }) => {
          const l = LABEL[getValue<string>()] ?? { text: getValue<string>(), variant: 'outline' as const }
          return <Badge variant={l.variant}>{l.text}</Badge>
        },
      },
      { accessorKey: 'size_bytes', header: 'Tamaño', cell: ({ getValue }) => <span className="tabular">{fmtBytes(getValue<number>())}</span> },
      {
        id: 'actions',
        header: '',
        enableSorting: false,
        cell: ({ row }) => (
          <div className="flex justify-end gap-1">
            <Button
              variant="ghost"
              size="sm"
              disabled={downloading === row.original.name || !canExport}
              title={canExport ? undefined : 'Descargar respaldos es parte de Pro'}
              onClick={async () => {
                setDownloading(row.original.name)
                try {
                  await downloadBackup(row.original.name)
                } catch (e) {
                  toast.error((e as Error).message)
                } finally {
                  setDownloading(null)
                }
              }}
            >
              {downloading === row.original.name ? <Loader2 className="animate-spin" /> : <Download />} Descargar
            </Button>
            <Button variant="ghost" size="sm" className="text-destructive hover:text-destructive" onClick={() => setToRestore(row.original)}>
              <RotateCcw /> Restaurar
            </Button>
          </div>
        ),
      },
    ],
    [downloading],
  )

  return (
    <div className="space-y-4">
      {restored && (
        <div className="flex items-start gap-3 rounded-2xl border border-warning/50 bg-warning/15 p-4">
          <AlertTriangle className="mt-0.5 size-5 shrink-0 text-warning-foreground dark:text-warning" />
          <div className="text-sm">
            <p className="font-medium">{restored.message}</p>
            <p className="text-muted-foreground">
              Antes de restaurar guardamos una copia de seguridad: <span className="font-mono text-xs">{restored.safety_backup}</span>
            </p>
          </div>
        </div>
      )}
      <div className="grid gap-3 sm:grid-cols-3">
        <InfoTile icon={Database} label="Base de datos" value={info.isLoading ? null : fmtBytes(info.data?.db_size_bytes)} />
        <InfoTile icon={History} label="Respaldos guardados" value={info.isLoading ? null : fmtNumber(info.data?.backups_count, 0)} />
        <InfoTile
          icon={HardDrive}
          label="Último respaldo"
          value={info.isLoading ? null : info.data?.last_backup ? fmtRelative(info.data.last_backup.created_at) : 'Nunca'}
        />
      </div>
      <SettingsCard
        title="Respaldos"
        description="Copias completas de la base de datos. Guardalas también en un pendrive o en la nube."
        action={
          <Button onClick={() => create.mutate()} disabled={create.isPending}>
            {create.isPending ? <Loader2 className="animate-spin" /> : <Plus />} Crear respaldo ahora
          </Button>
        }
      >
        {!backups.isLoading && !backups.data?.length ? (
          <EmptyState icon={HardDrive} title="Todavía no hay respaldos" description="Creá el primero con el botón de arriba." />
        ) : (
          <DataTable columns={columns} data={backups.data} loading={backups.isLoading} searchable={false} pageSize={10} />
        )}
        {info.data && (
          <p className="text-xs text-muted-foreground">
            Carpeta de datos: <span className="font-mono">{info.data.data_dir}</span>
          </p>
        )}
      </SettingsCard>
      <SettingsCard
        title="Respaldo automático"
        description="Se hace una copia por día al abrir la app y se conservan las más recientes."
        onSave={() => saveCfg.mutate(cfg)}
        saving={saveCfg.isPending}
        dirty={(cfg.enabled !== settings.enabled || cfg.keep !== settings.keep) && Number.isInteger(cfg.keep) && cfg.keep >= 3 && cfg.keep <= 365}
      >
        <SwitchRow
          title="Respaldo diario"
          description="Recomendado: dejalo siempre activado."
          control={<Switch checked={cfg.enabled} onCheckedChange={(v) => setCfg({ ...cfg, enabled: v })} />}
        />
        <Field label="Cantidad a conservar" htmlFor="bk-keep" hint="Entre 3 y 365. Los más viejos se borran solos." className="max-w-xs">
          <NumberInput id="bk-keep" value={cfg.keep} min={3} max={365} onChange={(v) => setCfg({ ...cfg, keep: v })} suffix="copias" />
        </Field>
      </SettingsCard>
      <ConfirmDialog
        open={!!toRestore}
        onOpenChange={(o) => !o && setToRestore(null)}
        title="¿Restaurar este respaldo?"
        destructive
        confirmLabel="Sí, restaurar"
        description={
          toRestore && (
            <>
              Se van a reemplazar <strong>todos los datos actuales</strong> por los del respaldo del{' '}
              <strong>{fmtDateTime(toRestore.created_at)}</strong>. Antes guardamos una copia automática del estado actual. Después
              vas a tener que cerrar y volver a abrir la app.
            </>
          )
        }
        onConfirm={() => {
          if (!toRestore) return
          const name = toRestore.name
          setToRestore(null)
          restore.mutate(name, {
            onSuccess: (r) => {
              setRestored(r)
              toast.success('Respaldo restaurado. Reiniciá la app.', { duration: 10_000 })
            },
          })
        }}
      />
    </div>
  )
}

function InfoTile({ icon: Icon, label, value }: { icon: typeof Database; label: string; value: string | null }) {
  return (
    <div className="flex items-center gap-3 rounded-2xl border bg-card p-4">
      <div className="flex size-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
        <Icon className="size-5" />
      </div>
      <div className="min-w-0">
        <p className="text-xs text-muted-foreground">{label}</p>
        {value == null ? <Skeleton className="mt-1 h-5 w-20" /> : <p className="tabular truncate font-semibold">{value}</p>}
      </div>
    </div>
  )
}

export function NetworkSection({ initialEnabled }: { initialEnabled: boolean }) {
  const info = useSystemInfo(true)
  const save = useSaveSetting('network', 'Modo red local actualizado')
  const [enabled, setEnabled] = useState(initialEnabled)
  const [changed, setChanged] = useState(false)
  const qr = useLanQr(enabled && !!info.data?.lan_url)
  const url = info.data?.lan_url
  return (
    <div className="space-y-4">
      <SettingsCard title="Red local" description="Usá la app desde una tablet o celular conectados al mismo Wi-Fi.">
        <SwitchRow
          title="Modo red local"
          description="Permite que otros dispositivos de tu red abran la app."
          control={
            <Switch
              checked={enabled}
              disabled={save.isPending}
              onCheckedChange={(v) =>
                save.mutate(
                  { lan_enabled: v },
                  {
                    onSuccess: () => {
                      setEnabled(v)
                      setChanged(true)
                    },
                  },
                )
              }
            />
          }
        />
        {changed && (
          <div className="flex items-start gap-3 rounded-xl border border-warning/50 bg-warning/15 p-3 text-sm">
            <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning-foreground dark:text-warning" />
            Para que el cambio tome efecto, cerrá y volvé a abrir la aplicación.
          </div>
        )}
        {info.isLoading ? (
          <Skeleton className="h-40 w-full rounded-xl" />
        ) : !url ? (
          <EmptyState icon={WifiOff} title="No encontramos una red local" description="Conectá esta computadora a un Wi-Fi o a un cable de red." />
        ) : (
          <div className="grid items-center gap-6 sm:grid-cols-[auto_1fr]">
            <div className="flex size-44 items-center justify-center overflow-hidden rounded-2xl border bg-white p-2">
              {!enabled ? (
                <WifiOff className="size-10 text-muted-foreground" />
              ) : qr.data ? (
                <img src={qr.data} alt={`Código QR para abrir ${url}`} className="size-full" />
              ) : qr.isError ? (
                <span className="text-center text-xs text-muted-foreground">Sin QR</span>
              ) : (
                <Skeleton className="size-full" />
              )}
            </div>
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                {enabled ? <Wifi className="size-5 text-success" /> : <WifiOff className="size-5 text-muted-foreground" />}
                <span className="font-medium">{enabled ? 'Escaneá el QR desde la tablet' : 'Activá el modo red local para compartir'}</span>
              </div>
              <div className="rounded-xl bg-muted p-3">
                <p className="text-xs text-muted-foreground">Dirección para la tablet</p>
                <p className="font-mono text-lg font-semibold select-all">{url}</p>
              </div>
              {info.data && info.data.lan_ips.length > 1 && (
                <p className="text-xs text-muted-foreground">Otras IP de este equipo: {info.data.lan_ips.slice(1).join(', ')}</p>
              )}
              <p className="text-xs text-muted-foreground">
                Si no abre, revisá que el firewall de Windows permita conexiones al puerto {info.data?.port}.
              </p>
            </div>
          </div>
        )}
      </SettingsCard>
    </div>
  )
}

export function PaymentMethodsSection({ query }: { query: ReturnType<typeof usePaymentMethods> }) {
  const update = useUpdatePaymentMethod()
  const columns: ColumnDef<PaymentMethod, unknown>[] = [
    { accessorKey: 'name', header: 'Medio de pago', cell: ({ getValue }) => <span className="font-medium">{getValue<string>()}</span> },
    { accessorKey: 'code', header: 'Código', cell: ({ getValue }) => <span className="font-mono text-xs text-muted-foreground">{getValue<string>()}</span> },
    { accessorKey: 'surcharge_pct', header: 'Recargo', cell: ({ getValue }) => <span className="tabular">{getValue<number>() ? fmtPct(getValue<number>()) : '—'}</span> },
    {
      accessorKey: 'active',
      header: 'Habilitado',
      enableSorting: false,
      cell: ({ row }) => (
        <div className="flex items-center gap-2">
          <Switch
            checked={row.original.active}
            disabled={update.isPending}
            onCheckedChange={(active) => update.mutate({ id: row.original.id, active })}
            aria-label={`Habilitar ${row.original.name}`}
          />
          {!row.original.active && <Badge variant="outline">Oculto en el cobro</Badge>}
        </div>
      ),
    },
  ]
  return (
    <SettingsCard
      title="Medios de pago"
      description="Los habilitados aparecen al cobrar en el punto de venta. Siempre tiene que quedar al menos uno."
    >
      <DataTable columns={columns} data={query.data} loading={query.isLoading} searchable={false} />
    </SettingsCard>
  )
}

export function AboutSection({ isAdmin }: { isAdmin: boolean }) {
  const info = useSystemInfo(isAdmin)
  return (
    <SettingsCard title="Acerca de">
      <div className="flex flex-col items-center gap-3 py-4 text-center">
        <Logo className="size-16 rounded-2xl shadow-sm" />
        <div>
          <p className="font-heading text-2xl font-semibold">{BRAND.name}</p>
          <p className="text-sm text-muted-foreground">{BRAND.description}</p>
        </div>
        {info.data && <Badge variant="secondary">Versión {info.data.version}</Badge>}
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="flex items-start gap-3 rounded-xl border p-4">
          <Scale className="mt-0.5 size-5 text-muted-foreground" />
          <div className="text-sm">
            <p className="font-medium">Licencia MIT</p>
            <p className="text-muted-foreground">Software libre: podés usarlo, modificarlo y compartirlo.</p>
          </div>
        </div>
        <div className="flex items-start gap-3 rounded-xl border p-4">
          <ExternalLink className="mt-0.5 size-5 text-muted-foreground" />
          <div className="text-sm">
            <p className="font-medium">Tus datos son tuyos</p>
            <p className="text-muted-foreground">Todo se guarda en esta computadora. No se envía nada a internet.</p>
          </div>
        </div>
      </div>
      <p className="text-center text-xs text-muted-foreground">
        Hecho con FastAPI, SQLite, React, Tailwind, shadcn/ui y Recharts.
      </p>
    </SettingsCard>
  )
}
