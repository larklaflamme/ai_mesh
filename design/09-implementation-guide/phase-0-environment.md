# Phase 0 — Environment and Instrumentation

| | |
|---|---|
| **Goal** | A measurable, reproducible environment before any agent work: infra up, tunnel proven, gateway metering every call, telemetry stored, GPU sampled, serving capacity characterized (E0) |
| **Duration** | ~2 weeks |
| **Prerequisites** | WP-B (bootstrap) done; HC-01 (remote setup) done, or in progress in parallel |
| **Human checkpoints** | HC-01 remote setup · HC-02 workstation facts · HC-03 model list and digests · HC-08 E0 card approval |
| **Exit gate** | §4 |

## 1. Work packages

### WP0.1 — Local infrastructure (`infra/local/compose.yaml`)

**Tasks:**

1. Write `compose.yaml` with these services. Pin every image by digest, recorded in `infra/local/IMAGES.lock`.

   | Service | Image | Networks | Published (host) | Notes |
   |---|---|---|---|---|
   | `postgres` | postgres:16 | `mesh-ctl` | 127.0.0.1:5432 | Volume `pgdata`; init script creates schemas `platform`, `telemetry`, `audit`, `langgraph`, plus roles `mesh_app` (INSERT/SELECT on telemetry/audit) and `mesh_admin` (migrations) |
   | `qdrant` | qdrant/qdrant | `mesh-ctl` | 127.0.0.1:6333 | API key from `.env` (`QDRANT__SERVICE__API_KEY`) |
   | `mesh-tunnel` | build `../tunnel` | `mesh-llm` | 127.0.0.1:11434, 127.0.0.1:9835 | See [02 §B2](02-remote-ollama-and-tunnel.md) |
   | `mesh-gateway` | build `../../gateway` | `mesh-llm`, `mesh-exec`, `mesh-ctl` | 127.0.0.1:8088 | Upstream `MESH_GATEWAY_UPSTREAM`; mounts `runs/` (rw, for blobs) and `infra/remote/` (ro, for `models.lock` and tokenizers) |
   | `pypi-proxy` | devpi-server (pinned) | `mesh-exec`, `mesh-egress` | — | Pull-through cache for PyPI; allow-list plugin or index restrictions (WP1.1 tightens it) |
   | `npm-proxy` | verdaccio (pinned) | `mesh-exec`, `mesh-egress` | — | Pull-through cache for npm |
   | `toxiproxy` | ghcr.io/shopify/toxiproxy (profile `test`) | `mesh-llm` | 127.0.0.1:8474 | Fault injection between gateway and tunnel |
   | `phoenix` | arizephoenix/phoenix (profile `obs`) | `mesh-ctl` | 127.0.0.1:6006 | Optional trace browser |

2. Networks:

   | Network | Type | Subnet |
   |---|---|---|
   | `mesh-ctl` | bridge | 172.28.0.0/24 |
   | `mesh-llm` | bridge | 172.29.0.0/24 (fixed, see 02 §B3) |
   | `mesh-exec` | `internal: true` | 172.30.0.0/24 |
   | `mesh-egress` | bridge | default |

3. Write `.env.example` with all variables. `make up` creates `.env` from it if missing, and **fails** on placeholder values.
4. Add `mesh doctor` checks for each service.

**Acceptance criteria:**

- `make up` brings everything healthy within 60 s, apart from the tunnel if the remote side is not ready yet. That is reported, not fatal.
- `mesh doctor` reports each component.
- A container on `mesh-exec` **cannot** reach the internet, PostgreSQL, Qdrant, the tunnel, or host ports. It **can** reach `mesh-gateway:8088`, `pypi-proxy`, `npm-proxy` (T0-INF-03).

### WP0.2 — Tunnel container and verification

**Tasks:**

1. Implement [02 Part B](02-remote-ollama-and-tunnel.md).
2. Automate V-01…V-08 as `mesh doctor --tunnel`.
3. Record V-06 (RTT) and V-07 (recovery time) in `telemetry.events`.

**Acceptance:** V-01…V-08 pass. V-09 and V-10 are confirmed by the human and recorded in `PROGRESS.md`.

### WP0.3 — Telemetry foundation

**Tasks:**

1. Alembic migrations for the `platform`, `telemetry` and `audit` schemas ([03 §3](03-interfaces-and-schemas.md)), plus the grants.
2. `mesh.core.manifest`: `RunManifest`, `build_manifest(...)`. It collects SHAs (refusing a dirty tree for `measured`), the model digest from `models.lock`, and the Ollama env hash.
3. `mesh.telemetry.writer`:
   - typed insert functions per table;
   - redaction (gitleaks rule set + known secret values from settings);
   - an async batch writer with flush-on-exit.
4. `mesh.telemetry.blobs`: content-addressed zstd blobs under `runs/<run_id>/blobs/`, with redaction applied before hashing.
5. `mesh.governance.audit`: single-writer appender (advisory lock), hash chain, anchors ([03 §9](03-interfaces-and-schemas.md)), `mesh audit verify`.
6. `mesh run new --label exploratory|measured --experiment <id>` creates a run and its manifest.

**Acceptance:**

- Manifests are written to both the file and the DB.
- Measured runs are refused on a dirty tree.
- The application role cannot UPDATE or DELETE telemetry or audit rows.
- Redaction removes planted secrets.
- `mesh audit verify` detects tampering.

### WP0.4 — `mesh-gateway` v0

**Tasks** (contract in [03 §4](03-interfaces-and-schemas.md)):

1. FastAPI app. httpx `AsyncClient` to upstream, with connection pooling and timeouts: connect 5 s; read 600 s for streaming, with idle-chunk timeout 120 s.
2. Auth via `platform.gateway_keys` (sha256 lookup; in-process cache with a 5 s TTL). `mesh.llm.keys` issue/revoke on the platform side.
3. `models.lock` loader:
   - aliases (`primary`, `worker`, `reviewer`, `embedding-cpu`);
   - digest check against upstream `/api/tags` at startup and every 5 min. **A mismatch makes `/ready` fail** and every request return 503 `model_digest_mismatch`.
4. Tokenizer-based budget check:
   - HF `tokenizers` loading the pinned `tokenizer.json`, with its sha256 verified;
   - chat-template overhead approximated per message (role tokens + separators) plus a safety margin (3% + 64);
   - **413 before any upstream call** when over budget.
5. Streaming passthrough (SSE for `/v1`, NDJSON for `/api/chat`). Metering: TTFT, decode rate, usage. Request/response blobs.
6. Cassette mode `record|replay|live` ([04 §5](04-test-strategy.md)).
7. `/ready`, `/healthz`, `/metrics`.
8. Dockerfile: Python 3.12 slim, non-root, read-only root filesystem, installed from `gateway/requirements.lock` with `--require-hashes`.

**Acceptance:**

- All T0-GW tests pass.
- Responses passed through the gateway are byte-identical in content to direct upstream responses, apart from injected `usage`.
- Gateway overhead p95 < 15 ms for non-streaming requests against the fake upstream.

### WP0.5 — Ollama metrics investigation

**Tasks:**

1. Determine empirically, against the real server:
   - Does `/v1/chat/completions` return `usage` when streaming with `stream_options.include_usage`?
   - Does it return any timing or prompt-eval fields?
   - Does native `/api/chat` return `prompt_eval_count`, `prompt_eval_duration`, `eval_count`, `eval_duration` and `load_duration`?
   - Does `prompt_eval_count` drop on a repeated identical prefix (cache reuse) for the primary (hybrid-attention) model?
2. Decide how `prompt_tokens_computed` is obtained:
   - (a) native passthrough fields;
   - (b) gateway-side translation of `/v1` to `/api/chat` for metering;
   - (c) parsing Ollama server debug logs.
3. Write `adr/ADR-019-ollama-metering.md` with the evidence (raw response samples, redacted) and the decision. Implement the chosen path in the gateway.

**Acceptance:** the ADR is written; `telemetry.llm_calls.prompt_tokens_computed` is populated on real calls (T0-GW-12, e2e).

### WP0.6 — GPU sampler (`tools/gpu-sampler`)

**Tasks:**

1. An async poller of the exporter at `mesh-tunnel:9835/metrics` (from the host: `127.0.0.1:9835`) every 1 s.
2. Map these fields: utilization, memory used, power, SM and memory clocks, temperature, ECC, and a throttle/power-cap indication if exposed. If power capping is not exposed, record `null` and note it in the ADR.
3. Write to `telemetry.gpu_samples`. Run as a `make sampler` background process, or a compose service in profile `obs`.

**Acceptance:** samples arrive at about 1 Hz while the tunnel is up. Gaps are recorded as `tunnel_down` events, not zeros.

### WP0.7 — Human-touch ledger CLI

**Tasks:** `mesh ledger start <category> [--run --task --gate --note]`, `mesh ledger stop`, `mesh ledger add --minutes N <category> …` (retroactive, flagged as such), `mesh ledger report`. Categories are listed in [03 §3.2](03-interfaces-and-schemas.md). The person ID is a pseudonymous configured value.

**Acceptance:** start/stop pairs give correct durations. A start without a stop is closed at the next start, with the `auto_closed` flag set.

### WP0.8 — Readiness and infra classification primitives

**Tasks:**

1. `mesh.capacity.readiness`: barrier checks for PostgreSQL, Qdrant, gateway `/ready`, Docker, and free disk on the `runs/` volume (≥ 15%).
2. Expose `wait_ready(timeout)` and `is_ready()`. Emit `readiness_change` events.
3. `mesh.core.failures.classify(exit_code, logs_meta, gateway_status) -> FailureClass`, implementing the rules in [03 §1](03-interfaces-and-schemas.md).

**Acceptance:** T0-RDY tests pass.

### WP0.9 — `llm-bench` and experiment E0

**Tasks:**

1. `tools/llm-bench` (Python CLI). Scenarios:

   | Scenario | Measures |
   |---|---|
   | `rtt` | 100 × `/api/version` through the tunnel |
   | `decode` | Single stream, contexts 8K / 32K / 64K (/ 128K if it fits without offload), 512 output tokens |
   | `concurrency` | 1 / 2 / 4 / 8 parallel streams at 16K context |
   | `prefix_stable` | 20-turn conversation appending ~1.5K tokens per turn, identical prefix (cache reuse) |
   | `prefix_unstable` | Same, but turn 1's system prompt changes per turn (worst case) |
   | `sustained` | 10 min at the planned concurrency; power capping and clocks over time |

   Use deterministic synthetic prompts built from a fixed corpus (the platform's own source files at a pinned SHA), with seed control.
2. Run both direct (`127.0.0.1:11434`, native API) and through the gateway (`127.0.0.1:8088`) to measure gateway overhead.
3. Write the E0 card `benchmark/experiments/E0-serving-capacity.yaml` with the models from HC-03, the scenarios, 3 repeats, and the decision rule:

   > choose the largest `OLLAMA_CONTEXT_LENGTH` and `NUM_PARALLEL` for which `ollama ps` shows 100% GPU and the aggregate decode at the planned concurrency is ≥ 0.8 × the best observed.

   Get it approved (HC-08).
4. Run E0 and generate the report (`make report EXP=E0-serving-capacity`) with tables and plots: tok/s vs context, tok/s vs concurrency, TTFT, cached-prefix ratio per turn, power and clocks over time.
5. Recommend final Ollama settings. **The human applies them** (02 §A3). Re-run the `decode` + `concurrency` subset to confirm.

**Acceptance:**

- The E0 report exists, with all scenarios × models × 3 repeats.
- Repeat variance ≤ 5% for decode tok/s, or explained.
- The recommendation has been applied and confirmed.
- 02 §10 numbers are updated in `PROGRESS.md` notes. The design doc update is proposed, not edited.

## 2. Phase 0 test plan

| ID | Level | Test | Pass criterion |
|---|---|---|---|
| T0-INF-01 | integration | `compose.yaml` validates; all images pinned by digest | `docker compose config` OK; no `:latest` or untagged image |
| T0-INF-02 | integration | `make up` health | All required services healthy ≤ 60 s |
| T0-INF-03 | security | Probe container on `mesh-exec` tries: internet (1.1.1.1:443), `postgres:5432`, `qdrant:6333`, `mesh-tunnel:11434`, host gateway IP ports | All fail; `mesh-gateway:8088`, `pypi-proxy`, `npm-proxy` reachable |
| T0-INF-04 | integration | DB roles | `mesh_app` UPDATE/DELETE on `telemetry.*` and `audit.*` denied |
| T0-TUN-01 | e2e | V-01..V-05 | As in 02 §C |
| T0-TUN-02 | e2e | Tunnel restart recovery | `/api/version` succeeds again ≤ 30 s after `docker compose restart mesh-tunnel` |
| T0-TUN-03 | e2e | Restriction | Shell and non-allowed forwards refused (V-08) |
| T0-TEL-01 | unit | Manifest builder | Refuses dirty tree for `measured`; includes all fields; JSON schema valid |
| T0-TEL-02 | integration | Telemetry writer | Rows written; batch flush on exit; schema enforced |
| T0-TEL-03 | unit (property) | Redaction | Planted secrets (API keys, private keys, `MESH_KEY` values) never appear in rows or blobs |
| T0-TEL-04 | unit (property) | Audit chain | Any single-row mutation is detected by `verify` |
| T0-TEL-05 | integration | Anchors | Anchor written per event and ≤ 60 s while active; verify checks against anchors |
| T0-GW-01 | contract | OpenAI compatibility | Non-streaming and streaming chat with tools round-trip correctly against `fake_ollama` |
| T0-GW-02 | unit | Auth | Unknown key 401; expired or revoked 403; key hash only stored |
| T0-GW-03 | unit | Model pinning | Request for another model → 400; model forced to the key's model |
| T0-GW-04 | unit (property) | Budget arithmetic | Over budget → 413 and **zero upstream calls**; never truncates |
| T0-GW-05 | unit | `max_tokens` clamp | Clamped to the key's `max_output_tokens` |
| T0-GW-06 | integration | Task GPU-token budget | Cumulative usage beyond the budget → 429 `budget_exhausted` |
| T0-GW-07 | integration | Upstream failure | Connection refused or 5xx → 503 `upstream_unavailable`, `error_class=infra`, `tunnel_down` event |
| T0-GW-08 | integration | Metering | Row per call: TTFT, total, usage, counted tokens, blobs exist and are redacted |
| T0-GW-09 | integration | Cassettes | Record then replay is identical; replay miss → 599; replay never contacts upstream |
| T0-GW-10 | integration | Digest pinning | Digest mismatch → `/ready` 503 and requests 503 `model_digest_mismatch` |
| T0-GW-11 | integration | Toxiproxy latency / drop | Latency reflected in `upstream_ms`; mid-stream reset → infra error, no partial "success" row |
| T0-GW-12 | e2e | Real calls | `prompt_tokens_computed` populated per ADR-019; streaming usage present |
| T0-GW-13 | integration | Overhead | p95 added latency < 15 ms (non-streaming, fake upstream) |
| T0-GPU-01 | unit | Exporter parsing | Fixture metrics map to the correct fields |
| T0-GPU-02 | e2e | Sampling | ~1 Hz samples; a tunnel outage produces an event, not zero rows |
| T0-LED-01 | unit | Ledger durations | Correct; auto-close flagged; retroactive entries flagged |
| T0-RDY-01 | integration | Readiness barrier | Any dependency down → `is_ready()` false with a reason; recovers when restored |
| T0-RDY-02 | unit | Classification table | Exit 137 → INFRA; gateway 503 → INFRA; 413 → BUDGET; judge fail → TASK; timeout without infra evidence → TIMEOUT |
| T0-BEN-01 | unit | `llm-bench` determinism | Same seed and corpus → identical prompts |
| T0-BEN-02 | gpu | E0 reproducibility | Decode tok/s repeat variance ≤ 5%, or explained in the report |

## 3. Measurements produced

- E0 report: capacity tables and plots; recommended Ollama settings.
- Tunnel RTT and recovery time.
- Gateway overhead.
- Cached-prefix ratio, stable vs unstable prefix.
- Power-capping behaviour under sustained load.

## 4. Exit gate (Phase 0 → Phase 1)

- [ ] WP0.1–WP0.9 ticked with evidence.
- [ ] All T0 tests green. `T0-*-e2e`/`gpu` results recorded with run IDs.
- [ ] E0 report approved by the human; final Ollama settings applied and confirmed.
- [ ] ADR-019 (metering) written.
- [ ] `models.lock` holds digests and tokenizer hashes for the Phase 1 model(s).
