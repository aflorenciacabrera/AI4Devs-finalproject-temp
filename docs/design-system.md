# Catálogo de interfaz

Los nombres de lo que ya existe en el panel (`frontend/`) y en el widget (`widget/`). Sirve para que quien
arme o pida una pantalla —una persona o un agente de IA— **elija** entre piezas con nombre en lugar de
inventar otras parecidas. Antes de crear una clase, un color o un componente nuevo, buscarlo acá.

No hay Storybook ni comparación visual: para un panel de cinco pantallas es más herramienta que problema.
Lo que sí se comprueba está al final.

## Colores: se nombra la intención, no el valor

**Regla:** en el panel y en el widget no se escriben colores a mano. Los valores literales viven en una sola
capa (`frontend/src/app/core/preset.ts` y dos en `frontend/src/styles.css`; `widget/src/styles/tokens.css`, el resto) y todo lo demás apunta
a un nombre.

### Panel (tema Aura de PrimeNG con la paleta de Firmadoc)

La paleta —acento azul `#1f5fbf` en claro y `#6ea3f2` en oscuro, y grises azulados— es la misma del panel
estático y se define una sola vez, en `frontend/src/app/core/preset.ts`.

| Para… | Token |
|---|---|
| Fondo de la página | `--bg` (propio: `#f6f7f9` claro, `#14171c` oscuro) |
| Fondo de tarjetas, tablas y menú | `--p-content-background` |
| Bordes y separadores | `--p-content-border-color` |
| Texto | `--p-text-color` |
| Texto secundario (ayudas, subtítulos, encabezados de tabla) | `--p-text-muted-color` |
| Acción principal y elemento activo del menú | `--p-primary-color` (texto encima: `--p-primary-contrast-color`) |
| Fondo de íconos destacados | `--p-highlight-background` |
| Advertencia en la línea de tiempo | `--warning` (propio) |
| Éxito y error en la línea de tiempo | `--p-green-600`, `--p-red-500` |

Los **estados** no usan colores sueltos: son un `p-tag` con severidad, y la correspondencia está en un solo
lugar (`statusSeverity` en `frontend/src/app/core/format.ts`):

| Estado | Severidad |
|---|---|
| `signed`, `delivered`, `active` | `success` |
| `pending`, `signing`, `pending_signature` | `warn` |
| `failed`, `disabled` | `danger` |
| cualquier otro (por ejemplo `draft`) | `secondary` |

El modo oscuro no se programa por pantalla: cambia `data-theme` en `<html>` y los tokens hacen el resto.

### Widget (`widget/src/styles/tokens.css`)

| Para… | Token |
|---|---|
| Fondo propio | `--bg` (transparente: el widget se ve sobre lo que lo embebe) |
| Tarjetas y opciones | `--surface`, `--surface-2` |
| Bordes | `--border` |
| Texto, secundario y terciario | `--text`, `--text-2`, `--text-3` |
| Marca y acción principal | `--brand` (texto encima: `--on-brand`), `--brand-tint` |
| Estados | `--teal` (bien), `--amber` (atención), `--red` (error), cada uno con su `-tint` |
| Foco del teclado | `--focus` |

El anfitrión elige el modo con `?theme=light|dark` y, si quiere sus colores, el acento con `?accent=<nombre>`
(lista cerrada: `blue`, que es lo que usa el panel, y `emerald`). Agregar un acento es agregar un bloque en `tokens.css` y su nombre
en `ACCENTS` (`widget/src/bootstrap/token.ts`); nunca un color libre por URL.

## Piezas del panel

Primero un componente de PrimeNG; una clase propia solo cuando PrimeNG no lo cubre.

| Pieza | Qué es | Cómo se arma |
|---|---|---|
| Menú lateral | Secciones, marca, tema y cierre de sesión | `p-menu` dentro de `.sidebar`; en pantallas angostas, el mismo contenido en un `p-drawer` |
| Encabezado de pantalla | Título y una línea de contexto | `<header class="page-head">` con `h2` y `p.muted` |
| Tabla con marco | Una tabla con su título, filtros y pie | `.table-card` → `.table-card-head` (título y filtros cortos) o `.filters` → `p-table` → `.pager` |
| Filtros | Campos en fila que bajan de línea solos | `form.filters`; `label.filter-wide` para el campo ancho; `.filter-actions` para los botones |
| Celda de dos líneas | Dato principal y un detalle chico | `.cell-main` + `small.cell-sub` |
| Acciones de fila | Botones chicos con ícono y texto | `p-button size="small"` dentro de `.row-actions`; columna `.col-actions` |
| Estado | Etiqueta de color | `p-tag` con `statusSeverity(...)`, `[rounded]="true"` |
| Tabla vacía | Ícono, qué pasa y qué hacer | `.empty-state` dentro de `#emptymessage` |
| Tarjeta de contenido | Bloque con título | `p-card` (`styleClass="panel-card"` en el detalle) |
| Documento cargado | Nombre, datos y acciones del PDF | `p-card.doc-card` con `.doc-row`, `.doc-tags`, `.doc-actions`, `.doc-footer` |
| Módulo de firma | El widget como una tarjeta más | `p-card.sign-widget` con `<app-widget-frame>`; al lado del documento con `.sign-ready.with-widget` |
| Carga de archivos | Zona para arrastrar y lista | `p-fileupload` con `.upload`, `.dropzone-hint`, `.upload-list`, `.upload-item` |
| Línea de tiempo | Cadena de custodia | `ol.timeline` con `li.ok`, `li.warning`, `li.error` |
| Clave y valor | Detalle técnico | `dl.kv` |
| Credenciales de un solo uso | Claves que se muestran una vez | `.credentials` con `code` |
| Aviso dentro de la pantalla | Algo que conviene saber antes de actuar | `p-message severity="warn"` con ícono de advertencia; `severity="error"` solo para errores, y el resultado de una firma usa `success` o `error` |
| Aviso y confirmación | Mensajes y preguntas | `p-toast` (vía `AdminApi.ok/fail`) y `p-confirmdialog` (vía `ConfirmationService`) |

Convenciones: botones siempre con texto (el ícono acompaña, no reemplaza); la acción destructiva lleva
`severity="danger"`; el texto en mono (`.mono`) es para huellas, URL y hashes.

## Piezas del widget

| Pieza | Archivo | Qué es |
|---|---|---|
| Pantalla | `components/Screen.tsx` | Título, cuerpo y acciones al pie; toda pantalla del flujo se arma con esto |
| Tarjeta del documento | `components/DocumentCard.tsx` | Nombre, páginas, tamaño y estado |
| Aviso | `components/Notice.tsx` | `.alert--info` y `.alert--error` |
| Opción de método | clases `.choice-card` (`--selected`, `--disabled`) | Token, remota o propia |
| Certificado | clases `.cert` (`--selected`, `--expired`) | Un certificado del token |
| Pasos | clases `.steps`, `.step` (`--active`, `--done`) | Avance mientras se firma |
| Resultado de lote | clases `.result-list`, `.result-item` (`--signed`, `--failed`) | Qué documento se firmó y cuál no |
| Botones | `.btn--primary`, `.btn--secondary` | Una acción principal por pantalla |

Las pantallas (`widget/src/screens/`): `ChooseProvider`, `ChooseCertificate`, `CertRejected`, `AgentMissing`,
`AwaitingPin`, `ConfirmLocal`, `ConfirmRemote`, `RemoteWaiting`, `Success`, `BatchResult`. Los textos están
en `widget/src/messages/es.ts`.

## Qué se comprueba, y qué no

| Pregunta | Dónde | Estado |
|---|---|---|
| ¿Se comporta bien cada pieza y cada pantalla? | Vitest: `widget/tests/`, `frontend/src/app/**/*.spec.ts` | Sí |
| ¿Es accesible? (roles, nombres, etiquetas, estructura) | axe: `widget/tests/*.test.tsx` y `frontend/src/app/a11y.spec.ts`, pantalla por pantalla y en sus estados menos frecuentes (vacío, detalle, error, diálogo abierto) | Sí, salvo el contraste de color |
| ¿Funcionan los recorridos completos? | `tests/e2e/` en Chrome real | Sí, para el widget y el panel estático; el panel Angular no tiene recorrido en navegador |
| ¿Se ve como debe? | — | **No se comprueba.** No hay comparación visual; las capturas del README se regeneran a mano (`docs/img/generar.py`) |

Dos hallazgos de la primera pasada de axe sobre el panel, por si reaparecen: el botón «X» del diálogo de
confirmación de PrimeNG 21 no tiene nombre accesible (se quitó: el diálogo se cierra con su botón de rechazo
o con Escape), y ese mismo componente deja un elemento con rol de diálogo vacío aunque esté cerrado (se
excluye de la revisión a propósito, con el motivo escrito en la prueba).
