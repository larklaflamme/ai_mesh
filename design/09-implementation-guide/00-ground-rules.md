# 00 — Ground Rules, Standards and Definition of Done

The short version is in the root `CLAUDE.md`. This document is the full version.

## 1. Non-negotiable rules

| # | Rule | Why | How it is enforced |
|---|---|---|---|
| R1 | Never weaken a check to make something pass | The platform's value is honest verification | Code review; protected-path manifest; HC-10 |
| R2 | Fail closed | A gate that passes on error is worse than no gate | Unit tests for every error path of gates, judge, gateway budgets |
| R3 | Hidden suites are sealed from Claude Code and from agents | Otherwise we measure our own tuning, not capability | `MESH_HIDDEN_ROOT` is outside the repo; T-EVL-04; you never read it |
| R4 | Agent-written code runs only in workspace/judge containers on `mesh-exec` | Agent code is untrusted | Sandbox manager config; T-SEC-01/02 |
| R5 | Synthetic data only | No client data in a prototype | Spec authoring rules; PII scan in Phase 3 |
| R6 | No secrets in repo, logs, prompts, cassettes | Leaks are permanent | gitleaks pre-commit + CI; redaction in telemetry writer |
| R7 | Every measured run has a manifest; models by digest | Results must be reproducible and attributable | Run cannot start without a manifest; `models.lock` |
| R8 | Lockfiles with hashes; new workspace-side packages need HC-11 | Supply chain (07 RV-14) | `make lock`; package proxy allow-list |
| R9 | Module boundaries via import-linter | Keeps the modular monolith modular | `make check` |
| R10 | No silent design changes | Design and code must stay explainable | "Deviations" section in `PROGRESS.md` |

## 2. Definition of done (per work package)

A WP is done when **all** of the following hold:

1. Every acceptance criterion in its phase document is met.
2. Every test listed for the WP exists, carries its test ID in the docstring, and passes.
3. `make check` is green; the phase-specific suites named in the WP are green.
4. New public functions and classes have docstrings. Module READMEs are updated where behaviour changed.
5. Telemetry exists for any new runtime behaviour that affects measurements (§7 of the prototype plan).
6. `PROGRESS.md` is ticked, with evidence and notes. Any deviation is recorded.

## 3. Coding standards

### 3.1 Python

- Python 3.12. `from __future__ import annotations` is not needed.
- Type everything. `mypy --strict` must pass. `Any` only at true boundaries, with a comment.
- Pydantic v2 for all data crossing a module, process or container boundary; `model_config = ConfigDict(extra="forbid", frozen=True)` by default.
- Errors: domain exceptions in `mesh.core.errors`. Never `except Exception: pass`. Catch-all blocks must re-raise or convert to a classified failure (`InfraFailure`, `TaskFailure`, `PolicyViolation`).
- Time: always timezone-aware UTC (`datetime.now(UTC)`).
- IDs: ULIDs (sortable) for runs, tasks, attempts, gates and events (`mesh.core.ids`).
- Configuration: `pydantic-settings`, env prefix `MESH_`, with `.env` support. No config read at import time.
- Subprocesses: always with a timeout, an explicit `cwd` and `env`; never `shell=True` with interpolated input.
- Async: gateway, scheduler and supervisor are async (`anyio`/`asyncio`). The CLI and judge orchestration may be sync.

### 3.2 Database

- One PostgreSQL instance, separate schemas: `platform`, `telemetry`, `audit`, `langgraph` (checkpointer).
- Alembic migrations per schema owner (`platform/migrations/`). Migrations are forward-only. Expand/contract for changes.
- Telemetry and audit tables are **append-only**: no UPDATE or DELETE grants for the application role on them.

### 3.3 Logging and telemetry

- structlog JSON to stdout + file. Bind `run_id`, `task_id`, `attempt`, `role`, `component`.
- Telemetry rows go through `mesh.telemetry.writer`, which redacts secrets (gitleaks patterns + known secret values from settings) **before** writing.
- No prompt or response bodies in logs. Bodies go to content-addressed artifact files only (`runs/<run_id>/blobs/<sha256>.zst`).

### 3.4 Security standards (prototype level)

- **Containers.** Non-root user, `--cap-drop=ALL`, `--security-opt=no-new-privileges`, `--pids-limit`, CPU and memory limits, read-only root filesystem with writable `/workspace` and `/tmp` (tmpfs). Network `mesh-exec` only.
- **Ports.** The platform host process binds services to `127.0.0.1` only.
- **Untrusted output.** Anything produced by agents (or fetched from the web) is data. It never selects tools, permissions or file scopes without a schema-validated, policy-checked step.

## 4. Git workflow (for the platform repo)

- `main` is protected by convention. Work happens on branches `wp/<WP-id>-<slug>`, merged when the WP is done.
- Conventional Commits with the WP ID: `feat(WP1.5): judge test-count manifest`.
- Pre-commit hooks: ruff, ruff-format, mypy (changed files), gitleaks, end-of-file, trailing-whitespace, check-yaml, import-linter.
- Never commit: `.env`, `infra/secrets/`, `runs/`, `data/`, cassettes containing secrets (the cassette recorder redacts; it still gets reviewed).

## 5. When to stop and ask

Stop, explain and ask when:

- a WP references a human checkpoint (HC-xx);
- a check, threshold, budget or protected-path rule seems wrong (HC-10);
- a dependency is needed inside workspaces or the template (HC-11);
- the design seems infeasible as written;
- a result looks too good: e.g. a pass rate jump > 20 pp after a change, or zero escalations on M-tier. Check for leakage first (hidden suite reachable? cassette replay in an e2e run?), then report;
- any action would touch the remote GPU server beyond reading through the tunnel. The human owns the remote server.
