# Phase 2 — Evaluation Harness and Benchmark

| | |
|---|---|
| **Goal** | Make measurement honest and repeatable: pre-registered experiments, repeats, confidence intervals, a larger and validated benchmark, the remaining harness adapters, the model/harness/engine decision (D2a, D2b, D3), and a human baseline |
| **Duration** | ~6 weeks (weeks 6–12; starts during Phase 1) |
| **Prerequisites** | Phase 0 exit; Phase 1 WP1.1–WP1.4 done (images, sandbox, adapters, judge) |
| **Human checkpoints** | HC-04 (S2, M2, H1 hidden suites) · HC-08 (cards) · HC-10 (oracle-strength threshold) · HC-13 (vLLM on the remote server, optional) · HC-14 (S-cal human build) |

## 1. Work packages

### WP2.1 — Experiment runner (`mesh.evaluation.runner`)

**Tasks:**

1. `ExperimentCard` Pydantic model ([08 §6.2](../08-prototype-plan.md)) with these fields:
   - `id`, `question`, `hypothesis`;
   - `configs` (each a model ref + quant + adapter + engine + Ollama env hash);
   - `dataset`, `repeats`, `budget`, `primary_metric`, `secondary`, `decision_rule`;
   - `frozen_bom: true`, `approved_by`, `approved_at`, `status`.
2. `mesh exp plan <card>` expands the card into a run matrix (config × item × repeat), with seeds derived deterministically: `seed = hash(card_id, config_id, item, repeat)`.
3. `mesh exp run <card>` executes the matrix sequentially (single GPU).
   - **Before every run:** check readiness and a BOM consistency guard. Platform SHA, roles SHA, model digest and Ollama env hash must equal the values fixed at the first run of the experiment; otherwise the runner **refuses** and asks.
   - The runner is resumable. Failed runs are recorded, never silently dropped.
4. Model switching between configs: for Ollama, a deliberate unload/load step with warm-up, recorded as an event, and excluded from metrics.
5. GPU-hour budget enforcement per card. Exceeding it stops the experiment and asks the human.

**Acceptance:** T2-RUN tests pass. A dry-run of the E3 card shows the full matrix and its estimated GPU-hours.

### WP2.2 — Analysis and reporting (`tools/analysis`, `mesh.evaluation.report`)

**Tasks:**

1. Nightly and on-demand export of the `telemetry` tables to Parquet (`runs/_parquet/<table>/date=…`). DuckDB views for runs, attempts, tasks, calls and scores.
2. **Statistics** (`mesh.evaluation.stats`):
   - percentile bootstrap CIs (10,000 resamples, seeded) for rates and medians;
   - **paired** comparisons on the same tasks: paired bootstrap of differences, McNemar's test for pass/fail;
   - Wilson intervals for single proportions;
   - effect sizes reported alongside p-values;
   - for multi-config comparisons, best-config CI overlap per the card's decision rule.
3. **Report generator:** a Markdown report plus PNG charts (matplotlib) per run and per experiment:
   - manifest summary;
   - primary and secondary metrics with CIs;
   - failure taxonomy;
   - cost breakdown;
   - **decision-rule outcome**, evaluated mechanically from the card;
   - validity check results;
   - deviations.
4. A test-ID trace report ([04 §1](04-test-strategy.md)).

**Acceptance:** T2-STAT and T2-REP pass. The E1 report from Phase 1 is regenerated with CIs.

### WP2.3 — Benchmark v1

**Tasks:**

1. **Micro-benchmark** grown to 150 tasks (target 100–300). Sources:
   - the S1 reference;
   - the S2 reference (new S project, written in the same way as S1);
   - **permissively licensed open-source FastAPI repositories with real tests**.
2. **Derivation tool** `mesh bench derive --from <repo@sha> --target <symbol>`:
   - stubs out the target implementation (raise `NotImplementedError`);
   - verifies that the visible tests fail on the stub and pass on the original;
   - emits a task folder.

   Hidden counterparts are supplied by the human (HC-04), or derived from held-back original tests that the human moves to the hidden repo.
3. **Licence check:** every external source repo is recorded in `benchmark/SOURCES.md` with its licence. Only MIT, Apache-2.0 or BSD. Contamination note: public repos may be in training data, so they are tagged `contamination: likely`, and capability claims are reported separately for `none-known` items.
4. **New project specs** (Claude Code drafts, human reviews at HC-05; hidden suites by humans at HC-04):
   - S2;
   - M2;
   - **H1 held-out**: M-tier, authored by a customer SME. Never used for tuning; run only at phase exits.
5. **RealWorld (Conduit) API** as a calibration item:
   - verify the licence and the test collection (⚠ before use);
   - label it `contamination: likely`;
   - harness calibration only.

**Acceptance:** `mesh bench validate` passes for all items (T-EVL-01, -04, -05). `SOURCES.md` is complete.

### WP2.4 — Additional worker adapters

**Tasks:**

1. **OpenHands adapter:**
   - the OpenHands Software Agent SDK running **inside** the workspace container in local-workspace mode, rooted at `/workspace`;
   - LLM configured to the gateway's OpenAI-compatible endpoint with `MESH_KEY`;
   - OpenHands' own browser, web and MCP tools disabled (only our network allows anything anyway);
   - verify the current SDK API.
2. **OpenCode adapter:**
   - OpenCode's non-interactive or headless mode inside the container, with a custom OpenAI-compatible provider pointing to the gateway;
   - verify the current CLI.
3. **Drop rule:** if a harness cannot be confined (needs Docker-in-Docker, insists on its own network access, cannot use a custom base URL), record that in an ADR and drop it.

**Acceptance:** T2-AD tests pass for every retained adapter.

### WP2.5 — Oracle-strength validation

**Tasks:**

1. `mesh bench mutate <item>` runs mutmut on the reference implementation with the **hidden** suite as the test command, inside the judge image, with the hidden suite mounted read-only. It reports the mutation score only.
2. The threshold (proposed: ≥ 70% killed, excluding equivalent mutants by sampling) is approved at HC-10.
3. Items below the threshold need hidden-suite strengthening by humans before use in `measured` runs.

**Acceptance:** every benchmark item has a recorded mutation score ≥ threshold, or is excluded.

### WP2.6 — Experiment E3: model, quantization, harness and engine bake-off

**Tasks:**

1. Card `E3-bakeoff.yaml`:
   - **configs:** the HC-03 model list × quantization {4, 6, 8-bit where available} × adapters {single_loop, deepagents, + retained ones}, pruned to ≤ 12 configs by E1/E0 evidence;
   - **dataset:** 150 micro tasks; k=3;
   - **primary metric:** accepted tasks per GPU-hour, at a hidden pass rate whose CI overlaps the best;
   - **secondary:** output tokens per accepted LOC, TTFT, escalation rate, cached-prefix ratio.
2. **Optional arms**, if E0 showed prefix-cache problems:
   - **vLLM:** the human deploys vLLM on the remote server behind the same tunnel port scheme (HC-13); the gateway upstream switches by config; the run manifest records the engine;
   - **planner/worker pair:** dense 27B for planning and review plus an MoE A3B worker, both resident. E0 must confirm the memory fit, with `OLLAMA_MAX_LOADED_MODELS=2`.
3. Run, report, decide. Write ADRs:
   - **ADR-020** primary model and quantization (D2a);
   - **ADR-021** serving engine (D2b);
   - **ADR-022** worker harness (D3).

**Acceptance:** the decision rule is evaluated mechanically and the three ADRs are written.

### WP2.7 — Human baseline calibration (S-cal)

**Tasks:**

1. A small human team builds the S2 project (or a dedicated S-cal spec) with the ledger running for all work (HC-14).
2. Before starting, the team produces a Wideband Delphi estimate for S2 and for M1/M2.
3. Compare actual vs Delphi for S2 → a Delphi bias factor applied to the O2 baselines (07 RV-07).
4. Run the hidden suite on the human build: this gives the human quality baseline.

**Acceptance:** S-cal report with actual hours by category, Delphi bias, and hidden pass rate.

### WP2.8 — Reproducibility study

**Tasks:**

1. Re-run E1's best configuration on 50 tasks with k=3 and new seeds.
2. Check T-EVL-03 (primary metric within ±5 pp). If it fails, increase the default k for measured runs and record that in the runner defaults.

**Acceptance:** reproducibility report; the default k is set.

## 2. Phase 2 test plan

| ID | Level | Test | Pass criterion |
|---|---|---|---|
| T2-RUN-01 | unit | Card validation | Missing approval → `measured` run refused; schema errors reported |
| T2-RUN-02 | unit | Seed derivation | Deterministic; distinct across repeats and configs |
| T2-RUN-03 | integration | BOM guard | Change `roles_sha` mid-experiment → next run refused with a clear message |
| T2-RUN-04 | conformance | Resume | Kill during an experiment; resume continues at the next pending run; no duplicates |
| T2-RUN-05 | integration | Budget stop | GPU-hour budget exceeded → experiment paused; human asked |
| T2-RUN-06 | integration | Model switch hygiene | Load/unload recorded as events and excluded from metrics |
| T2-STAT-01 | unit | Bootstrap CI | Coverage ≈ nominal on synthetic data with known parameters (simulation, seeded) |
| T2-STAT-02 | unit | Paired comparison | McNemar and paired bootstrap match reference values on fixtures |
| T2-STAT-03 | unit | Wilson interval | Matches reference values |
| T2-STAT-04 | unit | Decision rule evaluator | Each rule type evaluated correctly on fixtures, including ties and overlapping CIs |
| T2-REP-01 | integration | Report generation | All sections present; numbers match direct SQL queries on fixtures |
| T2-REP-02 | unit | Exploratory exclusion | `exploratory` and `test` runs never appear in experiment reports |
| T2-BEN-01 | integration | Derivation tool | Stubbed target → visible tests fail; original → pass; task folder valid |
| T2-BEN-02 | unit | Licence gate | Non-allowed licence → derivation refused |
| T2-BEN-03 | evaluation | Validity suite on all items | T-EVL-01/04/05 pass |
| T2-BEN-04 | evaluation | Oracle strength | Mutation score ≥ threshold, or item excluded |
| T2-AD-01..n | contract | New adapters | Same contract tests as T1-AD-01..03, plus confinement: no network beyond the gateway and proxies, no Docker-in-Docker |
| T2-REPRO-01 | evaluation | T-EVL-03 | Primary metric within ±5 pp across repeats, or k raised |

## 3. Measurements produced

- E3 bake-off report and ADR-020/021/022.
- Benchmark v1 inventory with validity and mutation scores.
- S-cal human baseline (hours by category, Delphi bias, hidden pass rate).
- Reproducibility report and default k.

## 4. Exit gate (Phase 2 → Phase 3 completion)

- [ ] WP2.1–WP2.8 ticked; all T2 tests green.
- [ ] Harness reproducible (T-EVL-03) and defaults set.
- [ ] D2a, D2b, D3 decided with ADRs.
- [ ] Benchmark v1 validated; H1 sealed and unused.
