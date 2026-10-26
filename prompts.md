> Detalla en esta sección los prompts principales utilizados durante la creación del proyecto, que justifiquen el uso de asistentes de código en todas las fases del ciclo de vida del desarrollo. Esperamos un máximo de 3 por sección, principalmente los de creación inicial o  los de corrección o adición de funcionalidades que consideres más relevantes.
Puedes añadir adicionalmente la conversación completa como link o archivo adjunto si así lo consideras

## Herramientas y modelos usados

| Herramienta | Modelo | Fase |
|---|---|---|
| Claude Code | Sonnet 5 y Sonnet 5.5 | Definición de la idea, investigación técnica (documentación de FirmAR/SIU, antecedentes académicos), decisiones de arquitectura y stack, redacción y verificación de la documentación de la Entrega 1 |
| Claude Code (flujo de diseño) | Sonnet 5 | Mockup interactivo de referencia visual, usado para detectar requisitos (`design/mockup/`) |
| Jira (vía MCP de Atlassian) | — | Carga del backlog en el proyecto `FIRDOC` y mantenimiento de estados y asignaciones durante el desarrollo |
| Claude Code + OpenSpec (comandos `/opsx:propose`, `/opsx:apply`, `/opsx:archive`) | Sonnet 5.5 | Implementación: cada cambio se propone (propuesta, diseño, especificaciones y tareas), se aplica, se prueba y se archiva sincronizando las especificaciones; ver `openspec/` |

No se usaron subagentes ni comandos personalizados en esta fase; el trabajo fue conversacional directo con Claude Code, más búsqueda y lectura web para la investigación de antecedentes y conectores MCP (GitHub, Atlassian).

## Índice

1. [Descripción general del producto](#1-descripción-general-del-producto)
2. [Arquitectura del sistema](#2-arquitectura-del-sistema)
3. [Modelo de datos](#3-modelo-de-datos)
4. [Especificación de la API](#4-especificación-de-la-api)
5. [Historias de usuario](#5-historias-de-usuario)
6. [Tickets de trabajo](#6-tickets-de-trabajo)
7. [Pull requests](#7-pull-requests)
8. [Ajustes humanos sobre el output de la IA](#8-ajustes-humanos-sobre-el-output-de-la-ia)

---

## 1. Descripción general del producto

**Prompt 1:**
> "se puede hacer un proyecto que se pueda integrar o embeber dentro de otro para que cualquier sistema [...] pueda tener su firmador [...] ¿qué te parece esta idea?"

Claude investigó la documentación real de integración de FirmAR (página y PDF de especificación) para entender el flujo real (OAuth + envío de documento + callback) antes de opinar, en lugar de responder con suposiciones.

**Prompt 2:**
> "mi idea con esto es hacer el entregable del master, reutilizar en mi trabajo y si es un buen tema proponer de tesis de grado"

Este dato subió el nivel de exigencia de la documentación (justificación de decisiones, consideraciones legales y de seguridad), más allá del mínimo del máster.

**Prompt 3:**
> "viendo el mockup la idea es poder agarrar un documento previamente adjuntado en mi BD, firmarlo [...] y luego poder descargar [...] o bien que el doc quede como vigente [...] versionado que no pise pero sí quede como la versión activa"

Precisó el caso de uso real (documentos preexistentes, no archivos sueltos) y un requisito de versionado que el texto no había capturado.

---

## 2. Arquitectura del Sistema

### **2.1. Diagrama de arquitectura:**

**Prompt 1:**
> "¿se puede hacer un firmador propio, así como el Firmar, sin necesidad de conectar con ello? ¿o conviene adaptar eso y además hacer el firmador propio?"

Claude propuso el patrón central del proyecto: un "hub de firma" con proveedores intercambiables (motor propio PAdES + adaptador simulado del contrato de FirmAR), en lugar de forzar una sola opción.

**Prompt 2:**
> "actualmente en mi organismo usamos de front Angular [...] ¿se va a poder embeber al proyecto?"

Claude ajustó la decisión de frontend (React) sin descartarla, agregando una capa de compatibilidad (iframe / Web Component).

**Prompt 3:**
Pedido de investigar si existía un firmador comercial equivalente al de un proveedor de expedientes judiciales electrónicos ("hacer algo similar"), y posterior aporte de una investigación previa de un compañero de trabajo (conversación compartida con Claude) para **rearmar la propuesta** como servicio de firma digital institucional. Claude detectó que un token USB no es accesible desde un navegador ni desde un servidor y agregó un tercer proveedor (`token`) basado en un **agente local con PKCS#11**; de la investigación del compañero tomó la **firma diferida** (el servidor prepara el PDF y calcula el hash, el token firma solo el hash, el servidor incrusta la firma), que simplifica el agente y deja la validación en el servidor. No se reutilizó código de esa investigación. Claude verificó contra documentación pública las afirmaciones que sostienen el diseño (firma interrumpida de pyHanko, aviso de acceso a red local de Chrome 142 y su política empresarial) y marcó como **no verificado** el límite de documentos por operación del servicio remoto.

### **2.2. Descripción de componentes principales:**

Sin prompt dedicado: derivada de la conversación de 2.1. La usuaria eligió el stack (Python + pyHanko, FastAPI, React) entre las alternativas propuestas por Claude. Con el proveedor `token` se sumaron el motor PAdES (preparar/completar), la validación de confianza y el Firmadoc Agent.

### **2.3. Descripción de alto nivel del proyecto y estructura de ficheros**

Sin prompt dedicado: derivada de la arquitectura de 2.1 (separación `backend/`, `widget/`, `admin-panel/`).

### **2.4. Infraestructura y despliegue**

Sin prompt dedicado: propuesta redactada por Claude como parte de la documentación; la viabilidad del despliegue on-premise queda pendiente de validar con el área de Sistemas del organismo adoptante.

### **2.5. Seguridad**

Sin prompt dedicado: redactada por Claude, incluyendo la nota de diseño sobre firma electrónica vs. firma digital bajo la Ley 25.506. Tras el cambio de propuesta, el proveedor `token` (certificado de una AC licenciada) produce firma digital y el proveedor `local` (autofirmado) queda como firma electrónica para demostraciones. Se sumaron validación de confianza, desafíos de un solo uso y controles de seguridad del agente local.

### **2.6. Tests**

Sin prompt dedicado: estrategia de tests redactada por Claude. Con el agente local se sumaron pruebas con SoftHSM (PKCS#11 por software, ejecutable en CI), casos de rechazo de la validación y verificación independiente con una herramienta ajena a pyHanko. Los supuestos no verificables se documentaron en la sección 2.7.

---

### 3. Modelo de Datos

**Prompt 1:**
El prompt de versionado de la sección 1 (Prompt 3) derivó en las entidades `Document` y `DocumentVersion`: versiones inmutables, append-only, con un puntero `current_version_id` que se actualiza sin pisar nada.

**Prompt 2:**
Pedido de la usuaria de dejar plasmada la firma **en lote** (varios documentos, una sola confirmación). Claude la modeló como `SignatureBatch`, que agrupa `SignatureRequest` existentes sin cambiar el mecanismo de firma ni de versionado por documento.

---

### 4. Especificación de la API

**Prompt 1:**
Tras el requisito de versionado, se ajustaron `POST /signature-requests`, `GET /signature-requests/{id}` y el webhook para incluir `document_id`, `external_document_id`, `version_number`, `is_active_version` y `download_url`. Con la firma diferida, el flujo principal pasó a `create` / `prepare` / `complete`; se agregaron `POST /signature-batches`, el cambio de estado del documento y la verificación como endpoints adicionales.

---

### 5. Historias de Usuario

**Prompt 1:**
Corrección de la usuaria: descarga y versionado no son alternativas ("y/o"), deben darse **siempre juntas** en toda firma completada. Se ajustaron los criterios de aceptación de las historias 1 a 4.

**Prompt 2:**
La firma en lote se priorizó como *should-have*, no *must-have*, siguiendo la disciplina de alcance de MVP de la Lección 1. Tras el cambio de propuesta se reordenó el backlog: la firma con token y el motor propio (para recorrer los flujos sin hardware) son *must-have*; FirmAR pasó a *should-have*. Se incorporaron los estados de documento `borrador → pendiente de firma (con fecha límite) → firmado` y el listado de firmantes, a propuesta de Claude tras revisar el manual público de un sistema de expediente electrónico judicial; Claude dejó explícito que el comportamiento al vencer el plazo no está definido por la fuente y debe acordarse con cada integrador.

---

### 6. Tickets de Trabajo

**Prompt 1:**
Los tickets de backend, frontend y base de datos se redactaron con tareas, criterios de aceptación y estimación, y se actualizaron tras el cambio de versionado y de propuesta (flujo `prepare`/`complete`). El agente local quedó como ticket adicional, fuera de los 3 detallados.

**Prompt 2 (implementación guiada por especificaciones):**
Cada funcionalidad se pidió con `/opsx:propose <tema>` (por ejemplo: "flujo de firma create prepare complete con motor local", "proveedor token y agente local", "widget de firma react") y se implementó con `/opsx:apply` y se archivó con `/opsx:archive`. Los cambios archivados están en `openspec/changes/archive/` y las especificaciones vigentes en `openspec/specs/`: flujo de firma diferida, proveedor token, agente local, widget, webhooks, firma en lote, estado y verificación de documentos, panel de administración, sello de tiempo, firma remota simulada, elección del método en el widget y base de datos real.

**Prompt 3 (autonomía acotada):**
Se pidió completar el backlog restante "automáticamente" (proponer, aplicar, archivar y confirmar cada cambio sin preguntar entre pasos), con la regla de detenerse ante un riesgo de seguridad o una decisión que cambie el alcance, y de no publicar en GitHub salvo pedido expreso.

---

### 7. Pull Requests

Todavía no se usaron Pull Requests: el trabajo está en commits sobre la rama principal del repositorio de Firmadoc, que se publicaron a pedido de la usuaria. Cada commit referencia la tarea de Jira que cierra.

---

## 8. Ajustes humanos sobre el output de la IA

- La **idea de negocio y el dominio del problema** (firma digital embebible para organismos públicos) los aportó íntegramente la usuaria, a partir de un dolor real de su trabajo; la IA lo analizó y estructuró.
- La usuaria **corrigió el alcance del embebido**: Claude había asumido React como única pieza de frontend; al informar que su organismo usa Angular, se separó la "implementación interna del widget" de la "superficie de embebido" (iframe / Web Component).
- La usuaria **eligió explícitamente el stack** entre las opciones propuestas.
- Los **datos de identidad del proyecto** (nombre, iniciales, nombre "Firmadoc") los aportó la usuaria.
- Por **confidencialidad**, a pedido de la usuaria se removió toda mención al nombre del organismo empleador, usando referencias genéricas.
- El requisito de **versionado** lo detectó la usuaria al revisar visualmente el mockup interactivo de referencia visual (en `design/mockup/`), no desde una especificación escrita: un prototipo temprano destapó un requisito que el texto no había capturado.
- Claude redactó una primera versión con descarga y versionado como alternativas; la usuaria lo **corrigió** (deben darse siempre ambos).
- La firma **en lote** fue pedido de la usuaria; la priorización como *should-have* fue decisión de la IA y la usuaria no la corrigió.
- Por confidencialidad, el README cita el paper académico utilizado como antecedente pero no nombra al organismo, a la provincia ni al proveedor comercial de referencia.
- La usuaria preguntó si el widget podía instalarse en un proyecto Angular y, después, si `<iframe>` estaba deprecado o traía riesgos a futuro. Claude contrastó con fuentes (MDN y artículos técnicos): el elemento no está deprecado (solo atributos de presentación), y detectó tres riesgos reales — delegación del permiso de red local con `allow`, cookies de terceros y cabeceras de embebido — marcando como secundarias las fuentes sobre el atributo `allow`. Al revisar el código del proyecto comprobó que la implementación ya aplicaba el atributo y que el token va en el fragmento de la URL (sin cookies), por lo que el cambio quedó limitado a corregir el ejemplo del README, documentar la alternativa de ventana emergente como **no implementada** y agregar el supuesto a verificar (Firefox/Safari no verificados). Claude propuso una librería Angular envoltorio del iframe como opción; no se implementó.
- Pendiente de revisión humana antes de cerrar la Entrega 1: validar que las estimaciones de horas por ticket sean realistas y confirmar la viabilidad del despliegue on-premise.
- La usuaria **decidió la arquitectura de firma**: el agente local en Python (no en otro lenguaje), el criterio de Angular cubierto con una página anfitriona y una guía (no con una app Angular), y que el widget no incluyera al principio la elección del método, el lote ni la administración (se agregaron después como cambios propios).
- La usuaria **pidió la base de datos real** (con los PDF dentro de la base, conectable con DBeaver y pensada para migrar a la base institucional) y que quedara documentada con su propia tarea de Jira y su cambio de OpenSpec.
- La IA **detectó y corrigió errores propios al verificar**: por ejemplo, un orden de operaciones en `complete` que gastaba la firma del token si fallaba la autoridad de sellado de tiempo, y restricciones duplicadas en la migración inicial que SQLite toleraba y PostgreSQL no (apareció al ejecutar por primera vez la suite contra PostgreSQL).
- La usuaria **pidió el panel como aplicación Angular con PrimeNG** (`frontend/`), para usarlo en la carga de documentos y como ejemplo de cómo se abre el widget desde Angular, y **corrigió el menú lateral** ("hacer bien utilizando PrimeNG"): la primera versión usaba botones sueltos y se reemplazó por el componente `p-menu`.
- Al verificar en Chrome, la IA **detectó que PrimeNG 22 cambió a una licencia comercial** («PrimeUI», con clave obligatoria aunque gratuita para estudiantes) y que su aviso de licencia violaba la CSP del panel; decidió quedarse en **PrimeNG 21 (MIT) con Angular 21** y lo dejó documentado como decisión a revisar si se actualiza.
- La usuaria **pidió el PIN "en el medio de la pantalla sobre el diálogo de Angular"**; la IA explicó que el PIN no puede ingresarse en el navegador (invariante de seguridad del proyecto) y lo resolvió en la ventana nativa del agente: mínima (titular, documento y PIN), centrada y siempre al frente. También pidió poder **simular la firma con token**: se agregó el token de software a la demo y al agente (`--software-token`).
- Quedan para revisión humana: la prueba con un **token físico** (solo se probó con SoftHSM y un token de software), la **firma del instalador** del agente, el contrato real de la firma remota (hoy simulado) y los valores de la política de la **autoridad de sellado de tiempo** institucional.
