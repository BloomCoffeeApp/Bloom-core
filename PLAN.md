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
ControlApp/
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
- **Commits con identidad neutra** (`ControlApp <controlapp@users.noreply.github.com>`) para no exponer datos personales en un repo público.
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
- **Índices de la base local** (migración `0007_hot_query_indexes`, solo índices): elegidos con `EXPLAIN QUERY PLAN` y tiempos sobre una base sintética de ~200k ventas / 640k movimientos de stock / 200k pedidos. `sales (status, ts, is_courtesy, total_cents, cost_cents)` (agregados por fecha del inicio y reportes sin leer la tabla; "anuladas"), `sales (cash_session_id, status)` reemplaza a `ix_sales_cash_session_id`, `stock_movements (stock_item_id, ts)` reemplaza a `ix_stock_movements_stock_item_id`, `(ref_type, ref_id)` (anular una venta) y `(type, ts)` (consumo/sugerencias), `loyalty_transactions` y `customer_account_movements (customer_id, ts)`. Las bases de los clientes no tienen estadísticas de `ANALYZE`, así que SQLite elige el índice con más columnas de igualdad al principio: se probó y descartó un índice `(status, is_courtesy, customer_id, …)` porque "robaba" las consultas de caja (8× más lentas). Upgrade en 200k ventas: ~4 s. Pendiente aparte: `orders.summary` carga los pedidos como objetos ORM (~2 s en el inicio con 365 días).
- **Dependencias**: se sacaron del front `react-hook-form`, `@hookform/resolvers`, `zod`, `clsx`, `tailwind-merge` (el paquete `cn` los reemplaza), `react-day-picker` (con el `ui/calendar.tsx` que nadie usaba) y `vitest` (no había tests de front). Back: `uvicorn` sin `[standard]` (la ventana local no usa httptools/websockets/PyYAML/python-dotenv; `watchfiles` pasó al extra `dev` por `--reload`), `cryptography` y `tzdata` agregados al `pyproject`/lock (se usaban y faltaban), `pydantic-settings` fuera del lock. El spec excluye Cython y setuptools (los arrastraba el `import cython` opcional de SQLAlchemy cuando el build Pro instala Cython) y los extras de uvicorn, httpx y pygments. Instalador Pro: 35,3 MB → 28,8 MB; carpeta instalada 79,6 MB → 70,5 MB.

## 10. Preguntas abiertas para el dueño
- ¿Cuántas PCs/cajas? ¿Se usará tablet en la barra? (define si “modo red local” es prioridad).
- ¿Hace falta facturación electrónica desde el día 1 o alcanza con ticket no fiscal?
- ¿Tienen impresora térmica? ¿Qué modelo?
- ¿Mesas con comandas abiertas (pedido que queda abierto y se cobra al final) o venta directa en mostrador? — v1 asumía **mostrador**; ya existe la mesa abierta mínima para los pedidos desde la mesa (ver sección 9).
