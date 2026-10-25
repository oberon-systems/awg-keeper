# Developer entry points for the agent. Normally reached from the repo root,
# which delegates here; standalone use works too.

REPO_ROOT := $(abspath $(CURDIR)/..)
VENV := $(REPO_ROOT)/.venv
PYTHON ?= python3
DOCKER ?= docker
DIST ?= dist
ARCH ?= amd64
NFPM_IMAGE ?= ghcr.io/goreleaser/nfpm:v2.43.0

# The sub-project tag is what a release is: awg-keeper-agent-v1.2.3 packages
# 1.2.3. An untagged tree builds 0.0.0, which no repository should ever carry.
VERSION ?= $(shell git -C $(REPO_ROOT) describe --tags --abbrev=0 \
	--match 'awg-keeper-agent-v*' 2>/dev/null | sed 's/^awg-keeper-agent-v//')
VERSION := $(if $(VERSION),$(VERSION),0.0.0)

# The image name goes last: everything after it is nfpm's own argv, so -e
# BINARY has to be passed before it.
NFPM_RUN = $(DOCKER) run --rm -u $(shell id -u):$(shell id -g) \
	-v $(CURDIR):/work -w /work -e VERSION=$(VERSION) -e ARCH=$(ARCH)

.DEFAULT_GOAL := help

.PHONY: help lint test run binaries rpm deb package clean

help:  ## Show the available targets
	@echo "awg-keeper agent"
	@echo
	@echo "Targets:"
	@awk 'BEGIN {FS = ":.*## "} /^[a-z-]+:.*## / {printf "  %-8s %s\n", $$1, $$2}' \
		$(MAKEFILE_LIST)

# Uses the repo virtualenv when it exists so the ruff version matches the one
# pinned in .pre-commit-config.yaml.
lint:  ## Run ruff over the agent sources
	@if [ -x $(VENV)/bin/ruff ]; then \
		$(VENV)/bin/ruff check .; \
	else \
		$(PYTHON) -m ruff check .; \
	fi

test:  ## Run the unit tests against the fake awg and xray binaries
	@if [ -x $(VENV)/bin/pytest ]; then \
		$(VENV)/bin/pytest -q; \
	else \
		$(PYTHON) -m pytest -q; \
	fi

run:  ## Run the agent in the foreground, reading AWG_KEEPER_* from the environment
	@if [ -x $(VENV)/bin/python ]; then \
		PYTHONPATH=src $(VENV)/bin/python -m awg_agent; \
	else \
		PYTHONPATH=src $(PYTHON) -m awg_agent; \
	fi

# One zipapp per distribution: pydantic-core is a compiled wheel, so the ABI of
# the build image is the ABI of the target.
$(DIST)/el10/awg-keeper-agent.pyz:  ## Build the EL10 zipapp
	DOCKER_BUILDKIT=1 $(DOCKER) build --target export --output type=local,dest=$(DIST)/el10 \
		-f packaging/Dockerfile.el10 .

$(DIST)/deb13/awg-keeper-agent.pyz:  ## Build the Debian 13 zipapp
	DOCKER_BUILDKIT=1 $(DOCKER) build --target export --output type=local,dest=$(DIST)/deb13 \
		-f packaging/Dockerfile.deb13 .

binaries: $(DIST)/el10/awg-keeper-agent.pyz $(DIST)/deb13/awg-keeper-agent.pyz  ## Build both zipapps

rpm: $(DIST)/el10/awg-keeper-agent.pyz  ## Build the rpm for EL10
	$(NFPM_RUN) -e BINARY=$(DIST)/el10/awg-keeper-agent.pyz $(NFPM_IMAGE) \
		package --config packaging/nfpm.yaml --packager rpm --target $(DIST)

deb: $(DIST)/deb13/awg-keeper-agent.pyz  ## Build the deb for Debian 13
	$(NFPM_RUN) -e BINARY=$(DIST)/deb13/awg-keeper-agent.pyz $(NFPM_IMAGE) \
		package --config packaging/nfpm.yaml --packager deb --target $(DIST)

package: rpm deb  ## Build both packages

clean:  ## Remove the build output
	rm -rf $(DIST)
