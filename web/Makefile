# Developer entry points for the panel. Normally reached from the repo root,
# which delegates here; standalone use works too.

REPO_ROOT := $(abspath $(CURDIR)/..)
VENV := $(REPO_ROOT)/.venv
PYTHON ?= python3
DOCKER ?= docker
NPM ?= npm

IMAGE ?= ghcr.io/oberon-systems/awg-keeper/panel
# The sub-project tag is what a release is: awg-keeper-web-v1.2.3 builds 1.2.3.
VERSION ?= $(shell git -C $(REPO_ROOT) describe --tags --abbrev=0 \
	--match 'awg-keeper-web-v*' 2>/dev/null | sed 's/^awg-keeper-web-v//')
VERSION := $(if $(VERSION),$(VERSION),0.0.0)

.DEFAULT_GOAL := help

.PHONY: help lint test run secrets bump ui image clean

help:  ## Show the available targets
	@echo "awg-keeper panel $(VERSION)"
	@echo
	@echo "Targets:"
	@awk 'BEGIN {FS = ":.*## "} /^[a-z-]+:.*## / {printf "  %-8s %s\n", $$1, $$2}' \
		$(MAKEFILE_LIST)

lint:  ## Run ruff over the panel sources and eslint over the ui
	@if [ -x $(VENV)/bin/ruff ]; then \
		$(VENV)/bin/ruff check .; \
	else \
		$(PYTHON) -m ruff check .; \
	fi
	cd ui && $(NPM) run lint

test:  ## Run the unit tests against a stub agent and a temporary database
	@if [ -x $(VENV)/bin/pytest ]; then \
		$(VENV)/bin/pytest -q; \
	else \
		$(PYTHON) -m pytest -q; \
	fi

# scripts/bump.sh reads only the commits that touched web/ and reads
# web/.cz.yaml, so the version and the tag it writes are the panel's alone.
bump:  ## Bump the panel version from the panel commits and tag it
	@if [ -x $(VENV)/bin/cz ]; then \
		CZ=$(VENV)/bin/cz scripts/bump.sh; \
	else \
		CZ="$(PYTHON) -m commitizen" scripts/bump.sh; \
	fi

ui:  ## Build the single page application into ui/dist
	cd ui && $(NPM) install --no-audit --no-fund && $(NPM) run build

image:  ## Build the panel container image
	DOCKER_BUILDKIT=1 $(DOCKER) build -t $(IMAGE):$(VERSION) -t $(IMAGE):latest .

run:  ## Run the panel in the foreground, reading AWG_PANEL_* from the environment
	@if [ -x $(VENV)/bin/python ]; then \
		PYTHONPATH=src $(VENV)/bin/python -m awg_panel; \
	else \
		PYTHONPATH=src $(PYTHON) -m awg_panel; \
	fi

secrets:  ## Mint the panel's secrets - pass ARGS=--ask to type the password
	@if [ -x $(VENV)/bin/python ]; then \
		PYTHONPATH=src $(VENV)/bin/python -m awg_panel.provision $(ARGS); \
	else \
		PYTHONPATH=src $(PYTHON) -m awg_panel.provision $(ARGS); \
	fi

clean:  ## Remove the built interface
	rm -rf ui/dist ui/node_modules
