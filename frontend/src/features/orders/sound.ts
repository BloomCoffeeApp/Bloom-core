/**
 * Order screen alerts: chimes generated with the Web Audio API (no audio files) and system
 * notifications (Notification API; in the desktop app WebView2 shows them as Windows toasts).
 *
 * Browsers only start audio after a user gesture: `unlockAudio()` must run from a click
 * ("Activar sonido"). Preferences are per device (each tablet decides), in localStorage.
 */
import type { Channel } from '../sales/types'

export type SoundId = 'campana' | 'dingdong' | 'marimba' | 'bip'
export type AlertKind = 'new' | 'late' | 'call' | 'paid'

export const SOUNDS: { id: SoundId; label: string }[] = [
  { id: 'campana', label: 'Campanita' },
  { id: 'dingdong', label: 'Ding-dong' },
  { id: 'marimba', label: 'Marimba' },
  { id: 'bip', label: 'Bip triple' },
]

export interface SoundPrefs {
  muted: boolean
  sound: SoundId
  /** Pro (`orders_pro`): a different sound per channel. */
  perChannel: Partial<Record<Channel, SoundId>>
  notify: boolean
}

const KEY = 'bloom.orders.sound.v1'
const DEFAULTS: SoundPrefs = { muted: false, sound: 'campana', perChannel: {}, notify: true }

export function loadPrefs(): SoundPrefs {
  try {
    const raw = localStorage.getItem(KEY)
    return raw ? { ...DEFAULTS, ...(JSON.parse(raw) as Partial<SoundPrefs>) } : DEFAULTS
  } catch {
    return DEFAULTS
  }
}

export function savePrefs(p: SoundPrefs) {
  try {
    localStorage.setItem(KEY, JSON.stringify(p))
  } catch {
    /* private mode: preferences last until reload */
  }
}

let ctx: AudioContext | null = null

function audio(): AudioContext | null {
  if (typeof window === 'undefined' || !('AudioContext' in window)) return null
  ctx ??= new AudioContext()
  return ctx
}

export const audioReady = () => ctx?.state === 'running'

/** Call from a click handler: resumes the AudioContext (autoplay policy). */
export async function unlockAudio(): Promise<boolean> {
  const c = audio()
  if (!c) return false
  try {
    await c.resume()
  } catch {
    return false
  }
  return c.state === 'running'
}

type Note = [freq: number, start: number, dur: number, type?: OscillatorType, gain?: number]

const PATTERNS: Record<SoundId, Note[]> = {
  campana: [
    [1318.5, 0, 1.2, 'sine', 0.35],
    [1975.5, 0, 0.8, 'sine', 0.12],
    [1568, 0.18, 1.3, 'sine', 0.3],
  ],
  dingdong: [
    [987.8, 0, 0.9, 'triangle', 0.4],
    [784, 0.42, 1.2, 'triangle', 0.4],
  ],
  marimba: [
    [523.3, 0, 0.35, 'sine', 0.4],
    [659.3, 0.12, 0.35, 'sine', 0.4],
    [784, 0.24, 0.35, 'sine', 0.4],
    [1046.5, 0.36, 0.6, 'sine', 0.35],
  ],
  bip: [
    [1760, 0, 0.12, 'square', 0.12],
    [1760, 0.2, 0.12, 'square', 0.12],
    [1760, 0.4, 0.12, 'square', 0.12],
  ],
}

// Late orders: a lower, insistent pattern so it can't be mistaken for a new order.
const LATE: Note[] = [
  [440, 0, 0.3, 'sawtooth', 0.12],
  [349.2, 0.32, 0.3, 'sawtooth', 0.12],
  [440, 0.64, 0.3, 'sawtooth', 0.12],
  [349.2, 0.96, 0.45, 'sawtooth', 0.12],
]
// Waiter call / bill: two quick high pings.
const CALL: Note[] = [
  [2093, 0, 0.25, 'sine', 0.3],
  [2637, 0.15, 0.4, 'sine', 0.3],
  [2093, 0.6, 0.25, 'sine', 0.3],
  [2637, 0.75, 0.4, 'sine', 0.3],
]

// A table paid everything from the phones: three short rising notes (different from the call ping and the late buzz).
const PAID: Note[] = [
  [659.3, 0, 0.18, 'sine', 0.3],
  [830.6, 0.14, 0.18, 'sine', 0.3],
  [987.8, 0.28, 0.5, 'sine', 0.3],
]

function playNotes(notes: Note[]) {
  const c = audio()
  if (!c || c.state !== 'running') return
  const t0 = c.currentTime + 0.02
  for (const [freq, start, dur, type = 'sine', gain = 0.3] of notes) {
    const osc = c.createOscillator()
    const g = c.createGain()
    osc.type = type
    osc.frequency.value = freq
    // Soft attack + exponential decay = bell-like, no clicks.
    g.gain.setValueAtTime(0.0001, t0 + start)
    g.gain.exponentialRampToValueAtTime(gain, t0 + start + 0.01)
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + start + dur)
    osc.connect(g).connect(c.destination)
    osc.start(t0 + start)
    osc.stop(t0 + start + dur + 0.05)
  }
}

export function playSound(id: SoundId) {
  playNotes(PATTERNS[id] ?? PATTERNS.campana)
}

export function playAlert(kind: AlertKind, prefs: SoundPrefs, channel?: Channel, pro = false) {
  if (prefs.muted) return
  if (kind === 'late') return playNotes(LATE)
  if (kind === 'call') return playNotes(CALL)
  if (kind === 'paid') return playNotes(PAID)
  const id = (pro && channel && prefs.perChannel[channel]) || prefs.sound
  playSound(id)
}

export const notificationsSupported = () => typeof window !== 'undefined' && 'Notification' in window

export async function requestNotifications(): Promise<boolean> {
  if (!notificationsSupported()) return false
  if (Notification.permission === 'granted') return true
  if (Notification.permission === 'denied') return false
  return (await Notification.requestPermission()) === 'granted'
}

export function notify(title: string, body: string, prefs: SoundPrefs, tag?: string) {
  if (!prefs.notify || !notificationsSupported() || Notification.permission !== 'granted') return
  try {
    const n = new Notification(title, { body, tag, silent: true }) // our chime already played
    n.onclick = () => {
      window.focus()
      n.close()
    }
  } catch {
    /* some webviews expose the API but refuse to construct notifications */
  }
}
