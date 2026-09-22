# Developer entry points for awg-keeper. Run `make help` for the target list.

VENV ?= .venv
PIP := $(VENV)/bin/pip

# Hook environments live in the repository, not in ~/.cache/pre-commit.
export PRE_COMMIT_HOME := $(CURDIR)/.pre-commit

.DEFAULT_GOAL := shell

.PHONY: help install lint test secrets kickstart clean shell

help:  ## Show the available targets
	@echo "awg-keeper"
	@echo
	@echo "Targets:"
	@awk 'BEGIN {FS = ":.*## "} /^[a-z-]+:.*## / {printf "  %-10s %s\n", $$1, $$2}' \
		$(MAKEFILE_LIST)

install:  ## Create the virtualenv, install the tooling and wire up the hooks
	python3 -m venv --prompt awg-keeper $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	$(PIP) install -r agent/requirements.txt -r agent/requirements-dev.txt
	$(PIP) install -r web/requirements.txt -r web/requirements-dev.txt
	$(VENV)/bin/pre-commit install

lint:  ## Run the pre-commit hooks over every file
	$(VENV)/bin/pre-commit run --all-files

test:  ## Run both test suites
	$(MAKE) -C agent test
	$(MAKE) -C web test

secrets:  ## Mint the panel's secrets for a new deployment
	$(MAKE) -C web secrets

kickstart:  ## Bring up the whole product locally over a fake awg/xray host
	$(MAKE) -C dev/stack kickstart

clean:  ## Remove the virtualenv and the hook environments
	rm -rf $(VENV) .pre-commit


# defaults
shell:  ## Open an interactive subshell with the virtualenv activated
	@rc="$$(mktemp)"; \
	trap 'rm -f "$$rc"' EXIT; \
	cat ~/.bashrc 2> /dev/null > "$$rc" || true; \
	echo 'export PRE_COMMIT_HOME="$(PRE_COMMIT_HOME)"' >> "$$rc"; \
	echo 'source $(CURDIR)/$(VENV)/bin/activate' >> "$$rc"; \
	bash --rcfile "$$rc" -i || true
