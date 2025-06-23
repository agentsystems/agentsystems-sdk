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

| Command | Description |
|---------|-------------|
| `agentsystems init [TARGET_DIR]` | Clone the deployment template and pull required Docker images into `TARGET_DIR`. |
| `agentsystems up [PROJECT_DIR]` | Start the full AgentSystems platform with Docker Compose (detached by default). |
| `agentsystems down [PROJECT_DIR]` | Stop containers (`docker compose down`), optionally `-v` to delete volumes. |
| `agentsystems version` | Show the installed SDK version. |

### `up` options

```
--detach / --foreground   Run containers in background (default) or stream logs
--fresh                   docker compose down -v before starting
--env-file PATH           Pass a custom .env file to Compose
--docker-token TEXT       Docker Hub Org Access Token (env `DOCKER_OAT`)
--no-login                Skip Docker login even if token env is set
```

Run `agentsystems up --help` for the authoritative list.

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

