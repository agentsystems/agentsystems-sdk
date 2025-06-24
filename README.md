# AgentSystems SDK & CLI

The AgentSystems **SDK** is a single-install Python package that provides:

* `agentsystems` — a polished command-line interface for bootstrapping and operating an AgentSystems deployment.
* A small helper library (future) so you can embed AgentSystems clients in your own code.

The CLI is designed to work **both interactively** (laptops) and **non-interactively** (CI, cloud VMs).


## Quick install (via pipx)

```bash
python3 -m pip install --upgrade pipx      # one-time setup
pipx install agentsystems-sdk              # installs isolated venv and the `agentsystems` app

# verify
agentsystems --version
```



### Install from source (contributors)

```bash
# in the repository root
pipx uninstall agentsystems-sdk  # if previously installed
pipx install --editable .        # live-reloads on file changes
```

---
## CLI commands

All commands are available through `agentsystems` (or the shorter alias `agntsys`).

| Command | Description |
|---------|-------------|
| `agentsystems init [TARGET_DIR]` | Clone the deployment template and pull required Docker images into `TARGET_DIR`. After it finishes, **run `cp .env.example .env` inside the directory and populate required tokens**. |
| `agentsystems up [PROJECT_DIR]` | Start the platform **plus Langfuse tracing stack** (`docker compose up`). **Waits for the gateway to be ready by default (spinner)**. Pass `--no-wait` to skip readiness wait or `--no-langfuse` to disable tracing. Requires a populated `.env` file (or use `--env-file PATH`). |
| `agentsystems down [PROJECT_DIR]` | Stop containers (`docker compose down`). Pass `-v/--volumes` to delete named volumes (interactive confirmation). |
| `agentsystems logs [PROJECT_DIR]` | Stream or view recent logs (`docker compose logs`). |
| `agentsystems status [PROJECT_DIR]` | List running containers and state (`docker compose ps`). |
| `agentsystems restart [PROJECT_DIR]` | Quick bounce (`down` → `up`). **Waits for readiness by default**. Add `-v/--volumes` to delete volumes (confirmation) or `--no-wait` to skip. **Requires `.env`**. |
| `agentsystems info` | Show environment diagnostics (SDK, Python, Docker). |
| `agentsystems version` | Show the installed SDK version. |

### `up` options

```
--detach / --foreground   Run containers in background (default) or stream logs
--fresh                   docker compose down -v before starting
--env-file PATH           Pass a custom .env file to Compose
--wait / --no-wait        Wait for gateway readiness (default: --wait)
--docker-token TEXT       Docker Hub Org Access Token (env `DOCKER_OAT`)
--no-login                Skip Docker login even if token env is set
--no-langfuse             Skip the Langfuse tracing stack (core services only)
```

Run `agentsystems up --help` for the authoritative list.

---
### Tracing & observability (Langfuse)

By default the CLI starts the [Langfuse](https://langfuse.com/) tracing stack alongside the core services and exposes its UI at <http://localhost:3000>. You can explore request traces and performance metrics there while developing.

If you prefer to run only the core platform (for example on a small CI runner) pass `--no-langfuse` to any stack command (`up`, `down`, `restart`, `logs`, `status`).


### Example: start and watch logs

```bash
agentsystems up --foreground    # run inside the deployment dir
```

### Example: fresh restart in CI

```bash
agentsystems up /opt/agent-platform-deployments --fresh --detach
```

---
### `init` options

```
--gh-token TEXT       GitHub PAT for private template repo (env `GITHUB_TOKEN`)
--docker-token TEXT   Docker Org Access Token (env `DOCKER_OAT`)
--branch TEXT         Template branch to clone (default: `main`)
```

If a flag is omitted the CLI falls back to environment variables / `.env`. When running
interactively it will **only prompt if the unauthenticated clone/pull fails**.

### Example: interactive laptop

```bash
agentsystems init
# prompts for directory and, only if needed, tokens
```

### Example: scripted cloud VM / CI

```bash
export GITHUB_TOKEN=ghp_xxx          # or use --gh-token
export DOCKER_OAT=st_xxx             # or use --docker-token

agentsystems init /opt/agentsystems/engine \
  --gh-token "$GITHUB_TOKEN" \
  --docker-token "$DOCKER_OAT"
```

---
## Environment variables & `.env`

Docker Hub token *must* include the "Read public repositories" permission so pulls for `postgres`, `redis`, etc. succeed.

| Variable | Purpose |
|----------|---------|
| `GITHUB_TOKEN` | GitHub Personal Access Token with **repo:read** scope |
| `DOCKER_OAT`   | Docker Hub Org Access Token for `agentsystems` org |

Create a local `.env` (git-ignored) so `agentsystems` picks them up automatically:

```ini
GITHUB_TOKEN=ghp_xxx
DOCKER_OAT=st_xxx
```

---
## Updating / upgrading

```bash
pipx upgrade agentsystems-sdk           # upgrade from PyPI
# or, from source repo:
pipx reinstall --editable .
```

---
## Security notes

* The CLI never prints your secrets. GitHub PATs are masked and Docker login uses `--password-stdin`.
* Delete tokens / `.env` after the resources become public.

---
## Support & feedback

Open an issue or discussion in the private GitHub repository.
Contributions welcome—see [CONTRIBUTING.md](CONTRIBUTING.md).

