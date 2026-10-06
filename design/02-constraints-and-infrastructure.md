# 02 — Constraints & Infrastructure Assessment

| | |
|---|---|
| **Project** | AI Mesh (working name) |
| **Status** | Draft v2.1 — §10 superseded by review R1 (see update box); updated with customer answers (2026-10-05); items marked ⚠ need confirmation |
| **Date** | 2026-10-05 |
| **Depends on** | [00-idea-assessment.md](00-idea-assessment.md), [01-project-charter.md](01-project-charter.md) |

## 1. Confirmed context (customer input, 2026-10-05)

| ID | Constraint |
|---|---|
| C1 | All inference stays on-prem; no external LLM APIs |
| C2 | Models served by **Ollama**, using open-weights coding models |
| C3 | Host: one **Ubuntu 24.04** server with one **NVIDIA H100 PCIe** (80 GB HBM2e, ~2.0 TB/s, PCIe Gen5 x16, 350 W limit, ECC on; driver 595.58.03, CUDA 13.2 — confirmed 2026-10-05; **dedicated to the mesh** — the ~8 GB of other workloads seen on 2026-10-05 are moved off before bring-up), **AMD EPYC 9124** (16 cores / 32 threads, 1 NUMA node, AVX-512), **124 GB RAM**, **4 TB** disk; **one server per project**, more servers later |
| C4 | A **knowledge graph** and a **vector store** per project |
| C5 | Supporting services run as **Docker** containers |
| C6 | Source control: **private repositories on github.com** |
| C7 | A **sandbox environment** for testing software and testing deployments |
| C8 | Projects are **greenfield** (new software only) |
| C9 | **No historical project data**; measurement and estimation rely on our own heuristics |
| C10 | Agents **may reach the internet**; web research via **Tavily** and **Brave Search**; access to some **on-prem databases** |
| C11 | Typical generated project: **100k–250k LOC**, microservices or modular monolith |
| C12 | **Platform** stack: Python, Go, LangChain/LangGraph, Qdrant, Chroma, FastAPI, SQLAlchemy, Svelte web front end or Tauri client. Generated systems use stacks from the technology catalog |
| C13 | "Production" for generated systems means **go-live** to real users, approved at G3 |

## 2. What changes relative to the idea assessment

1. **Capability ceiling.** The evidence in 00 came from frontier closed models (multi-agent compiler, browser builds). On-prem, capability is capped by what fits on the GPU(s). → Smaller task units, stronger oracles, more verify-and-retry loops, and more conservative autonomy targets.
2. **The binding constraint moves from money to throughput.** There is no per-token bill; the scarce resource is GPU time and wall-clock. → The orchestrator needs a GPU-aware scheduler, and concurrency is designed rather than assumed.
3. **Model diversity costs VRAM.** Reviewing with a *different* model means loading a second model or swapping models. → Batch reviews; get diversity from roles, instructions and executable checks first.
4. **The benchmark must be authored in-house.** No past projects means the reference projects, acceptance oracles and human-effort baselines are built by us. → Phase 1 grows.
5. **"Buy" now means open source.** Commercial SaaS agent platforms are out. The reusable worker layer is open-source agent runtimes that support local models.

## 3. Model capability on a single H100 (80 GB)

### 3.1 Candidates that fit

All figures are vendor- or community-reported, usually measured in full precision with a specific harness. Quantized builds as served by Ollama are not re-measured. Every candidate must be scored on our own benchmark in Phase 1.

| Model | Type | Licence | Fits 1×H100 | Reported coding result | Role fit / notes |
|---|---|---|---|---|---|
| **Qwen3.8-27B** | Dense 27B, 262K context, vision | Apache 2.0 | Yes (FP16 tight; 8-bit comfortable) | 61.7% SWE-bench Pro (model card; Claude Code harness, 256K context) | **Primary candidate** for planner and coder. Hybrid attention (only 16 of 64 layers use full attention) → small KV cache. ⚠ Verify Ollama kernel support and speed for this architecture. |
| **Qwen3.6-27B** | Dense 27B | Apache 2.0 | Yes (FP16 fits) | 77.2% SWE-bench Verified (reported) | Previous-generation fallback |
| **Qwen3.6-35B-A3B** | MoE, ~3B active | Open weights | Yes | OpenHands' first recommended local model (May 2026) | Fast worker for high-volume, well-specified tasks |
| **Devstral Small 2** | Dense 24B | Apache 2.0 (verify) | Yes | 68.0% SWE-bench Verified (vendor) | Built for agentic software engineering |
| **gpt-oss-120b** | MoE 117B / 5.1B active, MXFP4 | Apache 2.0 | Yes (fills most of the card) | Strong reasoning | Candidate planner/reviewer, but cannot co-reside with a 27B model on one card |
| GLM-5.2 (744B MoE), DeepSeek V4 Pro (1.6T MoE), Kimi K3 (2.8T) | Frontier open weights | MIT / modified MIT | **No** — multi-GPU clusters | Top open-weights scores | Out of reach on one H100 |

If the server has more GPUs, options widen materially. DeepSeek V4 Flash (284B MoE, 13B active) is described as bringing near-frontier quality to 2-GPU setups.

### 3.2 Expected capability gap

- One 2026 survey puts self-hostable single-card open coders at roughly 60–72% on SWE-bench Verified, versus 80–95% for frontier cloud coders. The newest 27B models narrow that gap.
- **The harness matters as much as the model.** Qwen3.6-27B scored 67.8% with a minimal agent (mini-swe-agent). An independent researcher reported far higher with a heavily engineered stack.
- Published figures for the same model sometimes disagree between sources. Treat every number as a hypothesis until our harness reproduces it.

**Implication:** the verification-first design (00 §6) matters *more* on-prem. Weaker models need tighter oracles and smaller, independently checkable tasks.

## 4. Serving: Ollama on one H100

### 4.1 Relevant facts

- **Parallelism.** `OLLAMA_NUM_PARALLEL` defaults to 1. Each parallel slot gets its own KV cache sized to the full context, so memory scales with *context × slots*.
- **Resident models.** `OLLAMA_MAX_LOADED_MODELS` caps how many models stay loaded. Alternating between models that don't fit together is the worst pattern: every switch reloads weights.
- **KV-cache quantization.** `OLLAMA_KV_CACHE_TYPE=q8_0` with FlashAttention roughly doubles the feasible context, with negligible quality loss.
- **Throughput under concurrency.** Ollama plateaus where vLLM's continuous batching keeps scaling. In one H100 benchmark with an 8B model at 32 concurrent requests, Ollama delivered ~320 tok/s total versus ~1,450 tok/s for vLLM.
- **API compatibility.** Ollama exposes OpenAI-compatible and (since v0.14, January 2026) Anthropic-compatible APIs. Agent runtimes speaking either dialect can use it.

### 4.2 VRAM budget — worked example (illustrative)

KV cache per token = 2 × (full-attention layers) × (KV heads) × (head dim) × (bytes per element).

For a *standard* GQA 27B-class model (64 layers, 8 KV heads, head dim 128) with an FP16 KV cache:
2 × 64 × 8 × 128 × 2 B = 256 KiB per token. A 128K-token context is then ≈ 32 GiB per slot, or ≈ 16 GiB with a q8_0 KV cache.

| Item | Approx. GB |
|---|---|
| Primary model weights, 8-bit (~27B) | ~29 |
| Embedding model | ~1–2 |
| Runtime overhead / reserve | ~5 |
| **Left for KV cache** | **~44** |

| Context per session (q8_0 KV) | Concurrent sessions, standard architecture | Concurrent sessions, hybrid attention (16/64 full-attention layers) |
|---|---|---|
| 128K | ~2 | ~8–10 (memory-wise) |
| 64K | ~5 | ~16+ (memory-wise) |

With hybrid-attention models, GPU compute will limit throughput before memory does.

**Conclusion:** plan for **a handful (≈2–8) of concurrent long-context agent sessions per H100**, not dozens. The 16-agents-in-parallel pattern from the compiler experiment is not feasible on one GPU. The mesh must be sequenced and scheduled. Real numbers come from the Phase 1 load test.

### 4.3 Recommendations

1. **Keep Ollama for v1**, as specified: simple operations, model management, and both API dialects.
2. **Put an LLM gateway in front of Ollama** (e.g. LiteLLM). It gives one endpoint for all agents, per-role model routing, quotas and budgets, and a full request log for audit. Swapping or adding an inference engine then becomes a configuration change.
3. **Load-test in Phase 1.** Compare Ollama against vLLM/SGLang on the chosen model at realistic agent concurrency, and decide D2b on the result. Note that vLLM needs AWQ, GPTQ or FP8 weights rather than Ollama's GGUF.
4. **Keep one primary model plus the embedding model resident.** Avoid model swapping during runs. Schedule heterogeneous-model reviews as batches.
5. **Build a GPU-aware scheduler into the orchestrator.** It needs priority queues, a per-GPU session cap, a context budget per agent role, and back-pressure when the queue grows.

## 5. Worker runtime options (local-model compatible)

| Runtime | Local-model support | Strengths | Concerns |
|---|---|---|---|
| **OpenHands** (Software Agent SDK, MIT) | Via LiteLLM: Ollama, vLLM, SGLang | Python SDK embeddable in our orchestrator; sandboxed workspaces; MCP tools; model routing | Local-model results are mixed in practice; SDK interface still evolving (V0 deprecated April 2026) |
| **Claude Code** pointed at Ollama's Anthropic-compatible API | Native since Ollama v0.14 | Mature harness (subagents, skills, hooks); Qwen3.8's published scores were measured in this harness | Proprietary licence — confirm the customer may use it with non-Anthropic models; hangs reported with some local Ollama setups |
| **OpenCode** (MIT) | Provider-agnostic, including Ollama | Lightweight, widely adopted | Less proven as an embedded, orchestrated worker |

**Recommendation:** define a **Worker Adapter** interface in the orchestrator. In Phase 1, run a bake-off on the benchmark suite (D3), scoring each runtime on acceptance pass rate, GPU-time per task, controllability (hooks, permissions, structured output) and stability.

## 6. Per-project knowledge graph and vector store

**Division of labour**

- **Knowledge graph = structure and traceability.** It links requirements, use cases, acceptance tests, components, interfaces, ADRs, tasks, commits, test results and agent decisions. This is what makes objective O5 (full traceability) possible.
- **Vector store = semantic retrieval.** It indexes requirements text, domain-research notes, code chunks and documentation.
- **Git remains the source of truth.** The graph and vectors are *derived indexes*, rebuildable from the repository and the run logs. Each embedding carries its embedding-model version, so a model change triggers a re-index rather than silent drift.

**Options**

| Option | Graph | Vectors | Pros | Cons |
|---|---|---|---|---|
| **A** | PostgreSQL + Apache AGE (openCypher) | pgvector | One engine; database-per-project isolation; graph and vectors in one transaction; simple backup and restore | AGE is less feature-rich than dedicated graph databases; vector performance at very large scale |
| **B** | Neo4j | Qdrant | Best-in-class tools for each job | Two engines per project; Neo4j Community is GPLv3 and Enterprise is commercial |
| **C** | Memgraph / Kuzu | Qdrant / Milvus | Lightweight or fast alternatives | More moving parts; smaller ecosystems |

**Recommendation:** Option A for v1, behind a repository interface so engines can change, validated in Phase 1 (D10). Each project gets its own database, created at project start and archived at close.

## 7. Sandboxes, containers and network

- **Agent workspaces:** one ephemeral container per agent task. Non-root, with CPU, memory and disk limits, no access to the host Docker socket, and scoped credentials. Evaluate the gVisor runtime for stronger isolation (D6).
- **Test and deployment sandbox:** separate from agent workspaces. Deployments happen only through the pipeline, never from an agent shell.
- **Network egress (confirmed allowed):** all traffic goes through an allow-listed, logged egress proxy (GitHub, Tavily, Brave, package registries, documentation sites). A local package cache (PyPI, Go module proxy, npm) is still recommended for speed and reproducible builds. See §12.
- **GitHub (confirmed: private repositories on github.com):**
  - Code is hosted by GitHub; it is not sent to any LLM.
  - Use **self-hosted Actions runners** on the server, so builds, tests and sandbox deployments run on-prem.
  - Access GitHub through a **GitHub App** with per-repository, least-privilege permissions, and protect `main`.
  - Implement the G3 release gate with **GitHub Environments and required reviewers**.

## 8. Measurement without historical data

- **Internal benchmark.** 6–10 greenfield reference projects in graded tiers (S / M / L). Each has written requirements, signed-off acceptance tests (the oracle), and an expert estimate of equivalent human effort. The estimate comes from Wideband Delphi with at least three engineers.
- **Held-out subset.** Some projects should be authored by people who do not build the mesh (e.g. customer SMEs), so we don't tune the mesh to our own test.
- **Baselines.**
  1. A single agent using the same local model and runtime, given the same signed-off spec.
  2. The expert human-effort estimate.
- **Estimation heuristic v0.** Size each project from its requirements (use-case points or function points, computed by agents and checked by humans). Map size to forecast agent work (tasks, GPU-hours, wall-clock at current capacity) and human review hours. Report forecasts as ranges and recalibrate after every benchmark run.
- **Core metrics.** Acceptance pass rate; escaped defects (seeded defects plus those found in UAT); human hours; GPU-hours; wall-clock; forecast calibration.

> **Update (v2):** §6 proposed PostgreSQL + AGE + pgvector before the customer named Qdrant and Chroma. The current proposal is in §13: Qdrant as the single vector engine, plus a graph store for the knowledge graph.

## 9. Decisions — status after customer answers

| ID | Decision | Status |
|---|---|---|
| D1 | Hosting & data boundary | **Resolved:** on-prem inference |
| D2 | Model strategy | **Resolved:** local open-weights models via Ollama |
| D2a | Model shortlist and primary model | Phase 1 bake-off (Qwen3.8-27B, Qwen3.6-35B-A3B, Devstral Small 2, gpt-oss-120b) |
| D2b | Serving engine at scale | Ollama for v1; load-test vs vLLM/SGLang in Phase 1 |
| D3 | Worker runtime | Phase 1 bake-off: **LangChain Deep Agents** (fits the LangGraph stack), OpenHands SDK, OpenCode; Claude Code via Ollama optional (licence check) |
| D4 | Orchestration substrate | **Preferred: LangGraph** with a PostgreSQL checkpointer; decide crash recovery (own supervisor vs. Temporal's LangGraph plugin) |
| D5 | GitHub hosting & CI runners | **Resolved:** private repos on github.com; self-hosted runners on the server |
| D6 | Sandbox isolation | Docker confirmed; evaluate gVisor |
| D10 | Knowledge-graph & vector engines | **Resolved roles:** knowledge graph = project knowledge and entity interactions (engine: PostgreSQL + Apache AGE or Neo4j, choose in Phase 1); Qdrant = knowledge base (semantic retrieval); Chroma = optional context/ideas cache |
| D11 | Network egress | **Resolved:** internet allowed via egress proxy; Tavily + Brave for search; local package cache recommended |
| D12 | Capacity model | **Resolved:** one project per server; CPU/RAM allocation in [05 §9.3](05-reference-architecture.md) |
| D13 | Web-research security controls | Proposed in §12 |

## 10. Capacity for 100k–250k LOC projects (order-of-magnitude model)

> **Update (2026-10-05, adversarial review R1 — [07 RV-05](07-adversarial-architecture-review.md)): the estimates below are superseded.** Three corrections:
>
> 1. **Output tokens per line were under-estimated.** §10.1 assumed 100–300 output tokens per final line. The cited compiler experiment actually used 140M output tokens for ~100k lines, about **1,400 per line** (verified). Planning range: 300–1,500 output tokens per accepted line, so **45–225M output tokens** for a 150k-LOC build.
> 2. **The decode ceiling used the H100 SXM figure** (3.35 TB/s). **Confirmed 2026-10-05: the card is an H100 PCIe** (~2.0 TB/s). Single-stream decode ceiling for a dense 27B model:
>    - **8-bit weights (~29 GB):** ~69 tok/s theoretical, ~40–55 tok/s realistic.
>    - **4–6-bit weights (~17–21 GB):** ~95–118 tok/s theoretical.
>
>    On this card, the quantization level and an MoE worker model (~3B active parameters) matter more than on SXM. Both are in the D2a bake-off.
>
>    `nvidia-smi` also shows ~4.9 h of cumulative software power capping at the 350 W limit. Prefill (compute-bound) may throttle under sustained load. Measure it in the Phase 1 load test.
> 3. **Prefix caching is unproven** on the hybrid (Gated-DeltaNet + attention) primary model in llama.cpp-family engines. The cached-prefix ratio becomes a D2b decision metric (Ollama vs vLLM).
>
> **Revised planning range** for a 150k-LOC build on one node: about **1 to 12 weeks of build wall-clock, P50 ~4–6 weeks**.
>
> - Decode: 45–225M tokens at 80–150 tok/s aggregate ≈ 4–33 days.
> - Prefill: 0.6–3.2B input tokens, 30–100% computed, at 2,000–5,000 tok/s ≈ 0.5–18 days.
> - Utilization: ~60%.
>
> This range is replaced in the capability spike by the measured **output tokens per accepted LOC**.
>
> **CI** on a single self-hosted runner is serial (one job at a time) and could add 7–20 days. CI moves to an execution-plane lane with several ephemeral runners and a merge queue.

This model gives orders of magnitude only. Phase 1 replaces every assumption with measurements.

### 10.1 Token volume per project (midpoint: 150k LOC)

| Quantity | Assumption | Result |
|---|---|---|
| Final code, including tests | 150k LOC × ~10 tokens per line | ~1.5M tokens |
| Generated output | 10–30× the final code (rewrites, failed attempts, reasoning, tool calls, docs) | 15–45M tokens |
| Input processed | 30–100× the output (agent loops re-read context every turn) | 0.5–4.5B tokens |
| Prefill actually computed | 20–50% of input after prefix-cache reuse | 0.1–2.2B tokens |

Cross-check: the frontier-model compiler experiment (~100k lines) took ~2,000 agent sessions and ~$20k of API spend. At 2026 frontier prices that corresponds to billions of input tokens — the same order of magnitude.

### 10.2 Throughput on one H100 (Ollama, ~27B dense model, 8-bit weights)

| Phase | Basis | Planning range |
|---|---|---|
| Decode, single stream | Memory-bandwidth bound: ~3.35 TB/s ÷ ~29 GB of weights ≈ 115 tok/s theoretical ceiling | 50–80 tok/s |
| Decode, aggregate (~4 slots) | Ollama batching plateaus early | 150–250 tok/s |
| Prefill | Compute bound | 3,000–6,000 tok/s |

MoE or hybrid-attention models and vLLM/SGLang change these figures materially; all of them will be measured in Phase 1.

### 10.3 GPU time per project

| | Low | High |
|---|---|---|
| Decode | 15M ÷ 250 tok/s ≈ 17 h | 45M ÷ 150 tok/s ≈ 83 h |
| Prefill | 0.1B ÷ 6,000 tok/s ≈ 5 h | 2.2B ÷ 3,000 tok/s ≈ 204 h |
| **Pure GPU time** | **~1 day** | **~12 days** |

At 50–70% utilization (queues, test runs, retries), that is **roughly 2 days to 3+ weeks of build wall-clock per L-tier project on one H100**, excluding time spent waiting at human gates.

### 10.4 Conclusions

1. **Throughput is workable at one active project per server** (a "project lane"): weeks, not months — provided quality holds.
2. **Prefill dominates the high end.** Context discipline is the main throughput lever: small task scopes, retrieval instead of whole files, prefix-stable prompts. vLLM/SGLang prefix caching could cut prefill cost several-fold (D2b).
3. **Capability, not throughput, is the bigger unknown.** There is no public evidence yet of local 27B-class models producing coherent 100k+ LOC systems; the public examples at that scale used frontier models with strong oracles. Mitigations:
   - decompose systems into modules of roughly 5–20k LOC, each with explicit contracts and its own acceptance tests;
   - grow project size tier by tier in the benchmark (S → M → L).
4. **Retrieval is mandatory.** A 150k-LOC codebase is about 1.5M tokens, over ten times any usable context window. The code graph and vector index are core infrastructure, not optional extras.

## 11. Server resource plan (v1: one server, 1×H100, 124 GB RAM, 4 TB disk)

### 11.1 RAM

| Component | RAM (GB) |
|---|---|
| OS, Docker, monitoring | ~8 |
| Ollama host side (runner, page-cache headroom) | 12–20 |
| PostgreSQL (system of record, LangGraph checkpoints, knowledge graph) | 12–16 |
| Qdrant (plus Chroma if kept) | 6–10 |
| Orchestrator, gateway, API, UI, tracing | 6–8 |
| Agent workspaces (3–4 concurrent × 4–6 GB) | 12–24 |
| CI runner plus test/deploy sandbox for a 100k–250k LOC system | 24–40 |
| **Total** | **~80–126** |

This is tight at the top end. Mitigations:

- strict container memory limits, and one deployment sandbox at a time;
- when scaling, move sandboxes and CI runners to a second, CPU-only server, which is cheaper than another GPU server;
- specify ≥ 256 GB RAM for future GPU servers.

Builds and tests are CPU-bound. With the EPYC 9124 (16 cores / 32 threads), the CPU allocation in [05 §9.3](05-reference-architecture.md) gives CI about 8 threads; full test runs of a 100k–250k LOC system should be measured in Phase 1.

### 11.2 Disk (4 TB)

| Item | Estimate |
|---|---|
| Models (4–6 candidates during the bake-off) | 150–350 GB |
| Docker images and build cache | 300–600 GB |
| Package cache (PyPI, Go module proxy, npm) | 100–300 GB |
| Per project: workspaces, artifacts, indexes, logs, checkpoints | 30–100 GB each |
| Telemetry and audit logs | 100–300 GB per year |

This fits v1 with retention policies. Backups must go off the server, because a single server is a single point of failure.

## 12. Internet access and web-research security

Research uses the Tavily and Brave Search APIs plus approved on-prem databases. Three risks come with it:

- **Prompt injection** through retrieved web content.
- **Leakage** of confidential context in search queries.
- **Licence contamination** from code copied off the web.

Controls:

1. The research role has no shell, repository-write or credential-bearing tools.
2. Retrieved content is stored and passed on only as quoted data with provenance.
3. Outbound queries pass a policy filter (no secrets, customer identifiers or internal hostnames), and every query is logged.
4. All egress goes through an allow-listed proxy.
5. On-prem databases are reached through read-only, scoped accounts behind an audited tool layer.
6. Every new dependency gets a licence and vulnerability scan, and no code is copied verbatim from the web without a licence check.

## 13. Stack fit notes

> **Update (2026-10-05):** FlowEngine + NeuroCore were proposed in place of LangGraph, and ArxDB / neurogossip-v3 for the knowledge graph and inter-agent communication. See [04-technology-review-proposed-stack.md](04-technology-review-proposed-stack.md) for the review. **Decision:** none of them are adopted for v1; the stack stays LangGraph, Qdrant and Chroma as described below.

- **LangGraph.** Its persistence layer with a checkpointer gives durable execution, and its interrupts can pause indefinitely for human input — a natural fit for G1, G2 and G3. Caveat: a LangGraph run lives in a single process, so after a crash something must re-invoke it. Temporal's LangGraph plugin adds full durable execution. Choose in Phase 1 between our own orchestrator supervisor and Temporal (D4).
- **LangChain Deep Agents** (MIT, built on LangGraph) is a model-agnostic agent harness. It offers sub-agents, filesystem and sandbox backends, context management and human approval of tool calls, and it works with Ollama and vLLM. That makes it a strong worker candidate aligned with the stack (D3). LangChain's **Open SWE** (MIT) is a useful reference design for internal coding agents.
- **Knowledge services — roles confirmed by the customer (2026-10-05):**
  - **Knowledge graph:** accumulates project knowledge and lets agents reason over entities and their interactions (delivery and domain layers; see 03 FR-KNW-01, FR-KNW-06).
  - **Qdrant:** the knowledge base — semantic retrieval over requirements, documents, research and code, with hits linked to graph nodes.
  - **Chroma (optional):** a cache of important context and ideas. Recommendation: start without it and store the cache as a separate Qdrant collection behind a small memory interface. Add Chroma only if Phase 1 shows a concrete benefit, since every extra engine costs RAM on the 124 GB server (§11.1) and operational effort.
  - Neither vector store is a graph database, so the graph engine is still needed:
  - a graph store for the knowledge graph: PostgreSQL + Apache AGE (reusing the PostgreSQL already needed for SQLAlchemy and checkpoints) or Neo4j.
- **Svelte vs. Tauri** is not either/or: Tauri can wrap a Svelte front end. Build a SvelteKit web UI in v1 and add a Tauri shell later if a desktop client is needed.
- **Go.** Use it where it clearly pays (sandbox manager, scheduler, CLI) and keep the platform core in Python, to avoid splitting the codebase early. ⚠ Confirm whether Go was meant for the platform or for generated services.

## 14. Questions for the customer

1. ~~Stack scope~~ — resolved: the platform itself.
2. ~~Roles of Qdrant and Chroma~~ — resolved 2026-10-05: Qdrant = knowledge base; Chroma = optional context/ideas cache.
3. ~~CPU cores~~ — resolved: EPYC 9124, 16C/32T.
4. ~~One project per server~~ — resolved: yes.
5. ~~Meaning of production~~ — resolved: go-live. Open: the go-live target environment (D18).
6. Which RDBMS should be used (PostgreSQL assumed)?

## Sources

- LangGraph — Durable execution: https://docs.langchain.com/oss/python/langgraph/durable-execution
- LangGraph — Interrupts: https://docs.langchain.com/oss/python/langgraph/interrupts
- Temporal — LangGraph plugin for durable execution: https://temporal.io/blog/temporal-langgraph-plugin-durable-execution
- LangChain Deep Agents (GitHub): https://github.com/langchain-ai/deepagents
- LangChain — Open models have crossed a threshold: https://www.langchain.com/blog/open-models-have-crossed-a-threshold
- Open SWE overview: https://www.mager.co/blog/2026-03-17-open-swe-coding-agents/

- Qwen3.8-27B model card: https://huggingface.co/aarontmaher/Qwen3.8-27B
- Qwen3.8-27B benchmarks overview (regolo.ai): https://regolo.ai/qwen3-8-27b-benchmarks-every-test-where-alibabas-27b-model-beats-claude-opus-4-6-max/
- Qwen3.8-27B NVFP4 card (architecture details): https://huggingface.co/philbert440/Qwen3.8-27B-NVFP4
- Best open-weight coding models to self-host (Digital Applied): https://www.digitalapplied.com/blog/best-open-weight-coding-models-self-host-hardware-match-2026
- Best open-weight coding model 2026 (andrew.ooo): https://andrew.ooo/answers/best-open-weight-coding-model-2026-glm-deepseek-qwen-guide/
- Best open-weight LLMs 2026 (Context Studios): https://www.contextstudios.ai/guides/best-open-weight-llms-2026
- Best open-source LLMs, October 2026 (Thunder Compute): https://www.thundercompute.com/blog/best-open-source-llms
- Top open-weight LLMs 2026 (agyn.io): https://agyn.io/blog/top-open-weight-llms-2026
- Qwen3.6-27B community discussion (harness effect): https://huggingface.co/Qwen/Qwen3.6-27B/discussions/33
- Ollama vs vLLM (Spheron): https://www.spheron.network/blog/ollama-vs-vllm/
- Ollama vs vLLM (Vercel): https://vercel.com/i/ollama-vs-vllm
- Ollama num_parallel and KV cache (DEV): https://dev.to/multigrid/ollamas-numparallel-setting-for-concurrent-requests-386l
- Running multiple models in Ollama (DEV): https://dev.to/multigrid/running-multiple-models-at-once-in-ollama-570g
- Optimizing Ollama performance (KV cache quantization): https://medium.com/@kapildevkhatik2/optimizing-ollama-performance-on-windows-hardware-quantization-parallelism-more-fac04802288e
- Ollama — Claude Code integration: https://docs.ollama.com/integrations/claude-code
- Claude Code issue: hangs with local Ollama backend: https://github.com/anthropics/claude-code/issues/51239
- OpenHands — Run local LLMs: https://docs.openhands.dev/openhands/usage/llms/local-llms
- Best open-source CLI coding agents 2026 (Pinggy): https://pinggy.io/blog/best_open_source_cli_coding_agents/
- LLM gateways for self-hosted models (Maxim): https://www.getmaxim.ai/articles/top-4-llm-gateways-for-self-hosted-models-vllm-sglang-and-ollama-2026/
