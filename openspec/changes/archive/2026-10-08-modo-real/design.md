## Context

La configuración permite combinar cualquier cosa: revocación `soft-fail` u `off`, proveedor `local` activo, simulado de firma remota, webhooks hacia `http` o hosts privados, sin anclas. Es cómodo para desarrollar y peligroso en un entorno real: una firma "válida" podría no haber consultado la revocación, o una firma de demostración podría pasar por firma digital.

## Goals / Non-Goals

**Goals:** que el entorno real no pueda arrancar mal configurado y que un error de configuración se diga con claridad antes de operar.

**Non-Goals:** automatizar la obtención de anclas, validar el hardware (ver proposal).

## Decisions

1. **Una sola bandera explícita (`FIRMADOC_REAL_MODE`), apagada por defecto.** El modo demostración sigue intacto y las pruebas existentes no cambian. Alternativa descartada: inferir "producción" de otras variables (frágil y sorpresivo).
2. **Fallar al arrancar, no al primer uso.** En modo real el *lifespan* ejecuta la verificación previa y, si hay errores, levanta una excepción con la lista completa: el proceso no queda sirviendo con una configuración insegura. Se informan **todos** los errores juntos, no de a uno.
3. **Qué es un error en modo real** (impide arrancar): falta el secreto del widget; la revocación no es `hard-fail`; con `hard-fail` no hay ninguna fuente de revocación (ni consulta por red ni CRL local); no hay ninguna ancla raíz en el directorio de confianza; el simulado de firma remota está habilitado; los webhooks permiten `http` o hosts privados. **Advertencia** (se informa, no impide): base SQLite, URL pública sin `https`, administración sin token, almacén en disco. **Información**: el proveedor `local` está deshabilitado.
4. **`hard-fail` exigido, no `soft-fail`**: con `soft-fail` un certificado revocado pasa si la consulta falla (por ejemplo, la AC no responde). En un entorno real preferimos rechazar una firma legítima que aceptar una revocada; es la política que la propuesta ya describe.
5. **`local` fuera del modo real**, no solo advertido: es una firma electrónica de demostración con un certificado autofirmado; en un entorno real puede confundirse con una firma digital. Se rechaza al crear la solicitud con el mismo error de "no habilitado". El proveedor `firmar` se habilita solo si hay servicio configurado (y el simulado no puede estar activo).
6. **El seed se niega en modo real** (salida con código distinto de cero): evita cargar el sistema integrador de demostración con una API key pública. Los integradores reales se crean con `python -m firmadoc.integrators`.
7. **La verificación previa es una función pura sobre `Settings`** (más la carpeta de confianza), sin red ni base de datos: se prueba con tablas de casos y sirve igual de comando y de chequeo al arrancar.

## Risks / Trade-offs

- `hard-fail` puede rechazar firmas si la AC no publica CRL/OCSP accesible desde el servidor; la guía lo advierte y el diagnóstico de revocación forma parte de la puesta en marcha.
- Un modo real que "pasa" la verificación no prueba que el hardware funcione: la guía lo dice explícitamente y lista lo que falta probar con el token físico.
