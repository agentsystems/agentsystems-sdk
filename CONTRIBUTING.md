# Contributing to AgentSystems SDK

Thanks for helping make the AgentSystems SDK awesome! This guide covers local development, testing, and the guarded release workflow.

---
## 1. Local development environment

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

# headless / CI
GITHUB_TOKEN=ghp_xxx DOCKER_OAT=st_xxx \
  agentsystems init /opt/agentsystems/engine --gh-token "$GITHUB_TOKEN" --docker-token "$DOCKER_OAT"
```

### Bring the platform up

```bash
cd ~/tmp/agent-platform-deployments   # or pass the path explicitly

# default: detached, returns immediately
agentsystems up

# watch logs in foreground
agentsystems up --foreground

# fresh restart (down -v, then up -d)
agentsystems up --fresh

# stop everything and remove volumes
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
## 4. Release workflow

All releases are driven by the shell script `./scripts/release.sh` which enforces version safety and PyPI hygiene.

1. **Bump version** inside `pyproject.toml` (`<major>.<minor>.<patch>`).
2. **Dry-run** everything locally:

   ```bash
   ./scripts/release.sh --version X.Y.Z --dry-run
   ```

3. **Publish to TestPyPI** (creates/ re-uses git tag):

   ```bash
   ./scripts/release.sh --version X.Y.Z --test
   pipx install --index-url https://test.pypi.org/simple/ agentsystems-sdk==X.Y.Z
   ```

4. Verify install & basic commands.
5. When satisfied, **promote the same tag to production PyPI**:

   ```bash
   ./scripts/release.sh --version X.Y.Z --prod
   ```

   The script will refuse to run if the working tree is dirty, if the tag doesn’t match `HEAD`, or if the version already exists on PyPI.

Environment requirements:

* `PYPI_API_TOKEN` or `~/.pypirc` for upload.
* Clean `git` status (no uncommitted files).

---
## 5. Updating documentation

* **README.md** – user-centric CLI docs (update options, examples, etc.).
* **CONTRIBUTING.md** – this file.
* Feel free to include asciinema gifs or screenshots of the Rich UI, but keep them lightweight.

---
## 6. Support

If you hit issues with the release script, reach out in the **#sdk** Slack channel or open a draft PR for discussion.

Happy hacking!
