/** Mirrors backend app/routers/account.py. */
export interface AccountSummary {
  email: string | null
  business_name: string | null
  name: string | null
  linked_at: number | null
}

export interface AccountInfo {
  linked: boolean
  account: AccountSummary | null
  server_configured: boolean
}

export interface LinkConfirmResult extends AccountInfo {
  /** started | existing | used | has_license (from the license server). */
  trial_status: string | null
  trial_started: boolean
}

export interface EmailCategory {
  key: 'news' | 'updates' | 'transactional'
  label: string
  description: string
  locked: boolean
}

export type EmailPreferences =
  | { available: false; reason: string }
  | {
      available: true
      email: string | null
      business_name: string | null
      preferences: { news: boolean; updates: boolean; transactional: true }
      categories: EmailCategory[]
    }

/** POST /account/delete/start (license server masks the email). */
export interface DeleteStartResult {
  ok: boolean
  email: string
  expires_in: number
}

export interface DeleteConfirmResult extends AccountInfo {
  deleted: boolean
  /** What the server keeps by law (anonymized billing, trial hash). */
  retained: string[]
}
