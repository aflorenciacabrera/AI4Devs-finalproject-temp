# syntax=docker/dockerfile:1
# Imagen del servidor de Firmadoc: API, widget de firma y panel de administración en un solo proceso.
# Tres etapas construyen (widget, panel, paquete Python) y la final solo lleva lo que hace falta para ejecutar:
# ni Node, ni el código fuente de los frontends, ni dependencias de desarrollo, ni ningún .env.
# La configuración (FIRMADOC_*) entra al arrancar el contenedor, nunca al construir la imagen.
# El agente local (agent/) no va en la imagen: corre en la PC de quien firma.

# --- Widget de firma (React + Vite) -------------------------------------------------------------------
FROM node:22-slim AS widget-build
WORKDIR /src/widget
# Primero solo las dependencias: esta capa se reutiliza mientras no cambie el lockfile.
COPY widget/package.json widget/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY widget/ ./
RUN npm run build

# --- Panel de administración (Angular + PrimeNG) ------------------------------------------------------
FROM node:22-slim AS panel-build
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- Dependencias de ejecución de Python, en un entorno virtual ---------------------------------------
# Se instala el proyecto para resolver sus dependencias (pyproject.toml) y se quita el paquete: el código
# viaja aparte, en /app/backend/src, con la misma disposición que el repositorio. El modo demostración y
# las migraciones ubican alembic.ini, las anclas y los builds a partir de esa ruta.
FROM python:3.12-slim AS python-build
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
WORKDIR /src
COPY pyproject.toml ./
COPY backend/src ./backend/src
RUN pip install --no-cache-dir . && pip uninstall --yes firmadoc

# --- Imagen final -------------------------------------------------------------------------------------
FROM python:3.12-slim
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin firmadoc
WORKDIR /app
COPY --from=python-build /opt/venv /opt/venv
COPY alembic.ini ./
COPY backend/src ./backend/src
COPY backend/migrations ./backend/migrations
# Anclas de confianza (certificados públicos de las AC). Las claves privadas de prueba no viajan (.dockerignore).
COPY backend/trust ./backend/trust
COPY --from=widget-build /src/widget/dist ./widget/dist
COPY --from=panel-build /src/frontend/dist/firmadoc-panel/browser ./frontend/dist/firmadoc-panel/browser
# Único directorio con escritura: datos locales (certificado propio, almacenamiento en disco, datos de la demo).
RUN mkdir -p /app/data && chown firmadoc:firmadoc /app/data
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONPATH=/app/backend/src \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
USER firmadoc
EXPOSE 8000
VOLUME ["/app/data"]
# Migrar y recién después arrancar: si la migración falla, el contenedor termina y no se sirve nada.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn firmadoc.main:app --host 0.0.0.0 --port 8000"]
