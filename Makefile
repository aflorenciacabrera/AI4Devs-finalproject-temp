# Atajos de desarrollo de Firmadoc.
# make help
#
# El pipeline (.github/workflows/ci.yml) llama a estos mismos atajos con PYTHON=python: lo que corre en la
# máquina limpia es lo mismo que corre en la tuya.

ifeq ($(OS),Windows_NT)
PYTHON ?= .venv/Scripts/python.exe
export PYTHONUTF8 := 1
else
PYTHON ?= .venv/bin/python
endif

WIDGET_DIST := widget/dist/index.html
PANEL_DIST := frontend/dist/firmadoc-panel/browser/index.html

IMAGE := firmadoc:local
DEMO_PORT ?= 8000
ACTIONLINT_IMAGE := rhysd/actionlint:1.7.12

.PHONY: help install build build-widget build-panel demo agent lint test test-backend test-agent test-e2e \
	image image-run image-stop ci-lint

help:
	@echo make install       entorno virtual, pip y npm
	@echo make build         recompila widget y panel
	@echo make demo          compila si falta el build y arranca la demo en :8000
	@echo make agent         agente con token de software (PIN 1234)
	@echo make lint          ruff
	@echo make test          toda la suite de pytest (backend, navegador y agente)
	@echo make test-backend  pytest tests            make test-agent  pytest agent/tests
	@echo make test-e2e      pytest tests/e2e (Chrome real; necesita el widget compilado)
	@echo make image         construye la imagen $(IMAGE)
	@echo make image-run     levanta la demo en contenedores (DEMO_PORT=8000) y muestra el token
	@echo make image-stop    detiene los contenedores (los datos quedan en los volumenes)
	@echo make ci-lint       valida los workflows con actionlint (usa Docker)
	@echo ARGS=--reset       se reenvia a demo, por ejemplo: make demo ARGS=--reset

install:
	python -m venv .venv
	$(PYTHON) -m pip install -e ".[dev]"
	cd widget && npm install
	cd frontend && npm install

build-widget:
	cd widget && npm run build

build-panel:
	cd frontend && npm run build

build: build-widget build-panel

$(WIDGET_DIST):
	cd widget && npm run build

$(PANEL_DIST):
	cd frontend && npm run build

demo: $(WIDGET_DIST) $(PANEL_DIST)
	$(PYTHON) -m firmadoc.demo $(ARGS)

agent:
	$(PYTHON) -m firmadoc_agent run --software-token data/demo/token/firmante.pem --origin http://localhost:8000

lint:
	$(PYTHON) -m ruff check .

test:
	$(PYTHON) -m pytest $(ARGS)

test-backend:
	$(PYTHON) -m pytest tests $(ARGS)

test-agent:
	$(PYTHON) -m pytest agent/tests $(ARGS)

test-e2e:
	$(PYTHON) -m pytest tests/e2e -v $(ARGS)

# Imagen del servidor (Dockerfile): se construye desde cero, sin nada de esta PC salvo el repositorio.
image:
	docker build -t $(IMAGE) .

# Base y demo en contenedores. El token de administración lo genera la demo: sale en sus registros.
image-run:
	docker compose --profile demo up -d --wait
	docker compose logs demo --no-log-prefix --tail 40
	curl -s http://localhost:$(DEMO_PORT)/health

image-stop:
	docker compose --profile demo down

# Valida .github/workflows/ sin instalar nada: la imagen oficial de actionlint, con el repositorio montado.
ci-lint:
	docker run --rm -v "$(CURDIR):/repo" -w /repo $(ACTIONLINT_IMAGE) -color
