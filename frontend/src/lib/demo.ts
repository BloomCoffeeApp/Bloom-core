/** Online demo flag (server started with BLOOM_DEMO=1), set by the demo banner from /api/health.
 * Printed documents read it to add the DEMO watermark; it's never on in the desktop app. */
let demo = false

export const setDemoMode = (on: boolean) => {
  demo = on
}
export const isDemoMode = () => demo

/** Watermark for printed documents of the demo: a diagonal "DEMO" behind everything + a top line. */
export const DEMO_PRINT_CSS = `
  body { position: relative; }
  .demo-mark { position: fixed; inset: 0; display: flex; align-items: center; justify-content: center; pointer-events: none; z-index: 0; }
  .demo-mark span { transform: rotate(-35deg); font: 700 64px/1 system-ui, sans-serif; color: rgba(0,0,0,.14); letter-spacing: 6px; }
  .demo-top { border: 2px solid black; text-align: center; font-weight: 700; padding: 3px; margin-bottom: 6px; position: relative; z-index: 1; }
`
export const DEMO_PRINT_HTML =
  '<div class="demo-mark" aria-hidden="true"><span>DEMO</span></div><div class="demo-top">DEMO · datos de ejemplo · no válido</div>'
