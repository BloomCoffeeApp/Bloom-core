<p align="center"><img src="frontend/public/logo.svg" width="96" alt="Bloom"></p>

# Bloom — gestión para cafeterías

Sistema de gestión integral para cafeterías, pensado para usarse en el mostrador y en la barra:
**punto de venta, caja, stock con recetas, compras, clientes, alertas, reportes** y un
**asistente para el barista** que registra extracciones y sugiere cómo calibrar el espresso.

Funciona como **aplicación de escritorio para Windows** (un `.exe` con base de datos local SQLite)
y también se puede abrir desde una **tablet o celular en la red local**.

## Funcionalidades

| Módulo | Qué hace |
|---|---|
| **Inicio** | KPIs del día con comparación, ventas por hora, top productos, medios de pago, alertas, receta del día y estado de caja. |
| **Punto de venta** | Pantalla táctil, modificadores (tipo de leche, shot extra…), pagos divididos, vuelto, clientes y puntos, ticket imprimible, atajos de teclado. |
| **Caja** | Apertura, ingresos/egresos, cierre con arqueo por medio de pago e historial de cierres. |
| **Productos** | Menú con categorías, recetas (escandallo) con costo y margen en vivo, aumentos masivos por % e historial de precios. |
| **Stock** | Insumos con semáforo, movimientos, mermas, conteo físico y sugerencia de compra. |
| **Compras** | Proveedores, órdenes de compra, recepción con costo promedio ponderado, facturas, pagos y vencimientos. |
| **Clientes** | Fichas con preferencias, historial, fidelización por puntos y cuenta corriente. |
| **Barista** | Cafés y días desde tueste, equipos y mantenimiento, registro de shots con cronómetro, asistente de calibración, recetas de filtrado paso a paso, calculadoras y estadísticas. |
| **Avisos** | Alertas automáticas (stock, vencimientos, caja, cumpleaños, mantenimiento), tablón del equipo y checklists de apertura/cierre. |
| **Reportes** | Ventas, rentabilidad, stock, mermas, compras y cajas, exportables a Excel y CSV. |
| **Configuración** | Usuarios con roles y PIN, datos del negocio, fidelización, umbrales, respaldos automáticos y modo red local con QR. |

## Ediciones

| | Gratis (este repo) | Pro |
|---|---|---|
| Punto de venta, caja, ventas, productos y recetas, stock, clientes y fidelización, avisos | ✓ | ✓ |
| Usuarios | hasta 2 | ilimitados |
| Asistente de barista y guía de bebidas | | ✓ |
| Compras, proveedores y cuenta corriente | | ✓ |
| Reportes avanzados y exportación a Excel/CSV | | ✓ |
| Menú para clientes (QR y pantalla) | | ✓ |
| Modo red local, descarga de respaldos | | ✓ |

Este repositorio es la edición gratuita, completa y funcional por sí sola. Los módulos Pro se
distribuyen aparte y se activan con una licencia (`Configuración → Licencia`): una licencia
firmada, atada a la computadora, que se valida **sin internet** y se renueva sola cuando hay
conexión. Si una suscripción vence, solo se apagan las funciones Pro: las ventas y los datos
nunca se bloquean.

## Tecnología

- **Backend:** Python 3.12+ · FastAPI · SQLAlchemy 2 · Alembic · SQLite
- **Frontend:** React · TypeScript · Vite · Tailwind CSS · shadcn/ui · TanStack Query · Recharts
- **Escritorio:** pywebview (WebView2) · PyInstaller · Inno Setup

La app es un servidor local que sirve la API y la interfaz; la ventana de escritorio solo la muestra.
La ventana no tiene el marco de Windows: la barra de título (arrastrar, doble clic para maximizar,
minimizar, maximizar, cerrar y bordes para redimensionar) es parte de la app y recuerda su posición y tamaño.
Por eso la misma instalación se puede usar desde otros dispositivos de la red local.

## Desarrollo

Requisitos: Python 3.12+, Node.js 20+, Windows 10/11 (WebView2).

```powershell
./scripts/setup.ps1   # instala dependencias (venv + npm)
./scripts/dev.ps1     # backend (puerto de brand.json) + frontend en :5173
```

Abrí <http://localhost:5173>. La primera vez aparece el asistente de configuración; podés cargar
**datos de ejemplo** (todos ficticios) para explorar la app. Usuarios demo: Caja `1111`, Barista `2222`, Encargado `3333`.

Tests:

```powershell
cd backend; .venv\Scripts\python -m pytest
cd frontend; npx tsc -b
```

### Tests end-to-end

Pruebas de la interfaz con [Playwright](https://playwright.dev) en `frontend/e2e/`:

```powershell
cd frontend
npm run e2e          # headless
npm run e2e:headed   # viendo el navegador
npm run e2e:ui       # modo interactivo de Playwright
```

- Usan el **Microsoft Edge** que viene con Windows (no hace falta descargar navegadores).
  Para usar el Chromium de Playwright: `$env:PW_CHANNEL="chromium"` (antes `npx playwright install chromium`).
- Levantan su propio backend (puerto 47899) y Vite (puerto 5199) con una **base de datos nueva y aislada**
  en una carpeta temporal: no tocan tu `dev.db` ni los servidores de desarrollo que tengas abiertos.
- La configuración inicial se hace con datos de ejemplo (admin "Admin", PIN `0000`).

## Generar el ejecutable

```powershell
./build/build.ps1
```

Genera `build/output/Bloom/Bloom.exe` y, si tenés [Inno Setup 6](https://jrsoftware.org/isinfo.php)
(`winget install --id JRSoftware.InnoSetup -e --scope user`), el instalador
`build/output/installer/Bloom-Setup-<versión>.exe` y su manifiesto de actualización `latest.json`.

El instalador es **por usuario** (sin permisos de administrador): instala en
`%LOCALAPPDATA%\Programs\Bloom`, crea accesos en el menú Inicio (y opcionalmente en el escritorio)
y se desinstala desde *Configuración de Windows → Aplicaciones*. Como no pide permisos, no agrega reglas
de firewall: la primera vez que actives el modo red, Windows pregunta si permitís el acceso (elegí *Permitir*).

Los datos se guardan en `%APPDATA%\Bloom` (base `data.db`, respaldos diarios y log).
Desinstalar la app **no** borra los datos. Al actualizar, la base se migra sola (con un respaldo previo).

### Actualizaciones automáticas

La app busca versiones nuevas un rato después de abrirse y cada 6 horas, en la dirección que indica la
configuración remota del distribuidor (ver abajo) o, si no hay, en `updateManifest` de `brand.json`
(vacío = desactivado). Si hay una, el administrador la ve en
*Configuración → Acerca de* (y un aviso en la barra superior); con *Actualizar ahora* la app descarga el
instalador, lo verifica, hace un respaldo y se cierra; el instalador corre en silencio y la vuelve a abrir.

El manifiesto (`latest.json`) tiene `version`, `url`, `sha256`, `size`, `notes`, `published_at` y
`signature`: una firma Ed25519 de los demás campos hecha con la clave privada del distribuidor (la misma que
firma las licencias; la app trae solo la clave pública). La app **ignora** manifiestos sin firma o con firma
inválida, versiones iguales o anteriores a la instalada, direcciones que no sean `https` y descargas cuyo
tamaño o `sha256` no coincidan. Sin internet no pasa nada: solo se muestra un aviso.

### Configuración remota

Si `brand.json` tiene `licenseServer`, la app descarga cada 6 horas (y unos segundos después de abrirse)
una configuración **firmada** del servidor del distribuidor (`GET <licenseServer>/v1/config`): dirección
del manifiesto de actualizaciones, versión mínima soportada (las anteriores ven *Actualización obligatoria*,
sin bloquear nada), link de novedades, contactos de soporte y links legales (en *Configuración → Acerca de*)
y avisos que se muestran arriba en la app (cada uno se puede cerrar y no vuelve a aparecer).

La firma es Ed25519 con la misma clave que las licencias, sobre `BLOOM-CONFIG1\n` + el JSON canónico del
contenido; se verifica con la clave pública que trae la app (nunca con algo que mande el servidor). Se
rechazan configuraciones sin firma, vencidas o más viejas que la guardada. La última válida queda en la
carpeta de datos (`remote_config.json`) y se usa sin internet. Lo único fijo en la app es la dirección del
servidor y la clave pública; `updateManifest` queda como respaldo para distribuciones sin servidor.

Las suscripciones también pueden recibir un **cambio de precio** anunciado con anticipación: el
administrador lo ve en *Configuración → Licencia → Tu suscripción* (y un aviso arriba) y elige **Aceptar
nuevo precio** o **Cancelar suscripción**; sin aceptación no se cobra el precio nuevo.

### Publicar una versión

1. Subí `version` en `brand.json` (es la única fuente: la usan la app, el instalador y el manifiesto).
2. `./build/build.ps1` → `build/output/installer/Bloom-Setup-<versión>.exe` y `latest.json` **sin firmar**.
   Con `updateManifest = https://github.com/<usuario>/<repo>/releases/latest/download/latest.json`,
   la `url` del instalador apunta a `.../releases/download/v<versión>/Bloom-Setup-<versión>.exe`.
3. Firmá `latest.json` con la clave del distribuidor (completa `sha256`, `size` y `signature`). Si armás
   tu propia distribución, generá tu par de claves y reemplazá `backend/app/licensing/public_key.txt`.
4. Publicá el release con los dos archivos:
   ```powershell
   gh release create v<versión> build/output/installer/Bloom-Setup-<versión>.exe build/output/installer/latest.json --title "Bloom <versión>" --notes "Novedades..."
   ```
   `releases/latest/download/latest.json` siempre apunta al último release, así que las instalaciones
   existentes lo ven en su próxima búsqueda. Para probar sin publicar: `BLOOM_UPDATE_MANIFEST=<url>`
   (solo funciona corriendo desde el código, nunca en el `.exe`).

## Cambiar el nombre, colores o puerto

Todo sale de [`brand.json`](brand.json) en la raíz:

| Campo | Para qué |
|---|---|
| `name`, `tagline`, `description` | Nombre visible (ventana, login, menú, título, instalador) |
| `exeName`, `dataDirName` | Nombre del `.exe` y carpeta de datos en `%APPDATA%` |
| `appId` | Identificador interno (el launcher lo usa para reconocer su propio servidor) |
| `port` | Puerto local del servidor (si está ocupado por otra app, el `.exe` usa el siguiente libre) |
| `colors` | Colores del logo e ícono |
| `version` | Versión de la app (instalador, *Acerca de*, actualizaciones) |
| `updateManifest` | Respaldo: dirección `https` del `latest.json` cuando no hay configuración remota (vacío = sin actualizaciones automáticas) |
| `licenseServer` | (opcional) Servidor de licencias del distribuidor: licencias, suscripciones y configuración remota firmada |

El ícono del `.exe` se regenera solo en `build/build.ps1` (`build/make_icon.py`); el logo de la app es `frontend/public/logo.svg` y `src/components/logo.tsx`.

## Cobros con QR, Point y transferencia (Pro)

La plata va **a la cuenta de cada local**, nunca a Bloom (Configuración → Cobros):

- **QR de Mercado Pago con el monto**: es interoperable en Argentina, así que el cliente lo puede pagar con
  Mercado Pago o con la app de su banco o billetera (MODO y bancos como Santander, Naranja X, Ualá…). Para
  **recibir** el pago, el local necesita una cuenta de Mercado Pago («Conectar Mercado Pago»).
- **Point (posnet)** de Mercado Pago vinculado al local, y **links de pago** (los usan los pedidos online).
- **Transferencia**: para locales que solo tienen cuenta en un banco. El alias/CBU/CVU se muestra en la pantalla
  del cliente y el cajero confirma «Pago recibido».
- **Pantalla del cliente**: una tablet o TV en la red local abre `/pantalla-cliente?token=…` y muestra la compra,
  el total y el QR; después, «¡Pago aprobado!». La venta se registra sola cuando el pago se aprueba.
- La PC del local no recibe webhooks: mientras hay un cobro abierto, la app consulta su estado cada 2 s.
- Otros proveedores (Getnet, Payway, MODO, Naranja X / Ualá Bis) se pueden sumar como adaptadores: ver
  `PLAN.md` §9.

## Seguridad

- Acceso por usuario + PIN con roles; todas las rutas de la API exigen sesión salvo login/configuración inicial.
- Bloqueo progresivo tras 5 PIN incorrectos (por usuario y por dispositivo), PINs con hash Argon2.
- Cambiar PIN, rol o desactivar un usuario cierra sus sesiones.
- El servidor escucha solo en `127.0.0.1`, salvo que actives "Modo red local" en Configuración.
- Encabezados de seguridad, documentación de la API desactivada en el `.exe`, exportaciones protegidas contra inyección de fórmulas.
- Respaldos automáticos diarios y antes de cada migración/restauración.

## Licencia

[MIT](LICENSE)
