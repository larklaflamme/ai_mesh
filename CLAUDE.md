# AI Mesh — instructions for Claude Code

You are building the **prototype of AI Mesh**: an on-prem platform in which a mesh of AI agents, running on local open-weights models, takes business requirements and designs, builds, tests and releases Python/FastAPI + SvelteKit systems. It is **verification-first**: humans approve the executable definition of "done", and agents iterate against it.

This file is loaded in every session. Keep it accurate; detail lives in the implementation guide.

## Where things are

| What | Where |
|---|---|
| Design rationale (read-only for you unless asked) | `design/00…08-*.md` — start with `design/08-prototype-plan.md` |
| **Implementation guide (your work instructions)** | `design/09-implementation-guide/README.md` — read it fully before your first task |
| Progress tracker (update it as you work) | `PROGRESS.md` |
| Human checkpoints (when you must stop and ask) | `design/09-implementation-guide/99-human-checkpoints.md` |
| Platform code | `platform/` (Python package `mesh`) |
| LLM gateway | `gateway/` |
| Code that runs inside agent workspaces | `worker_runtime/` |
| Local infrastructure | `infra/` |
| Benchmark specs and experiment cards | `benchmark/` |
| Hidden test suites | **NOT in this repo.** Path from `MESH_HIDDEN_ROOT`. You never read, write or list them (ground rule 3) |

## How to work

1. Activate the environment: `conda activate ai-mesh`.
2. Open `PROGRESS.md`. Take the **first unchecked work package** of the current phase, unless the human says otherwise.
3. Read that work package in its phase document, including its tests and acceptance criteria.
4. Implement in small commits. **Write or update the tests listed for the work package in the same change.**
5. Run `make check` (lint, types, import contracts, unit and integration tests). Run the phase-specific targets named in the work package.
6. Tick the work package in `PROGRESS.md` only when every acceptance criterion is met. Add one line of notes: what was done, test evidence, deviations.
7. If a work package requires a human checkpoint (HC-xx), **stop**: state precisely what you need and why.

## Ground rules (non-negotiable)

1. **Never weaken a check to make something pass.** This covers tests, judge rules, protected-path manifests, budgets, thresholds, lint and type settings. If a check seems wrong, stop and raise it (HC-10).
2. **Fail closed.** Missing data, parse errors, timeouts and unknown states mean "not approved" or "not passed". Never default to success.
3. **Hidden test suites are off-limits.** Do not open, list, grep, summarize or copy anything under `MESH_HIDDEN_ROOT`, and never put hidden content into prompts, cassettes, logs or the repo. You build only the runner that executes them and stores scores.
4. **Agent-written code never runs on the host.** It runs only inside workspace or judge containers on the `mesh-exec` network. No `docker.sock`, no host mounts beyond the task workspace, no secrets in containers.
5. **Synthetic data only.** No client data, credentials or real personal data anywhere in the prototype.
6. **No secrets in the repo, logs, prompts or cassettes.** Use `.env` (gitignored) and `infra/secrets/` (gitignored).
7. **Reproducibility.** Every run writes a manifest (platform SHA, role/prompt SHA, model digest, configs). Models are referenced by digest from `infra/remote/models.lock`, never by mutable tag.
8. **Pin dependencies.** Use lockfiles with hashes. Adding a dependency to the platform or the template needs a one-line justification in the commit message, and is an HC-11 item for anything that runs inside workspaces.
9. **Respect module boundaries** (`platform/.importlinter`). Do not add cross-module imports to get around a contract; propose a contract change instead.
10. **Do not change design decisions silently.** If implementation reveals that a design choice in `design/` is wrong or infeasible, record it in `PROGRESS.md` under "Deviations", and ask before diverging on anything security- or measurement-related.

## Commands

```
conda activate ai-mesh
make help            # list targets
make up / make down  # local infra (PostgreSQL, Qdrant, package proxy, tunnel, gateway)
make migrate         # apply DB migrations (platform + telemetry)
make check           # ruff + mypy + import-linter + unit + integration tests (no GPU needed)
make test-conformance / make test-security   # durability/fault-injection and isolation suites
make e2e             # end-to-end against the real model via the tunnel (needs GPU server)
make bench-e0        # throughput characterization (Phase 0)
make report RUN=<run_id> | EXP=<experiment_id>
```

## Coding standards

- Python 3.12, fully typed. `mypy --strict` on `platform/src`, `gateway/`, `worker_runtime/`; ruff format + lint.
- Pydantic v2 models for every cross-boundary payload. JSON schemas are generated from them, never hand-written.
- SQLAlchemy 2.x + Alembic for all DB schema. No raw DDL outside migrations.
- Structured logging (structlog, JSON). Every log line inside a run carries `run_id`; `task_id` and `role` where they apply.
- Use `asyncio` for I/O-bound services (gateway, scheduler); plain sync code is fine elsewhere.
- Tests use pytest. Markers: `unit`, `integration`, `contract`, `conformance`, `security`, `e2e`, `gpu`. CI never needs the GPU: LLM calls come from cassettes (see `design/09-implementation-guide/04-test-strategy.md`).
- Commits: Conventional Commits with the work package ID in the scope, e.g. `feat(WP0.4): stream metering in gateway`.

## Before you say something is done

- All acceptance criteria of the work package are met, with test evidence (test names, or report paths).
- `make check` is green, plus any phase-specific suites named in the work package.
- `PROGRESS.md` is updated.
- No TODOs left in security- or measurement-critical code paths.
