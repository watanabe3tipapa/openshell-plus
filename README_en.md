# openshell-plus

**OpenShell, from the browser.**

openshell-plus is a web UI/UX for [NVIDIA OpenShell](https://github.com/NVIDIA/OpenShell) that moves sandbox management and command execution into a single browser dashboard. One FastAPI + Vanilla JS application runs unchanged on local, Cloudflare Tunnel, Vercel, and Google Colab.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-v0.1.0-blue.svg)](https://github.com/watanabe3tipapa/openshell-plus/releases)
[![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-live-blue.svg)](https://watanabe3tipapa.github.io/openshell-plus/)
[![GitHub](https://img.shields.io/github/issues/watanabe3tipapa/openshell-plus.svg)](https://github.com/watanabe3tipapa/openshell-plus/issues)

[日本語](README.md) | [English](README_en.md)

**Quick links:** [Live site](https://watanabe3tipapa.github.io/openshell-plus/) · [Open in Colab](https://colab.research.google.com/github/watanabe3tipapa/openshell-plus/blob/main/deploy/colab/openshell_colab.ipynb) · [OpenShell](https://github.com/NVIDIA/OpenShell) · [OpenShell docs](https://docs.nvidia.com/openshell/latest/)

## Concept

### Why "Plus"

OpenShell is a powerful sandbox runtime, but its surfaces are CLI-first. Keeping track of what is running right now means holding state in your head. openshell-plus adds one browser screen on top of it.

**OpenShell is unchanged. Only the operator's experience improves.** That is the "plus".

| Activity | openshell-plus counterpart |
|---|---|
| Create a sandbox | A form for name and exposed port calls `client.create()` |
| See status | A list with `phase` rendered as a localized label, auto-refreshing |
| Work in a shell | A WebSocket console streaming stdout and stderr |
| Find the public URL | The URL of the port exposed at creation, fetched from the API |
| Clean up | Delete behind a confirmation dialog |
| Publish it | Four targets: loopback, Cloudflare Tunnel, Vercel, Colab |

### Where to run it

All four targets switch from the same application code. Only `OSUI_MODE` and the launch method change — no code edits.

| Target | Backend | Launch | Use |
|---|---|---|---|
| Local | OpenShell | `./scripts/run-local.sh` → `http://127.0.0.1:8080` | Real connection to a local gateway. No port forwarding |
| Cloudflare Tunnel | OpenShell | `./scripts/run-cloudflare.sh` | Expose the local gateway over HTTPS. Token required |
| Vercel | demo | `./scripts/deploy-vercel.sh` | Demo and UI preview. Automatic HTTPS |
| Google Colab | demo | Run the notebook → embed an iframe | Demo in the browser only. Works on GPU runtimes |

### A Corrector for Stale Docs

This repository also addresses the fact that pseudocode in a design guide often does not compile. The differences between the API sketched in `openshell-uiux-guide.html` and the real SDK are already resolved in the implementation.

- `SandboxSession(client, sandbox_id)` does not exist — `client.create()` returns a `SandboxRef`
- get / list / delete / exec identify a sandbox by `name` plus `workspace`, never by raw UUID
- `status.phase` is an int enum, not a string
- The image is set with `--from` (default `nvcr.io/nvidia/base/ubuntu:24.04`)
- There is no `openshell inference set` command

## Features

### Backends

- `core/backends/base.py` defines a `SandboxBackend` Protocol, so the OpenShell SDK and an in-memory demo satisfy one contract
- `core/factory.py` probes the gateway with a health call at startup and falls back to demo when unreachable (`OSUI_REQUIRE_GATEWAY=true` switches to fail-fast)
- The synchronous SDK is wrapped with `asyncio.to_thread`, keeping the API layer fully async
- `status.phase` is mapped through `phase_label()` for display

### API and transports

- REST for CRUD, WebSocket for streaming exec, SSE as an alternative stream
- **WebSocket is the primary transport.** Cloudflare Quick Tunnels do not support SSE, so `OSUI_SSE_ENABLED=false` can disable it
- `/api/health` is reachable without auth, which makes it usable as a load-balancer probe

### Auth and exposure safety

- Setting `OSUI_AUTH_TOKEN` protects every `/api/*` route and the WebSocket handshake
- **Binding to a non-loopback address without a token is refused** (`SettingsError`), so a public misconfiguration fails at construction time
- Browsers cannot attach headers to a WebSocket, so `Sec-WebSocket-Protocol: bearer.*` and `?token=` are also accepted
- mTLS and OIDC client credentials are supported, and the "TLS required for non-loopback gateways" rule is validated at startup

### Bundled content

- **[Colab notebook](deploy/colab/openshell_colab.ipynb)** — runs the demo in the browser. Public tunnels are intentionally disabled
- **`policy/ui-policy.yaml`** — an OpenShell policy in the current `version: 1` schema
- **`deploy/Dockerfile.ui`** — an image for running the UI inside an OpenShell sandbox
- **`deploy/cloudflared/config.yml.example`** — named-tunnel ingress example
- **[Landing page](site/)** — deployed to GitHub Pages automatically
- **[Architecture diagram](site/diagrams/openshell-plus-architecture.html)** — browser to FastAPI to gateway to isolation boundary (generated with Archify, also embedded in the LP)

## Try it on Google Colab

No local clone needed — run the demo straight from the browser.

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/watanabe3tipapa/openshell-plus/blob/main/deploy/colab/openshell_colab.ipynb)

- **Notebook** [`deploy/colab/openshell_colab.ipynb`](deploy/colab/openshell_colab.ipynb) — run the cells in order to install the package, start in demo mode, wait for the port, and embed the dashboard in an iframe

## Installation

### Prerequisites

| Tool | Required version | Check command |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | any (recommended) | `uv --version` |
| [OpenShell CLI](https://docs.nvidia.com/openshell/dev/about/installation) | latest | `openshell --version` |
| Python | >= 3.12 | `python3 --version` |
| Docker / OrbStack | optional (to run sandboxes) | `docker info` |
| Git | optional (deploy / contribution) | `git --version` |

You can also install the OpenShell CLI with the packaged installer.

```bash
curl -LsSf https://raw.githubusercontent.com/NVIDIA/OpenShell/main/install.sh | sh
openshell status
```

### Basic steps

1. Get the repository

```bash
git clone https://github.com/watanabe3tipapa/openshell-plus.git
cd openshell-plus
```

2. Install dependencies

```bash
uv sync --all-extras
```

3. Launch

```bash
./scripts/run-local.sh
```

Open `http://127.0.0.1:8080`. If the gateway is unreachable the app switches to **demo mode** with in-memory sandboxes, so the UI stays usable.

How a request flows:

```
Browser ──REST/WS──→ FastAPI ──→ Backend (OpenShell SDK / demo)
                                      │
                                      └→ OpenShell gateway → sandbox
```

### Key commands

| Command | Purpose |
|---|---|
| `./scripts/run-local.sh` | Launch on loopback (demo fallback when the gateway is unreachable) |
| `./scripts/run-cloudflare.sh` | Launch behind a named tunnel (pass `quick` for a Quick Tunnel) |
| `./scripts/deploy-vercel.sh` | Production deploy to Vercel (verifies the token first) |
| `uv run python -m openshell_ui` | Launch directly without the wrapper scripts |
| `uv run pytest` | Run the tests |
| `uv run ruff check .` | Lint |
| `uv run ruff format --check .` | Format check |
| `uv run pyright` | Type check |

### Publish

Pushing to `main` deploys `site/` to GitHub Pages automatically (`.github/workflows/pages.yml`).

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness, backend kind, gateway reachability (no auth) |
| GET | `/api/config` | Run mode, capabilities, workspace, auth state |
| GET | `/api/sandboxes` | List sandboxes |
| POST | `/api/sandboxes` | Create a sandbox |
| GET | `/api/sandboxes/{name}` | Fetch one sandbox |
| DELETE | `/api/sandboxes/{name}` | Delete a sandbox |
| POST | `/api/sandboxes/{name}/exec` | Run a command, aggregated result |
| WS | `/api/sandboxes/{name}/exec` | Streaming command output (primary path) |
| GET | `/api/sandboxes/{name}/exec/stream` | SSE variant |

Send `{"command": ["ls","-la"], "workdir": null, "timeout_seconds": 60}` and receive
`{"type": "stdout"|"stderr"|"exit", "data": "...", "exit_code": null|int}`. Clients must be ready to reconnect
because Vercel closes connections at `maxDuration`.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `OSUI_MODE` | auto | `local` / `cloudflare` / `vercel` / `colab` / `sandbox` |
| `OSUI_HOST` / `OSUI_PORT` | `127.0.0.1` / `8080` | Bind address. A token is required off loopback |
| `OSUI_AUTH_TOKEN` | (optional) | Setting it protects every API route and the console |
| `OSUI_DEMO` | `false` | Force the demo backend |
| `OSUI_REQUIRE_GATEWAY` | `false` | Disable the demo fallback and fail instead |
| `OSUI_WORKSPACE` | `default` | Target workspace |
| `OSUI_SSE_ENABLED` | `true` | Whether the SSE endpoint is exposed |
| `OSUI_GATEWAY_ENDPOINT` | (SDK auto-detect) | Set an explicit gateway endpoint |
| `OSUI_GATEWAY_CA_CERT` / `_CERT` / `_KEY` | (optional) | CA verification and mTLS. `_CERT` and `_KEY` must be set together |
| `OSUI_EXEC_DEFAULT_TIMEOUT` / `OSUI_EXEC_MAX_TIMEOUT` | `60` / `1800` | Default and maximum command timeout in seconds |
| `OSUI_OIDC_ISSUER` / `_CLIENT_ID` / `_CLIENT_SECRET` / `_AUDIENCE` | (optional) | OIDC client credentials |

See `.env.example` for the full list.

## Documentation

For newcomers, reading in this order gives you the full picture.

1. [Live site](https://watanabe3tipapa.github.io/openshell-plus/) — features, deployment targets, environment variables
2. `README.md` (Japanese) — concept and operations
3. `openshell-uiux-guide.html` — the original UI/UX guide
4. [DEV-MEMO.md](DEV-MEMO.md) — design decisions and verification notes per phase

## Contributing

Contributions are welcome. Before making major changes, please open an [issue](https://github.com/watanabe3tipapa/openshell-plus/issues) to share your plans first.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Pass every quality gate
5. Push to the branch and open a Pull Request

```bash
uv sync --all-extras
uv run pytest        # 147 tests
uv run ruff check .
uv run ruff format --check .
uv run pyright       # type check, zero errors
```

The tests use the demo backend and never contact a gateway. `make_settings()` in
`tests/helpers.py` guarantees the equivalent of `OSUI_DEMO=true`.

## Contact

- GitHub: https://github.com/watanabe3tipapa/openshell-plus
- Published site: https://watanabe3tipapa.github.io/openshell-plus/

## License

Distributed under the MIT License — see the [LICENSE](LICENSE) file for details.
