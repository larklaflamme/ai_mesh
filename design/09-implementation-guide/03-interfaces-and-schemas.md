# 03 — Interfaces and Schemas (shared contracts)

Every cross-module, cross-process or cross-container payload is defined here. Implement each one as a **Pydantic v2 model** in the module named. Generate JSON Schema from the models into `platform/schemas/` (`make schemas`), and test that the generated schemas match the committed ones. A contract change needs a schema version bump and a migration note.

Models use `ConfigDict(extra="forbid", frozen=True)` unless stated. All timestamps are UTC ISO-8601. All IDs come from `mesh.core.ids`.

## 1. Failure taxonomy — `mesh.core.failures`

```python
class FailureClass(StrEnum):
    NONE = "none"
    INFRA = "infra"            # tunnel/Ollama down, OOM-kill (exit 137), container start timeout, disk full
    BUDGET = "budget"          # context or token budget exceeded (gateway rejected)
    TASK = "task"              # agent's work failed a check
    POLICY = "policy"          # protected-path edit, scope violation, skip/xfail added, suppression growth
    ORACLE_DEFECT = "oracle_defect"  # worker filed a typed oracle-defect report (routed to human)
    TIMEOUT = "timeout"        # attempt exceeded wall-clock limit (counted as TASK unless infra evidence)

class CheckFailure(StrEnum):   # judge-level detail
    ASSERTION = "assertion"; ERROR = "error"; COLLECTION = "collection"; TIMEOUT = "timeout"
    LINT = "lint"; TYPE = "type"; ARCH = "architecture"; SEMGREP = "semgrep"
    PROTECTED_PATH = "protected_path"; SCOPE = "scope"; SKIP_DETECTED = "skip_detected"
    TEST_COUNT = "test_count"; SUPPRESSION_GROWTH = "suppression_growth"; RATCHET = "ratchet"
```

**Rule:** `INFRA` never increments `attempts`. Everything else does, except `ORACLE_DEFECT`, which pauses the task for a human.

## 2. Run manifest — `mesh.core.manifest.RunManifest`

| Field | Type | Notes |
|---|---|---|
| `schema_version` | `str` | `"1"` |
| `run_id` | `str` | `run_…` |
| `experiment_id` | `str \| None` | `None` only for `exploratory` runs |
| `label` | `Literal["measured","exploratory","test"]` | Reports include only `measured` |
| `benchmark_item` | `str` | e.g. `projects/S1@<git sha>` or `microbench@v1` |
| `seed` | `int` | Passed to the model (`options.seed`) and to every sampler |
| `platform_sha`, `roles_sha`, `template_sha` | `str` | Git SHAs; the run is refused if the work tree is dirty and `label=="measured"` |
| `worker` | `{adapter: str, version: str, config_hash: str}` | |
| `model` | `{name: str, digest: str, quant: str, tokenizer_sha256: str}` | Must match `infra/remote/models.lock` |
| `ollama` | `{version: str, env_hash: str}` | Hash of `infra/remote/ollama.override.conf` |
| `gateway_version` | `str` | |
| `embedding` | `{model: str, version: str}` | |
| `budgets` | `{context_by_role: dict[str,int], max_output_tokens_by_role: dict[str,int], task_gpu_tokens: int, attempts_per_task: int}` | |
| `topology` | `{workstation: str, arch: str, tunnel_endpoint_id: str}` | No secrets |
| `started_at`, `ended_at` | `datetime` | |

Written to `runs/<run_id>/manifest.json` and `telemetry.runs`. Immutable once written, except `ended_at` and the final status.

## 3. Database schemas (Alembic migrations in `platform/migrations/`)

Four PostgreSQL schemas:

- `platform` — mutable state;
- `telemetry` — append-only;
- `audit` — append-only, hash-chained;
- `langgraph` — owned by the checkpointer library.

The application role has **INSERT and SELECT only** on `telemetry` and `audit`.

### 3.1 `platform` schema

```sql
CREATE TABLE platform.gateway_keys (
  key_hash      text PRIMARY KEY,            -- sha256 of the virtual key; plaintext never stored
  run_id        text NOT NULL,
  task_id       text,
  attempt_id    text,
  role          text NOT NULL,
  model_name    text NOT NULL,
  context_budget int NOT NULL,
  max_output_tokens int NOT NULL,
  gpu_token_budget bigint,                    -- per task; NULL = no cap (only for E0)
  expires_at    timestamptz NOT NULL,
  revoked_at    timestamptz
);

CREATE TABLE platform.leases (                -- one table for all leases (fencing, RV-11)
  resource      text PRIMARY KEY,             -- e.g. 'thread:<thread_id>', 'task:<task_id>', 'slot:gpu:0'
  holder        text NOT NULL,                -- process/worker id
  epoch         bigint NOT NULL,              -- monotonically increasing fencing token
  expires_at    timestamptz NOT NULL,
  acquired_at   timestamptz NOT NULL,
  heartbeat_at  timestamptz NOT NULL
);

CREATE TABLE platform.task_queue (
  task_id       text PRIMARY KEY,
  run_id        text NOT NULL,
  priority      smallint NOT NULL,            -- 0 = P0 … 3 = P3
  state         text NOT NULL,                -- queued|leased|running|accepted|escalated|quarantined|cancelled
  attempts      int NOT NULL DEFAULT 0,
  infra_failures int NOT NULL DEFAULT 0,
  not_before    timestamptz NOT NULL DEFAULT now(),
  scope_lease   text[],                       -- hotspot scopes held (Phase 4)
  spec          jsonb NOT NULL,               -- TaskSpec
  created_at    timestamptz NOT NULL,
  updated_at    timestamptz NOT NULL
);
CREATE INDEX ON platform.task_queue (state, priority, not_before);

CREATE TABLE platform.gates (
  gate_id       text PRIMARY KEY,
  run_id        text NOT NULL,
  kind          text NOT NULL,                -- G1|G2|G2b|G3|G1-delta|hotfix
  package_hash  text NOT NULL,                -- sha256 of the canonical package archive
  package_path  text NOT NULL,
  status        text NOT NULL,                -- pending|approved|rejected|changes_requested
  decided_by    text,
  decided_at    timestamptz,
  signature     text,                         -- ssh-keygen -Y sign over the decision record
  comment       text
);
```

**Lease operations** are each **one SQL statement inside one transaction**. Never hold a transaction open across work.

| Operation | Semantics |
|---|---|
| `acquire` | Insert, or take over an expired lease, with `epoch = epoch + 1` |
| `renew` | Only if `holder` and `epoch` match |
| `release` | Only if `holder` and `epoch` match |

**Fenced writes:** every write on behalf of a lease (checkpoint puts, queue transitions, branch pushes) checks `epoch = :my_epoch` in the same statement, or fails with `LeaseLost`.

### 3.2 `telemetry` schema

```sql
CREATE TABLE telemetry.runs (run_id text PRIMARY KEY, experiment_id text, label text NOT NULL,
  manifest jsonb NOT NULL, status text, started_at timestamptz NOT NULL, ended_at timestamptz);

CREATE TABLE telemetry.llm_calls (
  call_id text PRIMARY KEY, run_id text NOT NULL, task_id text, attempt_id text, role text NOT NULL,
  call_seq int NOT NULL, model_digest text NOT NULL, endpoint text NOT NULL,      -- '/v1/chat/completions' | '/api/chat'
  prompt_tokens int, prompt_tokens_computed int,                                  -- cache misses actually prefilled (if available)
  completion_tokens int, thinking_tokens int,
  ttft_ms int, decode_tps real, total_ms int, upstream_ms int, tunnel_rtt_ms int,
  context_budget int, counted_prompt_tokens int,                                  -- gateway tokenizer count
  rejected_reason text,                                                           -- NULL | 'budget' | 'auth' | 'upstream'
  error_class text NOT NULL,                                                      -- FailureClass
  request_blob text, response_blob text,                                          -- sha256 refs to runs/<run_id>/blobs/
  started_at timestamptz NOT NULL);

CREATE TABLE telemetry.attempts (
  attempt_id text PRIMARY KEY, task_id text NOT NULL, run_id text NOT NULL, n int NOT NULL,
  worker text NOT NULL, status text NOT NULL, failure_class text NOT NULL,
  wall_clock_s real, gpu_s real, tool_s real, output_tokens bigint, input_tokens_computed bigint,
  loc_added int, loc_removed int, diff_blob text, transcript_blob text,
  started_at timestamptz NOT NULL, ended_at timestamptz);

CREATE TABLE telemetry.judge_results (
  verdict_id text PRIMARY KEY, attempt_id text NOT NULL, passed boolean NOT NULL,
  failure_class text NOT NULL, checks jsonb NOT NULL,          -- list[CheckResult]
  oracle_sha text NOT NULL, tests_expected int, tests_collected int, tests_passed int,
  skipped int, xfailed int, deselected int, created_at timestamptz NOT NULL);

CREATE TABLE telemetry.tasks (
  task_id text PRIMARY KEY, run_id text NOT NULL, kind text NOT NULL, final_status text,
  attempts int, infra_failures int, accepted_attempt_id text,
  output_tokens_total bigint, loc_accepted int, output_tokens_per_accepted_loc real,
  hidden_pass boolean, escalation_minutes real, created_at timestamptz NOT NULL, closed_at timestamptz);

CREATE TABLE telemetry.hidden_scores (                     -- only scores, never test content
  score_id text PRIMARY KEY, run_id text NOT NULL, scope text NOT NULL,   -- 'task:<id>' | 'project'
  suite_sha text NOT NULL, total int NOT NULL, passed int NOT NULL,
  by_priority jsonb, created_at timestamptz NOT NULL);

CREATE TABLE telemetry.project_results (run_id text PRIMARY KEY, metrics jsonb NOT NULL, created_at timestamptz NOT NULL);

CREATE TABLE telemetry.gpu_samples (ts timestamptz NOT NULL, gpu_util real, mem_used_mb real, power_w real,
  sm_clock_mhz real, mem_clock_mhz real, temp_c real, power_capped boolean, ecc_errors int, source text NOT NULL);
CREATE TABLE telemetry.system_samples (ts timestamptz NOT NULL, component text NOT NULL, cpu_pct real,
  mem_mb real, disk_used_pct real, extra jsonb);

CREATE TABLE telemetry.human_ledger (
  entry_id text PRIMARY KEY, person text NOT NULL, category text NOT NULL,
  -- categories: gate_review|g1_sampling|pr_review|escalation|clarification|uat|onboarding|platform_intervention|spec_authoring|hidden_suite_authoring
  run_id text, task_id text, gate_id text, started_at timestamptz NOT NULL, ended_at timestamptz, note text);

CREATE TABLE telemetry.events (event_id text PRIMARY KEY, run_id text, kind text NOT NULL,
  payload jsonb NOT NULL, ts timestamptz NOT NULL);    -- e.g. tunnel_down/up, readiness_change, quarantine, lease_lost
```

### 3.3 `audit` schema

```sql
CREATE TABLE audit.log (
  seq bigserial PRIMARY KEY, ts timestamptz NOT NULL, actor text NOT NULL, action text NOT NULL,
  subject text NOT NULL, payload_sha256 text NOT NULL, prev_hash text NOT NULL, hash text NOT NULL);
-- hash = sha256(prev_hash || seq || ts || actor || action || subject || payload_sha256)
-- written by a single appender (mesh.governance.audit) with an advisory lock; anchors in §9
```

## 4. Gateway API — `gateway/` (`mesh_gateway`)

| Endpoint | Method | Purpose |
|---|---|---|
| `/v1/chat/completions` | POST | OpenAI-compatible; streaming and non-streaming; tools passthrough |
| `/v1/models` | GET | Lists only models in `models.lock` |
| `/api/chat` | POST | Native Ollama passthrough (metering source for `prompt_tokens_computed`, if needed) |
| `/ready` | GET | 200 only if: upstream `/api/version` OK, pinned model digests match, and a 1-token generation succeeded within the last 60 s (cached) |
| `/healthz` | GET | Process liveness |
| `/metrics` | GET | Prometheus: requests, rejections by reason, tokens, latency histograms, upstream errors |

### 4.1 Request handling

- **Auth:** `Authorization: Bearer mk_<random 32 bytes urlsafe>`. Unknown key → **401**. Expired or revoked → **403**.
- **Model:** forced to the key's `model_name`. A mismatching `model` in the request → **400**. The client cannot choose another model.
- **Budget:**
  1. Render the messages with the model's chat template approximation.
  2. Count tokens with the pinned `tokenizer.json`, plus a safety margin of 3% + 64 tokens.
  3. If the count exceeds `context_budget - max_output_tokens`, return **413** `{"error":{"type":"budget_exceeded",...}}`. **No upstream call is made; nothing is truncated.**
- **Caps:**
  - `max_tokens` is clamped to `max_output_tokens`.
  - The task's cumulative `gpu_token_budget`, if set, is checked: exceeded → **429** `budget_exhausted`, task escalates.
  - Thinking limits are passed via model options where supported.
- **Usage:** for streaming, force `stream_options.include_usage=true` upstream. **Verify in WP0.6** that Ollama returns usage on `/v1`.
- **Errors:** upstream connection error or 5xx → **503** `upstream_unavailable`, `error_class=infra`. The gateway also emits a `tunnel_down` event when `/api/version` fails.
- **Metering:** one `telemetry.llm_calls` row per request: TTFT (first byte of the first content delta), total, decode tok/s (= completion_tokens / time after the first token), counted vs reported prompt tokens.
- **Blobs:** request and response bodies are written zstd-compressed to `runs/<run_id>/blobs/<sha256>.zst`. The runs volume is mounted into the gateway container; the bodies are redacted first.
- **Cassette mode:**
  - `MESH_GATEWAY_MODE=record|replay|live`;
  - key = sha256(model + canonical JSON of messages, tools and options, excluding `stream`);
  - record writes `platform/tests/cassettes/<suite>/<key>.json`;
  - replay serves it, and a miss → **599** `cassette_miss` (fails the test, never falls through to live).

### 4.2 Virtual key lifecycle (`mesh.llm.keys`)

| Function | Behaviour |
|---|---|
| `issue_key(run_id, task_id, attempt_id, role, budgets, ttl)` | Returns the plaintext key once; stores only its sha256 |
| `revoke_key(...)` | Called when an attempt ends, for any reason |

- Keys reach a workspace as an environment variable only, and are never written to disk in the workspace.
- One key per attempt.

## 5. Task and attempt contracts — `mesh.workers.contracts`

### 5.1 `TaskSpec`

| Field | Type | Notes |
|---|---|---|
| `task_id` | `str` | |
| `kind` | `Literal["implement","fix","refactor","test_author","migration","contract","docs"]` | |
| `title`, `goal` | `str` | Goal in plain language |
| `requirements` | `list[str]` | Requirement IDs |
| `must_turn_green` | `list[str]` | Test node IDs (visible oracle) this task must make pass (RV-08) |
| `context_files` | `list[str]` | Suggested files (retrieval hints) |
| `allowed_paths` | `list[str]` | Glob scope the worker may modify (FR-IMP-03) |
| `protected_manifest_sha` | `str` | Manifest version the judge applies |
| `checks` | `list[str]` | e.g. `["pytest:tests/acceptance/test_loans.py", "ruff", "mypy", "importlinter", "semgrep"]` |
| `limits` | `{wall_clock_s, max_turns, max_output_tokens_per_turn}` | |
| `failure_report` | `FailureReport \| None` | Structured feedback from the previous attempt (no raw logs) |

### 5.2 `FailureReport`

Built from `JudgeVerdict`. This is the **only** feedback channel into retries; raw CI or test output never goes back to the model (RV-15).

| Field | Content |
|---|---|
| `failed_tests` | Test IDs + assertion type + a short message, truncated to 300 chars and stripped of anything that looks like instructions |
| `failed_checks` | `CheckFailure` + the file and line where available |
| `policy_violations` | What was touched or added that is not allowed |

### 5.3 In-container contract (the worker runtime)

The host mounts a per-attempt directory at `/workspace` (the repo checkout at the base commit) and `/mesh` (read-only).

| Path | Direction | Content |
|---|---|---|
| `/mesh/task.json` | in, read-only | `TaskSpec` |
| `/mesh/runtime.json` | in, read-only | `{gateway_url, model, limits}`. The key is in env `MESH_KEY` |
| `/workspace` | in/out | Repository working tree |
| `/out/result.json` | out | `AttemptResult` |
| `/out/transcript.jsonl` | out | Harness transcript (tool calls, model turns), redacted |

The container's entrypoint is `python -m mesh_worker.run --adapter <name>`.

**Exit codes:**

| Code | Meaning |
|---|---|
| 0 | Finished; see `result.json` |
| 10 | Harness error (`TASK`) |
| 20 | Gateway unavailable (`INFRA`) |
| 30 | Budget exhausted (`BUDGET`) |
| 40 | Oracle-defect report filed |

An exit of 137 or a missing `result.json` is classified on the host (OOM → `INFRA`).

### 5.4 `AttemptResult`

| Field | Notes |
|---|---|
| `status` | `completed \| gave_up \| oracle_defect` |
| `summary` | Worker's own claim. **Ignored for pass/fail**; stored for analysis |
| `oracle_defect` | `{test_id, reason, evidence}` if filed |
| `turns`, `tool_calls` | Counts |

The diff is **not** taken from the worker. The host computes `git diff base..HEAD` of `/workspace` after the container exits.

### 5.5 `WorkerAdapter` protocol (host side) — `mesh.workers.base`

```python
class WorkerAdapter(Protocol):
    name: str
    version: str
    def image(self) -> str: ...                               # workspace image tag (digest-pinned)
    def command(self, spec: TaskSpec) -> list[str]: ...       # entrypoint args
    def config_hash(self) -> str: ...
```

The **sandbox manager** (`mesh.workspace`) runs it. Adapters never touch Docker or the host filesystem directly.

## 6. Judge contracts — `mesh.judge`

### 6.1 Inputs

| Input | Content |
|---|---|
| Candidate tree | The workspace after the attempt (copied, read-only) |
| `base_commit` | |
| Oracle checkout | Hash-pinned (`oracle_sha`), mounted read-only **at the paths the manifest defines**. These overwrite any same-named files in the candidate tree |
| Protected-path manifest | `ProtectedManifest` |
| Test manifest | Expected test node IDs per suite |

### 6.2 `ProtectedManifest` (YAML in the project repo; its sha is pinned in the task)

```yaml
version: 1
protected:            # any change → PROTECTED_PATH failure
  - "tests/acceptance/**"
  - "tests/e2e/**"
  - "**/conftest.py"
  - "pyproject.toml#tool.pytest"      # section-level: only this TOML table is protected
  - "pyproject.toml#tool.coverage"
  - "pyproject.toml#tool.ruff"
  - "pyproject.toml#tool.mypy"
  - ".importlinter"
  - "contracts/**"
  - ".github/**"
  - "migrations/versions/**"          # existing revisions immutable; new files allowed only for migration tasks
  - "mesh/protected-manifest.yaml"
ratchets:
  suppressions: ["# noqa", "# type: ignore", "# nosec", "# pragma: no cover", "@pytest.mark.skip", "@pytest.mark.xfail"]
  max_new_per_attempt: 0
```

### 6.3 `JudgeVerdict`

| Field | Notes |
|---|---|
| `verdict_id`, `attempt_id`, `passed` | |
| `failure_class` | `FailureClass` |
| `checks` | `list[CheckResult{name, passed, failure: CheckFailure \| None, details_blob}]` |
| `oracle_sha`, `tests_expected`, `tests_collected`, `tests_passed`, `skipped`, `xfailed`, `deselected` | |

`passed` is true only if: every check passed, AND `tests_collected == tests_expected`, AND `skipped == xfailed == deselected == 0` for oracle suites, AND no policy violation. **Default `False`.**

## 7. Gate packages — `mesh.governance.gates`

- **Layout:** a directory `runs/<run_id>/gates/<gate_id>/` with `package.md` (YAML front matter: `gate_id`, `kind`, `run_id`, `created_at`, `inputs: [paths + sha256]`) and attached files.
- **Hash:** sha256 of a deterministic tar of the directory (sorted paths, fixed mtimes, uid/gid 0). Stored in `platform.gates.package_hash`.
- **Approval:**

  ```
  mesh gate approve <gate_id> --hash <first 12 hex chars> [--comment ...]
  ```

  - The CLI recomputes the hash. A mismatch with the prefix, or with the stored hash → `GateMismatch`, which fails closed.
  - It writes a decision record `{gate_id, package_hash, decision, approver, ts}` and signs it with `ssh-keygen -Y sign -f $MESH_APPROVER_SSH_KEY -n mesh-gate`.
  - It stores the signature, appends to `audit.log`, and resumes the graph with `Command(resume={"package_hash": ..., "decision": ..., "signature": ...})`.
- **The graph node after the interrupt verifies:**
  - the signature, against `infra/approvers/allowed_signers`;
  - the hash, against the stored package.

  Either failing → reject.
- **Never:** agents and the orchestrator hold no approver key, and the approve command refuses to run inside a container (it checks for `/.dockerenv`).

## 8. Role definitions — `roles/<role>.yaml`

```yaml
role: worker                       # unique
version: 3                         # bump on any change; roles_sha recorded per run
model_ref: primary                 # resolved via models.lock aliases
context_budget: 49152
max_output_tokens: 8192
thinking: {enabled: true, max_tokens: 4096}
temperature: 0.2
tools: [read_file, write_file, edit_file, list_dir, grep, run_tests, run_shell]   # names from the adapter's tool registry
output_schema: null                # or a pydantic model path for structured roles, e.g. mesh.agents.schemas:ArchitectureDraft
prompt: prompts/worker.md.j2       # Jinja2; static parts first (prefix-stable), task-specific last
taint_policy: deny_new_dependencies_from_tainted_context
```

**Structured outputs:**

- Roles with an `output_schema` call the model with JSON-schema-constrained output (Ollama `format` with a JSON schema, or tool calling).
- The result is validated with Pydantic, with up to 2 repair retries.
- Still invalid → `TASK` failure (fail closed).

## 9. Audit anchors — `mesh.governance.audit`

- After each gate decision, each deploy event, and at least every 60 s while runs are active, the appender writes the current head `(seq, hash)` to `$MESH_ANCHOR_PATH` (default `~/.mesh-anchors/anchors.log`, **outside the repo and the Docker volumes**), signed with the approver-independent `MESH_ANCHOR_SSH_KEY`.
- `mesh audit verify` recomputes the chain and checks it against the anchors.

## 10. Benchmark formats — `benchmark/`

**`projects/<id>/meta.yaml`:**

```yaml
id: S1
tier: S
title: Library lending API
stack: python-fastapi            # + svelte from M-tier
size_estimate_loc: 8000
delphi_hours: {p10: 0, p50: 0, p90: 0}     # filled by humans (HC-04)
contamination: none-known        # or a note, e.g. "public spec; models likely trained on implementations"
hidden_suite_ref: S1@<sha>       # resolved under MESH_HIDDEN_ROOT; only the sha is in this repo
spec_version: 1
```

**`projects/<id>/spec/`:**

- `requirements.md` (EARS, IDs `REQ-…`, with a priority of critical/high/medium/low);
- `features/*.feature` (Gherkin with Examples tables);
- `contracts/openapi.yaml` (once frozen, for spike projects);
- `tasks.yaml` (spike task list, Phase 1 only).

**`microbench/<task-id>/task.yaml`:**

```yaml
id: MB-0042
source: S1-reference@<sha>       # repo snapshot the task starts from
kind: implement
goal: "Implement POST /loans/{id}/return including late-fee calculation per REQ-LOAN-07"
allowed_paths: ["src/app/modules/loans/**"]
visible_tests: ["tests/acceptance/test_loan_return.py"]
hidden_ref: MB-0042@<sha>        # under MESH_HIDDEN_ROOT
tier: task
```

**`experiments/<E-id>.yaml`:** the format in [08 §6.2](../08-prototype-plan.md). Fields are validated by `mesh.evaluation.cards.ExperimentCard`. A card must have `approved_by` and `approved_at` set (HC-08) before a `measured` run starts.
