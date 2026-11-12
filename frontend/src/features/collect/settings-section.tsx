import { Copy, ExternalLink, Info, Loader2, Monitor, Plus, RefreshCw, Trash2 } from 'lucide-react'
import { Suspense, useState } from 'react'
import { toast } from 'sonner'

import { ConfirmDialog } from '@/components/confirm-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { proModules } from '@pro'

import { UpgradeCard } from '../license/pro-gate'
import { useHasFeature } from '../license/api'
import { CardSkeleton, Field, NumberInput, SettingsCard, SwitchRow } from '../settings/form'
import { useCollectStatus, useSaveCollectConfig, useScreenMutations, useScreens } from './api'
import type { CollectStatus, CustomerScreen, TransferInfo } from './types'

/** Configuración → Cobros (Pro `payments`): the cafe collects into ITS OWN accounts. */
export function CollectSettingsSection() {
  const licensed = useHasFeature('payments')
  const status = useCollectStatus()
  if (licensed === false) return <UpgradeCard feature="payments" compact />
  if (!status.data) return <CardSkeleton />
  return (
    <div className="space-y-6">
      <HowItWorks />
      <ProviderCard status={status.data} />
      <TransferCard key={JSON.stringify(status.data.transfer)} initial={status.data.transfer} />
      <ScreensCard status={status.data} />
    </div>
  )
}

function HowItWorks() {
  return (
    <SettingsCard title="Cobros con QR, posnet y transferencia" description="La plata va directo a la cuenta de tu local: Bloom no toca tu dinero.">
      <div className="flex gap-3 rounded-xl bg-info/10 p-4 text-sm" data-testid="collect-interop-note">
        <Info className="mt-0.5 size-5 shrink-0 text-info" />
        <div className="space-y-2">
          <p>
            <strong>QR de Mercado Pago:</strong> el QR con el monto es interoperable en Argentina. Tu cliente lo puede pagar con
            Mercado Pago o con la app de su banco o billetera (MODO, Santander y otros bancos, Naranja X, Ualá…). Para{' '}
            <strong>recibir</strong> la plata, el local necesita una cuenta de Mercado Pago.
          </p>
          <p>
            <strong>Si solo tenés cuenta en un banco</strong>, usá «Transferencia»: en la pantalla del cliente aparece tu alias o
            CBU/CVU y el cajero confirma «Pago recibido» cuando ve la plata.
          </p>
          <p className="text-muted-foreground">
            Sin conexión a internet desde el exterior: la app consulta el estado del pago cada 2 segundos mientras el cobro está abierto.
          </p>
        </div>
      </div>
    </SettingsCard>
  )
}

function ProviderCard({ status }: { status: CollectStatus }) {
  const save = useSaveCollectConfig()
  const [minutes, setMinutes] = useState(status.expires_minutes)
  const Connect = proModules.MercadoPagoConnect
  return (
    <div className="space-y-6">
      {Connect ? (
        <Suspense fallback={<CardSkeleton />}>
          <Connect />
        </Suspense>
      ) : (
        <UpgradeCard feature="payments" compact notIncluded />
      )}
      <SettingsCard
        title="Opciones del cobro"
        onSave={() => save.mutate({ expires_minutes: minutes })}
        saving={save.isPending}
        dirty={minutes !== status.expires_minutes && Number.isFinite(minutes)}
      >
        <Field label="El QR vence a los" htmlFor="collect-expires" hint="Si el cliente no paga en ese tiempo, el cobro se cancela solo.">
          <NumberInput id="collect-expires" value={minutes} onChange={setMinutes} min={2} max={60} suffix="minutos" className="w-40" />
        </Field>
        {status.fake_allowed && (
          <SwitchRow
            title="Modo de prueba (simulado)"
            description="Para probar el flujo sin Mercado Pago: el cobro se aprueba con «Simular pago». No se cobra de verdad."
            control={
              <Switch
                checked={status.provider === 'fake'}
                disabled={save.isPending}
                onCheckedChange={(on) => save.mutate({ provider: on ? 'fake' : null })}
                aria-label="Modo de prueba"
              />
            }
          />
        )}
      </SettingsCard>
    </div>
  )
}

function TransferCard({ initial }: { initial: TransferInfo }) {
  const save = useSaveCollectConfig()
  const [t, setT] = useState(initial)
  const set = (patch: Partial<TransferInfo>) => setT((x) => ({ ...x, ...patch }))
  const dirty = JSON.stringify(t) !== JSON.stringify(initial)
  return (
    <SettingsCard
      title="Transferencia"
      description="Al elegir «Transferencia» en la caja, el cliente ve estos datos en su pantalla y el cajero confirma «Pago recibido»."
      onSave={() => save.mutate({ transfer: t })}
      saving={save.isPending}
      dirty={dirty}
    >
      <SwitchRow
        title="Mostrar los datos de transferencia al cobrar"
        control={<Switch checked={t.enabled} onCheckedChange={(enabled) => set({ enabled })} aria-label="Mostrar transferencia" />}
      />
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Alias" htmlFor="tr-alias">
          <Input id="tr-alias" value={t.alias} maxLength={40} onChange={(e) => set({ alias: e.target.value })} placeholder="cafe.ejemplo.mp" />
        </Field>
        <Field label="CBU / CVU" htmlFor="tr-cbu">
          <Input id="tr-cbu" value={t.cbu} maxLength={30} inputMode="numeric" onChange={(e) => set({ cbu: e.target.value.replace(/[^0-9 ]/g, '') })} />
        </Field>
        <Field label="Titular" htmlFor="tr-holder">
          <Input id="tr-holder" value={t.holder} maxLength={80} onChange={(e) => set({ holder: e.target.value })} />
        </Field>
        <Field label="Banco o billetera" htmlFor="tr-bank">
          <Input id="tr-bank" value={t.bank} maxLength={60} onChange={(e) => set({ bank: e.target.value })} />
        </Field>
        <Field label="CUIT (opcional)" htmlFor="tr-cuit">
          <Input id="tr-cuit" value={t.cuit} maxLength={20} onChange={(e) => set({ cuit: e.target.value })} />
        </Field>
      </div>
    </SettingsCard>
  )
}

function ScreenRow({ s, isDefault, onDefault }: { s: CustomerScreen; isDefault: boolean; onDefault: () => void }) {
  const m = useScreenMutations()
  const [confirmDelete, setConfirmDelete] = useState(false)
  const link = s.url ?? `${window.location.origin}${s.path}`
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(link)
      toast.success('Link copiado')
    } catch {
      toast.error('No se pudo copiar: seleccioná el link a mano')
    }
  }
  return (
    <li className="flex flex-col gap-3 rounded-xl border p-4 sm:flex-row sm:items-center" data-testid={`screen-${s.id}`}>
      {s.qr_png && <img src={s.qr_png} alt={`QR para abrir ${s.name}`} className="size-28 shrink-0 rounded-lg border bg-white p-1" />}
      <div className="min-w-0 flex-1 space-y-1">
        <p className="flex flex-wrap items-center gap-2 font-medium">
          <Monitor className="size-4" /> {s.name}
          {isDefault && <Badge variant="secondary">Predeterminada</Badge>}
          {s.last_seen_at ? <Badge variant="outline">Conectada</Badge> : <Badge variant="outline">Nunca abierta</Badge>}
        </p>
        <p className="truncate font-mono text-xs text-muted-foreground" title={link}>
          {link}
        </p>
        {!s.url && <p className="text-xs text-muted-foreground">Para abrirla en una tablet activá el modo red local (Configuración → Red local).</p>}
      </div>
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" className="h-11" onClick={copy}>
          <Copy /> Copiar link
        </Button>
        <Button variant="outline" className="h-11" asChild>
          <a href={s.path} target="_blank" rel="noreferrer">
            <ExternalLink /> Abrir
          </a>
        </Button>
        {!isDefault && (
          <Button variant="ghost" className="h-11" onClick={onDefault}>
            Usar por defecto
          </Button>
        )}
        <Button variant="ghost" size="icon-lg" className="size-11" aria-label="Cambiar el link" title="Cambiar el link (el anterior deja de andar)"
          onClick={() => m.update.mutate({ id: s.id, rotate: true })}>
          <RefreshCw />
        </Button>
        <Button variant="ghost" size="icon-lg" className="size-11" aria-label={`Quitar ${s.name}`} onClick={() => setConfirmDelete(true)}>
          <Trash2 />
        </Button>
      </div>
      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title={`¿Quitar «${s.name}»?`}
        description="Esa pantalla deja de mostrar los cobros. Podés volver a agregarla cuando quieras."
        confirmLabel="Quitar"
        destructive
        onConfirm={() => m.remove.mutate(s.id)}
      />
    </li>
  )
}

function ScreensCard({ status }: { status: CollectStatus }) {
  const screens = useScreens()
  const m = useScreenMutations()
  const save = useSaveCollectConfig()
  const [name, setName] = useState('')
  const add = () => {
    if (!name.trim()) return
    m.create.mutate(name.trim(), { onSuccess: () => setName('') })
  }
  return (
    <SettingsCard
      title="Pantallas del cliente"
      description="Una tablet o TV en el mostrador que le muestra al cliente su compra, el total y el QR para pagar. Abrí el link en esa pantalla (misma red Wi-Fi)."
    >
      <div className="flex gap-2">
        <Input
          value={name}
          maxLength={60}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && add()}
          placeholder="Ej.: Tablet del mostrador"
          aria-label="Nombre de la pantalla"
          className="h-11"
        />
        <Button className="h-11" onClick={add} disabled={!name.trim() || m.create.isPending}>
          {m.create.isPending ? <Loader2 className="animate-spin" /> : <Plus />} Agregar pantalla
        </Button>
      </div>
      {screens.data && screens.data.length > 0 ? (
        <ul className="space-y-3">
          {screens.data.map((s) => (
            <ScreenRow
              key={s.id}
              s={s}
              isDefault={status.default_screen_id === s.id}
              onDefault={() => save.mutate({ default_screen_id: s.id })}
            />
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">Todavía no registraste pantallas. El cobro se puede mostrar igual en la caja.</p>
      )}
    </SettingsCard>
  )
}
