# 04 — Technology Review: Proposed Foundation Stack

| | |
|---|---|
| **Project** | AI Mesh (working name) |
| **Status** | v1 — **Decision recorded 2026-10-05: none of the reviewed components are adopted for v1.** The platform stays on LangChain/LangGraph, Qdrant and Chroma (see §0). |
| **Date** | 2026-10-05 |
| **Depends on** | [01-project-charter.md](01-project-charter.md), [02-constraints-and-infrastructure.md](02-constraints-and-infrastructure.md), [03-platform-requirements.md](03-platform-requirements.md) |

## 0. Decision (2026-10-05)

After this review, the decision is **not to use FlowEngine, NeuroCore, neurocore-skills, ArxDB or neurogossip-v3 in v1**. v1 stays on the original plan:

- **Workflow / orchestration:** LangGraph with a PostgreSQL checkpointer (D4).
- **Agent framework and worker harness:** LangChain; LangChain Deep Agents remains a candidate in the worker-runtime bake-off (D3, D15).
- **Vectors:** Qdrant, with Chroma per the original plan (D10).
- **Knowledge graph:** PostgreSQL + Apache AGE or Neo4j (D10).
- **Inter-agent communication:** typed handoffs through a durable PostgreSQL task queue plus an event channel (D17).
- **Audit trail:** an append-only, tamper-evident audit table (D16).

The review below is kept as a record and as input for re-assessment after v1. Its design lessons still apply to our own components: fail-closed gates and judges, schema-validated outputs, per-branch state isolation, and a concurrency cap tied to the GPU scheduler.

## 1. Scope and method

Five repositories were proposed as the foundation of the mesh:

| Proposed role | Repository |
|---|---|
| Workflow engine (instead of LangGraph) | [alexh-scrt/flowengine](https://github.com/alexh-scrt/flowengine) |
| Agent-application foundation | [alexh-scrt/neurocore](https://github.com/alexh-scrt/neurocore) |
| Skills that enforce NeuroCore behaviour | [alexh-scrt/neurocore-skills](https://github.com/alexh-scrt/neurocore-skills) |
| Knowledge graph | [larklaflamme/arxdb](https://github.com/larklaflamme/arxdb) |
| Cross-agent communication | [larklaflamme/neurogossip — neurogossip-v3](https://github.com/larklaflamme/neurogossip/tree/master/neurogossip-v3) |

**Method.** Each repository was cloned (default branch, 2026-10-05) and reviewed statically: README and design documents, source code on the paths our requirements depend on, tests, licence, history and CI. Each was assessed against the requirements in [03](03-platform-requirements.md).

**Limitation.** The repositories' test suites were **not executed** in this review — installing and running third-party code was not permitted in the review environment. All findings below come from reading the code. Every finding marked *(verify)* should be confirmed by a test in the Phase 1 conformance spike (§8).

**Verdict scale:** **Adopt** · **Adopt conditionally** (trial in Phase 1 behind an interface, with listed fixes as go/no-go) · **Reuse parts** · **Not for v1**.

## 2. Summary

| Component | Proposed role | Verdict | One-line reason |
|---|---|---|---|
| FlowEngine | Workflow engine | **Adopt conditionally** | Small, typed, well-tested, agent-generatable YAML with a safe expression evaluator and policy layer. Checkpoints only at approval pauses and in memory, so no crash recovery yet |
| NeuroCore | Agent-application chassis | **Adopt conditionally** | Good skill/blueprint/provider-injection model and a correct approval gate. Resume, crash-recovery and concurrent-branch defects in the runtime; SQLite-only run store |
| neurocore-skills | Role skills and enforcement | **Reuse parts** (integrations only) | Orchestration skills are scaffolds that report success without doing work and approve by default. No licence |
| ArxDB | Knowledge graph | **Not for v1 as the KG**; candidate for the audit/attestation ledger | Well-built signed Merkle store, but its data model is mathematical claims and inference edges, not a traceability graph |
| neurogossip-v3 | Cross-agent communication | **Not for v1** | Self-described "Design Phase"; in-memory state only; no agent authentication; peer deliberation conflicts with our typed-handoff design. No licence |

**Overall:** the proposal is a coherent family. FlowEngine and NeuroCore are the strongest pieces and a reasonable alternative to LangGraph for our workflow layer, provided the durability gaps are closed in Phase 1. The other three do not meet v1 needs in their proposed roles.

## 3. Repository health

| | FlowEngine | NeuroCore | neurocore-skills | ArxDB | neurogossip |
|---|---|---|---|---|---|
| Licence | MIT | Apache-2.0 | **none** | MIT | **none** |
| Version / maturity | 0.6.0, "Beta" | 0.4.0, "Alpha" | unversioned | "production-ready" (README) | v3: "Design Phase" (README) |
| Commits / history | 17, Dec 2025 – Jun 2026 | 23, Feb – Jun 2026 | 3, Jun – Aug 2026 | 27, Aug – Sep 2026 | 3, Jun – Aug 2026 |
| Contributors | 1 | 1 | 2 | 2 | 1 |
| Source / test lines (Python) | ~7.2k / ~8.9k | ~5.4k / ~6.4k (+ ~6.8k in bundled skill packages) | ~4.7k incl. ~2.4k math skill | ~5.6k Py + ~4.5k Go / ~3.5k | v3: ~1.6k / ~1.3k |
| CI | none | none | none | Docker build only | none |
| Python | ≥ 3.11 | ≥ 3.13 | per package | ≥ 3.10 | — |

**Cross-cutting risks**

1. **Bus factor and support.** Every repository has one or two contributors and no CI. For a customer platform, each adopted component needs a named in-house owner, a pinned fork or vendored copy, and our own CI running its tests.
   - If these projects are developed by you or your team, this becomes an ownership decision rather than a vendor risk, and the fixes below are within your control.
2. **Licensing.** neurocore-skills and neurogossip have no licence file, so by default no one else has the right to use, modify or redistribute them. A licence must be added before the customer uses any part of them (NFR-MNT-04).
3. **Self-reported status.** ArxDB's "production-ready" badge sits on a one-month-old repository. Status claims in READMEs should be treated as the authors' own assessment.

## 4. FlowEngine — workflow engine

### 4.1 What it is

A lightweight engine that runs flows defined in YAML: sequential, conditional and graph flows, including cyclic graphs with iteration limits. Components route execution through named ports. From v0.5 it doubles as an "Agent Workflow IR": agents can generate a flow, validate it (machine-readable issues with JSON-patch repair hints), plan, run, trace and replay it. Its only dependencies are `pyyaml` and `pydantic`.

### 4.2 Strengths

- **Small and typed.** mypy-strict configuration, and more test code than source code.
- **Safe conditions.** Condition expressions are checked against an AST allowlist that permits no function calls, and are evaluated with empty builtins (`eval/safe_ast.py`, `eval/evaluator.py:85-87`).
- **Policy layer.** `ExecutionPolicy` (`agent/policy.py`) supports allow/deny lists of components, risk and approval gates, and caps on runtime, iterations, component calls and parallel nodes. This maps directly to FR-AGT-01 and NFR-SEC-03.
- **Agent-friendly flows.** Flows are declarative YAML that agents can generate and repair, which suits FR-AGT-01 (versioned, declarative role and workflow definitions in git).
- **Human gates.** Cyclic graphs with `max_iterations` and per-node `max_visits`, plus suspend/resume, support bounded review loops and human gates.

### 4.3 Gaps against our requirements

| # | Finding | Evidence | Requirement affected | Fix |
|---|---|---|---|---|
| F1 | A checkpoint is written **only when a flow suspends** (e.g. at an approval gate), not after each step. A crash mid-flow loses all progress since the last suspension. | `core/engine.py:292-303` | NFR-REL-01, FR-PRJ-04 | Add a hook that saves a checkpoint after every node; `resume()` already skips completed nodes |
| F2 | Only an in-memory checkpoint store exists ("Production uses DB-backed store", but none is provided). | `core/checkpoint.py:71-85` | NFR-REL-01 | Write a PostgreSQL `CheckpointStore` (~1 day; the interface has three methods) |
| F3 | Graph nodes run **one at a time**, in topological order, on both the sync and async paths. | `core/graph.py:213-229, 465-486` | — (acceptable) | None needed for v1: parallelism belongs in the GPU-aware scheduler, not the workflow engine |
| F4 | Component `type` is a Python import path loaded with `importlib`. | `config/registry.py:41` | NFR-SEC-03 | Any flow an agent generates must run under an `ExecutionPolicy` allowlist — enforce this in the platform, never optional |
| F5 | `resume()` is implemented only for graph flows. | `core/engine.py:400-402` | FR-HUM-01 | Model gated lifecycles as graph flows |

### 4.4 FlowEngine vs LangGraph for this project

| Criterion | FlowEngine | LangGraph |
|---|---|---|
| Fit to our workflow layer (lifecycle state machine with gates; coding work done by external worker harnesses) | Good — declarative, small, policy-aware | Good — but much of its value (agent loops, message state) we would not use |
| Durable per-step checkpoints | **Missing** (F1–F2) — small, contained fix | Built in (PostgreSQL checkpointer) |
| Crash recovery of a running process | Ours to build (supervisor re-invokes `resume`) | Also ours to build, or via Temporal |
| Agent-generated, validated workflows | **Strong** (compiler, repair hints, JSON Schema export) | Code-defined graphs |
| Ecosystem, maturity, support | 1 maintainer, v0.6, no CI | Large ecosystem, v1.x, commercial backing |
| Ownership | Small enough (~7k lines) to own outright | Too large to own; dependency on the vendor's roadmap |

**Verdict: Adopt conditionally.** FlowEngine is a defensible choice for the workflow layer if F1, F2 and F4 are closed and it passes the conformance spike (§8). Keep LangGraph as the documented fallback. Effort: ~1–2 engineer-weeks, including tests.

## 5. NeuroCore — agent-application chassis

### 5.1 What it is

An application framework on top of FlowEngine. It provides:

- **Skills:** pip-installable `Skill`/`AsyncSkill` classes with `SkillMeta` declaring what they provide, consume and require, auto-discovered via entry points.
- **Blueprints:** YAML flows that wire skills together.
- **LLM provider injection:** Anthropic, OpenAI, Gemini, Ollama/vLLM/OpenAI-compatible, LiteLLM, and a mock.
- **Durable run history:** SQLite by default, with list/inspect/replay/resume commands.
- **Human approval gate**, an MCP tool skill, retries with backoff, structured logging, a CLI and project scaffolding.

### 5.2 Strengths

- **The skill contract** (`SkillMeta`: provides/consumes/config schema/retry policy) is a clean unit for agent roles and integrations. It matches our worker-adapter design.
- **Correct approval gate.** The built-in `ApprovalSkill` suspends the run and waits for an explicit decision, and rejection fails the run when `require` is set (`skills/builtin/approval.py`). This is the right shape for G1, G2 and G3.
- **Provider injection** works with local OpenAI-compatible endpoints, so it can point at our LLM gateway in front of Ollama.
- **Run history** with per-step records gives a starting point for FR-RPT and NFR-OBS.

### 5.3 Gaps against our requirements

| # | Finding | Evidence | Requirement affected |
|---|---|---|---|
| N1 | **Resuming a failed async/DAG run appears to restart from scratch, without the original inputs.** On failure, the run's `final_context` is not saved (only status and error). Resume rebuilds the context from `final_context or {}`, so no steps are marked completed and none are skipped, and `initial_data` is not re-injected. The test for this case checks only the failing step's attempt count, not that the completed step was skipped. *(verify)* | `runtime/executor.py:825-831` (failure path), `:904-916` (resume), `tests/unit/test_executor_tracking.py:248-251` | FR-PRJ-04, NFR-REL-01 |
| N2 | **No recovery after a process crash.** A run killed mid-flight (OOM, restart) stays `RUNNING`, and resume accepts only `SUSPENDED` or `FAILED` runs. | `runtime/executor.py:857` | FR-PRJ-04, NFR-REL-01 |
| N3 | **Concurrent DAG branches share one mutable context.** Every node in a layer receives the same `FlowContext` object, and results are merged "last write wins per key". Two branches writing the same key overwrite each other silently. *(verify)* | `runtime/executor.py:475-477, 489-492` | O1, O5 (correctness, traceability) |
| N4 | **No concurrency cap.** A whole layer is launched at once via `asyncio.gather`. On one H100, uncapped LLM calls defeat the GPU-aware scheduler (NFR-CAP-02). | `runtime/executor.py:475` | NFR-CAP-02 |
| N5 | **Error attribution on concurrent failure.** If one node in a layer fails, every node in that layer is recorded as `FAILED`, including any that succeeded. | `runtime/executor.py:478-488` | FR-RPT-01 |
| N6 | **Run store is SQLite or in-memory only.** We need PostgreSQL, shared by multiple worker processes. | `persistence/` | NFR-REL-02, NFR-SCA-02 |
| N7 | **The LLM interface is text-only**: messages are `(role, content)` strings, and responses carry no tool calls or structured output. NeuroCore cannot host a coding agent's tool loop itself, so coding workers stay external harnesses (Deep Agents, OpenHands, OpenCode) wrapped as skills. This matches the worker-adapter plan; it is a scope note, not a defect. | `llm/provider.py:10-60` | FR-IMP-01 |
| N8 | Python ≥ 3.13 is required; `anthropic` is a hard dependency (unused on-prem, but it pulls in a cloud SDK). | `pyproject.toml` | NFR-MNT-04 (minor) |

**Verdict: Adopt conditionally** as the agent-application chassis, if N1–N6 are fixed (upstream or in our fork) and it passes the conformance spike (§8).

- The fixes are contained in `runtime/executor.py` (~1k lines) and `persistence/`: a PostgreSQL `RunStore`; per-step context persistence; stale-`RUNNING` detection and resume; per-branch context copies with an explicit merge that raises on key conflicts; a semaphore wired to the scheduler.
- Effort: ~2–4 engineer-weeks, including tests.
- If the fixes cannot be committed to, fall back to FlowEngine directly with a thin in-house skill layer that copies NeuroCore's `SkillMeta` contract.

## 6. neurocore-skills — role skills and enforcement

### 6.1 What it is

A monorepo of 22 small NeuroCore skill packages:

- **Integrations:** Tavily, Brave, arXiv, Qdrant, Postgres, Ollama, Telegram, Wolfram.
- **Orchestration roles:** planner, worker, coordinator, judge, reviewer, researcher, writer, fact-checker, human, start/end/error.
- **Math:** a substantial math skill (~2.4k lines) and a math verifier.

### 6.2 Findings

The orchestration skills are **scaffolds, not working components**, and several **fail open**. For a verification-first platform this is disqualifying for those roles:

| Skill | Behaviour found in code |
|---|---|
| `worker` | Parses the task YAML and sets `"Task step <id> executed successfully."` **without executing anything**. |
| `coordinator` | Ends the flow after a hard-coded second cycle (`cycle_count >= 2`). |
| `judge` | Treats any LLM response containing the substring `"true"` as approval, so "this is not true" approves. **Approves by default when the LLM call fails or no LLM is configured.** |
| `reviewer` | On LLM failure, returns a canned critique ("The draft is solid but requires more citations"). |
| `human` | Defaults to `auto_approve`. In interactive mode, empty input approves, and a stdin error auto-approves. (NeuroCore's built-in `ApprovalSkill` is the correct gate; this skill should not be used.) |
| `planner` | Free-text YAML plan with no validation; a fixed fallback plan if the LLM fails; default provider `mock`. |
| all role skills | Each call opens and tears down a Redis "gossip" listener that lives only for the duration of that call, and silently falls back to a mock transport if Redis is unavailable. Untrusted task output is pasted directly into prompts. |

**Other findings**

- **Tests** check metadata only — e.g. the `worker` test asserts the skill's name and outputs.
- **Off-prem default model.** The repository's `neurocore.yaml` sets `deepseek-v4-flash:cloud`, an **Ollama Cloud** model that would send data off-prem. This conflicts with C1 and NFR-DAT-01 if copied as a default.
- **Committed run database.** `data/runs.db` (~260 KB) is committed and may contain prompts and run data.
- **No licence.**

**Verdict: Reuse parts.**

- **Do not adopt the role skills.** Write our own planner, worker-adapter, judge, reviewer and gate skills to these rules:
  1. **Fail closed.** No output, an error or an unparseable result means *not approved*.
  2. **Structured outputs.** Validate every model output against a JSON schema; never search the text for keywords.
  3. **Executable verification first.** The judge runs tests and checks (FR-IMP-05); LLM opinion supplements them and never replaces them.
  4. **Untrusted content stays data.** Untrusted content is passed as quoted data, never as instructions (NFR-SEC-05).
- **Integration skills** (Tavily, Brave, Qdrant, Postgres, Ollama) are reasonable ~120-line starting points once a licence is added, behind the egress and query-policy controls in [02 §12](02-constraints-and-infrastructure.md).
- **"Enforcing" best practices** belongs in CI gates and executable checks (FR-QA-02, FR-ARC-04), not in LLM skills.

## 7. ArxDB — proposed knowledge graph

### 7.1 What it is

A "reasoning graph database" for mathematical knowledge:

- **Nodes** are immutable, content-addressed claims (`claim`, `domain`, `polarity`).
- **Edges** are signed inference steps (premises → conclusion by a rule). Each edge carries a proof, a verification verdict and a strength grade (κ).
- **Edge types:** definition, deduction, numerical, spectral, reduction, refutation, analogy, citation.
- **Verification layer:** sympy, mpmath, z3 and Lean.
- **Storage:** an object store, a structural adjacency index and an Ed25519-signed append-only log with Merkle inclusion proofs. It runs in SQLite or as a Go/Pebble daemon over gRPC, with cross-language parity tests.

### 7.2 Fit against FR-KNW-01

The README is explicit: *"A knowledge graph stores asserted facts … ArxDB is the second kind"* — it stores derived claims, not asserted relations. Our knowledge graph is the first kind.

| We need (FR-KNW-01, FR-DOC-02, FR-PLN) | ArxDB provides |
|---|---|
| Typed nodes with properties: Requirement, UseCase, AcceptanceTest, Module, Task, PR, TestRun, ADR … | One node type (claim text plus domain); no properties |
| Mutable state: requirement versions, task status, test results over time | Append-only, immutable nodes; a node's identity is the hash of its content |
| Typed relations: `verified_by`, `implements`, `depends_on`, `touches` | Fixed set of 8 mathematical edge types, each requiring a proof and κ grade |
| Ad-hoc queries: traceability matrix, impact analysis ("which acceptance tests cover modules changed in PR X?") | Two queries: reachability and path discovery |
| Per-project create, archive and rebuild | Possible (one data root per project) |

**Verdict: Not for v1 as the knowledge graph.** Keep D10: PostgreSQL + Apache AGE, or Neo4j.

**Where ArxDB does fit.** Its signed, append-only Merkle log is a strong match for **NFR-SEC-04 (a tamper-evident audit log)**. It could also hold a **verification-evidence ledger**: signed attestations such as "acceptance test AT-12 passed on commit `abc123`" or "G2 approved by <reviewer> on <date>", each bound to the artifact hash. That would make release evidence independently checkable.

Recommended as an **optional Phase 2 trial** (D16):

- use the storage layer's generic object store and signed log;
- add a custom checker, or none, for software evidence;
- keep it out of the critical path until proven.

## 8. neurogossip-v3 — proposed cross-agent communication

### 8.1 What it is

A deliberation protocol: agents hold stateful, multi-turn group conversations with turn-taking, voting and interruption until an issue is resolved. It is layered on the neurogossip WebSocket registry and relay (server and client packages in the same repository).

### 8.2 Findings

| # | Finding | Evidence |
|---|---|---|
| G1 | The v3 README states **"Status: Design Phase"**. Redis persistence and the later phases are planned, not built. | `neurogossip-v3/README.md` |
| G2 | Only an **in-memory** state store is implemented, so deliberations do not survive restarts despite that being a design goal. | `src/neurogossip_v3/state_store.py:117` |
| G3 | **"Closed-family trust model — no auth needed"** between agents. Our research agents read untrusted web content, so an injected instruction could propagate agent-to-agent with no authentication or authorization check. | `neurogossip-v3/README.md` |
| G4 | **Architecture conflict.** Peer deliberation as the core primitive is the pattern the evidence warns against: inter-agent misalignment caused ~37% of failures in the MAST study, and Cursor found flat peer coordination failed. Our design (charter principle 7) uses hierarchical planner → worker → judge with **typed handoffs**, and workers do not converse. | [00 §4.3](00-idea-assessment.md) |
| G5 | The pieces aren't wired together yet: neurocore-skills imports `neurogossip_agent` (agent-v3), which v3 is designed to replace. | neurocore-skills role skills |
| G6 | No licence. | repository root |

**Verdict: Not for v1.** Cross-agent communication in v1:

- **Work handoff.** Typed task and result artifacts, with a durable task queue in PostgreSQL (e.g. `SELECT … FOR UPDATE SKIP LOCKED`). Task state is mirrored to GitHub Issues/Projects.
- **Code and specifications** move through git.
- **Notifications.** A lightweight event channel (PostgreSQL `LISTEN/NOTIFY`, or Redis Streams if needed) for wake-ups and dashboards.
- **Re-assess in Phase 3.** One bounded use could fit: the adversarial architecture review (FR-ARC-05) — a fixed set of reviewer roles, a round limit and a vote. Preconditions: persistence, agent authentication, tests and a licence exist.

## 9. Phase 1 conformance spike (go/no-go for FlowEngine and NeuroCore)

Run in the first 2–3 weeks of Phase 1, in an isolated environment, alongside the model and runtime bake-offs.

| # | Test | Pass criterion |
|---|---|---|
| T1 | Run each project's own test suite in our CI | Green on our pinned versions |
| T2 | Kill the process (SIGKILL) mid-run, restart the supervisor | Run resumes from the last completed node with original inputs; no completed node re-executes |
| T3 | Fail a step, then resume | Completed steps are skipped; the counts are asserted |
| T4 | Human gate: suspend, wait (simulated days), approve or reject via API | Approve continues; reject and timeout **fail closed** |
| T5 | Two parallel branches write the same key | Explicit conflict error, never silent overwrite |
| T6 | Concurrency cap | Never more concurrent LLM calls than the scheduler's limit |
| T7 | Multi-process workers on the PostgreSQL run and checkpoint store | No lost or duplicated steps under contention |
| T8 | Agent-generated flow referencing a non-allowlisted component | Rejected at compile time and at run time |
| T9 | Engine overhead | Negligible relative to LLM latency (< 1% of node time) |
| T10 | Licence and dependency scan | All adopted code under approved licences |

**If T2–T8 cannot be met** with ≤ 4 engineer-weeks of fixes, fall back to LangGraph + PostgreSQL checkpointer for the workflow layer (D4 fallback) and keep NeuroCore's `SkillMeta` contract as an in-house pattern.

## 10. Recommended stack after this review

| Layer | Recommendation | Decision |
|---|---|---|
| Workflow / lifecycle engine | **FlowEngine** (conditional), with a PostgreSQL checkpoint store and per-node checkpoints; LangGraph as fallback | D4 (updated) |
| Agent-application chassis | **NeuroCore** (conditional), with fixes N1–N6 | D15 (new) |
| Role skills | In-house, fail-closed, schema-validated; reuse neurocore-skills integrations after licensing | D15 |
| Coding workers | External harness behind the worker adapter (Deep Agents / OpenHands / OpenCode bake-off) | D3 (unchanged) |
| Knowledge graph | PostgreSQL + Apache AGE (or Neo4j); Qdrant for vectors | D10 (unchanged) |
| Audit / evidence ledger | Append-only audit table now; **ArxDB** signed log as an optional Phase 2 trial | D16 (new) |
| Inter-agent communication | Typed handoffs + durable PostgreSQL task queue + event channel; neurogossip re-assessed in Phase 3 | D17 (new) |

## 11. Open questions

1. Who will own FlowEngine and NeuroCore for the customer (fixes, releases, CI), and will upstream accept the fixes or should we fork?
2. Can licences be added to neurocore-skills and neurogossip?
3. Is the customer comfortable with single-maintainer foundations, given the ownership plan in (1)?
