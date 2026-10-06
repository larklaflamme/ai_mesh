# Phase 3 — Mesh Core, Increment 1

| | |
|---|---|
| **Goal** | Build the verification-first workflow on durable mechanics: LangGraph graphs with fenced leases, a supervisor and readiness barrier, a GPU-aware scheduler, the gated lifecycle up to G2b, roles v1, knowledge v1 and the GitHub test organization. The conformance (T-DUR) and security (T-SEC) suites must be green |
| **Duration** | ~7 weeks (weeks 10–16; starts during Phase 2) |
| **Prerequisites** | HC-06 = **pass** (or pivot with the change recorded). Phase 2 WP2.1–WP2.2 done. ADR-020/021/022 decided, or a provisional model/harness recorded in `PROGRESS.md` → Decisions |
| **Human checkpoints** | HC-07 GitHub test org and App · HC-08 E6 card · HC-09 gate approver keys · HC-15 G1/G2/G2b approvals during the S1 run (the human acts as the client) |
| **Not in this phase** | Foundation stage, merge queue, scope leases, Change Requests, Svelte UI, graph DB engine, release. Those are Phases 4–5 |

## 0. Design anchors

Read before starting: [05 §6 (modules), §8 (durability), §17 (revisions)](../05-reference-architecture.md); [07 RV-01, RV-03, RV-04, RV-09, RV-11, RV-12, RV-17](../07-adversarial-architecture-review.md); [03 §3, §7, §8](03-interfaces-and-schemas.md).

**Durability model in one paragraph.** A project is a LangGraph *thread*. Every node boundary is checkpointed in PostgreSQL with `durability="sync"`. Exactly one runner may advance a thread; it proves this with a **fenced lease** (`thread:<id>`) and passes the lease's epoch to every side-effecting write. Side effects outside PostgreSQL (git pushes, PRs, gate package files) go through an **idempotency ledger**, so a re-executed node finds its earlier effect instead of repeating it. Human gates are `interrupt()` nodes that do nothing else; resuming them never regenerates their package.

### 0.1 Schema additions (Alembic migration `0007_phase3`)

Add these to `platform` and update [03 §3.1](03-interfaces-and-schemas.md) in the same PR:

```sql
CREATE TABLE platform.side_effects (            -- idempotency ledger for external effects
  effect_key    text PRIMARY KEY,               -- sha256(thread_id, node_name, flow_version, logical_key)
  thread_id     text NOT NULL,
  kind          text NOT NULL,                  -- git_push|pr_open|pr_merge|gate_package|file_write|notify
  epoch         bigint NOT NULL,                -- lease epoch that performed it
  state         text NOT NULL,                  -- intent|done|failed
  result        jsonb,                          -- e.g. {"sha": ..., "pr": 12}
  created_at    timestamptz NOT NULL,
  completed_at  timestamptz
);

CREATE TABLE platform.threads (
  thread_id     text PRIMARY KEY,               -- = project run thread
  run_id        text NOT NULL,
  flow_name     text NOT NULL,                  -- project|stage|task
  flow_version  int NOT NULL,
  state         text NOT NULL,                  -- active|parked|quarantined|done|failed
  parked_at     text,                           -- node name if parked at an interrupt
  resume_failures int NOT NULL DEFAULT 0,
  updated_at    timestamptz NOT NULL
);

CREATE TABLE platform.requirements (            -- traceability (knowledge v1)
  req_id        text PRIMARY KEY,               -- REQ-<n>
  run_id        text NOT NULL,
  title         text NOT NULL,
  moscow        text NOT NULL,                  -- must|should|could|wont
  priority      text NOT NULL,                  -- critical|high|medium|low
  text          text NOT NULL,
  source_sha    text NOT NULL,                  -- sha256 of the source document section
  taint         text NOT NULL DEFAULT 'trusted' -- trusted|tainted
);

CREATE TABLE platform.trace_links (
  src           text NOT NULL,                  -- REQ-1 | SCN-3 | TASK-7 | file:path | test:nodeid | ADR-4
  dst           text NOT NULL,
  kind          text NOT NULL,                  -- refines|verified_by|implements|decided_by|depends_on
  run_id        text NOT NULL,
  created_by    text NOT NULL,                  -- role or human
  PRIMARY KEY (src, dst, kind)
);

CREATE TABLE platform.oracle_bindings (
  scenario_id   text PRIMARY KEY,               -- SCN-<n>, from a Gherkin scenario
  run_id        text NOT NULL,
  req_ids       text[] NOT NULL,
  feature_path  text NOT NULL,
  test_nodeids  text[] NOT NULL,                -- pytest node ids that implement the scenario
  examples_rows int NOT NULL,                   -- rows in the example table
  bound_rows    int NOT NULL,                   -- rows with a parametrized test case
  status        text NOT NULL,                  -- draft|bound|approved
  oracle_sha    text                            -- set when G2b approves; pinned from then on
);
```

## 1. Work packages

### WP3.1 — Orchestration core (`mesh.orchestration`)

**Tasks:**

1. **Checkpointer.** `langgraph-checkpoint-postgres` `PostgresSaver` on the `langgraph` schema (search_path set on the connection pool), `setup()` run by `make migrate`. All graph invocations use `durability="sync"`. ⚠ Verify the parameter name and the checkpointer API against the pinned LangGraph version; record the version in `PROGRESS.md` → Environment.
2. **Graphs** (`graphs/project.py`, `graphs/stage.py`, `graphs/task.py`), each with a module constant `FLOW_VERSION: int` and a `STATE_SCHEMA` (Pydantic or TypedDict):
   - **project graph:** `intake → clarify → usecases → oracle_draft → G1 → design → adversarial_review → (revise ↺ max 2) → G2 → oracle_bind → G2b → plan → build(stage subgraphs) → final_score → done`;
   - **stage graph:** fan-out of task subgraphs from the plan, with the scheduler deciding admission (WP3.2); integration check at the end of the stage;
   - **task graph:** `lease_task → prepare_workspace → attempt → judge → (accept | retry | escalate)`; attempts run via the existing `run_attempt` (Phase 1).
3. **Node rules** (enforced by a decorator `@mesh_node(effects=...)` and a unit test that inspects every registered node):
   - a node is either *pure* (state in → state out) or *effectful*; effectful nodes declare their effect kinds;
   - effectful nodes call `effects.perform(effect_key, kind, fn)`, which records `intent`, checks for an existing `done` row (returns its `result` without re-running), runs `fn`, records `done` — all with the fenced epoch;
   - gate nodes contain **only** `interrupt()` plus verification of the resume payload (03 §7). Package generation happens in the node **before** the gate.
4. **Fenced leases** (`mesh.orchestration.leases`): `acquire/renew/release` per 03 §3.1. A heartbeat **thread** (not an asyncio task) renews every `ttl/3`; if renewal fails or the lease is lost, it sets a `lost` event, and the runner aborts at the next checkpoint boundary and exits non-zero. Checkpoint writes are wrapped so that a write with a stale epoch raises `LeaseLost` (implement with a `BEFORE INSERT` trigger on the checkpoint tables or a wrapper saver that checks `platform.leases` in the same transaction — pick one, document it in ADR-023).
5. **Supervisor** (`mesh supervisor run`): a single long-running process that
   - scans `platform.threads` for `active` threads without a live lease and resumes them (with a new epoch);
   - caps resume failures: after `MESH_MAX_RESUME_FAILURES` (default 3) consecutive failures of the same checkpoint → state `quarantined`, alert event, no further resumes;
   - never resumes `parked` threads (they wait for a gate decision).
6. **Readiness barrier:** before admitting any LLM-using node, the runner checks the Phase 0 readiness probe (gateway `/ready` → tunnel → Ollama model loaded with the expected digest). Not ready → the node does not start; the thread waits with exponential back-off (max 60 s) and an `infra_wait` event. Infra waits never count as attempts.
7. **`flow_version` compatibility:** every checkpoint stores `flow_version`. On resume, if the stored version ≠ current: look up `MIGRATIONS[(old, new)]`; if a migration exists, apply it to the state; if not and the thread is parked at a gate that still exists, resume on the new graph; otherwise refuse and mark the thread `failed` with a clear message. A CI test (T3-ORC-05) builds every graph at the previous released version from a fixture checkpoint and resumes it.

**Acceptance:** T3-ORC-01..08 and T-DUR-01, -02, -05, -09 pass.

### WP3.2 — Scheduler and capacity (`mesh.capacity`)

**Tasks:**

1. **GPU slots** = `OLLAMA_NUM_PARALLEL` from ADR/E0 (e.g. 4). Each slot is a lease `slot:gpu:<n>`. One slot is **reserved for P0** (gate-blocking and judge-escalation work); P1–P3 can use the others.
2. **Priority classes:** P0 gate path and blocking fixes · P1 critical-path tasks · P2 normal tasks · P3 background (refactors, docs, re-indexing). Within a class: FIFO by `not_before`, then by critical-path length (from the plan).
3. **CPU lane:** test runs and judge runs use a separate semaphore `MESH_CPU_LANE` (default `min(8, cores/2)`), so a long test run never holds a GPU slot. A worker attempt releases its GPU slot while its tools run if the adapter supports it (single_loop does; record it per adapter).
4. **Admission control:**
   - readiness barrier (WP3.1-6);
   - disk guard: at 85% of the data volume, stop admitting P2/P3 and the CPU lane; at 90%, stop everything except P0; event `disk_pressure` (T-DUR-10);
   - GPU-hour budget per run (from the run manifest): at 100%, pause and ask the human.
5. **Queue mechanics:** `SELECT … FOR UPDATE SKIP LOCKED` on `platform.task_queue`; transitions are fenced by the task lease epoch. Infra failures set `not_before = now() + backoff` and increment `infra_failures`, never `attempts` (03 §1).
6. **Metrics:** slot utilisation, queue wait per class, P0 wait (target: p95 < 60 s), written to `telemetry.events` and visible in the run report.

**Acceptance:** T3-SCH-01..07 pass; T-DUR-03, -04, -10 pass.

### WP3.3 — Lifecycle and gates (`mesh.governance`, `mesh.oracle`)

**Tasks:**

1. **Gate packages** per 03 §7 for G1, G2, G2b. Contents:
   - **G1:** requirements list with MoSCoW and priority; use cases; clarification log (questions + answers); Gherkin features with example tables; the list of assumptions; open risks; a one-page summary at the top.
   - **G2:** architecture document (C4 context + container views as Mermaid), module list with responsibilities and allowed dependencies (generated `.importlinter`), data model, API contract (OpenAPI draft), ADRs, the adversarial review report with dispositions (accepted / rejected with reason), and the **protected-path manifest** (03 §6.2).
   - **G2b:** the bound oracle: for every scenario, the test node ids and the binding coverage (`bound_rows / examples_rows`), the oracle mutation score where available, and the `oracle_sha` that will be pinned.
2. **CLI:** `mesh gate list`, `mesh gate show <gate_id>` (opens `package.md`), `mesh gate approve|reject|request-changes <gate_id> --hash <12hex> [--comment]`. `request-changes` routes back to the producing stage with the comment as input (max 3 cycles, then escalate).
3. **Approver keys (HC-09):** the human creates an approver SSH key outside the repo and adds the public key to `infra/approvers/allowed_signers` (committed). `MESH_APPROVER_SSH_KEY` points to the private key; never in `.env` files that containers read.
4. **Oracle binding (`mesh.oracle`):**
   - parse Gherkin with `gherkin-official` (pin it); every scenario gets a stable `SCN-n` id written back as a tag (`@SCN-7`);
   - the test-author role writes pytest tests that carry `@pytest.mark.scenario("SCN-7")` and are parametrized over the example table;
   - `mesh oracle check` computes `bound_rows / examples_rows` per scenario by collecting tests (`pytest --collect-only -q` in the judge image) and matching markers and parameter ids;
   - G2b requires 100% binding for scenarios linked to `critical`/`high` requirements and ≥ 90% overall (threshold confirmed at HC-10); otherwise the package is generated with the gaps highlighted and the gate cannot be approved (`mesh gate approve` refuses with `OracleIncomplete`).
5. **Oracle pinning:** on G2b approval, `oracle_sha` = git tree hash of `tests/acceptance/` + `features/`; from then on the judge checks out the oracle at that sha (Phase 1 overlay mechanism) for every task.

**Acceptance:** T3-GATE-01..08 and T-DUR-06, -07 pass.

### WP3.4 — Roles v1 (`roles/`, `mesh.agents`)

**Tasks:**

1. Role YAML + prompt templates (03 §8) for: `intake`, `clarifier`, `usecase_analyst`, `oracle_author`, `architect`, `reviewer_security`, `reviewer_architecture`, `reviewer_testability`, `planner`, `worker`, `test_author`. The judge is **not** an LLM role in v1 (mechanical only; LLM-based review findings are advisory).
2. **Structured outputs** (`mesh.agents.schemas`): Pydantic models `RequirementSet`, `ClarificationQuestions`, `UseCaseSet`, `GherkinFeatureSet`, `ArchitectureDraft`, `ReviewReport` (findings with severity, location, rationale, suggested fix), `Plan` (tasks with ids, deps, scope globs, acceptance scenario ids, estimate), `Disposition`. Calls use JSON-schema-constrained output through the gateway (Ollama `format` / OpenAI `response_format: json_schema` — ⚠ verify which the pinned Ollama honours on `/v1`); validation + 2 repair retries; still invalid → `TASK` failure.
3. **Clarifier:** emits at most N questions (default 15) per round, max 2 rounds. In the prototype the human answers them in a Markdown file `runs/<run_id>/clarifications/round-<k>.md` and runs `mesh clarify submit <run_id> <file>` (this is an interrupt like a gate, but without a signature).
4. **Oracle author ×2:** two independent generations (different seeds and a prompt variant that asks for edge cases first). A merge step (pure code) unions scenarios, deduplicates by normalised step text, and flags **disagreements** (same scenario title, different expected outcomes) into the G1 package for the human.
5. **Adversarial review:** three reviewer roles run in parallel on the architecture draft; mechanical checks run first and their output is given to the reviewers:
   - generated `.importlinter` contracts are acyclic and every module has an owner;
   - every `critical/high` requirement is traced to at least one module and one scenario;
   - OpenAPI draft validates (`openapi-spec-validator`);
   - no dependency outside the allow-list (HC-11).
   The architect produces dispositions; at most 2 revise cycles; unresolved `high` findings go to the G2 package.
6. **Planner:** produces a DAG; a pure validator checks acyclicity, that every Must requirement is covered by some task, that scope globs don't overlap within a stage unless the tasks are dependent, and that each task names its acceptance scenarios.
7. **Prompt hygiene:** static prefix first (role instructions, tool docs, project conventions), task-specific suffix last, so the prefix cache works (E0 finding). `roles_sha` = hash of `roles/` recorded in every manifest.
8. **Cassettes:** every role gets at least one recorded cassette fixture so the graph runs in CI without a GPU.

**Acceptance:** T3-ROLE-01..07 pass.

### WP3.5 — Knowledge v1 (`mesh.knowledge`)

**Tasks:**

1. **Traceability store** on `platform.requirements` and `platform.trace_links`; API `link(src, dst, kind)`, `trace(id, depth)`, `coverage(run_id)` (requirements → scenarios → tests → files).
2. **Code graph:** for the generated repo, build the import graph with `grimp` and a call graph approximation with `ast` (module-level functions and class methods, resolved by name within the package). Stored as JSONL under `runs/<run_id>/knowledge/codegraph-<sha>.jsonl` and summarized into `trace_links (kind=depends_on)` at module level. Rebuilt on every accepted merge.
3. **Retrieval:** Qdrant collection per run (`run_<id>_docs`, `run_<id>_code`), CPU embeddings via `fastembed` (pin the model and record its name + version in the manifest). Chunking: Markdown by heading; code by function/class with the file path and symbol in the payload. Retrieval API returns chunks **with their taint label**.
4. **Taint labels:** anything from outside the trusted set (web research, dependency READMEs, tool output from executed code) is `tainted`. Rules (enforced in `mesh.agents` before the call and in the planner validator after):
   - tainted context can never, by itself, introduce a new dependency, URL, shell command pattern, or scope change; such proposals are routed to the human (event `taint_block`);
   - taint propagates: an output produced with tainted context in the prompt is tainted unless a mechanical check or a human clears it.
5. **Context budgeting:** `mesh.knowledge.context.assemble(role, task)` fills the role budget in priority order (task spec → bound scenarios → interface contracts → retrieved code → retrieved docs) and **never** truncates mid-item; it reports what was left out.

**Acceptance:** T3-KNW-01..06 and T-SEC-07 pass.

### WP3.6 — GitHub test organization (`mesh.scm.github`)

**Human first (HC-07):** create the test org, the platform-owned repo `mesh-platform-workflows`, and a GitHub App `mesh-delivery` with **only**: `contents: write`, `pull_requests: write`, `checks: read`, `metadata: read`. **No** `workflows`, `administration`, `secrets` or `members` permissions. Install it on the test org. Store the App private key outside the repo (`MESH_GH_APP_KEY_PATH`).

**Tasks:**

1. `mesh.scm.github`: App authentication (JWT → installation token, cached, refreshed before expiry), create repo from template, push branch, open PR, read check runs, merge when the platform's required checks are green. All calls go through `effects.perform` (idempotent).
2. **Pinned workflows:** in `mesh-platform-workflows`, a reusable workflow `judge.yml` that runs the same checks as the local judge. Generated repos call it **by commit SHA**. The repo's own `.github/workflows/` is in the protected-path manifest; the delivery App cannot write it anyway (no `workflows` permission), and the judge rejects diffs that touch it.
3. **Rulesets / branch protection on `main`:** PRs required, required status check = the pinned judge workflow, CODEOWNERS review on protected paths (the human team is the code owner), no force pushes. ⚠ Organization-wide required workflows and some ruleset features need GitHub Enterprise (DN-5). If unavailable, use per-repo branch protection + the platform judge as the authority, and record it.
4. **Local judge remains authoritative.** GitHub checks are a second signal. If they disagree, the task is escalated (event `judge_disagreement`).
5. Default `MESH_SCM=local` for CI and most experiments; `MESH_SCM=github` for the S1 end-to-end run and T3-GH tests (marked `github`, run manually or nightly).

**Acceptance:** T3-GH-01..06 pass against the test org.

### WP3.7 — Conformance and security suites

**Tasks:**

1. Implement **T-DUR-01..10** in `platform/tests/conformance/` and **T-SEC-01..10** in `platform/tests/security/` exactly as specified in [08 §5.3–5.4](../08-prototype-plan.md), using the fault-injection toolkit from [04 §5](04-test-strategy.md) (`MESH_FAULT_AT=<node>:<when>`, `MESH_FAULT_STALL_HEARTBEAT`, Toxiproxy for the tunnel, cgroup OOM, a disk-fill fixture on a size-limited volume).
2. Each test runs on cassettes in CI, and a `@pytest.mark.gpu` variant runs nightly with the real model.
3. Every T-DUR test asserts on **three** things: the final state, the absence of duplicate side effects (`platform.side_effects` and the git/GitHub state), and the event trail.
4. Security tests use red-team fixtures in `platform/tests/security/fixtures/` (malicious diffs, planted prompt injections, a fake package name) — never real malware.

**Acceptance:** `make test-conformance` and `make test-security` are green in CI and in one nightly GPU run.

### WP3.8 — S1 end-to-end and E6 (durability under faults)

**Tasks:**

1. `mesh run start --project benchmark/projects/S1 --scm github --label measured` drives S1 through the whole lifecycle. The human acts as the client at G1, G2 and G2b (HC-15) and records all time with the ledger.
2. At the end, the harness scores the final repo on the S1 hidden suite (Phase 1 scorer); the report includes the traceability coverage and gate cycle counts.
3. **E6 card** (HC-08): run the T-DUR faults at scale during real runs (≥ 10 injected faults across 2 S1 runs: kills at random nodes, tunnel drops 30–180 s, a stalled heartbeat, a workspace OOM). Metrics: lost work (GPU-s re-spent), duplicate side effects (must be 0), recovery time p50/p95.

**Acceptance:** S1 delivered through G1/G2/G2b and scored; E6 report published; zero duplicate side effects.

## 2. Phase 3 test plan

Test IDs go in docstrings. "conf" = conformance, "sec" = security.

| ID | Level | Test | Pass criterion |
|---|---|---|---|
| T3-ORC-01 | unit | Node registry inspection | Every node is pure or declares effects; gate nodes contain only interrupt + verification |
| T3-ORC-02 | integration | Checkpoint round-trip | State after each node equals state loaded from PostgreSQL; `durability="sync"` used on every invocation (asserted via a wrapper) |
| T3-ORC-03 | integration | Idempotent effects | Re-executing an effectful node after `done` returns the recorded result; `fn` called once |
| T3-ORC-04 | integration | Effect after crash between `intent` and `done` | On resume, the effect is reconciled (e.g. branch exists at expected sha → mark done) rather than repeated; reconcile function required per effect kind |
| T3-ORC-05 | contract | `flow_version` resume | Fixture checkpoints from version N−1 resume on N (migration or compatible path) or fail with a clear message — never silently |
| T3-ORC-06 | unit | Lease operations | acquire/renew/release semantics, epoch monotonic, expired takeover increments epoch (Hypothesis-based interleavings) |
| T3-ORC-07 | integration | Fenced checkpoint write | Write with a stale epoch raises `LeaseLost`; no row written |
| T3-ORC-08 | integration | Supervisor | Resumes orphaned active threads; skips parked; quarantines after N resume failures |
| T3-SCH-01 | unit | P0 reservation | With all non-reserved slots busy, P0 is admitted; P1–P3 are not |
| T3-SCH-02 | unit | Priority ordering | Higher class first; within class FIFO then critical-path length |
| T3-SCH-03 | integration | SKIP LOCKED | Two schedulers never lease the same task (1,000 randomized trials) |
| T3-SCH-04 | integration | CPU lane | Test runs bounded by the lane; GPU slots not held during tool runs (single_loop) |
| T3-SCH-05 | unit | Infra failure accounting | Infra failures never increment `attempts`; back-off applied |
| T3-SCH-06 | integration | Budget pause | GPU-hour budget reached → run paused, event emitted, human asked |
| T3-SCH-07 | integration | P0 latency | Synthetic load: P0 queue wait p95 < 60 s |
| T3-GATE-01 | unit | Package determinism | Same inputs → same hash, across machines (fixed mtimes, sorted entries) |
| T3-GATE-02 | integration | Approve happy path | Correct hash + valid signature → graph resumes; audit row appended; anchor written |
| T3-GATE-03 | integration | Wrong hash prefix | `GateMismatch`; graph not resumed |
| T3-GATE-04 | integration | Package modified after generation | Recomputed hash ≠ stored → refused |
| T3-GATE-05 | integration | Bad or unknown signature | Rejected by the post-interrupt node; gate stays pending |
| T3-GATE-06 | integration | Approve inside a container | CLI refuses |
| T3-GATE-07 | integration | request-changes loop | Producing stage re-runs with the comment; capped at 3 cycles then escalates |
| T3-GATE-08 | unit | Oracle binding coverage | Fixtures with missing rows → `OracleIncomplete`; critical/high must be 100% |
| T3-ROLE-01 | unit | Role YAML schema | All roles validate; unknown tools rejected; `roles_sha` stable |
| T3-ROLE-02 | contract | Structured outputs | Each schema accepted from cassette outputs; malformed output repaired ≤ 2 times then `TASK` failure |
| T3-ROLE-03 | unit | Oracle merge | Union, dedup and disagreement detection on fixtures |
| T3-ROLE-04 | unit | Planner validator | Cycles, uncovered Must requirements, overlapping scopes, missing scenarios → rejected |
| T3-ROLE-05 | unit | Mechanical review checks | Each check fires on a seeded fixture defect |
| T3-ROLE-06 | unit | Prompt prefix stability | Rendering two tasks of the same role yields an identical static prefix (byte-equal) |
| T3-ROLE-07 | integration | Clarification interrupt | Submitting answers resumes the graph; malformed file rejected |
| T3-KNW-01 | unit | Trace coverage | Coverage query correct on a fixture graph |
| T3-KNW-02 | integration | Code graph | Import graph of a fixture repo matches expected edges |
| T3-KNW-03 | integration | Retrieval | Top-k returns expected chunks on a fixture corpus; payload carries path, symbol, taint |
| T3-KNW-04 | unit | Taint propagation | Output from tainted context is tainted; cleared only by check or human |
| T3-KNW-05 | unit | Taint block | Tainted proposal of a new dependency → routed to human, not applied |
| T3-KNW-06 | unit | Context assembly | Never exceeds budget; never truncates an item; reports omissions |
| T3-GH-01 | integration (github) | App permissions | Installation token cannot write `.github/workflows/*` (API returns 403/404); recorded |
| T3-GH-02 | integration (github) | Idempotent PR | Crash after PR creation → resume finds the existing PR; no duplicate |
| T3-GH-03 | integration (github) | Pinned workflow | Generated repo references `judge.yml@<sha>`; a branch changing the ref is rejected by the local judge |
| T3-GH-04 | integration (github) | Branch protection | Direct push to `main` refused |
| T3-GH-05 | integration (github) | Judge disagreement | Forced mismatch → escalation event |
| T3-GH-06 | integration (github) | Token refresh | Token near expiry is refreshed before a call; no 401 in a 2-hour soak |
| T-DUR-01..10 | conf | See [08 §5.3](../08-prototype-plan.md) | As specified, plus the three assertions of WP3.7-3 |
| T-SEC-01..10 | sec | See [08 §5.4](../08-prototype-plan.md) | As specified |
| T3-E2E-01 | e2e (gpu) | S1 end-to-end | Reaches `done` through G1/G2/G2b; hidden suite scored; report generated |

## 3. Measurements produced

- S1 end-to-end report: hidden pass rate (overall and critical/high), traceability coverage, gate cycles, clarification rounds, human minutes by ledger category, GPU-hours, tokens per accepted LOC.
- E6 report: lost GPU-s per fault, duplicate side effects (0), recovery time p50/p95 by fault type.
- Scheduler metrics: slot utilisation, queue waits per class.
- Comparison of S1 (mesh) against S1 (Phase 1 spike loop) — exploratory until E4.

## 4. Exit gate (Phase 3 → Phase 4)

- [ ] WP3.1–WP3.8 ticked with evidence; all T3 tests green.
- [ ] `make test-conformance` and `make test-security` green in CI and in one nightly GPU run.
- [ ] S1 delivered through G1/G2/G2b and scored on its hidden suite (T3-E2E-01).
- [ ] E6: zero duplicate side effects; recovery times recorded.
- [ ] ADR-023 (fencing implementation) and ADR-024 (GitHub configuration, incl. any DN-5 workaround) written.
- [ ] Human sign-off recorded in `PROGRESS.md`.
