import { ChevronLeft, ChevronRight, X } from 'lucide-react'
import { type ReactNode, useCallback, useEffect, useLayoutEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { useLocation, useNavigate } from 'react-router'

import { Button } from '@/components/ui/button'
import { useModules } from '@/features/business/api'
import { useAuth } from '@/lib/auth'
import { NAV } from '@/lib/nav'
import { cn } from '@/lib/utils'

import { TOUR_STEPS, type TourStep } from './steps'
import { TourContext } from './use-tour'

const doneKey = (userId: number) => `bloom.tour.done.${userId}`

function readDone(userId: number) {
  try {
    return localStorage.getItem(doneKey(userId)) === '1'
  } catch {
    return true // no storage: don't nag on every login
  }
}

function writeDone(userId: number) {
  try {
    localStorage.setItem(doneKey(userId), '1')
  } catch {
    /* storage unavailable */
  }
}

/** Mount once inside the router; auto-starts the first time each user logs in. */
export function TourProvider({ children }: { children: ReactNode }) {
  const { user, can } = useAuth()
  const [index, setIndex] = useState<number | null>(null)

  const modules = useModules()
  const steps = useMemo(
    () =>
      TOUR_STEPS.filter((s) => {
        if (s.roles?.length && !can(...s.roles)) return false
        // Sections hidden for this business type aren't in the sidebar: skip their step.
        const item = s.target?.startsWith('nav-') ? NAV.find((n) => `nav-${n.to}` === s.target) : undefined
        return !item?.module || modules.on(item.module)
      }),
    [can, modules],
  )

  const start = useCallback(() => setIndex(0), [])
  const finish = useCallback(() => {
    if (user) writeDone(user.id)
    setIndex(null)
  }, [user])

  useEffect(() => {
    if (!user || readDone(user.id)) return
    const t = setTimeout(() => setIndex((i) => i ?? 0), 800)
    return () => clearTimeout(t)
  }, [user])

  const value = useMemo(() => ({ start }), [start])
  return (
    <TourContext.Provider value={value}>
      {children}
      {index != null && steps[index] && (
        <TourOverlay
          step={steps[index]}
          index={index}
          total={steps.length}
          onPrev={() => setIndex((i) => Math.max(0, (i ?? 0) - 1))}
          onNext={() => (index + 1 >= steps.length ? finish() : setIndex(index + 1))}
          onClose={finish}
        />
      )}
    </TourContext.Provider>
  )
}

interface Rect {
  top: number
  left: number
  width: number
  height: number
}

const PAD = 6
const CARD_W = 340
const GAP = 14

/** Tracks the target's viewport rect; null while missing or hidden (e.g. collapsed mobile menu). */
function useTargetRect(target: string | undefined, routeKey: string) {
  // Measurements are tagged with the target/route they belong to, so a stale rect from the
  // previous step is never returned (instead of resetting it to null inside the effect).
  const key = `${target ?? ''}|${routeKey}`
  const [measured, setMeasured] = useState<{ key: string; rect: Rect | null }>({ key, rect: null })
  useLayoutEffect(() => {
    if (!target) return
    let el: Element | null = null
    let frame = 0
    let tries = 0
    const measure = () => {
      if (!el) return
      const r = el.getBoundingClientRect()
      setMeasured({ key, rect: r.width && r.height ? { top: r.top, left: r.left, width: r.width, height: r.height } : null })
    }
    // The target may appear a little later (lazy routes, sidebar animation).
    const find = () => {
      el = document.querySelector(`[data-tour="${CSS.escape(target)}"]`)
      if (el) {
        el.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
        measure()
      } else if (tries++ < 60) frame = requestAnimationFrame(find)
    }
    find()
    const ro = new ResizeObserver(measure)
    const observe = setInterval(() => el && (ro.observe(el), clearInterval(observe)), 100)
    window.addEventListener('resize', measure)
    window.addEventListener('scroll', measure, true)
    // Sidebar collapse/expand animates; keep up with it.
    const tick = setInterval(measure, 250)
    return () => {
      cancelAnimationFrame(frame)
      clearInterval(observe)
      clearInterval(tick)
      ro.disconnect()
      window.removeEventListener('resize', measure)
      window.removeEventListener('scroll', measure, true)
    }
  }, [target, key])
  return measured.key === key ? measured.rect : null
}

function cardPosition(rect: Rect | null, cardH: number) {
  const vw = window.innerWidth
  const vh = window.innerHeight
  const w = Math.min(CARD_W, vw - 32)
  if (!rect || vw < 640) {
    return rect && vw < 640
      ? { left: 16, top: rect.top + rect.height + GAP + cardH < vh ? rect.top + rect.height + GAP : 16, width: w }
      : { left: (vw - w) / 2, top: Math.max(16, (vh - cardH) / 2), width: w }
  }
  const clampTop = (t: number) => Math.min(Math.max(16, t), vh - cardH - 16)
  const clampLeft = (l: number) => Math.min(Math.max(16, l), vw - w - 16)
  // Right of the target (sidebar items), else below, else above, else left.
  if (rect.left + rect.width + GAP + w < vw - 16)
    return { left: rect.left + rect.width + GAP + PAD, top: clampTop(rect.top + rect.height / 2 - cardH / 2), width: w }
  if (rect.top + rect.height + GAP + cardH < vh - 16)
    return { left: clampLeft(rect.left + rect.width / 2 - w / 2), top: rect.top + rect.height + GAP + PAD, width: w }
  if (rect.top - GAP - cardH > 16)
    return { left: clampLeft(rect.left + rect.width / 2 - w / 2), top: rect.top - GAP - PAD - cardH, width: w }
  return { left: clampLeft(rect.left - GAP - PAD - w), top: clampTop(rect.top), width: w }
}

function TourOverlay({
  step,
  index,
  total,
  onPrev,
  onNext,
  onClose,
}: {
  step: TourStep
  index: number
  total: number
  onPrev: () => void
  onNext: () => void
  onClose: () => void
}) {
  const location = useLocation()
  const navigate = useNavigate()
  const [cardH, setCardH] = useState(200)
  const [card, setCard] = useState<HTMLDivElement | null>(null)

  useEffect(() => {
    if (step.route && location.pathname !== step.route) navigate(step.route)
  }, [step.route, location.pathname, navigate])

  const rect = useTargetRect(step.target, location.pathname)

  // Track the card's height (it changes with each step's text) to position it.
  useLayoutEffect(() => {
    if (!card) return
    const ro = new ResizeObserver(() => setCardH(card.offsetHeight))
    ro.observe(card)
    return () => ro.disconnect()
  }, [card])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
      else if (e.key === 'ArrowRight' || e.key === 'Enter') onNext()
      else if (e.key === 'ArrowLeft') onPrev()
      else return
      e.preventDefault()
      e.stopPropagation()
    }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [onClose, onNext, onPrev])

  const hole = rect && {
    top: rect.top - PAD,
    left: rect.left - PAD,
    width: rect.width + PAD * 2,
    height: rect.height + PAD * 2,
  }
  const pos = cardPosition(rect, cardH)
  const veil = 'fixed bg-background/60 backdrop-blur-[3px] transition-all duration-300 ease-out'

  return createPortal(
    <div className="fixed inset-0 z-[100]" role="dialog" aria-modal="true" aria-labelledby="tour-title">
      {hole ? (
        <>
          {/* Four panels around the target: everything else is dimmed and blurred. */}
          <div className={veil} style={{ top: 0, left: 0, right: 0, height: Math.max(0, hole.top) }} />
          <div className={veil} style={{ top: hole.top + hole.height, left: 0, right: 0, bottom: 0 }} />
          <div className={veil} style={{ top: hole.top, left: 0, width: Math.max(0, hole.left), height: hole.height }} />
          <div className={veil} style={{ top: hole.top, left: hole.left + hole.width, right: 0, height: hole.height }} />
          {/* Blocks clicks on the target so the tour can't be left half-way. */}
          <div
            className="fixed rounded-xl ring-2 ring-primary transition-all duration-300 ease-out"
            style={hole}
          >
            <span className="absolute inset-0 animate-ping rounded-xl ring-2 ring-primary/60 [animation-duration:1.6s]" />
          </div>
        </>
      ) : (
        <div className={cn(veil, 'inset-0')} />
      )}

      <div
        ref={setCard}
        className="fixed rounded-2xl border bg-popover p-5 text-popover-foreground shadow-2xl transition-all duration-300 ease-out"
        style={pos}
      >
        <button
          onClick={onClose}
          className="absolute top-3 right-3 rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
          aria-label="Cerrar tutorial"
        >
          <X className="size-4" />
        </button>
        <p className="text-xs font-medium text-primary">
          Paso {index + 1} de {total}
        </p>
        <h2 id="tour-title" className="mt-1 pr-6 font-heading text-lg font-semibold">
          {step.title}
        </h2>
        <p className="mt-1.5 text-sm text-muted-foreground">{step.body}</p>
        <div className="mt-4 flex gap-1" aria-hidden>
          {Array.from({ length: total }).map((_, i) => (
            <span
              key={i}
              className={cn('h-1 flex-1 rounded-full transition-colors', i <= index ? 'bg-primary' : 'bg-muted')}
            />
          ))}
        </div>
        <div className="mt-4 flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={onClose} className="text-muted-foreground">
            Saltar
          </Button>
          <div className="ml-auto flex gap-2">
            {index > 0 && (
              <Button variant="outline" size="sm" onClick={onPrev}>
                <ChevronLeft /> Anterior
              </Button>
            )}
            <Button size="sm" onClick={onNext} autoFocus>
              {index + 1 >= total ? 'Terminar' : 'Siguiente'}
              {index + 1 < total && <ChevronRight />}
            </Button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  )
}
