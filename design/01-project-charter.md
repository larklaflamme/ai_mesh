# 01 — Project Charter & Planning Baseline

| | |
|---|---|
| **Project** | AI Mesh (working name) |
| **Sponsor** | Customer (in-house platform) |
| **Status** | Draft v9 — items marked ⚠ are assumptions pending customer confirmation |
| **Date** | 2026-10-05 (v1: baseline · v2: on-prem constraints · v3: server, GitHub, internet, project size, stack · v4: foundation stack review · v5: stack decision — LangGraph, Qdrant, Chroma · v6: CPU, one server per project, go-live, platform stack · v7: Python/FastAPI for generated systems; client-site go-live · v8: Svelte front end, SQL-agnostic/PostgreSQL, pilot direct push · v9: adversarial review R1 — [07](07-adversarial-architecture-review.md)) |
| **Depends on** | [00-idea-assessment.md](00-idea-assessment.md), [02-constraints-and-infrastructure.md](02-constraints-and-infrastructure.md), [03-platform-requirements.md](03-platform-requirements.md) |

## 1. Purpose

Build an in-house platform that deploys a mesh of AI agents per software project and takes business, technical and non-technical requirements through planning, design, implementation, testing, deployment, QA and documentation — with humans owning the decisions that define "correct" and "safe to release".

## 2. Confirmed context

Customer input, 2026-10-05. Details and implications are in [02](02-constraints-and-infrastructure.md).

- **Inference on-prem:** Ollama serving open-weights coding models.
- **Server:** one Ubuntu 24.04 server with one H100 **PCIe** (80 GB), an AMD EPYC 9124 CPU (16 cores / 32 threads), 124 GB RAM and 4 TB disk. **One server per project** in v1; more servers are added for more projects.
- **Knowledge services:** a knowledge graph and a vector store per project; supporting services run in Docker containers.
- **Source control:** private repositories on github.com, plus a sandbox environment for testing software and deployments.
- **Network:** agents may use the internet. Web research goes through Tavily and Brave Search, and agents can access some on-prem databases.
- **Generated projects:** greenfield, typically **100k–250k LOC**, as microservices or a modular monolith.
- **Platform stack** (applies to the platform itself, not to the systems it builds): Python, Go, LangChain/LangGraph, Qdrant, Chroma, FastAPI, SQLAlchemy, Svelte web front end or Tauri client.
- **Production = go-live:** G3 approves the go-live of the generated system for real users.
- **Knowledge services:** a per-project knowledge graph that accumulates project knowledge and supports reasoning over entities and their interactions; Qdrant as the knowledge base; Chroma optionally as a cache of important context and ideas.
- **No historical project data:** measurement relies on our own heuristics and an internally built benchmark.

## 3. Vision

Delivery teams describe *what* is needed. The platform turns that into a signed-off, executable definition of done, then delivers working, tested and documented software against it — on the customer's own infrastructure, with every decision traceable and every forecast calibrated.

## 4. Objectives (v1)

Targets are initial proposals, to be confirmed in Phase 0.

| # | Objective | Proposed target |
|---|---|---|
| O1 | Deliver benchmark and pilot projects that meet their requirements, judged independently | **Primary metric: pass rate on a sealed, human-authored hidden acceptance suite** the mesh never sees. Release bar: 100% of critical/high-priority requirements pass; any other failure needs a signed waiver; 0 critical escaped defects within a 30-day hypercare window (severity scale defined in P0) |
| O2 | Reduce human effort per delivered feature | ≥ 50% fewer human hours than the human baseline, counting **all** project-attributable human time from the human-touch ledger (gates, reviews, escalations, clarifications, UAT, onboarding, platform-team interventions). The Delphi baseline is calibrated by at least one real human-team S-tier project |
| O3 | Outperform the strongest simple alternative | Mesh vs a single-agent loop with the same oracle, CI, task list and GPU budget: **never worse on escaped defects**, and better on at least two of {hidden-suite pass, human hours, GPU-hours}, with confidence intervals from ≥ 3 runs. Ablations justify each mesh component |
| O4 | Calibrated forecasts | Calibration measured at **task level** (thousands of samples) and rolled up to modules/projects by Monte Carlo; scored with interval scores; calibration windows version-stamped per platform BOM |
| O5 | Full traceability | Every requirement ↔ test ↔ code change ↔ agent decision ↔ release linked in the project knowledge graph |
| O6 | Safe operation | 0 unapproved go-live changes; every approval bound to a content hash; all agent actions within their permission tier; agents never touch protected paths |
| O7 | Operate within on-prem capacity | One project per server. Planning range for a 150k-LOC build on one node: ~1–12 weeks (P50 ~4–6 weeks, [02 §10](02-constraints-and-infrastructure.md)); the numeric target is set from **measured output tokens per accepted LOC** at the end of the capability spike |

Pass / pivot / kill thresholds for each phase are in [07 §4.2](07-adversarial-architecture-review.md) (⚠ values to confirm with the customer, DN-2).

## 5. Scope

### In scope (v1)

- Greenfield projects in **one** project class, sized **100k–250k LOC**, built as a modular monolith (default) or microservices, on the v1 reference stack for generated systems: **Python / FastAPI** backend and **SvelteKit** front end, SQL-engine agnostic with **PostgreSQL** as the v1 engine ([06](06-generated-system-baseline-and-release.md)).
- Go-live into **clients' data centres and client sites**, on **Docker Compose hosts and Kubernetes**, via direct push, GitOps pull or an offline bundle ([06 §6](06-generated-system-baseline-and-release.md)).
- A benchmark in size tiers: **S** (~10–20k LOC), **M** (~40–60k LOC), **L** (≥ 100k LOC).
- The lifecycle stages in §7 at the autonomy levels shown.
- The on-prem inference stack: Ollama, LLM gateway, GPU-aware scheduling.
- Per-project knowledge graph, vector collections and code graph.
- Web research via Tavily and Brave; read-only access to approved on-prem databases.
- GitHub integration (private repositories, PRs, Issues/Projects, Actions on self-hosted runners) and the sandbox environment.
- Governance: permission tiers, sandboxes, audit log, egress proxy, capacity controls.

### Out of scope (v1)

- External LLM APIs or cloud-hosted inference.
- Brownfield / legacy codebases.
- Projects larger than 250k LOC.
- Production releases without human approval.
- Building a proprietary coding-agent runtime; training or fine-tuning foundation models (fine-tuning can be revisited after v1).
- Mobile, embedded, safety-critical or certification-regulated software.

## 6. Guiding principles

1. **Verification first.** No implementation task starts without an executable oracle (acceptance tests, contracts, fitness functions). This matters even more with local models.
2. **Humans own the oracle and the release.** Three gates: **G1** requirements & acceptance criteria, **G2** architecture, **G3** production release.
3. **Build the mesh, reuse the workers.** Orchestration, verification, governance and knowledge are built in-house. Open-source agent runtimes that support local models are pluggable workers behind an adapter.
4. **Model- and engine-agnostic.** All inference goes through an LLM gateway: Ollama today, swappable tomorrow. Models are routed per role.
5. **Git is the source of truth.** Specs, plans, ADRs, tests, code and task state live in version control. The knowledge graph and vector store are derived, rebuildable indexes.
6. **Decompose to fit.** 100k–250k LOC systems are built as modules of roughly 5–20k LOC with explicit contracts and their own acceptance tests. No agent ever needs the whole system in context.
7. **Few roles, typed handoffs.** Hierarchical planner → worker → judge. Workers do not converse with each other; handoffs are structured artifacts.
8. **Capacity-aware.** GPU time is the scarce resource. The scheduler queues, prioritizes and caps concurrent sessions; context discipline is a first-class design concern.
9. **Enforce, don't hope.** Best practices are CI gates and policies, not prompt instructions alone.
10. **Least privilege, sandboxed, audited.** Agents act in ephemeral, isolated containers with scoped credentials. Untrusted content (web pages, issues, documents) never grants permissions, and every action is logged.
11. **Measure everything.** Every claim about the mesh is tested against baselines in the evaluation harness.

## 7. Capability map and target autonomy

Autonomy levels: **A** = autonomous · **G** = autonomous up to a human gate · **H** = human-led, agent-assisted.

| Lifecycle stage | In v1 | v1 autonomy | Key risk |
|---|---|---|---|
| Requirements intake & clarification | ✓ | G (G1) | Ambiguity; missing stakeholder intent |
| Business use case identification | ✓ | G (G1) | Plausible but wrong use cases |
| Domain research (Tavily, Brave, on-prem databases) | ✓ | A (cited; reviewed at G1) | Hallucinated or stale facts; prompt injection; query leakage |
| Acceptance criteria → executable tests (the oracle) | ✓ | G (G1) | Tests that encode a misunderstanding |
| Architecture design, module decomposition & ADRs | ✓ | G (G2) | Over-engineering; modules too large for agents |
| Adversarial architecture review | ✓ | A (findings go to G2); a second model in batched runs | Shared blind spots between same-model agents |
| Technology mapping & selection | ✓ (approved catalog only) | G (G2) | Unvetted dependencies; licensing |
| Project plan, schedule, work breakdown | ✓ | A | Plan drifts from reality |
| Effort, cost & GPU-time forecasting | ✓ | A (ranges) | Poor calibration before enough runs |
| Implementation | ✓ | A | Spec drift; regressions; local-model capability at L-tier scale |
| Code review | ✓ | A + sampled human review | Reviewer blind spots |
| Testing (unit, integration, end-to-end) | ✓ | A | Weak or tautological tests |
| Source control (branches, commits, PRs, merges) | ✓ | A (merge to main gated by CI) | Conflicts; noisy history |
| Deployment to the sandbox environment | ✓ | A | Environment drift; RAM pressure on the shared server |
| Production release | ✓ | H (G3, via GitHub Environments) | Outages; destructive actions |
| QA & exploratory testing | ✓ | A + human UAT | Missed UX or business issues |
| Technical & business documentation | ✓ | A (reviewed at G3) | Docs diverge from code |
| Progress tracking & reporting | ✓ | A | Misleading status |

## 8. Phased roadmap

Durations are **preliminary ranges**, assuming a dedicated core team (§9). They will be re-forecast at the end of Phase 0.

| Phase | Goal | Key outputs | Duration |
|---|---|---|---|
| **0. Discovery & foundations** | Pin down context, security architecture, legal and economics; bring up the stack | Server set-up with **control/execution plane split** (execution on a CPU companion server or microVMs), network zones, internal package proxy, model register; Ollama + gateway; threat model and security decisions (GitHub App split, OIDC → OpenBao, UI auth); legal deliverables (contract template, licence process); TCO model; budget, hiring plan, SME hours; **WBS + re-forecast (go/no-go)** | 4–6 weeks |
| **0/1. Capability spike** (new) | Test the riskiest hypothesis first | Loop + git + tests with one model and one off-the-shelf harness, on one M-tier spec and a 2–3-module L-tier slice with contracts. Measures output tokens per accepted LOC, cached-prefix ratio, escalations, hidden-suite pass rate. **Pass / pivot / kill gate** | 6–8 weeks (overlaps P1) |
| **1. Benchmark, harness & baselines** | Measure honestly before building the mesh | 2 S + 2 M + 1 L-slice reference projects with **sealed hidden suites** and mutation-validated oracles; harness with k ≥ 3 repeats; bake-offs on a 100–300-task micro-benchmark; explicit GPU-hour budget; strongest-simple-alternative baseline | 8–10 weeks |
| **2. Verification-first core (MVP)** | Requirements → oracle → binding → foundation → build loop | LangGraph orchestrator with scheduler, fencing leases and versioned threads; G1, G2, **G2b (oracle binding)**; Foundation stage; integration milestones; merge queue and scope leases; protected-path manifest; acceptance ratchet; change-request flow; traceability; human-touch ledger. **S- and M-tier delivered end-to-end; L-tier probe by month 4–5** | 3–4 months |
| **3a. L-tier build (internal target)** | Prove L-tier delivery without real-user exposure | Deployment, QA, documentation agents; G3 with promotion attestation; Hypercare/Maintenance states; L-tier (≥ 100k LOC) build delivered to an internal or friendly target | 2–3 months |
| **3b. Client go-live** | First real-user go-live | Hardened release; named engineering owner; security sign-off; platform penetration test passed; direct push to the pilot client (D21) | 1–2 months |
| **4. Expansion** | Broaden scope and capacity | Projects up to 250k LOC; more nodes; GitOps and other delivery modes as needed; GPU time-sharing; second SQL engine; forecast calibration from accumulated runs | Ongoing |

Indicative time to a completed client go-live: **~11–14 months**, subject to the capability-spike gate (~month 3). The main schedule risk remains local-model capability at L-tier scale; it is now tested first.

### Phase exit criteria

Numeric pass / pivot / kill thresholds: [07 §4.2](07-adversarial-architecture-review.md) (⚠ DN-2).

- **P0 → P1:** security architecture decided and in place (plane split, zones, App split); legal set and TCO done; WBS + re-forecast approved.
- **Capability spike:** pass / pivot / kill on hidden-suite pass rate, escalations and GPU budget.
- **P1 → P2:** harness reproduces the baseline within ±5 pp over 3 repeats; primary model, worker runtime and serving engine selected on micro-benchmark data.
- **P2 → P3a:** mesh meets absolute hidden-suite thresholds on M, is never worse than the baseline on escaped defects, and beats it on two of {hidden pass, human hours, GPU-hours} with CIs; L-tier probe shows no superlinear escalation growth.
- **P3a → P3b:** L-tier build passes 100% of critical/high requirements on the hidden suite; erosion metrics within budget; security sign-off.
- **P3b → P4:** client go-live completed; 30-day hypercare without critical defects.

## 9. Team (indicative)

| Role | FTE | Responsibilities |
|---|---|---|
| Product owner (customer) | 0.5 | Priorities, gate decisions, acceptance |
| Technical lead / architect | 1 | Platform architecture, ADRs, technical direction |
| Platform engineers | 2–3 | Orchestrator, scheduler, GitHub and sandbox integrations, knowledge services, UI |
| Agent / LLM engineers | 2 | Agent roles, instructions and skills, worker adapters, context management, model routing |
| Inference / MLOps engineer | 1 | Ollama and gateway, model evaluation, quantization, GPU capacity planning, load tests |
| Evaluation & QA engineer | 1 | Benchmark authoring, harness, metrics, seeded-defect testing |
| DevOps / security engineer | 1 | Server, sandboxes, egress proxy, permissions, secrets, audit, backups |
| Front-end engineer | 1 | Platform UI; SvelteKit template, UI contract and e2e conventions for generated systems |
| Delivery manager | 0.5 | Plan, WBS, demos, SME scheduling, stage-gate reporting |
| Reviewers (engineering) | 1–2 (or named customer commitment) | G1 golden scenarios and sampling, PR sampling, escalations; named engineering owner at G3 ([07 RV-07](07-adversarial-architecture-review.md)) |
| Domain SMEs (customer) | Committed hours per phase (⚠ DN-6) | Hidden suites and held-out projects, golden scenarios, clarifications, UAT |
| Legal / procurement (customer) | As needed in P0 | Contract template, licences, DPA |

## 10. Cost drivers

- **People** — the dominant cost.
- **GPU capacity** — no per-token spend. Capacity scales by adding servers ("project lanes").
- **Server resources** — 124 GB RAM is tight for inference, CI and sandboxes together ([02 §11](02-constraints-and-infrastructure.md)). A second, CPU-only server for CI runners and sandboxes is a likely early, low-cost addition. Specify ≥ 256 GB RAM for future GPU servers.
- **External services** — Tavily and Brave Search API usage; GitHub plan (private repos, Actions on self-hosted runners).
- **Tooling & licences** — observability and any commercial components.

A budget estimate (as ranges) follows the Phase 0 confirmations.

## 11. Key decisions (ADR candidates)

| ID | Decision | Status / options | Needed by |
|---|---|---|---|
| D1 | Hosting & data boundary | **Resolved:** on-prem inference | — |
| D2 | Model strategy | **Resolved:** local open-weights models via Ollama | — |
| D2a | Primary model & shortlist | Bake-off: Qwen3.8-27B, Qwen3.6-35B-A3B, Devstral Small 2, gpt-oss-120b | Phase 1 |
| D2b | Serving engine at scale | Ollama for v1; load-test vs vLLM/SGLang behind the gateway | Phase 1 |
| D3 | Worker runtime | Bake-off: LangChain Deep Agents / OpenHands SDK / OpenCode; Claude Code via Ollama optional (licence check) | Phase 1 |
| D4 | Orchestration substrate | **Resolved: LangGraph** with a PostgreSQL checkpointer; crash recovery via own supervisor vs Temporal's LangGraph plugin to be decided in Phase 1. FlowEngine/NeuroCore reviewed and not adopted for v1 ([04](04-technology-review-proposed-stack.md)) | Phase 1 (recovery approach) |
| D5 | GitHub hosting & CI runners | **Resolved:** private repos on github.com; self-hosted runners; GitHub App; Environments for G3 | — |
| D6 | Sandbox isolation | Docker confirmed; evaluate gVisor | Phase 1 |
| D7 | Spec & oracle formats | EARS requirements; Gherkin/BDD; OpenAPI contracts; architecture fitness functions | Phase 1 |
| D8 | v1 stack for generated systems | **Resolved:** Python / FastAPI backend, SvelteKit front end, SQL-engine agnostic with PostgreSQL as the v1 engine; catalog in [06 §2](06-generated-system-baseline-and-release.md) | — |
| D9 | Platform architecture style | **Proposed:** modular monolith in Python; Go where it clearly pays | Phase 1 |
| D10 | Knowledge services | **Roles resolved:** knowledge graph for project knowledge and entity interactions (engine: PostgreSQL + Apache AGE vs Neo4j — Phase 1); **Qdrant** knowledge base; **Chroma** optional context/ideas cache, added only if Phase 1 shows a benefit | Phase 1 (graph engine) |
| D11 | Network egress | **Resolved:** internet via an allow-listed egress proxy; Tavily + Brave; local package cache | — |
| D12 | Capacity model | **Resolved:** one project per server (single-tenant project node); scale by adding servers, with an optional CPU companion server for CI/sandboxes | — |
| D19 | Front end for generated systems | **Resolved:** SvelteKit ([06 §2.1a](06-generated-system-baseline-and-release.md)) | — |
| D20 | SQL engine for generated systems | **Resolved:** engine-agnostic by design, PostgreSQL only in v1 ([06 §2.4](06-generated-system-baseline-and-release.md)) | — |
| D21 | Pilot delivery mode | **Resolved:** direct push to the pilot client, hardened per [07 RV-10](07-adversarial-architecture-review.md) | — |
| D22 | Control/execution plane split | **Proposed:** CI, sandbox and workspaces on a CPU companion server (or microVMs); ephemeral JIT runners; network zones ([07 RV-01](07-adversarial-architecture-review.md), ⚠ DN-1) | Phase 0 |
| D23 | Verification integrity | **Proposed:** protected-path manifest; platform-owned pinned workflows; App without `workflows`; judge runs oracle from pinned checkout; hidden held-out scenarios ([07 RV-02](07-adversarial-architecture-review.md)) | Phase 1 |
| D24 | Oracle in two stages | **Proposed:** G1 = Gherkin + example tables; Oracle Binding stage + G2b after G2 ([07 RV-06](07-adversarial-architecture-review.md)) | Phase 1 |
| D25 | Release integrity | **Proposed:** gate packages hashed; G3 promotion attestation of approved digests; dedicated deploy runner with short-lived credentials ([07 RV-10](07-adversarial-architecture-review.md)) | Phase 1 |
| D26 | GitHub plan | **Proposed:** GitHub Enterprise (required reviewers, rulesets, required workflows on private repos) (⚠ DN-5) | Phase 0 |
| D27 | Supply chain & model provenance | **Proposed:** internal package proxy with allow-list and quarantine; model register with official sources and digests ([07 RV-14](07-adversarial-architecture-review.md)) | Phase 0 |
| D28 | Platform UI authentication | **Proposed:** OIDC with the customer IdP, MFA, four-eyes rules ([07 RV-17](07-adversarial-architecture-review.md)) | Phase 0 |
| D18 | Go-live target & delivery | **Resolved:** clients' data centres and client sites, on Docker Compose and Kubernetes; offline bundle for every release + direct push; **pilot client: direct push**; GitOps pull when a client needs it ([06 §6](06-generated-system-baseline-and-release.md)) | — |
| D13 | Web-research security controls | Proposed in [02 §12](02-constraints-and-infrastructure.md) | Phase 1 |
| D14 | Observability stack | Self-hosted tracing (Langfuse vs self-hosted LangSmith); Prometheus + Grafana | Phase 1 |
| D15 | Agent framework & role skills | **Resolved: LangChain/LangGraph**; agent roles built in-house, fail-closed, with schema-validated outputs | — |
| D16 | Audit / evidence ledger | **Resolved for v1:** append-only, tamper-evident audit table in PostgreSQL | — |
| D17 | Inter-agent communication | **Proposed:** typed handoffs + durable PostgreSQL task queue + event channel | Phase 1 |

## 12. Top risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Local models cannot keep 100k–250k LOC systems coherent | High | High | Module decomposition with contracts; per-module oracles; tiered benchmark (S → M → L); retrieval-based context; human gating where weak; re-evaluate as new open models ship |
| GPU throughput bottleneck (Ollama serialization, KV-cache limits, prefill-heavy agent loops) | High | High | GPU-aware scheduler; context discipline; KV-cache quantization; gateway for an engine swap to vLLM/SGLang; additional servers |
| RAM contention on the single 124 GB server | High | Medium | Container memory limits; one deployment sandbox at a time; second CPU-only server for CI/sandboxes |
| Requirements too ambiguous to produce a reliable oracle | High | High | G1 gate with SMEs; prototype validation; clarification agent with an explicit question budget |
| Prompt injection via web content, or data leakage via search queries | Medium | High | Tool-less research role; content passed as data; query policy filter; egress proxy; audit log |
| Mesh does not beat the single-agent baseline | Medium | High | Harness first (Phase 1); simplify criterion; few roles |
| Benchmark bias (authored by the team that builds the mesh) | Medium | Medium | Held-out projects authored by customer SMEs; rotate new projects into the suite |
| Scope creep toward "generic for any complexity" | High | High | Narrow v1 class; domain packs later; charter-level change control |
| Single server is a single point of failure | Medium | High | Off-box backups; GitHub as code source of truth; rebuildable indexes; documented restore |
| New model architectures poorly supported or slow in Ollama | Medium | Medium | Verify support during the bake-off; fallback model; engine-agnostic gateway |
| Agent takes destructive action in shared environments | Medium | High | Ephemeral sandboxes; permission tiers; G3; audit log; dry runs |
| Code quality and security debt in generated code | Medium | High | CI gates (SAST, dependency/licence policy, architecture tests); sampled human review |
| Stakeholders expect "fully autonomous" delivery | High | Medium | Gates stated explicitly; demos show the gates |
| Agent-written code compromises the node (CI, tests, dependencies) | Medium | Critical | Control/execution plane split; JIT runners; no docker.sock; network zones; package proxy ([07 RV-01, RV-14](07-adversarial-architecture-review.md)) |
| Agents game the oracle (edit workflows, configs, fixtures; special-case code) | High | High | Protected-path manifest; pinned platform workflows; hidden scenarios; test-count manifest ([07 RV-02](07-adversarial-architecture-review.md)) |
| Self-graded success hides real quality | High | High | Sealed hidden suites; absolute thresholds; k ≥ 3 repeats ([07 RV-03](07-adversarial-architecture-review.md)) |
| Human review load overwhelms reviewers; G1 rubber-stamped | High | High | Risk-tiered G1 with golden scenarios and sampling; human-touch ledger; reviewer capacity ([07 RV-07](07-adversarial-architecture-review.md)) |
| Design erosion across hundreds of small tasks | High | High | Foundation stage; integration milestones; refactor tasks; merge queue; scope leases ([07 RV-08](07-adversarial-architecture-review.md)) |
| Throughput lower than planned (output-heavy generation, PCIe GPU, serial CI) | High | High | Re-based estimates; measured output tokens per LOC; CI lane on the execution plane; vLLM option ([07 RV-05](07-adversarial-architecture-review.md)) |
| No post-go-live support path for delivered systems | High | High | Change Request flow; Hypercare/Maintenance states; central signing and SBOM CVE monitoring ([07 RV-09](07-adversarial-architecture-review.md)) |
| Legal/contractual blockers at client sites (IP, liability, DPA, model licences) | Medium | High | P0 legal deliverables and model register ([07 RV-23](07-adversarial-architecture-review.md)) |

## 13. Open questions for the customer

**Resolved 2026-10-05:**
- platform stack scope (the platform itself); CPU (EPYC 9124, 16C/32T); one server per project; production = go-live;
- generated systems: Python / FastAPI + SvelteKit; SQL-engine agnostic, PostgreSQL focus; go-live at clients' data centres and client sites on Docker Compose and Kubernetes; pilot client reached directly (direct push);
- client registries and identity providers: unknown — handled per client by a site profile ([06 §9](06-generated-system-baseline-and-release.md));
- project type (greenfield) and size (100k–250k LOC);
- hosting and data boundary (on-prem inference), model serving (Ollama);
- server (1×H100, 124 GB RAM, 4 TB disk; more servers later);
- GitHub (private repos on github.com), internet access (Tavily, Brave, on-prem databases);
- preferred stack; historical data (none available).

**Open:**

1. **DN-1** Execution-plane hardware (CPU companion server per node) and node resilience spec (mirrored NVMe, ECC, dual PSU, UPS, spare node).
2. **DN-2** Stage-gated funding thresholds ([07 §4.2](07-adversarial-architecture-review.md)).
3. **DN-3** MoSCoW re-baseline ([07 §4.3](07-adversarial-architecture-review.md)).
4. **DN-4** Benchmark staging: S-tier API-only, UI from M-tier.
5. **DN-5** GitHub Enterprise.
6. **DN-6** Budget envelope, hiring plan, SME hours per phase; who the platform's users are.
7. **DN-7** Pilot split into P3a (internal L-tier) and P3b (client go-live).
8. **DN-8** GPU economics: accept low utilization per project in v1; time-sharing in P4.
9. ~~DN-9 GPU form factor~~ — resolved: **H100 PCIe**. ~~DN-10~~ resolved: the GPU is **dedicated to the mesh**; existing GPU workloads are moved off before Phase 0 bring-up.
10. Pilot client's site profile ([06 §9](06-generated-system-baseline-and-release.md)); notification channel; compliance regimes and audit retention.

## 14. Planned design artifacts

| # | Artifact | Phase |
|---|---|---|
| 00 | Idea assessment | Done |
| 01 | Project charter & planning baseline | This document (v9) |
| 02 | Constraints & infrastructure assessment | Done (v2) |
| 03 | Platform requirements (functional & non-functional) | Done (v1) |
| 04 | Technology review: proposed foundation stack | Done (v1; not adopted for v1) |
| 05 | Reference architecture (conceptual) | Done (v1.2) |
| 06 | Generated-system baseline (v1) and release & go-live model | Done (v1.2) |
| 07 | Adversarial architecture review (round 1) | Done (v1) |
| 08 | Prototype plan: structure, phases, tests, measurements | Done (v1) |
| 09 | Implementation guide for Claude Code (handoff: bootstrap, tunnel, contracts, test strategy, phases 0–5, human checkpoints) | Done (v1) |
| 10 | Evaluation harness & benchmark design | 1 |
| 11 | Agent roles, handoff contracts & protocols | 1–2 |
| 12 | Verification & oracle pipeline design | 1–2 |
| 13 | Governance, security & permission model | 0 (security decisions are a P0 exit criterion) |
| 14 | Estimation & forecasting model | 2 |
| 15 | Delivery plan & work breakdown for Phases 0–2 | 0 |
