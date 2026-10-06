# Phase 1 — Capability Spike

| | |
|---|---|
| **Goal** | Answer the riskiest question first, with the simplest machinery: can a local model on the H100 PCIe, through an off-the-shelf harness or a plain agent loop, deliver S1, M1 and an L-slice against sealed hidden suites? At what cost per accepted line? |
| **Duration** | ~6 weeks (weeks 3–8) |
| **Prerequisites** | Phase 0 exit gate passed |
| **Human checkpoints** | HC-04 hidden suites (S1, M1, L-slice) · HC-05 spec review · HC-08 E1/E2 cards · HC-11 template and workspace packages · **HC-06 capability gate decision** |
| **Not in this phase** | LangGraph orchestration, gates, knowledge graph, GitHub. The spike loop is deliberately plain (compiler-experiment pattern) |

## 1. Work packages

### WP1.1 — Workspace and judge images, package proxy allow-list

**Tasks:**

1. **`infra/images/workspace/Dockerfile`:**
   - based on `python:3.12-slim` (pinned by digest);
   - adds Node 22, git, ripgrep, `uv`;
   - non-root user `agent` (uid 10001), `WORKDIR /workspace`;
   - installs `mesh_worker` from `worker_runtime/requirements.lock` with hashes;
   - package managers point only at the proxies: `PIP_INDEX_URL=http://pypi-proxy:3141/root/pypi/+simple/`, `UV_INDEX_URL` the same, `npm config set registry http://npm-proxy:4873/`;
   - no compilers unless a wheel is missing; record any exception.
2. **`infra/images/judge/Dockerfile`:**
   - same base and toolchain;
   - plus the pinned checker tools (ruff, mypy, import-linter, semgrep, pytest-junit utilities);
   - no `mesh_worker`, no harnesses.
3. **Image build:** `make images` builds both; their digests go into `infra/images/IMAGES.lock` and every run manifest.
4. **Package proxy allow-list:**
   - seeded from the template's lockfile and its transitive closure;
   - requests for anything else are refused by the proxy and logged;
   - additions go through HC-11 (`infra/local/allowlist/pypi.txt`, `npm.txt`, reviewed in PRs).
5. **Lockfile hygiene inside workspaces:** `uv pip sync --require-hashes`; `npm ci --ignore-scripts`.

**Acceptance:**

- Images are built and pinned.
- A workspace can install allow-listed packages and is refused others.
- T1-WS-07 passes.

### WP1.2 — Sandbox manager (`mesh.workspace`)

**API:**

```python
run_attempt(spec: TaskSpec, adapter: WorkerAdapter, repo: Path, base_commit: str,
            budgets: Budgets, services: list[Literal["postgres"]]) -> AttemptOutcome
```

**Tasks:**

1. Create `runs/<run_id>/attempts/<attempt_id>/`:
   - `workspace/` is a clone of `repo` at `base_commit` (a `git clone --local --no-hardlinks`, so the agent cannot touch the source repo's objects);
   - `mesh/` holds `task.json`, `runtime.json` and the rendered role prompt;
   - `out/` is empty.
2. Issue a virtual key ([03 §4.2](03-interfaces-and-schemas.md)).
3. If `services` includes `postgres`, start a sidecar PostgreSQL container on `mesh-exec` with random credentials and pass `DATABASE_URL` to the workspace. The template's test fixtures use `DATABASE_URL`; there is no Testcontainers inside workspaces.
4. Start the workspace container:
   - **mounts:** `workspace/` → `/workspace` (rw), `mesh/` → `/mesh` (ro), `out/` → `/out` (rw);
   - **network:** `mesh-exec`;
   - **hardening:** `read_only=True`, `tmpfs={"/tmp": "size=2g"}`, `cap_drop=["ALL"]`, `security_opt=["no-new-privileges"]`;
   - **limits:** `pids_limit=512`, `mem_limit` and `nano_cpus` from config (default 6 GB, 2 CPUs), `user=10001`;
   - **environment:** `MESH_KEY` and the proxy settings only;
   - **labels:** `mesh.run_id`, `mesh.task_id`, `mesh.attempt_id`, `mesh.lease_epoch`;
   - **forbidden:** `docker.sock`, host networking, other host paths.
5. Wait with `limits.wall_clock_s`. On timeout, kill the container and classify the result (`TIMEOUT`, unless infra evidence).
6. **Collect:**
   - `out/result.json`, validated; missing or invalid means `TASK` failure, unless exit 137 / OOMKilled, which means `INFRA`;
   - the transcript (redacted into blobs);
   - `git -C workspace diff --binary base_commit` and LOC counts.
7. Revoke the key, stop the sidecar, remove the containers.
8. **Reaper:** every 60 s, remove containers whose `mesh.attempt_id` has no active attempt, and emit an event.
9. Write telemetry `attempts` rows.

**Acceptance:** T1-WS tests pass. No container survives an attempt (checked by the reaper test).

### WP1.3 — Worker runtime and adapters (`worker_runtime/`, `mesh.workers`)

**Tasks:**

1. **`mesh_worker.run`:** reads `/mesh/task.json` and `/mesh/runtime.json`, dispatches to the adapter named by `--adapter`, writes `/out/result.json`, and uses the exit codes in [03 §5.3](03-interfaces-and-schemas.md).
2. **Tool set** (shared by the adapters that can use custom tools):

   | Tool | Behaviour |
   |---|---|
   | `read_file`, `write_file`, `edit_file` (search/replace), `list_dir`, `grep` | Confined to `/workspace`, with path-traversal and symlink-escape checks |
   | `run_shell` | 120 s timeout, output truncated to 8 KB (head + tail), no network beyond the proxies |
   | `run_tests` | `pytest -q --junitxml=/tmp/junit.xml <paths>`, returning a structured summary |
   | `report_oracle_defect(test_id, reason, evidence)` | Writes to the result and exits with code 40 |
   | `finish(summary)` | Ends the attempt |

3. **`single_loop` adapter** (the baseline):
   - an OpenAI tool-calling loop over httpx to the gateway;
   - system prompt = rendered role file (prefix-stable: static instructions and tool docs first, task spec last);
   - the loop stops on `finish`, `max_turns` or budget exhaustion;
   - optional context compaction (summarise old turns) only behind a flag, **off** by default (prefix stability);
   - every call is attributed through `MESH_KEY`.
4. **`deepagents` adapter:**
   - LangChain Deep Agents (`create_deep_agent`), with the chat model `ChatOpenAI(base_url=<gateway>/v1, api_key=MESH_KEY, model=<pinned>)`;
   - a filesystem backend rooted at `/workspace`, plus a shell tool executing inside the container;
   - **verify the current Deep Agents API and backend options** when implementing, and record the version in the adapter's `version`;
   - subagents disabled initially (single worker) to keep the comparison clean.
5. **Host-side adapters** (`mesh.workers.single_loop`, `mesh.workers.deepagents`) implement `WorkerAdapter`: image digest, command, config hash.

**Acceptance:** T1-WR and T1-AD tests pass. Both adapters complete the toy project (fixture `toy3`, 3 tasks) in replay mode in CI, and live in a nightly run.

### WP1.4 — Judge v0 (`mesh.judge`)

**Tasks:**

1. **Pre-checks on the host** (pure git, nothing executed):
   - changed files vs the `ProtectedManifest`, including TOML-section rules;
   - changed files vs `allowed_paths` (scope);
   - added lines scanned for ratchet patterns ([03 §6.2](03-interfaces-and-schemas.md));
   - deleted or renamed test files.

   Any hit → `POLICY` with details. **The judge does not run tests on a policy failure.**
2. **Judge container** (judge image, network `mesh-exec` plus a sidecar PostgreSQL if needed):
   - copy the candidate tree into the container's tmpfs;
   - **overlay the oracle checkout** (pinned `oracle_sha`) at the manifest's oracle paths, so worker changes to those paths are discarded even if the pre-check missed them;
   - install project dependencies from the project lock through the proxy, with a cached venv volume keyed by the lock hash;
   - run the checks in order, each with a timeout:
     1. `pytest --collect-only -q` → collected node IDs; compare with the test manifest (`TEST_COUNT`);
     2. pytest on the oracle suites and `must_turn_green` with `--junitxml`;
     3. ruff, mypy, `lint-imports`;
     4. Semgrep with `infra/semgrep/test-mode.yml` (test-mode branches, `dependency_overrides` outside tests, env-conditional returns).
3. **Parse JUnit:** count skipped, xfailed and errors. Any skip, xfail or deselect in oracle suites → `SKIP_DETECTED`.
4. **Build the `JudgeVerdict`**, default `passed=False`. Malformed or missing JUnit, a judge-container crash or a timeout produce `passed=False`. Container death or exit 137 → `INFRA` (no attempt consumed). Anything else → `TASK`.
5. **`FailureReport` builder:** structured and truncated; no raw logs.
6. **Hidden scoring** (`mesh.evaluation.hidden`):
   - the same judge image, with the hidden suite mounted read-only from `MESH_HIDDEN_ROOT/<ref>`, run as a separate container invocation;
   - **only counts are returned and stored** (`total`, `passed`, `by_priority`), never names or content;
   - its output never feeds back into any worker attempt;
   - the hidden root is mounted into **no** other container.

**Acceptance:** all T1-JDG tests pass, including every red-team fixture. Judge branch coverage ≥ 95%.

### WP1.5 — Generated-system template v0 (`templates/python-fastapi-svelte`, API-only variant)

**Tasks:**

1. A minimal FastAPI project per [06 §4](../06-generated-system-baseline-and-release.md), plus the secure defaults from 06 §11.1:
   - auth dependency on all routers;
   - an explicit `public` marker;
   - a test that fails if any route lacks auth;
   - a local test token issuer for tests.
2. `pyproject.toml` with pytest/ruff/mypy sections, `.importlinter`, `mesh/protected-manifest.yaml`, a protected `tests/conftest.py` providing a DB session from `DATABASE_URL`, Alembic, and a hash-locked `requirements.lock`.
3. `make`-like scripts inside the template: `scripts/test.sh`, `scripts/lint.sh`.
4. HC-11 review of the template's dependency list.

**Acceptance:** the template's own tests pass in a workspace with a sidecar PostgreSQL. The judge passes an unmodified template and fails the red-team variants.

### WP1.6 — Benchmark content v0

**Tasks:**

1. **Claude Code drafts** (human reviews at HC-05):
   - `benchmark/projects/S1/spec/` (requirements, Gherkin + examples, `openapi.yaml`, `tasks.yaml` with 30–60 ordered tasks and their `must_turn_green` lists);
   - the visible acceptance tests implementing the Gherkin for the spike: the spike's oracle is given, not generated;
   - `M1` (~40–60k LOC scope, API-only for the spike; UI arrives in Phase 4);
   - the L-slice (L spec outline + frozen contracts for 2–3 modules).
2. **Human (HC-04):** hidden suites for S1, M1 and the L-slice in `MESH_HIDDEN_ROOT`, with priority markers (`@pytest.mark.priority("critical"|"high"|"medium"|"low")`), and hidden defect lists. Claude Code only receives the refs (`<id>@<sha>`).
3. **Reference implementation of S1** (needed for the micro-benchmark and T-EVL-01). Written by a human, or by a **separate, isolated Claude Code session in a separate repository** that never sees the platform prompts; per HC-04 rules, it is verified against the hidden suite by the human.
4. **Micro-benchmark v0:** 50 tasks cut from the S1 reference. The pattern: remove the implementation of one function, endpoint or module; keep its visible tests; the hidden counterpart is supplied by the human. Format per [03 §10](03-interfaces-and-schemas.md).
5. Run `mesh bench validate` (T-EVL-01, -04, -05) on all items.

**Acceptance:** HC-04 and HC-05 are signed off; validity checks pass.

### WP1.7 — Spike loop runner (`mesh.evaluation.spike`)

```
mesh spike run --item projects/S1 --adapter single_loop|deepagents --label measured --experiment E2-… [--max-attempts 3]
```

**Tasks:**

1. Create the run and its manifest. Readiness barrier.
2. Load `tasks.yaml` into `platform.task_queue` (state `queued`, dependencies respected).
3. For each runnable task:
   1. Run `run_attempt` → judge.
   2. **Pass:** commit to the spike repo's `main` with trailers (`Task-Id`, `Attempt-Id`, `Run-Id`, `Model-Digest`, `Adapter`); per-task hidden score (if the hidden suite maps tests to tasks) → `telemetry.hidden_scores`.
   3. **Fail:** build the `FailureReport` and start the next attempt.
   4. **Attempts exhausted:** state `escalated`; write `runs/<run_id>/escalations/<task_id>.md`. Continue with independent tasks; stop dependent ones.
   5. **`INFRA`:** wait for readiness and retry without counting.
   6. **`ORACLE_DEFECT`:** pause the task and notify the human (ledger category `escalation`).
4. **Resume:** restarting with the same `run_id` continues from `platform.task_queue` state.
5. **End of run:** project-level hidden scoring, `project_results` metrics ([08 §7.2](../08-prototype-plan.md)), erosion metrics (radon, duplication via jscpd, module sizes, suppression count), and the run report.

**Acceptance:** T1-SPK tests pass. The toy project completes end-to-end live (nightly). An S1 exploratory run completes before E2 starts.

### WP1.8 — Experiments E1 and E2, capability gate pack

**Tasks:**

1. Write the cards `E1-microbench-baseline.yaml` and `E2-capability-spike.yaml`. Get them approved (HC-08):
   - **E1:** 50 tasks × 2 adapters × k=3.
   - **E2:** S1 → M1 → L-slice with the better adapter from E1 (or both, if close), k=1 for M1/L-slice, k=3 for S1. GPU-hour budget stated.
2. Run them, labelled `measured`.
3. Generate the reports. Compile the **capability gate pack** (`runs/_reports/capability-gate.md`):
   - hidden pass rate by priority (S1, M1, L-slice);
   - escalations per KLOC;
   - output tokens per accepted LOC;
   - GPU-hours and wall-clock;
   - the scale curve S → M → L-slice;
   - erosion trend;
   - human minutes;
   - a comparison against the thresholds in [07 §4.2](../07-adversarial-architecture-review.md);
   - Claude Code's recommendation (pass / pivot / kill) with reasons.

**Acceptance:** the pack is complete and the human decides at HC-06.

## 2. Phase 1 test plan

| ID | Level | Test | Pass criterion |
|---|---|---|---|
| T1-WS-01 | security | Workspace mounts | Only `/workspace` (rw), `/mesh` (ro), `/out` (rw), `/tmp` (tmpfs); no `docker.sock`; root fs read-only |
| T1-WS-02 | security | Network from workspace | Same probe as T0-INF-03; gateway and proxies only |
| T1-WS-03 | security | Privileges | uid 10001; `CapEff` = 0; `no_new_privs` = 1 |
| T1-WS-04 | integration | Limits | Memory hog → exit 137 → `INFRA`; fork bomb stopped by the pids limit; CPU quota observed |
| T1-WS-05 | integration | Sidecar PostgreSQL | `DATABASE_URL` works; sidecar removed afterwards |
| T1-WS-06 | integration | Reaper | Orphan container (simulated platform crash) removed ≤ 2 min; event emitted |
| T1-WS-07 | security | Package proxy | Allow-listed package installs; unknown or typo-squat name refused and logged |
| T1-WS-08 | security | Hidden root | No container except hidden scoring has `MESH_HIDDEN_ROOT` mounted; scan of `runs/`, blobs, cassettes and logs finds no hidden file content (hash comparison against the hidden repo, done by a human-run script) |
| T1-WR-01 | unit | Path confinement | `../`, absolute paths and symlink escapes rejected |
| T1-WR-02 | unit | `run_shell` | Timeout enforced; output truncated head + tail; exit code captured |
| T1-WR-03 | unit | Exit codes | Each failure mode maps to the documented exit code |
| T1-WR-04 | unit | Gateway outage in the worker | Connection errors → exit 20 (`INFRA`), not a task failure |
| T1-AD-01 | contract | Adapter conformance | Both adapters satisfy `WorkerAdapter`; produce valid `result.json` on `toy3` (replay) |
| T1-AD-02 | contract | Attribution | Every LLM call in the run is attributed to the right task, attempt and role |
| T1-AD-03 | contract | Prefix stability | Rendered prompts for consecutive turns share the static prefix byte-for-byte |
| T1-JDG-01 | integration | Good candidate | Unmodified correct fixture passes; verdict fields complete |
| T1-JDG-02 | security | Red team: `conftest.py` edit (skip hook) | `POLICY` / `PROTECTED_PATH` |
| T1-JDG-03 | security | Red team: `[tool.pytest]` `addopts = -k "not slow"` | `POLICY` / `PROTECTED_PATH` (TOML-section rule) |
| T1-JDG-04 | security | Red team: `@pytest.mark.skip` / `xfail` added to an oracle test | `POLICY` / `SUPPRESSION_GROWTH`; and if overlay-restored, `SKIP_DETECTED` never shows a pass |
| T1-JDG-05 | security | Red team: oracle test file deleted or renamed | `POLICY`; the overlay restores it; `TEST_COUNT` mismatch if not |
| T1-JDG-06 | security | Red team: `collect_ignore` in a non-protected location | `TEST_COUNT` failure |
| T1-JDG-07 | security | Red team: `if settings.TESTING: return expected` in app code | Semgrep finding → fail |
| T1-JDG-08 | security | Red team: `# noqa`, `# type: ignore` added | `SUPPRESSION_GROWTH` |
| T1-JDG-09 | security | Red team: change outside `allowed_paths` | `SCOPE` |
| T1-JDG-10 | security | Red team: `.github/workflows` or `contracts/` edit | `PROTECTED_PATH` |
| T1-JDG-11 | conformance | Fail closed | Missing JUnit, malformed JUnit, judge timeout, judge crash → `passed=False` with the right class |
| T1-JDG-12 | unit | `FailureReport` | No raw logs; instruction-like text stripped; size bounded |
| T1-JDG-13 | integration | Determinism | Same candidate twice → identical verdict (except IDs and timestamps) |
| T1-JDG-14 | integration | Hidden scoring | Returns counts only; no hidden test names in any output; result not visible to workers |
| T1-SPK-01 | integration | Spike loop on `toy3` (replay) | All tasks accepted; commits carry trailers; telemetry complete |
| T1-SPK-02 | conformance | Kill the runner mid-task, restart | Continues; no task re-accepted; no duplicate commit |
| T1-SPK-03 | conformance | Toxiproxy cuts upstream for 90 s | Tasks pause; attempts not consumed; resume automatically |
| T1-SPK-04 | integration | Escalation | Task failing N times → escalated; dependents blocked; independents continue |
| T1-SPK-05 | unit | Metrics | `output_tokens_per_accepted_loc`, escalations per KLOC and erosion metrics computed correctly from fixtures |
| T1-SPK-06 | integration | Telemetry completeness | Every attempt has `llm_calls` rows, a `judge_results` row, a blob refs set; every run has a manifest |
| T1-SPK-07 | e2e | `toy3` live, nightly | Completes; numbers trend-tracked |
| T1-EVL-01 | evaluation | T-EVL-01: S1 reference passes its hidden suite | 100% |
| T1-EVL-04 | evaluation | T-EVL-04: hidden isolation audit | Pass |
| T1-EVL-05 | evaluation | T-EVL-05: baseline fairness for E1 | Same budgets, oracle and tasks for both adapters |

## 3. Measurements produced

- E1: hidden pass rate per adapter, output tokens per accepted LOC, GPU-seconds per task, attempts per task, failure taxonomy.
- E2: everything above, at project level; the scale curve; erosion; human minutes (escalations, oracle defects).
- Capability gate pack.

## 4. Exit gate (Phase 1 → Phase 3, with Phase 2 continuing in parallel)

- [ ] WP1.1–WP1.8 ticked with evidence. All T1 tests green.
- [ ] E1 and E2 reports published. The capability gate pack is complete.
- [ ] **HC-06 decision recorded** in `PROGRESS.md`: pass / pivot (with the chosen change) / kill.
- [ ] 02 §10 throughput numbers replaced by measured values (proposed design update).
