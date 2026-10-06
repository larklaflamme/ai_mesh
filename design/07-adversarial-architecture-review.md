# 07 — Adversarial Architecture Review (Round 1)

| | |
|---|---|
| **Project** | AI Mesh (working name) |
| **Status** | v1 — findings triaged; accepted changes applied to 01, 02, 03, 05, 06; items in §5 await customer decisions |
| **Date** | 2026-10-05 |
| **Reviewed** | [00](00-idea-assessment.md)–[06](06-generated-system-baseline-and-release.md) as of 2026-10-05 (charter v8, architecture v1.1, baseline v1.1) |

## 1. Method

Five independent reviewers each read the design documents cold, with one adversarial lens. None had seen the conversation that produced the design.

| Lens | Prefix | Findings |
|---|---|---|
| Security, trust boundaries, abuse cases | S | 14 |
| Reliability, durability, day-2 operations | R | 13 |
| Capacity, throughput, performance | P | 12 |
| Agent effectiveness and verification honesty | V | 14 |
| Delivery feasibility, scope, economics, legal | D | 14 |

The 67 findings were de-duplicated into **30 themes** (RV-01…RV-30). Each theme was checked against the documents and given a disposition:

- **Accept** — change applied;
- **Accept, modified** — applied in a different form; reason given;
- **Decision needed** — the change touches an earlier customer decision, cost or hardware (§5);
- **Reject** — reason given.

**Facts checked independently** before relying on them:

- **Token volume.** The compiler experiment used 2B input and 140M output tokens for ~100k lines, about 1,400 output tokens per line ([Anthropic](https://www.anthropic.com/engineering/building-c-compiler)).
- **LiteLLM supply-chain compromise.** LiteLLM's PyPI releases were compromised with a credential stealer in March 2026, via compromised Trivy CI tooling ([LiteLLM](https://docs.litellm.ai/blog/security-update-march-2026), [The Register](https://www.theregister.com/2026/03/24/trivy_compromise_litellm/)).
- **GitHub plan.** On GitHub Free, Pro and Team, environment *required reviewers* work only for public repositories ([GitHub Docs](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments)), so our second G3 enforcement on private repos needs GitHub Enterprise.

Reviewer claims not independently verified are marked *(to verify in Phase 0/1)*.

## 2. Verdict

The core of the design held up. **All five reviewers independently named the same strengths:**

1. Verification first, with humans owning the oracle and the release.
2. A judge that runs the checks itself and never trusts the worker.
3. Gates, judges and schema checks that fail closed.
4. Git as the source of truth.
5. A gateway and adapters that keep models, engines and harnesses replaceable.
6. Typed handoffs instead of agent chat.
7. Tiered S → M → L measurement against a single-agent baseline.

**Five problems are serious enough to fix before building:**

1. **Agent-written code runs on the same host as the keys to everything** (RV-01). CI jobs, Testcontainers and kind need Docker-level access. A malicious or careless test can reach the signing key, the client deploy credentials and the audit log.
2. **Agents can edit the machinery that judges them** (RV-02). Workflows, `conftest.py`, test and lint configs, and contracts are all editable. A same-repo PR runs *its own* workflow file, so a worker can make its required check green.
3. **The platform grades itself with its own oracle** (RV-03). Success metrics count tests the same model wrote. There is no independent hidden test suite, no absolute pass threshold, and no kill criterion that stops funding.
4. **The riskiest assumption is tested last** (RV-04). That assumption is whether local models can keep a 100k+ LOC system coherent. The plan builds most of the platform first, and 100 of 115 requirements are "must".
5. **Throughput estimates are 3–10× optimistic** (RV-05). Output tokens per line were under-estimated 5–14×. The GPU's memory bandwidth may be that of the PCIe card, not SXM. Prefix caching on the hybrid primary model is unproven, and CI on one runner is serial.

None of these invalidate the approach. All are design or plan changes, and most are cheap if made now.

## 3. Findings register (by theme, most severe first)

### Critical

**RV-01 — Untrusted code shares a host and kernel with the control plane.**
*Source: S-1, S-8, P-9, R-6.* · **Disposition:** Accept (hardware option in §5, DN-1)

- **Problem.** CI jobs, Testcontainers, kind/k3s and workspaces all execute agent-written code. The runner mounts `docker.sock` by default, which is root on the host. On that same host live OpenBao (cosign key, client SSH keys and kubeconfigs), the GitHub App key, the PostgreSQL audit log and gate records, and Ollama. Ollama and Qdrant have no authentication by default, and no network zones are defined.
- **Change.**
  - Separate a **control plane** (API, orchestrator, PostgreSQL, OpenBao, gateway, Ollama) from an **execution plane** (workspaces, CI runners, sandbox).
  - **Preferred:** the execution plane runs on a CPU companion server from day one. **Minimum:** KVM microVMs (Kata/Firecracker) on the node.
  - Runners are ephemeral just-in-time runners, one VM per job, with no `docker.sock` on the control host.
  - Network zones with default-deny egress at L3/L4:
    - execution zones reach only the package proxy and the gateway, using per-task virtual keys;
    - Ollama is reachable only from the gateway;
    - Qdrant uses API keys;
    - PostgreSQL has a role per module;
    - OpenBao is reachable only from the orchestrator and the deploy runner.
  - Jobs authenticate to OpenBao with GitHub OIDC claims. No static tokens on any runner.

**RV-02 — Agents can edit the verification machinery.**
*Source: V-2, S-2.* · **Disposition:** Accept

- **Problem.** Only `tests/acceptance` and e2e scenarios are read-only. Everything else that decides a pass stays editable:
  - workflows, `conftest.py`, pytest/coverage/lint/type configs, `.importlinter`;
  - `contracts/`;
  - suppression comments (`noqa`, `type: ignore`, `nosec`).

  Research shows coding agents modifying tests in a large share of impossible tasks, and also special-casing production code for tests ([ImpossibleBench](https://arxiv.org/html/2510.20270v1)).
- **Change.**
  - A platform-owned **protected-path manifest**: any diff touching it fails the judge and needs human CODEOWNERS approval.
  - The GitHub App gets **no `workflows` permission**.
  - CI, release and deploy logic live as **reusable workflows in a platform-owned repository, pinned by SHA** and enforced by rulesets. Gate thresholds and scanner configs come from the platform baseline, not the project repo.
  - The judge runs the oracle from a **separate, hash-pinned checkout** against the built image.
  - These count as failures: collected-test count ≠ approved manifest; any skip, xfail or deselect; growth in suppressions (ratchet).
  - Semgrep rules flag test-mode branches (`if settings.TESTING`, dependency overrides in app code).
  - A **hidden held-out slice** of acceptance scenarios that workers never see.
  - A typed **"oracle defect / impossible task" report**, so flagging a bad test is cheaper than gaming it.

**RV-03 — Success is measured with the mesh's own oracle; no absolute thresholds or kill criteria.**
*Source: V-1, V-11, V-12, D-3.* · **Disposition:** Accept (thresholds proposed in §4; customer to confirm, DN-2)

- **Problem.**
  - O1 counts tests the mesh wrote, and allows 10% of approved tests to fail at go-live.
  - Benchmark gates are "simulated", so no human checks the oracle in benchmark mode.
  - The P2→P3 exit ("2 of 3 metrics") can pass with *more* escaped defects.
  - The benchmark is too small and gets one run per configuration.
  - The baseline is undefined.
  - O4 cannot distinguish good calibration from bad with ≤10 runs.
- **Change.**
  - Every benchmark project gets a **sealed, human-authored hidden acceptance suite** and a hidden defect list. The pass rate on the hidden suite is the primary metric.
  - O1 becomes: 100% of critical and high-priority requirements pass, with any other failure needing a signed waiver.
  - **k ≥ 3 repeats** on S/M runs, reported with confidence intervals.
  - The baseline is the **strongest simple alternative at equal GPU budget**: one agent loop with the same oracle, CI and task list.
  - **Ablations** justify each mesh component.
  - Forecast calibration is measured at **task level** (thousands of samples) and rolled up by Monte Carlo.
  - **Stage-gated funding** with pass, pivot and kill thresholds per phase (§4).
  - Align O3, 00 §7 and the exit criteria: never worse on escaped defects.

**RV-04 — The riskiest hypothesis is tested last; the v1 scope is too large.**
*Source: D-1, D-2, P-8, V-12.* · **Disposition:** Accept (scope cut list needs customer agreement, DN-3)

- **Problem.** The first end-to-end result arrives around month 7–9, and the first L-tier attempt around month 10–13. Phase 1 holds 6–10 benchmark projects, a harness, three bake-offs and about 11 decisions, all in 8–10 weeks. 100 of 115 requirements are "must".
- **Change.**
  - A **6–8-week capability spike** in Phase 0/1. Use the compiler-experiment pattern (loop + git + tests) with one model and one off-the-shelf harness, on one M-tier spec plus a 2–3-module slice of an L-tier spec with contracts.
  - An **L-tier probe by month 4–5**.
  - Bake-offs run on a **task-level micro-benchmark** (100–300 tasks), not full projects.
  - Spread decisions across P0–P2.
  - **MoSCoW re-baseline** to about 35–45 must requirements (proposal in §4.3).

**RV-05 — Throughput and GPU-time estimates are materially optimistic.**
*Source: P-1, P-2, P-3, P-4, P-5, P-8.* · **Disposition:** Accept

- **Problem.**
  - **Output tokens.** 02 §10 assumed 100–300 output tokens per final line; the compiler run used ~1,400 (verified).
  - **Memory bandwidth.** The decode ceiling used the H100 **SXM** figure (3.35 TB/s). A single-GPU EPYC server likely has the **PCIe** card (~2.0 TB/s) *(to verify: `nvidia-smi -q`)*.
  - **Prefix caching.** Reuse on the hybrid Gated-DeltaNet primary model has repeatedly broken in llama.cpp-family engines *(to verify)*.
  - **CI.** One self-hosted runner executes one job at a time, so CI for 300–500 task PRs could take 7–20 days serially.
  - **GPU duty cycle.** Agents use the GPU only ~40–60% of the time, so 3–4 workspaces cannot keep 4 slots busy.
- **Change.**
  - 02 §10 is re-based (see the update there). Planning range for a 150k-LOC build on one node: **~1 to ~12 weeks, P50 ~4–6 weeks**, to be replaced by measured **output tokens per accepted LOC**.
  - Confirm the GPU form factor.
  - Make the **cached-prefix ratio** a D2b decision metric (Ollama vs vLLM hybrid prefix caching).
  - CI becomes a scheduled lane with N ephemeral runners, a **merge queue**, tiered CI (affected tests on PRs; full suites per merge batch) and persisted caches.
  - Size workspaces from GPU slots ÷ duty cycle.
  - Write an explicit Phase 1 GPU-hour budget.

### High

**RV-06 — Executable acceptance tests are frozen at G1, before the API exists.**
*Source: V-3.* · **Disposition:** Accept

- **Problem.** Step definitions, fixtures and Playwright locators depend on the API, data model and UI decided at G2. Mutation testing "at G1" has no code to mutate.
- **Change.**
  - **G1** approves human-readable Gherkin plus **example tables** (inputs and expected outputs as data).
  - A new **Oracle Binding** stage after G2: step definitions and locators are written by a role separate from the workers, against the approved contracts.
  - Assertions are mechanically checked to use the example values, and none may be weaker.
  - Approved at a light **G2b**.
  - Spec mutation at G1; code mutation per module (changed code) before "module done" and at G3.

**RV-07 — Human review load is unsized; G1 will be rubber-stamped; O2 hides human hours.**
*Source: V-4, D-7, V-10.* · **Disposition:** Accept

- **Problem.** An L-tier G1 package means hundreds to thousands of scenarios. 500–1,000+ PRs at 10–20% sampling means 100–200 expert reviews. Escalations add more. O2 compares *measured* mesh hours with an *estimated* human baseline. No reviewer FTE exists, and no one is named as owning the code at go-live.
- **Change.**
  - **Risk-tiered G1:**
    - SMEs write or verify **golden scenarios** for the top-risk use cases;
    - the rest is **statistically sampled**, and the batch is rejected above a defect threshold;
    - the oracle is generated twice, independently, and disagreements go to humans.
  - A mandatory **human-touch ledger** covers every project-attributable minute, including platform-team interventions; O2 counts all of it.
  - An **escalation budget per tier** acts as a kill trigger.
  - Run at least one S-tier project with a real human team (actual vs actual).
  - Add 1–2 reviewer FTE, or make reviewers a named customer commitment.
  - A **named engineering owner** signs G3.

**RV-08 — Nothing keeps a 100k–250k LOC system coherent across hundreds of small tasks.**
*Source: V-5, V-6, V-7.* · **Disposition:** Accept

- **Problem.**
  - No foundation stage for cross-cutting concerns.
  - No module integration milestones.
  - No refactoring task type.
  - Parallel PRs that are each green can break `main` together.
  - Hotspot files have no single writer: Alembic heads, `contracts/`, the generated TypeScript client, `core/`.
  - The per-task oracle is mostly worker-written unit tests.
  - Agent code erodes even while its tests pass ([SlopCodeBench](https://arxiv.org/html/2603.24755v1)).
- **Change.**
  - A **Foundation stage** after G2: cross-cutting modules plus one end-to-end vertical slice, human-reviewed.
  - **Module integration milestones**, each with a module acceptance run and an architect conformance review.
  - A **refactor/consolidate task type**, triggered by ratcheted metrics (duplication, complexity, module size).
  - A **GitHub merge queue**.
  - **Scope leases** in the scheduler, with serialized hotspots: one migration writer at a time; contract changes land first as their own tasks; derived artifacts are regenerated after merge.
  - Each task names the acceptance or contract tests it must turn green.
  - Task unit tests are written by a separate test-author call before the worker starts.
  - An **acceptance ratchet**: tests that have passed may never fail again.
  - A CI check for multiple Alembic heads.

**RV-09 — The lifecycle ends at go-live; no change-request or maintenance path.**
*Source: V-8, D-8, R-8.* · **Disposition:** Accept

- **Change.**
  - A **Change Request** stage graph: KG impact analysis → delta oracle → G1-delta (affected scenarios only) → task invalidation and re-plan → re-forecast.
  - **Hypercare** and **Maintenance** lifecycle states with a hotfix fast path (reduced, still human, gate).
  - A tested **re-hydration** of a project onto any node from git and backups.
  - Release signing, site profiles and the SBOM register move to a **central service** outside project nodes.
  - Daily **CVE monitoring of delivered SBOMs**.
  - A support model (incident intake, SLA, owner) for generated systems.
  - Changes to systems the mesh built ("self-built brownfield") come **into v1 scope**.
  - Each M/L benchmark includes one change request and one post-release fix.

**RV-10 — Release integrity, deploy credentials and interrupted deployments.**
*Source: S-4, S-5, R-4, R-5.* · **Disposition:** Accept, modified (keeps the pilot's direct-push decision, D21)

- **Problem.**
  - The cosign signature proves who built an artifact, not that G3 approved it.
  - Approvals are not bound to digests, so something else can be swapped in between review and deploy.
  - LangGraph re-runs a node from its start on resume, so code before `interrupt()` can regenerate the approved package.
  - Standing SSH and kubeconfig credentials into client data centres sit on a node that runs untrusted code.
  - Nothing defines what happens if the node dies mid-deploy.
- **Change.**
  - Every gate package is assembled in an earlier node and stored immutably with a content hash. The interrupt node contains only `interrupt()`. The resume `Command` carries the package hash and the approver identity, and fails closed on any mismatch.
  - A **G3 promotion attestation** lists the approved digests. The deploy job deploys only those. Clients verify the signatures and the attestation (a Kubernetes admission policy; a verify script for Compose).
  - Mode A deploys from a **dedicated deploy runner**:
    - on the control-plane side, never the execution plane;
    - **short-lived SSH certificates or Kubernetes tokens**, issued by OpenBao to jobs whose OIDC claims match the site environment and a release tag;
    - on Compose hosts, a non-docker-group deploy user with a **forced command** that verifies the digest, then converges;
    - minimal Kubernetes RBAC;
    - clients allow only the deploy runner's source IP.
  - A **deploy state machine** records a deploy intent before dispatch. A go-live is never auto-retried after a crash; the state is reconciled and a human decides.
  - `helm upgrade --atomic`, and idempotent Compose scripts.
  - A **break-glass rollback** from an operator machine using the offline bundle.

**RV-11 — Long-lived threads, leases and restarts.**
*Source: R-2, R-3, R-12.* · **Disposition:** Accept

- **Problem.**
  - LangGraph resumes old threads on the *latest* graph code.
  - Ollama tags are mutable, so the weights behind a tag can change.
  - Leases have no fencing, so a live-but-stalled runner and its replacement can both act.
  - The default checkpoint durability is `async`.
  - Nothing gates work on dependency readiness after a restart: OpenBao comes up sealed, Ollama comes up cold.
  - Infrastructure failures consume task attempts.
- **Change.**
  - A per-project **platform BOM**, pinned at project start: platform image digest, graph versions, instruction SHA, model and embedding digests. A change to it is a change request.
  - `flow_version` is stamped into state, and parked checkpoints are resume-tested in CI before any rollout.
  - **One lease table with an epoch fencing token**, checked in every checkpoint write and queue transition. Branch pushes use `--force-with-lease`.
  - Heartbeats run in a separate thread; a runner that cannot renew kills itself.
  - Orphaned slots and workspaces are reaped.
  - Resume attempts are capped, after which the thread is quarantined.
  - `durability="sync"`.
  - A **readiness barrier** before admitting work.
  - **Infra vs task failure classification**: infra failures pause and alert, and never consume attempts.

**RV-12 — Backup, restore and hardware resilience are incomplete.**
*Source: R-1, R-6, R-13.* · **Disposition:** Accept (hardware spec in §5, DN-1)

- **Problem.** Backups miss:
  - OpenBao (signing and deploy keys) and the GitHub App key;
  - traces/run logs, which "rebuildable" depends on;
  - research snapshots, since web content cannot be re-fetched;
  - offline bundles and evidence;
  - host config.

  Daily `pg_dump` gives an RPO of up to 24 h. There is no reconciliation with GitHub after a restore. The hardware has no redundancy, there is nowhere to restore to, and one shared 4 TB filesystem has no quotas.
- **Change.**
  - A **state inventory**: source of truth / derived / secret, each with its own backup method and restore order.
  - PostgreSQL **PITR** (WAL archiving, minutes of RPO).
  - Encrypted OpenBao snapshots, with unseal shares escrowed by named people.
  - Research findings stored with content snapshots in PostgreSQL or git.
  - A **post-restore reconciliation** scans GitHub by task-ID keys and freezes go-live until done.
  - An audit "restore epoch" record.
  - Quarterly restore drills onto other hardware.
  - Mirrored NVMe, ECC, dual PSU, UPS.
  - Separate volumes with quotas, GC jobs, and disk alerts with scheduler back-pressure.
  - Two RTOs: "state restored" and "throughput restored".

**RV-13 — Day-2 operations of the platform itself.**
*Source: R-7, R-9, R-11.* · **Disposition:** Accept

- **Problem.**
  - No platform release or upgrade process, and no host patching policy.
  - GitHub enforces minimum self-hosted runner versions (30 days).
  - GitHub's secondary rate limits are ignored.
  - Alerting has no external heartbeat, and there is no stuck-project detection, operator console, runbooks or on-call model.
- **Change.**
  - A platform release runbook:
    - canary on the benchmark node;
    - drain running graphs;
    - forward-only migrations;
    - health-gated re-admission;
    - no upgrades during go-live windows.
  - Pinned host image with no unattended driver or kernel upgrades; monthly patch windows.
  - A runner-image update pipeline with age alerts.
  - All GitHub writes go through an **outbox with a rate budget**; GitHub outages never count as task attempts.
  - An external heartbeat.
  - An alert catalog: no progress while the queue is non-empty, oldest queue age, gate-wait age, lease churn, GPU idle while work is queued, disk forecast, backup age, OpenBao sealed, runner offline, rate-limit headroom.
  - An **operator console or CLI** with audited actions: inspect, release lease, quarantine, rewind, cancel.
  - Runbooks per alert, and a stated ops model (business hours, with an overnight pause on anomalies).

**RV-14 — Supply chain: hallucinated packages, platform dependencies, model provenance.**
*Source: S-7, S-12, D-6.* · **Disposition:** Accept

- **Problem.**
  - LLMs frequently hallucinate package names ([USENIX Sec '25](https://www.usenix.org/conference/usenixsecurity25/presentation/spracklen)).
  - Licence and known-CVE checks cannot catch new malicious packages.
  - Our own gateway, LiteLLM, shipped a credential stealer in March 2026 (verified).
  - Some candidate-model sources cited in 02 are personal Hugging Face namespaces.
- **Change.**
  - Workspaces and CI reach **only an internal package proxy** that serves an allow-list (catalog plus vetted transitive closure), with a 7–14 day quarantine for new versions.
  - `uv` lockfiles with hashes.
  - `npm ci --ignore-scripts`.
  - A lockfile diff that adds a package needs **human approval**.
  - Platform dependencies (including LiteLLM, Ollama, Trivy) are pinned by digest and tracked against advisories. All actions are pinned by SHA.
  - A **model register**: official publisher organization, licence and usage policy, SHA-256, an internal model mirror, and no runtime pulls. The model digest is recorded in every trace and evidence bundle.

**RV-15 — Prompt injection and data exfiltration paths.**
*Source: S-6, S-13.* · **Disposition:** Accept

- **Problem.**
  - "Quoted data" is a prompt convention, not an enforced boundary.
  - The Researcher combines private data (on-prem DBs), untrusted content (the web) and an exfiltration channel (search queries).
  - Summaries lose provenance.
  - CI and test output reach retries unfiltered.
  - There is no data classification for what may leave the node.
- **Change.**
  - Split the Researcher into a **WebResearcher** (no internal data, templated queries over approved topics) and an **InternalDataAnalyst** (on-prem DBs, no web).
  - **Taint labels** on KG nodes and Qdrant points, inherited through summaries. Tainted context cannot introduce a dependency, URL, command or scope change without human approval.
  - CI output enters retries only as structured fields.
  - **Data classes** with allowed destinations.
  - Synthetic-only fixtures, with a PII scan on commits and issue bodies.
  - The Issues mirror carries IDs and status only.
  - DPA and zero-retention terms with the search providers.
  - Injection red-team cases in the benchmark.

**RV-16 — Ollama and context-management pitfalls.**
*Source: P-6, P-7, P-10, P-11.* · **Disposition:** Accept (configuration policy + Phase 1 measurement)

- **Problem.**
  - Ollama's default context is allocated per slot.
  - The `/v1` endpoint can ignore `num_ctx`, and over-length prompts are **silently truncated** *(to verify)*.
  - Changing `num_ctx` reloads the model.
  - Layers can spill to the CPU silently.
  - The scheduler's admission unit is undefined.
  - There are no per-turn token caps or loop detection.
  - Embeddings and a second model can evict the primary model.
- **Change.**
  - One server-wide context length and slot count, pinned in infrastructure-as-code, sized for no offload, with an alert on any CPU offload.
  - Role context budgets enforced with a tokenizer in the gateway or harness: **fail closed, never truncate**.
  - Admission unit = session lease = slot, with **one slot reserved for P0**.
  - Per-role caps on output and thinking tokens, a repetition/no-progress detector, and per-task GPU-token budgets.
  - **Embeddings on the CPU** in their own container.
  - Second-model review only in Design, with Build drained.
  - The bake-off includes a 27B + A3B MoE pairing, quantization levels, and vLLM with and without MTP.

**RV-17 — Platform UI authentication and separation of duties.**
*Source: S-9.* · **Disposition:** Accept

- **Change.**
  - **OIDC** with the customer's identity provider in v1.
  - Phishing-resistant MFA and step-up authentication for gate actions.
  - Roles: PO, architect, security officer, operator, reviewer.
  - **Four-eyes rule:** the requester is never the approver, and G3 needs two humans.
  - Agent and orchestrator credentials can never call gate-decision endpoints.
  - The API is unreachable from execution networks.
  - CSRF and Origin checks.

**RV-18 — Generated systems lack a secure-by-default baseline.**
*Source: S-10, V-9.* · **Disposition:** Accept

- **Change.**
  - OIDC authentication and **deny-by-default authorization in the core template**, with a fitness function that fails on any route without an auth dependency or an explicit public marker.
  - Security headers, CORS and rate limits.
  - **OWASP ASVS L2** as the default NFR.
  - A **STRIDE threat model** in the G2 package.
  - An **authorization matrix** (actor × endpoint) generated at G1/G2 and run as tests.
  - ZAP baseline/API scans in the sandbox.
  - IaC scanning.
  - Kubernetes Pod Security "restricted", NetworkPolicies, read-only root filesystem.
  - Encrypted backups and hardened Keycloak.
  - A human **security sign-off** at G3.

**RV-19 — Non-functional requirements have no definition of done; performance tests on a contended node are meaningless.**
*Source: V-9.* · **Disposition:** Accept

- **Change.**
  - An **NFR DoD catalog**: for each NFR type, the evidence, environment, threshold, cadence and owner.
  - Performance runs as **relative regression budgets** on a quiesced runner (execution plane, GPU idle), plus an absolute run on reference hardware before G3.
  - A manual accessibility pass in UAT.

**RV-20 — UI correctness and UX are barely oracled.**
*Source: V-14, D-11.* · **Disposition:** Accept, modified (Svelte front end stays, per D19)

- **Change.**
  - The prototype becomes **mandatory**.
  - A **UI contract** at G2: route map, page → use case, accessible roles and labels.
  - E2E tests use role and label locators.
  - Humans approve visual-regression baselines at each module's first render.
  - Time-boxed human UX checkpoints per module during Build.
  - Exploratory QA becomes a must.
  - Benchmark staging (DN-4): S-tier projects are API-only first, and UI is added from the M tier, so back-end and UI autonomy are measured separately.

**RV-21 — The audit log can be rewritten from the node; traces will capture secrets.**
*Source: S-11.* · **Disposition:** Accept

- **Change.**
  - An INSERT-only audit role and a single-writer appender with batched hashing.
  - The chain head is anchored **per gate and deploy event and at least every minute** to off-node WORM storage, with a key held off the node.
  - An off-box verifier cross-checks against GitHub's audit log.
  - **Secrets are redacted** before traces and audit records are written; sensitive I/O is stored as hashes.

**RV-22 — GitHub App scope, runner scope and plan.**
*Source: S-3, D-12.* · **Disposition:** Accept (plan in §5, DN-5)

- **Change.**
  - **Two Apps:**
    - a provisioning App (administration), used only by a human-triggered operator tool;
    - a delivery App (contents, pull requests, issues, checks read), with **no administration, workflows, environments, secrets or actions-write**.
  - Installation tokens scoped to one repository.
  - A separate key per node.
  - Runners registered per repository.
  - Environments with "prevent self-review" on, no admin bypass, and deployment from protected tags only.
  - Required reviewers on private repositories need **GitHub Enterprise** (verified).

**RV-23 — No legal or contractual workstream.**
*Source: D-6.* · **Disposition:** Accept

- **Change.** A Phase 0 legal deliverable set:
  - **model register** with licences and usage policies;
  - an OSS licence-obligation process driven from SBOMs (attribution/NOTICE);
  - a client contract template covering IP assignment for generated code, warranty and defect remediation, limitation of liability, consent for code hosting on github.com, remote-access terms for client systems, and a DPA;
  - synthetic data only in sandbox and UAT unless a DPA covers real data.

**RV-24 — Program gaps.**
*Source: D-4, D-13.* · **Disposition:** Accept (customer input needed, DN-6)

- **Change.**
  - An indicative budget range and a role-based hiring plan.
  - Committed **SME hours per phase**.
  - Monthly demo milestones.
  - A WBS + re-forecast as a P0 go/no-go deliverable.
  - Team additions: 1 front-end engineer, 0.5 delivery manager, and reviewer capacity (RV-07).
  - Resolve who the users are.
  - A "Client" stakeholder role and a RACI per gate.
  - Day-in-the-life journeys with service levels (e.g. clarifications answered within one business day).
  - A **human-takeover protocol**.
  - A notification budget per role.

**RV-25 — The pilot stacks two firsts (first L-tier build and first client go-live).**
*Source: D-5.* · **Disposition:** Accept (customer to confirm, DN-7)

- **Change.**
  - **P3a:** an L-tier build delivered to an internal or friendly target.
  - **P3b:** client go-live of a hardened system, signed by a named engineering owner.
  - Client go-live moves to P4 if P3a misses its thresholds.

**RV-26 — One H100 per project leaves the GPU idle most of the project's life.**
*Source: D-12, P-5.* · **Disposition:** Decision needed (DN-8)

- **Change.**
  - A per-project **TCO model** in Phase 0.
  - Keep data isolation per project, but allow **sequential time-sharing** of GPU nodes via tested re-hydration (RV-09), or pooled inference across project-isolated data stacks, in Phase 4.
  - Idle-time fillers: scaffolding for queued tasks, documentation, re-indexing.

**RV-27 — Adversarial architecture review by one weak model is unmeasured.**
*Source: V-13.* · **Disposition:** Accept

- **Change.**
  - Seed architecture flaws in benchmark designs and measure reviewer recall and precision.
  - Anchor reviews to mechanical checks:
    - every scenario traced to a call sequence over the contracts;
    - unique data ownership;
    - an NFR → tactic map;
    - module-size budgets.
  - A second-model round is **mandatory for M/L**.
  - Severity downgrades need reviewer agreement or human sign-off.

**RV-28 — PostgreSQL carries five workloads.**
*Source: R-10, P-12.* · **Disposition:** Accept

- **Change.**
  - Leases are expiry columns, never open transactions, with `idle_in_transaction_session_timeout` set.
  - Per-table autovacuum tuning for the queue.
  - Physical backups (PITR) instead of `pg_dump`.
  - Large payloads (diffs, transcripts) live outside graph state, referenced by hash.
  - Checkpoints at task-graph node boundaries only, with pruning after evidence is extracted.
  - Tracing outside the system-of-record instance.
  - Separate databases per concern.

**RV-29 — Inconsistencies between documents.**
*Source: D-14.* · **Disposition:** Accept (fixed in this revision)

- D19–D21 were missing from the charter.
- FR-DEP-04 made all three delivery modes "must", while 06 deferred GitOps.
- The sandbox was described as "Compose" in one place and "Compose + Kubernetes" in another.
- GHCR conflicted with client-site registries.
- Some resolved questions were still listed as open.
- The team size was inconsistent.

**RV-30 — Scope that reviewers proposed cutting, but that the customer decided.**
*Source: D-10, D-11.* · **Disposition:** Partly rejected, modified

| Reviewer proposal | Disposition | Reason |
|---|---|---|
| Drop SQL-engine agnosticism | **Reject** — keep a light form | The customer asked for engine agnosticism. Repository isolation and generic types are cheap; we keep the rules and the lint, but test only PostgreSQL in v1 (already the case). |
| Support only the pilot's target type | **Accept, modified** | Both Compose and Kubernetes stay supported. Each RC is rehearsed **only on the target types present in the project's site profiles**, not always on both. |
| GitOps (mode B) is "must" | **Accept** | Demoted to "should", matching 06. |
| Offline bundle rehearsed every RC | **Accept, modified** | It is still produced for every RC as the archival record (cheap), and rehearsed only when a mode-C site exists. |
| Replace the Svelte front end with API-only | **Reject** for the product; **accept** staging in the benchmark (RV-20) | Customer decision D19. |

### Not adopted

| Reviewer item | Reason |
|---|---|
| Prefer pull-based delivery (GitOps or client agent) over direct push for the pilot (S-4) | The customer chose direct push for the pilot (D21). RV-10 hardens push instead: dedicated deploy runner, short-lived certificates, forced command, client IP allow-listing. Pull stays available per client. |

## 4. Proposed plan changes (applied to the charter as v9; DN-2 and DN-3 need confirmation)

### 4.1 Revised phases

| Phase | Change |
|---|---|
| **P0 Discovery & foundations (4–6 wk)** | Adds: threat model and security decisions (control/execution plane split, App split, network zones, OIDC to OpenBao, UI auth); legal deliverables; model register; TCO; budget, hiring plan, SME hours; WBS + re-forecast as a go/no-go. |
| **P0/P1 Capability spike (6–8 wk, overlaps P1 start)** | **New.** Loop + git + tests with one model and one off-the-shelf harness on one M-tier spec and a 2–3-module L-tier slice. Measures output tokens per accepted LOC, cached-prefix ratio, escalation rate and hidden-suite pass rate. **Pass / pivot / kill gate.** |
| **P1 Benchmark, harness, baselines (8–10 wk)** | Benchmark reduced to 2 S + 2 M + 1 L-slice with sealed hidden suites, mutation-validated oracles, and public open-source systems where useful. Bake-offs run on a 100–300-task micro-benchmark. Explicit GPU-hour budget. |
| **P2 Verification-first core** | Adds: Oracle Binding + G2b, Foundation stage, integration milestones, merge queue, scope leases, acceptance ratchet, protected-path manifest, change-request flow. **L-tier probe by month 4–5.** |
| **P3a L-tier build (internal target)** | The L-tier build is delivered to an internal or friendly target. |
| **P3b Client go-live** | Hardened release, named engineering owner, security sign-off, penetration test of the platform passed. |
| **P4 Expansion** | GitOps and other delivery modes as needed; GPU time-sharing; second SQL engine; more domain packs. |

### 4.2 Stage-gated funding thresholds (proposed values; to be confirmed with the customer)

| Gate | Pass | Pivot | Kill |
|---|---|---|---|
| End of capability spike (~month 3) | Best model + harness ≥ 70% hidden-suite pass on the M-tier spec within the GPU budget; escalations ≤ budget | 40–70%: change model or engine, add GPU, or narrow to S/M assistance | < 40%, or escalations superlinear in size |
| P1 → P2 | Harness reproduces the baseline within ±5 pp across 3 repeats on S | — | Harness not reproducible |
| P2 → P3a | Mesh ≥ 80% hidden-suite pass on M; ≤ X human hours per KLOC; **not worse** than the baseline on escaped defects; better than the baseline on two of {human hours, GPU-hours, hidden pass} with CIs from ≥ 3 runs | Mesh not better than the baseline: simplify the mesh | Absolute quality below the spike result |
| P3a → P3b | L-tier: 100% critical/high requirements pass on the hidden suite; erosion metrics within budget; security sign-off | Re-scope to M-tier client go-live | Escalations superlinear at L |

### 4.3 MoSCoW re-baseline (proposal — DN-3)

Requirements serving the core question (can local models plus verification-first deliver M/L systems safely?) stay **must**. These move to **should** for v1, with their **trigger** for promotion:

| Requirement | Change | Promote when |
|---|---|---|
| FR-KNW-01 domain layer, FR-KNW-06, FR-KNW-07 | v1 must: delivery layer, traceability, code graph and Qdrant. Domain layer and graph-reasoning tools become **should** | An ablation shows a benefit (spike / P2) |
| FR-PLN-03/04/05 | Forecasts come from harness telemetry at task level; a full forecasting UI becomes **should** | P2 |
| FR-RPT-01 | GitHub Projects + Grafana first; custom dashboard **should** | P3 |
| FR-HUM-01 | Gate packages as Markdown in PRs and reviews first, with custom screens **should**, **but** approvals still go through the platform with OIDC, MFA and package hashes (RV-10, RV-17) | P2 |
| FR-REQ-01 | Markdown and PDF intake first; DOCX **should** | P2 |
| FR-DEP-04 GitOps mode | **should** | First client that needs it |
| FR-DOC-02/03 | Business documentation and drift checks **should** | P3 |

## 5. Decisions needed from the customer

| ID | Decision | Recommendation |
|---|---|---|
| **DN-1** | **Execution-plane hardware and node resilience.** A CPU companion server per project node from day one (CI runners, sandbox, workspaces). Node spec: mirrored NVMe, ECC, dual PSU, UPS. A spare or standby node. | Yes to the companion server. It fixes isolation (RV-01), CI throughput (RV-05) and RAM pressure in one step. If not possible, run microVM isolation on the node and accept slower CI. |
| **DN-2** | Stage-gated funding with pass / pivot / kill thresholds (§4.2) | Adopt; agree the threshold values. |
| **DN-3** | MoSCoW re-baseline (§4.3) | Adopt. |
| **DN-4** | Benchmark staging: S-tier API-only, UI from M-tier | Adopt; the Svelte front end stays in the product. |
| **DN-5** | **GitHub Enterprise** (required reviewers on private-repo environments; rulesets; required workflows) | Adopt; otherwise move the second G3 enforcement to the platform's deploy runner with a signed promotion attestation. |
| **DN-6** | Budget envelope, hiring plan (+1 front-end engineer, +0.5 delivery manager, 1–2 reviewers or a named customer commitment), SME hours per phase; who the platform's users are | Needed for the P0 go/no-go. |
| **DN-7** | Split the pilot into P3a (internal L-tier) and P3b (client go-live) | Adopt. |
| **DN-8** | GPU economics: accept low GPU utilization per project in v1, or plan sequential time-sharing in P4 | Accept for v1; produce the TCO model in P0. |
| ~~DN-9~~ | ~~GPU form factor~~ — **resolved 2026-10-05: H100 PCIe** (~2.0 TB/s). The PCIe-based estimates in 02 §10 (update box) stand. | — |
| ~~DN-10~~ | ~~GPU dedication~~ — **resolved 2026-10-05: the GPU is dedicated to the mesh.** Existing GPU workloads are moved off before Phase 0 bring-up; the scheduler owns all 80 GB. Original question: `nvidia-smi` shows ~8 GB already in use by three other processes (two Python processes and an Ollama runner). Will the GPU be dedicated to the mesh on its project node? | Yes: the capacity plan assumes all 80 GB and no unscheduled GPU work. Any other GPU tenant must be moved off, or budgeted by the scheduler. |

## 6. Changes applied in this revision

| Document | Changes |
|---|---|
| [01 charter](01-project-charter.md) → v9 | O1–O4/O7 revised; phases revised (capability spike, P3a/P3b); exit criteria point to §4.2; team additions; D19–D21 added; D22–D28 added; risks updated; open questions = DN-1…DN-9 |
| [02 constraints](02-constraints-and-infrastructure.md) | §10 throughput re-based (update box); GPU form factor flagged |
| [03 requirements](03-platform-requirements.md) | FR-ORC-01/02, FR-DEP-04, FR-DEP-06 amended; new requirements in §10 (R1 additions); MoSCoW proposal referenced |
| [05 architecture](05-reference-architecture.md) → v1.2 | Lifecycle diagram revised (Foundation, Oracle Binding/G2b, Change Request, Hypercare, Maintenance); new §17 revisions (planes and zones, gates bound to hashes, fencing and versioning, CI lane, deploy runner, operations) |
| [06 baseline](06-generated-system-baseline-and-release.md) → v1.2 | Secure-by-default baseline; package proxy; promotion attestation; rehearsal only on profiled targets; hardened direct push |

## Sources

- Anthropic — Building a C compiler with a team of parallel Claudes (token counts): https://www.anthropic.com/engineering/building-c-compiler
- LiteLLM — Security update, March 2026: https://docs.litellm.ai/blog/security-update-march-2026
- The Register — LiteLLM infected via Trivy compromise: https://www.theregister.com/2026/03/24/trivy_compromise_litellm/
- Simon Willison — Malicious litellm 1.82.8: https://simonwillison.net/2026/Mar/24/malicious-litellm/
- GitHub Docs — Deployments and environments (required reviewers by plan): https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments
- GitHub Docs — Secure use of Actions / self-hosted runners: https://docs.github.com/en/actions/reference/security/secure-use
- ImpossibleBench — reward hacking in coding agents: https://arxiv.org/html/2510.20270v1
- SlopCodeBench — code erosion in iterative agent trajectories: https://arxiv.org/html/2603.24755v1
- USENIX Security '25 — package hallucinations in code LLMs: https://www.usenix.org/conference/usenixsecurity25/presentation/spracklen
- LangGraph docs — backward compatibility, interrupts, checkpointers, fault tolerance: https://docs.langchain.com/oss/python/langgraph/backward-compatibility · https://docs.langchain.com/oss/python/langgraph/interrupts · https://docs.langchain.com/oss/python/langgraph/checkpointers · https://docs.langchain.com/oss/python/langgraph/fault-tolerance
- GitHub — self-hosted runner minimum-version enforcement: https://github.blog/changelog/2026-06-12-github-actions-minimum-version-enforcement-timeline-for-self-hosted-runners/
- H100 PCIe / SXM / NVL specifications: https://www.thundercompute.com/blog/nvidia-h100-specs-full-guide
- Simon Willison — the lethal trifecta: https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/
