# 03 — Platform Requirements (Functional & Non-Functional)

| | |
|---|---|
| **Project** | AI Mesh (working name) |
| **Status** | Draft v1.1 — amended by adversarial review R1 ([07](07-adversarial-architecture-review.md)); new requirements in §10; items marked ⚠ need customer confirmation |
| **Date** | 2026-10-05 |
| **Depends on** | [01-project-charter.md](01-project-charter.md), [02-constraints-and-infrastructure.md](02-constraints-and-infrastructure.md) |

## 1. About this document

These are the requirements for the **AI Mesh platform itself**, not for the software projects it builds.

- **IDs:** `FR-<area>-nn` for functional requirements, `NFR-<area>-nn` for non-functional ones.
- **Priority (v1):** **M** = must, **S** = should, **C** = could.
- **Objective:** the charter objective (O1–O7) each requirement serves.
- **Wording:** "shall" statements, EARS-style where a trigger or state applies.

## 2. Users and stakeholders

| Role | Interaction with the platform |
|---|---|
| Product owner / sponsor (customer) | Submits the requirements package; answers clarifications; approves G1 and G3 |
| Solution architect (human) | Reviews and approves G2; maintains the technology catalog |
| Delivery engineer / reviewer | Reviews sampled PRs; handles escalations; can take over a task |
| Domain SME | Answers clarification questions; authors held-out benchmark projects; performs UAT |
| Platform operator (MLOps / DevOps) | Operates the servers, models, gateway, sandboxes and capacity |
| Security officer / auditor | Reads audit trails; approves security policies |

## 3. Context summary

Details are in [02](02-constraints-and-infrastructure.md).

- **Server:** one Ubuntu 24.04 server with one H100 (80 GB), AMD EPYC 9124 (16 cores / 32 threads), 124 GB RAM and 4 TB disk; one server per project, more servers later.
- **Inference:** fully on-prem, Ollama serving open-weights models.
- **Source control:** private repositories on github.com.
- **Network:** internet access allowed; web research via Tavily and Brave Search; access to some on-prem databases.
- **Generated projects:** greenfield, 100k–250k LOC, microservices or modular monolith.
- **Platform stack** (the platform itself; generated systems use stacks from the technology catalog): Python, Go, LangChain/LangGraph, Qdrant, Chroma, FastAPI, SQLAlchemy, Svelte web front end or Tauri client.
- **Production** means go-live of the generated system, approved at G3.

## 4. Functional requirements

### 4.1 Project lifecycle (FR-PRJ)

| ID | Requirement | Pri | Obj |
|---|---|---|---|
| FR-PRJ-01 | When a user submits a requirements package (business, technical and non-technical requirements; documents; links), the platform shall create a project and provision: a private GitHub repository, a project database, vector collections, a knowledge graph, a sandbox namespace and a capacity budget. | M | O1, O5 |
| FR-PRJ-02 | The platform shall move each project through defined states: Intake → Clarification → **G1** → Design → **G2** → Build → Verify → **G3** → Released → Archived. Transitions happen only through defined events. | M | O1, O6 |
| FR-PRJ-03 | The platform shall let authorized users pause, resume or cancel a project at any time. | M | O6 |
| FR-PRJ-04 | When the platform restarts after a failure, it shall resume each active project from its last checkpoint without repeating completed, verified work. | M | O7 |
| FR-PRJ-05 | When a project is archived, the platform shall freeze its indexes, retain its audit trail and release its compute resources. | M | O5 |
| FR-PRJ-06 | The platform should support project templates ("domain packs") that preset the catalog, standards and agent configuration. | C | — |

### 4.2 Requirements intake and clarification (FR-REQ)

| ID | Requirement | Pri | Obj |
|---|---|---|---|
| FR-REQ-01 | The platform shall ingest requirement sources (Markdown, DOCX, PDF, plain text, links) and normalize them into uniquely identified, structured requirements (EARS notation), each traceable to its source text. | M | O5 |
| FR-REQ-02 | The platform shall detect ambiguities, conflicts and gaps, and generate prioritized clarification questions within a configurable question budget. | M | O1 |
| FR-REQ-03 | When a stakeholder answers a clarification question, the platform shall record the answer and apply it as a versioned requirement change. | M | O5 |
| FR-REQ-04 | The platform shall derive actors and business use cases and map each use case to its requirements. | M | O1 |
| FR-REQ-05 | The platform shall convert non-functional requirements into measurable targets, or flag them as not measurable for resolution at G1. | M | O1 |
| FR-REQ-06 | The platform should generate a clickable UI prototype (Svelte) for stakeholder validation before G1. | S | O1 |

### 4.3 Domain research (FR-RES)

| ID | Requirement | Pri | Obj |
|---|---|---|---|
| FR-RES-01 | The platform shall research domain topics using Tavily, Brave Search and approved on-prem databases. Each finding is stored with its source, retrieval date and summary. | M | O1 |
| FR-RES-02 | Research agents shall have no shell, code-execution, repository-write or credential-bearing tools. | M | O6 |
| FR-RES-03 | The platform shall block outbound search queries containing secrets, credentials, internal hostnames or configured customer-confidential terms, and shall log all queries. | M | O6 |
| FR-RES-04 | The platform shall pass retrieved web content to other agents only as quoted data with provenance, never as instructions. | M | O6 |
| FR-RES-05 | Access to on-prem databases shall use read-only, scoped accounts through an audited tool layer. | M | O6 |
| FR-RES-06 | The platform should flag time-sensitive findings for re-validation before G1 and G2. | S | O1 |

### 4.4 Oracle construction — verification first (FR-ORC)

| ID | Requirement | Pri | Obj |
|---|---|---|---|
| FR-ORC-01 | For every functional requirement, the platform shall generate acceptance criteria as human-readable Gherkin **with concrete example tables** (inputs and expected outputs as data), linked to the requirement in the knowledge graph. Executable step definitions are produced later, in the Oracle Binding stage (FR-ORC-06). | M | O1, O5 |
| FR-ORC-02 | The platform shall assemble a **G1 package** (requirements, use cases, Gherkin + example tables, resolved and open questions, research summary, prototype), reviewed **risk-tiered**: SME-verified golden scenarios for top-risk use cases, statistical sampling for the rest (batch rejected above a defect threshold), and human review of disagreements between two independently generated oracles. The package is stored immutably with a content hash; approval is bound to that hash. | M | O1 |
| FR-ORC-03 | After G1 approval, implementation agents shall not modify approved acceptance tests. Changes require a change request approved by a human. | M | O1, O6 |
| FR-ORC-04 | The platform shall express measurable NFRs as executable checks (e.g. load-test thresholds, security scans). | M | O1 |
| FR-ORC-05 | The platform shall measure oracle strength: spec mutation of example tables at G1, and code mutation testing on each module's changed code before the module is done and at G3, with a mutation-score gate. | M | O1, O3 |

### 4.5 Architecture and adversarial review (FR-ARC)

| ID | Requirement | Pri | Obj |
|---|---|---|---|
| FR-ARC-01 | The platform shall produce an architecture description with: C4 context and container views; module or service decomposition; explicit interfaces (OpenAPI for HTTP, schemas for events, typed interfaces for in-process modules); data model; deployment view. | M | O1 |
| FR-ARC-02 | The platform shall size modules so each can be built and tested independently by agents (initial target ≤ ~15–20k LOC per module; ⚠ calibrate in Phase 1). | M | O1, O7 |
| FR-ARC-03 | The platform shall record each significant decision as an ADR, including the choice of modular monolith (default) vs. microservices, justified by NFRs. | M | O5 |
| FR-ARC-04 | The platform shall generate architecture fitness functions as CI checks (dependency direction, module boundaries, layering), e.g. import-linter for Python and package rules for Go. | M | O1 |
| FR-ARC-05 | The platform shall run an adversarial review with independent reviewer roles (security, scalability, operability, cost, simplicity). Each finding gets a severity; the architect role revises; the loop ends when no high-severity findings remain or after N rounds. | M | O1 |
| FR-ARC-06 | The platform should run at least one review round with a different model, scheduled as a batch to avoid model swapping. | S | O1 |
| FR-ARC-07 | The platform shall assemble a **G2 package** (architecture, ADRs, review findings and resolutions, technology selections, plan and forecast) for human approval. | M | O1 |

### 4.6 Technology mapping (FR-TEC)

| ID | Requirement | Pri | Obj |
|---|---|---|---|
| FR-TEC-01 | The platform shall maintain a human-curated technology catalog (languages, frameworks, libraries, versions, licences). | M | O6 |
| FR-TEC-02 | Agents shall select technologies from the catalog. Proposals outside the catalog require approval at G2. | M | O6 |
| FR-TEC-03 | The platform shall check every new dependency for licence and known vulnerabilities before adoption. | M | O6 |

### 4.7 Planning, scheduling and forecasting (FR-PLN)

| ID | Requirement | Pri | Obj |
|---|---|---|---|
| FR-PLN-01 | The platform shall derive a work breakdown from the architecture (epics per module, tasks sized to independently verifiable units, dependencies) and publish it as GitHub Issues and a GitHub Project. | M | O1 |
| FR-PLN-02 | The platform shall schedule tasks against available capacity (GPU lanes, concurrent-session caps, human gate availability). | M | O7 |
| FR-PLN-03 | The platform shall forecast agent effort (GPU-hours, wall-clock) and human hours as P10 / P50 / P90 ranges, and re-forecast at each milestone. | M | O4 |
| FR-PLN-04 | The platform shall size projects with a documented, versioned heuristic (use-case points or function points), and record forecast vs. actual for calibration. | M | O4 |
| FR-PLN-05 | The platform should translate GPU-hours and human hours into cost using configurable rates (amortized hardware, labour). | S | O4 |

### 4.8 Implementation (FR-IMP)

| ID | Requirement | Pri | Obj |
|---|---|---|---|
| FR-IMP-01 | The platform shall execute each implementation task in an ephemeral, sandboxed workspace through a **worker adapter**, so coding runtimes are interchangeable. | M | O1, O6 |
| FR-IMP-02 | Each task shall carry: goal, linked requirements and tests, interface contracts, permitted file and module scope, done criteria, and a context budget. | M | O1 |
| FR-IMP-03 | Workers shall modify only files within the task's permitted scope. Out-of-scope changes require escalation to the planner. | M | O1 |
| FR-IMP-04 | Workers shall get context through retrieval (code graph plus vector search), so no agent needs the whole repository in its context window. | M | O7 |
| FR-IMP-05 | A judge step shall mark a task complete only after running its tests and checks, never on the worker's claim alone. | M | O1, O3 |
| FR-IMP-06 | When a task fails N attempts, the platform shall escalate it to a human with a diagnostic summary. | M | O2 |
| FR-IMP-07 | Each task shall run on its own branch and be delivered as a pull request (per task or per small batch). | M | O5 |

### 4.9 Review, testing and QA (FR-QA)

| ID | Requirement | Pri | Obj |
|---|---|---|---|
| FR-QA-01 | The platform shall review every PR automatically for correctness, security, and conformance to contracts and ADRs. | M | O1 |
| FR-QA-02 | CI shall gate merges on: formatting and linting (ruff, gofmt, golangci-lint, eslint / svelte-check); type checks (mypy or pyright); unit, integration and acceptance tests; fitness functions; SAST; dependency, licence and secret scans; coverage threshold. | M | O1, O6 |
| FR-QA-03 | The platform shall route a configurable, risk-weighted sample of PRs to human review. | M | O1 |
| FR-QA-04 | The platform shall run system-level integration and end-to-end tests in the sandbox environment before G3. | M | O1 |
| FR-QA-05 | The platform should run an exploratory QA agent (e.g. Playwright-driven UI exploration) that files defects as GitHub Issues. | S | O1 |
| FR-QA-06 | The platform shall support UAT: deploy to the sandbox and provide a test guide derived from the use cases. | M | O1 |

### 4.10 Source control (FR-SCM)

| ID | Requirement | Pri | Obj |
|---|---|---|---|
| FR-SCM-01 | The platform shall access GitHub through a GitHub App with least-privilege, per-repository permissions. | M | O6 |
| FR-SCM-02 | `main` shall be protected. Merges go through PRs with required checks passing; agents can neither push to `main` nor change protection rules. | M | O6 |
| FR-SCM-03 | When a merge conflict occurs, an agent shall resolve it and re-run all affected checks. | M | O1 |
| FR-SCM-04 | Commits shall follow a convention (e.g. Conventional Commits) and reference task and requirement IDs. | M | O5 |
| FR-SCM-05 | The platform shall tag releases and generate changelogs. | M | O5 |
| FR-SCM-06 | Agent commits should be signed. | S | O6 |

### 4.11 Deployment (FR-DEP)

| ID | Requirement | Pri | Obj |
|---|---|---|---|
| FR-DEP-01 | The platform shall containerize each generated system and deploy it to the sandbox through GitHub Actions on self-hosted runners. | M | O1 |
| FR-DEP-02 | **Go-live** deployments (production for real users) shall run only after **G3** approval, enforced in the platform and again through a GitHub Environment with required reviewers. Agents can prepare a release but never approve it. | M | O6 |
| FR-DEP-03 | The platform shall generate a rollback procedure for each release and exercise it in the sandbox. | M | O6 |
| FR-DEP-04 | Go-live targets shall be configurable per project and per client site. v1 shall support **Docker Compose hosts and Kubernetes** in clients' data centres and at client sites. **Must:** direct push (hardened per FR-SEC-07) and the offline bundle as an archival artifact. **Should:** GitOps pull, added when a client needs it ([06 §6](06-generated-system-baseline-and-release.md)). | M | — |
| FR-DEP-06 | Every release candidate shall be built once, with images referenced by digest and signed, and shall include SBOMs, checksums, a Compose bundle and a Helm chart. Before G3 it shall be rehearsed in the sandbox (install, upgrade from the previous release, rollback) **on each target type present in the project's site profiles**; the offline bundle is rehearsed only when a mode-C site exists. | M | O1, O6 |
| FR-DEP-07 | An offline bundle shall be produced for every release candidate, so air-gapped or client-operated sites can install, upgrade, roll back and smoke-test without access to the platform. | M | O6 |
| FR-DEP-08 | The platform shall keep a versioned **site profile** per client target: target type, network path, registry, identity provider, database, TLS/DNS, secrets, observability, backups ([06 §9](06-generated-system-baseline-and-release.md)). Missing fields block go-live to that site (fail closed), and pre-flight checks validate the profile before G3. | M | O6 |
| FR-DEP-05 | Each release candidate shall include an evidence bundle: acceptance results per requirement, scan reports, traceability matrix, UAT sign-off, runbook and rollback plan. Post-go-live smoke tests trigger the rollback procedure on failure. | M | O1, O5, O6 |

### 4.12 Documentation (FR-DOC)

| ID | Requirement | Pri | Obj |
|---|---|---|---|
| FR-DOC-01 | The platform shall generate technical documentation: architecture (C4), ADRs, API reference (OpenAPI), module READMEs, runbooks and a deployment guide. | M | O1 |
| FR-DOC-02 | The platform shall generate business documentation: use-case catalog, user guide, release notes, and a requirement → test → code → status traceability matrix. | M | O5 |
| FR-DOC-03 | At each release, the platform shall validate documentation against the code (API docs vs. OpenAPI, module docs vs. structure) and flag drift. | M | O1 |

### 4.13 Progress tracking and reporting (FR-RPT)

| ID | Requirement | Pri | Obj |
|---|---|---|---|
| FR-RPT-01 | The platform shall provide a dashboard showing: project state and gates; task burndown; acceptance-test pass rate per requirement; forecast vs. actual; GPU utilization and queue; blocked items; open questions. | M | O4, O7 |
| FR-RPT-02 | The platform shall generate periodic status reports computed from tracked data, not from agent narrative alone. | M | O4 |
| FR-RPT-03 | The platform shall notify the responsible humans of gate requests, clarification questions and escalations (⚠ channel: email / Slack / Teams). | M | O2 |

### 4.14 Human gates and intervention (FR-HUM)

| ID | Requirement | Pri | Obj |
|---|---|---|---|
| FR-HUM-01 | The platform shall provide G1, G2 and G3 review screens showing summaries and diffs since the last review, with approve / reject / request-changes actions and comments. | M | O1, O6 |
| FR-HUM-02 | The platform shall record every human decision in the audit log and the knowledge graph. | M | O5 |
| FR-HUM-03 | Authorized humans shall be able to edit requirements, pin decisions, or take over any task at any time. | M | O6 |

### 4.15 Knowledge services (FR-KNW)

| ID | Requirement | Pri | Obj |
|---|---|---|---|
| FR-KNW-01 | The platform shall keep a per-project **knowledge graph** that accumulates project knowledge as typed entities and their interactions, in two layers. **Delivery layer:** Requirement, UseCase, AcceptanceTest, Module, Interface, ADR, Task, PullRequest/Commit, TestRun, Finding, Decision, ResearchSource. **Domain layer** (the system being built): business entities, actors, services/modules, APIs, events, data stores and external systems. Typed relationships within and across the layers (e.g. `implements`, `verified_by`, `depends_on`, `calls`, `publishes`, `consumes`, `owns_data`, `touches`). | M | O1, O5 |
| FR-KNW-02 | The platform shall keep per-project vector collections for requirements and documents, research notes, and code chunks. Code chunks are re-indexed on every merge to `main`. | M | O1, O7 |
| FR-KNW-03 | The platform shall index a code graph (symbols, imports, references) on every merge to `main`. | M | O7 |
| FR-KNW-04 | Knowledge indexes shall be rebuildable from git plus the run logs. Every embedding records its embedding-model version. | M | O5 |
| FR-KNW-05 | The platform could keep cross-project organizational knowledge (patterns, lessons learned) with explicit opt-in and IP isolation. | C | — |
| FR-KNW-06 | The platform shall let agents reason over the knowledge graph through graph queries exposed as tools, at minimum: impact analysis (what a change to an entity affects), coverage (requirements without tests, modules without owners), dependency and interaction analysis (call/event paths, cycles, boundary violations), and consistency checks (architecture vs. code). | M | O1, O5 |
| FR-KNW-07 | Retrieval shall be hybrid: Qdrant semantic hits are linked to knowledge-graph nodes, so an agent can move from a relevant text chunk to the entities and relationships around it, and back. | S | O1, O7 |
| FR-KNW-08 | The platform could keep a per-project **context and ideas cache** (Chroma): important context, distilled findings and ideas saved by agents for reuse across tasks. It is optional; it is never the source of truth, and anything decision-relevant is promoted to the knowledge graph or git. | C | O7 |

### 4.16 Agent configuration and models (FR-AGT)

| ID | Requirement | Pri | Obj |
|---|---|---|---|
| FR-AGT-01 | Agent roles shall be defined declaratively (role, instructions, tools, model, context budget, permission tier) and versioned in git. | M | O5, O6 |
| FR-AGT-02 | All model calls shall go through the LLM gateway, which routes models per role. | M | O7 |
| FR-AGT-03 | Changes to agent instructions, skills, models or runtimes shall pass the benchmark regression suite before rollout. | M | O3 |

### 4.17 Evaluation harness (FR-EVL)

| ID | Requirement | Pri | Obj |
|---|---|---|---|
| FR-EVL-01 | The platform shall run benchmark projects end-to-end headless, with simulated gate decisions, and collect all core metrics. | M | O3 |
| FR-EVL-02 | The platform shall support a single-agent baseline mode and side-by-side comparison of configurations (model, runtime, instructions). | M | O3 |
| FR-EVL-03 | The platform shall inject seeded defects to measure review and test effectiveness. | M | O1, O3 |

## 5. Non-functional requirements

### 5.1 Data residency and privacy (NFR-DAT)

| ID | Requirement | Pri |
|---|---|---|
| NFR-DAT-01 | All LLM inference shall run on-prem; no project content is sent to external LLM services. | M |
| NFR-DAT-02 | Outbound traffic shall pass through an allow-listed, logged egress proxy: GitHub, Tavily, Brave, package registries and approved documentation sites. | M |
| NFR-DAT-03 | Generated source code shall be hosted only in private repositories on github.com (accepted by the customer). | M |

### 5.2 Security (NFR-SEC)

| ID | Requirement | Pri |
|---|---|---|
| NFR-SEC-01 | Secrets shall live in a secrets manager (e.g. OpenBao / Vault), be injected at runtime, and never appear in prompts, logs or commits. | M |
| NFR-SEC-02 | Agent workspaces shall run non-root, with resource limits and network policies, and without access to the host Docker socket. A stronger isolation runtime (gVisor) should be evaluated. | M |
| NFR-SEC-03 | Every tool available to an agent shall be bound to a permission tier, and every tool call shall be authorized against the agent's role. | M |
| NFR-SEC-04 | The audit log shall be append-only and tamper-evident. | M |
| NFR-SEC-05 | Prompt-injection containment: untrusted content (web pages, issue text, documents) never grants new permissions or changes an agent's task. | M |

### 5.3 Reliability and recovery (NFR-REL)

| ID | Requirement | Pri |
|---|---|---|
| NFR-REL-01 | Workflow state shall be checkpointed at every step, so no completed and verified work is lost on a crash. | M |
| NFR-REL-02 | Platform databases (PostgreSQL, vector store, graph store) shall be backed up off the server daily (RPO ≤ 24 h); the target restore time is ≤ 1 business day (RTO) for the single-server v1. | M |
| NFR-REL-03 | GitHub shall remain the source of truth for code; all derived indexes are rebuildable. | M |

### 5.4 Performance and capacity (NFR-CAP)

| ID | Requirement | Pri |
|---|---|---|
| NFR-CAP-01 | Each server (1×H100, EPYC 9124, 124 GB) runs exactly one project (confirmed); the build-phase throughput target is set after the Phase 1 load test. | M |
| NFR-CAP-02 | The scheduler shall cap concurrent LLM sessions per GPU and apply priority queuing, so interactive gate work is never starved by batch build work. | M |
| NFR-CAP-03 | GPU utilization during build phases should reach ≥ 60%. | S |
| NFR-CAP-04 | Container memory limits shall keep total RAM use within the server's 124 GB with a safety margin (see 02 §11). | M |
| NFR-CAP-05 | UI pages for gate review shall load in < 2 s on the internal network. | S |

### 5.5 Scalability (NFR-SCA)

| ID | Requirement | Pri |
|---|---|---|
| NFR-SCA-01 | Capacity shall scale horizontally by adding servers, either as additional project lanes or as role-specialized nodes (GPU inference, CPU sandbox/CI), without architectural change. | M |
| NFR-SCA-02 | Workers shall be stateless; all state lives in git, the platform database and the knowledge services. | M |

### 5.6 Observability and auditability (NFR-OBS)

| ID | Requirement | Pri |
|---|---|---|
| NFR-OBS-01 | Every model call and tool call shall be traced with: project, task, role, model and version, instruction version, token counts and latency. A self-hosted tracing tool will be used (candidates: Langfuse, self-hosted LangSmith). | M |
| NFR-OBS-02 | Infrastructure metrics (GPU, RAM, disk, queues) shall be collected and alerted on (e.g. Prometheus and Grafana). | M |
| NFR-OBS-03 | Audit records shall retain agent actions, inputs and outputs (or their hashes), and human decisions for ⚠ a retention period to be defined. | M |

### 5.7 Maintainability and portability (NFR-MNT)

| ID | Requirement | Pri |
|---|---|---|
| NFR-MNT-01 | The platform shall be built as a modular monolith in Python, using Go only where it clearly pays (e.g. sandbox manager, scheduler), with enforced module boundaries. | S |
| NFR-MNT-02 | The platform's own repository shall pass the same CI gates it imposes on generated projects. | M |
| NFR-MNT-03 | Switching models or inference engines shall be a configuration change (gateway plus role configuration), with no code changes in agents. | M |
| NFR-MNT-04 | All platform dependencies shall carry permissive or explicitly approved licences. | M |

### 5.8 Usability (NFR-USE)

| ID | Requirement | Pri |
|---|---|---|
| NFR-USE-01 | v1 shall provide a SvelteKit web UI; a Tauri desktop shell can wrap the same front end later. | M |
| NFR-USE-02 | A typical gate package should be reviewable in ≤ 30–60 minutes, through summaries, diffs and drill-down. | S |

## 6. Stack mapping (proposed — ⚠ confirm)

> **Update (2026-10-05):** alternative foundations were reviewed in [04-technology-review-proposed-stack.md](04-technology-review-proposed-stack.md) and not adopted; the mapping below (LangGraph, Qdrant, Chroma) stands for v1.

| Concern | Customer preference | Proposed use |
|---|---|---|
| Platform language | Python, Go | Python for the orchestrator, agents and API; Go for performance-critical infrastructure services if justified |
| Agent orchestration | LangChain / LangGraph or alternative | LangGraph with a PostgreSQL checkpointer for workflows and human-gate interrupts. Durability approach to decide (D4). LangChain Deep Agents as a worker-runtime candidate (D3) |
| Platform API | FastAPI | Platform REST/WebSocket API |
| Relational data | SQLAlchemy | Platform system of record on PostgreSQL (⚠ confirm the RDBMS) |
| Knowledge graph | — | Per-project graph of delivery and domain entities and their interactions (FR-KNW-01, FR-KNW-06); engine: PostgreSQL + Apache AGE or Neo4j (D10, decide in Phase 1) |
| Knowledge base / vectors | Qdrant (KB) | **Qdrant**: per-project collections for requirements and documents, research notes and code chunks, linked to graph nodes (FR-KNW-02, FR-KNW-07) |
| Context and ideas cache | Chroma (optional) | **Chroma**, optional: cache of important context and ideas (FR-KNW-08). Included only if Phase 1 shows a benefit over a separate Qdrant collection |
| Web search | Tavily, Brave | Research tools behind the query-policy filter and egress proxy |
| Front end | Svelte web or Tauri | SvelteKit web UI in v1; optional Tauri shell later |
| Generated systems | Python / FastAPI; Svelte | Not bound to the platform stack. v1 catalog: Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2 + Alembic (SQL-engine agnostic, PostgreSQL in v1), pytest; SvelteKit + TypeScript front end with a generated API client, Vitest, Playwright; full baseline in [06 §2](06-generated-system-baseline-and-release.md) |

## 7. Out of scope (v1)

External LLM APIs; brownfield codebases; production deployment without G3; training or fine-tuning foundation models; mobile, embedded and safety-critical software; projects larger than 250k LOC.

## 8. Traceability to objectives

| Objective | Main requirement groups |
|---|---|
| O1 Deliver against signed-off acceptance tests | FR-REQ, FR-ORC, FR-ARC, FR-IMP, FR-QA, FR-DEP, FR-DOC |
| O2 Reduce human effort | FR-IMP-06, FR-RPT-03, FR-HUM, NFR-USE |
| O3 Beat the single-agent baseline | FR-EVL, FR-AGT-03, FR-IMP-05 |
| O4 Calibrated forecasts | FR-PLN-03..05, FR-RPT |
| O5 Full traceability | FR-KNW, FR-REQ-01, FR-SCM-04, FR-DOC-02, FR-HUM-02 |
| O6 Safe operation | FR-RES-02..05, FR-SCM, FR-DEP-02, NFR-SEC, NFR-DAT |
| O7 Operate within on-prem capacity | FR-PLN-02, FR-IMP-04, FR-KNW-02/03, NFR-CAP, NFR-SCA |

## 9. Open items

1. ~~Stack scope~~ — resolved: the platform itself; generated systems use Python / FastAPI in v1 (D8). Open: front end for generated systems ([06 §9](06-generated-system-baseline-and-release.md)).
2. ~~Qdrant vs. Chroma roles~~ — resolved 2026-10-05 (Qdrant = knowledge base; Chroma = optional context/ideas cache). Knowledge-graph engine still to choose (D10).
3. ~~RDBMS~~ — resolved: PostgreSQL for the platform; generated systems are SQL-engine agnostic with PostgreSQL as the v1 engine (D20).
4. ~~Meaning of production~~ — resolved: go-live at clients' data centres and client sites, on Docker Compose and Kubernetes (D18). Open: the pilot client's delivery mode.
5. Notification channel (email / Slack / Teams).
6. Audit-log retention period and any compliance regime.
7. ~~One project per server~~ — resolved: yes.

## 10. Requirements added by adversarial review R1

Source themes in [07](07-adversarial-architecture-review.md). Priorities are subject to the MoSCoW re-baseline (07 §4.3, ⚠ DN-3).

### 10.1 Verification integrity and oracle (FR-ORC, FR-IMP, FR-QA)

| ID | Requirement | Pri | Source |
|---|---|---|---|
| FR-ORC-06 | **Oracle Binding stage** after G2: step definitions, fixtures and UI locators are written by a role separate from the workers, against the approved contracts. Assertions are mechanically checked to use the G1 example values, and none may be weaker. Approved at **G2b**. | M | RV-06 |
| FR-ORC-07 | A **hidden held-out slice** of acceptance scenarios is withheld from workers and run only by the judge and harness. | M | RV-02 |
| FR-IMP-08 | A platform-owned **protected-path manifest** (acceptance and e2e tests, all `conftest.py`, test/lint/type/coverage configs, `.importlinter`, `contracts/`, `.github/`, migration history). The judge rejects any diff touching it; changes need human CODEOWNERS approval. | M | RV-02 |
| FR-IMP-09 | The judge runs the oracle from a **separate, hash-pinned checkout** against the built image. These count as failures: collected-test count ≠ approved manifest; any skip, xfail or deselect; growth in suppressions (`noqa`, `type: ignore`, `nosec`). | M | RV-02 |
| FR-IMP-10 | Workers can file a typed **oracle defect / impossible task** report, routed to the planner and a human, instead of working around a test. | M | RV-02 |
| FR-IMP-11 | Each task names the acceptance or contract tests it must turn green. Task unit tests are written by a separate test-author call before the worker starts, and are frozen for that task. An **acceptance ratchet** prevents passed tests from failing again. | M | RV-08 |
| FR-QA-07 | CI and release logic run as **platform-owned reusable workflows pinned by SHA**, enforced by rulesets; gate thresholds and scanner configs come from the platform baseline. | M | RV-02 |
| FR-QA-08 | Semgrep rules flag test-mode branches and env-conditional logic in application code. | M | RV-02 |

### 10.2 System coherence and change (FR-PLN, FR-SCM, FR-PRJ)

| ID | Requirement | Pri | Source |
|---|---|---|---|
| FR-PLN-06 | A **Foundation stage** after G2: cross-cutting modules and one end-to-end vertical slice, human-reviewed before parallel Build. | M | RV-08 |
| FR-PLN-07 | **Module integration milestones** with a module acceptance run and an architect conformance review against the ADRs. | M | RV-08 |
| FR-PLN-08 | A **refactor/consolidate** task type, triggered by ratcheted metrics (duplication, complexity, module-size budgets, public-surface growth). | M | RV-08 |
| FR-SCM-07 | A **merge queue** tests combined changes before merge. **Scope leases** serialize hotspot artifacts (one migration writer at a time; contract changes land first as their own tasks). Derived artifacts (generated client, docs) are regenerated after merge. CI rejects multiple Alembic heads. | M | RV-08 |
| FR-PRJ-07 | A **Change Request** flow: KG impact analysis → delta oracle → G1-delta (affected scenarios only) → task invalidation and re-plan → re-forecast. | M | RV-09 |
| FR-PRJ-08 | **Hypercare** and **Maintenance** lifecycle states with a hotfix fast path (reduced, still human, gate); changes to systems the mesh built are in v1 scope. | M | RV-09 |
| FR-PRJ-09 | A tested **re-hydration** of a project onto any node from git and backups. | M | RV-09 |
| FR-DEP-09 | Daily CVE monitoring of delivered SBOMs, raising maintenance tasks. | M | RV-09 |

### 10.3 Security (FR-SEC — new group)

| ID | Requirement | Pri | Source |
|---|---|---|---|
| FR-SEC-01 | **Control/execution plane split**: workspaces, CI runners and sandbox run on a separate execution plane (CPU companion server or KVM microVMs); ephemeral just-in-time runners, one VM per job; no `docker.sock` on the control host. | M | RV-01 |
| FR-SEC-02 | **Network zones** with default-deny egress at L3/L4: execution zones reach only the package proxy and the gateway (per-task virtual keys); Ollama reachable only from the gateway; Qdrant with API keys; PostgreSQL roles per module; OpenBao reachable only from the orchestrator and deploy runner. Jobs authenticate to OpenBao with GitHub OIDC claims. | M | RV-01 |
| FR-SEC-03 | **Two GitHub Apps**: provisioning (administration, human-triggered tool only) and delivery (contents, pull requests, issues, checks read; **no** administration, workflows, environments, secrets or actions-write). Tokens scoped to one repository; key per node; runners registered per repository. | M | RV-22 |
| FR-SEC-04 | **Internal package proxy** serving an allow-list (catalog plus vetted transitive closure) with a 7–14 day quarantine for new versions; lockfiles with hashes; `npm ci --ignore-scripts`; new packages in a lockfile diff need human approval. | M | RV-14 |
| FR-SEC-05 | **Model register**: official publisher source, licence and usage policy, SHA-256, internal mirror, no runtime pulls; model digest recorded in traces and evidence bundles. Platform dependencies pinned by digest and tracked against advisories; all actions pinned by SHA. | M | RV-14 |
| FR-SEC-06 | **Researcher split** into WebResearcher (no internal data; templated queries over approved topics) and InternalDataAnalyst (on-prem DBs; no web). **Taint labels** on KG nodes and Qdrant points; tainted context cannot introduce a dependency, URL, command or scope change without human approval. CI output enters retries only as structured fields. | M | RV-15 |
| FR-SEC-07 | **Hardened direct push**: a dedicated deploy runner on the control side; short-lived SSH certificates or Kubernetes tokens issued only to jobs whose OIDC claims match the site environment and a release tag; forced-command deploy user on Compose hosts; minimal Kubernetes RBAC; client allow-lists the deploy runner's IP; revocation runbook. | M | RV-10 |
| FR-SEC-08 | **G3 promotion attestation** listing the approved digests; the deploy job deploys only those; clients verify signatures and attestation. Every gate package is assembled in an earlier node, stored immutably with a hash, and the resume carries the hash and approver identity (fail closed on mismatch). | M | RV-10 |
| FR-SEC-09 | **Data classes** with allowed destinations; synthetic-only fixtures; PII scan on commits and issue bodies; Issues mirror carries IDs and status only. | M | RV-15 |
| FR-SEC-10 | A **kill switch** that pauses all agents and revokes App, OpenBao and client credentials, rehearsed; platform penetration test before P3b. | M | S-14 |

### 10.4 Reliability and operations (NFR)

| ID | Requirement | Pri | Source |
|---|---|---|---|
| NFR-REL-04 | Per-project **platform BOM** pinned at project start (platform image digest, graph versions, instruction SHA, model and embedding digests); changes are change requests. `flow_version` stamped into graph state; parked checkpoints resume-tested in CI before any rollout. | M | RV-11 |
| NFR-REL-05 | **Fenced leases**: one lease table with an epoch token checked in every checkpoint write and queue transition; heartbeat in a separate thread; self-termination on lost lease; orphan reaping; capped resume attempts with quarantine; `durability="sync"`. | M | RV-11 |
| NFR-REL-06 | **Readiness barrier** before admitting work after restart; **infra vs task failure classification** (infra failures pause and alert, never consume attempts). | M | RV-11 |
| NFR-REL-07 | **State inventory** with per-store backup and restore order; PostgreSQL PITR (minutes RPO); encrypted OpenBao snapshots with escrowed unseal shares; research snapshots stored; post-restore reconciliation with GitHub; quarterly restore drills on other hardware. | M | RV-12 |
| NFR-REL-08 | Node hardware: mirrored NVMe, ECC RAM, dual PSU, UPS; separate volumes with quotas, GC jobs and disk back-pressure (⚠ DN-1). | M | RV-12 |
| NFR-REL-09 | **Deploy state machine** with a recorded deploy intent; a go-live is never auto-retried after a crash; `helm upgrade --atomic`; break-glass rollback from an operator machine. | M | RV-10 |
| NFR-OBS-04 | External heartbeat; alert catalog (no progress with non-empty queue, gate-wait age, lease churn, GPU idle with work queued, disk forecast, backup age, OpenBao sealed, runner offline, GitHub rate-limit headroom); **operator console** with audited inspect / release-lease / quarantine / rewind / cancel; runbooks per alert. | M | RV-13 |
| NFR-OBS-05 | Audit log written by an INSERT-only single writer; chain head anchored per gate/deploy event and at least every minute to off-node WORM storage with an off-node key; secrets redacted before traces and audit. | M | RV-21 |
| NFR-MNT-05 | Platform release process: canary node, drain, forward-only migrations, health-gated re-admission, no upgrades during go-live windows; pinned host image, monthly patch windows; runner-image update pipeline; GitHub writes via an outbox with a rate budget. | M | RV-13 |
| NFR-CAP-06 | Ollama configuration pinned in IaC (one context length and slot count, no CPU offload, alert on offload); role context budgets enforced with a tokenizer, **fail closed, never truncate**; one GPU slot reserved for P0; per-role output/thinking token caps; repetition detector; embeddings on CPU. | M | RV-16 |
| NFR-CAP-07 | CI as a scheduled execution-plane lane: several ephemeral runners, tiered CI (affected tests on PRs, full suites per merge batch, full e2e nightly), persisted caches, wall-clock budgets per tier. | M | RV-05 |
| NFR-USE-03 | Platform UI: OIDC with the customer IdP, phishing-resistant MFA and step-up for gate actions, roles, four-eyes (requester ≠ approver; G3 needs two humans); agent credentials can never call gate endpoints. | M | RV-17 |

### 10.5 Measurement (FR-EVL)

| ID | Requirement | Pri | Source |
|---|---|---|---|
| FR-EVL-04 | Every benchmark project has a **sealed, human-authored hidden acceptance suite** and hidden defect list; the hidden-suite pass rate is the primary metric; mesh-oracle vs hidden-suite agreement is reported. Benchmark gate decisions are never auto-approved. | M | RV-03 |
| FR-EVL-05 | k ≥ 3 repeats on S/M with confidence intervals; baseline = strongest simple alternative at equal GPU budget; ablations per mesh component; sealed held-out projects used only at phase exits. | M | RV-03 |
| FR-EVL-06 | **Human-touch ledger** capturing every project-attributable human minute, including platform-team interventions; escalation budget per tier. | M | RV-07 |
| FR-EVL-07 | Seeded architecture flaws to measure adversarial-review recall and precision; injection red-team cases. | S | RV-27, RV-15 |
