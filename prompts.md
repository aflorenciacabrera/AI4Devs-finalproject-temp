> Detalla en esta sección los prompts principales utilizados durante la creación del proyecto, que justifiquen el uso de asistentes de código en todas las fases del ciclo de vida del desarrollo. Esperamos un máximo de 3 por sección, principalmente los de creación inicial o  los de corrección o adición de funcionalidades que consideres más relevantes.
Puedes añadir adicionalmente la conversación completa como link o archivo adjunto si así lo consideras

## Herramientas y modelos usados

| Herramienta | Modelo | Fase |
|---|---|---|
| Claude Code | Sonnet 5 y Sonnet 5.5 | Definición de la idea, investigación técnica (documentación de FirmAR/SIU, antecedentes académicos), decisiones de arquitectura y stack, redacción y verificación de la documentación de la Entrega 1 |
| Claude Code (flujo de diseño) | Sonnet 5 | Mockup interactivo de referencia visual, usado para detectar requisitos (`design/mockup/`) |
| Jira (vía MCP de Atlassian) | — | Carga del backlog en el proyecto `FIRDOC` |

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

---

### 7. Pull Requests

Pendiente: la Entrega 1 es 100% documentación, sin código. Se completará desde la Entrega 2.

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
- Pendiente de revisión humana antes de cerrar la Entrega 1: validar que las estimaciones de horas por ticket sean realistas y confirmar la viabilidad del despliegue on-premise.
