# 00 — Idea Assessment: Agentic Mesh for End-to-End Software Delivery

| | |
|---|---|
| **Project** | AI Mesh (working name) — in-house agentic software-delivery platform |
| **Context** | Customer-commissioned in-house build (not a commercial product) |
| **Status** | Draft v1 |
| **Date** | 2026-10-05 |

## 1. The idea as stated

Given business, technical and non-technical requirements as input, a mesh of AI agents should: create a detailed project plan and schedule; estimate effort and cost; identify business use cases; research the domain; design the architecture; review it adversarially, revise and improve it; map requirements to the best-suited tools and technologies; implement and test; deploy and QA; manage source-control commits and revisions; generate technical and business documentation; and follow best software design and implementation practices throughout. The framework is generic and deployed per project, for projects of varying complexity.

## 2. Verdict

**Sound in direction; realistic with reframing.** As of October 2026 most individual stages are technically achievable. Three claims are not realistic as written and should be replaced in the platform requirements:

| As stated | Replace with |
|---|---|
| "Accurately estimate efforts and costs" | Calibrated forecasts (ranges with confidence levels), re-forecast continuously from the platform's own run telemetry |
| "Generic framework for projects of varying complexity" | A narrow v1 (one project class, one stack, greenfield) with a pluggable design that expands through domain packs |
| End-to-end autonomy from requirements to production | Autonomy between three human gates: requirements/acceptance sign-off, architecture sign-off, production release |

## 3. Evidence: what is achievable now

- **Implementation from a clear spec.** Top vendor-reported SWE-bench Pro scores are near 90%, but the benchmark is noisy: an OpenAI audit (July 2026) estimated roughly 30% of the public split is broken, the test harness alone moves scores by 10–20 points, and scores drop on private codebases. Treat benchmark numbers as upper bounds.
- **Long autonomous builds — when a strong oracle exists.**
  - Anthropic: 16 parallel Claude agents built a ~100k-line C compiler in Rust that compiles Linux 6.9 on x86, ARM and RISC-V, over ~2,000 sessions and ~$20k of API cost. There was no orchestrator agent — just a loop, git-based task locks and tests.
  - Cursor: hundreds of agents in a planner / worker / judge hierarchy ran for about a week and produced a 1M+ line browser that, by Cursor's own account, only partly works.
- **Spec-driven pipelines are mainstream tooling.** GitHub Spec Kit and AWS Kiro implement requirements → design → tasks → implementation flows; Kiro uses EARS notation for requirements.
- **Autonomous task length is growing fast.** METR's 50% time horizon for frontier models reached double-digit hours in early 2026, doubling roughly every 4–5 months since 2023.

## 4. Where the idea breaks — and what that implies

### 4.1 The oracle problem (critical)
Every headline success had a near-perfect automatic verifier (GCC as a reference compiler; extensive existing test suites). Business software built from requirements has no such oracle: "correct" lives with stakeholders. Even in the compiler project, a human defined what "correct" meant.

**Implication:** the platform's first job is to *manufacture the oracle* — executable acceptance tests, interface contracts, architecture fitness functions and a validated prototype — and have humans sign it off before implementation starts.

### 4.2 Estimation
Studies find LLMs estimate about as accurately as human developers — not better — and traditional proxies such as story points miss the dominant effort drivers in AI-assisted work, which are oversight and interaction. Agent compute cost is also heavy-tailed.

**Implication:** treat estimation as a forecasting problem fed by telemetry and measured by calibration, not as a one-shot answer.

### 4.3 Role-play multi-agent designs underperform
The 2023-era "virtual software company" pattern (PM, architect, developer and QA agents conversing — MetaGPT, ChatDev) performs poorly: ChatDev reached ~33% correctness on simple programs such as Tic-Tac-Toe, Chess and Sudoku. Berkeley's MAST study of 1,600+ execution traces found failures split roughly 42% specification, 37% inter-agent misalignment and 21% verification, and many multi-agent systems lose to a single strong agent.

What works in 2026: hierarchical planners → workers → judge; state in git and the tracker; workers do not converse with each other; instructions matter more than the harness; too much structure creates fragility.

**Implication:** few, well-specified roles with typed handoffs; prove the mesh beats a single-agent baseline.

### 4.4 Messy, long-running work
METR measured large gaps between clean and messy tasks (≈18 h vs ≈6 h horizons for the same model), and a 50% horizon does not mean tasks of that length can be delegated. Real projects are messy and run for months.

**Implication:** decompose into independently verifiable units; concentrate human review where messiness concentrates (requirements, integration, data migration).

### 4.5 Autonomous deployment and source control
Industry reporting in 2026 attributes ~10% of disclosed outages to AI and documents multiple cases of agents taking destructive actions against production systems on their own.

**Implication:** least-privilege permission tiers, sandboxed execution, a human-gated production release and a complete audit trail.

### 4.6 Spec drift
Even spec-first tools generate requirements and design upfront and do not keep them in sync when implementation uncovers new constraints.

**Implication:** a living requirement ↔ test ↔ code ↔ decision traceability loop is a core platform capability.

### 4.7 "Always follow best practices"
This cannot be asserted as a property of a language model. It must be enforced: linters, static analysis, architecture tests, security scanning, dependency and licence policy, review checklists — all as gates in CI.

## 5. Build vs buy (in-house context)

Commercial platforms already cover parts of this scope: Factory's "software factories" with multi-agent Missions (raised $200M at a $5B valuation in September 2026), Cognition/Devin, Cursor background agents, Claude Code agent teams, OpenAI Codex, AWS Kiro. An in-house build is justified when the customer needs one or more of:

- control of code, requirements and IP (data residency, private or sovereign hosting);
- model independence (switch providers; mix frontier and open-weights models);
- the customer's own SDLC, standards, architecture rules and compliance encoded as first-class policy;
- auditability of every agent action and decision;
- cost control at scale.

**Recommendation:** build the **orchestration, verification, governance and knowledge** layers in-house; **adopt** existing coding-agent runtimes (e.g. Claude Agent SDK / Claude Code, Codex, OpenHands) and models as pluggable workers behind an adapter. Rebuilding a coding agent is where the money would go and where in-house work adds the least value.

> **Update 2026-10-05 — on-prem constraint.** The customer confirmed that all inference stays on-prem (Ollama + open-weights coding models on H100). Commercial SaaS platforms and external model APIs are therefore out of scope. The recommendation stands, with the reusable worker layer limited to open-source or locally runnable agent runtimes. The evidence in §3 came from frontier closed models; expect a capability gap on local models. See [02-constraints-and-infrastructure.md](02-constraints-and-infrastructure.md).

## 6. Reframed thesis

> **A verification-first agent mesh.** Before writing code, the mesh produces the artifacts that define "done" — acceptance tests derived from requirements, interface contracts, architecture fitness functions and a validated prototype — and humans sign them off. Worker agents then iterate against those oracles, the way the compiler agents iterated against GCC. Humans own three gates; everything between them is autonomous, traced and measured.

## 7. Kill / simplify criterion

Run the mesh and a single strong agent on the same signed-off spec. If the mesh does not win on escaped defects, total cost and human hours per delivered feature, simplify the mesh.

## Sources

- Anthropic — Building a C compiler with a team of parallel Claudes: https://www.anthropic.com/engineering/building-c-compiler
- Cemri et al. — Why Do Multi-Agent LLM Systems Fail? (MAST): https://arxiv.org/pdf/2503.13657
- METR — Frontier Risk Report (Feb–Mar 2026): https://metr.org/blog/2026-05-19-frontier-risk-report/
- METR — Clarifying limitations of time horizon: https://metr.org/notes/2026-01-22-time-horizon-limitations/
- METR — Time Horizon 1.1: https://metr.org/blog/2026-1-29-time-horizon-1-1/
- The Decoder — Cursor's agent swarm: https://the-decoder.com/cursors-agent-swarm-tackles-one-of-softwares-hardest-problems-and-delivers-a-working-browser/
- Factory — From coding agents to software factories: https://factory.com/news/software-factory
- BenchLM — SWE-bench Pro leaderboard: https://benchlm.ai/benchmarks/swe-bench-pro
- Digital Applied — SWE-bench benchmarks vs scaffolding: https://www.digitalapplied.com/blog/swe-bench-verified-june-2026-benchmark-vs-scaffolding-analysis
- Villarrubia et al. — LLMs for agile effort estimation: https://link.springer.com/article/10.1007/s00766-026-00463-y
- Hybrid intelligence effort for software effort estimation: https://link.springer.com/article/10.1007/s10791-026-10331-6
- SiliconANGLE — StackGen Autonomous Operations Factory: https://siliconangle.com/2026/09/15/stackgen-launches-autonomous-operations-factory-to-govern-production-agents/
- TechTimes — Kiro at AWS Summit New York 2026: https://www.techtimes.com/articles/318546/20260617/aws-summit-new-york-2026-kiro-brings-aerospace-spec-standards-ai-coding.htm
