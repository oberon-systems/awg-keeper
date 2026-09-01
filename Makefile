# Developer entry points for awg-keeper. Run `make` for the target list.

VENV ?= .venv
PIP := $(VENV)/bin/pip

.DEFAULT_GOAL := help

.PHONY: help init lint clean

help:  ## Show the available targets
	@echo "awg-keeper"
	@echo
	@echo "Targets:"
	@awk 'BEGIN {FS = ":.*## "} /^[a-z-]+:.*## / {printf "  %-8s %s\n", $$1, $$2}' \
		$(MAKEFILE_LIST)

init:  ## Create the virtualenv, install the tooling and wire up the hooks
	python3 -m venv --prompt awg-keeper $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	$(VENV)/bin/pre-commit install

lint:  ## Run the pre-commit hooks over every file
	$(VENV)/bin/pre-commit run --all-files

clean:  ## Remove the virtualenv and the hook environments
	rm -rf $(VENV) .pre-commit
