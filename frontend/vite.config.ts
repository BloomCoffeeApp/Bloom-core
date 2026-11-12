import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, type Plugin } from 'vite'

// Branding (name, colors, port) comes from /brand.json — the single source of truth.
const root = path.resolve(import.meta.dirname, '..')

// Pro edition when the private modules are linked (../pro/scripts/link.ps1), Free otherwise.
const PRO_INDEX = path.resolve(import.meta.dirname, './src/pro/index.ts')
const PRO_ENTRY = existsSync(PRO_INDEX) ? PRO_INDEX : path.resolve(import.meta.dirname, './src/pro-stub.ts')
const brand = JSON.parse(readFileSync(path.join(root, 'brand.json'), 'utf-8'))
const apiPort = Number(process.env.CAFE_PORT ?? brand.port)

function brandHtml(): Plugin {
  return {
    name: 'brand-html',
    transformIndexHtml: (html) =>
      html
        .replaceAll('%APP_NAME%', brand.name)
        .replaceAll('%APP_DESCRIPTION%', brand.description ?? '')
        .replaceAll('%THEME_COLOR%', brand.colors?.primary ?? '#8B5A2B'),
  }
}

// Installable app (PWA) for phones/tablets on the shop's Wi-Fi (LAN mode).
// - /manifest.webmanifest: always (dev and build), from brand.json.
// - /sw.js: build only, from pwa/sw.template.js with a build id and the shell file list.
// The worker is registered only in secure contexts (localhost / https) and never inside the
// desktop window (src/lib/pwa.ts). Over plain http on the LAN the manifest alone still allows
// "Agregar a la pantalla principal".
function manifest() {
  const c = brand.colors ?? {}
  return {
    name: brand.name,
    short_name: brand.name,
    description: brand.description ?? '',
    lang: 'es-AR',
    start_url: '/',
    scope: '/',
    display: 'standalone',
    orientation: 'any',
    background_color: c.background ?? '#FAF7F2',
    theme_color: c.primary ?? '#8B5A2B',
    icons: [
      { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
      { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
      { src: '/icons/maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
    ],
  }
}

function pwa(): Plugin {
  const body = () => JSON.stringify(manifest(), null, 2)
  return {
    name: 'bloom-pwa',
    configureServer(server) {
      server.middlewares.use('/manifest.webmanifest', (_req, res) => {
        res.setHeader('Content-Type', 'application/manifest+json')
        res.end(body())
      })
    },
    generateBundle(_opts, bundle) {
      this.emitFile({ type: 'asset', fileName: 'manifest.webmanifest', source: body() })
      const files = Object.keys(bundle).filter((f) => f.startsWith('assets/') && !f.endsWith('.map'))
      const shell = ['/index.html', '/manifest.webmanifest', '/logo.svg', '/icons/icon-192.png', '/icons/icon-512.png',
        '/icons/maskable-512.png', '/icons/apple-touch-icon.png', ...files.map((f) => `/${f}`)]
      const buildId = `${brand.version}-${Date.now().toString(36)}`
      const template = readFileSync(path.resolve(import.meta.dirname, 'pwa/sw.template.js'), 'utf-8')
      this.emitFile({
        type: 'asset',
        fileName: 'sw.js',
        source: template.replace('__BUILD_ID__', buildId).replace('__PRECACHE__', JSON.stringify(shell)),
      })
    },
  }
}

// Records which npm packages end up in the production bundle, so build/third_party_notices.py
// lists exactly those (not every devDependency). CSS @imports handled by Tailwind are read
// from src/index.css by the script itself.
function bundledPackages(): Plugin {
  return {
    name: 'bundled-packages',
    apply: 'build',
    generateBundle() {
      const names = new Set<string>()
      for (const id of this.getModuleIds()) {
        const norm = id.replaceAll('\\', '/')
        const at = norm.lastIndexOf('/node_modules/')
        if (at < 0) continue
        const parts = norm.slice(at + '/node_modules/'.length).split('/')
        names.add(parts[0].startsWith('@') ? `${parts[0]}/${parts[1]}` : parts[0])
      }
      const out = path.resolve(import.meta.dirname, 'node_modules/.cache/bloom')
      mkdirSync(out, { recursive: true })
      writeFileSync(path.join(out, 'bundled-packages.json'), JSON.stringify([...names].sort(), null, 2))
    },
  }
}

export default defineConfig({
  plugins: [react(), tailwindcss(), brandHtml(), bundledPackages(), pwa()],
  define: { __BRAND__: JSON.stringify(brand) },
  // The e2e suite runs its own Vite next to the dev server; a separate cache avoids clashes.
  cacheDir: process.env.VITE_CACHE_DIR ?? 'node_modules/.vite',
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, './src'), '@pro': PRO_ENTRY },
    // Pro modules are a junction into the private repo: keep their paths under src/ so
    // they resolve node_modules from here.
    preserveSymlinks: true,
  },
  server: {
    port: 5173,
    // Dev server stays on localhost; set VITE_LAN=1 to test from a tablet on the LAN.
    host: process.env.VITE_LAN === '1',
    // /uploads: product photos are served by the backend too.
    proxy: { '/api': `http://127.0.0.1:${apiPort}`, '/uploads': `http://127.0.0.1:${apiPort}` },
  },
  build: { chunkSizeWarningLimit: 1500 },
})
