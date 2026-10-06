# 99 — Human Checkpoints (HC-01 … HC-18)

A **human checkpoint** is a point where Claude Code must stop and hand over to a person. Some checkpoints exist because only a human can do the work (remote server, keys, hidden suites). Others exist because the decision must stay with a human (thresholds, go/no-go, dependency trust).

## How a checkpoint works

1. **Prepare.** Claude Code does everything around the checkpoint: drafts, scripts, checklists, a short explanation, and one clear question or action.
2. **Ask.** It writes an entry in `PROGRESS.md` → "Human checkpoints" with the status `waiting`, the HC id, what is needed, where the material is, and what is blocked. It then tells the human and stops work that depends on the checkpoint. Independent work may continue only if the WP says it is independent.
3. **Record.** When the human responds, Claude Code records the outcome (`done` / `decided: …`), the date, who decided, and the evidence (commit, file, signature, report). Decisions that change design go to an ADR.
4. **Never simulate.** Claude Code never fills in a human's part: no self-approved gates, no self-written hidden suites, no invented hardware facts, no generated keys for approvers.

## Summary

| HC | Name | Phase | Blocks | Owner |
|---|---|---|---|---|
| HC-01 | Remote GPU server setup | 0 | WP0.2 onward (anything needing the LLM) | Infra lead |
| HC-02 | Workstation facts | B/0 | Image architecture choices; E0 manifest | Human lead |
| HC-03 | Model list and digests | 0 | E0, E1 | Tech lead |
| HC-04 | Hidden suites and defect lists | 1, 2, 4, 5 | Measured runs on that item | QA lead / SME (not Claude Code) |
| HC-05 | Benchmark spec review | 1, 2, 5 | Hidden-suite authoring; runs on that item | Tech lead + SME |
| HC-06 | Capability gate decision | 1 | Phase 3 | Steering (customer + tech lead) |
| HC-07 | GitHub test organization and App | 3 | WP3.6, S1 end-to-end on GitHub | GitHub admin |
| HC-08 | Experiment card approval | 0–5 | Any `measured` run of that experiment | Tech lead |
| HC-09 | Gate approver keys | 3 | WP3.3 approvals | Each approver |
| HC-10 | Checks and thresholds | any | The change in question | Tech lead + QA lead |
| HC-11 | New dependencies in workspaces/template | any | Allow-list change | Security lead |
| HC-12 | P2 → P3a gate | 4 | Phase 5 release slice beyond preparation; P3a | Steering |
| HC-13 | vLLM on the remote server (optional) | 2 | E3 vLLM arm only | Infra lead |
| HC-14 | S-cal human baseline build | 2 | WP2.7 | Human dev team |
| HC-15 | Acting as client at gates | 3–5 | Progress of that run past G1/G2/G2b/G3 | Human lead (client role) |
| HC-16 | UX checkpoint | 4 | Visual baselines for that project | UX/product reviewer |
| HC-17 | Release signing keys | 5 | WP5.2 signing and promotion | Security lead + approver |
| HC-18 | Decision pack review | 5 | End of prototype | Steering |

## Details

### HC-01 — Remote GPU server setup

- **Human does:** Part A of [02-remote-ollama-and-tunnel.md](02-remote-ollama-and-tunnel.md): GPU cleared of other workloads, driver pinned, Ollama configured with the override file, models pulled from official sources, GPU exporter on `127.0.0.1:9835`, restricted `mesh-tunnel` user with the `authorized_keys` line for the workstation's public key.
- **Claude Code prepares:** the tunnel key pair (public key printed for the human), the exact `authorized_keys` line, the `sshd` Match block, and the verification checklist V-01…V-10.
- **Evidence:** V-01…V-10 pass from the workstation; `/api/tags` output with digests saved to `infra/remote/models.lock`; Ollama version and env hash recorded.
- **Never:** Claude Code does not log in to the remote server and does not ask for credentials other than the tunnel key it generated.

### HC-02 — Workstation facts

- **Human provides:** OS and version, CPU architecture (x86_64 or arm64), RAM, free disk, Docker Engine/Desktop version, whether Docker runs rootless, and whether the workstation is the Ubuntu dev machine or another one (the repo path suggests `/Users/...`). ⚠ This matters for networking (`host.docker.internal` vs `172.29.0.1`) and for multi-arch images.
- **Claude Code prepares:** a `mesh doctor` output and the questions it cannot answer by itself.
- **Evidence:** `PROGRESS.md` → Environment filled in.

### HC-03 — Model list and digests

- **Human decides:** which candidate models and quantizations enter E0/E1 (from the shortlist in 02/08), within licence constraints the customer accepts.
- **Claude Code prepares:** a table of candidates with sizes, context limits, licence, expected VRAM at 64K context with q8_0 KV cache, and the `ollama pull` names.
- **Evidence:** `infra/remote/models.lock` with name, tag, digest, licence; ADR if a candidate is excluded for licence reasons.

### HC-04 — Hidden suites and defect lists

- **Human does:** writes (or commissions) the hidden acceptance suite and the hidden defect list for each benchmark item in the separate private repo `ai_mesh-hidden`, with priority markers; prepares CR delta suites for E4 and the L-probe suite for E5. Alternatively, a **separate, isolated Claude session in a separate repository** may draft them, and a human verifies them; that session must never see the platform repo, prompts or roles.
- **Claude Code prepares:** the spec (HC-05), the marker conventions, and the `meta.yaml` fields; it receives only `<id>@<sha>` references.
- **Evidence:** `MESH_HIDDEN_ROOT` refs recorded in `benchmark/projects/<id>/meta.yaml`; T-EVL validity checks pass; mutation score (WP2.5) recorded.
- **Never:** Claude Code does not open, read, list, grep or summarize anything under `MESH_HIDDEN_ROOT` (ground rule R3). The harness mounts it read-only into the judge only.

### HC-05 — Benchmark spec review

- **Human does:** reviews the requirements, Gherkin features and example tables Claude Code drafted for S1, M1, L-slice, S2, M2, the L-probe; corrects ambiguity; approves.
- **Evidence:** spec commit tagged `spec-<id>-v<n>`; approval line in `PROGRESS.md`.

### HC-06 — Capability gate decision

- **Human decides:** pass / pivot (with the chosen change, e.g. different model, harness or scope) / kill, using the capability gate pack from WP1.8 and the thresholds in 07 §4.2 (⚠ DN-2).
- **Evidence:** decision, date and rationale in `PROGRESS.md`; ADR if it pivots.

### HC-07 — GitHub test organization and App

- **Human does:** creates the test org, the `mesh-platform-workflows` repo, and the `mesh-delivery` GitHub App with only `contents: write`, `pull_requests: write`, `checks: read`, `metadata: read` (no `workflows`, `administration`, `secrets`, `members`); installs it; stores the private key outside the repo; sets branch protection/rulesets and CODEOWNERS.
- **Claude Code prepares:** the exact permission list, the ruleset settings, the CODEOWNERS file, and the T3-GH test plan.
- **Evidence:** T3-GH-01 output showing the App cannot write workflow files; ADR-024.

### HC-08 — Experiment card approval

- **Human does:** reviews the card (question, hypothesis, configs, dataset, repeats, budget, metrics, decision rule) **before** any measured run, then sets `approved_by`/`approved_at`.
- **Rule:** after approval the card and the BOM are frozen. Any change → new card version and new approval.
- **Evidence:** the approved card in `benchmark/experiments/`, committed.

### HC-09 — Gate approver keys

- **Human does:** each approver creates an SSH signing key on their own machine (`ssh-keygen -t ed25519 -f ~/.ssh/mesh_approver`), sends the public key; it is added to `infra/approvers/allowed_signers` with the approver's identity and the `namespaces="mesh-gate"` option.
- **Never:** approver private keys on the workstation's shared paths, in `.env`, in containers, or anywhere Claude Code operates. In the prototype the human lead may use the workstation, but the key stays in their home directory and is passed only via `MESH_APPROVER_SSH_KEY` to the `mesh gate approve` command they run themselves.

### HC-10 — Checks and thresholds

- **Trigger:** any proposal to change a check, a threshold, a budget, the protected-path manifest, the ratchet tolerances, the oracle-binding or mutation thresholds, or the judge's behaviour.
- **Human decides:** approve or reject the change; Claude Code never weakens a check on its own (ground rule R1).
- **Evidence:** PR with the change, linked issue, approval comment; `PROGRESS.md` → Decisions.

### HC-11 — New dependencies in workspaces or the template

- **Trigger:** any package added to `infra/local/allowlist/pypi.txt` / `npm.txt`, to the template's lockfiles, or to the workspace/judge images.
- **Human checks:** name, maintainer, age, download history, licence (MIT/Apache-2.0/BSD/ISC/PSF unless approved), known vulnerabilities; then approves the PR.
- **Evidence:** PR approved by the security lead.

### HC-12 — P2 → P3a gate

- **Human decides:** go / go with changes / no-go based on the E4/E7 gate pack and 07 §4.2 thresholds (⚠ DN-2).
- **Evidence:** decision in `PROGRESS.md`; any changes become WPs or ADRs.

### HC-13 — vLLM on the remote server (optional)

- **Human does:** deploys vLLM (pinned version and image digest) on the remote server, bound to `127.0.0.1:<port>`, and extends the tunnel `PermitOpen` list; or declines.
- **Claude Code prepares:** the gateway upstream switch, the model/quantization mapping and the comparison plan inside E3.

### HC-14 — S-cal human baseline build

- **Human team does:** produces Wideband Delphi estimates first, then builds S2 (or the S-cal spec) with the ledger running for all work.
- **Claude Code prepares:** the ledger categories, the Delphi worksheet, and the analysis script.

### HC-15 — Acting as client at gates

- **Human does:** answers clarification rounds; reviews and approves / rejects / requests changes at G1, G2, G2b, G1-delta, hotfix gates and G3, using `mesh gate show` and `mesh gate approve … --hash …`; keeps the ledger running while doing so.
- **Rule:** the human's minutes are part of the measured cost (O2/O3); they are not "free".

### HC-16 — UX checkpoint

- **Human does:** reviews the screens of a project with a UI against the UI contract; approves the visual baseline set (WP4.4).
- **Evidence:** approved baseline commit; ledger entry.

### HC-17 — Release signing keys

- **Human does:** creates the cosign release key pair and the approver release key (promotion attestation), stores private keys outside the repo (`infra/secrets/release/` is gitignored but on the workstation — accepted for the prototype only), and distributes the public keys into `infra/release/keys/`.
- **Evidence:** public keys committed; T5-REL-06 key-isolation test passes; ADR-027 lists the P3a replacement (OpenBao custody).

### HC-18 — Decision pack review

- **Human does:** reviews `reports/decision-pack-P3a.md` with the customer and decides go to P3a / go with changes / pivot / stop; accepts or rejects the proposed design-doc updates.
- **Evidence:** decision in `PROGRESS.md`; design docs updated by agreement.
