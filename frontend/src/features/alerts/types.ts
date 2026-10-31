export type Severity = 'critical' | 'warning' | 'info'
export type AlertStatus = 'open' | 'read' | 'resolved'
export type AlertFilter = 'active' | 'open' | 'read' | 'resolved' | 'all'

export interface Alert {
  id: number
  type: string
  severity: Severity
  title: string
  message: string | null
  link: string | null
  entity: string | null
  entity_id: number | null
  status: AlertStatus
  created_at: string
  resolved_at: string | null
}

export interface AlertSummary {
  open: number
  critical: number
  read: number
  warning: number
  info: number
}

export type NoticeColor = 'amber' | 'rose' | 'sky' | 'emerald' | 'violet' | 'stone'

export interface Notice {
  id: number
  title: string
  body: string | null
  pinned: boolean
  color: NoticeColor
  expires_at: string | null
  author_id: number | null
  author_name: string | null
  created_at: string
  updated_at: string
  expired: boolean
}

export interface NoticeInput {
  title: string
  body: string | null
  pinned: boolean
  color: NoticeColor
  expires_at: string | null
}

export type ChecklistKind = 'opening' | 'closing' | 'custom'

export interface ChecklistItem {
  id: number
  text: string
  sort_order: number
}

export interface Checklist {
  id: number
  name: string
  kind: ChecklistKind
  active: boolean
  items: ChecklistItem[]
}

export interface ChecklistInput {
  name: string
  kind: ChecklistKind
  active?: boolean
  items: { id?: number; text: string }[]
}

export interface RunItem {
  item_id: number
  text: string
  done: boolean
  done_by: number | null
  done_by_name: string | null
  done_at: string | null
}

export interface ChecklistRun {
  checklist_id: number
  name: string
  kind: ChecklistKind
  run_id: number | null
  started_at: string | null
  started_by_name: string | null
  completed_at: string | null
  done: number
  total: number
  items: RunItem[]
}
