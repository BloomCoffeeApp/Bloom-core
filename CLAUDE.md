# CLAUDE.md — Bloom (antes Cafetería ControlApp)

App de gestión para cafetería (POS, caja, stock, compras, clientes, alertas, reportes) + módulo de asistencia al barista.
**El plan completo y las fases están en `PLAN.md`. Leerlo antes de trabajar y tildar checkboxes al avanzar.**

## Stack
- Backend: Python 3.13, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, SQLite (WAL). Carpeta `backend/`.
- Frontend: React 19 + TS + Vite, Tailwind v4, shadcn/ui, TanStack Query/Table, React Router 7, RHF + Zod, Recharts. Carpeta `frontend/`.
- Escritorio: `launcher.py` levanta Uvicorn en un hilo y abre pywebview. Empaquetado con PyInstaller (onedir) + Inno Setup.

## Comandos
- Dev (todo junto): `./scripts/dev.ps1`
- Backend tests: `cd backend; .venv\Scripts\python -m pytest`
- Front: `cd frontend; npm run dev | npm run build | npx tsc -b | npm run lint`
- E2E (Playwright + Edge, stack aislado en puertos 47899/5199 con DB temporal): `cd frontend; npm run e2e` (`e2e:headed`, `e2e:ui`). Specs en `frontend/e2e/`.
- Modo demo online (`BLOOM_DEMO=1`, ignorado en el .exe): `backend/app/demo/`, una base SQLite por visitante;
  tests `tests/test_demo.py` y `npm run e2e:demo` (puertos 48071/5371). No tocar `get_db` sin revisarlo.
- Nueva migración: `cd backend; .venv\Scripts\alembic revision --autogenerate -m "..."` y revisar el archivo generado.
- Build del .exe: `./build/build.ps1`

## Ediciones Free / Pro
- Este repo es la edición **gratuita** (pública). Los módulos Pro (barista, compras, reportes, menú público)
  viven en un repo privado (`../pro`) y se enchufan con `../pro/scripts/link.ps1` como junctions en
  `backend/bloom_pro`, `backend/tests/pro`, `frontend/src/pro`, `frontend/e2e/pro` (todas en `.gitignore`:
  **nunca commitear su contenido acá**).
- Backend: `app.main` importa `bloom_pro` si existe y llama `register(app)`. Frontend: `@pro` resolve a
  `src/pro/index.ts` (Pro) o `src/pro-stub.ts` (Free); la forma está en `src/pro-modules.ts`.
- Licencias: `app/licensing` (token Ed25519 firmado, offline, atado a la PC). Capacidades Pro del core se
  protegen con `require_feature(...)` / `has_feature(...)`; en el front `ProGate`/`ProModule`/`useHasFeature`.
- Todo tiene que funcionar **sin** Pro: correr pytest, `tsc -b`, `npm run build` y `npm run e2e` también con
  `../pro/scripts/unlink.ps1`.

## Repo público
- Nada personal en el repo: datos demo 100% ficticios (`seed.py`), sin emails/teléfonos reales, sin rutas de usuario.
- `.gitignore` excluye `*.db`, backups, uploads, builds y `.env`. Nunca commitear una base de datos.

## Convenciones (obligatorias)
- **Dinero siempre en centavos enteros** (`*_cents`) en DB, API y lógica. Se formatea solo en la UI (`lib/format.ts`, `es-AR`, `ARS`).
- Fechas en UTC en DB; se muestran en `America/Argentina/Buenos_Aires`.
- **La lógica de negocio vive en `backend/app/services/`.** Los routers solo validan, llaman al service y devuelven. Nada de lógica en componentes React más allá de presentación.
- Todo cambio de stock pasa por `stock_service.apply_movement` — nunca actualizar `current_qty` directo.
- Operaciones multi-tabla (ventas, anulaciones, recepciones de compra, cierres de caja) dentro de **una transacción**.
- Todo cambio de schema = migración Alembic. Nunca `create_all` en producción.
- Front: cliente `api` de `src/lib/api.ts`; cada módulo tiene `features/<modulo>/types.ts` (tipos que reflejan los schemas Pydantic) y `api.ts` (hooks de TanStack Query). Si cambiás un schema, actualizá su `types.ts`.
- Componentes por módulo en `src/features/<modulo>/`. Reutilizar `components/` compartidos (DataTable, PageHeader, MoneyInput, StatCard, EmptyState, ConfirmDialog) antes de crear nuevos.
- Colores solo vía tokens del tema (variables CSS de shadcn); no hex sueltos en componentes.
- Textos de UI en **español rioplatense** (vos, “Guardar”, “Cobrar”). Código, nombres de variables y commits en inglés.
- Targets táctiles ≥ 44 px en POS y Barista.
- Tests de pytest para cada regla de la sección 6 de `PLAN.md` y para cada regla de dial-in del barista.

## Al terminar una fase
1. Tests verdes (pytest + vitest; Playwright si la fase lo pide).
2. Levantar la app y verificar el criterio “Listo cuando” de la fase, sin errores en consola.
3. Tildar checkboxes en `PLAN.md`, anotar decisiones nuevas en su sección 9.
4. Commit.
