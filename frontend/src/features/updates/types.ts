/** Mirrors backend app/schemas/updates.py */
export type UpdateState = 'idle' | 'checking' | 'downloading' | 'verifying' | 'installing' | 'ready' | 'error'

export interface UpdateInfo {
  version: string
  notes: string
  published_at: string
  size: number
}

export interface UpdateStatus {
  current_version: string
  configured: boolean
  state: UpdateState
  available: boolean
  latest: UpdateInfo | null
  checked_at: string | null
  error: string | null
  message: string | null
  progress: { downloaded: number; total: number }
  can_install: boolean
}
