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
  plugins: [react(), tailwindcss(), brandHtml(), bundledPackages()],
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
