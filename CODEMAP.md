# CODEMAP — Bloom core (edición gratuita)

Mapa para ubicar código rápido sin recorrer el árbol. Rutas relativas a `core/`. Convenciones en `CLAUDE.md`,
fases y decisiones en `PLAN.md`. Los módulos Pro tienen su propio mapa en el repo privado (`../pro/CODEMAP.md`).
**Actualizalo cuando agregues un módulo, un punto de extensión o muevas algo grande.**

## Arranque y plataforma
| Qué | Dónde |
|---|---|
| App de escritorio (Uvicorn en hilo + pywebview) | `launcher.py`, `desktop_window.py` |
| App FastAPI, registro de routers, carga de `bloom_pro` | `backend/app/main.py` |
| Config (data dir `CAFE_DATA_DIR`, puerto `CAFE_PORT`) | `backend/app/config.py`, `db.py` |
| Migraciones al iniciar (backup previo, recuperación, rollback) | `backend/app/migrate.py`, `alembic/versions/` (head: `0015_collect_payments`) |
| Auth por PIN, `Perm(...)`, `CurrentUser`, `login_throttle` | `backend/app/auth.py` |
| Catálogo de permisos y roles predefinidos | `backend/app/permissions.py`; roles editables `services/roles.py` |
| Licencia Free/Pro (token Ed25519 offline, `require_feature`) | `backend/app/licensing/` (`features.py`, `status.py`, `token.py`, `client.py`) |
| Plan gratis "opción C" (qué queda usable sin licencia) | `services/free_plan.py` |
| Jobs en segundo plano (alertas, backup diario, licencia, updates) | `backend/app/jobs.py` |
| Modo LAN (segundo listener 0.0.0.0) | `backend/app/lan.py` |
| Config remota firmada | `backend/app/remote_config.py` |
| Demo online (una SQLite por visitante, tope 2 h, límites por IP) | `backend/app/demo/` |
| Build .exe + instalador | `build/build.ps1`, `cafeteria.spec`, `installer.iss` |

## Backend por dominio (`backend/app/`)
Patrón: `routers/<x>.py` valida → `services/<x>.py` lógica → `models/<x>.py` tablas, `schemas/<x>.py` Pydantic.

| Dominio | Service (lógica) | Notas |
|---|---|---|
| Catálogo: productos, recetas, tamaños, modificadores | `catalog.py` (787), `recipes.py` | costeo de recetas compartido |
| Insumos por canal (vaso, tapa, bolsa según salón/llevar/delivery) | `channel_supplies.py` | configurable por producto o categoría |
| Ventas / checkout atómico, anulación, ticket | `sales.py` (625) | stock + puntos + cuenta corriente en 1 transacción |
| Hooks del checkout para Pro | `sale_hooks.py` | Free no registra ninguno |
| Caja: apertura, movimientos, arqueo/cierre Z | `cash.py` | |
| Stock: único punto de cambio | `stock.py` → `apply_movement` | **nunca** tocar `current_qty` directo |
| Stock: ítems, kardex, mermas, conteos, sugerencias, paquetes | `stock_ops.py` (629) | descarte rápido con motivos: front `features/stock/discard.tsx` |
| Pedidos (pantalla barra/cocina, mesas, cuentas abiertas) | `orders.py` (890) | entrada única `orders.transition(...)` |
| Máquina de estados por canal (Strategy) | `order_flows.py` | `FLOWS`: caja, mesa, take_away, delivery; API `GET /api/orders/flows` |
| Cobros (QR, Point, links, transferencias, devoluciones) | `collect.py` (922) | protocolo `CollectProvider`; FakeProvider con `BLOOM_COLLECT_FAKE` |
| Credenciales cifradas (DPAPI) | `secret_store.py` | |
| Gastos (categorías, fijos mensuales, pagos, ganancia) | `expenses.py` (661) | Free; el reporte de ganancia es Pro |
| Clientes, cuenta corriente, puntos | `customers.py` | |
| Alertas (motor de reglas) | `alerts_engine.py` | |
| Avisos internos y checklists apertura/cierre | `notices.py` | |
| Dashboard / KPIs (helpers usados por reportes Pro) | `dashboard.py` | |
| Impresión térmica ESC/POS directa | `printing.py`, `escpos.py`, `printers.py` | |
| Perfil de negocio (qué módulos se muestran) | `business_profile.py` | ocultar es solo UI |
| Backups/restore, info del sistema, auditoría | `system.py`, `backup.py`, `audit.py` | restore rechaza bases demo |
| Actualizaciones in-app (manifiesto firmado) | `updates.py` | |
| Fotos de productos | `product_images.py` | |
| Datos demo | `seed.py`, `demo_sales.py` | 100% ficticios |
| Fechas locales | `timeutil.py` | DB en UTC naive |

## Frontend (`frontend/src/`)
- Rutas: `router.tsx`, shell/nav: `components/app-shell.tsx`, `lib/nav.ts`. Cliente HTTP: `lib/api.ts`.
- Auth y permisos en UI: `lib/auth.ts` (`useAuth().can('perm')`), `lib/auth-provider.tsx`, `lib/permissions.ts`.
- Cada módulo: `features/<modulo>/{index.tsx, api.ts (TanStack Query), types.ts}`.
  Módulos: `pos`, `cash`, `sales`, `orders`, `catalog`, `stock`, `customers`, `expenses`, `collect`, `alerts`,
  `dashboard`, `settings` (incluye `roles-section.tsx`, `users-section.tsx`), `license`, `account`, `business`,
  `printing`, `updates`, `remote-config`, `tutorial`, `auth`.
- Compartidos (reusar antes de crear): `components/` → DataTable, PageHeader, MoneyInput, StatCard, EmptyState,
  ConfirmDialog, report-kit. Formato: `lib/format.ts`. PWA: `lib/pwa.ts` + `pwa/sw.template.js`.
- Punto de enchufe Pro: `pro-modules.ts` (forma), `pro-stub.ts` (Free), alias `@pro`; gating `features/license/pro-gate.tsx`.
- POS: `features/pos/` (`cart-panel.tsx`, `checkout-dialog.tsx`, `use-cart.ts`, `modifier-dialog.tsx`).

## Tests
- pytest: `backend/tests/test_<dominio>.py` (conftest con `seeded`, `login(client, nombre, pin)`; usuarios demo:
  Admin, Encargado Demo, Caja Demo). Migraciones: `test_migrate_safety.py`.
- E2E Playwright: `frontend/e2e/<x>.spec.ts` (fixtures/helpers en `fixtures.ts`, `helpers.ts`).

## Puntos de extensión (dónde se enchufa algo nuevo)
- Router nuevo → `app/main.py`. Permiso nuevo → `app/permissions.py` (+ roles por defecto).
- Canal/estado de pedido nuevo → una entrada en `FLOWS` (`order_flows.py`).
- Proveedor de cobro nuevo → implementar `CollectProvider` y `register_handler` (`services/collect.py`).
- Efecto al vender (Pro) → `sale_hooks.py`. Feature con licencia → `licensing/features.py`.
