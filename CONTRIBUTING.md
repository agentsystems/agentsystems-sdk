# Contributing to AgentSystems SDK

Thanks for helping make the AgentSystems SDK awesome! This guide covers local development, testing, and the guarded release workflow.

---
## 1. Local development environment

### Quick dev environment setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pre-commit install
pre-commit run --all-files
```

### Prerequisites

* **Python ≥ 3.11** (matching the runtime in `pyproject.toml`)
* **Docker Desktop** (for pulling and running the AgentSystems images)
* **pipx** (recommended for an isolated CLI install)
* A **GitHub Personal Access Token (PAT)** and **Docker Org Access Token (OAT)** when resources are private.

### Clone & editable install

```bash
# fork & clone the repo
 git clone git@github.com:agentsystems/agentsystems-sdk.git
 cd agentsystems-sdk

# create / update a virtualenv managed by pipx
 pipx uninstall agentsystems-sdk || true
 pipx install --editable .

# verify
 agentsystems --version
```

Tokens can be supplied via `--gh-token / --docker-token` flags or loaded automatically from environment variables / `.env`.

---
## 2. Running and testing the CLI

### Initialise deployment template

```bash
agentsystems init ~/tmp/agent-platform-deployments           # interactive
cd ~/tmp/agent-platform-deployments
cp .env.example .env                               # create your config
# edit .env with GitHub and Docker tokens

# headless / CI
GITHUB_TOKEN=ghp_xxx DOCKER_OAT=st_xxx \
  agentsystems init /opt/agentsystems/engine --gh-token "$GITHUB_TOKEN" --docker-token "$DOCKER_OAT"
```

### Bring the platform up

```bash
cd ~/tmp/agent-platform-deployments   # or pass the path explicitly

# default: detached, returns immediately (requires .env in this directory)
agentsystems up

# watch logs in foreground
agentsystems up --foreground

# restart stack (down + up, detached)
agentsystems restart

# restart stack and remove volumes (confirmation required)
agentsystems restart --volumes

# stop everything (keep volumes)
agentsystems down

# stop and remove volumes (confirmation required)
agentsystems down --volumes
```

`DOCKER_OAT` must have the **"Read public repositories"** permission so pulls for `postgres`, `redis`, etc. succeed.

The CLI prints Rich progress bars, masks secrets, and logs into Docker with `--password-stdin`.

---
## 3. Coding standards

* Keep changes minimal and focused on the task.
* Use [Black](https://black.readthedocs.io/) defaults for formatting (`black .`).
* Follow conventional commit messages (e.g. `feat: add up command`).
* Update `NOTICE` when adding new runtime dependencies (license + copyright).

---
## 4. Release workflow (branch-based)

Releases are driven by `./scripts/release.sh`.  The script now **requires** a dedicated `release/<version>` branch and creates the Git tag (`v<version>`) automatically.  Flow:

1. **Create a release branch** and bump version:

   ```bash
   git checkout -b release/0.2.19
   # edit pyproject.toml -> version = "0.2.19"
   git commit -am "chore: bump version to 0.2.19"
   ```

2. **Dry-run locally** (sanity check, no push):

   ```bash
   ./scripts/release.sh --version 0.2.19 --dry-run
   ```

3. **Publish to TestPyPI**:

   ```bash
   ./scripts/release.sh --version 0.2.19 --test
   # verify
   pipx install --index-url https://test.pypi.org/simple/ agentsystems-sdk==0.2.19
   agentsystems --version
   ```

4. Open a **PR from `release/0.2.19` → `main`**.  CI will build & install the wheel and run smoke tests.
5. After review & green CI, **merge the PR**.  The merge keeps the tag intact; the branch can be deleted.
6. **Promote to production PyPI** from the same branch/tag:

   ```bash
   ./scripts/release.sh --version 0.2.19 --prod
   ```

The script aborts if:
* Working tree is dirty.
* Version in `pyproject.toml` doesn’t match `--version`.
* Git tag `v<version>` already exists.
* Version already exists on the target index.

Environment requirements:

* A **virtual environment** activated (e.g. `python3 -m venv .venv && source .venv/bin/activate`). This avoids the PEP 668 "externally-managed environment" error on macOS/Homebrew Python.
* `PYPI_API_TOKEN` or `~/.pypirc` for upload.
* Clean `git` status (no uncommitted files).

---
## 5. Updating documentation

---

## 6. Roadmap

| Timeline | Item |
|----------|------|
| short-term | **Port-probe startup fallback** – CLI attempts a TCP connect to the agent port when no Docker HEALTHCHECK is present. |
| short-term | **CI end-to-end tests** – pytest workflow that runs `agentsystems up`, waits for readiness, then verifies `/agents` and a sample agent response. |
| short-term | **Config schema versioning** – add a `version:` field to `agentsystems-config.yml` and warn when mismatched. |
| short-term | **Secrets helper** – `agentsystems secrets set NAME=value` for safe, masked updates to `.env`. |
| mid-term   | **Marketplace catalog endpoint** – lightweight HTTP endpoint that lists containers available via each `registry_connection`, served as cards/links. |
| research   | **Scale-to-zero/on-demand agents** – design auto-start & idle shutdown for heavy models. |



* **README.md** – user-centric CLI docs (update options, examples, etc.).
* **CONTRIBUTING.md** – this file.
* Feel free to include asciinema gifs or screenshots of the Rich UI, but keep them lightweight.

---
## 6. Support

If you hit issues with the release script, reach out in the **#sdk** Slack channel or open a draft PR for discussion.

Happy hacking!
