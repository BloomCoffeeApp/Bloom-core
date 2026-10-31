import { Bell, ClipboardCheck, StickyNote } from 'lucide-react'
import { Route, Routes, useSearchParams } from 'react-router'

import { PageHeader } from '@/components/page-header'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { cn } from '@/lib/utils'

import { AlertsTab } from './AlertsTab'
import { useAlertSummary, useChecklistsToday } from './api'
import { ChecklistsTab } from './ChecklistsTab'
import { NoticesTab } from './NoticesTab'

const TABS = ['alertas', 'tablon', 'checklists'] as const
type Tab = (typeof TABS)[number]

function AvisosPage() {
  const [params, setParams] = useSearchParams()
  const raw = params.get('tab')
  const tab: Tab = TABS.includes(raw as Tab) ? (raw as Tab) : 'alertas'
  const { data: summary } = useAlertSummary()
  const { data: runs } = useChecklistsToday()
  const pendingChecklists = runs?.filter((r) => r.total > 0 && r.done < r.total).length ?? 0

  const setTab = (t: string) => {
    const next = new URLSearchParams(params)
    if (t === 'alertas') next.delete('tab')
    else next.set('tab', t)
    setParams(next, { replace: true })
  }

  return (
    <div>
      <PageHeader title="Avisos" description="Alertas automáticas, tablón del equipo y checklists del día." />
      <Tabs value={tab} onValueChange={setTab} className="gap-5">
        <TabsList className="h-11 w-full max-w-xl">
          <TabsTrigger value="alertas" className="gap-2">
            <Bell /> Alertas
            {!!summary?.open && (
              <Badge
                className={cn(
                  'tabular h-5 min-w-5 rounded-full px-1.5',
                  summary.critical ? 'bg-destructive text-white' : '',
                )}
              >
                {summary.open}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="tablon" className="gap-2">
            <StickyNote /> Tablón
          </TabsTrigger>
          <TabsTrigger value="checklists" className="gap-2">
            <ClipboardCheck /> Checklists
            {pendingChecklists > 0 && (
              <Badge variant="secondary" className="tabular h-5 min-w-5 rounded-full px-1.5">
                {pendingChecklists}
              </Badge>
            )}
          </TabsTrigger>
        </TabsList>
        <TabsContent value="alertas">
          <AlertsTab />
        </TabsContent>
        <TabsContent value="tablon">
          <NoticesTab />
        </TabsContent>
        <TabsContent value="checklists">
          <ChecklistsTab />
        </TabsContent>
      </Tabs>
    </div>
  )
}

export default function AlertsModule() {
  return (
    <Routes>
      <Route index element={<AvisosPage />} />
      <Route path="*" element={<AvisosPage />} />
    </Routes>
  )
}
