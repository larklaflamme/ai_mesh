# 09 — Implementation Guide for Claude Code

| | |
|---|---|
| **Status** | v1 — handoff package |
| **Date** | 2026-10-05 |
| **Implements** | [08-prototype-plan.md](../08-prototype-plan.md) |
| **Audience** | Claude Code (implementer) and the human lead (reviewer, owner of human checkpoints) |

This guide turns the prototype plan into executable work. It is written so that Claude Code can take over: each phase document lists **work packages (WP)** with ordered tasks, files to create, interface contracts, **acceptance criteria**, a **phase test plan**, the measurements produced, and an **exit gate**.

## Reading order

| # | Document | Read when |
|---|---|---|
| 0 | [00-ground-rules.md](00-ground-rules.md) | Before anything. Rules, definition of done, coding and security standards |
| 1 | [01-bootstrap.md](01-bootstrap.md) | First session: repo skeleton, conda environment, tooling, CI |
| 2 | [02-remote-ollama-and-tunnel.md](02-remote-ollama-and-tunnel.md) | Before Phase 0 WP0.2 (the human sets up the remote side) |
| 3 | [03-interfaces-and-schemas.md](03-interfaces-and-schemas.md) | Before writing any cross-module code; the shared contracts |
| 4 | [04-test-strategy.md](04-test-strategy.md) | Before writing tests; levels, markers, cassettes, fixtures, CI |
| 5 | [phase-0-environment.md](phase-0-environment.md) | Phase 0 — environment and instrumentation |
| 6 | [phase-1-capability-spike.md](phase-1-capability-spike.md) | Phase 1 — capability spike |
| 7 | [phase-2-harness-benchmark.md](phase-2-harness-benchmark.md) | Phase 2 — harness and benchmark |
| 8 | [phase-3-mesh-core-1.md](phase-3-mesh-core-1.md) | Phase 3 — mesh core, increment 1 |
| 9 | [phase-4-mesh-core-2.md](phase-4-mesh-core-2.md) | Phase 4 — mesh core, increment 2; mesh vs baseline |
| 10 | [phase-5-l-probe-release.md](phase-5-l-probe-release.md) | Phase 5 — L-tier probe and release slice |
| 11 | [99-human-checkpoints.md](99-human-checkpoints.md) | Whenever a WP references an HC-xx |

## Phase map

| Phase | Weeks (indicative) | Gate |
|---|---|---|
| 0 Environment & instrumentation | 1–2 | E0 report; tunnel and gateway proven |
| 1 Capability spike | 3–8 | **Capability gate (pass / pivot / kill)**, HC-06 |
| 2 Harness & benchmark | 6–12 (overlaps 1) | Reproducible harness; model/harness chosen (D2a/D2b/D3) |
| 3 Mesh core 1 | 10–16 | S1 end-to-end through G1/G2/G2b; conformance and security suites green |
| 4 Mesh core 2 | 15–22 | Mesh vs baseline (E4) meets thresholds, HC-12 |
| 5 L-probe & release | 20–26 | Scale curve; signed release rehearsed; decision pack |

## How Claude Code should operate

1. **One work package at a time**, in the order given in `PROGRESS.md`. WPs inside a phase are ordered by dependency. Parallel work is fine only where the WP says "independent".
2. **Tests belong to the WP.** A WP is not done until its listed tests exist and pass. Test IDs (e.g. `T0-GW-03`) must appear in the test function's docstring, so a test report can be traced back to this guide.
3. **Evidence over assertion.** When ticking a WP, cite test names, `make` targets, or report files.
4. **Stop at human checkpoints.** Prepare everything around the checkpoint (drafts, scripts, a clear question), then stop and ask.
5. **Experiments are pre-registered.** Never run a measured experiment (E0–E7) without a card in `benchmark/experiments/` that the human has approved (HC-08). Exploratory runs are fine, but they are labelled `exploratory` and excluded from reports.
6. **Keep the design and the code consistent.** Record any deviation in `PROGRESS.md` → "Deviations" with the reason. Propose design-doc updates; do not edit `design/00–08` unless asked.

## Glossary

| Term | Meaning |
|---|---|
| Workspace | Ephemeral container in which a worker (agent harness) edits code for one task attempt |
| Judge | Platform component that decides pass/fail **by running checks itself**, in its own container, against a pinned oracle |
| Oracle | The approved acceptance tests (visible). The **hidden suite** is a separate, sealed set that only the harness and judge run, and only for scoring |
| Gateway | `mesh-gateway`: the only path to the LLM. Attributes, meters and enforces budgets |
| Virtual key | Per-task API key issued by the platform; the gateway maps it to run/task/role/attempt |
| Run | One execution of the platform (or spike loop) on one benchmark item with one configuration; has a manifest |
| BOM | Bill of materials of a run: platform SHA, role/prompt SHA, model digest, configs |
| Infra failure | Failure not caused by the agent (tunnel down, OOM-kill, container start timeout). Never consumes a task attempt |
| S / M / L | Project size tiers: ~5–10k / ~40–60k / ≥100k LOC |
