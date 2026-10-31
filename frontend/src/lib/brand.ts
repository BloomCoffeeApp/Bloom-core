/** App branding injected at build time from /brand.json (see vite.config.ts). */
export interface Brand {
  name: string
  tagline: string
  description: string
  appId: string
  colors: { primary: string; accent: string; background: string }
}

declare const __BRAND__: Brand

export const BRAND: Brand = __BRAND__
