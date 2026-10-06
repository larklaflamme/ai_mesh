# 01 — Bootstrap: Repository, Conda Environment, Tooling

**Goal:** an empty-but-working monorepo in `ai_mesh/`. `make check` passes, CI runs, and every directory from [08 §3](../08-prototype-plan.md) exists with a README stating its purpose.

**Work package:** WP-B (precedes Phase 0). Tick it in `PROGRESS.md` when §9 passes.

## 1. Preconditions (check, don't install silently)

| Tool | Check | If missing |
|---|---|---|
| git ≥ 2.40 | `git --version` | Ask the human |
| Docker Engine + Compose v2 | `docker version && docker compose version` | Ask the human (needs admin) |
| Conda (Miniforge recommended) | `conda --version` | Ask the human; recommend Miniforge (conda-forge default channel) |
| GNU make | `make --version` | `conda install -c conda-forge make` inside the env is acceptable |
| OpenSSH client | `ssh -V` | Ask the human |
| Disk | ≥ 100 GB free on the Docker data root | Ask the human |

**Record the workstation facts** (OS, CPU architecture, cores, RAM) in `PROGRESS.md` → "Environment". On **arm64** (Apple Silicon), set `MESH_TARGET_PLATFORMS=linux/amd64,linux/arm64` for later image builds (Phase 5).

## 2. Repository initialisation

`ai_mesh/` already contains `design/`, `CLAUDE.md` and `PROGRESS.md`. **Do not modify `design/00–08`.**

```bash
cd ai_mesh
git init -b main            # if not already a repo
```

Create `.gitignore`:

```gitignore
# python
__pycache__/
*.py[cod]
.mypy_cache/
.ruff_cache/
.pytest_cache/
.coverage*
htmlcov/
*.egg-info/
dist/
build/
# env & secrets
.env
.env.*
!.env.example
infra/secrets/
*.pem
*_ed25519*
# runtime data
runs/
data/
*.parquet
*.duckdb
# node
node_modules/
# os/editor
.DS_Store
.idea/
.vscode/
```

## 3. Directory skeleton

Create these directories. Each gets a `README.md` with 2–5 lines: purpose, owner module, and which phase fills it.

```
adr/
platform/src/mesh/{core,telemetry,llm,capacity,orchestration,agents,workers,workspace,judge,oracle,knowledge,scm,governance,evaluation,cli}/
platform/src/mesh/workers/{single_loop,deepagents,openhands,opencode}/
platform/tests/{unit,integration,contract,conformance,security,e2e,cassettes,fixtures}/
platform/migrations/
gateway/src/mesh_gateway/
gateway/tests/
worker_runtime/src/mesh_worker/
worker_runtime/tests/
roles/
templates/python-fastapi-svelte/
benchmark/{projects,microbench,experiments}/
tools/{llm-bench,gpu-sampler,analysis}/
infra/{local,remote,tunnel,images,secrets}/
requirements/
.github/workflows/
```

**Package roles:**

- `platform/` is the control-plane application. It runs on the host from the conda env.
- `gateway/` is a separate deployable. It runs as a container and is installed editable in the conda env for tests.
- `worker_runtime/` is installed **only inside workspace images**. It is installed editable in the conda env only so that its unit tests run.

## 4. Conda environment

Create `environment.yml` at the repo root:

```yaml
name: ai-mesh
channels:
  - conda-forge
dependencies:
  - python=3.12
  - pip
  - nodejs=22          # needed for front-end tooling, jscpd, Playwright helpers
  - make
  - git
  - openssh
  - pip:
      - uv             # fast, hash-locking installer; works inside the active conda env
```

Commands:

```bash
conda env create -f environment.yml        # first time
conda activate ai-mesh
python --version                            # expect 3.12.x
uv --version
```

**Policy:**

- **Conda provides** the interpreter and system-level tools.
- **Python packages** are installed with `uv pip` into the **active conda env**. uv detects the active conda environment via `CONDA_PREFIX`. Never `pip install` ad hoc.
- To update the environment: `conda env update -f environment.yml --prune`.
- **Fallback:** if `uv pip` misbehaves with conda on this machine, use `pip install --require-hashes -r requirements/dev.lock` (same lock), and record the fallback under Deviations.

## 5. Python packages and locks

### 5.1 `platform/pyproject.toml`

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "mesh"
version = "0.1.0"
requires-python = ">=3.12,<3.13"
dependencies = [
  "pydantic>=2", "pydantic-settings", "structlog", "typer", "rich", "pyyaml", "jinja2",
  "httpx", "anyio", "tenacity",
  "sqlalchemy>=2", "alembic", "psycopg[binary]",
  "langgraph", "langgraph-checkpoint-postgres", "langchain-core", "langchain-openai",
  "qdrant-client", "fastembed",
  "docker",
  "tokenizers",
  "duckdb", "pyarrow",
  "grimp",
  "python-ulid",
  "opentelemetry-sdk",
  "zstandard",
]

[project.optional-dependencies]
dev = [
  "pytest", "pytest-asyncio", "pytest-xdist", "pytest-cov", "pytest-timeout",
  "hypothesis", "respx", "testcontainers[postgres]",
  "mypy", "ruff", "import-linter", "pre-commit",
  "types-PyYAML",
]

[project.scripts]
mesh = "mesh.cli.main:app"

[tool.hatch.build.targets.wheel]
packages = ["src/mesh"]

[tool.ruff]
line-length = 100
target-version = "py312"
[tool.ruff.lint]
select = ["E","F","W","I","B","UP","S","SIM","RUF","PT","ASYNC","DTZ"]
ignore = ["S101"]           # assert allowed in tests via per-file below
[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101","S105","S106"]

[tool.mypy]
python_version = "3.12"
strict = true
plugins = ["pydantic.mypy"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers --timeout=300"
markers = [
  "unit", "integration", "contract", "conformance", "security", "e2e", "gpu",
]
asyncio_mode = "auto"
```

### 5.2 Other packages

- **`gateway/pyproject.toml`:**
  - package `mesh-gateway`; dependencies: `fastapi`, `uvicorn[standard]`, `httpx`, `pydantic>=2`, `pydantic-settings`, `structlog`, `tokenizers`, `psycopg[binary]`, `sqlalchemy>=2`, `zstandard`, `python-ulid`;
  - dev extra mirrors the platform's (pytest, respx, mypy, ruff);
  - same ruff, mypy and pytest settings as the platform.
- **`worker_runtime/pyproject.toml`:**
  - package `mesh-worker`; dependencies: `pydantic>=2`, `httpx`, `langchain-openai`, `langchain-core`;
  - harness extras added per adapter in Phases 1–2: `deepagents`, `openhands-sdk`, ...;
  - keep it small: it is installed in every workspace image.

### 5.3 Lock and install

```bash
# host dev environment (all three packages + dev extras), hashed lock
uv pip compile platform/pyproject.toml gateway/pyproject.toml worker_runtime/pyproject.toml \
   --extra dev --generate-hashes -o requirements/dev.lock
uv pip sync requirements/dev.lock
uv pip install --no-deps -e platform -e gateway -e worker_runtime

# container locks (used by Dockerfiles)
uv pip compile gateway/pyproject.toml --generate-hashes -o gateway/requirements.lock
uv pip compile worker_runtime/pyproject.toml --generate-hashes -o worker_runtime/requirements.lock
```

**Pinning policy:**

- Versions are resolved at bootstrap time to the latest stable releases and frozen in the locks.
- Upgrades are deliberate PRs titled `chore(deps): …`.
- **LiteLLM is not a dependency** of the prototype (see 08 §2.4).

## 6. Import-linter contracts — `platform/.importlinter`

```ini
[importlinter]
root_packages =
    mesh

[importlinter:contract:layers]
name = Platform layering (higher may import lower, never the reverse)
type = layers
layers =
    mesh.cli
    mesh.evaluation
    mesh.orchestration
    mesh.agents | mesh.judge | mesh.oracle | mesh.workspace | mesh.knowledge | mesh.scm | mesh.workers
    mesh.capacity | mesh.governance
    mesh.llm
    mesh.telemetry
    mesh.core

[importlinter:contract:judge-independent]
name = Judge must not depend on workers or agents (independence of verification)
type = forbidden
source_modules =
    mesh.judge
forbidden_modules =
    mesh.workers
    mesh.agents
```

Verify the `|` (independent siblings) syntax against the installed import-linter version. If it is unsupported, express the same intent with `independence` contracts and note it in Deviations.

## 7. Pre-commit — `.pre-commit-config.yaml`

Hooks:

- `ruff` (lint, `--fix`), `ruff-format`;
- `mypy` (local hook using the conda env, on `platform/src gateway/src worker_runtime/src`);
- `gitleaks`;
- `check-yaml`, `end-of-file-fixer`, `trailing-whitespace`, `check-added-large-files` (max 1 MB);
- a local hook running `lint-imports` from `platform/`.

Install with `pre-commit install`.

## 8. Makefile (root)

Create a self-documenting Makefile (`make help` lists targets with `##` comments). Required targets:

| Target | Does |
|---|---|
| `env` | `conda env create -f environment.yml \|\| conda env update -f environment.yml --prune` |
| `lock` | Regenerate the three lock files (§5.3) |
| `install` | `uv pip sync requirements/dev.lock` + editable installs |
| `fmt` | `ruff format` all packages |
| `lint` | `ruff check` + `lint-imports` |
| `typecheck` | `mypy --strict` on the three packages |
| `test-unit` | `pytest -m unit` in each package |
| `test-int` | `pytest -m "integration or contract"` (Testcontainers; no GPU) |
| `check` | `lint typecheck test-unit test-int` |
| `test-conformance` | `pytest -m conformance` |
| `test-security` | `pytest -m security` |
| `e2e` | `pytest -m e2e` (requires `make up` and a live tunnel) |
| `up` / `down` / `logs` | `docker compose -f infra/local/compose.yaml --env-file .env up -d` / `down` / `logs -f` |
| `migrate` | `alembic -c platform/alembic.ini upgrade head` |
| `bench-e0` | Run `tools/llm-bench` with the E0 card (Phase 0) |
| `report` | `python -m mesh.cli.main report …` |
| `images` | Build workspace, judge and gateway images |

Every target that needs the conda env checks `CONDA_DEFAULT_ENV == ai-mesh` and fails with a clear message otherwise.

## 9. Minimal code so that `make check` is meaningful

| File | Content |
|---|---|
| `platform/src/mesh/__init__.py` | `__version__ = "0.1.0"` |
| `platform/src/mesh/core/settings.py` | `MeshSettings(BaseSettings)` with `env_prefix="MESH_"`. Fields: `database_url`, `qdrant_url`, `gateway_url`, `hidden_root: Path \| None`, `runs_root: Path = Path("runs")`, `approver_ssh_key: Path \| None`. Loaded via a function, never at import |
| `platform/src/mesh/core/ids.py` | `new_id(prefix: str) -> str` returning `f"{prefix}_{ULID()}"`. Prefixes: `run`, `task`, `att`, `gate`, `evt`, `exp` |
| `platform/src/mesh/core/errors.py` | `MeshError`, `InfraFailure`, `TaskFailure`, `PolicyViolation`, `BudgetExceeded`, `GateMismatch` |
| `platform/src/mesh/cli/main.py` | Typer app with `version` and `doctor`. `doctor` checks the conda env, Docker reachability, and DB/Qdrant/gateway reachability (each reported independently, non-zero exit if any required check fails) |
| `.env.example` | All `MESH_*` variables with safe placeholder values and comments |
| `README.md` (root) | One paragraph + links to `CLAUDE.md`, `design/README.md`, `design/09-implementation-guide/README.md` |

Bootstrap tests (in `platform/tests/unit/test_bootstrap.py`):

| ID | Test | Pass criterion |
|---|---|---|
| T-BOOT-01 | `mesh.core.ids.new_id` | Correct prefix; ULID format; sortable by creation time |
| T-BOOT-02 | Settings load from env with prefix; no import-time loading | Values read; importing `mesh` without env vars does not fail |
| T-BOOT-03 | Error hierarchy | `InfraFailure` and `TaskFailure` are distinct; both subclass `MeshError` |
| T-BOOT-04 | CLI `mesh version` | Exit 0; prints the version |
| T-BOOT-05 | `lint-imports` passes on the skeleton | Exit 0 |

## 10. CI — `.github/workflows/ci.yml`

Runs on push and PR, on GitHub-hosted runners. These run only **platform code and synthetic fixtures**, never agent-generated code.

1. Set up Miniforge (`conda-incubator/setup-miniconda`, action pinned by SHA) with `environment.yml`.
2. `uv pip sync requirements/dev.lock` + editable installs.
3. `make lint typecheck test-unit test-int`. Testcontainers works on GitHub-hosted Ubuntu runners.
4. Upload JUnit XML and coverage.
5. gitleaks.

**Pin every action by full commit SHA**, not by tag (07 RV-14).

## 11. Bootstrap acceptance checklist

- [ ] `conda activate ai-mesh && python -V` shows 3.12.
- [ ] `make install` succeeds from a clean env using only the lock.
- [ ] `make check` is green locally.
- [ ] `mesh doctor` runs. Infra checks may fail before Phase 0; they must report clearly.
- [ ] Pre-commit is installed; a test commit with a fake secret is blocked by gitleaks.
- [ ] CI is green on the first push (if the repo is pushed to GitHub — ask the human where; HC-07 covers the org).
- [ ] Workstation facts recorded in `PROGRESS.md`.
