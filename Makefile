# Atajos de desarrollo de Firmadoc.
# make help

ifeq ($(OS),Windows_NT)
PYTHON := .venv/Scripts/python.exe
export PYTHONUTF8 := 1
else
PYTHON := .venv/bin/python
endif

WIDGET_DIST := widget/dist/index.html
PANEL_DIST := frontend/dist/firmadoc-panel/browser/index.html

.PHONY: help install build build-widget build-panel demo agent test

help:
	@echo make install       entorno virtual, pip y npm
	@echo make build         recompila widget y panel
	@echo make demo          compila si falta el build y arranca la demo en :8000
	@echo make agent         agente con token de software (PIN 1234)
	@echo make test          pytest
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

test:
	$(PYTHON) -m pytest
