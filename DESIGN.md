# Silver Usage Report Design System

Referencia visual principal: captura de `silver.dev`.

Este documento reemplaza el sistema anterior. El objetivo no es duplicar CSS propietario, sino traducir el lenguaje visual de Silver a este producto: utilitario, editorial, denso, directo y con superficies de borde firme.

## Principios

- **Primero herramienta, despues decoracion.** La primera pantalla debe permitir crear o recuperar un reporte sin pasar por una landing.
- **Hero negro Silver.dev.** Fondo near-black, serif gigante, palabras coral, header negro con marca blanca y CTA coral.
- **Densidad alta.** Menos aire vertical, mas informacion por bloque, grillas compactas y tablas escaneables.
- **Jerarquia por lineas, no por sombras.** Los paneles se separan con bordes, divisores y contraste tipografico.
- **Marca funcional.** Header fijo con logo Silver.dev, nav uppercase y boton coral como en la captura.
- **Un solo modo.** La interfaz queda fija en el modo negro de Silver.dev; no hay selector claro/oscuro.

## Tokens

### Tipografia

- Hero display: `Georgia`, `Times New Roman`, serif.
- UI: `Geist`, `Arial`, system sans.
- Mono / numeros: `Geist Mono`, `SFMono-Regular`, `Consolas`, monospace.
- H1 hero: `clamp(4rem, 8.8vw, 8.75rem)`, serif, `line-height: .92`, max width amplio.
- Labels: uppercase, `11px`, letter spacing positivo.
- Numeros: monospace siempre en metricas, tablas y codigos.

### Color base

- Background: `#030303`
- Foreground: `#f7f3ea`
- Surface: `#0b0b0a`
- Muted surface: `#151311`
- Border: `rgba(247, 243, 234, .16)`
- Primary / coral: `#ff4b36`
- Primary hover: `#ff664f`
- Primary foreground: `#ffffff`
- Danger: `#a03324`
- Success: `#2f6946`
- Warning: `#8a5b12`

## Componentes

### Header

- Fixed top, ancho completo, fondo negro.
- Brand `Silver.dev` en blanco con mark geometrico.
- Nav compacta con underline animado y desplazamiento vertical minimo.
- CTA coral a la derecha.

### Hero / Home

- Layout full-width negro.
- H1 serif enorme con palabras coral.
- Lede blanca compacta.
- Formulario funcional debajo, como reemplazo operativo del CTA de la landing.
- Banda de marcas/capacidades inmediatamente debajo del hero.

### Capitulos

- `Getting Started is Simple`: titulo centrado, palabra coral y pasos compactos.
- Secciones negras, amplias y centradas, siguiendo la pagina completa de `silver.dev`.

### Paneles

- Bordes de 1px, radio bajo-medio (`10px`).
- Padding compacto: `clamp(18px, 2.5vw, 28px)`.
- Sin sombras salvo interaccion minima.
- `panel-heading` con titulo y descripcion alineados para lectura rapida.

### Metricas

- Grilla densa con `grid-auto-flow: dense`.
- Cards separadas por borde, sin fondos muy alejados del canvas.
- Numeros grandes en mono, labels uppercase.

### Tablas

- Header sticky cuando aplique.
- Celdas compactas, bordes horizontales, numeros monospace.
- Hover con surface muted, sin zebra fuerte.

### Formularios

- Label arriba del input.
- Inputs transparentes/surface, borde firme.
- Focus con outline coral de 2px.
- Estados danger/success/warning legibles sobre fondo negro.

## Tailwind v4

El proyecto usa Tailwind v4 como pipeline CSS:

```bash
npm run build:css
```

Fuente:

- `app/web/static/styles.tailwind.css`

Salida servida por FastAPI:

- `app/web/static/styles.css`

La salida compilada queda versionada para que Docker no necesite Node en runtime.

## Checklist visual

- Header negro estilo Silver.dev aplicado.
- H1 serif/coral en 2-3 lineas maximas en desktop.
- Formulario visible en primera pantalla.
- Grillas sin huecos muertos (`grid-auto-flow: dense`).
- Botones con contraste AA sobre fondo negro.
- Cards oscuras con foreground legible.
- Sin paleta lila/neon.
- Sin decoracion orbital, blobs o gradientes genericos.
