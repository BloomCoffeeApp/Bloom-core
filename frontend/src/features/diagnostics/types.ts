/** Mirrors backend app/services/diagnostics.py (and the closed schema of the license server). */
export interface DiagnosticError {
  ts: string
  kind: string
  message: string
}

export interface Diagnostic {
  os: string
  app_version: string
  db_ok: boolean | null
  db_size_mb: number | null
  last_backup_at: string | null
  backups: number | null
  printer: { configured: boolean; last_ok: boolean | null } | null
  license: { state: string; plan: string | null; expires: string | null } | null
  modules: string[]
  errors: DiagnosticError[]
  uptime_hours: number | null
}

export interface DiagnosticPreview {
  /** false when this install has no support server (demo, or no server configured). */
  available: boolean
  reason: string | null
  diagnostic: Diagnostic
  /** The license token goes along (support sees whose it is); otherwise the diagnostic is anonymous. */
  includes_license: boolean
}

export interface DiagnosticSent {
  support_code: string
}
