# 02 — Remote Ollama Server and SSH Tunnel

**Split of work:**

- **Part A** is done by the **human** on the remote GPU server (HC-01).
- **Part B** is done by **Claude Code** on the workstation.
- **Part C** is verified together.

**Target picture:** Ollama and a GPU metrics exporter listen **only on 127.0.0.1 of the GPU server**. The workstation reaches them through an SSH tunnel that a restricted key allows to forward **only those two ports**. Locally, the tunnel runs as a container on a private Docker network, so `mesh-gateway` (also a container) can reach it. Host tools reach it through ports published on `127.0.0.1`.

```
workstation                                          GPU server (H100 PCIe)
┌─────────────────────────────────────────────┐      ┌───────────────────────────────┐
│ host tools ──► 127.0.0.1:11434 / :9835 ─┐   │      │ ollama        127.0.0.1:11434 │
│                                          │   │ SSH │ gpu exporter  127.0.0.1:9835  │
│ [mesh-llm network]                       ▼   │═════│ sshd: user mesh-tunnel,       │
│   mesh-gateway ──► mesh-tunnel (autossh) ────│─────│   forwarding to the two ports │
│ [mesh-exec network, internal]                │      │   only                        │
│   workspaces ──► mesh-gateway                │      └───────────────────────────────┘
└─────────────────────────────────────────────┘
```

## Part A — Remote GPU server (human)

### A1. Clear the GPU

The GPU is dedicated to the mesh (DN-10). Stop the existing GPU processes (two Python processes and an Ollama runner were seen on 2026-10-05).

```bash
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv   # expect: no rows
```

### A2. Pin the driver

```bash
sudo apt-mark hold 'nvidia-driver-*' 'libnvidia-*' 'cuda-drivers*'   # match the installed package names
```

Disable unattended upgrades for NVIDIA and kernel packages (07 RV-13). Expected: driver 595.58.03, CUDA 13.2.

### A3. Install or upgrade Ollama and pin its version

Install a specific Ollama release (record the version in `infra/remote/VERSIONS.md` in the repo). Do not enable auto-update.

Configure the service with a systemd drop-in, `/etc/systemd/system/ollama.service.d/override.conf`:

```ini
[Service]
Environment="OLLAMA_HOST=127.0.0.1:11434"
Environment="OLLAMA_CONTEXT_LENGTH=65536"
Environment="OLLAMA_NUM_PARALLEL=4"
Environment="OLLAMA_MAX_LOADED_MODELS=1"
Environment="OLLAMA_KEEP_ALIVE=-1"
Environment="OLLAMA_FLASH_ATTENTION=1"
Environment="OLLAMA_KV_CACHE_TYPE=q8_0"
Environment="OLLAMA_MAX_QUEUE=64"
# put models on a fast local NVMe path with enough space (~300 GB for the bake-off)
Environment="OLLAMA_MODELS=/srv/ollama/models"
```

Apply it:

```bash
sudo systemctl daemon-reload && sudo systemctl restart ollama
ss -ltnp | grep 11434        # must show 127.0.0.1:11434 only, never 0.0.0.0 or [::]
```

`OLLAMA_CONTEXT_LENGTH` and `OLLAMA_NUM_PARALLEL` are **initial values**. Phase 0 experiment E0 sets the final values, and the human applies them. Keep a copy of this file in the repo at `infra/remote/ollama.override.conf`; Claude Code maintains it.

### A4. Pull candidate models from official sources only

Candidate list for E0/E3 (final list confirmed at HC-03):

- Qwen3.8-27B at several quantizations;
- a Qwen3.x 35B-A3B MoE;
- Devstral Small 2;
- optionally gpt-oss-120b.

Use only the official Ollama library entries, or GGUFs from the **publisher's own** Hugging Face organization. Never personal re-uploads (07 RV-14).

```bash
ollama pull <official-name>:<tag>
curl -s http://127.0.0.1:11434/api/tags | jq '.models[] | {name, digest, size, details}'
```

Send the `name` + `digest` lines to Claude Code. They go into `infra/remote/models.lock`. **The gateway refuses to start if a digest in use does not match the lock.**

Also download each model's official `tokenizer.json` (from the publisher's HF repo). Claude Code stores them in `infra/remote/tokenizers/<model-family>/tokenizer.json` with their SHA-256 recorded in `models.lock`.

### A5. GPU metrics exporter (localhost only)

Option 1 (recommended, light): **`nvidia_gpu_exporter`** as a systemd service listening on `127.0.0.1:9835`.

Option 2: **DCGM exporter** in Docker, published only on localhost:

```bash
docker run -d --gpus all --restart unless-stopped -p 127.0.0.1:9400:9400 nvcr.io/nvidia/k8s/dcgm-exporter:<pinned-tag>
```

If you use DCGM, tell Claude Code: the port becomes 9400 and the metric names differ.

Verify: `curl -s 127.0.0.1:9835/metrics | head`, and `ss -ltnp | grep 9835` shows `127.0.0.1` only.

### A6. Restricted tunnel user

```bash
sudo adduser --disabled-password --gecos "" mesh-tunnel
sudo install -d -m 700 -o mesh-tunnel -g mesh-tunnel /home/mesh-tunnel/.ssh
```

Add to `/etc/ssh/sshd_config` (or `/etc/ssh/sshd_config.d/mesh-tunnel.conf`):

```
Match User mesh-tunnel
    AllowTcpForwarding local
    PermitOpen 127.0.0.1:11434 127.0.0.1:9835
    X11Forwarding no
    AllowAgentForwarding no
    PermitTTY no
    ForceCommand /bin/false
```

The workstation generates the key pair (Part B1). Append its **public** key to `/home/mesh-tunnel/.ssh/authorized_keys` with options:

```
restrict,port-forwarding,permitopen="127.0.0.1:11434",permitopen="127.0.0.1:9835" ssh-ed25519 AAAA... mesh-tunnel@workstation
```

Then:

```bash
sudo chmod 600 /home/mesh-tunnel/.ssh/authorized_keys && sudo chown mesh-tunnel: /home/mesh-tunnel/.ssh/authorized_keys
sudo sshd -t && sudo systemctl reload ssh
```

### A7. Hand-over to Claude Code

Provide:

- the hostname or IP and SSH port;
- the server's host key fingerprint (`ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`);
- the `api/tags` output (A4);
- the exporter option (A5);
- the Ollama version (A3).

## Part B — Workstation (Claude Code)

### B1. Key pair and known_hosts

Ask the human before generating the key; it is part of HC-01.

```bash
mkdir -p infra/secrets && chmod 700 infra/secrets
ssh-keygen -t ed25519 -N "" -C "mesh-tunnel@$(hostname)" -f infra/secrets/mesh_tunnel_ed25519
ssh-keyscan -p <port> -t ed25519 <host> > infra/secrets/known_hosts
ssh-keygen -lf infra/secrets/known_hosts      # human compares with the fingerprint from A7
```

`infra/secrets/` is gitignored. Give the **public** key to the human for A6.

### B2. Tunnel container — `infra/tunnel/`

`infra/tunnel/Dockerfile`:

```dockerfile
FROM alpine:3.20
RUN apk add --no-cache openssh-client autossh curl \
 && adduser -D -u 10001 tunnel
USER tunnel
COPY --chown=tunnel entrypoint.sh /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
```

`infra/tunnel/entrypoint.sh` (executable):

```sh
#!/bin/sh
set -eu
: "${MESH_TUNNEL_HOST:?}"; : "${MESH_TUNNEL_PORT:=22}"; : "${MESH_TUNNEL_USER:=mesh-tunnel}"
: "${MESH_EXPORTER_PORT:=9835}"
exec autossh -M 0 -N \
  -o ServerAliveInterval=15 -o ServerAliveCountMax=3 \
  -o ExitOnForwardFailure=yes -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile=/secrets/known_hosts -o IdentitiesOnly=yes \
  -o GatewayPorts=yes \
  -i /secrets/mesh_tunnel_ed25519 -p "$MESH_TUNNEL_PORT" \
  -L 0.0.0.0:11434:127.0.0.1:11434 \
  -L 0.0.0.0:${MESH_EXPORTER_PORT}:127.0.0.1:${MESH_EXPORTER_PORT} \
  "$MESH_TUNNEL_USER@$MESH_TUNNEL_HOST"
```

`0.0.0.0` here is **inside the container**: only the `mesh-llm` Docker network and the host ports published on `127.0.0.1` can reach it.

Compose service (part of `infra/local/compose.yaml`, written fully in Phase 0 WP0.2):

```yaml
  mesh-tunnel:
    build: ../tunnel
    restart: unless-stopped
    env_file: ../../.env                 # MESH_TUNNEL_HOST, MESH_TUNNEL_PORT, MESH_TUNNEL_USER, MESH_EXPORTER_PORT
    volumes:
      - ../secrets/mesh_tunnel_ed25519:/secrets/mesh_tunnel_ed25519:ro
      - ../secrets/known_hosts:/secrets/known_hosts:ro
    networks: [mesh-llm]
    ports:
      - "127.0.0.1:11434:11434"          # host tools (llm-bench, debugging)
      - "127.0.0.1:9835:9835"            # gpu sampler
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://127.0.0.1:11434/api/version"]
      interval: 10s
      timeout: 5s
      retries: 3
```

**File permissions:** the private key must be readable by UID 10001 inside the container. Either `chmod 640` with a group mapping, or copy it into a named volume at startup. Document the choice in `infra/tunnel/README.md`.

### B3. Alternative: a host tunnel run by the human

If the human prefers to run the tunnel on the host, **do not also run `mesh-tunnel`** on the same ports.

**Linux:** containers cannot reach the host's `127.0.0.1`. Bind the forwards to the fixed gateway IP of the `mesh-llm` bridge instead, and point the gateway there:

```bash
# mesh-llm subnet is fixed to 172.29.0.0/24 in compose.yaml; its gateway on the host is 172.29.0.1
autossh -M 0 -N -o ServerAliveInterval=15 -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes \
  -i ~/.ssh/mesh_tunnel_ed25519 \
  -L 127.0.0.1:11434:127.0.0.1:11434 -L 172.29.0.1:11434:127.0.0.1:11434 \
  -L 127.0.0.1:9835:127.0.0.1:9835 \
  mesh-tunnel@<host>
# gateway setting:  MESH_GATEWAY_UPSTREAM=http://172.29.0.1:11434
```

Run it as a user systemd unit with `Restart=always`. The `mesh-llm` network must exist before the tunnel starts (`make up` creates it).

**macOS with Docker Desktop:** containers reach host loopback services via `host.docker.internal`. Use `MESH_GATEWAY_UPSTREAM=http://host.docker.internal:11434`.

The containerized tunnel (B2) is the default because it behaves the same on every OS and keeps the forward off the host's network interfaces.

### B4. `.env` entries (placeholders in `.env.example`)

```
MESH_TUNNEL_HOST=<gpu-host>
MESH_TUNNEL_PORT=22
MESH_TUNNEL_USER=mesh-tunnel
MESH_EXPORTER_PORT=9835
MESH_GATEWAY_UPSTREAM=http://mesh-tunnel:11434
```

## Part C — Verification

Claude Code runs these and records the results in `PROGRESS.md`. Each one is also an automated test in Phase 0 (see the IDs).

| # | Check | Command / method | Pass |
|---|---|---|---|
| V-01 | Tunnel up | `docker compose ps mesh-tunnel` → healthy | Healthy within 30 s |
| V-02 | Ollama reachable | `curl -s 127.0.0.1:11434/api/version` | JSON with the pinned version |
| V-03 | Model digests match the lock | `mesh doctor --models` compares `/api/tags` digests with `models.lock` (T0-GW-10) | All match; mismatch → non-zero exit |
| V-04 | Real generation | `curl 127.0.0.1:11434/api/generate -d '{"model":"<pinned>","prompt":"Say OK","stream":false,"options":{"num_predict":2}}'` | `response` non-empty; `eval_count` ≥ 1 |
| V-05 | Exporter reachable | `curl -s 127.0.0.1:9835/metrics \| grep -c nvidia` | > 0 |
| V-06 | Tunnel overhead | `tools/llm-bench rtt` (100 × `/api/version`) | p50 and p95 recorded (used to separate network from model latency) |
| V-07 | Drop and recover | `docker compose restart mesh-tunnel` while polling `/api/version` | Recovers automatically; recovery time recorded (T0-TUN-02) |
| V-08 | Restriction works | From the tunnel container: `ssh -i … mesh-tunnel@host` (no `-N`) and `-L` to a different port | Shell refused; non-allowed forward refused |
| V-09 | Remote exposure | Human runs `ss -ltnp` on the GPU server | 11434 and 9835 bound to 127.0.0.1 only |
| V-10 | GPU dedicated | `nvidia-smi --query-compute-apps=pid --format=csv,noheader` on the server, with nothing running | Empty apart from Ollama's runner when a model is loaded |

## Part D — Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `ExitOnForwardFailure` loop | Port already bound (host tunnel and container both running) | Run only one tunnel (B2 **or** B3) |
| `Host key verification failed` | known_hosts mismatch | Re-check the fingerprint with the human; never disable `StrictHostKeyChecking` |
| `administratively prohibited: open failed` | `PermitOpen` / `permitopen` mismatch | Ports must match on both sides |
| Generation works from the host but not the gateway | Gateway upstream URL wrong | `MESH_GATEWAY_UPSTREAM=http://mesh-tunnel:11434` (B2) or the bridge IP (B3) |
| First request slow, later fast | Model loading | `OLLAMA_KEEP_ALIVE=-1`; warm up after start (the gateway `/ready` does it) |
| `ollama ps` shows < 100% GPU | Context × slots too large → CPU offload | Lower `OLLAMA_CONTEXT_LENGTH` or `NUM_PARALLEL` (from E0); never accept offload |
