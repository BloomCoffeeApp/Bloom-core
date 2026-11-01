import { Info, Megaphone, TriangleAlert, X } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

import { type Announcement, useRemoteConfig } from './api'

const STORAGE_KEY = 'bloom.dismissedAnnouncements'

function readDismissed(): number[] {
  try {
    const raw = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '[]')
    return Array.isArray(raw) ? raw.filter((n): n is number => typeof n === 'number') : []
  } catch {
    return []
  }
}

function saveDismissed(ids: number[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(ids.slice(-100)))
  } catch {
    /* private mode / storage full: it just shows again next time */
  }
}

const STYLE: Record<Announcement['level'], { className: string; icon: typeof Info }> = {
  info: { className: 'bg-primary/10', icon: Megaphone },
  warning: { className: 'bg-warning/15', icon: Info },
  critical: { className: 'bg-destructive/10', icon: TriangleAlert },
}

/** Messages from the vendor (remote config), under the header; each one can be closed and stays closed. */
export function AnnouncementsBanner() {
  const { data } = useRemoteConfig()
  const [dismissed, setDismissed] = useState(readDismissed)
  const visible = (data?.announcements ?? []).filter((a) => !dismissed.includes(a.id))
  if (!visible.length) return null
  const dismiss = (id: number) => {
    const next = [...dismissed, id]
    setDismissed(next)
    saveDismissed(next)
  }
  return (
    <div className="divide-y border-b" data-testid="announcements">
      {visible.map((a) => {
        const { className, icon: Icon } = STYLE[a.level] ?? STYLE.info
        return (
          <div key={a.id} className={cn('flex items-start gap-2 px-4 py-2 text-sm', className)} role="status">
            <Icon className="mt-0.5 size-4 shrink-0" />
            <div className="min-w-0 flex-1">
              <span className="font-medium">{a.title}</span>
              {a.body && <span className="whitespace-pre-line text-muted-foreground"> — {a.body}</span>}
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="-my-1 size-8 shrink-0"
              aria-label={`Cerrar aviso: ${a.title}`}
              onClick={() => dismiss(a.id)}
            >
              <X />
            </Button>
          </div>
        )
      })}
    </div>
  )
}
