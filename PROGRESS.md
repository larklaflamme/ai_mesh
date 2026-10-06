# PROGRESS — AI Mesh prototype

Tracker for Claude Code and the human lead. The work packages (WPs) are defined in [`design/09-implementation-guide/`](design/09-implementation-guide/README.md).

**Rules**
- Take the first unchecked WP of the current phase, unless the human says otherwise.
- Tick a WP only when every acceptance criterion is met.
- After a ticked WP, write one line: the date, what was done, the evidence (tests / `make` targets / reports), and any deviations.
- Human checkpoints (HC-xx) are tracked in their own table. Never tick a WP that waits on a `waiting` HC.

**Current phase:** WP-B (bootstrap)

---

## Environment

Fill in during WP-B and WP0.2. HC-02 covers the workstation facts.

| Item | Value |
|---|---|
| Workstation OS / version | Ubuntu 24.04.4 LTS, kernel 6.8.0-110 (repo at `/home/ubuntu/ai_mesh`, not macOS). ⚠ HC-02: this host also has the H100 — see Open questions |
| CPU architecture / cores / RAM / free disk | x86_64, AMD EPYC 9124 (16C/32T), 188 GB RAM, 2.4 TB free on `/` (Docker root `/var/lib/docker` on same FS) |
| Docker engine / version / rootless? | Docker Engine 29.4.0, Compose v5.1.3, rootful, cgroup v2, apparmor + seccomp |
| Conda version; env `ai-mesh` Python version | conda 26.1.1 (Miniconda, not Miniforge; env uses `conda-forge` + `nodefaults` only); Python 3.12.14 |
| uv version | 0.12.23 |
| Node version (conda) | 22.23.2 in env (note: `~/.nvm` Node 24 precedes it on this shell's PATH; use `$CONDA_PREFIX/bin/node` where it matters) |
| Remote: Ollama version; env hash | |
| Remote: driver / CUDA | 595.58.03 / 13.2 (from nvidia-smi; re-check at HC-01) |
| Models (name → digest) | see `infra/remote/models.lock` |
| Tunnel mode (container / host) and endpoint ID | |
| LangGraph / langgraph-checkpoint-postgres versions | 1.2.13 / 3.1.2 (from `requirements/dev.lock`) |
| Image digests (workspace / judge) | see `infra/images/IMAGES.lock` |

## Human checkpoints

| HC | Status | Requested | Needed / where | Outcome / evidence |
|---|---|---|---|---|
| HC-01 Remote GPU server setup | open | | 02 Part A | |
| HC-02 Workstation facts | waiting | 2026-10-06 | Environment table above + Open questions Q1–Q3 (topology, port collisions) | Facts gathered by Claude Code; human confirmation of topology needed |
| HC-03 Model list and digests | open | | | |
| HC-04 Hidden suites (S1, M1, L-slice) | open | | | |
| HC-05 Spec review (S1, M1, L-slice) | open | | | |
| HC-06 Capability gate decision | open | | | |
| HC-07 GitHub test org and App | open | | | |
| HC-08 Experiment cards (E0…E7) | open | | | |
| HC-09 Gate approver keys | open | | | |
| HC-10 Checks and thresholds (as raised) | — | | | |
| HC-11 Dependency additions (as raised) | — | | | |
| HC-12 P2 → P3a gate | open | | | |
| HC-13 vLLM (optional) | open | | | |
| HC-14 S-cal human build | open | | | |
| HC-15 Client role at gates (per run) | — | | | |
| HC-16 UX checkpoint | open | | | |
| HC-17 Release signing keys | open | | | |
| HC-18 Decision pack review | open | | | |

## Work packages

### Bootstrap
- [ ] WP-B — Repository skeleton, conda env `ai-mesh`, locks, import-linter, pre-commit, Makefile, minimal CLI, CI ([01](design/09-implementation-guide/01-bootstrap.md))

### Phase 0 — Environment and instrumentation ([phase-0](design/09-implementation-guide/phase-0-environment.md))
- [ ] WP0.1 — Local infrastructure (compose: postgres, qdrant, tunnel, gateway, proxies, toxiproxy, phoenix)
- [ ] WP0.2 — Tunnel container and verification (V-01…V-10) — needs HC-01
- [ ] WP0.3 — Telemetry foundation (schemas, manifest, audit chain)
- [ ] WP0.4 — `mesh-gateway` v0
- [ ] WP0.5 — Ollama metrics investigation → ADR-019
- [ ] WP0.6 — GPU sampler
- [ ] WP0.7 — Human-touch ledger CLI
- [ ] WP0.8 — Readiness and infra classification primitives
- [ ] WP0.9 — `llm-bench` and experiment E0 — needs HC-03, HC-08
- [ ] **Phase 0 exit gate**

### Phase 1 — Capability spike ([phase-1](design/09-implementation-guide/phase-1-capability-spike.md))
- [ ] WP1.1 — Workspace and judge images; package proxy allow-list
- [ ] WP1.2 — Sandbox manager
- [ ] WP1.3 — Worker runtime and adapters (`single_loop`, `deepagents`)
- [ ] WP1.4 — Judge v0
- [ ] WP1.5 — Generated-system template v0 (API-only) — HC-11
- [ ] WP1.6 — Benchmark content v0 — HC-04, HC-05
- [ ] WP1.7 — Spike loop runner
- [ ] WP1.8 — E1, E2 and capability gate pack — HC-08
- [ ] **HC-06 capability gate decision:** ____

### Phase 2 — Harness and benchmark ([phase-2](design/09-implementation-guide/phase-2-harness-benchmark.md))
- [ ] WP2.1 — Experiment runner
- [ ] WP2.2 — Analysis and reporting
- [ ] WP2.3 — Benchmark v1 — HC-04, HC-05
- [ ] WP2.4 — OpenHands / OpenCode adapters
- [ ] WP2.5 — Oracle-strength validation — HC-10
- [ ] WP2.6 — E3 bake-off → ADR-020/021/022 — HC-08, HC-13 optional
- [ ] WP2.7 — S-cal human baseline — HC-14
- [ ] WP2.8 — Reproducibility study
- [ ] **Phase 2 exit gate**

### Phase 3 — Mesh core 1 ([phase-3](design/09-implementation-guide/phase-3-mesh-core-1.md))
- [ ] WP3.1 — Orchestration core (checkpointer, graphs, effects ledger, fenced leases, supervisor, readiness, flow_version) → ADR-023
- [ ] WP3.2 — Scheduler and capacity
- [ ] WP3.3 — Lifecycle and gates (G1/G2/G2b, oracle binding) — HC-09
- [ ] WP3.4 — Roles v1
- [ ] WP3.5 — Knowledge v1
- [ ] WP3.6 — GitHub test organization → ADR-024 — HC-07
- [ ] WP3.7 — Conformance (T-DUR) and security (T-SEC) suites
- [ ] WP3.8 — S1 end-to-end and E6 — HC-08, HC-15
- [ ] **Phase 3 exit gate**

### Phase 4 — Mesh core 2 ([phase-4](design/09-implementation-guide/phase-4-mesh-core-2.md))
- [ ] WP4.1 — Foundation stage, milestones, ratcheted refactoring
- [ ] WP4.2 — Merge queue, scope leases, acceptance ratchet
- [ ] WP4.3 — Change Request flow
- [ ] WP4.4 — Svelte front end — HC-11, HC-16
- [ ] WP4.5 — Knowledge graph engine trial → ADR-025
- [ ] WP4.6 — E4 and E7; P2 → P3a gate pack — HC-08, HC-04
- [ ] **HC-12 P2 → P3a decision:** ____

### Phase 5 — L-probe and release slice ([phase-5](design/09-implementation-guide/phase-5-l-probe-release.md))
- [ ] WP5.1 — E5 L-tier probe and scale curve — HC-04, HC-05, HC-08
- [ ] WP5.2 — Release pipeline (build once, SBOM, signing, G3, offline bundle) — HC-17
- [ ] WP5.3 — Rehearsal and deploy state machine → ADR-026
- [ ] WP5.4 — Hypercare and hotfix path
- [ ] WP5.5 — Decision pack for P3a → ADR-027 — HC-18
- [ ] **End-of-prototype exit gate**

---

## Log

One line per ticked WP or significant event: `YYYY-MM-DD — WP — what — evidence — deviations`.

- 2026-10-06 — WP-B (in progress, not ticked) — skeleton (52 dir READMEs), conda env `ai-mesh`, three packages + hashed locks (`requirements/dev.lock`, `gateway/requirements.lock`, `worker_runtime/requirements.lock`), `platform/.importlinter`, pre-commit (SHA-pinned), Makefile, `mesh version` / `mesh doctor`, CI workflow (SHA-pinned actions) — `make check` green: ruff ✓, import-linter 2 kept / 0 broken (planted violations core→telemetry, judge→workers, scm→oracle all detected), mypy strict ✓, 21 unit tests pass (T-BOOT-01…06); `pre-commit run --all-files` ✓; planted `ghp_…` token commit blocked by gitleaks (`github-pat`) — open items: CI not run (no remote yet, see Q4); HC-02 topology confirmation.

## Deviations

Departures from `design/` or this guide, with the reason and who approved them: `YYYY-MM-DD — what — why — approved by / pending`.

- 2026-10-06 — Default branch is `master` (existing repo), not `main`; WP branches `wp/<id>-<slug>` off it — pre-existing repo state, renaming is the human's call — pending.
- 2026-10-06 — `environment.yml` adds `nodefaults` channel and `go` (conda-forge). gitleaks is not on conda-forge; it runs via its official pre-commit hook built with the env's Go (`language_version: system`) instead of downloading a toolchain (go.dev download returned 502 / truncated twice) — tooling only — pending.
- 2026-10-06 — Platform dev extra adds `types-docker` (mypy stubs for `mesh.cli.doctor`) and `setuptools` (`uv pip sync` otherwise removes it and breaks conda's `distutils-precedence.pth`) — dev-only, host-side — pending.
- 2026-10-06 — `make test-*` tolerate pytest exit 5 ("no tests collected") per package and print it explicitly; needed while a level has no tests yet. Any other non-zero exit fails. Revisit once each level has tests (HC-10 if you'd rather it fail) — pending.
- 2026-10-06 — Pre-commit excludes `design/` entirely: ruff 0.16 formats Python blocks inside Markdown and rewrote `03-interfaces-and-schemas.md` (reverted) — protects design docs — pending.
- 2026-10-06 — `mesh.core.ids.new_id` is monotonic within a process (same-millisecond ULIDs increment the random part), so event IDs sort in creation order; unknown prefixes raise — stricter than spec — pending.
- 2026-10-06 — Extra test ID T-BOOT-06 (doctor fail-closed behaviour) and T-BOOT-GW / T-BOOT-WRK (package smoke tests) beyond the guide's T-BOOT-01…05 — pending.

## Decisions

Decisions made during implementation that are not yet ADRs (and links to the ADRs that are): `YYYY-MM-DD — decision — rationale — ADR`.

## Open questions

Questions for the human that do not block current work.

- **Q1 (HC-02, topology) — 2026-10-06.** This workstation itself has an **NVIDIA H100 PCIe 80 GB, driver 595.58.03** and a running host **Ollama 0.33.1 on 127.0.0.1:11434** (systemd `ollama`, active). The design assumes the H100 is on a *remote* server reached through an SSH tunnel. Is the "remote GPU server" this same machine, or a second H100 host? If it is this machine, the tunnel (WP0.2, HC-01) could reduce to a loopback/`host.docker.internal` upstream; that is a design change (02, 08 §2) and needs your decision. Blocks: WP0.2 design, not WP0.1.
- **Q2 (port collisions) — 2026-10-06.** Host ports the design fixes are already taken: `127.0.0.1:11434` (host Ollama) and `127.0.0.1:6333-6334` (another project's container `skye-qdrant`). Proposal for WP0.1: publish our services on non-default host ports (e.g. Qdrant 16333, tunnel 21434, Postgres 15432 — 5432 is currently free) via `.env`, without touching other projects' containers. Until then `mesh doctor`'s Qdrant check is a **false positive** (it reaches `skye-qdrant`); WP0.1 will make doctor verify identity (API key), not just reachability.
- **Q3 (GPU sharing) — 2026-10-06.** If this H100 is the measurement GPU, it is shared with other local workloads (several other projects' containers run here). 08 §2.3 requires the card cleared of other workloads before E0 (DN-10).
- **Q4 (CI remote) — 2026-10-06.** Where should this repo be pushed so CI can run (WP-B acceptance)? The workflow is ready (`.github/workflows/ci.yml`); HC-07 covers the test org later.
