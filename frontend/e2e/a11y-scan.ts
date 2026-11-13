import AxeBuilder from '@axe-core/playwright'
import type { Page } from '@playwright/test'

/**
 * Accessibility (axe-core, WCAG 2.1 A/AA): every main screen must have no serious or critical violations.
 * Each violation prints its rule, how many elements and a selector + HTML so it can be fixed from the report.
 *
 * `KNOWN` is the accepted backlog: a rule + the elements it is accepted for + why. It is deliberately narrow
 * (never a whole rule), so a NEW problem still fails. The goal is to empty this list; delete entries as fixed.
 */
export const KNOWN: { rule: string; selector: RegExp; why: string }[] = []

export async function scan(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze()
  const out: string[] = []
  for (const v of results.violations) {
    if (v.impact !== 'serious' && v.impact !== 'critical') continue
    const fresh = v.nodes.filter(
      (n) => !KNOWN.some((k) => k.rule === v.id && (n.target.some((t) => k.selector.test(String(t))) || k.selector.test(n.html))),
    )
    if (!fresh.length) continue
    out.push(
      `${v.id} [${v.impact}] x${fresh.length}: ${v.help} -> ` +
        fresh.slice(0, 3).map((n) => `${n.target.join(' ')} <${n.html.slice(0, 110)}>`).join(' | '),
    )
  }
  return out
}

