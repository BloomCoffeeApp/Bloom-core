# Bloom (antes Cafetería ControlApp) — Plan de implementación

> Documento maestro. Lo ejecuta un agente (Sonnet) **fase por fase**, marcando los checkboxes a medida que avanza.
> Idioma de la UI: **español rioplatense**. Moneda por defecto: **ARS**. Zona horaria: **America/Argentina/Buenos_Aires**.

---

## 1. Decisión de stack (y por qué)

| Capa | Elección | Motivo |
|---|---|---|
| Ventana de escritorio | **pywebview** (WebView2 en Windows) | `.exe` liviano, usa el Edge del sistema; no hace falta empaquetar Chromium (Electron pesa 150 MB+). |
| Backend | **Python 3.13 + FastAPI + Uvicorn** | SQLite viene incluido en Python (sin módulos nativos que compilar), PyInstaller lo empaqueta sin dolor, FastAPI genera OpenAPI → tipos TS automáticos. |
| ORM / migraciones | **SQLAlchemy 2.0 + Alembic** | Migraciones versionadas: la DB del cliente se actualiza sola al instalar una versión nueva. |
| Validación | **Pydantic v2** | Esquemas de entrada/salida de la API. |
| DB | **SQLite** (modo WAL) | Un solo archivo, cero instalación, backups = copiar un archivo. |
| Frontend | **React 19 + TypeScript + Vite** | |
| UI | **Tailwind CSS v4 + shadcn/ui + lucide-react** | Look moderno, componentes accesibles, fácil de personalizar. |
| Datos en el front | **TanStack Query** + cliente `fetch` propio (`lib/api.ts`) y tipos por módulo | Cache, reintentos, invalidación. |
| Ruteo | **React Router 7** (modo SPA) | |
| Formularios | Estado de React + validación en el backend (Pydantic) | RHF + Zod se sacaron por no usarse. |
| Tablas | **TanStack Table** (vía DataTable de shadcn) | Orden, filtro, paginación. |
| Gráficos | **Recharts** (charts de shadcn) | |
| Extras UI | **cmdk** (paleta de comandos Ctrl+K), **sonner** (toasts), **date-fns** (locale `es`) | |
| Empaquetado | **PyInstaller** (`--onedir`) + **Inno Setup** para el instalador | `onedir` arranca más rápido que `onefile`. |
| Tests | **pytest** (backend), **Playwright** (flujos e2e) | Vitest se sacó (no había tests de front). |

### Arquitectura clave: servidor local + ventana

```
┌───────────────────────────── CafeteriaApp.exe ─────────────────────────────┐
│  launcher.py                                                               │
│   ├─ hilo: Uvicorn → FastAPI  (http://127.0.0.1:8765)                      │
│   │         ├─ /api/*        → routers → services → SQLAlchemy → SQLite    │
│   │         └─ /*            → sirve el build de React (frontend/dist)     │
│   └─ pywebview.create_window("http://127.0.0.1:8765")                      │
└────────────────────────────────────────────────────────────────────────────┘
          ▲ opcional: "Modo red local" escucha en 0.0.0.0 → tablet de la barra
```

**Por qué así y no pywebview con `js_api`:** al ser un servidor HTTP real, la **misma app sirve para una tablet en la barra o un celular** (módulo barista) entrando por la IP de la PC en la red local, y el día de mañana migrar a web/nube es cambiar dónde corre el backend, no reescribir. Desarrollo = `vite dev` + `uvicorn --reload` como cualquier app web.

---

## 2. Estructura de carpetas

```
Bloom/
├─ PLAN.md                 ← este archivo
├─ CLAUDE.md               ← convenciones para el agente
├─ backend/
│  ├─ pyproject.toml
│  ├─ alembic.ini
│  ├─ app/
│  │  ├─ main.py           ← crea FastAPI, monta routers y estáticos
│  │  ├─ config.py         ← rutas (DB en %APPDATA%\CafeteriaApp), puerto, flags
│  │  ├─ db.py             ← engine, session, PRAGMAs (WAL, foreign_keys=ON)
│  │  ├─ models/           ← un archivo por dominio (sales.py, stock.py, barista.py…)
│  │  ├─ schemas/          ← Pydantic in/out por dominio
│  │  ├─ services/         ← LÓGICA DE NEGOCIO (stock, ventas, caja, alertas…)
│  │  ├─ routers/          ← endpoints finos: validan, llaman al service, devuelven
│  │  ├─ auth.py           ← login por PIN, tokens, dependencia de roles
│  │  ├─ jobs.py           ← tareas periódicas (alertas, backup diario)
│  │  └─ seed.py           ← datos demo
│  ├─ migrations/          ← Alembic
│  └─ tests/
├─ frontend/
│  ├─ package.json
│  ├─ src/
│  │  ├─ main.tsx, App.tsx, router.tsx
│  │  ├─ lib/              ← cliente api, auth, formato, tema, navegación
│  │  ├─ components/ui/    ← shadcn
│  │  ├─ components/       ← compartidos (DataTable, MoneyInput, StatCard, PageHeader…)
│  │  ├─ features/         ← una carpeta por módulo (pos/, stock/, barista/…)
│  │  ├─ lib/              ← formatters (moneda, fechas), utils
│  │  └─ styles/
│  └─ e2e/
├─ launcher.py             ← entrada del .exe
├─ build/                  ← spec de PyInstaller, script Inno Setup, íconos
└─ scripts/                ← setup.ps1, dev.ps1
```

---

## 3. Módulos y funcionalidades

### 3.1 Acceso y usuarios
- Login rápido por **PIN de 4–6 dígitos** con teclado numérico en pantalla (selección de usuario por avatar).
- Roles: **admin**, **encargado**, **cajero**, **barista**. Matriz de permisos en el backend (decorador/dependencia `require_role`).
- Bloqueo automático por inactividad (configurable) → vuelve a la pantalla de PIN.
- Auditoría: quién hizo cada venta, ajuste de stock, anulación, apertura/cierre de caja.

### 3.2 Dashboard (inicio)
- KPIs del día con comparación vs mismo día de la semana anterior: **ventas $**, **cantidad de tickets**, **ticket promedio**, **margen bruto estimado**.
- Gráfico de ventas por hora (hoy vs promedio), ventas últimos 30 días, top 10 productos, mix por medio de pago, mix por categoría.
- Panel de **alertas activas** (stock bajo, caja abierta, vencimientos, cumpleaños).
- Estado de caja actual, últimos tickets, “café del día” / receta de espresso en uso (del módulo barista).
- Selector de rango (hoy / semana / mes / personalizado).

### 3.3 Punto de venta (POS) — prioridad máxima en UX
- Pantalla **táctil-friendly**: grilla de productos por categoría (tiles grandes con color/ícono/foto), buscador, carrito a la derecha.
- **Modificadores** por producto (tamaño, tipo de leche, shot extra, sin azúcar) con precio adicional e impacto opcional en receta/stock.
- Notas por ítem, descuentos por ítem o total (% o $, con permiso), tipo de consumo: **salón / para llevar / delivery**, número de mesa opcional.
- Asociar **cliente** (búsqueda por nombre/teléfono) → suma puntos.
- Cobro con **pago dividido**: efectivo (con cálculo de vuelto), débito, crédito, transferencia, Mercado Pago/QR, cuenta corriente.
- Al confirmar: descuenta stock según recetas (transacción atómica), genera número correlativo.
- Historial de tickets, reimpresión, **anulación** con motivo (reintegra stock, requiere encargado).
- Atajos de teclado (F2 buscar, F9 cobrar, Esc cancelar).
- Ticket imprimible (HTML → impresión del sistema). ESC/POS térmica queda para fase opcional.

### 3.4 Caja
- **Apertura** con monto inicial, **cierre** con arqueo: esperado vs contado por medio de pago, diferencia, observaciones.
- Movimientos manuales: ingresos/egresos de caja (pago a proveedor en efectivo, retiro, etc.).
- Resumen de cierre imprimible (tipo “Z”).
- No se puede vender sin caja abierta.

### 3.5 Productos, insumos y recetas
- **Productos vendibles**: nombre, categoría, precio, foto/color, activo, visible en POS, modificadores.
- **Insumos (stock)**: nombre, unidad base (g, ml, unidad), stock actual, **stock mínimo**, costo promedio ponderado, proveedor habitual, categoría (café, lácteos, descartables, panadería…), vencimiento opcional por lote.
- **Recetas / escandallo**: cada producto consume N insumos (Latte = 18 g café + 200 ml leche + 1 vaso + 1 tapa). → **costo y margen calculados en vivo**.
- Productos “simples” que son a la vez insumo (ej. medialuna comprada → se vende tal cual): flag para que el producto apunte directo a 1 insumo.
- **Actualización masiva de precios** por % (por categoría o todo) — clave con inflación. Historial de precios.

### 3.6 Stock
- Stock calculado como **libro de movimientos** (`stock_movements`) con saldo cacheado en el insumo. Tipos: compra, venta, ajuste, merma/desperdicio, consumo interno, anulación.
- Vista de stock con semáforo (ok / bajo / sin stock), valorización total del inventario.
- **Conteo físico (inventario)**: pantalla para cargar conteo real → genera ajustes por diferencia.
- Registro de **mermas** con motivo (vencido, se cayó, prueba de barista…).
- Sugerencia de compra: insumos bajo mínimo + consumo promedio de los últimos 14 días → cantidad sugerida.

### 3.7 Compras y proveedores
- **Proveedores**: datos de contacto, CUIT, condiciones, insumos que provee, notas.
- **Orden de compra** (borrador → enviada → recibida). Al recibir: ingresa stock y actualiza costo promedio.
- Carga rápida de **factura de compra** sin OC previa.
- Estado de pago (pendiente / pagado parcial / pagado), vencimiento, **cuenta corriente con proveedores**.
- Generar OC desde la “sugerencia de compra” con un clic; exportar/compartir OC (PDF/texto para WhatsApp).

### 3.8 Clientes
- Ficha: nombre, teléfono, email, cumpleaños, notas/preferencias (“latte con leche de avena, sin azúcar”).
- Historial de compras, gasto total, frecuencia, último consumo, producto favorito.
- **Fidelización**: puntos por $ gastado, canje configurable (ej. cada 10 cafés uno gratis).
- **Cuenta corriente** (fiado/empresas): saldo, pagos, límite.
- Segmentos simples: frecuentes, inactivos (+30 días), cumpleañeros del mes.

### 3.9 Alertas y avisos
- **Alertas automáticas** (job cada 5 min + al arrancar):
  - stock bajo / sin stock,
  - vencimientos de lotes en ≤ N días,
  - facturas de proveedor por vencer,
  - caja abierta de un día anterior,
  - cumpleaños de clientes hoy,
  - café con > X días desde tueste o bolsa por terminarse (barista),
  - mantenimiento de equipos (limpieza de grupo, backflush, cambio de filtro de agua, calibración de molino) por fecha o cantidad de shots.
- Campanita en el header con contador, centro de notificaciones, marcar leída/resolver.
- **Tablón de avisos internos** para el equipo (notas fijadas, ej. “hoy llega el proveedor de leche”), con autor y vencimiento.
- **Checklists** de apertura/cierre del local (tildar tareas, queda registro de quién y cuándo).

### 3.10 Módulo Barista ☕ (diferencial)
Pensado para usarse en una **tablet en la barra**: botones grandes, modo oscuro, mínima escritura.

- **Cafés / granos**: nombre, tostador, origen, varietal, proceso, altura, nivel de tueste, **fecha de tueste** (muestra “días desde tueste” y ventana óptima), notas de cata, vinculado al insumo de stock.
- **Equipos**: máquinas (grupos, presión nominal), molinos (tipo de escala: numérica/stepless), con contador de shots y plan de mantenimiento.
- **Recetas objetivo** por café y método: dosis, rendimiento, **ratio**, tiempo objetivo (rango), temperatura, presión, preinfusión, molienda de referencia.
- **Registro de extracción (shot log)** — formulario ultrarrápido:
  - café, molino, **grado de molienda**, dosis (g), rendimiento (g), **tiempo (s)** con **cronómetro integrado** (tap para iniciar/parar y se autocompleta), temperatura (°C), presión (bar), preinfusión (s), TDS y **% extracción** opcional (calculada: `EY = TDS × rendimiento / dosis`), ratio calculado automáticamente.
  - Evaluación sensorial: sliders ácido↔amargo, cuerpo, dulzor, puntaje 1–5, notas libres.
  - Marcar como “✅ calibrado” → pasa a ser la receta del día visible en el dashboard y en la barra.
- **Asistente de calibración (dial-in)**: motor de reglas que compara el shot con la receta objetivo y sugiere el próximo ajuste, ej.:
  - rápido + ácido → “molé más fino (≈1–2 puntos)”;
  - lento + amargo/astringente → “molé más grueso”;
  - en tiempo pero ácido → “subí temperatura 1 °C o aumentá ratio”;
  - en tiempo pero amargo → “bajá temperatura o acortá ratio”;
  - canalización reportada → checklist de distribución/tampeo.
  Las reglas viven en un archivo de configuración editable, no hardcodeadas en componentes.
- **Gráficos**: tiempo vs molienda por café, evolución del puntaje, historial de calibraciones por día (ver cómo “se mueve” el café con los días de tueste).
- **Métodos de filtrado** (V60, Chemex, Aeropress, prensa francesa, Cold brew): recetas con **pasos cronometrados** (bloom 0:00–0:45, vertido hasta 150 g…), calculadora de ratio (ingresás g de café o ml de agua → calcula el resto).
- **Calculadoras**: ratio, EY, conversión de recetas a N tazas.
- **Bitácora del barista**: notas del día, problemas de máquina.

### 3.11 Reportes
- Ventas por rango / día / hora / producto / categoría / medio de pago / usuario.
- Rentabilidad por producto (precio − costo de receta), productos menos vendidos.
- Movimientos de stock, mermas valorizadas, compras por proveedor.
- Cierres de caja históricos.
- **Exportar a Excel (.xlsx) y CSV** en todos los reportes.

### 3.12 Configuración
- Datos del negocio (nombre, logo, CUIT, dirección) para tickets.
- Medios de pago habilitados, recargos/descuentos por medio de pago.
- Reglas de fidelización, umbrales de alertas, timeout de bloqueo.
- **Backups**: automático diario (rotación de 30), manual con un clic, restaurar desde archivo.
- “Modo red local” on/off (muestra la IP y un QR para abrir desde la tablet).
- Tema claro/oscuro/sistema.

---

## 4. Modelo de datos (SQLite)

Convenciones: PK `id INTEGER`, `created_at`/`updated_at` en UTC, **dinero en centavos (`INTEGER`)**, cantidades de stock en `NUMERIC`/`REAL` en la unidad base del insumo, borrado lógico con `active`/`deleted_at` donde aplique.

**Acceso**
- `users` (name, pin_hash, role, color, active, last_login_at)
- `audit_log` (user_id, action, entity, entity_id, payload_json, ts)
- `settings` (key PK, value_json)

**Catálogo**
- `product_categories` (name, color, icon, sort_order)
- `products` (category_id, name, price_cents, image_path, color, active, show_in_pos, stock_item_id NULL, sort_order)
- `modifier_groups` (name, min_select, max_select) · `product_modifier_groups` (product_id, group_id)
- `modifiers` (group_id, name, price_delta_cents)
- `modifier_recipe_items` (modifier_id, stock_item_id, qty_delta) — ej. “leche de avena”: −200 ml leche, +200 ml avena
- `recipe_items` (product_id, stock_item_id, qty)
- `price_history` (product_id, old_cents, new_cents, user_id, ts)

**Stock**
- `stock_categories` (name)
- `stock_items` (category_id, name, unit[g|ml|u], current_qty, min_qty, avg_cost_cents_per_unit, default_supplier_id, track_expiry, active)
- `stock_lots` (stock_item_id, qty_remaining, expiry_date, purchase_item_id)
- `stock_movements` (stock_item_id, type, qty (+/−), unit_cost_cents, ref_type, ref_id, reason, user_id, ts)
- `inventory_counts` (status, user_id, ts) · `inventory_count_items` (count_id, stock_item_id, expected_qty, counted_qty)

**Ventas y caja**
- `cash_sessions` (opened_by, opened_at, opening_cents, closed_by, closed_at, notes, status)
- `cash_session_counts` (session_id, payment_method, expected_cents, counted_cents)
- `cash_movements` (session_id, type[in|out], amount_cents, reason, user_id, ts)
- `sales` (number, cash_session_id, user_id, customer_id, channel, table_label, subtotal_cents, discount_cents, total_cents, status[completed|voided], void_reason, voided_by, ts)
- `sale_items` (sale_id, product_id, name_snapshot, qty, unit_price_cents, discount_cents, modifiers_json, notes, cost_cents_snapshot)
- `sale_payments` (sale_id, method, amount_cents, tendered_cents, change_cents)
- `payment_methods` (code, name, active, surcharge_pct)

**Compras**
- `suppliers` (name, cuit, phone, email, address, payment_terms, notes, active)
- `purchase_orders` (supplier_id, status, expected_date, notes, total_cents, created_by)
- `purchases` (supplier_id, purchase_order_id NULL, invoice_number, invoice_date, due_date, total_cents, paid_cents, status)
- `purchase_items` (purchase_id, stock_item_id, qty, unit_cost_cents, expiry_date)
- `supplier_payments` (purchase_id, amount_cents, method, ts)

**Clientes**
- `customers` (name, phone, email, birthday, notes, points, credit_limit_cents, balance_cents, active)
- `loyalty_transactions` (customer_id, points, reason, sale_id, ts)
- `customer_account_movements` (customer_id, amount_cents, type[charge|payment], sale_id, ts)

**Alertas y equipo**
- `alerts` (type, severity, title, message, entity, entity_id, dedupe_key UNIQUE, status[open|read|resolved], created_at, resolved_at)
- `notices` (author_id, title, body, pinned, expires_at)
- `checklists` (name, kind[opening|closing|custom]) · `checklist_items` · `checklist_runs` · `checklist_run_items`

**Barista**
- `coffees` (name, roaster, origin, variety, process, altitude_m, roast_level, roast_date, tasting_notes, stock_item_id, active)
- `equipment` (kind[machine|grinder|other], name, brand, model, grind_scale, shot_counter, notes)
- `maintenance_tasks` (equipment_id, name, every_days NULL, every_shots NULL, last_done_at, last_done_shots)
- `brew_recipes` (coffee_id NULL, method[espresso|v60|chemex|aeropress|french_press|cold_brew], name, dose_g, yield_g, time_min_s, time_max_s, temp_c, pressure_bar, preinfusion_s, grind_ref, steps_json, is_current)
- `shot_logs` (coffee_id, grinder_id, machine_id, recipe_id, user_id, grind_setting, dose_g, yield_g, time_s, temp_c, pressure_bar, preinfusion_s, tds, ey_pct, acidity, bitterness, body, sweetness, score, channeling, notes, is_dialed_in, days_off_roast, ts)
- `barista_journal` (user_id, body, ts)

---

## 5. Diseño visual (UI/UX)

- **Paleta “café”**: fondo crema cálido en claro (`#FAF7F2`), carbón en oscuro (`#17130F`), primario espresso/caramelo (`#8B5A2B` / `#C8874A`), acentos: verde salvia (ok), ámbar (alerta), terracota (error). Definir como **tokens CSS** del tema de shadcn (no colores sueltos en componentes).
- Tipografía: **Inter** (UI) + números tabulares (`font-variant-numeric: tabular-nums`) en montos; títulos en **Fraunces** o similar para un toque “cafetería”.
- Layout: **sidebar colapsable** con íconos (Inicio, POS, Caja, Stock, Compras, Clientes, Barista, Reportes, Avisos, Config) + header con búsqueda global (Ctrl+K), campanita de alertas, usuario activo, botón bloquear.
- Esquinas redondeadas generosas (`rounded-2xl`), sombras suaves, estados vacíos con ilustración/ícono y CTA, skeletons al cargar, toasts en cada acción.
- **Targets táctiles ≥ 44 px** en POS y Barista. Modo “barra” (pantalla completa, fuente grande) para el barista.
- Formateo consistente: `$ 12.345,67`, fechas `30/10/2026 14:05`.
- Accesibilidad: foco visible, contraste AA, todo usable con teclado.

---

## 6. Reglas de negocio críticas (testear sí o sí)

1. **Venta = transacción atómica**: crea sale + items + payments + movimientos de stock por receta (incluyendo modificadores) + puntos del cliente. Si algo falla, no queda nada a medias.
2. Suma de pagos == total (tolerancia 0). Vuelto solo sobre efectivo.
3. **Anulación** revierte stock, puntos y cuenta corriente; no borra la venta.
4. **Costo promedio ponderado** al recibir compras: `nuevo = (stock×costo + qty×costo_compra) / (stock + qty)` (si stock ≤ 0 se toma el costo de compra).
5. Stock puede quedar negativo (no bloquear la venta) pero genera alerta.
6. Numeración de tickets correlativa sin huecos.
7. Arqueo: esperado por medio = apertura + ventas en ese medio + ingresos − egresos.
8. Alertas con `dedupe_key` para no duplicarse; se autorresuelven cuando la condición desaparece.
9. EY% y ratio se calculan en backend (y se muestran en vivo en front con la misma fórmula).

---

## 7. Fases de ejecución

Cada fase termina con: tests pasando, app levantando sin errores de consola, commit con mensaje claro, y checkboxes de este archivo actualizados.

### Fase 0 — Base del proyecto
- [ ] `git init`, `.gitignore` (node_modules, dist, .venv, *.db, build/output).
- [ ] Backend: venv, `pyproject.toml`, FastAPI con `/api/health`, config de rutas (DB en `%APPDATA%\CafeteriaApp\data.db`, en dev `./backend/dev.db`), SQLAlchemy + PRAGMAs, Alembic inicializado.
- [ ] Frontend: Vite + React + TS, Tailwind v4, shadcn init con tema café (claro/oscuro), React Router, TanStack Query, sonner, fuente.
- [x] Cliente API propio (`frontend/src/lib/api.ts`) con manejo de errores y token.
- [ ] `scripts/dev.ps1`: levanta backend (reload) + Vite (proxy `/api` → 8765).
- [ ] `launcher.py` con pywebview apuntando al servidor (probado en modo dev).
- [ ] **AppShell**: sidebar, header, páginas placeholder para todos los módulos, toggle de tema, Ctrl+K vacío.
- **Listo cuando:** `dev.ps1` abre la app con navegación entre secciones vacías, tema claro/oscuro funcionando.

### Fase 1 — Usuarios, auth y configuración
- [ ] Modelos `users`, `settings`, `audit_log` + migración.
- [ ] Login por PIN (hash con `argon2` o `bcrypt`), token de sesión, dependencia `require_role`.
- [ ] Pantalla de PIN con selección de usuario, bloqueo por inactividad.
- [ ] Primer arranque: wizard para crear el admin y datos del negocio.
- [ ] ABM de usuarios (solo admin).
- **Listo cuando:** sin login no se accede a nada; roles restringen menús y endpoints.

### Fase 2 — Catálogo, insumos y recetas
- [ ] Categorías, productos, modificadores, insumos, recetas (modelos, services, routers, tests).
- [ ] UI: listas con DataTable, formularios en Sheet/Dialog, editor de receta con costo y margen en vivo.
- [ ] Actualización masiva de precios por % + historial.
- [ ] `seed.py` con un catálogo demo realista (espresso, cortado, latte, flat white, capuccino, medialunas, tostados, etc.).
- **Listo cuando:** se puede armar el menú completo con recetas y ver el margen de cada producto.

### Fase 3 — Stock
- [ ] Libro de movimientos, service único `stock_service.apply_movement(...)` (lo usan ventas, compras, ajustes).
- [ ] Vista de stock con semáforo y valorización, ajustes, mermas, conteo físico.
- [ ] Sugerencia de compra.
- **Listo cuando:** tests de movimientos y costo promedio verdes; conteo físico genera ajustes correctos.

### Fase 4 — Caja y POS
- [ ] Caja: apertura, movimientos, cierre con arqueo, resumen imprimible.
- [ ] POS completo (sección 3.3) con descuento de stock por receta + modificadores.
- [ ] Historial de tickets, anulación, reimpresión, ticket HTML imprimible.
- [ ] Tests: venta atómica, pagos divididos, anulación, arqueo.
- [ ] e2e Playwright: abrir caja → vender 3 productos con pago dividido → cerrar caja.
- **Listo cuando:** una venta típica se hace en ≤ 4 toques y el stock baja correctamente.

### Fase 5 — Compras y proveedores
- [ ] Proveedores, órdenes de compra, recepción (ingresa stock + costo promedio), facturas sin OC, pagos y vencimientos.
- [ ] Generar OC desde sugerencia de compra; exportar OC a PDF/texto.
- **Listo cuando:** recibir una compra actualiza stock y costo de recetas.

### Fase 6 — Clientes y fidelización
- [ ] Ficha, historial, puntos, canjes, cuenta corriente, segmentos.
- [ ] Integración con POS (buscar/crear cliente al vuelo, canjear puntos, cobrar a cuenta corriente).
- **Listo cuando:** una venta con cliente suma puntos y aparece en su historial.

### Fase 7 — Módulo Barista
- [ ] Cafés, equipos, mantenimiento, recetas objetivo.
- [ ] Shot log con cronómetro, cálculo de ratio/EY, evaluación sensorial.
- [ ] Motor de reglas de dial-in (config en `backend/app/services/dialin_rules.yaml` o `.json`) + tests de cada regla.
- [ ] Recetas de filtrado con pasos cronometrados, calculadoras.
- [ ] Gráficos de calibración, “receta del día”.
- [ ] Modo barra (pantalla completa, tipografía grande) usable en tablet.
- **Listo cuando:** registrar un shot toma < 20 s y el asistente da una sugerencia coherente.

### Fase 8 — Alertas, avisos y checklists
- [ ] `jobs.py` con scheduler simple (hilo + intervalo, o APScheduler) que evalúa reglas de alertas.
- [ ] Centro de notificaciones, campanita, tablón de avisos, checklists de apertura/cierre.
- **Listo cuando:** bajar un insumo bajo el mínimo genera la alerta y reponerlo la resuelve sola.

### Fase 9 — Dashboard y reportes
- [ ] Endpoints de agregados (con índices en `sales.ts`, `sale_items.product_id`).
- [ ] Dashboard (sección 3.2) y reportes (3.11) con exportación xlsx (`openpyxl`) y CSV.
- **Listo cuando:** con el seed de ventas demo (generar ~3 meses de ventas sintéticas) el dashboard carga en < 1 s.

### Fase 10 — Empaquetado, backups y pulido
- [ ] Backups automáticos/manuales/restaurar; migraciones Alembic corren solas al iniciar.
- [ ] Modo red local + QR.
- [ ] `build/cafeteria.spec` (PyInstaller onedir, incluye `frontend/dist` y migraciones), ícono, splash.
- [ ] Instalador Inno Setup (acceso directo, desinstalador que **no** borra la DB).
- [ ] Verificar en PC limpia (WebView2 viene con Windows 11; en Win10 el instalador debe chequearlo).
- [ ] Pasada de pulido: estados vacíos, skeletons, mensajes de error en español, atajos.
- **Listo cuando:** se instala con doble clic, abre, y actualizar a una versión nueva conserva los datos.

### Fases opcionales (después de v1)
- Impresora térmica ESC/POS (`python-escpos`) y cajón de dinero.
- **Facturación electrónica ARCA/AFIP** (vía `pyafipws` o un servicio tipo TusFacturas/Facturante).
- Integración Mercado Pago (QR dinámico / Point).
- Pedidos online / delivery, sincronización a la nube y multi-sucursal (Postgres).
- App/web para clientes con su tarjeta de puntos.

---

## 8. Cómo ejecutar este plan (instrucciones para el agente)

1. Leer `CLAUDE.md` y este archivo completo antes de empezar.
2. Trabajar **una fase por sesión** (o una fase por PR/commit grande). No saltar fases: cada una depende de la anterior.
3. Al terminar cada fase: correr tests, levantar la app y verificar a mano el criterio “Listo cuando”, tildar checkboxes, commitear.
4. Si una decisión no está cubierta acá, elegir lo más simple coherente con el plan y anotarla en la sección 9.

## 9. Decisiones tomadas durante la ejecución
- **Tipos del front escritos a mano por módulo** (`features/<modulo>/types.ts`) en lugar de generarlos desde OpenAPI: los módulos se construyeron en paralelo y un archivo generado compartido generaba conflictos. Sigue siendo viable agregar `openapi-typescript` más adelante.
- **Todo el modelo de datos en una sola migración inicial** (`0001_initial_schema`), definida antes de construir los módulos, para que se pudieran desarrollar en paralelo sin conflictos de migraciones.
- **Rutas del front**: cada módulo (`features/<modulo>/index.tsx`) define sus propias sub-rutas; el router global solo monta `/<ruta>/*` con control de roles.
- **shadcn/ui estilo `radix-nova`** con tokens de color propios (paleta café) y tokens extra `success`, `warning`, `info`.
- **TanStack Table v8** (v9 todavía cambia la API).
- **Commits con identidad neutra** (`Bloom <bloom@bloom.invalid>`, dominio reservado que no se puede asociar a ninguna cuenta) para no exponer datos personales en un repo público. Antes se usaba `controlapp@users.noreply.github.com`, que es de otra cuenta de GitHub: reemplazado en todo el historial el 12/11/2026.
- **Zona horaria**: la DB guarda UTC; los "días" de negocio se calculan en `America/Argentina/Buenos_Aires` (`services/timeutil.py`).

- **Menú para clientes** (`/menu` celular por QR, `/menu/pantalla` TV): sin login, `GET /api/public/menu` expone solo nombre, descripción, precio y modificadores. Se activa/oculta desde Configuración (`public_menu`). Para acceder desde otros dispositivos hace falta "Modo red local".
- **Tutorial** guiado y repetible (`features/tutorial`): se abre solo la primera vez por usuario (flag en localStorage) y se repite desde el menú de usuario, el botón "?" o Ctrl+K. Los pasos apuntan a elementos con `data-tour`.
- **Medios de pago**: habilitar/deshabilitar desde Configuración (solo admin); siempre queda al menos uno habilitado.

- **Ventana sin marco** (`desktop_window.py`): la barra de título la dibuja la app (header + `components/window-controls.tsx`). Arrastrar usa el loop nativo de Windows (`WM_NCLBUTTONDOWN`/HTCAPTION); redimensionar desde los bordes lo hace Python siguiendo el cursor (Windows no redimensiona ventanas sin `WS_THICKFRAME`). Posición/tamaño/maximizado se guardan en `window.json` (píxeles físicos). En navegador/tablet no aparece nada de esto.

- **Instalador por usuario + actualizaciones** (`build/installer.iss`, `app/services/updates.py`): Inno Setup sin UAC en `%LOCALAPPDATA%\Programs\<name>` (sin regla de firewall: Windows pregunta al activar el modo red). La versión vive solo en `brand.json`. La app lee `brand.json → updateManifest` (`latest.json`, p. ej. el último release de GitHub), firmado con Ed25519 con la clave de licencias sobre `BLOOM-UPDATE1\n` + JSON canónico (el prefijo evita confundirlo con un token de licencia); se rechazan firmas inválidas, versiones no más nuevas, URLs no https y descargas con otro `sha256`/tamaño. Instalar = respaldo `pre-update` → instalador `/SILENT /UPDATE=1` → la app se cierra (handler del launcher); el instalador espera el mutex `<appId>-app-running` (el Restart Manager sin admin no siempre puede cerrar la app) y la vuelve a abrir. Desde el código fuente no se ejecuta el instalador.

- **Tamaños (variantes) y detalle del ítem** (migración `0004_product_sizes_and_details`, puramente aditiva): lista de tamaños propia de cada negocio (`sizes`: nombre, abreviatura, ml opcional, orden, activo) y, por producto, `product_sizes` (precio propio, `recipe_scale` y un predeterminado) + `product_size_recipe_items` (ajustes: la cantidad REEMPLAZA a la escalada; 0 = no se usa). Receta del tamaño = receta base (incl. insumo de reventa) × factor + ajustes; los deltas de receta de los modificadores (p. ej. "Bebida de avena": −leche +avena) se escalan con el mismo factor (no siguen los ajustes manuales). Un producto sin tamaños se comporta igual que antes; uno con tamaños tiene `price_cents` = precio del predeterminado (para listas/menús) y su precio real vive en cada tamaño (historial de precios por tamaño con `price_history.size_id`). La venta guarda `sale_items.size_id` + `size_name` (snapshot, sin FK) además de precio y costo del momento; sin `size_id` se usa el predeterminado. Producto: `long_description`, `tags` (lista fija `catalog.PRODUCT_TAGS`), `featured` y foto (`PUT /api/products/{id}/photo` con el cuerpo crudo — no se agregó python-multipart —; Pillow valida, corrige orientación, achica a 1200 px y re-encodea a WebP sin metadatos en `uploads/products/`). Menú online: miniaturas WebP de 240 px como data URL solo mientras el snapshot quede < 220 KB (límite del servidor 300 KB), destacados primero; el resto va sin foto.

- **Pantalla de pedidos (barra/cocina) y pedidos desde la mesa** (migración `0005_orders_and_tables`, puramente aditiva: `orders`, `order_items`, `dining_tables`, `table_tabs`, `waiter_calls`, `order_stations`, `product_categories.send_to_orders` (default true) y `.station_id`, `products.prep_minutes`).
  - Ciclo: `pending` (pedido de un cliente, espera confirmación del mozo/cajero) → `received` → `preparing` → `ready` → `delivered`, o `cancelled`; se puede volver un paso atrás (deshacer). Los pedidos **no mueven stock**: lo mueve la venta. Cada venta del POS genera un pedido en la misma transacción (`services/orders.create_from_sale`), según la config `orders` (activado y canales salón/para llevar/delivery) y la categoría (`send_to_orders`, p. ej. panadería no va); las líneas con `to_bar=false` (cobro de una mesa) no se repiten. Número de pedido por día local.
  - Tiempos: el reloj arranca en `received_at` y se detiene en `ready_at`; objetivo = objetivo del canal (Free) o el mayor de los `prep_minutes` de sus productos/objetivo del canal (Pro). Verde → amarillo (desde `warn_pct` del objetivo) → rojo (atrasado); los atrasados suben primero. Un único reloj `orders.now()` (los tests lo congelan). La pantalla calcula el tiempo en vivo desde `elapsed_s` del servidor (sin depender del reloj de cada tablet).
  - **Polling cada 2 s (no SSE)**: el payload es chico, SQLite + uvicorn con endpoints sync no ganan nada con conexiones largas, el polling sobrevive solo a cortes de Wi-Fi y suspensiones de tablets, funciona igual detrás del listener LAN y no ata hilos del servidor. El celular del cliente consulta el estado de su pedido cada 4 s.
  - Avisos: campanita generada con Web Audio (4 sonidos, sin archivos), sonido distinto para atrasos y llamados; se habilita con un toque ("Activar sonido", política de autoplay) y las preferencias son por equipo (localStorage). Avisos del sistema con la Notification API (en la app de escritorio los muestra WebView2).
  - Free vs Pro: la pantalla (una sola, estados, reloj con objetivo por canal, sonido al llegar y aviso de atraso) y la línea del inicio ("N atrasados · promedio X min") son **Free**. **Pro `orders_pro`** ("Pedidos avanzados"): estaciones (barra/cocina; la venta se divide en un pedido por estación con el mismo número, ruteado por categoría), tiempos por producto, pantalla de retiro para TV (`/menu/retiro`, `GET /api/public/pickup`, solo números), comanda impresa al llegar a una estación (directo por ESC/POS si la estación tiene impresora asignada; si no, la pantalla de esa estación con el diálogo del sistema), sonido por canal y métricas detalladas en Reportes → Pedidos (por hora, canal, producto y quién preparó; exportables).
  - **Pedidos desde la mesa (Pro `public_menu`)**: mesas en Configuración → Mesas, cada una con un token secreto en su QR (`/menu?mesa=<id>&t=<token>`, rotable; editar la URL no sirve para otra mesa). Hoja A4 con 6 QR por página (servicio `qr_png`). El cliente arma el carrito (tamaños y modificadores con las mismas reglas min/max del POS, validadas en el servidor con `sales.LineContext`), deja nota y envía; llega como `pending` y solo pasa a la barra cuando un mozo lo confirma. Límites (config `table_ordering`): máximo de productos por pedido, pedidos por celular (IP en la red local) cada 10 min, el doble por mesa y pedidos sin confirmar por mesa. "Llamar al mozo" y "Pedir la cuenta" se deduplican y vencen solos. Solo funciona en la red local: el menú online sigue siendo de solo lectura.
  - **Mesa abierta**: al confirmar, el pedido se suma a la cuenta abierta de la mesa (`table_tabs`). En el POS, "Mesas abiertas" carga la cuenta en el carrito (precios actuales del catálogo) y se cobra como una venta normal con `tab_id` (una transacción: venta + stock por la receta del tamaño + cierre de la cuenta + vínculo de los pedidos), con descuentos o cortesía si corresponde. Anular esa venta **reabre la cuenta** en la misma transacción (`orders.reopen_tab`): si la mesa no tiene otra cuenta abierta se reabre la misma con sus líneas; si ya tiene otra (volvieron a pedir), los pedidos de la cuenta anulada se pasan a esa (una sola cuenta por mesa) y la vieja queda `merged`. Los pedidos conservan su estado (ya entregados) y pierden el vínculo con la venta anulada; al volver a cobrar van con `to_bar=false`, así que no vuelven a la barra. Se audita (`reopen`, `table_tab`) y el diálogo de anulación avisa «La cuenta de la Mesa N se va a reabrir» (`SaleDetail.table_tab`). Las líneas agregadas en el POS al cobrar (fuera de la cuenta) no vuelven a la cuenta. `table_tabs.payment_ref` y `orders.payment_status/payment_ref` quedan listos para cobrar con QR de Mercado Pago (pendiente).

- **Bajar a gratis = "opción C"** (`services/free_plan.py`, sin migración: setting `free_actives`). Sin licencia válida solo N de cada tipo (productos, clientes, insumos, usuarios; N = `free_limits` de la config remota firmada) quedan **activos para usar**; el resto se ve con candado («Pro»), conserva historial/ventas/reportes y a un cliente bloqueado se le puede cobrar la cuenta corriente. Por defecto, los N más antiguos por `id` (determinístico). La regla vive en un solo lugar (`active_ids`, caché chica por base, invalidada en cada cambio) y la aplica el **backend** con 402: catálogo del POS (no aparecen), `sales.LineContext` (ventas, cobro de mesas y pedidos desde la mesa), cliente de la venta, edición (solo archivar), puntos, recetas/modificadores (no se puede **agregar** un insumo bloqueado; lo que ya estaba queda), ajustes/mermas/conteos (los conteos nuevos no incluyen bloqueados), fotos y aumento masivo. Usuarios: el login y la sesión de un usuario bloqueado se rechazan; siempre hay un admin entre los activos (con la feature `users` no hay límite).
  - La selección se "materializa" (se congela el conjunto actual en el setting) antes de cualquier cambio en Free: archivar un activo **libera un lugar y nada se desbloquea solo**; el dueño crea uno nuevo o desbloquea uno bloqueado (sin espera). **Sacar** un activo que sigue en uso (intercambio) tiene espera `free_limits.swap_cooldown_days` (default 7, 0 = sin espera; editable en el panel del servidor). Reactivar uno archivado ocupa un lugar libre si hay; si no, vuelve bloqueado. Con Pro todo se desbloquea al instante y la selección queda guardada para la próxima vez.
  - API: `GET /api/license/free-plan`, `GET|PUT /api/license/free-plan/{kind}` (rutas dentro del router de licencias para no tocar `main.py`); el PUT genérico de settings no acepta `free_actives`. UI: Configuración → «Elegí tus activos», candado en listas/POS/login y aviso con link.
  - Si la config remota baja N, quedan los N más antiguos de la selección; si lo sube, los lugares nuevos quedan libres (no se rellenan solos).

- **Ganchos del cobro** (`services/sale_hooks.py`): el core expone puntos de extensión que el Pro registra en `bloom_pro.register` (precio por línea, premios, después de vender y de anular), todos dentro de la transacción de la venta. Sin Pro no hay ganchos: `POST /api/pos/quote` devuelve todo en 0 y pedir un premio da 402. Migración `0006_loyalty_stamps_and_promos` (aditiva): `loyalty_programs`, `loyalty_stamps`, `promos`; `sales.reward_program_id`/`reward_discount_cents`; `sale_items.promo_id`/`promo_name`/`promo_discount_cents`/`reward_program_id`/`courtesy_reason`.
- **Tarjeta de sellos (Pro `loyalty_pro`)**: programas con qué suma (cualquier compra = 1 sello por venta con algo cobrado; producto/categoría = 1 sello por unidad; monto mínimo = 1 sello si el total lo alcanza), sellos necesarios, premio (producto y tamaño opcional, o % / $ de descuento de la venta) y fechas. Suman solo ventas completadas con cliente (no cortesías ni líneas premio); el saldo es la suma del libro `loyalty_stamps`; canjear resta `stamps_required`; anular la venta revierte todos sus movimientos de sellos (ganados y canjeados). El premio producto es una línea de $0 con `courtesy_reason = "Premio fidelidad"` (mueve stock, costo real; la venta no es cortesía), 1 unidad, sin descuentos manuales; el premio descuento va en `discount_cents` después del canje de puntos. Convive con los puntos. POS: tarjeta «7/15 sellos», «¡Le toca un … gratis!» y «Canjear» de un toque; ficha del cliente con la tarjeta y su historial.
- **Promos (Pro `promos`)**: combos (precio fijo por un conjunto de productos/tamaños con cantidades) y descuentos (% o $ por unidad) por producto o categoría, con fechas, días de la semana y franja horaria `[desde, hasta)` en hora local (si desde > hasta cruza la medianoche). Un único reloj `promos.now()` (los tests lo congelan). Cada línea lleva **una** sola promo de descuento (la que más ahorra); los combos se arman primero (el que más ahorra) solo si ahorran más que los descuentos de esas mismas unidades; las unidades del combo no llevan otro descuento y el resto de la línea puede llevar su mejor descuento (el nombre queda "Combo + Happy hour"). El combo reemplaza el precio base del tamaño; los modificadores se cobran aparte. El descuento del combo se reparte entre sus líneas proporcional al precio (centavos exactos). La venta guarda `promo_name` y `promo_discount_cents` (dentro de `discount_cents`); el costo no cambia, así que el margen queda bien. El POS pide `/api/pos/quote` en cada cambio del carrito (y cada minuto, para las franjas) y no deja cobrar mientras recalcula; el backend recalcula siempre. Reportes Pro → Productos: «Promociones» (`GET /api/reports/promos`, exportable). Menú local y online: badge + precio promo del tamaño mostrado y sección «Promos» con los combos activos; el menú online publica lo vigente al momento (el job de ~5 min republica cuando cambia), con el mismo CSP/escape y precios ocultos si el local los oculta.
- **Tipos de negocio (perfiles)** (`services/business_profile.py`, sin migración: setting `business_profile` = `{"profile", "modules"}` con solo las diferencias respecto del perfil). Perfiles: «Take away / al paso», «Cafetería chica», «Cafetería con salón» (todo; es el default de las instalaciones que nunca eligieron y de los datos demo) y «Solo pedidos / delivery»; agregar otro (panadería, heladería…) = una entrada en `PROFILES` (+ ícono en `ProfileIcon`). Módulos: canales del POS (salón/para llevar/delivery, siempre queda uno), mesas (requiere salón), pantalla de pedidos, estaciones y retiro (requiere pedidos), barista, stock, compras, reportes, clientes, fidelización (requiere clientes), promos y menú para clientes; un módulo sin su requisito queda apagado y «Activarlo» prende también lo que necesita. Es **simplicidad, no licencia**: la UI oculta nav, búsqueda (Ctrl K), widgets del inicio, pestañas de Configuración/Productos y opciones del POS; el Pro se sigue chequeando encima (un módulo visible sin licencia muestra el cartel de Pro). Ocultar no borra nada y todas las rutas siguen andando (API incluida); un deep link a un módulo oculto muestra «Este módulo está oculto para tu tipo de negocio — Activarlo» (`ModuleRoute`). Única regla del backend: con la pantalla de pedidos oculta las ventas no generan pedidos (no se acumulan pedidos viejos). API: `GET /api/business/catalog` (público, para el asistente), `GET /api/business/modules`, `PUT /api/business/profile`, `PUT /api/business/modules/{key}` (admin; el PUT genérico de settings no acepta la clave). El asistente inicial tiene un paso 2 «¿Qué tipo de negocio tenés?» con «Personalizar módulos»; Configuración → Negocio muestra el tipo actual y «Cambiar tipo de negocio» con vista previa de lo que aparece/se oculta. Servidor de licencias: `plans.profiles` (JSON nullable, vía `ensure_columns`), editable en «Planes y precios» («Recomendado para»); la tarjeta de suscripción de la app ordena primero los planes recomendados para el tipo de negocio actual.

- **Impresión directa ESC/POS** (sin migración: setting `printing`, solo por `/api/printing/*`; no está en `settings.DEFAULTS`, así el PUT genérico no lo acepta). `services/escpos.py` arma los bytes (funciones puras, mismos datos que el ticket/Z/comanda en HTML: `sales.ticket` validado con `TicketOut`, `cash.session_summary(detail=True)`, `orders.serialize`), con página de códigos por `ESC t` (CP858 por defecto; CP850/CP437/sin acentos) y reemplazo de lo que no se puede imprimir; corte parcial/total/ninguno, avance, cajón `ESC p` (pin 2/5); sin logo. `services/printers.py`: spooler de Windows con datatype RAW por ctypes (`winspool.drv`: EnumPrinters nivel 4, OpenPrinter/StartDocPrinter/WritePrinter; sin pywin32) y TCP crudo a IP:9100. Roles: impresora de caja (tickets, Z y cajón) y una por estación (Pro). Ticket después de cada venta: preguntar (botón, como antes) / automático / nunca (sin botón; se reimprime desde Ventas); el cajón se abre solo en ventas con efectivo, nunca al reimprimir. Las comandas las imprime el **backend** cuando un pedido llega a una estación con «Imprimir comanda» e impresora asignada: se arman dentro de la transacción y se mandan en un hilo después del commit (evento `after_commit`; un rollback no imprime nada); si fallan, `board.print_failures` hace que la pantalla de esa estación la imprima con el diálogo y avise. Fallback del front (`features/printing/direct.ts`): sin impresora de caja → diálogo del sistema sin aviso; si la impresora falla (502) → mensaje claro + diálogo. Desactivado en la demo (`BLOOM_DEMO`, también bloqueado en el middleware) y fuera de Windows. Tests: bytes dorados en `tests/golden/*.bin` (`BLOOM_UPDATE_GOLDEN=1` para regenerar).

- **Avisos de licencias de terceros** (`build/third_party_notices.py`, lo corre `build/build.ps1` después del build del front): lista exactamente lo que se distribuye — paquetes npm que quedan en el bundle (los registra el plugin `bundled-packages` de `vite.config.ts` en `node_modules/.cache/bloom/`) más los `@import` CSS de `src/index.css` (Tailwind, Inter y Fraunces OFL-1.1, tw-animate-css, estilos de shadcn); la clausura de dependencias de runtime de `pyproject.toml` leída con `importlib.metadata` (menos los `excludes` del spec); y CPython (su LICENSE incluye OpenSSL/SQLite/libffi…), el bootloader de PyInstaller y los runtimes de Microsoft. Solo stdlib. Salida en `build/generated/` (`THIRD_PARTY_NOTICES.txt` + `third_party_notices.json`, en `.gitignore`), empaquetada junto a `brand.json`; `GET /api/system/third-party-licenses` (cualquier usuario) la sirve y Configuración → Acerca de → «Licencias de terceros» la muestra con búsqueda y texto completo (desde el código fuente dice «se genera al compilar» si no se corrió el script). Marca copyleft/desconocidas sin fallar (`--strict` para fallar): hoy solo el bootloader de PyInstaller (GPL-2.0+ con excepción del bootloader, que permite distribuirlo con cualquier licencia).
- **Índices de la base local** (migración `0007_hot_query_indexes`, solo índices): elegidos con `EXPLAIN QUERY PLAN` y tiempos sobre una base sintética de ~200k ventas / 640k movimientos de stock / 200k pedidos. `sales (status, ts, is_courtesy, total_cents, cost_cents)` (agregados por fecha del inicio y reportes sin leer la tabla; "anuladas"), `sales (cash_session_id, status)` reemplaza a `ix_sales_cash_session_id`, `stock_movements (stock_item_id, ts)` reemplaza a `ix_stock_movements_stock_item_id`, `(ref_type, ref_id)` (anular una venta) y `(type, ts)` (consumo/sugerencias), `loyalty_transactions` y `customer_account_movements (customer_id, ts)`. Las bases de los clientes no tienen estadísticas de `ANALYZE`, así que SQLite elige el índice con más columnas de igualdad al principio: se probó y descartó un índice `(status, is_courtesy, customer_id, …)` porque "robaba" las consultas de caja (8× más lentas). Upgrade en 200k ventas: ~4 s. `orders.summary` (tiempos de preparación del Inicio) ahora agrega en SQL (`_finished_stats`: un solo `SELECT` con `julianday`, sin objetos ORM ni ítems): 80k pedidos en 365 días pasaron de ~3,1 s a ~0,46 s con el mismo resultado (test de equivalencia contra la versión por objetos, incluidos casos de borde de milisegundos). No hizo falta un índice nuevo.
- **Dependencias**: se sacaron del front `react-hook-form`, `@hookform/resolvers`, `zod`, `clsx`, `tailwind-merge` (el paquete `cn` los reemplaza), `react-day-picker` (con el `ui/calendar.tsx` que nadie usaba) y `vitest` (no había tests de front). Back: `uvicorn` sin `[standard]` (la ventana local no usa httptools/websockets/PyYAML/python-dotenv; `watchfiles` pasó al extra `dev` por `--reload`), `cryptography` y `tzdata` agregados al `pyproject`/lock (se usaban y faltaban), `pydantic-settings` fuera del lock. El spec excluye Cython y setuptools (los arrastraba el `import cython` opcional de SQLAlchemy cuando el build Pro instala Cython) y los extras de uvicorn, httpx y pygments. Instalador Pro: 35,3 MB → 28,8 MB; carpeta instalada 79,6 MB → 70,5 MB.
- **Cobros del local: QR, Point, links de pago y transferencia (Pro `payments`, «Cobros con QR, posnet y links de pago»)**. La plata va a la cuenta de **cada local**, nunca a Bloom. Migración `0015_collect_payments` (aditiva): `collect_charges`, `collect_refunds`, `customer_screens`; medios de pago nuevos `mp_qr` («QR Mercado Pago») y `mp_point` («Point (posnet)»), apagados hasta conectar Mercado Pago.
  - **API interna para otros módulos** (`app/services/collect.py`; p. ej. take away/delivery para «pagar el pedido»). Todo en centavos; `ref` es un texto propio del módulo (máx. 64, `[A-Za-z0-9_-]`, se manda a MP como `external_reference`, sin datos personales):
    ```python
    from app.services import collect
    ch = collect.create_charge(db, kind="link", amount_cents=1250000, description="Pedido #23",
                               ref="order-23", ref_type="online_order", ref_id=23,
                               items=[{"name": "Latte", "qty": 2, "total_cents": 1000000}],  # opcional (pantalla)
                               expires_in_s=900, user_id=None, commit=True)
    # kind: "qr" (QR dinámico, qr_data EMVCo) | "link" (url para abrir la billetera) | "point" (posnet) | "transfer"
    collect.charge_status(db, ch.id)            # dict: id, status, kind, amount_cents, refunded_cents, qr_data,
                                                # url, expires_at, provider, ref, ref_type, ref_id, sale_id, error
    collect.refund(db, ch.id, amount_cents=None, user_id=uid)  # None = total; parcial = monto (acumula)
    collect.cancel_charge(db, ch.id, user_id=uid)
    collect.confirm_manual(db, ch.id, user_id=uid)             # solo kind="transfer": «Pago recibido»
    collect.register_handler("online_order", on_approved=fn, on_closed=fn2)  # en el arranque del módulo
    ```
    Estados: `pending` → `approved` | `rejected` | `cancelled` | `expired`; `approved` → `refunded` (total). Una devolución parcial deja `approved` con `refunded_cents > 0`. `on_approved(db, charge)` corre **dentro de la misma transacción** que marca el cobro aprobado (si levanta una excepción, el cobro queda aprobado con `error` y se puede reintentar con `collect.retry_handler`); `on_closed(db, charge)` cuando vence/se cancela/rechaza. `create_charge` llama al proveedor (HTTP) **antes** de abrir la transacción; con `commit=False` la fila queda en tu transacción (si hacés rollback, llamá a `cancel_charge`). Sin licencia `payments` → `HTTPException(402)`; sin proveedor configurado → 400 con mensaje claro. `kind="transfer"` no necesita proveedor (muestra alias/CBU de Configuración → Cobros).
  - **Proveedor**: protocolo `CollectProvider` (`create_qr_charge`, `create_payment_link`, `send_to_point`, `get_status`, `refund`, `cancel`) con registro `collect.register_provider(name, factory)`. Core: `FakeProvider` (tests, demo y desarrollo: se aprueba con «Simular pago»; nunca en el .exe salvo la demo) y el manual de transferencia. Pro: `MercadoPagoProvider` (Orders API: `POST /v1/orders` `type=qr` `mode=dynamic` / `type=point`; `GET /v1/orders/{id}`; `POST …/cancel` y `…/refund`; links con Checkout Pro). Futuros adaptadores en la nota de diseño de abajo.
  - **Sin webhooks** (la PC del local no es alcanzable desde internet): mientras un cobro está abierto se consulta su estado cada 2 s durante el primer minuto, 5 s hasta los 5 min y 15 s después; si el proveedor falla, backoff 2→4→…→30 s (`poll_failures`/`next_poll_at`). Lo hace un hilo `collect-poller` (arranca con los jobs del escritorio; duerme si no hay cobros abiertos) **y** cualquier consulta de estado (POS y pantalla cada 1,5 s; `charge_status` de otros módulos), con un candado por cobro. La aprobación es un `UPDATE … WHERE status='pending'` condicional: dos consultas simultáneas nunca crean la venta dos veces. Vencido el plazo (+30 s) se pide la cancelación al proveedor y queda `expired`. **Opcional, no implementado**: relay de webhooks de MP (tópico `orders`) al buzón del servidor de licencias (`/v1/webhooks/mp-collect` → inbox del local por `user_id`) para forzar una consulta inmediata; el polling alcanza.
  - **POS**: medios «QR Mercado Pago», «Point (posnet)» (si hay un Point elegido) y «Transferencia» (si hay alias/CBU cargado). `POST /api/collect/pos-charges {sale, method, screen_id}` valida la venta con una corrida en seco (`sales._create_sale` + rollback: caja abierta, precios, promos, totales) y abre el cobro guardando el `SaleIn`; al aprobarse, el handler `pos_sale` crea la venta en la misma transacción que marca el cobro aprobado. Si falla (p. ej. cerraron la caja), el cobro queda aprobado con `error` y el POS ofrece «Reintentar». El cobro se puede mostrar en una **pantalla del cliente** registrada (Configuración → Cobros: nombre, link/QR con token secreto rotable; `GET /api/public/customer-screen?token=`) y siempre en el POS. Cancelar hace una última consulta antes (no se cancela un pago que ya entró). «Simular pago» solo con el `FakeProvider`.
  - **Devoluciones**: detalle de la venta → «Devolver» (total o parcial, acumulable; permiso `sales.void`); con devolución total se puede anular también la venta. Las transferencias se devuelven desde el banco. `collect_refunds` guarda cada una.
  - **Conectar Mercado Pago (Pro)**: OAuth con PKCE vía el servidor de licencias (`/v1/payments/mp/oauth/start|callback|claim|refresh`, módulo `license_server/payments_mp.py`): el `client_secret` de la app de Bloom nunca sale del servidor; el handoff queda atado a la licencia + PC, los tokens se guardan cifrados solo entre el callback y el primer `claim` (15 min máx.) y el refresh es de paso. Alternativa avanzada: pegar el Access Token propio. Después hay que crear sucursal + caja (`POST /users/{id}/stores`, `POST /pos`) o indicar una caja existente: el QR dinámico la necesita. Point: `GET /terminals/v1/list` y elegir uno.
  - **Credenciales cifradas en reposo** (`services/secret_store.py`, setting `collect_credentials`, solo el cifrado): en Windows **DPAPI** por ctypes (atado al usuario de Windows de esa PC; una copia de la base o un respaldo no alcanzan para leerlo; restaurar en otra PC pide conectar de nuevo); fuera de Windows (dev, demo) Fernet con `secret.key` 0600 en la carpeta de datos (los respaldos copian solo la `.db`).
  - **Demo online**: proveedor simulado y alias ficticio; los endpoints `/api/collect/mp/*` están bloqueados.
  - **Variables de entorno** (servidor de licencias): `MP_CLIENT_ID`, `MP_CLIENT_SECRET` (app de Mercado Pago de Bloom con OAuth/marketplace; Redirect URL = `PUBLIC_URL/v1/payments/mp/oauth/callback`), opcionales `MP_AUTH_URL` y `MP_HANDOFF_KEY`. App: `BLOOM_COLLECT_FAKE=1` habilita el simulador en un .exe (solo para pruebas), `BLOOM_SECRET_BACKEND=file` / `BLOOM_SECRET_KEY_FILE` (tests).
  - **Nota de diseño — próximos adaptadores** (cada uno implementa `CollectProvider` y se registra con `register_provider`; ninguno cambia el POS ni la API interna):
    · **Getnet (Santander)**: QR/terminal y links vía su API de comercios; requiere alta del local como comercio Getnet, credenciales `client_id/secret` por comercio y homologación. Polling por `orderId`.
    · **Payway (Prisma)**: Payway Checkout/links y botón de pago; requiere `site_id` + API keys del comercio; QR vía Payway QR (interoperable). Devoluciones por API.
    · **MODO**: QR interoperable de MODO para comercios vía su API de pagos (alta como comercio MODO o a través de un adquirente/PSP); `get_status` por id de intención de pago.
    · **Naranja X / Ualá Bis**: links y QR de cobro con sus APIs para comercios (Ualá Bis API checkout con `client_id/secret`; Naranja X Checkout); requieren cuenta de comercio y credenciales propias del local.
    En todos los casos: credenciales por local cifradas con `store_credentials`, sin webhooks (polling) y `external_reference` = `ref` del cobro.

- **Roles y permisos editables** (`app/permissions.py`, `services/roles.py`, migración `0010_roles_and_staff`, tabla `roles`): catálogo de permisos derivado de los chequeos de rol que existían (`pos.sell`, `pos.discount`, `pos.courtesy`, `sales.void`, `cash.open_close`, `cash.movements`, `catalog.edit`, `prices.edit`, `stock.view|edit|adjust`, `purchases.manage`, `customers.edit|manage`, `promos.manage`, `orders.manage`, `notices.manage`, `barista.use|manage`, `reports.view`, `expenses.manage`, `staff.manage`, `settings.manage`, `users.manage`, `system.manage`). Los roles de fábrica mapean a los permisos que tenían (mismo comportamiento si nadie edita nada; sin filas en `roles` hasta la primera edición). El backend exige con **una sola dependencia** `require_permission(...)` / `Perm(...)` (cualquiera de los permisos alcanza; admin siempre pasa); los permisos del usuario se calculan una vez por request (`roles.permissions_of`). `require_role`/`Manager` quedan como legado (solo nombres fijos: un rol propio nunca los pasa). Front: `/auth/me` y el login devuelven `permissions` y `role_name`; `can(...permisos)` (sin argumentos = solo admin) oculta nav, rutas, pestañas de Configuración y botones.
  - Anti-bloqueo: `admin` siempre tiene todo, no se edita ni se borra; los de fábrica se editan y se **restablecen**; un rol en uso no se borra (409); tiene que quedar un admin activo (como antes). Siempre de admin (no delegable): licencia, cuenta Bloom, «Elegí tus activos» y el editor de roles. Un no-admin con `users.manage` solo asigna roles cuyos permisos sean subconjunto de los suyos y no toca administradores. Algunos permisos traen su requisito (`REQUIRES`: descuento → vender, ajustar stock → ver stock…). Todo cambio queda en auditoría (`role`: create/update con agregados/quitados/reset/delete). Los bloqueos del plan gratuito siguen aplicando igual (por usuario, no por rol).
  - Los cambios de un rol valen desde el próximo request de sus usuarios en el backend; la UI de esos usuarios se actualiza al recargar (los permisos viajan con `/auth/me`).
- **Empleados (Pro `staff`)** (`app/models/staff.py`, `bloom_pro/services/staff.py`, misma migración): ficha (nombre, puesto, por hora o mensual en centavos, ingreso, teléfono opcional y notas — datos personales mínimos), vinculada a un usuario (ficha con el PIN de ese usuario) o sin acceso a la app (PIN propio solo para fichar). **Fichaje** sin sesión (`/api/staff/clock`, con el mismo freno de intentos que el login) desde el botón «Fichar» del login (PC o tablet en red local) y desde el menú de usuario; entrada, salida y pausas. Un turno cuenta entero en el día local de su entrada (turnos que cruzan la medianoche). Correcciones y cargas manuales solo con `staff.manage` y **motivo obligatorio**, auditadas con antes/después. Horas extra: lo que pasa de `daily_hours` por día (setting `staff`, default 8 h, recargo `overtime_pct` 50 %) — se pagan solo a los de por hora; para mensuales se informan. Mensual prorrateado por días calendario de cada mes del período (mes completo = sueldo, desde la fecha de ingreso). Adelantos con fecha: se descuentan del período que la contiene. Turnos abiertos no se cuentan. Reporte semana / quincena (1–15, 16–fin) / mes con exportación Excel/CSV. **Control interno, no es un recibo de sueldo** (aviso en la UI y en el export). Turnos/planificación de horarios: no se hizo (no era barato); queda anotado en `pro/PENDIENTES.md`.
- **PWA (app instalable en celulares/tablets)**: `manifest.webmanifest` generado desde `brand.json` (plugin `pwa` de `vite.config.ts`, también en dev), íconos generados desde `build/icon.png` (`build/make_pwa_icons.py` → `public/icons/`, incluye maskable y apple-touch) y `sw.js` generado en el build desde `pwa/sw.template.js` con un id de build y la lista del shell. El service worker **solo cachea el shell** (index, `/assets/*` con hash, íconos): nunca `/api/*` ni `/uploads/*`; navegación network-first con el shell cacheado de respaldo, y la app muestra «Sin conexión con la PC del local» con Reintentar (reintenta sola cada 5 s). Una versión nueva queda esperando hasta tocar «Actualizar» (toast). No se registra en dev ni dentro de la ventana de escritorio (pywebview; si hubiera uno, se desregistra). El servidor manda `Cache-Control: no-cache` para `sw.js`, el manifest e `index.html`.
  - **Contexto seguro**: los service workers solo andan en `localhost` o `https`. En la red local la tablet abre `http://192.168.x.x:puerto`, que **no** es contexto seguro. Opciones evaluadas: (a) flag de Chrome `unsafely-treat-insecure-origin-as-secure` por tablet (sirve para pruebas, no para clientes); (b) certificado autofirmado generado por instalación + listener https: hay que instalar y confiar la CA en cada dispositivo (Android lo esconde en Ajustes → Seguridad, iOS pide perfil + confianza manual) y si no, el navegador muestra pantalla roja y no registra el SW; (c) manifest + «Agregar a la pantalla principal» sin SW. Se implementó **(c) por LAN** (ícono propio, pantalla completa en iOS/Android; necesita la PC prendida) y **PWA completa** cuando se sirve por `https`/localhost (p. ej. la demo online). Instrucciones en Configuración → Red local («Instalá Bloom en la tablet»). Si en el futuro hace falta offline real en la tablet, el camino es (b) con un asistente de instalación del certificado.

- **Gestión de gastos** (migración `0012_expenses`: reconstruye la tabla `expenses` de 0001, que nunca se usó, y agrega `expense_categories` con 10 categorías editables y `recurring_expenses`). **Cargar gastos es Free (core)**: sin eso no hay "ganancia real" y es lo que cualquier local necesita; el **reporte completo "Resultado del mes" es Pro `reports`** (mes a mes, comparación, gastos por categoría con variación, exportable). La tarjeta del Inicio «Ganancia real del mes» es Free (es el gancho para cargar gastos). Regla: ventas − costo de mercadería (`sales.cost_cents`) − mermas (movimientos `waste` a su costo) − cortesías (costo) − gastos = ganancia real. Los gastos van por **devengado** (`Expense.date` = fecha local del mes al que corresponden; pagados o pendientes); el mes en curso se muestra «hasta hoy» (ventas y gastos con fecha hasta hoy) y aparte «Faltan $X de gastos de este mes» (`expenses_upcoming_cents`), así a principio de mes no da una pérdida engañosa. Las compras de mercadería NO son gastos (entran por el costo de lo vendido). Fijos mensuales: `generate_recurring` (job de 5 min + al abrir Gastos/Inicio) crea el pendiente de cada mes con su vencimiento (día clampado al largo del mes); `last_period` evita regenerar un mes borrado a mano; editar el fijo vale para los meses siguientes. **Pagado en efectivo de la caja** = egreso `CashMovement` en la misma transacción (requiere caja abierta); cambiar monto/medio o borrar corrige el egreso solo si esa caja sigue abierta (si se cerró: 409). Comprobante: foto por el mismo pipeline de las fotos de productos (Pillow → WebP sin metadatos) pero guardada en `<datos>/receipts/` (no en `/uploads`, que es público) y servida solo a quien tiene `expenses.manage`. Avisos: `expense_due` (vence en ≤ `alerts.expense_due_days`, default 3; vencido = crítico). Permiso nuevo `expenses.manage` (encargado y admin).
- **Límite de mesas por plan**: `plans.max_tables` (nullable, vía `ensure_columns`; panel → Planes y precios → «Mesas (máx.)», vacío = sin límite) viaja **firmado en el token** como claim opcional `limits: {"tables": N}` (se lee del plan en vivo en cada emisión/refresh: subir el límite llega a la app en el próximo refresh). Se eligió el claim del token (y no la config remota) porque está atado a la licencia y a la PC y funciona offline sin poder editarse. El módulo Pro lo verifica con su propio guard (`_guard.limit`, misma verificación de firma que las features) al crear mesas (una o en lote: el lote se rechaza entero) → 402 «Tu plan permite hasta N mesas… pasá a un plan con más mesas»; bajar el límite nunca desactiva mesas existentes. Sin claim = sin límite. Las mesas son Pro (`public_menu`): el plan gratuito no tiene mesas, así que no hay `free_limits.tables`. `GET /api/tables/limit` y `LicenseStatus.limits` para la UI.
- **Demo anti-abuso**: vida máxima absoluta por demo (`BLOOM_DEMO_MAX_LIFETIME_HOURS`, 2 h aunque siga activa) con cuenta regresiva en el cartel («Tu demo se borra en 45 min», calculada con los segundos que manda el servidor, no con el reloj del visitante) y pantalla final con «Descargá Bloom gratis», «Crear mi cuenta» (`BLOOM_DEMO_SIGNUP_URL`) y «Empezar otra demo» (recargar no crea otra sola). Por IP: tope diario móvil (`BLOOM_DEMO_NEW_PER_IP_DAY`, 5) además del horario, y bloqueo temporal (`BLOOM_DEMO_BLOCK_MINUTES`, 60) si abre más de `BLOOM_DEMO_BURST_COUNT` (3) en `BLOOM_DEMO_BURST_MINUTES` (10). Todo lo impreso por el diálogo (ticket, Z, comanda, hoja de QR) lleva marca de agua DEMO (`lib/demo.ts`, `printHtml`); los exportes Excel/CSV llevan fila «DEMO…», hoja y archivo `DEMO-…`. Respaldos: descarga/restauración siguen bloqueadas (403) y además la base de la demo tiene la marca `settings.demo_sandbox`: restaurar un respaldo con esa marca se rechaza, así que los datos de la demo nunca entran a una instalación real. Subir comprobantes también está desactivado en la demo.
- **Descartar insumos y envases** (migración `0013_stock_packages`, aditiva): `POST /api/stock/waste` acepta una cantidad, N envases o «todo» (del insumo o de un lote), con motivo fijo (vencido, derrame/se cayó, rotura, sobrante de preparación, otro + nota obligatoria) → siempre `apply_movement(..., "waste")`, así aparece en Mermas y en la ganancia real; del lote elegido o FEFO. Descarte rápido desde el POS y el barista (`/api/stock/quick-discard`, permisos `pos.sell`/`barista.use`, hasta 1 L / 1 kg / 10 u; para más, Stock). Envases por insumo (`stock_packages`: nombre, contenido en la unidad base, código de barras y costo opcionales, uno principal): el stock sigue en g/ml/u (el consumo de recetas no cambia) y se muestra como «4 × Sachet 1 L + 730 ml»; conteos y compras (Pro) pueden cargarse en envases (el front convierte a la unidad base).

- **Cata del barista (Pro `barista`)** (migración `0014_barista_tasting`, aditiva y nullable): `shot_logs.aroma` (1–5), `cupping` (JSON 0–10: General, Fragancia/Aroma, Sabor, Acidez, Cuerpo, Sabor de boca, Balance) y `flavor_notes` (keys de la rueda); `coffees.flavor_notes`, `roast_point` (medium|high|city|full_city|french|italian = Claro…Muy oscuro), `taste_profile` (1–5) y `menu_role` (house|decaf|origin). La **rueda de sabores** vive en `bloom_pro/services/flavor_wheel.json` (9 categorías, 2–3 niveles, keys únicas; `GET /api/barista/flavor-wheel`); el backend valida las notas contra ella. Front: `barista/tasting/` (rueda SVG con zoom por categoría + lista de chips con búsqueda, «Mapa de sabor» SVG pentágono/heptágono con el mejor shot como overlay, dot sliders 1–5, escala de tueste; colores en `flavor-palette.css`). Reglas nuevas en `dialin_rules.json` (todas con test): muy ácido/amargo, ácido+corto, amargo+largo, sin tiempo, aguado (`watery_body`), notas de la rueda que marcan defectos (`note_flags`: agrio, quemado, ceniza, acre) y **edad del tueste** vs el último shot bueno del café (±`roast_age_days`, ≈1 punto cada `roast_days_per_step` días, tope `roast_max_steps`; además «recién tostado»/«pasado» con la ventana de Alertas). Mejor shot = último calibrado; si no hay, el de mayor puntaje. Endpoints: `GET /barista/coffees/{id}/history|prefill`, `GET /barista/shots/compare?a=&b=`, `GET|POST /barista/coffee-menu[/modifier]`. **Café para clientes**: el menú público publica `coffees` (solo campos seguros) ligados a los productos cuya receta usa el insumo del café (o, sin insumo, a los que tienen una guía con espresso) y a las opciones del grupo «Tipo de café»; el menú online lo renderiza con el mismo CSP/escape (radar con solo números). «Ofrecer como opción en el menú» crea/actualiza ese grupo (mín 0, máx 1: por defecto el cliente no elige) con −café de la casa +café elegido en la cantidad más común de las recetas; el vínculo opción→café va en el setting `coffee_menu`.

- **Estados del pedido por canal = máquina de estados declarativa (Strategy por canal)** (`services/order_flows.py`, migración `0009_online_orders`, aditiva: los códigos viejos no cambian). Un `OrderFlow` por canal registrado en `FLOWS` (`caja`, `mesa`, `take_away`, `delivery`; el pedido elige el suyo con `flow_key`: origen + canal; sumar un canal = una definición más): estados en orden, transiciones permitidas (incluye salidas `rejected`/`expired`/`cancelled`), acciones (botones) de cada estado con `tone/place/needs` (eta, reason, reason_optional, confirm) y guardas/efectos por transición (`on`/`guard`, `"*"` = cualquier origen). Única entrada `orders.transition(db, order, to, actor, reason, params, via)`: `via="ui"` solo acepta acciones del estado actual (y que pasen su guarda), `via="system"` cualquier transición declarada (pago aprobado, vencimiento, cobro de la mesa, pasos encadenados); corre guardas y efectos en la transacción del llamador, audita y da 409 claro. La API expone los flujos (`GET /api/orders/flows`) y cada pedido trae `flow`, `status_label`, `column` y `actions`: la pantalla de Pedidos arma columnas y botones desde los datos. Caja: confirmado → en preparación → listo → entregado. Mesa: pedido → confirmado → … → servido → pagado (al cobrar la cuenta; anular la venta vuelve a servido). Take away/delivery: pedido → aceptado (ETA) → pago pendiente → pagado → en preparación → listo → (enviado →) retirado/entregado; efectivo salta el pago; salidas rechazado (motivo obligatorio), vencido, cancelado (+ devuelto).
- **Pedidos online take away / delivery (Pro `online_orders`)**. El cliente pide en el menú online (`/m/{slug}`: carrito con tamaños, modificadores y notas, retiro/delivery, nombre + WhatsApp, dirección con referencia y zona, medio de pago) y sigue el pedido en `/p/{token}`. El servidor (`license_server/order_inbox.py`) valida contra el menú publicado (productos, tamaños, reglas de modificadores, canales, horario, zonas, medios de pago, máximo de productos), rechaza cualquier campo de precio/descuento (`extra="forbid"`), limita por IP y por local, honeypot y Turnstile opcional, y guarda el pedido 7 días en un buzón por licencia; la app (sin IP pública) hace `pull`/`ack` cada 5 s con su token de licencia (`bloom_pro/services/order_inbox.py`, hilo propio) y devuelve los cambios de estado (`/v1/inbox/status`) para la página de seguimiento. **Precios, promos y totales los recalcula siempre la app** con su catálogo (`LineContext`/`price_cart`, items armados explícitamente). Aceptación manual por defecto (sonido + cartel; «Aceptar» con ETA o «Rechazar» con motivo; automática opcional por franja, apagada); al aceptar se habilita el pago: link del proveedor de cobros (`services/collect.py`, `ref_type="online_order"`, se aprueba solo y pasa a pagado), transferencia (alias/CBU, «Pago recibido») o efectivo al recibir; vence a los N min (15). «Cancelar y devolver» llama a `collect.refund`. Pagado (o entregado en efectivo) = venta en la caja abierta (stock, reportes; si no hay caja, «Registrar venta»). Clientes por teléfono: un pedido anónimo **nunca** modifica un cliente guardado (solo lo vincula); la ficha nueva se crea al aceptar y los datos distintos se muestran como «Datos nuevos» con «Actualizar datos del cliente». Botón WhatsApp (wa.me con mensaje armado, plantillas editables) y «Avisar por WhatsApp» al aceptar con el link de seguimiento/pago. Configuración → Pedidos online respeta el tipo de negocio (módulos take away/delivery). Botón «WiFi» (red, clave y QR `WIFI:T:WPA;S:…;P:…;;`) en el menú local y, si se elige, en el online; apagado de fábrica.
- **Medio de pago de las ventas de pedidos online (Pro `online_orders`)**: mapeo fijo en código (`SALE_METHODS`), ya no configurable: link de cobros → `mp_qr` (si no está activo, `qr`), transferencia → `transferencia`, efectivo → `efectivo`. **Nunca cae a otro tipo de medio**: si el medio no está activo la venta queda «sin registrar» (no suma al efectivo esperado del cierre) y «Registrar venta» avisa cuál habilitar o que falta abrir la caja. Las configs viejas con `sale_methods` se ignoran y se limpian al guardar.
- **Insumos según el canal** (`services/channel_supplies.py`, migración `0011_packaging_by_channel`, tabla `channel_supplies`): cualquier insumo y cantidad por unidad vendida según el canal (salón, para llevar, delivery; cada uno su lista completa, vacía de fábrica), por categoría (predeterminado) y por producto (reemplaza al de la categoría), con ajustes por tamaño (la cantidad reemplaza a la general; 0 = no se usa). Se suma al consumo de la receta de la venta en la misma transacción (`stock.apply_movement`), así que anular la venta lo devuelve. Editor «Insumos según el canal» en el producto y en la categoría.

- **Envío en la venta** (migración `0016_sale_delivery_fee`, aditiva): la venta tiene `delivery_fee_cents` (solo canal delivery; en cortesías no): suma al total y a los pagos; no a los puntos ni a los descuentos; se muestra como «Envío» en ticket y detalle. Pro: `register_sale` de pedidos online lo manda.

- **Movimiento (animaciones)** (`frontend/src/index.css`, `lib/motion.ts`; sin dependencias nuevas): una sola escala y una sola curva para toda la app. Tokens `--motion-fast` 120 ms (hover, menús, overlays), `--motion-base` 180 ms (diálogos, popovers, tarjetas), `--motion-slow` 260 ms (hojas laterales, sidebar) y curvas `--ease-out-soft` (entrar) / `--ease-in-soft` (salir). Se usan como utilidades `motion-fast|base|slow` (fijan `--tw-duration`/`--tw-ease`, así sirven tanto para `tw-animate-css` como para `transition-*`) y `data-closed:motion-exit` para que salir sea un poco más seco que entrar; **no se escriben más `duration-N` ni `ease-*` sueltos**. Regla: solo `transform`/`opacity` (y colores/sombras, que no tocan el layout); nada de `transition-all`. Excepciones a propósito: barras de progreso y puntos del paginador animan `width` (elementos chicos), el tutorial anima la posición del foco (se muestra rara vez) y el carrusel de la pantalla de TV conserva sus 500/1000 ms (es contemplativo). **`prefers-reduced-motion`**: una guarda global en `index.css` deja toda animación/transición en ~0 ms, corta los loops infinitos (`animate-pulse`/`ping`) en un ciclo y apaga el scroll suave; `animate-spin` queda exento porque es un indicador de carga. Feedback nuevo, solo de entrada (nada espera una animación de salida): `motion-enter` (línea nueva del carrito, tarjeta nueva de Pedidos, comprobante, botón de carrito del menú), `motion-fade` (cambio de módulo —se remonta por el primer segmento de la ruta, así las sub-rutas conservan su estado—, filas y tarjetas que reemplazan al skeleton, estado vacío), `motion-pop` (tilde de «Pago aprobado», estado de la tarjeta del pedido al cambiar) y `motion-bump` (total del POS, contador del carrito) con `useBump(valor)`, que remonta el elemento al cambiar el valor (no al montar). El menú online del servidor (`menu_online.py`/`order_page.py`) usa la misma escala y la misma guarda. Test: `e2e/motion.spec.ts` (tokens, guarda con `emulateMedia({ reducedMotion })`, entrada de líneas y bump).

- **Turnos planificados, tardanzas, horas extra de mensuales y feriados (Pro `staff`)** (migración `0029_shifts_and_holidays`, aditiva: `shifts` y `holidays`; código en `bloom_pro/services/{shifts,holidays,staff_alerts}.py` y `staff.py::report`). Un turno es un día local + hora de entrada/salida «HH:MM» (si la salida es menor o igual a la entrada, termina al día siguiente), máximo 16 h, sin superponerse con otro turno de la misma persona (se mira el día anterior y el siguiente por los nocturnos); «Copiar semana» (con o sin reemplazo). Un fichaje pertenece a un turno si su entrada cae entre 2 h antes del inicio y el fin (gana el inicio más cercano); eso gobierna:
  - **Hora extra**: con turno = lo trabajado de más que los minutos planificados, solo si supera `overtime_tolerance_min` (10); sin turno = la regla de siempre (> `daily_hours` por día). **Sueldo mensual**: valor hora = sueldo ÷ `hour_divisor` (200, a confirmar con el contador) y las extras se suman al sueldo prorrateado con `overtime_pct`; con `pay_monthly_overtime` apagado vuelve a solo informarse.
  - **Feriados** (`holidays`, tabla de la migración 0029): la lista de cada año se siembra la primera vez que se consulta, por **país y provincia** (Configuración de Feriados; por defecto Argentina) y de la **primera fuente con datos**: (1) la **config remota firmada** (`remote_config.holidays(país, año)`, sección `holidays` del payload: `{"AR": {"2026": [{"date", "name", "kind"}]}}`; la publica el servidor de licencias tras revisar en `/admin/feriados` lo que una API de feriados trae y la librería no, ver `license_server/holidays_sync.py`; la app superpone esos días a la lista de la librería —en una fecha que ya estaba, gana el nombre y tipo del servidor— y cuando suma días a un año ya sembrado solo agrega las fechas nuevas, nunca pisa lo que editó el local); (2) la librería **`holidays`** (python-holidays, MIT, 200+ países y subdivisiones, offline; se actualiza con cada versión de Bloom; ~1,6 MB comprimida); (3) la **Ley 27.399 calculada** (solo Argentina: inamovibles + Viernes Santo y Carnaval por la Pascua + trasladables 17/6, 17/8, 12/10 y 20/11 → lunes anterior si cae martes/miércoles, lunes siguiente si jueves/viernes), de respaldo. La lista es editable (sumar locales/provinciales, mover, quitar: quitar uno incluido solo lo apaga y no se vuelve a sembrar; cambiar el país o la provincia reemplaza lo incluido y conserva lo propio). Los «puentes» (días no laborables con fines turísticos; la librería los llama «Feriado con fines turísticos») **no** son feriados: se pagan como un día común, así que se siembran **apagados** con tipo `bridge` y el local los activa solo si los paga como feriado. Horas en feriado: por hora, la hora a (100 + `holiday_pct`) %; mensual, solo el recargo (el día ya está en el sueldo); extra en feriado al mayor de los dos porcentajes (no se acumulan).
  - **Tardanza / ausencia**: entrada más de `late_tolerance_min` (10) después del inicio = tardanza; sin fichar `absence_after_min` (30) después del inicio = ausencia (nunca un turno futuro). Resumen y Excel/CSV con planificadas, tardanzas, ausencias, horas y pago de feriado y extras.
  - **Avisos**: el motor de alertas del core tiene un punto de extensión `alerts_engine.register_rule(key, fn, types, permission)` (los tipos registrados se auto-resuelven y quedan ocultos a quien no tenga el permiso; reemplaza el ocultamiento fijo de `expense_due`). Pro registra `staff_late` / `staff_absent` (una alerta por turno, `staff_shift:<id>`, solo `staff.manage`).
  - **Bloom Equipo**: `GET /api/staff/shifts/me` (cualquier sesión vinculada a un empleado): próximos 7 días, próximo turno y recordatorio «tu turno empezó y no fichaste» (solo avisa, nunca ficha solo).

- **Arranque y cierre de la base (15/11)**: `upgrade_db` chequea la salud **antes** del respaldo previo (con la base dañada ese respaldo fallaba y el servidor no arrancaba); si el respaldo no se puede tomar o está dañado, restaura la copia sana más nueva de `backups/` (`latest_healthy_backup`), deja lo dañado como `.danada-*` y lo registra en la Auditoría (`recover`, `database`). El launcher toma un candado por carpeta de datos (`instance.lock`, `msvcrt.locking`; el puerto en `instance.json`): una segunda apertura solo abre otra ventana, nunca un segundo servidor sobre el mismo archivo. Al cerrar la ventana, `shutdown_server` frena los jobs y `db.close_cleanly` hace `wal_checkpoint(TRUNCATE)` + `dispose` (máx. 8 s) antes de `os._exit`. Si el servidor no arranca, la ventana muestra `startup_error_html` en vez de la página de error del navegador.

## 10. Preguntas abiertas para el dueño
- ¿Cuántas PCs/cajas? ¿Se usará tablet en la barra? (define si “modo red local” es prioridad).
- ¿Hace falta facturación electrónica desde el día 1 o alcanza con ticket no fiscal?
- ¿Tienen impresora térmica? ¿Qué modelo?
- ¿Mesas con comandas abiertas (pedido que queda abierto y se cobra al final) o venta directa en mostrador? — v1 asumía **mostrador**; ya existe la mesa abierta mínima para los pedidos desde la mesa (ver sección 9).
