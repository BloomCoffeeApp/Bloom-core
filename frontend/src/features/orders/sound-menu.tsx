import { Bell, BellOff, Play, Volume2, VolumeX } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'

import { ProBadge } from '../license/pro-gate'
import { CHANNEL_LABEL, type Channel } from '../sales/types'
import {
  notificationsSupported,
  playSound,
  requestNotifications,
  type SoundId,
  type SoundPrefs,
  SOUNDS,
  unlockAudio,
} from './sound'

const CHANNELS: Channel[] = ['salon', 'llevar', 'delivery']

function SoundSelect({ id, value, onChange, allowDefault }: { id: string; value: SoundId | ''; onChange: (v: SoundId | '') => void; allowDefault?: boolean }) {
  return (
    <Select value={value || 'default'} onValueChange={(v) => onChange(v === 'default' ? '' : (v as SoundId))}>
      <SelectTrigger id={id} className="h-11 w-full">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {allowDefault && <SelectItem value="default">Igual que el general</SelectItem>}
        {SOUNDS.map((s) => (
          <SelectItem key={s.id} value={s.id}>
            {s.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

/** Per-device alert settings of the order screen. */
export function SoundMenu({ prefs, onChange, pro }: { prefs: SoundPrefs; onChange: (p: SoundPrefs) => void; pro: boolean }) {
  const perm = notificationsSupported() ? Notification.permission : 'denied'
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" className="h-11" aria-label="Sonido y avisos">
          {prefs.muted ? <VolumeX /> : <Volume2 />}
          <span className="hidden sm:inline">Sonido</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 space-y-4">
        <div className="flex items-center justify-between gap-3">
          <Label htmlFor="snd-muted">Silenciar</Label>
          <Switch id="snd-muted" checked={prefs.muted} onCheckedChange={(muted) => onChange({ ...prefs, muted })} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="snd-main">Sonido de pedido nuevo</Label>
          <div className="flex gap-2">
            <SoundSelect id="snd-main" value={prefs.sound} onChange={(v) => onChange({ ...prefs, sound: (v || 'campana') as SoundId })} />
            <Button
              variant="outline"
              className="size-11 shrink-0"
              aria-label="Probar sonido"
              onClick={async () => {
                await unlockAudio()
                playSound(prefs.sound)
              }}
            >
              <Play />
            </Button>
          </div>
        </div>
        <div className="space-y-2">
          <p className="flex items-center gap-2 text-sm font-medium">
            Un sonido por canal {!pro && <ProBadge />}
          </p>
          {CHANNELS.map((c) =>
            pro ? (
              <div key={c} className="grid grid-cols-[6.5rem_1fr] items-center gap-2">
                <Label htmlFor={`snd-${c}`} className="text-muted-foreground">
                  {CHANNEL_LABEL[c]}
                </Label>
                <SoundSelect
                  id={`snd-${c}`}
                  allowDefault
                  value={prefs.perChannel[c] ?? ''}
                  onChange={(v) => onChange({ ...prefs, perChannel: { ...prefs.perChannel, [c]: v || undefined } })}
                />
              </div>
            ) : null,
          )}
          {!pro && <p className="text-xs text-muted-foreground">Con Pedidos avanzados elegís un sonido distinto para salón, para llevar y delivery.</p>}
        </div>
        <div className="space-y-2 border-t pt-3">
          <div className="flex items-center justify-between gap-3">
            <Label htmlFor="snd-notify" className="flex items-center gap-2">
              {prefs.notify ? <Bell className="size-4" /> : <BellOff className="size-4" />} Avisos del sistema
            </Label>
            <Switch
              id="snd-notify"
              checked={prefs.notify && perm === 'granted'}
              disabled={perm === 'denied'}
              onCheckedChange={async (on) => {
                const ok = on ? await requestNotifications() : false
                onChange({ ...prefs, notify: on && ok })
              }}
            />
          </div>
          <p className="text-xs text-muted-foreground">
            {perm === 'denied'
              ? 'Este navegador o equipo bloqueó los avisos. Habilitalos desde su configuración.'
              : 'Muestra un aviso de Windows cuando llega un pedido, se atrasa o llaman al mozo.'}
          </p>
        </div>
      </PopoverContent>
    </Popover>
  )
}
