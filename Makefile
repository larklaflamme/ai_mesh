# AI Mesh prototype — root Makefile. `make help` lists targets.
SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

PACKAGES   := platform gateway worker_runtime
SRC_DIRS   := platform/src gateway/src worker_runtime/src
COMPOSE    := docker compose -f infra/local/compose.yaml --env-file .env
PYTEST     := python -m pytest
PYTEST_ARGS ?=

# Guard: targets that use Python tooling must run inside the ai-mesh conda env.
define require_env
	@if [ "$${CONDA_DEFAULT_ENV:-}" != "ai-mesh" ]; then \
	  echo "error: activate the conda env first: conda activate ai-mesh (active: '$${CONDA_DEFAULT_ENV:-none}')" >&2; \
	  exit 1; \
	fi
endef

# Run pytest with a marker expression in each package. Exit code 5 ("no tests collected")
# is reported explicitly and tolerated only because a package may have no tests at that
# level yet; every other non-zero exit fails the target.
define pytest_each
	@for pkg in $(PACKAGES); do \
	  echo "== $$pkg: pytest -m '$(1)'"; \
	  rc=0; (cd $$pkg && $(PYTEST) -m '$(1)' $(2) $(PYTEST_ARGS)) || rc=$$?; \
	  if [ $$rc -eq 5 ]; then echo "   (no '$(1)' tests in $$pkg yet)"; \
	  elif [ $$rc -ne 0 ]; then exit $$rc; fi; \
	done
endef

.PHONY: help
help: ## List targets
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# --- environment -----------------------------------------------------------------------
.PHONY: env lock install hooks
env: ## Create or update the ai-mesh conda env
	conda env create -f environment.yml || conda env update -f environment.yml --prune

lock: ## Regenerate hashed lock files (dev + container locks)
	$(require_env)
	uv pip compile platform/pyproject.toml gateway/pyproject.toml worker_runtime/pyproject.toml \
	  --extra dev --generate-hashes --python-version 3.12 -o requirements/dev.lock
	uv pip compile gateway/pyproject.toml --generate-hashes --python-version 3.12 \
	  -o gateway/requirements.lock
	uv pip compile worker_runtime/pyproject.toml --generate-hashes --python-version 3.12 \
	  -o worker_runtime/requirements.lock

install: ## Install the dev lock + editable packages into the active env
	$(require_env)
	uv pip sync --require-hashes requirements/dev.lock
	uv pip install --no-deps -e platform -e gateway -e worker_runtime

hooks: ## Install pre-commit hooks
	$(require_env)
	pre-commit install

# --- quality ---------------------------------------------------------------------------
.PHONY: fmt lint typecheck secrets
fmt: ## Format all packages (ruff format)
	$(require_env)
	@for pkg in $(PACKAGES); do (cd $$pkg && ruff format . && ruff check --fix --select I .); done

lint: ## ruff check + format check + import-linter
	$(require_env)
	@for pkg in $(PACKAGES); do echo "== $$pkg: ruff"; (cd $$pkg && ruff check . && ruff format --check .); done
	cd platform && lint-imports

typecheck: ## mypy --strict on the three packages
	$(require_env)
	@for pkg in $(PACKAGES); do echo "== $$pkg: mypy"; (cd $$pkg && mypy --strict src tests); done

secrets: ## Scan the repo for secrets (gitleaks via pre-commit)
	$(require_env)
	pre-commit run gitleaks --all-files

# --- tests -----------------------------------------------------------------------------
.PHONY: test-unit test-int check test-conformance test-security e2e
test-unit: ## Unit tests in every package
	$(require_env)
	$(call pytest_each,unit,)

test-int: ## Integration + contract tests (Testcontainers; no GPU)
	$(require_env)
	$(call pytest_each,integration or contract,)

check: lint typecheck test-unit test-int ## lint + typecheck + unit + integration

test-conformance: ## Durability / fencing / fault-injection suite
	$(require_env)
	$(call pytest_each,conformance,)

test-security: ## Isolation and red-team suite
	$(require_env)
	$(call pytest_each,security,)

e2e: ## End-to-end against the real model (needs `make up` and a live tunnel)
	$(require_env)
	$(call pytest_each,e2e,)

# --- local infrastructure (WP0.1) ------------------------------------------------------
.PHONY: up down logs migrate
up: ## Start local infra (PostgreSQL, Qdrant, tunnel, gateway, proxies)
	@test -f infra/local/compose.yaml || { echo "error: infra/local/compose.yaml not written yet (WP0.1)" >&2; exit 1; }
	@test -f .env || { echo "error: .env missing; copy .env.example and fill in values" >&2; exit 1; }
	@if grep -qE '=change-me$$' .env; then echo "error: .env still has placeholder values (change-me)" >&2; exit 1; fi
	$(COMPOSE) up -d

down: ## Stop local infra
	$(COMPOSE) down

logs: ## Follow local infra logs
	$(COMPOSE) logs -f

migrate: ## Apply DB migrations (platform + telemetry + audit)
	$(require_env)
	@test -f platform/alembic.ini || { echo "error: migrations not written yet (WP0.3)" >&2; exit 1; }
	alembic -c platform/alembic.ini upgrade head

# --- benchmarks, reports, images -------------------------------------------------------
.PHONY: bench-e0 report images
bench-e0: ## Run llm-bench with the E0 card (Phase 0, needs HC-03 and HC-08)
	$(require_env)
	@test -f benchmark/experiments/E0-serving-capacity.yaml || { echo "error: E0 card missing or not approved (WP0.9, HC-08)" >&2; exit 1; }
	python -m llm_bench --card benchmark/experiments/E0-serving-capacity.yaml

report: ## Build a report: make report RUN=<run_id> | EXP=<experiment_id>
	$(require_env)
	@if [ -n "$(RUN)" ]; then python -m mesh.cli.main report --run "$(RUN)"; \
	elif [ -n "$(EXP)" ]; then python -m mesh.cli.main report --experiment "$(EXP)"; \
	else echo "usage: make report RUN=<run_id> | EXP=<experiment_id>" >&2; exit 1; fi

images: ## Build workspace, judge and gateway images
	@test -f gateway/Dockerfile || { echo "error: gateway/Dockerfile not written yet (WP0.4)" >&2; exit 1; }
	docker build -t mesh-gateway:dev gateway
	@for img in workspace judge; do \
	  if [ -f infra/images/$$img/Dockerfile ]; then docker build -t mesh-$$img:dev infra/images/$$img; \
	  else echo "skip $$img image: infra/images/$$img/Dockerfile not written yet (WP1.1)"; fi; \
	done
