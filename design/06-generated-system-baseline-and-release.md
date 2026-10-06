# 06 — Generated-System Baseline (v1) and Release & Go-Live Model

| | |
|---|---|
| **Project** | AI Mesh (working name) |
| **Status** | Draft v1.2 — revised after adversarial review R1 ([07](07-adversarial-architecture-review.md)); see §11; items marked ⚠ need confirmation |
| **Date** | 2026-10-05 |
| **Depends on** | [03-platform-requirements.md](03-platform-requirements.md), [05-reference-architecture.md](05-reference-architecture.md) |

## 1. Confirmed context (customer input, 2026-10-05)

| ID | Decision |
|---|---|
| D8 | Systems built by the platform in v1 use **Python / FastAPI** |
| D18 | Generated systems go live in **clients' own data centres and at client sites**, on **Docker Compose hosts** and on **Kubernetes** |
| D19 | Generated systems include a **web front end in Svelte** (SvelteKit), matching the platform |
| D20 | Generated systems are **SQL-engine agnostic by design**, with **PostgreSQL as the v1 focus** (the only engine tested in v1) |
| D21 | **Pilot client:** the platform **reaches the client's servers directly** (delivery mode A) |
| — | Client container registries and identity providers are **not known yet**; the design must work with or without them (§9) |

This document defines:

1. the **v1 technology catalog** and project template that agents build from (§2–4);
2. the **release and go-live model** that delivers those systems into client environments (§5–8).

It is the input for the benchmark projects (Phase 1) and for the `catalog` and `release` platform modules ([05 §6](05-reference-architecture.md)).

## 2. v1 technology catalog — generated systems

The catalog is human-curated (FR-TEC-01). Agents choose only from it; anything else needs approval at G2 (FR-TEC-02). Versions are pinned per project at project start, choosing the then-current stable releases, and upgraded only through PRs that pass all gates.

### 2.1 Core (always used)

| Concern | Catalog entry | Notes |
|---|---|---|
| Language / runtime | Python 3.12+ | One minor version per project, pinned |
| Web framework | FastAPI + Uvicorn | ASGI; Gunicorn with Uvicorn workers optional for process management |
| Data models & validation | Pydantic v2, pydantic-settings | All config from environment (12-factor) |
| Persistence | SQLAlchemy 2.x + Alembic, engine-agnostic; **PostgreSQL** is the v1 engine | Portability rules in §2.4; migrations follow expand/contract (§7.3) |
| HTTP client | httpx | Timeouts and retries are mandatory |
| Packaging & environments | uv, `pyproject.toml`, lockfile committed | Reproducible builds |
| Logging & telemetry | structlog (JSON logs), OpenTelemetry (traces, metrics) | Exporters configurable per site |
| Containers | OCI images, multi-stage, non-root, slim base | Image digests pinned in releases |

### 2.1a Web front end (core)

| Concern | Catalog entry | Notes |
|---|---|---|
| Framework | SvelteKit + TypeScript | Same framework family as the platform UI |
| Build & serve | Vite; static build served by Nginx in its own container (default), or SvelteKit Node adapter when server-side rendering is required (ADR at G2) | Same-origin API through a reverse proxy |
| API client | TypeScript client generated from `contracts/openapi.yaml` | The front end and backend share one contract; contract changes regenerate the client in the same PR |
| UI components & styling | ⚠ to be chosen at Phase 0 (e.g. a headless component library + Tailwind CSS) | One choice for all v1 projects, recorded in the catalog |
| Accessibility | WCAG 2.1 AA as the default NFR | Checked with axe in end-to-end tests |

### 2.2 Quality gates (CI)

| Gate | Tools |
|---|---|
| Format & lint | ruff (format + lint) |
| Types | mypy (strict) or pyright — one per project |
| Unit / integration tests | pytest, pytest-cov, Testcontainers (real PostgreSQL in tests), Hypothesis (property tests where useful) |
| Acceptance tests (the oracle) | pytest-bdd (Gherkin from G1), run against the containerized system |
| API contract tests | OpenAPI schema checked into git; Schemathesis against the running service; breaking-change diff on every PR |
| Architecture fitness functions | import-linter (module boundaries and layering) |
| Security | Semgrep or Bandit (SAST); pip-audit (dependency CVEs); gitleaks (secrets); Trivy (image scan) |
| Supply chain | Licence check against the allow-list; Syft (SBOM); cosign (image signing) |
| Front end | eslint + prettier; `svelte-check` (types); Vitest (unit/component tests); Playwright end-to-end tests, including UI acceptance scenarios from G1 and axe accessibility checks |
| Database portability | Semgrep rule / import-linter contract: no engine-specific SQL or dialect imports outside the `persistence` adapter (§2.4) |
| Deployment artifacts | `docker compose config` validation; `helm lint` + kubeconform for Kubernetes manifests |

### 2.3 Optional entries (selected at G2 when the architecture needs them)

| Concern | Catalog entry |
|---|---|
| Background jobs | ARQ or Celery with Redis ⚠ choose one |
| Messaging between services | RabbitMQ or NATS ⚠ choose one; transactional outbox pattern |
| Caching | Redis |
| Search | PostgreSQL full-text first; OpenSearch only with justification |
| Authentication | **Core, not optional** (moved by review R1, see §11.1). OIDC, provider-agnostic: an auth module validates tokens from any standard OIDC provider configured per site. For sites without an identity provider, a bundled Keycloak is offered as an optional component of the Compose bundle and Helm chart (§9) |
| Object storage | S3-compatible (e.g. MinIO on-prem) |

### 2.4 Database portability rules (D20)

1. **All data access goes through SQLAlchemy** (ORM or Core expressions). Raw SQL is allowed only inside the module's `persistence` adapter, and only with a portability note.
2. **Portable types by default.** Use SQLAlchemy generic types (`String`, `Numeric`, `DateTime(timezone=True)`, `JSON`, `Uuid`) rather than dialect-specific ones.
3. **PostgreSQL-only features** (e.g. `JSONB` operators, `LISTEN/NOTIFY`, `tsvector`, array columns) are allowed only behind a repository interface, recorded in an ADR, with a documented fallback.
4. **Alembic migrations use portable operations.** Engine-specific DDL is isolated in clearly marked migration steps.
5. **Testing:** v1 tests run on PostgreSQL only (Testcontainers). The test harness takes the engine as a parameter, so adding SQL Server or Oracle later means adding a CI matrix entry, not rewriting tests.

## 3. Architecture styles supported

| Style | When (decided at G2 with an ADR) | Shape |
|---|---|---|
| **Modular monolith** (default) | Most 100k–250k LOC systems; one team; one deployable | One FastAPI application; packages per bounded context under `src/<app>/modules/`; boundaries enforced by import-linter; one database, a schema per module |
| **Microservices** | Independent scaling or release cadence, or distinct data ownership, justified by NFRs | One FastAPI service per bounded context; OpenAPI and event contracts in a shared `contracts/` directory; a database per service; contract tests between services |

Both styles produce the same deployment artifacts (§6). A modular monolith can be split later, because its module boundaries and contracts already exist.

## 4. Project template (what agents generate)

```
<repo>/
├── pyproject.toml / uv.lock
├── src/<app>/
│   ├── main.py                 # FastAPI app factory
│   ├── core/                   # config, logging, telemetry, db session, errors
│   └── modules/<context>/      # api/ (routers) · domain/ · service/ · repository/ · schemas/
├── web/                        # SvelteKit front end: src/routes, src/lib (generated API client), tests (Vitest, Playwright)
├── migrations/                 # Alembic
├── contracts/                  # openapi.yaml (+ event schemas for microservices)
├── tests/
│   ├── unit/  integration/  contract/
│   ├── acceptance/             # Gherkin features from G1 + step definitions (read-only for agents after G1)
│   └── e2e/                    # Playwright UI scenarios (acceptance scenarios with a UI are read-only after G1)
├── deploy/
│   ├── compose/                # compose.yaml, .env.example, healthchecks
│   └── helm/<app>/             # Chart.yaml, values.yaml, values-<site>.yaml.example
├── docs/                       # architecture (C4), ADRs, API reference, runbook, user guide
├── .importlinter               # architecture fitness functions
└── .github/workflows/          # ci.yml, release.yml, deploy-<target>.yml
```

**Conventions**

- **Health endpoints:** `/health/live` and `/health/ready`, both required.
- **Errors:** structured error responses (RFC 9457 problem details).
- **API changes:** every API change is a contract change and must pass the breaking-change check.

## 5. Release model

Every release candidate (RC) is built **once** in CI and promoted unchanged from the sandbox to go-live. Nothing is rebuilt per environment.

| RC content | Purpose |
|---|---|
| Container images, referenced by **digest** and **signed** (cosign) | Integrity; what is tested is what ships |
| SBOM per image (Syft) and vulnerability report (Trivy) | Supply-chain evidence for the client |
| `deploy/compose/` bundle and Helm chart (packaged, versioned) | Both target types from the same release |
| Database migration plan (Alembic revision range, expand/contract steps) | Safe upgrades |
| Runbook: install, upgrade, rollback, backup/restore, smoke test | Operations at the client site |
| Release notes and changelog | Business and technical communication |
| **Evidence bundle**: acceptance results per requirement, scan reports, traceability matrix, UAT sign-off | G3 decision basis (FR-DEP-05) |
| Checksums and signatures for all of the above | Tamper evidence for offline transfer |

**Rehearsal in the sandbox (before G3).** Each RC is deployed in the sandbox **on each target type present in the project's site profiles** (Docker Compose and/or single-node Kubernetes). On each, the sandbox runs the acceptance suite, an upgrade from the previous release, and a rollback. The offline bundle is always produced, and rehearsed only when a mode-C site exists (review R1, RV-30).

## 6. Go-live delivery modes

Client environments differ in reachability and control, so v1 supports three delivery modes. Every target uses one of them.

| Mode | When | How | Who executes |
|---|---|---|---|
| **A. Direct push** | The target is reachable from the project node and the client permits it | GitHub Environment per target with required reviewers (G3). The deploy job runs on the self-hosted runner. Compose: `docker compose` over SSH to the host. Kubernetes: `helm upgrade --install` with a namespace-scoped kubeconfig | Platform pipeline, after human approval |
| **B. GitOps pull** | Kubernetes at a client who runs Argo CD or Flux | The platform publishes the signed chart and image digests to a release repository/registry; the client's GitOps controller syncs the approved release tag | Client's controller; the platform only publishes |
| **C. Offline bundle** | Air-gapped or client-operated sites; no inbound access | A signed archive: OCI image tarballs, Compose bundle, Helm chart, values template, SBOMs, runbook, install/upgrade/rollback/smoke-test scripts, checksums | Client's operator, following the runbook |

**v1 decision for the pilot (D21): mode A — direct push.** The platform reaches the pilot client's servers directly.

**v1 recommendation**

- **Always produce the offline bundle (C)** for every RC. It is the lowest common denominator and the archival record of what was approved.
- **Implement direct push (A)** for both Compose and Kubernetes.
- **Add GitOps (B)** when the first client that uses it is onboarded. It reuses the same chart and registry artifacts.

**Supporting requirements**

- **Registry access:** client sites usually cannot pull from GHCR. Mode A pushes images to the client's registry, or loads them onto the host. Mode C carries them in the bundle.
- **Site-specific configuration:** lives in `values-<site>.yaml` / `.env` files kept outside the bundle, with secrets supplied by the client's secret store. No secrets in any artifact.
- **Network path (mode A):** the project node needs an allow-listed outbound route to each target (SSH or the Kubernetes API). Each route is a change to the egress proxy policy, approved per client.

## 7. Go-live procedure (G3 and after)

### 7.1 Sequence

1. The release engineer agent assembles the RC and the G3 package (§5).
2. Humans review and approve G3 in the platform UI. For mode A, the GitHub Environment for that target requires a second approval by a named reviewer. Agents can never approve either.
3. **Pre-flight:** check target reachability and capacity (mode A), verify signatures and checksums, and confirm a backup and restore point exists for the client's database.
4. **Deploy:**
   - mode A — the pipeline deploys;
   - mode B — the release is tagged for sync;
   - mode C — the bundle is delivered to the client's operator.
5. **Post-deploy smoke tests** from the runbook. In modes B and C the client runs them, and the result is recorded in the platform (signed report or attested confirmation).
6. **On failure:** run the rehearsed rollback, record the incident, and return the project to Build.
7. **On success:** the release is marked live and the evidence bundle archived (audit log + git tag).

### 7.2 Responsibilities

| Step | Platform | Client |
|---|---|---|
| Build, test, sign, rehearse | ✓ | |
| G3 approval | Customer's approvers | Client sign-off (UAT) as input |
| Deploy | Mode A | Modes B and C |
| Smoke test | Mode A | Modes B and C (reported back) |
| Rollback | Mode A (automated) | Modes B and C (runbook) |

### 7.3 Database changes

- **Alembic migrations follow expand/contract.** Releases add schema first, and remove it only in a later release. A rollback of the application never requires a destructive down-migration.
- **Backup before every go-live.** Restore is part of the rollback procedure and is rehearsed in the sandbox.

## 8. Effects on the platform node

- **Sandbox capacity.** Adding a single-node Kubernetes cluster costs roughly 2–4 GB RAM and 1–2 CPU threads on top of the Compose sandbox ([05 §9.3](05-reference-architecture.md)). Run the Compose and Kubernetes rehearsals one after the other, not in parallel.
- **Supply-chain tooling.** Syft, Trivy and cosign are added to the runner image. The signing key is held in OpenBao, used only by the release workflow, and never available to agents.
- **New egress entries.** One allow-list entry per mode-A target, and client registry endpoints where used.

## 9. Client site profile (registry and identity provider unknown)

Client registries and identity providers are not known yet, so each client site is described by a **site profile**: versioned configuration in the platform, completed during client onboarding. Deploy pipelines and the generated system's configuration read from it. Unknown fields block go-live to that site (fail closed), not development.

| Profile field | Options the design supports | Default if the client has none |
|---|---|---|
| Target type | Docker Compose host / Kubernetes (version, ingress, storage class) | — (required) |
| Network path from the project node | SSH (Compose); Kubernetes API endpoint + namespace | — (required for mode A) |
| Container registry | Client registry (e.g. Harbor, Nexus) — images pushed by digest | **Compose:** images transferred over SSH and loaded on the host (`docker save` / `docker load`). **Kubernetes:** a lightweight registry deployed in the client cluster as part of onboarding, or images imported into the node runtime ⚠ client's choice |
| Identity provider | Any standard OIDC provider (e.g. Keycloak, Azure AD / Entra ID) | Bundled Keycloak, deployed with the system |
| Database | Client-managed PostgreSQL, or PostgreSQL deployed with the system | PostgreSQL in the Compose bundle / Helm chart, with backups configured |
| TLS & DNS | Client certificates and DNS names | Self-signed for UAT only; go-live requires client-supplied certificates |
| Secrets | Client secret store, or files/Kubernetes Secrets provisioned by the client | Kubernetes Secrets / `.env` files provisioned during onboarding, never stored in the bundle |
| Observability | Client's monitoring (OpenTelemetry endpoint, log shipping) | Logs to stdout; metrics endpoint exposed |
| Backups | Client backup tooling | Scheduled `pg_dump` job included in the deployment |

- **Onboarding checklist.** The release engineer agent generates the checklist from the profile's empty fields, and a human completes it with the client.
- **Pre-flight checks.** Before G3, pre-flight validates the profile: connectivity, registry login, Kubernetes namespace permissions, IdP discovery URL.

## 10. Open questions

1. ~~Front end~~ — resolved: SvelteKit (D19). Open: UI component library and styling choice for the catalog (Phase 0).
2. ~~Database~~ — resolved: engine-agnostic design, PostgreSQL focus (D20).
3. ~~Pilot delivery mode~~ — resolved: direct push (D21). Needed for the pilot: the pilot client's site profile (§9).
4. **Optional catalog choices.** Pick one job queue (ARQ or Celery) and one message broker (RabbitMQ or NATS), or defer until a benchmark project needs them.
5. **Client registries and identity providers** — unknown for now; handled by the site profile (§9) and confirmed per client at onboarding.
6. **Kubernetes without a registry** — if the pilot or a later client runs Kubernetes without a registry, choose between deploying a lightweight in-cluster registry and importing images into the node runtime.

## 11. Revisions from adversarial review R1

Source: [07-adversarial-architecture-review.md](07-adversarial-architecture-review.md). Where this section conflicts with earlier sections, this section wins.

### 11.1 Secure-by-default baseline for generated systems (RV-18)

| Control | Requirement |
|---|---|
| Authentication | OIDC in the **core** template, not optional |
| Authorization | **Deny by default**. A fitness function fails CI if any FastAPI route lacks an auth dependency or an explicit `public` marker |
| Authorization tests | An **authorization matrix** (actor × endpoint × tenant) generated from actors and use cases at G1/G2, run as executable tests |
| Security NFR default | **OWASP ASVS Level 2**, with checks mapped to it |
| Threat model | A STRIDE threat model is part of the G2 package |
| Web hardening | Security headers, CSP, CORS policy, rate limiting in the template |
| Dynamic testing | OWASP ZAP baseline and API scans against the sandbox at each RC |
| IaC | Trivy config / kube-linter scans of Compose and Helm |
| Kubernetes | Pod Security "restricted", NetworkPolicies, non-root, read-only root filesystem |
| Data | Encrypted backups; service-to-service TLS where crossing hosts; hardened bundled Keycloak |
| G3 | Human **security sign-off** required |

### 11.2 Verification of UI and NFRs (RV-19, RV-20)

- The prototype is **mandatory**. G2 approves a **UI contract**: route map, page → use case, accessible roles and labels.
- E2E tests use role and label locators. Humans approve visual-regression baselines at each module's first render. Time-boxed human UX checkpoints per module run during Build. Exploratory QA is a must.
- An **NFR definition-of-done catalog** gives, for each NFR type, the evidence, environment, threshold, cadence and owner. Performance runs as relative regression budgets on a quiesced execution-plane runner, plus an absolute run on reference hardware before G3. A manual accessibility pass is part of UAT.

### 11.3 Supply chain (RV-14)

- Workspaces and CI install only through the **internal package proxy**: allow-listed packages, 7–14 day quarantine on new versions, hash-pinned lockfiles, `npm ci --ignore-scripts`.
- A lockfile diff that adds a package needs human approval and an existence/reputation check.
- All GitHub Actions are pinned by full SHA. Scanner tooling (including Trivy) runs from pinned, verified images.

### 11.4 Release integrity and hardened direct push (RV-10)

**G3 promotion attestation.** Approvers sign an attestation listing the approved image digests and artifact hashes. Build provenance is signed separately. The deploy job deploys only digests in the promotion attestation, and clients verify both (cosign/Kyverno policy on Kubernetes; the verify script on Compose hosts and for offline bundles), with public keys delivered out of band.

**Mode A, direct push** (pilot, D21):

- Runs only on the **dedicated deploy runner** on the control side. Never from the execution plane.
- Credentials: **short-lived SSH certificates** (OpenBao SSH CA) or short-lived Kubernetes tokens, issued only to jobs whose OIDC claims match the site environment and a release tag.
- On Compose hosts: a non-docker-group deploy user with a **forced command** that verifies signature and digest, then converges.
- On Kubernetes: minimal RBAC, with no broad Secret read.
- Clients allow-list the deploy runner's source IP. Credentials and egress routes are separate per site, with a revocation runbook.

**Interrupted deploys.** A deploy state machine records a deploy intent before dispatch. A go-live is never auto-retried after a crash; the state is reconciled from the GitHub run and the target's observed state, and a human decides. `helm upgrade --atomic --wait`; idempotent Compose convergence. Break-glass rollback runs from an operator machine using the offline bundle.

### 11.5 After go-live (RV-09)

- **Hypercare** (default 30 days) and **Maintenance** states, with a hotfix fast path.
- Daily CVE monitoring of delivered SBOMs raises maintenance tasks.
- Release signing, site profiles and the SBOM register are held in a central service outside project nodes, so a released system can be patched even after its node is reassigned.
- A support model (incident intake, SLA, owner) is agreed per client contract (⚠ legal workstream, RV-23).
