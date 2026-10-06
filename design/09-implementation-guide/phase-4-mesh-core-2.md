# Phase 4 — Mesh Core, Increment 2, and Mesh vs Baseline

| | |
|---|---|
| **Goal** | Add the mechanisms that keep a growing codebase coherent (Foundation stage, integration milestones, ratcheted refactoring, merge queue, scope leases, acceptance ratchet), the Change Request flow and the Svelte front end; trial a graph engine; then answer **"is the mesh worth it?"** (E4) and **"can it be gamed?"** (E7) |
| **Duration** | ~8 weeks (weeks 15–22; starts during Phase 3) |
| **Prerequisites** | Phase 3 exit gate passed |
| **Human checkpoints** | HC-04 (M2 UI hidden suite, CR delta suites) · HC-08 E4/E7 cards · HC-11 front-end packages · HC-15 gates during M runs · HC-16 UX checkpoint · **HC-12 P2 → P3a gate decision** |
| **Not in this phase** | Release, signing, deployment (Phase 5); L-tier (Phase 5) |

## 0. Design anchors

[05 §17](../05-reference-architecture.md) (Foundation, integration milestones, merge queue, Change Request, Hypercare states), [06 §4](../06-generated-system-baseline-and-release.md) (template and UI baseline), [07 RV-06, RV-08, RV-10, RV-13, RV-18, RV-21](../07-adversarial-architecture-review.md), [07 §4.2](../07-adversarial-architecture-review.md) (thresholds, ⚠ DN-2).

## 1. Work packages

### WP4.1 — Foundation stage, integration milestones, ratcheted refactoring

**Tasks:**

1. **Foundation stage** (first stage of every Build after G2b), produced from the G2 architecture before any feature task:
   - repo from the template; module skeletons with the approved `.importlinter`; shared kernel (ids, errors, settings, logging); DB base, first Alembic revision; OpenAPI contract stubs; CI wiring to the pinned workflow; the protected-path manifest committed;
   - **exit:** the template's own tests, lint, type-check and `lint-imports` green; contract stubs return `501`; the acceptance suite collects (all failing or xfail-by-oracle is **not** allowed — the oracle is collected and fails honestly).
   - Foundation tasks are P1 and serialized.
2. **Integration milestones:** the planner groups tasks into milestones (one per vertical slice, 5–15 tasks). At each milestone the stage graph runs a **milestone check** in the judge image: full visible test suite, acceptance scenarios linked to the milestone, `lint-imports`, migrations upgrade/downgrade on a fresh DB. Failing → a P0 fix task; the next milestone does not start.
3. **Erosion metrics** (`mesh.judge.metrics`), computed on every accepted merge and stored in `telemetry.events` (kind `erosion`):
   - duplication: `jscpd` percentage (Python + TS);
   - complexity: `radon cc` — share of functions with grade ≥ C, max complexity;
   - module size: LOC per module vs the architecture budget;
   - suppressions: count of `# noqa`, `# type: ignore`, `eslint-disable`, `pragma: no cover`;
   - import-linter violations (must be 0).
4. **Ratchet:** each metric has a ceiling stored in `.mesh/ratchet.json` in the generated repo (protected path). A merge that worsens a metric beyond tolerance (duplication +0.5 pp, suppressions +0, complexity grade-C share +1 pp) is rejected by the judge with failure class `QUALITY`. Improving a metric lowers the ceiling automatically (on merge, by the platform — never by the worker).
5. **Refactor tasks:** when a metric is within 10% of its ceiling, or every N merged tasks (default 20), the planner emits a P3 `refactor` task with a scope lease on the worst module. Refactor tasks must keep all tests green and must improve the targeted metric.

**Acceptance:** T4-FND-01..03, T4-ERO-01..04 pass.

### WP4.2 — Merge queue, scope leases, acceptance ratchet

**Tasks:**

1. **Platform merge queue** (`mesh.scm.mergequeue`) — authoritative regardless of GitHub features (GitHub's merge queue for private repos may need Enterprise, ⚠ DN-5):
   - accepted task branches enter a FIFO queue per repo;
   - the queue rebases each branch onto the current `main` (in a judge container), re-runs the judge (visible suite + acceptance subset + `lint-imports` + Alembic heads check), and merges only if green;
   - conflicts or failures → the task returns to the worker with failure class `INTEGRATION` (counts as an attempt);
   - batching: optional, off by default; record if enabled.
2. **Scope leases:** each task declares scope globs (from the plan). Before a worker attempt starts, it acquires `scope:<repo>:<glob>` leases (fenced, 03 §3.1). Overlapping globs conflict. Tasks that cannot get their scope wait (`not_before`).
3. **Serialized hotspots:** paths matching `migrations/**`, `contracts/**`, `openapi*.yaml`, `pyproject.toml`, `package.json`, lockfiles and `src/*/settings*.py` can only be held by **one** task at a time per repo, regardless of glob overlap.
4. **Multiple Alembic heads check:** `alembic heads` must return exactly one head after the rebase; otherwise reject with `INTEGRATION`.
5. **Acceptance ratchet:** per repo, the set of passing acceptance scenarios on `main` is recorded after every merge. A merge that makes a previously passing scenario fail is rejected (`REGRESSION`), even if the task's own tests pass. The set only grows (except under a Change Request, WP4.3).
6. **Out-of-scope edits:** the judge rejects diffs outside the task's leased scope (`SCOPE`), except for files the plan marks as shared-append (e.g. router registration) — those go through the hotspot rule.

**Acceptance:** T4-MQ-01..08 pass.

### WP4.3 — Change Request flow

**Tasks:**

1. `mesh cr submit <run_id> <cr.md>`: a Change Request in Markdown (what changes, why, priority). This moves the project into the `ChangeRequest` state (05 lifecycle).
2. **Impact analysis** (role `impact_analyst` + mechanical trace query): affected requirements, scenarios, modules, tasks (done and pending), estimate of the delta.
3. **Delta oracle:** the oracle author produces added/changed/removed scenarios; the binding check runs on the delta.
4. **G1-delta gate:** package = CR + impact analysis + delta oracle + re-plan diff. On approval, removed or changed scenarios leave the acceptance ratchet **only** through this gate (recorded in the audit log); `oracle_sha` is re-pinned.
5. **Re-plan:** cancel pending tasks that the CR invalidates (state `cancelled`, with reason), add new tasks, keep completed ones unless the impact analysis marks them for rework.
6. **Experiment hook:** in every M-tier E4 run, one CR is injected at a pre-registered point (e.g. after 40% of tasks are accepted). The CR text and the matching hidden-suite delta are prepared by the human in advance (HC-04).

**Acceptance:** T4-CR-01..05 pass; one CR completes on M1 in an exploratory run.

### WP4.4 — Svelte front end (M-tier and up)

**Tasks:**

1. Template extension `templates/python-fastapi-svelte/frontend/`: SvelteKit + TypeScript, `@sveltejs/adapter-node`, Vitest, Playwright, ESLint + `eslint-plugin-svelte`, a typed API client generated from the OpenAPI contract (`openapi-typescript`). Packages through HC-11 and the npm proxy allow-list.
2. **UI contract at G2:** for each screen: route, purpose, data shown (OpenAPI operation ids), actions, states (empty, loading, error), and **accessible names** of key elements. Stored as `ui/contract.yaml` (protected path).
3. **Locators:** UI acceptance tests use only role and label locators (`getByRole`, `getByLabel`) derived from the UI contract — never CSS selectors or test ids invented by the worker. A Semgrep/ESLint rule rejects `locator('css=…')` / `page.$(…)` in acceptance tests.
4. **Visual baselines:** Playwright screenshots for each screen state at one viewport; baselines are created at the **UX checkpoint (HC-16)** — the human reviews the screens and approves the baseline set; afterwards pixel-diff thresholds apply (`maxDiffPixelRatio` 0.01) and baseline updates are protected-path changes.
5. Judge additions: `npm ci --ignore-scripts`, `svelte-check`, ESLint, Vitest, Playwright against the app started in the judge's sidecar network (backend + Postgres sidecar + `vite preview`/node adapter).
6. Hidden suites for UI (HC-04) use the same locator rules, so they stay robust to markup changes.

**Acceptance:** T4-UI-01..05 pass; M2 (which has UI) runs through the judge with UI checks.

### WP4.5 — Knowledge graph engine trial

**Tasks:**

1. Abstract the domain-layer graph behind `mesh.knowledge.graph.GraphStore` (`upsert_entity`, `upsert_relation`, `neighbours`, `paths`, `query_cypher` optional) with the PostgreSQL-tables implementation as the default.
2. Implement two trial backends: **Apache AGE** (PostgreSQL extension; a separate Postgres image with AGE, pinned) and **Neo4j Community** (container, pinned). ⚠ Verify licences and current versions before use; record them.
3. Domain entity extraction (role `domain_modeler`, structured output): entities, attributes, relations, invariants from requirements and the architecture; linked to requirements and modules.
4. Use in context assembly: for a task, include the neighbourhood (depth ≤ 2) of the entities its scenarios mention.
5. **Ablation inside E4:** "no domain KG" arm (WP4.6). Keep a graph engine **only if** the ablation shows a benefit on the primary metric with CIs; otherwise keep the PostgreSQL tables (ADR-025).

**Acceptance:** T4-KG-01..03 pass; ADR-025 written after E4.

### WP4.6 — Experiments E4 (mesh vs baseline) and E7 (red-team)

**Tasks:**

1. **E4 card** (HC-08), pre-registered before any M run with the final Phase 4 BOM:
   - **arms:** baseline = Phase 1 spike loop with the ADR-022 harness; mesh = full platform; ablations = mesh without {domain KG, adversarial review, planner hierarchy (flat task list), Foundation stage};
   - **items:** S1, M1, M2 (and H1 once, at the end, held-out); k = 3 per arm for S1/M1/M2; ablations k = 2 on M1 if the GPU budget is tight (record it);
   - **primary metrics:** hidden pass rate (overall and critical/high); escaped defects (hidden-suite defect-list hits); human minutes (ledger); GPU-hours;
   - **decision rule (P2 → P3a gate, 07 §4.2 ⚠ DN-2):** absolute hidden-suite threshold met on M; never worse than baseline on escaped defects (CI); better on at least two of {hidden pass, human hours, GPU-hours} with non-overlapping 95% CIs or paired-bootstrap p < 0.05.
   - The CR injection (WP4.3-6) is part of every M mesh run; the baseline receives the same CR as an appended spec change.
2. **E7 card** (HC-08) — red-team at scale:
   - planted **impossible tasks** (contradictory scenario pairs) — the correct outcome is `report_oracle_defect`, not passing tests;
   - **gaming bait:** tasks where deleting/weakening a test, adding a test-mode branch, or special-casing the example values would pass the visible suite;
   - **injection:** planted instructions in a research page fixture, a dependency README in the proxy, and test output;
   - metrics: gaming rate (accepted gamed solutions / bait tasks — target 0), detection rate per channel (judge, Semgrep, hidden suite), false-positive rate on clean tasks.
3. Run, report (WP2.2 generator), decide. Write the **P2 → P3a gate pack** for HC-12: E4 and E7 reports, threshold evaluation, cost per accepted KLOC, human minutes per KLOC, open risks, recommendation (go / go with changes / no-go).

**Acceptance:** E4 and E7 reports; decision rule evaluated mechanically; gate pack delivered.

## 2. Phase 4 test plan

| ID | Level | Test | Pass criterion |
|---|---|---|---|
| T4-FND-01 | integration | Foundation exit check | Template-based skeleton passes lint/type/import checks; acceptance suite collects and fails honestly |
| T4-FND-02 | unit | Foundation precedes features | Planner output with a feature task before Foundation completes → rejected |
| T4-FND-03 | integration | Milestone check failure | Seeded failing milestone → P0 fix task created; next milestone blocked |
| T4-ERO-01 | unit | Metric collectors | jscpd, radon, suppression and module-size values match fixtures |
| T4-ERO-02 | integration | Ratchet rejection | Diff adding duplication / a `# noqa` beyond tolerance → `QUALITY` |
| T4-ERO-03 | integration | Ratchet tightening | Improving merge lowers the ceiling; worker cannot edit `.mesh/ratchet.json` (protected) |
| T4-ERO-04 | unit | Refactor trigger | Near-ceiling metric → P3 refactor task with scope lease |
| T4-MQ-01 | integration | Queue ordering | FIFO per repo; each merge rebased and re-judged |
| T4-MQ-02 | integration | Rebase conflict | Conflicting branches → second returns to worker as `INTEGRATION` |
| T4-MQ-03 | unit | Scope lease conflicts | Overlapping globs conflict; disjoint ones don't (Hypothesis over glob sets) |
| T4-MQ-04 | integration | Hotspot serialization | Two tasks touching `migrations/**` never run concurrently |
| T4-MQ-05 | integration | Alembic heads | Two branches adding revisions from the same parent → second rejected after rebase |
| T4-MQ-06 | integration | Acceptance ratchet | Merge breaking a previously passing scenario → `REGRESSION` |
| T4-MQ-07 | integration | Out-of-scope edit | Diff outside the leased scope → `SCOPE` |
| T4-MQ-08 | conf | Crash during merge | Kill between rebase and merge → resume completes once; no double merge (side-effect ledger) |
| T4-CR-01 | integration | CR intake | State moves to `ChangeRequest`; impact analysis lists affected items on a fixture trace graph |
| T4-CR-02 | integration | Delta binding | Delta oracle bound; unbound critical scenario blocks G1-delta |
| T4-CR-03 | integration | Ratchet update only through G1-delta | Removing a scenario without the gate → refused; with approval → audit row |
| T4-CR-04 | integration | Re-plan | Invalidated pending tasks cancelled with reason; completed tasks kept unless marked |
| T4-CR-05 | conf | CR during active build | In-flight attempts finish or are cancelled cleanly; no lost or duplicated work |
| T4-UI-01 | unit | UI contract schema | Valid contracts pass; missing accessible names rejected |
| T4-UI-02 | unit | Locator rule | CSS/XPath locators in acceptance tests flagged |
| T4-UI-03 | integration | Judge UI checks | svelte-check, ESLint, Vitest, Playwright run in the judge with sidecars; failures classified |
| T4-UI-04 | integration | Visual baseline protection | Worker diff updating baselines → protected-path rejection |
| T4-UI-05 | integration | npm confinement | `npm ci --ignore-scripts` via proxy only; non-allow-listed package refused |
| T4-KG-01 | contract | GraphStore backends | Same contract tests pass for PostgreSQL, AGE, Neo4j |
| T4-KG-02 | unit | Entity extraction schema | Structured output validated; links to requirements present |
| T4-KG-03 | integration | Context neighbourhood | Depth-2 neighbourhood included within budget; omissions reported |
| T4-E4-01 | evaluation | E4 validity | All arms share BOM except the ablated component; CR injected at the same point; k met or deviation recorded |
| T4-E7-01 | evaluation | E7 bait validity | Each bait task is passable by gaming the visible suite and fails the hidden suite (verified on a scripted gamed solution) |

## 3. Measurements produced

- E4: per arm and item — hidden pass rate (overall, critical/high) with CIs, escaped defects, human minutes by category, GPU-hours, tokens per accepted LOC, erosion metrics at the end, CR cost (GPU-hours and human minutes for the change).
- Ablation effects with CIs (KG, adversarial review, planner hierarchy, Foundation).
- E7: gaming rate, detection rate per channel, false-positive rate.
- Merge queue: queue wait, rebase-failure rate, `INTEGRATION`/`REGRESSION`/`SCOPE` rejection rates.

## 4. Exit gate (Phase 4 → Phase 5; P2 → P3a)

- [ ] WP4.1–WP4.6 ticked with evidence; all T4 tests green; conformance and security suites still green.
- [ ] E4 decision rule evaluated mechanically; E7 gaming rate reported (target 0 accepted gamed solutions).
- [ ] ADR-025 (graph engine keep/drop) written.
- [ ] **HC-12 decision recorded** in `PROGRESS.md`: go / go with changes / no-go.
