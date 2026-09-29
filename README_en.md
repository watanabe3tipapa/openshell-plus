# openshell-plus

**OpenShell, from the browser.**

openshell-plus is a web UI/UX for [NVIDIA OpenShell](https://github.com/NVIDIA/OpenShell) that moves sandbox management and command execution into a single browser dashboard. One FastAPI + Vanilla JS application runs unchanged on local, Cloudflare Tunnel, Vercel, and Google Colab.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-v0.1.0-blue.svg)](https://github.com/watanabe3tipapa/openshell-plus/releases)
[![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-live-blue.svg)](https://watanabe3tipapa.github.io/openshell-plus/)
[![GitHub](https://img.shields.io/github/issues/watanabe3tipapa/openshell-plus.svg)](https://github.com/watanabe3tipapa/openshell-plus/issues)
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/watanabe3tipapa/openshell-plus/blob/main/deploy/colab/openshell_colab.ipynb)

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
- **[USAGE.md](USAGE.md)** — recipes by goal, constraints, troubleshooting (Japanese)
- **[Architecture diagram](site/diagrams/openshell-plus-architecture.html)** — browser to FastAPI to gateway to isolation boundary (generated with Archify, also embedded in the LP)

## Try it on Google Colab (3 steps, no clone)

The demo runs in the browser. There is nothing to clone or build locally.

| Step | Action | Time |
|---|---|---|
| 1 | Click the badge below to open the notebook in Colab | a few seconds |
| 2 | Choose "Runtime" then "Run all" | 1-2 minutes |
| 3 | The dashboard appears in an iframe under the output cell | the page stays as is |

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/watanabe3tipapa/openshell-plus/blob/main/deploy/colab/openshell_colab.ipynb)

Once step 3 finishes, create a sandbox named `demo-box` in the list and run `ls` in the console. A demo response means the app started correctly.

The cells are already in dependency order, so there is no need to pick them one by one. What they do:

1. Install the package from `git+https://github.com/watanabe3tipapa/openshell-plus`
2. Set `OSUI_DEMO=true` and `OSUI_MODE=colab`, then start uvicorn
3. Wait up to 30 seconds for `127.0.0.1:8080` to accept connections
4. Embed the dashboard in an iframe

**Worth knowing before you run it**

- **The runtime shuts down when idle and is lost when the VM is reset.** To continue, run "Run all" again
- Colab has neither a Docker daemon nor an OpenShell gateway, so the app starts with the demo backend. No real sandbox is involved
- Public tunnels are intentionally disabled because the Colab terms prohibit them. See `USAGE.md` and the notebook
- File: [`deploy/colab/openshell_colab.ipynb`](deploy/colab/openshell_colab.ipynb)

The same steps work on a GPU runtime. Neither the screen nor the responses depend on the GPU.

## Installation

### Prerequisites

| Tool | Required version | Check command |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | any (recommended) | `uv --version` |
| [OpenShell CLI](https://docs.nvidia.com/openshell/dev/about/installation) | latest | `openshell --version` |
| Python | >= 3.12 | `python3 --version` |
| Docker Engine | optional (to run sandboxes; OpenShell requires 28.0 or later) | `docker version` |
| [OrbStack](https://orbstack.dev/) | optional (recommended way to get Docker on macOS) | `orb version` |
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

## Environment setup on macOS with OrbStack

To actually run sandboxes on macOS, using [OrbStack](https://orbstack.dev/) as the Docker runtime keeps the procedure shortest. The same `docker` commands work as with Docker Desktop.

### 1. Install OrbStack

```bash
brew install orbstack
open -a OrbStack
```

Use the `orb` command to start and stop without the GUI (for CI and headless environments).

```bash
orb            # start (same as orb start)
orb stop       # stop
```

Auto-update does not run without the GUI. If you operate from the CLI only, update through Homebrew.

```bash
brew upgrade --greedy orbstack
```

### 2. Verify the Docker engine is running

```bash
orb version
docker context ls
docker info
```

OrbStack creates a Docker context named `orbstack` and uses it automatically for `docker` commands run from the terminal. If `orbstack` is missing from `docker context ls`, select it explicitly.

```bash
docker context use orbstack
```

If `docker info` does not respond, the engine is stopped.

```bash
orb start
orb restart docker
orb logs docker
```

**OpenShell requires Docker Engine 28.0 or later.** Check the version.

```bash
docker version --format 'server: {{.Server.Version}}'
```

### 3. Check the socket path (the most common macOS failure)

Without an explicit `socket_path`, the OpenShell Docker driver auto-detects a socket and prefers `/var/run/docker.sock`. OrbStack only creates a symlink there **if you have admin access**. Without that symlink, OpenShell fails to find the socket and cannot create sandboxes.

```bash
ls -l /var/run/docker.sock 2>/dev/null || echo 'not created'
```

If it prints `not created`, point the gateway configuration at OrbStack's socket. The gateway reads `~/.config/openshell/gateway.toml` first and falls back to the Homebrew location (`$(brew --prefix)/var/openshell/gateway.toml`). Creating `~/.config/openshell/gateway.toml` is the reliable option.

```bash
mkdir -p ~/.config/openshell
```

`~/.config/openshell/gateway.toml`:

```toml
[openshell]
version = 2

[openshell.gateway]
compute_driver = "docker"

[openshell.drivers.docker]
socket_path = "/Users/your-username/.orbstack/run/docker.sock"
```

**TOML does not expand `~` or shell variables.** Write the absolute path. Print the real value with:

```bash
echo "$HOME/.orbstack/run/docker.sock"
```

Validate the file before restarting the gateway.

```bash
openshell-gateway config preflight --path ~/.config/openshell/gateway.toml
```

### 4. Install the OpenShell gateway

```bash
curl -LsSf https://raw.githubusercontent.com/NVIDIA/OpenShell/main/install.sh | sh
openshell status
```

On macOS the installer uses Homebrew and runs the gateway as a Homebrew service on `https://localhost:17670`.

```bash
brew services list
brew services restart openshell
```

### 5. Launch openshell-plus

```bash
git clone https://github.com/watanabe3tipapa/openshell-plus.git
cd openshell-plus
uv sync --all-extras

export OSUI_GATEWAY_ENDPOINT=127.0.0.1:17670
export OSUI_REQUIRE_GATEWAY=true
./scripts/run-local.sh
```

Setting `OSUI_REQUIRE_GATEWAY=true` stops the app from quietly falling back to the demo backend when the connection fails. Confirm a real connection by checking that `backend` is `openshell` in `/api/health`.

```bash
curl -s http://127.0.0.1:8080/api/health | python3 -m json.tool
```

### 6. Check your CPU architecture

```bash
uname -m
```

| Output | Meaning | Images |
|---|---|---|
| `arm64` | Apple Silicon | OrbStack runs x86_64 images through Rosetta, so `linux/amd64`-only images still work |
| `x86_64` | Intel Mac | `linux/amd64` is the default. `linux/arm64`-only images do not run |

OpenShell's default sandbox image `nvcr.io/nvidia/base:ubuntu:24.04` is multi-architecture, so it works on either Mac. To pin amd64, use the environment variable:

```bash
export DOCKER_DEFAULT_PLATFORM=linux/amd64
```

### Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `docker info` does not respond | Engine is stopped | `orb start` → `orb restart docker` → `orb logs docker` |
| `orbstack` missing from `docker context ls` | CLI installed on its own | `brew reinstall orbstack` to recreate the context |
| Sandbox creation fails with a Docker connection error | `/var/run/docker.sock` is missing | Set `socket_path` in the TOML as described in §3 |
| TOML edits have no effect | Wrong configuration file location | Put it at `~/.config/openshell/gateway.toml`. Precedence is `--config` / `OPENSHELL_GATEWAY_CONFIG` → TOML → built-in default |
| `openshell status` cannot connect | Homebrew service is stopped | `brew services restart openshell` |
| Reports `server: 27.x` | Engine older than 28.0 | Update OrbStack to the latest version |
| Push to a private registry fails | Different credential store | OrbStack uses `osxkeychain`; run `docker login` again |
| x86_64-only image fails on an Intel Mac | Intel Macs cannot run arm64 | Pick an image with a `linux/amd64` variant |

## OrbStack and AI agents

openshell-plus exists to run agent workloads in sandboxes. OrbStack is explicitly designed with that use case in mind, which makes it fit better than other Docker runtimes.

### OrbStack lists AI agents first among its isolated use cases

An isolated machine is a Linux environment cut off from the macOS file system. OrbStack's documentation lists **"AI agents that run shell commands on their own"** as its first use case, followed by untrusted dependencies and build scripts, code review of unfamiliar projects, and experiments you would rather not have touch your home directory. The reasoning is supply-chain risk: a single `postinstall` script in a dependency can read your files, SSH keys, and environment variables.

```bash
orb create --isolated ubuntu agent-sandbox
```

An isolated machine differs from a normal one in four ways.

| Normal machine | Isolated machine |
|---|---|
| Mounts your Mac's file system at `/mnt/mac` | Does not mount it |
| Can run `mac` commands against macOS | Cannot |
| Forwards the SSH agent by default | Disabled by default |
| Passes through USB, serial, and sound | Does not |

Internet access, `.orb.local` domains, and SSH plus `orb` access from your Mac still work. Add only what you need.

```bash
# Share just the working folder
orb create --isolated --mount ~/project:/work ubuntu agent-sandbox

# Also block other machines and host IPs, keeping only internet access
orb create --isolated --isolate-network ubuntu agent-sandbox

# Allow the SSH agent only when git push is required
orb create --isolated --forward-ssh-agent ubuntu agent-sandbox
```

Settings can be changed later on an existing machine.

```bash
orb config set machine.agent-sandbox.isolated true
orb config set machine.agent-sandbox.isolate_network true
```

**However, an isolated machine is not a complete security boundary.** All machines and containers share one kernel inside a single Linux VM. OrbStack states this itself and recommends a full VM with its own kernel for code that actively tries to escape the sandbox. It suits ordinary untrusted code and agents; it is not meant for malware analysis.

### Pairing it with OpenShell's MicroVM driver gives two layers

OpenShell has a `vm` driver that isolates each sandbox in its own lightweight VM, using Hypervisor.framework on macOS. Running the gateway inside an OrbStack isolated machine blocks the agent's path to the host in two stages.

```toml
[openshell.gateway]
compute_driver = "vm"

[openshell.drivers.vm]
default_image = "nvcr.io/nvidia/base:ubuntu:24.04"
```

`vm` is never auto-detected, so it must be set explicitly (the `OPENSHELL_COMPUTE_DRIVER=vm` environment variable works too). Two caveats:

- **VM sandboxes have no network interface.** All traffic flows through the supervisor on the host. For a proxy, use `http://host.openshell.internal:<port>`
- **`--cpu` and `--memory` are ignored.** Use `vcpus` and `mem_mib`

### Speed and power

Like WSL 2, OrbStack uses a lightweight Linux VM with a shared kernel. Its core services are purpose-built in Swift, Go, Rust, and C, and the Docker engine runs in the same VM as Linux machines. File transfer builds on VirtioFS plus a low-latency bidirectional share of `~/OrbStack` on the macOS side. On Apple Silicon, Rosetta speeds up x86_64 emulation, and KASLR is strengthened without the KPTI syscall overhead.

OrbStack publishes its own performance and power benchmarks using real development workloads: provisioning Open edX, building the PostHog image, Kubernetes with Helm, Supabase, and a 38-service Sentry stack. The measurements were taken in August 2023 comparing OrbStack v0.17.0 against Docker Desktop v4.22.0 on an M1 Max MacBook Pro. Numbers depend strongly on the workload, so read the [official benchmarks](https://docs.orbstack.dev/benchmarks) before drawing conclusions.

Agents start and stop frequently, so low startup cost matters in practice. Machines can be created and destroyed in under a minute, and background CPU usage with no containers running is reported at around 0.1% on M1.

### Operational rules for running agents

- **Never expose the engine to the network.** Adding `tcp://0.0.0.0:2375` to the OrbStack `hosts` config lets any device on your LAN or VPN take full control of your Mac and all its data. OrbStack itself calls this extremely dangerous. Use SSH, or TLS with client authentication, if you need remote access
- **Default agents to `read_only`.** Widen write access only where it is required
- **`bind mount` exposes gateway host files to the sandbox.** It bypasses workspace isolation and filesystem policy, so enable `enable_bind_mounts` only when needed
- **Pass secrets through providers, not environment variables.** Use `openshell provider`

### Summary

| Goal | Recommendation | Reason |
|---|---|---|
| Just get it running | OrbStack + Docker driver | Shortest path, and the `docker` commands work unchanged |
| Run untrusted dependency scripts | OrbStack + isolated machine | The central agent use case OrbStack designs for |
| Analyze code that attempts escape | A full VM such as UTM | A shared kernel cannot contain it |
| Production-grade isolation | MicroVM driver | An independent VM boundary per sandbox |

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
3. `USAGE.md` (Japanese) — recipes by goal, constraints, troubleshooting
4. `openshell-uiux-guide.html` — the original UI/UX guide (pseudocode; the real SDK diff is summarised in the "A Corrector for Stale Docs" section)
5. [DEV-MEMO.md](DEV-MEMO.md) — design decisions and verification notes per phase

## Contributing

Contributions are welcome. Before making major changes, please open an [issue](https://github.com/watanabe3tipapa/openshell-plus/issues) to share your plans first.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Pass every quality gate
5. Push to the branch and open a Pull Request

```bash
uv sync --all-extras
uv run pytest        # 149 tests
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
