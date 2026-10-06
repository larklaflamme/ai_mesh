# AI Mesh — prototype

AI Mesh is an on-prem platform in which a mesh of AI agents, running on local open-weights models,
takes business requirements and designs, builds, tests and releases Python/FastAPI + SvelteKit
systems. It is verification-first: humans approve the executable definition of "done", and agents
iterate against it. This repository holds the prototype: the `mesh` control plane (`platform/`),
the LLM gateway (`gateway/`), the worker runtime (`worker_runtime/`), infrastructure, and the
benchmark used to measure it.

- [`CLAUDE.md`](CLAUDE.md) — working instructions and ground rules
- [`design/README.md`](design/README.md) — design artifacts 00–08
- [`design/09-implementation-guide/README.md`](design/09-implementation-guide/README.md) — implementation guide (phases, work packages, tests)
- [`PROGRESS.md`](PROGRESS.md) — progress tracker and human checkpoints

Quick start: `make env && conda activate ai-mesh && make install && make check`.
