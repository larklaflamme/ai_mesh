# Phase 5 — L-Tier Probe and Release Slice

| | |
|---|---|
| **Goal** | (1) Measure how the mesh behaves as size grows toward L-tier (E5, the scale curve). (2) Prove the release path end to end on the workstation: build once, SBOM, signing, G3 promotion attestation, rehearsal on Compose and Kubernetes (install / upgrade / rollback), offline bundle, deploy state machine, and one hotfix through Hypercare. (3) Produce the decision pack for P3a |
| **Duration** | ~7 weeks (weeks 20–26; starts during Phase 4) |
| **Prerequisites** | Phase 4 exit gate passed with HC-12 = go or go-with-changes (E5 may start once WP4.1–4.2 are done; the release slice needs only WP3.x) |
| **Human checkpoints** | HC-04 (L-probe hidden suite) · HC-08 E5 card · HC-17 release signing keys · HC-15 G3 approval (as the client) · HC-18 decision pack review |
| **Not in this phase** | Real client sites, GitOps (mode B), OpenBao, the production project node. Those belong to P3a/P3b |

## 0. Design anchors

[06 §5–§9, §11](../06-generated-system-baseline-and-release.md) (release model, delivery modes, deploy state machine, site profile), [05 §17](../05-reference-architecture.md) (Hypercare, Maintenance), [07 RV-15, RV-16, RV-19, RV-30](../07-adversarial-architecture-review.md).

**Prototype simplifications (record them in the decision pack):**

| Production design | Prototype |
|---|---|
| Signing key in OpenBao, used only by the release workflow | cosign key pair on the workstation in `infra/secrets/release/` (gitignored), password from a prompt or `COSIGN_PASSWORD` set only for the release command; **never** mounted into workspaces or the judge |
| Self-hosted runner on the project node | Release pipeline runs as `mesh release …` CLI on the workstation, in a dedicated `release` container with no agent code |
| Client registry | Local `registry:2` (compose profile `release`) on `127.0.0.1:5000` |
| Client hosts | A **fake client** Compose host — a small local VM (preferred) or a container with its own Docker engine under `sysbox`; **not** a privileged `docker:dind` — reached over SSH; plus a **kind** cluster. Record the choice in ADR-026 |
| Transparency log | None: `cosign sign --tlog-upload=false`, verification with `--insecure-ignore-tlog` (offline, on-prem policy) ⚠ verify flag names for the pinned cosign |

## 1. Work packages

### WP5.1 — Experiment E5: L-tier probe and scale curve

**Tasks:**

1. **L-probe spec** (Claude Code drafts, human reviews at HC-05; hidden suite by humans at HC-04): 3–5 modules, target ≥ 30–50k LOC, with **frozen contracts** between modules (OpenAPI + shared schemas approved at G2 and protected).
2. **E5 card** (HC-08):
   - one mesh run (k = 1 is acceptable for the probe; k = 2 if budget allows — record it);
   - checkpoints at every 5k LOC accepted: hidden pass rate on the modules completed so far, erosion metrics, escalations per KLOC, GPU-hours per KLOC, human minutes per KLOC, merge-queue rejection rates, context-budget pressure (share of calls with omissions);
   - **scale curve:** these metrics vs accepted LOC, with S1/M1/M2 from E4 as earlier points.
3. **Stop rules** (pre-registered): stop and report if escalations/KLOC exceed 3× the M-tier value for two consecutive checkpoints, or if the GPU-hour budget is exhausted.
4. Report with a projection to 100k / 150k LOC (explicitly labelled as extrapolation, with the assumptions) and an updated estimate for 02 §10.

**Acceptance:** E5 report with the scale curve and the stop-rule outcome.

### WP5.2 — Release pipeline (`mesh.release`)

**Tasks:**

1. **Build once:** `mesh release build <run_id> --version <semver>-rc.<n>` in the release container:
   - builds backend and frontend images from the accepted `main` sha with `docker buildx` (reproducible flags: `SOURCE_DATE_EPOCH`, no cache from untrusted layers);
   - pushes to the local registry; records **digests**; everything after this step refers to digests only.
2. **Evidence:** Syft SBOM (SPDX JSON) per image; Trivy vulnerability report (offline DB snapshot, pinned date); licence check against the allow-list; `helm lint` + `kubeconform`; `docker compose config` validation; Trivy config scan of Compose and Helm.
3. **Signing:** `cosign sign` each image digest; `cosign attest` the SBOM (predicate type SPDX) and a **build provenance** statement (SLSA-style: source repo, sha, builder = release container image digest, run_id, BOM).
4. **Release candidate record:** `runs/<run_id>/release/<version>/rc.json` = image digests, chart and bundle hashes, SBOM hashes, test evidence (acceptance on the rehearsal targets), vulnerability summary. Audit log entry.
5. **Rehearsal (WP5.3)** must pass before G3 can be requested.
6. **G3 gate:** package = rc.json + rehearsal reports + vulnerability summary with dispositions + runbook + release notes. On approval the approver also signs the **promotion attestation** (`cosign attest --predicate promotion.json` listing approved digests and artifact hashes, signed with the approver's release key — HC-17). The deploy step refuses digests not in a verified promotion attestation.
7. **Offline bundle (mode C):** `mesh release bundle <version>` → `app-<version>-offline.tar` with OCI image tarballs (`docker save` by digest), Compose bundle, packaged Helm chart, `values-site.yaml.example`, SBOMs, attestations, public keys, runbook, `install.sh`/`upgrade.sh`/`rollback.sh`/`smoke.sh`/`verify.sh`, and `SHA256SUMS` signed with cosign `sign-blob`. `verify.sh` checks checksums, signatures and the promotion attestation **before** loading anything.

**Acceptance:** T5-REL-01..08 pass.

### WP5.3 — Rehearsal and deploy state machine (`mesh.deploy`)

**Tasks:**

1. **Targets** described by site profiles (06 §9) in `infra/local/sites/`:
   - `fake-compose.yaml`: SSH host, deploy user, registry mode = `load` (images transferred and `docker load`ed);
   - `kind.yaml`: kind cluster `mesh-rehearsal`, namespace-scoped kubeconfig for a ServiceAccount with a Role limited to that namespace, registry = local registry connected to the kind network.
2. **Fake client Compose host:** a deploy user with a **forced command** wrapper (`command="/usr/local/bin/mesh-deploy-shim",restrict` in `authorized_keys`) that allows only `load <tar>`, `up <bundle-dir>`, `down`, `ps`, `rollback <version>`, `smoke`. Everything else is refused and logged.
3. **Deploy state machine** (persisted in `platform.deploys`, new table: `deploy_id, run_id, site, version, digests, state, intent_at, dispatched_at, observed, decided_by`):
   `planned → preflight_ok → intent_recorded → dispatched → observed_healthy | observed_failed → (rolled_back) → closed`.
   - pre-flight per 06 §9 (connectivity, registry/load path, namespace permissions, disk space on the host);
   - the intent is recorded **before** dispatch; after a crash the state is **reconciled** from the target (`ps` / `helm status`), never auto-retried; a human decides (`mesh deploy decide <id> retry|rollback|abandon`);
   - Kubernetes: `helm upgrade --install --atomic --wait --timeout 10m` with digests from the promotion attestation; Compose: idempotent `docker compose up -d` with digest-pinned images;
   - verification before deploy: `cosign verify` + `cosign verify-attestation` for every digest (Kubernetes: also a Kyverno `verifyImages` policy in the kind cluster — ⚠ pin Kyverno; optional if time is short, record it).
4. **Rehearsal script** `mesh release rehearse <version> --site fake-compose --site kind`, for each site:
   install previous release (or empty) → run smoke + acceptance suite against the deployed URL → upgrade to the RC → smoke + acceptance → **rollback** to the previous release → smoke → upgrade again. Data continuity: seed data created before the upgrade must survive upgrade and rollback (Alembic downgrade policy from 06 applies; record if a migration is irreversible).
5. **Offline bundle rehearsal** (because the prototype has no mode-C site, run it once anyway as a test): on a clean fake host, `verify.sh && install.sh && smoke.sh` using only the bundle (no registry access, no internet — enforce with the network config).

**Acceptance:** T5-DEP-01..09 pass; rehearsal report for both target types.

### WP5.4 — Hypercare and hotfix path

**Tasks:**

1. After G3 and deploy to both rehearsal targets, the project enters **Hypercare** (05 lifecycle): incidents are filed with `mesh incident open <run_id> <incident.md>`.
2. **Hotfix flow:** incident → triage role (structured output: severity, suspected area, reproduction steps) → a **failing regression test first** (test author; the human approves it as an oracle addition through a lightweight `hotfix` gate) → worker fix → judge (full suite + acceptance ratchet) → patch release (`x.y.z+1`) through WP5.2 (build, sign, rehearse, G3) → deploy → close.
3. **Exercise:** the human plants one realistic defect report (from the hidden defect list of the probe or S1) after deployment; measure time-to-fix, GPU-hours, human minutes, and whether the regression test would have caught the original defect.
4. After the hypercare window (configurable; 1 day in the prototype), the project moves to **Maintenance** (queues P3 refactor and dependency-update tasks only on request).

**Acceptance:** T5-HC-01..04 pass; hotfix exercise report.

### WP5.5 — Decision pack for P3a

**Tasks:**

1. Assemble `reports/decision-pack-P3a.md` (HC-18):
   - capability and scale: E2, E4, E5 results with CIs; scale curve; projection with assumptions;
   - quality: hidden pass rates, escaped defects, E7 gaming/detection;
   - cost: GPU-hours and human minutes per accepted KLOC; comparison with the S-cal human baseline and the Delphi-corrected estimates;
   - durability and security: T-DUR/T-SEC status, E6 results;
   - release: rehearsal results, prototype simplifications that P3a must replace (signing key custody, runner, registry, site pre-flight);
   - updated risks; open decisions DN-1…DN-8 with the evidence gathered for each;
   - recommendation: go to P3a on the real project node / go with changes / pivot / stop.
2. Propose updates to design docs 01, 02, 05, 06 (as a list of diffs for the human to accept; do not edit them directly unless asked).

**Acceptance:** decision pack delivered; HC-18 review recorded.

## 2. Phase 5 test plan

| ID | Level | Test | Pass criterion |
|---|---|---|---|
| T5-E5-01 | evaluation | E5 validity | Frozen contracts unchanged during the run (protected); checkpoints recorded every 5k LOC; stop rules evaluated mechanically |
| T5-REL-01 | integration | Build once | Two builds of the same sha produce the same digests, or the difference is explained and recorded (reproducibility note) |
| T5-REL-02 | integration | Digest-only downstream | Any step referencing an image by tag instead of digest fails |
| T5-REL-03 | integration | Signatures | `cosign verify` passes with the release key; fails with another key and for an unsigned digest |
| T5-REL-04 | integration | SBOM attestation | `cosign verify-attestation --type spdxjson` passes; SBOM lists the lockfile packages |
| T5-REL-05 | integration | Promotion attestation required | Deploy of a signed digest **not** in the promotion attestation → refused |
| T5-REL-06 | integration | Key isolation | Release key and approver key absent from workspace, judge and gateway containers (filesystem and env scan) |
| T5-REL-07 | integration | Offline bundle integrity | Tampering with any file in the bundle → `verify.sh` fails before loading anything |
| T5-REL-08 | integration | G3 hash/signature | Same fail-closed behaviour as T3-GATE-02..06 for G3 |
| T5-DEP-01 | integration | Pre-flight | Missing permission / unreachable host / low disk → `preflight_failed`, no dispatch |
| T5-DEP-02 | integration | Forced-command shim | Any command outside the allowed set refused and logged |
| T5-DEP-03 | integration | Namespace scope | Kubeconfig cannot create resources outside the namespace or cluster-scoped resources |
| T5-DEP-04 | e2e | Rehearsal — Compose | install → upgrade → rollback → upgrade; smoke + acceptance pass at each step; seed data survives |
| T5-DEP-05 | e2e | Rehearsal — kind | Same as DEP-04 with `helm --atomic` |
| T5-DEP-06 | conf | Crash after intent, before dispatch | Reconciled to `intent_recorded`; no dispatch without a human decision |
| T5-DEP-07 | conf | Crash after dispatch | State reconciled from the target; never auto-retried; human decision required |
| T5-DEP-08 | integration | Failed upgrade | Helm `--atomic` rolls back; Compose rollback script restores the previous digests; state `observed_failed → rolled_back` |
| T5-DEP-09 | e2e | Offline install | Clean host with no network: verify + install + smoke from the bundle only |
| T5-HC-01 | integration | Incident intake | Incident moves the project to a hotfix path; triage output validated |
| T5-HC-02 | integration | Regression test first | Fix task cannot start until the failing regression test is approved and fails on the current release |
| T5-HC-03 | e2e | Patch release | Patch goes through build/sign/rehearse/G3/deploy; ratchet intact |
| T5-HC-04 | unit | Lifecycle transitions | Hypercare → Maintenance only after the window and no open P0/P1 incidents |

## 3. Measurements produced

- E5 scale curve and projection; erosion trends; escalations/KLOC; context-budget pressure.
- Release: build time, reproducibility of digests, SBOM size, vulnerability counts by severity, rehearsal duration per target, rollback time.
- Deploy: pre-flight failure reasons, reconcile cases.
- Hotfix: time-to-fix, GPU-hours, human minutes.

## 4. Exit gate (end of prototype)

- [ ] WP5.1–WP5.5 ticked with evidence; all T5 tests green; conformance and security suites still green.
- [ ] E5 report and scale curve published.
- [ ] Signed release rehearsed on Compose and kind (install / upgrade / rollback) and as an offline bundle.
- [ ] One hotfix delivered through Hypercare.
- [ ] ADR-026 (fake client host) and ADR-027 (prototype release simplifications and their P3a replacements) written.
- [ ] **HC-18 decision recorded** in `PROGRESS.md`.
