# Imagen, pipeline y secretos

Qué se construye, qué garantiza cada trabajo del pipeline, qué **no** comprueba y qué secretos existen. Un
pipeline en verde significa que ninguna de las comprobaciones que hay falló; esta página dice cuáles hay.

## La imagen del servidor

`Dockerfile` (raíz) construye una sola imagen con la API, el widget y el panel. Tiene tres etapas de
construcción (widget con Node, panel con Node, dependencias de Python en un entorno virtual) y una final que solo
lleva lo necesario para ejecutar.

| Va en la imagen final | Queda afuera |
|---|---|
| Python 3.12 y las dependencias de ejecución (`pyproject.toml`) | Node, npm y los `node_modules` |
| El código del servidor (`backend/src`) | El código fuente del widget y del panel |
| `widget/dist` y el build del panel | Dependencias de desarrollo (pytest, ruff, playwright) |
| Migraciones (`backend/migrations`, `alembic.ini`) | Pruebas, documentación, specs y el agente local |
| Anclas de confianza públicas (`backend/trust/*.crt`) | `.env`, bases `*.db`, `data/` y claves privadas de prueba |

- Corre como el usuario sin privilegios `firmadoc` (uid 10001). Solo puede escribir en `/app/data`.
- **No hay ninguna variable de configuración con valor dentro de la imagen.** Todo `FIRMADOC_*` entra al
  arrancar el contenedor (`.env.example` las lista).
- El comando por defecto migra y recién después arranca (`alembic upgrade head && uvicorn ...`): si la
  migración falla, el contenedor termina y no se sirve nada. Las migraciones solo agregan; volver a la
  imagen anterior no deshace una migración ya aplicada.
- El agente local no va en la imagen: corre en la PC de quien firma (`agent/README.md`).

```bash
make image        # construye firmadoc:local desde cero
make image-run    # PostgreSQL + Firmadoc en modo demostración, en contenedores; muestra el token
make image-stop   # los detiene (los datos quedan en los volúmenes)
```

`make image-run` usa el perfil `demo` de `docker-compose.yml`. El modo demostración genera su propio token
de administración y sus secretos dentro del volumen `firmadoc-demo-data`, así que el archivo de compose no
tiene ninguno escrito. Otro puerto: `make image-run DEMO_PORT=8010` con `FIRMADOC_DEMO_PORT=8010` en el
entorno (el puerto publicado y el del contenedor son el mismo a propósito: el widget solo se embebe desde
el origen con el que se abre el panel). La firma con token desde esa demo usa el agente de la PC, igual que
sin contenedores.

Para una instalación real, la misma imagen se arranca con su configuración:

```bash
docker run --rm -p 8000:8000 --env-file .env -v firmadoc-data:/app/data firmadoc:local
```

con, como mínimo, `FIRMADOC_DATABASE_URL`, `FIRMADOC_PUBLIC_BASE_URL`, `FIRMADOC_SIGNING_SECRET` y
`FIRMADOC_ADMIN_TOKEN` (y `FIRMADOC_REAL_MODE=true`, que rehúsa arrancar con una configuración insegura;
`docs/real-mode.md`). Se despliega una etiqueta concreta de la imagen, no `latest`.

## El pipeline: un trabajo por pregunta

`.github/workflows/ci.yml`. Corre en cada pull request, en cada push a `main` y a mano.

| Trabajo | Pregunta que responde | Qué **no** afirma |
|---|---|---|
| `backend` | ¿Pasa el lint y la suite del backend en una máquina limpia, contra un PostgreSQL real? | Nada sobre un token físico ni sobre la TSA o la firma remota reales (se simulan) |
| `agent` | ¿El agente firma con un token PKCS#11 por software (SoftHSM) y su diálogo funciona? | Que funcione con el middleware de un fabricante |
| `agent-windows` | ¿El agente se prueba y se empaqueta en Windows? | Que el instalador esté firmado ni que se despliegue por política de dominio |
| `widget` | ¿El widget compila con tipos estrictos y pasa lint, pruebas y accesibilidad (axe)? | Cómo se ve: no hay comparación visual |
| `frontend` | ¿El panel pasa sus pruebas y compila? | Accesibilidad ni aspecto del panel |
| `e2e` | ¿Los recorridos críticos funcionan en un Chrome real? | Firefox, Safari ni Edge (Edge se prueba a mano con `FIRMADOC_E2E_BROWSER=msedge`) |
| `image` | ¿La imagen se puede fabricar desde cero? | Que arranque ni que firme: eso es `make image-run` en una PC |
| `lint-workflows` | ¿Los archivos del pipeline son válidos (actionlint)? | Que hagan lo que dicen |

Lo que **ningún** trabajo comprueba hoy: vulnerabilidades de dependencias y de la imagen, secretos
filtrados en el historial, análisis estático de seguridad, cobertura, rendimiento, el despliegue (no hay) y
la firma con hardware.

Reglas del archivo:

- **Un solo comando en los dos sitios.** Los trabajos de Python llaman a `make lint`, `make test-backend`,
  `make test-agent` y `make test-e2e` con `PYTHON=python`; son los mismos atajos que se usan en una PC.
- **Permisos mínimos.** Sin permisos por defecto (`permissions: {}`); cada trabajo declara `contents: read`.
- **Acciones fijadas a un commit completo**, con la versión en el comentario. `.github/dependabot.yml`
  avisa cuando hay que moverlas (y lo mismo para pip y npm).
- **Una ejecución por rama:** un push nuevo cancela la anterior.
- **El recuento de pruebas va en el resumen de la ejecución** (`.github/scripts/pytest_summary.py`), con
  un aviso si un nivel no ejecutó ninguna prueba o si hubo omitidas.
- `make ci-lint` valida los workflows en una PC con la misma herramienta que el trabajo `lint-workflows`.

No hay trabajos de despliegue ni de infraestructura: todavía no existe un destino (FIRDOC-42). Cuando
exista, esa mitad solo correrá para cambios del propio repositorio, porque un cambio que viene de un fork
no recibe secretos.

## Secretos

El pipeline **no usa ningún secreto**: construye y prueba con valores descartables (la contraseña del
PostgreSQL de servicio y la clave del integrador de demostración no dan acceso a nada).

Los que sí existen son de ejecución. Se listan sin valores; viven en el entorno del contenedor, nunca en el
repositorio ni en la imagen.

| Variable | Para qué sirve | Si se filtra | Cómo se cambia |
|---|---|---|---|
| `FIRMADOC_ADMIN_TOKEN` | Entrar al panel y a `/api/v1/admin` | Acceso de administración completo | Se reemplaza y se reinicia; las sesiones abiertas dejan de valer |
| `FIRMADOC_SIGNING_SECRET` | Firmar los enlaces del widget (`#t=`) | Se podrían fabricar enlaces de firma válidos | Se reemplaza; los enlaces emitidos vencen solos (`FIRMADOC_SIGNING_TOKEN_TTL_SECONDS`) |
| `FIRMADOC_FIRMAR_CLIENT_SECRET` | Autenticarse ante el servicio de firma remota | Operar ante ese servicio como Firmadoc | En el servicio remoto y acá |
| `FIRMADOC_FIRMAR_CALLBACK_SECRET` | Verificar el HMAC del callback de la firma remota | Se podrían falsificar avisos de «firmado» | Se reemplaza en los dos extremos |
| Contraseña de la base (en `FIRMADOC_DATABASE_URL`) | Conectarse a PostgreSQL | Lectura y escritura de documentos y auditoría | En PostgreSQL y en la URL |
| API key y secreto de webhook de cada integrador | Los genera el panel y se muestran una sola vez; de la API key se guarda solo el hash | Operar como ese integrador o falsificar sus avisos | «Rotar» en el panel (Integradores) |
| Clave del certificado propio (`data/local-cert`) | Firma de demostración (`local`) | Firmas de demostración a nombre de Firmadoc | «Rotar certificado» en el panel (Confianza) |

No son secretos (configuración que puede verse): `FIRMADOC_PUBLIC_BASE_URL`, `FIRMADOC_TSA_URL`,
`FIRMADOC_TRUST_DIR`, los orígenes permitidos y el resto de `.env.example`.

El PIN del token y su clave privada no figuran porque nunca llegan al servidor.
