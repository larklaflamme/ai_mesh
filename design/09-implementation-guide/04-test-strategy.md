# 04 — Test Strategy (platform, gateway, worker runtime)

This document covers how **we** test the platform. How the platform tests **generated systems** is the judge's job (phase documents), and how we test the **benchmark** is §8 below.

## 1. Principles

1. **Tests ship with the work package.** Every WP lists test IDs, and a WP without its tests is not done.
2. **Critical paths are tested on their failure branches first.** Every gate, the judge, the gateway budget, leases and hashing get a test that the unhappy path *fails closed*.
3. **No GPU in CI.** Model behaviour comes from cassettes. Real-model tests are marked `e2e`/`gpu` and run locally.
4. **Determinism.** Fixed seeds, frozen clocks (`time-machine` or injected clocks), no reliance on wall-clock ordering.
5. **Traceability.** Each test's docstring starts with its ID (e.g. `"""T1-JDG-04: ..."""`). `tools/analysis/test_trace.py` maps JUnit results to IDs and reports any ID in the guide without a test.

## 2. Levels and markers

| Marker | Scope | External deps | Runs in CI | Typical runtime |
|---|---|---|---|---|
| `unit` | Pure functions and classes | None | Yes | < 1 min total |
| `integration` | Module + real PostgreSQL/Qdrant/Docker | Testcontainers, Docker | Yes | < 10 min |
| `contract` | Interface conformance (adapters, gateway OpenAI-compat, schemas) | Fake Ollama, cassettes | Yes | < 5 min |
| `conformance` | Durability, fencing, gates, fault injection | Docker, Toxiproxy, fake Ollama | Yes (nightly full; PR subset) | < 20 min |
| `security` | Isolation and oracle-gaming red team | Docker | Yes | < 15 min |
| `e2e` | Full flows with the real model through the tunnel | Live tunnel + GPU | **No** (local, nightly) | Minutes to hours |
| `gpu` | Benchmarks touching the GPU (E0 smoke) | Live tunnel + GPU | No | Varies |

Tests needing Docker are skipped (with a clear reason) only when `MESH_ALLOW_SKIP_DOCKER=1`. In CI that is never set, so a missing Docker is a failure.

## 3. Directory layout

```
platform/tests/
  unit/<module>/test_*.py
  integration/<module>/test_*.py
  contract/test_worker_adapters.py, test_gateway_openai_compat.py, test_schemas.py
  conformance/test_durability.py, test_leases.py, test_gates.py, test_infra_classification.py
  security/test_workspace_isolation.py, test_judge_redteam.py, test_injection.py, test_gate_access.py
  e2e/test_spike_s1.py, test_mesh_s1.py, ...
  fixtures/
    fake_ollama/            # FastAPI app emulating /api/version, /api/tags, /api/chat, /v1/chat/completions (stream + non-stream)
    repos/                  # tiny git repos used by judge tests (good, bad, red-team variants)
    toxiproxy/              # config for latency / drop injection between gateway and upstream
  cassettes/<suite>/<key>.json
gateway/tests/ (unit, integration, contract)
worker_runtime/tests/ (unit; adapters against the fake gateway)
```

## 4. Shared fixtures (`platform/tests/conftest.py` and `fixtures/`)

| Fixture | Scope | Provides |
|---|---|---|
| `pg` | session | PostgreSQL 16 Testcontainer, migrated to head, app role with INSERT/SELECT-only grants on `telemetry` and `audit` |
| `qdrant` | session | Qdrant Testcontainer |
| `fake_ollama` | function | Running fake Ollama with knobs: `latency_ms`, `fail_next(n, kind)`, `stream_chunks`, `usage_on_stream: bool`, `digest` |
| `gateway_app` | function | Gateway ASGI app wired to `fake_ollama` and `pg`; `httpx.AsyncClient` against it |
| `toxiproxy` | session | Toxiproxy container to inject latency or cut connections between the gateway and upstream (simulates tunnel drops) |
| `docker_client` | session | Docker SDK client; creates `mesh-exec-test` (internal) and `mesh-llm-test` networks, cleaned up afterwards |
| `workspace_image` | session | Built test workspace image (minimal Python + `mesh_worker`) |
| `judge_image` | session | Built judge image |
| `git_repo_factory` | function | Creates temporary git repos from `fixtures/repos/<name>` at a given commit |
| `frozen_clock` | function | Injectable clock |
| `run_ctx` | function | Fresh `run_id`, manifest, telemetry writer pointed at `pg` and a temp `runs/` directory |

## 5. Cassettes (GPU-free determinism)

- **Recording.**
  - Run `MESH_GATEWAY_MODE=record pytest -m e2e -k <test> --cassette-suite=<name>` with the live tunnel.
  - The gateway writes the cassettes.
  - A human reviews the diff before committing, checking for secrets and for hidden-suite content: cassettes must never contain hidden tests (R3).
- **Replay.** CI runs the same scenario with `MESH_GATEWAY_MODE=replay`. A cassette miss returns 599 and fails the test.
- **Re-recording** is required when prompts, role versions or tool schemas change; the cassette key includes them. Note it in the commit (`test(cassettes): re-record …`).
- **Scope.** Cassettes test *platform mechanics* (flows, retries, judge integration, telemetry), never model *quality*. Quality is measured only by experiments with live models.

## 6. Fault injection toolkit (`mesh.testing.faults`, test-only package)

| Fault | Mechanism |
|---|---|
| Process crash | Run the platform worker as a subprocess; `SIGKILL` at a named checkpoint (env `MESH_FAULT_AT=<node_name>` makes the process kill itself at that node) |
| Stalled heartbeat | `MESH_FAULT_STALL_HEARTBEAT=1` blocks the heartbeat thread |
| Tunnel drop / latency | Toxiproxy toxics `timeout` / `latency` / `reset_peer` on the upstream link |
| Upstream errors | `fake_ollama.fail_next(n, "500" \| "disconnect" \| "slow")` |
| OOM | Workspace container with `mem_limit=64m` running a memory hog → exit 137 |
| Disk pressure | Small tmpfs-backed runs directory filled to a threshold |
| Clock skew | Injected clock jumps |

## 7. Coverage and test strength

- **Branch coverage gates** (ratchet: may only go up):

  | Code | Minimum branch coverage |
  |---|---|
  | `mesh.judge`, `mesh.governance`, `mesh.llm.keys` | 95% |
  | Gateway budget and auth modules | 95% |
  | `mesh.orchestration.leases` | 95% |
  | Everything else | 80% |

- **Mutation testing** of the platform's own critical modules runs weekly, plus before each phase exit: mutmut on judge rules, gateway budget enforcement, lease fencing, gate hash verification. Surviving mutants in these modules must be killed by new tests or justified in `PROGRESS.md`.
- **Property-based tests** (Hypothesis) for:
  - token-budget arithmetic;
  - the protected-path glob and TOML-section matcher;
  - gate package hashing determinism (permutations of file order and mtimes give the same hash);
  - audit chain verification (any single-row mutation is detected).

## 8. Benchmark validity tests (run before each experiment)

These tests are measurement-integrity checks, not platform tests: T-EVL-01..05 from [08 §5.5](../08-prototype-plan.md).

- They are implemented in `mesh.evaluation.validity`.
- Each runs as `mesh bench validate <item>`.
- Their results are attached to the experiment report.
- A failing validity check blocks a `measured` run.

## 9. Flaky tests

- No automatic retries in `unit`, `integration`, `conformance` or `security`.
- A flaky test is fixed or deleted. Quarantining one (marker `quarantine`, excluded from CI) requires a human OK (HC-10) and an issue reference.
- `e2e` tests with live models may use `pytest-rerunfailures` **only** for infra-classified failures, never for assertion failures.

## 10. CI and local commands

| When | What runs |
|---|---|
| Every push / PR (GitHub-hosted) | `make lint typecheck test-unit test-int`, contract tests, PR subset of conformance and security |
| Nightly (local workstation, cron or systemd timer) | Full conformance + security; `make e2e` (live tunnel); cassette drift check (replay vs live diff report); `make report` of nightly e2e metrics |
| Phase exit | Everything above + mutation testing of critical modules + the phase exit tests listed in the phase document |

**Test reports:**

- JUnit XML;
- coverage XML;
- the trace report (test IDs ↔ guide);
- archived under `runs/_ci/<date>/`.
