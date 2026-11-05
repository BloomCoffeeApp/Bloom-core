import { CheckCircle2, Loader2, Mail, Unlink } from 'lucide-react'
import { useState } from 'react'

import { ConfirmDialog } from '@/components/confirm-dialog'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

import { CardSkeleton, Field, SettingsCard } from '../settings/form'
import { useAccount, useLinkConfirm, useLinkStart, useUnlink } from './api'
import { DataRightsCard } from './data-rights-card'

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/

/** Configuración → Cuenta: optional link of this installation to the vendor account (email → code). */
export function AccountSection() {
  const account = useAccount()
  if (!account.data) return <CardSkeleton />
  const info = account.data
  const main = !info.server_configured ? (
    <SettingsCard title="Cuenta" description="Vinculá esta computadora a tu cuenta de Bloom.">
      <p className="text-sm text-muted-foreground" data-testid="account-unavailable">
        Esta instalación no tiene servidor configurado, así que no hace falta una cuenta. Bloom funciona igual, sin
        internet.
      </p>
    </SettingsCard>
  ) : info.linked && info.account ? (
    <LinkedCard email={info.account.email} business={info.account.business_name} />
  ) : (
    <LinkForm />
  )
  return (
    <div className="space-y-6">
      {main}
      <DataRightsCard serverConfigured={info.server_configured} />
    </div>
  )
}

function LinkedCard({ email, business }: { email: string | null; business: string | null }) {
  const unlink = useUnlink()
  const [confirm, setConfirm] = useState(false)
  return (
    <SettingsCard
      title="Cuenta"
      description="Esta computadora está vinculada a tu cuenta de Bloom."
      footer={
        <Button variant="outline" className="h-9" onClick={() => setConfirm(true)} disabled={unlink.isPending}>
          <Unlink />
          Desvincular
        </Button>
      }
    >
      <div className="flex items-start gap-3 rounded-xl border bg-primary/5 p-4">
        <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-primary" />
        <div className="min-w-0">
          <p className="font-medium break-all">{email}</p>
          {business && <p className="text-sm text-muted-foreground">{business}</p>}
        </div>
      </div>
      <p className="text-sm text-muted-foreground">
        Elegí qué mails querés recibir en <span className="font-medium text-foreground">Notificaciones</span>.
      </p>
      <ConfirmDialog
        open={confirm}
        onOpenChange={setConfirm}
        title="¿Desvincular esta computadora?"
        description="Bloom sigue funcionando igual (la licencia no cambia). Podés volver a vincularla cuando quieras."
        confirmLabel="Desvincular"
        destructive
        onConfirm={() => unlink.mutate()}
      />
    </SettingsCard>
  )
}

function LinkForm() {
  const start = useLinkStart()
  const confirm = useLinkConfirm()
  const [email, setEmail] = useState('')
  const [terms, setTerms] = useState(false)
  const [news, setNews] = useState(false)
  const [code, setCode] = useState('')
  const [sentTo, setSentTo] = useState<string | null>(null)
  const validEmail = EMAIL_RE.test(email.trim())

  if (sentTo) {
    return (
      <SettingsCard
        title="Revisá tu mail"
        description={`Te mandamos un código de 6 dígitos a ${sentTo}. Vence en 15 minutos.`}
        footer={
          <>
            <Button variant="ghost" className="h-9" onClick={() => { setSentTo(null); setCode(''); confirm.reset() }}>
              Cambiar email
            </Button>
            <Button
              className="h-9 px-4"
              disabled={code.length !== 6 || confirm.isPending}
              onClick={() => confirm.mutate({ email: sentTo, code })}
            >
              {confirm.isPending && <Loader2 className="animate-spin" />}
              Vincular
            </Button>
          </>
        }
      >
        <Field label="Código" htmlFor="acc-code" hint="Si no llega en unos minutos, revisá la carpeta de spam.">
          <Input
            id="acc-code"
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
            inputMode="numeric"
            autoComplete="one-time-code"
            placeholder="000000"
            className="h-11 max-w-40 text-center font-mono text-lg tracking-[0.4em]"
          />
        </Field>
        {confirm.error && <p className="text-sm text-destructive" role="alert">{confirm.error.message}</p>}
      </SettingsCard>
    )
  }

  return (
    <SettingsCard
      title="Cuenta"
      description="Opcional: vinculá esta computadora a tu cuenta de Bloom para elegir qué mails recibís y, si es tu primera vez, probar Pro gratis. Sin cuenta, Bloom funciona igual."
      footer={
        <Button
          className="h-9 px-4"
          disabled={!validEmail || !terms || start.isPending}
          onClick={() =>
            start.mutate(
              { email: email.trim(), accept_terms: true, marketing_opt_in: news },
              { onSuccess: () => setSentTo(email.trim().toLowerCase()) },
            )
          }
        >
          {start.isPending ? <Loader2 className="animate-spin" /> : <Mail />}
          Mandarme el código
        </Button>
      }
    >
      <Field label="Tu email" htmlFor="acc-email" hint="El mismo con el que creaste la cuenta en la web (o uno nuevo: la creamos).">
        <Input id="acc-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="vos@ejemplo.com" className="max-w-sm" />
      </Field>
      <div className="space-y-3">
        <div className="flex items-start gap-2.5">
          <Checkbox id="acc-terms" checked={terms} onCheckedChange={(v) => setTerms(v === true)} className="mt-0.5" />
          <Label htmlFor="acc-terms" className="leading-snug font-normal">Acepto los términos y la política de privacidad de Bloom.</Label>
        </div>
        <div className="flex items-start gap-2.5">
          <Checkbox id="acc-news" checked={news} onCheckedChange={(v) => setNews(v === true)} className="mt-0.5" />
          <Label htmlFor="acc-news" className="leading-snug font-normal">Quiero recibir novedades y promociones por mail (opcional).</Label>
        </div>
      </div>
      {start.error && <p className="text-sm text-destructive" role="alert">{start.error.message}</p>}
    </SettingsCard>
  )
}
